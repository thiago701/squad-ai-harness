"""Catálogo das regras MEM-xx — fonte única lida pela lente, pelo checklist de review e pelos evals.

Severidades do protocolo do tech-lead-review:
  🟡 NECESSÁRIO (corrigir antes do merge em código que processa volume não limitado ou roda em serviço)
  🔵 SUGESTÃO   (melhoria desejável; registre como débito se não aplicar)
Memória não tem "veto" como segurança: a lente só reprova com `--falhar-em necessario` (modo review).
`mecanica=True` = a lente detecta por AST; `False` = item de leitura do checklist (P2.MEM).
"""
from __future__ import annotations

from dataclasses import dataclass

NEC, SUG = "🟡", "🔵"


@dataclass(frozen=True)
class Regra:
    id: str
    severidade: str
    titulo: str
    deteccao: str
    correcao: str
    referencia: str
    mecanica: bool = True


REGRAS: tuple[Regra, ...] = (
    # ---------------- coleções e iteração ----------------
    Regra("MEM-01", NEC, "Cache sem limite (`@cache` / `lru_cache(maxsize=None)` / em método de instância)",
          "decorador functools.cache, lru_cache() sem maxsize numérico, ou lru_cache em método (self fica vivo no cache)",
          "`lru_cache(maxsize=N)` dimensionado, TTL (cachetools) ou cache externo; em método, cache por instância "
          "(`cached_property`) ou chave sem `self`.",
          "references/padroes-codigo.md"),
    Regra("MEM-02", NEC, "Arquivo inteiro em memória (`readlines()`, `read().splitlines()`, `for l in f.readlines()`)",
          "chamada .readlines() ou .read() seguida de .splitlines()/.split(\"\\n\")",
          "itere o arquivo (`for linha in f`), `csv.reader(f)`, `ijson`/`msgspec` para JSON grande, ou leia em blocos "
          "(`iter(lambda: f.read(1 << 20), b\"\")`).",
          "references/padroes-codigo.md"),
    Regra("MEM-04", NEC, "Lista materializada onde um gerador basta (`sum([...])`, `any([...])`, `set([...])`, `sorted([...])`…)",
          "Call a sum/any/all/min/max/sorted/set/frozenset/tuple/enumerate/zip/map/filter com argumento ListComp (str.join NÃO: precisa do tamanho)",
          "troque `[...]` por `(...)`: expressão geradora não aloca a lista intermediária.",
          "references/padroes-codigo.md"),
    Regra("MEM-05", NEC, "Concatenação de string/lista em loop (`s += ...`, `lista = lista + [x]`)",
          "AugAssign `+=` com valor str/f-string/str()/concatenação, ou `x = x + [...]`, dentro de for/while",
          "acumule em lista e `\"\".join(partes)` / `io.StringIO`; para listas use `append`/`extend` (amortizado O(1)).",
          "references/padroes-codigo.md"),
    Regra("MEM-06", SUG, "`list(d.keys()/values()/items())` só para iterar",
          "For cujo iterável é list(<x>.keys()|values()|items()) e o corpo não altera <x>",
          "itere a view diretamente (`for k, v in d.items()`); só materialize se for mutar o dict durante o loop.",
          "references/padroes-codigo.md"),
    Regra("MEM-07", NEC, "`copy.deepcopy` dentro de loop",
          "Call copy.deepcopy/deepcopy no corpo de for/while/comprehension",
          "estruturas imutáveis (tuple/frozen dataclass) ou cópia rasa do que realmente muda; mova a cópia para fora do loop.",
          "references/padroes-codigo.md"),
    Regra("MEM-19", SUG, "`for x in [comprehension]` — lista intermediária só para iterar",
          "For cujo iterável é uma ListComp",
          "use expressão geradora `(… for …)` ou itere a fonte com `if` no corpo.",
          "references/padroes-codigo.md"),
    Regra("MEM-18", SUG, "`sorted(x)[0]` / `sorted(x)[-1]` para achar extremo",
          "Subscript 0/-1 sobre Call sorted(...)",
          "`min(x)`/`max(x)` (O(n), sem cópia) ou `heapq.nsmallest/nlargest(k, x)` para k > 1.",
          "references/padroes-codigo.md"),

    # ---------------- dados ----------------
    Regra("MEM-08", SUG, "`pandas.read_*` sem `dtype`/`usecols`/`chunksize`/`nrows`/`columns`/`dtype_backend`",
          "Call pd.read_csv/read_json/read_parquet/read_excel/read_sql sem nenhum desses kwargs",
          "declare `usecols` + `dtype` (ou `dtype_backend=\"pyarrow\"`), `chunksize` para streaming, `columns` no parquet; "
          "em ETL grande prefira `polars.scan_*` (lazy) ou DuckDB.",
          "references/dados.md"),
    Regra("MEM-09", NEC, "`df.iterrows()` (um objeto Series por linha)",
          "Call .iterrows()",
          "vetorize; se precisar iterar, `itertuples(index=False)` ou `to_dict(\"records\")` em chunks.",
          "references/dados.md"),
    Regra("MEM-10", NEC, "`pd.concat`/`df.append`/`df.copy()` dentro de loop (quadrático em memória)",
          "Call pd.concat / .append / .copy em DataFrame dentro de for/while",
          "acumule os pedaços numa lista e concatene UMA vez fora do loop; evite `.copy()` desnecessário (CoW no pandas ≥ 2.0).",
          "references/dados.md"),

    # ---------------- I/O e rede ----------------
    Regra("MEM-11", SUG, "Download/upload inteiro em memória (`f.write(r.content)`, `.read()` para enviar)",
          "Call .write(<x>.content) ou .write(<x>.read())",
          "`requests.get(stream=True)` + `iter_content(1 << 20)`; `httpx.stream`; `boto3` `download_fileobj`/`upload_fileobj`.",
          "references/padroes-codigo.md"),
    Regra("MEM-14", NEC, "Hash de arquivo lido inteiro (`hashlib.sha256(f.read())`)",
          "Call hashlib.<alg>(<y>.read()) ou <h>.update(<y>.read())",
          "`hashlib.file_digest(f, \"sha256\")` (3.11+) ou blocos de 1 MiB com `.update`.",
          "references/padroes-codigo.md"),

    # ---------------- retenção e vazamento ----------------
    Regra("MEM-12", SUG, "Cache/buffer/histórico global mutável sem política de descarte",
          "atribuição de módulo `NOME = {}|[]|dict()|list()|set()` com nome cache|buffer|memo|registry|historico|history|"
          "eventos|events e mutação (.append/[k]=v/.add) em função, sem pop/clear/maxlen/TTL no módulo",
          "`collections.deque(maxlen=N)`, `lru_cache(maxsize)`, `cachetools.TTLCache`, ou persistência fora do processo.",
          "references/padroes-codigo.md"),
    Regra("MEM-15", NEC, "Exceção guardada em coleção (`erros.append(e)` dentro de `except … as e`)",
          "Call .append/.add/atribuição em coleção com o Name do `except … as e` como argumento",
          "guarde `str(e)`/`repr(e)`/um dict com tipo+mensagem: a exceção segura `__traceback__` → frames → locais inteiros.",
          "references/padroes-codigo.md"),
    Regra("MEM-13", SUG, "`@dataclass` com ≥ 4 campos sem `slots=True`, instanciada em massa (em loop/comprehension ou nome de registro)",
          "ClassDef decorada com dataclass (sem slots=True), ≥ 4 campos, E instanciada em loop/comprehension no módulo ou com nome de registro (Item, Evento, Linha, Registro…)",
          "`@dataclass(slots=True)` (3.10+): ~40-60 % menos memória por instância e acesso mais rápido; "
          "idem `__slots__` em classes comuns instanciadas em massa.",
          "references/runtime-alocador.md"),

    # ---------------- concorrência ----------------
    Regra("MEM-16", SUG, "`asyncio.gather(*[...])`/`create_task` em loop sem backpressure",
          "Call gather com Starred de comprehension, ou create_task dentro de for, sem Semaphore/TaskGroup limitado na função",
          "`asyncio.Semaphore(N)` em volta da corrotina, `TaskGroup` com janela, ou consumir em lotes (`itertools.batched`).",
          "references/concorrencia-processos.md"),
    Regra("MEM-17", SUG, "`multiprocessing.Pool()` sem `maxtasksperchild` / `queue.Queue()` sem `maxsize`",
          "Call Pool(...) sem maxtasksperchild; Call Queue()/asyncio.Queue() sem maxsize",
          "`Pool(maxtasksperchild=…)` recicla workers que vazam; `Queue(maxsize=N)` dá backpressure ao produtor.",
          "references/concorrencia-processos.md"),

    # ---------------- leitura (checklist P2.MEM) ----------------
    Regra("MEM-20", NEC, "Pipeline materializa coleção inteira entre etapas",
          "leitura: função retorna lista enorme consumida por outra que itera uma vez",
          "generators/iteradores entre etapas; `yield` em vez de `append`+`return`.",
          "references/padroes-codigo.md", mecanica=False),
    Regra("MEM-21", NEC, "Sem orçamento de memória medido no teste",
          "leitura: código que processa arquivo/lote/stream sem teste que mede pico (tracemalloc/pytest-memray)",
          "`with orcamento(max_pico_mb=…)` ou `@pytest.mark.limit_memory` no teste do caminho quente.",
          "references/medicao-profiling.md", mecanica=False),
    Regra("MEM-22", NEC, "Workers de longa vida sem reciclagem/limite",
          "leitura: gunicorn/uvicorn/celery sem max-requests/worker_max_memory_per_child; container sem memory limit; "
          "runtime 3.14.0-3.14.4 em serviço longo (GC incremental revertido no 3.14.5)",
          "`--max-requests` + jitter, `worker_max_memory_per_child`, `memory.max`/limits no orquestrador; Python ≥ 3.14.5 ou 3.13.x.",
          "references/producao.md", mecanica=False),
    Regra("MEM-23", SUG, "Lambda com `MemorySize` não dimensionado",
          "leitura: template sem MemorySize ou 128 MB com pandas/numpy",
          "AWS Lambda Power Tuning; memória também é CPU; medir p99 e custo.",
          "references/producao.md", mecanica=False),
    Regra("MEM-24", SUG, "Fork com heap grande sem `gc.freeze()`; workers que quebram copy-on-write",
          "leitura: multiprocessing fork após carregar modelo/cache grande",
          "`gc.freeze()` antes do fork, `spawn` quando o pai é gordo, `shared_memory`/mmap para dados compartilhados.",
          "references/concorrencia-processos.md", mecanica=False),
)

POR_ID = {r.id: r for r in REGRAS}
IDS_MECANICAS = tuple(r.id for r in REGRAS if r.mecanica)


def tabela_markdown() -> str:
    linhas = ["| ID | Sev. | Regra | Detecção |", "|---|---|---|---|"]
    for r in REGRAS:
        linhas.append(f"| {r.id} | {r.severidade} | {r.titulo} | {'AST' if r.mecanica else 'leitura'} |")
    return "\n".join(linhas)
