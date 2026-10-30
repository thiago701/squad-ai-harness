# python-memoria · reference — Checklist de review de memória (lente `rev-mem`)

> Hub: `../SKILL.md`. Consumido pelo `tech-lead-review` (PASSO 1d + **P2.MEM** no fluxo de 5 passos) e pelo
> `squad-pipeline` (Fase 5/6 em código Python). Fonte única das regras: `scripts/memoria/regras.py`
> (`python lint_memoria.py catalogo` regenera a tabela). Severidades: 🟡 NECESSÁRIO · 🔵 SUGESTÃO.
> **Memória não é veto**: não existe 🔴 nesta lente — vazamento de segredo é da `rev-logs`/G7; estouro de memória
> é P2/P3, arbitrado por P1>P2>P3 **com número**.

## 1. Como a lente roda

```bash
# determinístico (AST, segundos, sem LLM, sem rede) — só arquivos .py do diff; testes ficam fora por padrão
python -X utf8 skills/python-memoria/scripts/lint_memoria.py verificar --raiz . --diff <base> \
       --falhar-em necessario --saida .claude/pipeline/<slug>/05d-memoria
# orçamento do caminho quente tocado pelo PR (número que entra no laudo)
python -X utf8 skills/python-memoria/scripts/lint_memoria.py medir --script <entrada> --so-rss -- <args>
```

Mapeamento para o veredito do Tech Lead: 🟡 ativo em **código de serviço, job ou caminho de volume não
limitado** → **AGUARDANDO** (corrige sem novo round); 🟡 em script pontual/ferramenta interna → o revisor pode
rebaixar para 🔵 com justificativa no laudo; só 🔵 → APROVADO com observações; `INCONCLUSIVO` (2) nunca vira
aprovação (`NAO_VERIFICADO`). Supressão `# mem-ok: <motivo>` aparece no relatório: o revisor confere se o motivo
é defensável ("config de 200 bytes lida uma vez" sim; "é rápido" não).

## 2. Catálogo (mecânico + leitura)

| ID | Sev. | Regra | Detecção |
|---|---|---|---|
| MEM-01 | 🟡 | Cache sem limite (`@cache` / `lru_cache(maxsize=None)` / em método de instância) | AST |
| MEM-02 | 🟡 | Arquivo inteiro em memória (`readlines()`, `read().splitlines()`, `for l in f.readlines()`) | AST |
| MEM-04 | 🟡 | Lista materializada onde um gerador basta (`sum([...])`, `any([...])`, `set([...])`, `sorted([...])`…) | AST |
| MEM-05 | 🟡 | Concatenação de string/lista em loop (`s += ...`, `lista = lista + [x]`) | AST |
| MEM-06 | 🔵 | `list(d.keys()/values()/items())` só para iterar | AST |
| MEM-07 | 🟡 | `copy.deepcopy` dentro de loop | AST |
| MEM-08 | 🔵 | `pandas.read_*` sem `dtype`/`usecols`/`chunksize`/`nrows`/`columns`/`dtype_backend` | AST |
| MEM-09 | 🟡 | `df.iterrows()` (um objeto Series por linha) | AST |
| MEM-10 | 🟡 | `pd.concat`/`df.copy()` dentro de loop (quadrático em memória) | AST |
| MEM-11 | 🔵 | Download/upload inteiro em memória (`f.write(r.content)`, `.read()` para enviar) | AST |
| MEM-12 | 🔵 | Cache/buffer/histórico global mutável sem política de descarte | AST |
| MEM-13 | 🔵 | `@dataclass` ≥ 4 campos sem `slots=True`, instanciada em massa | AST |
| MEM-14 | 🟡 | Hash de arquivo lido inteiro (`hashlib.sha256(f.read())`) | AST |
| MEM-15 | 🟡 | Exceção guardada em coleção (`erros.append(e)`) | AST |
| MEM-16 | 🔵 | `asyncio.gather(*[...])`/`create_task` em loop sem backpressure | AST |
| MEM-17 | 🔵 | `Pool()` sem `maxtasksperchild` / `Queue()` sem `maxsize` | AST |
| MEM-18 | 🔵 | `sorted(x)[0]`/`[-1]` para extremo | AST |
| MEM-19 | 🔵 | `for x in [comprehension]` | AST |
| MEM-20 | 🟡 | Pipeline materializa coleção inteira entre etapas | leitura |
| MEM-21 | 🟡 | Sem orçamento de memória medido no teste do caminho quente | leitura |
| MEM-22 | 🟡 | Workers/servidores de longa vida sem reciclagem/limite | leitura |
| MEM-23 | 🔵 | Lambda com `MemorySize` não dimensionado (Power Tuning) | leitura |
| MEM-24 | 🔵 | Fork com heap grande sem `gc.freeze()`; COW quebrado | leitura |

