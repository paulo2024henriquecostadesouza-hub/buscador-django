# Correções aplicadas no Buscador-Django
**Data:** 30/03/2026
**Arquivos alterados:** `mapa/views.py` e `mapa/templates/mapa/index.html`

---

## Contexto — o que estava errado

O sistema possuía três bugs relacionados ao filtro de resolução (Feito/Pendente) e à exibição correta do status dos serviços no mapa.

---

## Bug 1 — Filtro "Somente Feitos / Somente Pendentes" não funcionava

### Diagnóstico
O `index.html` possui um `<select id="filtroResolucao">` com as opções:
- `""` → Feito + Pendente
- `"feito"` → Somente Feitos
- `"pendente"` → Somente Pendentes

O JavaScript já enviava o parâmetro `resolucao` corretamente na URL da API:
```
/api/dados/?...&resolucao=feito
/api/stats/?...&resolucao=feito
```

**Porém**, o backend (`views.py`) lia o parâmetro mas não fazia nada com ele. As funções `dados_mapa` e `stats_mapa` simplesmente ignoravam o valor de `resolucao`.

### Solução aplicada em `mapa/views.py`

**Passo 1 — Criar função auxiliar `_feito_q()`**

Logo após a função `_normalizar_busca`, antes de `def dados_mapa(request):`, inserir:

```python
def _feito_q():
    """Retorna Q para serviços considerados 'feitos'."""
    return (
        Q(data_finalizacao__isnull=False) |
        Q(data_execucao__isnull=False) |
        Q(status__icontains='finaliz') |
        Q(status__icontains='execut') |
        Q(status__icontains='conclu') |
        Q(status__icontains='realiz')
    )
```

Esta função centraliza o critério de "feito" em um único lugar, reutilizado em todas as partes do código.

---

**Passo 2 — Aplicar o filtro em `dados_mapa`**

Na função `dados_mapa`, adicionar leitura do parâmetro `resolucao`:

```python
resolucao = request.GET.get('resolucao', '').strip()
```

E, após todos os outros filtros (busca, tipo, status, fonte, mes), adicionar:

```python
if resolucao == 'feito':
    servicos_qs = servicos_qs.filter(_feito_q())
elif resolucao == 'pendente':
    servicos_qs = servicos_qs.exclude(_feito_q())
```

---

**Passo 3 — Aplicar o filtro em `stats_mapa`**

Na função `stats_mapa`, adicionar leitura do parâmetro `resolucao`:

```python
resolucao = request.GET.get('resolucao', '').strip()
```

Após todos os outros filtros, adicionar:

```python
if resolucao == 'feito':
    qs = qs.filter(_feito_q())
elif resolucao == 'pendente':
    qs = qs.exclude(_feito_q())
```

Também substituir o antigo bloco de contagem de feitos/pendentes (que usava Python puro com `re` e iterava todos os registros em memória) pela versão com query direta ao banco:

**Remover:**
```python
import re as _re
_feito_pat = _re.compile(r'finaliz|execut|conclu|realiz', _re.IGNORECASE)
registros = list(qs.values('status', 'data_execucao', 'data_finalizacao'))
feitos = sum(
    1 for r in registros
    if r['data_finalizacao'] or r['data_execucao'] or _feito_pat.search(r['status'] or '')
)
pendentes = total - feitos
```

**Inserir:**
```python
feitos    = qs.filter(_feito_q()).count()
pendentes = total - feitos
```

---

## Bug 2 — Status dos marcadores incorreto (tudo marcado como "Feito")

### Diagnóstico
Quando um serviço não tinha `data_execucao`, o backend enviava a string `'-'` para o frontend:

```python
# ANTES (linha ~100 em dados_mapa):
'data': s['data_execucao'].strftime('%d/%m/%Y') if s['data_execucao'] else '-',
```

No JavaScript, a função `eFeito()` verifica se `data_execucao` tem conteúdo:

