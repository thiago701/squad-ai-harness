# python-memoria · reference — Padrões de código (antes → depois)

> Hub: `../SKILL.md`. Regras: MEM-01, 02, 04, 05, 06, 07, 11, 12, 14, 15, 18, 19, 20 (`scripts/memoria/regras.py`).
> Toda troca abaixo é **medível**: prove com `with orcamento(...)` antes de aceitar que "ficou melhor".

## 1. Iterar, não materializar (MEM-02, 04, 06, 18, 19, 20)

| Antes (pico ∝ tamanho do dado) | Depois (pico ∝ um item) |
|---|---|
| `linhas = f.readlines(); for l in linhas: …` | `for l in f: …` — objeto-arquivo já é iterador por linha |
| `dados = f.read().splitlines()` | idem; para blocos binários `for bloco in iter(lambda: f.read(1 << 20), b""):` |
| `total = sum([x.valor for x in itens])` | `total = sum(x.valor for x in itens)` — expressão geradora |
| `if any([p(x) for x in xs])` | `if any(p(x) for x in xs)` — para no primeiro `True` |
| `maior = sorted(xs)[-1]` | `maior = max(xs)` (O(n), sem cópia); top-k: `heapq.nlargest(k, xs)` |
| `for x in [y for y in xs if ok(y)]:` | `for x in (y for y in xs if ok(y)):` ou `for y in xs: if ok(y): …` |
| `for k in list(d.keys()):` (só lê) | `for k in d:` — materialize só se for **mutar** `d` no loop |
| etapa A devolve `list`, etapa B itera uma vez | A faz `yield`; B consome o gerador — nada vivo entre etapas |
| `itens = list(cursor)` para paginar | `itertools.islice(cursor, 1000)` / `itertools.batched(it, 1000)` (3.12) |

Quando materializar **é** certo: precisa de `len`, índice aleatório, várias passadas, ou `str.join` (ele precisa do
tamanho e converte gerador em lista de qualquer forma — por isso `"".join([...])` **não** é penalizado).

## 2. Acumular certo (MEM-05, 07)

| Antes | Depois |
|---|---|
| `s = ""; for x in xs: s += f"{x};"` | `partes = []; …partes.append(f"{x};"); s = "".join(partes)` ou `io.StringIO` |
| `lista = lista + [x]` em loop (copia tudo a cada volta) | `lista.append(x)` / `lista.extend(novos)` |
| `copia = copy.deepcopy(obj)` em loop | estrutura imutável (`@dataclass(frozen=True)`, `tuple`) dispensa cópia; se precisar, copie **uma vez** fora do loop ou copie só o campo que muda |
| `resultado = {**resultado, k: v}` em loop | `resultado[k] = v` |

## 3. Todo cache tem limite (MEM-01, 12)

```python
# ANTES — vazamento com nome bonito
@functools.cache                      # nunca descarta; domínio de entrada não limitado = cresce para sempre
def cotacao(moeda, data): ...
class Repo:
    @functools.lru_cache(maxsize=256) # chave inclui self → cada instância fica presa no cache GLOBAL da classe
    def buscar(self, id): ...
HISTORICO = []                        # global que só cresce
def registrar(ev): HISTORICO.append(ev)

# DEPOIS
@functools.lru_cache(maxsize=4_096)   # dimensionado pelo domínio real; cache_info() mostra hit rate
def cotacao(moeda, data): ...
class Repo:
    def __init__(self): self._cache = cachetools.LRUCache(maxsize=256)   # por instância, morre com ela
    # ou: função de módulo com lru_cache cuja chave NÃO inclui self
HISTORICO = collections.deque(maxlen=10_000)   # o mais velho sai sozinho; TTL: cachetools.TTLCache(maxsize, ttl)
```
`functools.cached_property` é por instância e some com ela — ok. `lru_cache` em função com argumento
"único por chamada" (timestamp, request id) é 0 % de hit e 100 % de retenção: remova.

## 4. Não guarde "para depois" o que é gordo (MEM-15)

