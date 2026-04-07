"""
Importação dos relatórios do sistema Flip.
Detecta automaticamente o tipo de serviço pelo nome do arquivo
(ACIC, BFS, CNC, OUVIDORIA, SAC).
"""
import csv
import unicodedata
from datetime import datetime

from .models import Servico, ConsultaProgramada, ImportacaoRelatorio


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def _normalizar(texto):
    """Remove acentos e converte para lowercase para comparação robusta."""
    if not texto:
        return ''
    nfkd = unicodedata.normalize('NFKD', str(texto))
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _parse_data(valor):
    if not valor or str(valor).strip() == '':
        return None
    for fmt in ('%d/%m/%Y %H:%M:%S', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(str(valor).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_coord(valor):
    """Converte string 'lat,lng' em (float, float) ou (None, None)."""
    if not valor or str(valor).strip() == '':
        return None, None
    try:
        partes = str(valor).split(',')
        lat = float(partes[0].strip())
        lng = float(partes[1].strip())
        # Validação básica: coordenadas no Brasil
        if -35.0 <= lat <= 5.0 and -75.0 <= lng <= -28.0:
            return lat, lng
    except (ValueError, IndexError):
        pass
    return None, None


def _decodificar_misto(dados):
    """
    Decodifica arquivos com encoding misto: UTF-8 BOM no cabeçalho
    mas bytes Latin-1 isolados nos dados (padrão dos exports do Flip).
    Usa surrogateescape para capturar bytes inválidos e re-decodifica como Latin-1.
    """
    if dados[:3] == b'\xef\xbb\xbf':
        texto_raw = dados.decode('utf-8-sig', errors='surrogateescape')
    else:
        texto_raw = dados.decode('cp1252', errors='replace')
        return texto_raw

    resultado = []
    for char in texto_raw:
        if '\udc80' <= char <= '\udcff':
            # Byte inválido em UTF-8: reinterpreta como Latin-1
            byte_val = ord(char) - 0xDC00
            resultado.append(bytes([byte_val]).decode('latin-1'))
        else:
            resultado.append(char)
    return ''.join(resultado)


def _ler_csv(arquivo):
    """Lê arquivo CSV com detecção de encoding misto e retorna lista de dicts."""
    dados = arquivo.read()
    conteudo = _decodificar_misto(dados)
    linhas = conteudo.splitlines()
    if not linhas:
        return []
    delimitador = ';' if ';' in linhas[0] else ','
    reader = csv.DictReader(linhas, delimiter=delimitador)
    return list(reader)


def _ler_excel(arquivo):
    import pandas as pd
    df = pd.read_excel(arquivo)
    # Converte tudo para string para uniformidade
    return df.astype(str).replace('nan', '').to_dict('records')


# ---------------------------------------------------------------------------
# Configuração por tipo de serviço Flip
#
# Cada chave é uma lista de nomes NORMALIZADOS (sem acentos, lowercase) que
# podem aparecer nessa coluna, em ordem de prioridade.
# ---------------------------------------------------------------------------

CONFIGURACAO = {
    'ACIC': {
        'numero_os':       ['n_acic', 'n_bfs'],
        'tipo_servico':    ['servico'],
        'status':          ['status'],
        'endereco':        ['endereco'],
        'data_execucao':   ['data_execucao', 'data_confirmacao', 'data_fiscalizacao'],
        'data_finalizacao':['data_confirmacao', 'data_acic'],
        'fiscal':          ['agente_fiscalizador', 'responsavel'],
        'coordenadas':     ['coordenada_vistoria', 'coordenada_resposta', 'coordenada_aceite'],
    },
    'BFS': {
        'numero_os':       ['numero_bfs'],
        'tipo_servico':    ['tipo_servico'],
        'status':          ['status'],
        'endereco':        ['endereco'],
        'data_execucao':   ['data_vistoria', 'data_fiscalizacao'],
        'data_finalizacao':['data_fiscalizacao'],
        'fiscal':          ['fiscal'],
        'coordenadas':     ['coordenadas_vistoria', 'coordenadas_resposta', 'coordenadas_aceite'],
    },
    'CNC': {
        'numero_os':       ['n_cnc', 'n_bfs'],
        'tipo_servico':    ['servico'],
        'status':          ['situacao_cnc'],
        'endereco':        ['endereco'],
        'data_execucao':   ['data_execucao', 'data_fiscalizacao'],
        'data_finalizacao':['data_execucao'],
        'fiscal':          ['fiscal', 'fiscal_contratada'],
        'coordenadas':     ['coordenada'],
    },
    'OUVIDORIA': {
        'numero_os':       ['numero_chamado'],
        'tipo_servico':    ['servico'],
        'status':          ['status'],
        'endereco':        ['endereco'],
        'data_execucao':   ['data_execucao', 'data_realizacao_vistoria'],
        'data_finalizacao':['data_execucao', 'data_realizacao_confirmacao_execucao'],
        'fiscal':          ['usuario_execucao'],
        'coordenadas':     ['coordenadas'],
    },
    'SAC': {
        'numero_os':       ['numero_chamado'],
        'tipo_servico':    ['servico'],
        'status':          ['status'],
        'endereco':        ['endereco'],
        'data_execucao':   ['data_execucao', 'data_realizacao_vistoria'],
        'data_finalizacao':['data_realizacao_confirmacao_execucao', 'data_ultima_atualizacao'],
        'fiscal':          ['usuario_execucao', 'usuario_primeira_vistoria'],
        'coordenadas':     ['coordenadas'],
    },
}


def _detectar_tipo(nome_arquivo):
    nome_upper = nome_arquivo.upper()
    for tipo in ('OUVIDORIA', 'ACIC', 'BFS', 'CNC', 'SAC'):
        if tipo in nome_upper:
            return tipo
    return None


# ---------------------------------------------------------------------------
# Funções públicas
# ---------------------------------------------------------------------------

def importar_relatorio_flip(arquivo, fonte=None):
    """
    Importa relatório CSV/Excel do sistema Flip.
    Detecta o tipo de serviço pelo nome do arquivo (ACIC/BFS/CNC/OUVIDORIA/SAC).
    Se `fonte` for informado, usa diretamente (ignora o nome do arquivo).
    Retorna o total de registros importados.
    """
    nome = arquivo.name
    tipo_fonte = fonte or _detectar_tipo(nome)

    if nome.lower().endswith('.csv'):
        rows = _ler_csv(arquivo)
    else:
        rows = _ler_excel(arquivo)

    if not rows:
        ImportacaoRelatorio.objects.create(arquivo_nome=nome, tipo='relatorio', total_registros=0)
        return 0

    # Mapa: nome_normalizado → nome_original_da_coluna
    colunas_originais = list(rows[0].keys())
    mapa_norm = {_normalizar(c): c for c in colunas_originais}

    config = CONFIGURACAO.get(tipo_fonte, {})

    def pegar_col(opcoes):
        for op in opcoes:
            col = mapa_norm.get(op)
            if col:
                return col
        return None

    def val(row, opcoes):
        col = pegar_col(opcoes)
        if col:
            return str(row.get(col, '')).strip()
        return ''

    def coord(row):
        opcoes = config.get('coordenadas', [])
        for op in opcoes:
            col = mapa_norm.get(op)
            if col and str(row.get(col, '')).strip():
                lat, lng = _parse_coord(row[col])
                if lat is not None:
                    return lat, lng
        return None, None

    objs = []
    for row in rows:
        endereco = val(row, config.get('endereco', ['endereco']))
        if not endereco:
            continue

        lat, lng = coord(row)

        objs.append(Servico(
            numero_os=val(row, config.get('numero_os', [])),
            tipo_servico=val(row, config.get('tipo_servico', [])) or 'Não informado',
            status=val(row, config.get('status', [])) or 'Não informado',
            endereco=endereco,
            endereco_normalizado=_normalizar(endereco),
            latitude=lat,
            longitude=lng,
            data_execucao=_parse_data(val(row, config.get('data_execucao', []))),
            data_finalizacao=_parse_data(val(row, config.get('data_finalizacao', []))),
            fiscal=val(row, config.get('fiscal', [])),
            fonte=tipo_fonte or 'Flip',
        ))

    # Limpa registros anteriores da mesma fonte antes de inserir os novos.
    # Isso evita duplicidade quando o mesmo arquivo é reimportado.
    if tipo_fonte:
        Servico.objects.filter(fonte=tipo_fonte).delete()

    Servico.objects.bulk_create(objs, batch_size=500)
    total = len(objs)

    ImportacaoRelatorio.objects.create(
        arquivo_nome=nome,
        tipo='relatorio',
        total_registros=total,
    )
    return total


def importar_consultas_programadas(arquivo):
    """
    Importa controle de consultas programadas (CSV/Excel).
    Retorna o total de registros importados.
    """
    nome = arquivo.name

    if nome.lower().endswith('.csv'):
        rows = _ler_csv(arquivo)
    else:
        rows = _ler_excel(arquivo)

    if not rows:
        ImportacaoRelatorio.objects.create(arquivo_nome=nome, tipo='programados', total_registros=0)
        return 0

    colunas_originais = list(rows[0].keys())
    mapa_norm = {_normalizar(c): c for c in colunas_originais}

    MAPA = {
        'endereco':       ['endereco', 'logradouro', 'local'],
        'bairro':         ['bairro'],
        'cidade':         ['cidade', 'municipio'],
        'tipo_servico':   ['tipo_servico', 'servico', 'tipo de servico', 'tipo'],
        'data_programada':['data_programada', 'data programada', 'dt programada', 'data'],
        'observacao':     ['observacao', 'obs'],
        'coordenadas':    ['coordenadas', 'coordenada', 'latlong', 'lat_lng'],
    }

    def val(row, campo):
        for op in MAPA[campo]:
            col = mapa_norm.get(op)
            if col and str(row.get(col, '')).strip():
                return str(row[col]).strip()
        return ''

    total = 0
    for row in rows:
        endereco = val(row, 'endereco')
        data_prog = _parse_data(val(row, 'data_programada'))
        if not endereco or not data_prog:
            continue

        lat, lng = _parse_coord(val(row, 'coordenadas'))

        ConsultaProgramada.objects.create(
            endereco=endereco,
            bairro=val(row, 'bairro'),
            cidade=val(row, 'cidade'),
            latitude=lat,
            longitude=lng,
            tipo_servico=val(row, 'tipo_servico') or 'Não informado',
            data_programada=data_prog,
            observacao=val(row, 'observacao'),
        )
        total += 1

    ImportacaoRelatorio.objects.create(
        arquivo_nome=nome,
        tipo='programados',
        total_registros=total,
    )
    return total