```javascript
function eFeito(status, data_execucao, data_finalizacao) {
    if (data_finalizacao && data_finalizacao.trim()) return true;
    if (data_execucao   && data_execucao.trim()   ) return true;   // <-- bug aqui
    return /finaliz|execut|conclu|realiz/i.test(status || '');
}
```

Como `'-'.trim()` é truthy (string não vazia), **todo serviço sem data de execução era marcado como "Feito"** — mesmo aqueles genuinamente pendentes.

### Solução aplicada

**Em `mapa/views.py`**, na função `dados_mapa`, trocar:

```python
# ANTES:
'data': s['data_execucao'].strftime('%d/%m/%Y') if s['data_execucao'] else '-',

# DEPOIS:
'data': s['data_execucao'].strftime('%d/%m/%Y') if s['data_execucao'] else '',
```

**Em `mapa/templates/mapa/index.html`**, no bloco de montagem do popup dos serviços, trocar:

```javascript
// ANTES (dentro do .map(s => ...) de servicosHtml):
<span class="data"> | ${s.data}</span>

// DEPOIS:
<span class="data"> | ${s.data || '-'}</span>
```

Desta forma:
- O campo `data` vai como `''` (vazio) quando não há data — o JavaScript interpreta como falso e não marca como "feito"
- O popup continua exibindo `'-'` visualmente para o usuário via `s.data || '-'`

---

## Bug 3 — Filtro de mês ignorava serviços finalizados sem data de execução

### Diagnóstico
O filtro de mês em ambas as funções usava apenas `data_execucao`:

```python
# ANTES:
qs = qs.filter(data_execucao__year=int(ano), data_execucao__month=int(m))
```

Serviços que tinham `data_finalizacao` no mês selecionado, mas não tinham `data_execucao`, eram excluídos do resultado.

### Solução aplicada em `mapa/views.py`

Em `dados_mapa` e `stats_mapa`, substituir o filtro de mês por:

```python
servicos_qs = servicos_qs.filter(
    Q(data_execucao__year=int(ano), data_execucao__month=int(m)) |
    Q(data_finalizacao__year=int(ano), data_finalizacao__month=int(m))
)
```

---

## Resumo das alterações por arquivo

### `mapa/views.py`

| Local | O que mudou |
|-------|-------------|
| Após `_normalizar_busca` | Adicionada função `_feito_q()` |
| `dados_mapa` — início | Adicionada leitura de `resolucao = request.GET.get('resolucao', '').strip()` |
| `dados_mapa` — filtro de mês | Filtro ampliado para incluir `data_finalizacao` |
| `dados_mapa` — campo `data` | Retorna `''` em vez de `'-'` quando data_execucao é nula |
| `dados_mapa` — após filtros | Adicionado bloco `if resolucao == 'feito'` / `elif resolucao == 'pendente'` |
| `stats_mapa` — início | Adicionada leitura de `resolucao` |
| `stats_mapa` — filtro de mês | Filtro ampliado para incluir `data_finalizacao` |
| `stats_mapa` — após filtros | Adicionado bloco `if resolucao == 'feito'` / `elif resolucao == 'pendente'` |
| `stats_mapa` — contagem feitos | Substituído loop Python + regex por `qs.filter(_feito_q()).count()` |

### `mapa/templates/mapa/index.html`

| Local | O que mudou |
|-------|-------------|
| Popup de serviços — campo data | `${s.data}` → `${s.data \|\| '-'}` |

---

## Critério unificado de "Feito"

Um serviço é considerado **Feito** se qualquer uma destas condições for verdadeira:

1. O campo `data_finalizacao` está preenchido
2. O campo `data_execucao` está preenchido
3. O campo `status` contém uma das palavras: `finaliz`, `execut`, `conclu`, `realiz` (insensível a maiúsculas)

Um serviço é **Pendente** se **nenhuma** das condições acima for verdadeira.

Esta lógica está implementada centralmente em `_feito_q()` (backend) e espelhada na função `eFeito()` já existente no JavaScript do `index.html` (frontend).