**Limites declarados do linter** (o que ele **não** vê — por isso existe a leitura): tipo de variável (`s += x`
com `x` de tipo desconhecido não dispara); `json.load` de arquivo grande (não sabe o tamanho); objeto gordo
retido via atributo (`self.cache[k] = obj`) fora de nome sugestivo; dataclass instanciada em massa em **outro**
módulo; `str.join([...])` é aceito de propósito; arquivos de teste ficam fora (`--incluir-testes` para vê-los).

## 3. P2.MEM — checklist de leitura (PASSO 2 do fluxo de 5 passos)

Só para arquivos `.py` tocados pelo diff; cada item responde `achado | limpo | não verificado (motivo)` na
Auditoria de Cobertura.

**Fluxo de dados**
- [ ] MEM-20: cada etapa consome iterador/gerador; nada vivo "entre" etapas além de um item/lote.
- [ ] Tamanho do dado é **ilimitado** (arquivo do usuário, tabela, fila)? Então `readlines`/`json.load`/`list(cursor)` é 🟡 mesmo fora do padrão mecânico.
- [ ] Objetos de domínio inteiros ou DataFrames passados onde bastam ids/colunas.

**Retenção**
- [ ] Caches/registries/listas em módulo ou em `self` com teto; `lru_cache` só em funções puras com domínio limitado.
- [ ] Nada guarda exceção/traceback/request/response gordos; handlers de log configurados uma vez.
- [ ] Objetos grandes liberados cedo (`del`/escopo de função) em jobs longos.

**Dados** (`dados.md`)
- [ ] dtypes/`usecols`/`chunksize` declarados; `category` onde cabe; `concat` uma vez; parquet/arrow/polars/DuckDB para o que não cabe.

**Concorrência e produção** (`concorrencia-processos.md`, `producao.md`)
- [ ] Semaphore/TaskGroup/Queue(maxsize)/Pool(maxtasksperchild); `gc.freeze()` em pai gordo + fork (MEM-24).
- [ ] MEM-22/23: limite de memória declarado (container/Lambda), reciclagem de worker, alarme a ~80 %.
- [ ] MEM-22: runtime de serviço longo fixado em **≥ 3.14.5** ou 3.13.x (`3.14.[0-4]` em `Dockerfile`/`.python-version`/`requires-python` = GC incremental revertido por pressão de memória).

**Medição** (`medicao-profiling.md`)
- [ ] MEM-21: teste de orçamento (`with orcamento(max_pico_mb=…)` / `limit_memory`) no caminho que processa arquivo/lote/stream.
- [ ] PR com número antes/depois (`medir --so-rss`), não adjetivo ("ficou mais leve").
- [ ] Otimização proposta respeita P1: se a versão enxuta é ilegível e o ganho é < 10 %, fica a legível (registrar débito).

## 4. Saída esperada no laudo (`NN-review.md` / `05d-memoria.md`)

```
### Lente rev-mem (python-memoria 1.1.0)
veredito: APROVADO | AGUARDANDO | NAO_VERIFICADO        sha_revisado: <sha>
mecânico: 🟡 2 · 🔵 5 · suprimidos 1 (motivos conferidos: sim) · densidade 1,3 achados/1k linhas (baseline do repo: 1,0)
orçamento: processar_lote(200k linhas) heap pico 41 MB · RSS +58 MB (teste test_processar_lote_orcamento, teto 64 MB)
leitura (P2.MEM): fluxo=limpo · retenção=achado(MEM-12 x1) · dados=limpo · concorrência=não verificado (sem async no diff) · medição=limpo
achados:
  🟡 MEM-02 app/importador.py:88 — readlines() em arquivo do usuário → iterar o arquivo
  🟡 MEM-15 app/importador.py:131 — erros.append(e) → guardar str(e)
```
