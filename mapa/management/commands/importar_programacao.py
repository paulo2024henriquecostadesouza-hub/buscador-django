"""
Importa todos os arquivos Excel da pasta Programação (organizada por subprefeitura).
Detecta o tipo de serviço pelo nome do arquivo.

Uso:
    python manage.py importar_programacao
    python manage.py importar_programacao --pasta "C:/caminho/alternativo"
"""
import os
import re
from datetime import datetime
from pathlib import Path

import openpyxl
from django.conf import settings
from django.core.management.base import BaseCommand

from mapa.models import ProgramacaoServico

PASTA_PADRAO = os.path.join(settings.BASE_DIR, 'programação')

# Mapeamento nome-do-arquivo → nome legível
TIPO_POR_ARQUIVO = {
    'boca de lobo':         'Boca de Lobo',
    'cata-bagulho':         'Cata-Bagulho',
    'cata bagulho':         'Cata-Bagulho',
    'lavagem especial':     'Lavagem Especial',
    'monumentos':           'Limpeza de Monumentos',
    'mutirao':              'Mutirão de Zeladoria',
    'mutirão':              'Mutirão de Zeladoria',
    'nucleos habitacionais':'Núcleos Habitacionais',
    'núcleos habitacionais':'Núcleos Habitacionais',
}


def _tipo_do_arquivo(nome):
    base = Path(nome).stem.lower()
    for chave, valor in TIPO_POR_ARQUIVO.items():
        if chave in base:
            return valor
    return Path(nome).stem


def _parse_coord(valor):
    if not valor:
        return None
    return float(str(valor).replace(',', '.').strip())


def _parse_data(valor):
    if not valor:
        return None
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(str(valor).strip(), fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def _normalizar_opcoes_data(valor):
    """Normaliza o campo Opção de data → string 'dd/mm/yyyy;...' """
    if not valor:
        return ''
    s = str(valor).strip()
    # Substitui separadores variados por ;
    s = re.sub(r'\s*[-–]\s*', ';', s)
    s = re.sub(r'\s*;\s*', ';', s)
    # Limpa trailing separators
    s = s.strip('; ')
    return s


def importar_arquivo(path, subprefeitura, tipo_nome):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        wb.close()
        return 0

    headers = [str(h or '').strip().lower() for h in rows[0]]

    def col(nome_parcial):
        for i, h in enumerate(headers):
            if nome_parcial in h:
                return i
        return None

    idx_lat    = col('latitude')
    idx_lng    = col('longitude')
    idx_log    = col('logradouro')
    idx_ref    = col('referencia')
    idx_local  = col('nome do local')
    idx_setor  = col('setor')
    idx_tipo   = col('tipo de servi')
    idx_sub    = col('sub')
    idx_turno  = col('turno')
    idx_ini    = col('data inicio')
    idx_fim    = col('data de fim')
    idx_hini   = col('horário inicio') or col('horario inicio')
    idx_hfim   = col('horário fim')    or col('horario fim')
    idx_freq   = col('frequ')
    idx_opts   = col('opção de data') or col('opcao de data') or col('op')
    idx_ops    = col('quantidade operador')
    idx_veic   = col('quantidade de ve')

    def v(row, idx):
        if idx is None or idx >= len(row):
            return ''
        val = row[idx]
        return str(val).strip() if val is not None else ''

    total = 0
    objs = []
    for row in rows[1:]:
        lat = _parse_coord(v(row, idx_lat))
        lng = _parse_coord(v(row, idx_lng))
        logradouro = v(row, idx_log)
        if not logradouro:
            continue

        opcoes_raw = v(row, idx_opts)

        objs.append(ProgramacaoServico(
            subprefeitura  = subprefeitura,
            tipo_nome      = tipo_nome,
            tipo_cod       = v(row, idx_tipo),
            setor          = v(row, idx_setor),
            logradouro     = logradouro,
            referencia     = v(row, idx_ref),
            nome_local     = v(row, idx_local) if idx_local is not None else '',
            latitude       = lat,
            longitude      = lng,
            data_inicio    = _parse_data(v(row, idx_ini)),
            data_fim       = _parse_data(v(row, idx_fim)),
            horario_inicio = v(row, idx_hini),
            horario_fim    = v(row, idx_hfim),
            frequencia     = v(row, idx_freq),
            turno          = v(row, idx_turno),
            opcoes_data    = _normalizar_opcoes_data(opcoes_raw),
            qtd_operadores = int(float(v(row, idx_ops)))  if v(row, idx_ops)  else 0,
            qtd_veiculos   = int(float(v(row, idx_veic))) if v(row, idx_veic) else 0,
        ))
        total += 1

    ProgramacaoServico.objects.bulk_create(objs, batch_size=500)
    wb.close()
    return total


class Command(BaseCommand):
    help = 'Importa plano de trabalho da pasta Programação (subpastas por subprefeitura)'

    def add_arguments(self, parser):
        parser.add_argument('--pasta', default=PASTA_PADRAO)
        parser.add_argument('--limpar', action='store_true',
                            help='Apaga registros anteriores antes de importar')

    def handle(self, *args, **options):
        pasta = options['pasta']

        if not os.path.isdir(pasta):
            self.stderr.write(self.style.ERROR(f'Pasta não encontrada: {pasta}'))
            return

        if options['limpar']:
            total_apagados = ProgramacaoServico.objects.count()
            ProgramacaoServico.objects.all().delete()
            self.stdout.write(f'  {total_apagados} registros anteriores removidos.')

        total_geral = 0
        for sub in sorted(os.listdir(pasta)):
            sub_path = os.path.join(pasta, sub)
            if not os.path.isdir(sub_path):
                continue
            for fname in sorted(os.listdir(sub_path)):
                if not fname.lower().endswith('.xlsx'):
                    continue
                tipo = _tipo_do_arquivo(fname)
                fpath = os.path.join(sub_path, fname)
                try:
                    n = importar_arquivo(fpath, sub, tipo)
                    total_geral += n
                    self.stdout.write(f'  {sub} / {fname}: {n} registros')
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f'  ERRO {sub}/{fname}: {e}'))

        self.stdout.write(self.style.SUCCESS(
            f'\nConcluído: {total_geral} registros importados.'
        ))