```python
# ANTES
except ValueError as e:
    erros.append(e)                   # e.__traceback__ → frames → TODOS os locais de cada frame ficam vivos

# DEPOIS
except ValueError as e:
    erros.append({"item": item_id, "erro": f"{type(e).__name__}: {e}"})   # texto; log.exception() loga o stack
```
Por que a própria linguagem concorda: `except E as e:` é compilado como `try: … finally: del e` justamente porque
a exceção com traceback "forma um ciclo de referência com o frame, mantendo vivos todos os locais daquele frame
até a próxima coleta" (referência da linguagem). Guardar `e` numa lista desfaz essa proteção. Se precisar reter
a exceção, `traceback.clear_frames(e.__traceback__)` antes.
Outros ganchos de retenção: closures que capturam o lote inteiro; `logging.getLogger().addHandler` repetido em
função (handlers acumulam — configure uma vez); `sys.exc_info()` guardado em objeto de longa vida; callbacks
registrados sem `weakref`; `__del__` em ciclos (adia a coleta). Solte cedo: `del grande` ao fim do uso em função
longa, ou extraia a parte pesada para uma função — o escopo libera ao retornar. Exemplo medido (pythonspeed):
`dados → etapa1 → etapa2` com arrays de 1 GB tem pico de **3 GB** só porque `dados` continua nomeado; encadear
(`etapa2(etapa1(carregar()))`) ou reatribuir a mesma variável baixa para 2 GB.

## 5. I/O em blocos (MEM-11, 14)

| Antes | Depois |
|---|---|
| `open(dest, "wb").write(requests.get(url).content)` | `with requests.get(url, stream=True) as r: for b in r.iter_content(1 << 20): f.write(b)` · `httpx.stream` · `boto3` `download_fileobj`/`upload_fileobj` (multipart automático) |
| `hashlib.sha256(f.read()).hexdigest()` | `hashlib.file_digest(f, "sha256")` (3.11+) ou `h.update(bloco)` em blocos de 1 MiB |
| `json.load(f)` de arquivo gigante | `ijson.items(f, "item")` (streaming), `msgspec.json.Decoder(Tipo).decode` (schema → só os campos, em `Struct`), ou JSON Lines linha a linha. Benchmark oficial do msgspec num JSON de 77 MiB: `msgspec` com Structs **68 MiB**, `json` 295 MiB, `orjson` **406 MiB** — rápido ≠ leve |
| `csv.reader(f.read().splitlines())` | `csv.reader(f)` direto |
| `data = f.read(); processar(data[i:j])` repetidamente | `mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)` + `memoryview` (fatias zero-copy) |
| `bytes(buf[a:b])` em loop | `memoryview(buf)[a:b]` — view, sem cópia |

## 6. Checklist rápido ao escrever

- [ ] Arquivo/stream/cursor é consumido por iteração; entre etapas passam geradores (MEM-02/20).
- [ ] Agregações recebem expressão geradora; extremos com `min/max`; `for` não itera sobre list comprehension (MEM-04/18/19).
- [ ] Strings/listas acumulam com `append`/`join`; `deepcopy` fora de loop (MEM-05/07).
- [ ] Todo cache tem `maxsize`/TTL/`maxlen`; nenhum `@cache`, `maxsize=None` ou `lru_cache` em método (MEM-01/12).
- [ ] Nenhuma exceção/frame/objeto gordo guardado em coleção (MEM-15).
- [ ] Download/upload/hash/JSON grande em blocos ou streaming (MEM-11/14).
- [ ] Teste de orçamento no caminho quente (`references/medicao-profiling.md`).

## Fontes

- Iteradores e geradores: https://docs.python.org/3/howto/functional.html · `itertools` (`islice`, `batched` 3.12): https://docs.python.org/3/library/itertools.html
- `functools.lru_cache`/`cache`/`cached_property`: https://docs.python.org/3/library/functools.html · `collections.deque(maxlen)`: https://docs.python.org/3/library/collections.html#collections.deque
- Exceções retêm `__traceback__` (ciclo com frames): https://docs.python.org/3/reference/compound_stmts.html#the-try-statement
- `hashlib.file_digest`: https://docs.python.org/3/library/hashlib.html#hashlib.file_digest · `mmap`: https://docs.python.org/3/library/mmap.html · `memoryview`: https://docs.python.org/3/library/stdtypes.html#memoryview
- requests streaming: https://requests.readthedocs.io/en/latest/user/advanced/#body-content-workflow · boto3 `download_fileobj`: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/download_fileobj.html
- ijson: https://github.com/ICRAR/ijson · msgspec: https://jcristharif.com/msgspec/
- Itamar Turner-Trauring (pythonspeed) — "Processing large JSON files…": https://pythonspeed.com/articles/json-memory-streaming/ · "Reducing memory usage… generators": https://pythonspeed.com/memory/ · "Function calls prevent garbage collection" (variável local segura o pico): https://pythonspeed.com/articles/function-calls-prevent-garbage-collection/
- Benchmark de memória JSON do msgspec (`json`/`orjson`/`msgspec`): https://jcristharif.com/msgspec/benchmarks.html · `traceback.clear_frames`: https://docs.python.org/3/library/traceback.html#traceback.clear_frames
