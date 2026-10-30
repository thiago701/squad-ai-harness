# Rule — Memória RAM always-on de Python (invariantes — código novo já nasce enxuto)

> **Pack:** python · **Origin:** `squad-ai` · **Dono:** `python-memoria` (doutrina) + `arquiteto-performance`
> (arbitragem P2). Destilação dos invariantes; o **como** (medição, profiling, dados, processos, Lambda) vive em
> [`skills/python-memoria/SKILL.md`](../../skills/python-memoria/SKILL.md). Não duplicar a skill aqui.
> **Arbitragem:** P1-Simplicidade > P2-Performance > P3-CustoBaixo — memória é P2 **e** P3 (RAM = CPU = custo no
> Lambda/container); só otimize com medição, nunca por intuição.

RAM se gasta em três lugares: **objetos que você materializa sem precisar**, **referências que você esquece de
soltar** e **processos que você não limita**. Escreva certo na primeira vez; a lente `rev-mem` só confirma.

## Invariantes (sempre verdade)

- **Itere, não materialize.** Arquivo → `for linha in f` (nunca `readlines()`/`read().splitlines()`); pipeline →
  generators/`yield` entre etapas; agregação → `sum(x for …)`, nunca `sum([…])`; `for x in (…)`, nunca sobre
  list comprehension; `min`/`max`, nunca `sorted(x)[0]`. Materialize **uma vez**, e só quando precisar de índice,
  tamanho ou várias passadas.
- **Acumule certo.** String em loop → lista + `"".join`; lista → `append`/`extend` (nunca `x = x + […]`);
  `deepcopy` fora do loop; estruturas imutáveis (`frozen`) dispensam cópia defensiva.
- **Todo cache tem limite.** `@cache` e `lru_cache(maxsize=None)` são vazamentos com nome bonito;
  `lru_cache(maxsize=N)` dimensionado, `cachetools.TTLCache`, `deque(maxlen=N)` para histórico; nunca
  `lru_cache` em método de instância (prende `self`). Global mutável que só cresce precisa de política de descarte.
- **Não guarde exceções, frames ou objetos gordos "para depois".** `erros.append(str(e))`, nunca `append(e)`
  (a exceção segura `__traceback__` → frames → todos os locais); handlers de log sem duplicar; `del`/escopo de
  função para soltar cedo o que é grande.
- **I/O em blocos.** Download/upload: `stream=True` + `iter_content(1 << 20)` / `download_fileobj`; hash:
  `hashlib.file_digest`; JSON/CSV grande: `ijson`/`csv.reader(f)`/`msgspec`; binário: `memoryview`/`mmap`,
  `bytes` só quando precisa copiar.
- **Dados com tipo declarado e em pedaços.** `pd.read_*` sempre com `usecols` + `dtype` (ou `dtype_backend=
  "pyarrow"`), `chunksize` para streaming, `category` para baixa cardinalidade; nunca `iterrows()`; `pd.concat`
  **uma vez** fora do loop; ETL grande em `polars.scan_*` (lazy) ou DuckDB — parquet, não CSV.
- **Muitas instâncias → `slots`.** `@dataclass(slots=True)` / `__slots__` em classes instanciadas em massa (≈ metade
  da memória por objeto); `msgspec.Struct` quando (des)serializa muito; `array`/numpy para números homogêneos.
- **Concorrência com teto.** `asyncio.Semaphore`/`TaskGroup` com janela (nunca `gather(*[… para tudo])`),
  `Queue(maxsize=N)` dá backpressure; `Pool(maxtasksperchild=N)` e `--max-requests` reciclam worker que vaza;
  fork com heap grande → `gc.freeze()` antes (copy-on-write quebra por refcount); dados compartilhados via
  `shared_memory`/mmap, não cópia por processo.
- **Produção tem limite declarado.** Container com `memory` limit e `--max-requests`+jitter; Lambda com
  `MemorySize` dimensionado por Power Tuning (memória é CPU); `PYTHONMALLOC`/`MALLOC_ARENA_MAX=2` quando o RSS
  não volta; o número que vale é o **RSS/HWM do processo**, não o `tracemalloc`.
- **Orçamento é teste.** Caminho que processa arquivo/lote/stream tem `with orcamento(max_pico_mb=…)` (ou
  `@pytest.mark.limit_memory`) — regressão de memória é bug, não surpresa de produção.

## O que fazer AO ESCREVER (não depois)

1. **Antes de codar o caminho quente:** decida o *contrato de memória* — "processa N linhas com pico ≤ X MB" —
   e escreva o teste de orçamento primeiro (TDD): `templates/pytest/conftest_memoria.py`.
2. **Ao codar:** generators entre etapas, tipos declarados nos dados, caches com limite, I/O em blocos, slots em
   massa. `exemplos/bom/etl_pedidos.py` é o modelo; `exemplos/ruim/` é o que a lente reprova.
3. **Antes de entregar o arquivo:** `python -X utf8 skills/python-memoria/scripts/lint_memoria.py verificar
   --raiz . --arquivos <tocados> --falhar-em necessario` — zero 🟡; `# mem-ok: <motivo>` só com motivo real.
4. **Quando o RSS surpreender:** `lint_memoria.py medir --script …` (pico heap + RSS), depois `memray run`
   / `scalene` para achar a linha — `references/medicao-profiling.md`.
