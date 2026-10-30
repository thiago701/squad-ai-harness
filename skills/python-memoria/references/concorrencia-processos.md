# python-memoria · reference — Concorrência e processos com teto

> Hub: `../SKILL.md`. Regras: MEM-16, MEM-17 (+ leitura MEM-22, MEM-24). Memória em concorrência explode por
> **quantidade de coisas vivas ao mesmo tempo** (tarefas, itens em fila, cópias por processo) — a resposta é
> sempre um **teto explícito**.

## 1. asyncio — backpressure (MEM-16)

```python
# ANTES — 50 mil corrotinas vivas, 50 mil respostas em memória, cliente HTTP sem limite
resultados = await asyncio.gather(*[baixar(u) for u in urls])

# DEPOIS — janela de N; TaskGroup cancela tudo se uma falhar
sem = asyncio.Semaphore(32)
async def limitado(u):
    async with sem:
        return await baixar(u)
async with asyncio.TaskGroup() as tg:
    tarefas = [tg.create_task(limitado(u)) for u in urls]
# consumir à medida que termina (sem guardar tudo): for fut in asyncio.as_completed([...]): ...
# produtor/consumidor: asyncio.Queue(maxsize=1_000) — put() bloqueia quando cheia
```
- `create_task` em loop sem referência forte → tarefa pode ser coletada no meio (bug) **e** sem limite (memória):
  use `TaskGroup` ou guarde em `set` com `discard` no `done_callback`.
- Respostas grandes: `async with session.get(url) as r: async for bloco in r.content.iter_chunked(1 << 20)`.
- Lote: `itertools.batched(urls, 500)` → processa, grava, descarta, próximo lote.

## 2. Threads vs processos

- Threads compartilham o heap: baratas em memória, mas o GIL limita CPU (até o free-threading 3.13t/3.14 — que
  **aumenta** o consumo por objeto/estruturas; meça antes de adotar).
- `ThreadPoolExecutor(max_workers=N)` e `ProcessPoolExecutor(max_workers=N)`: N explícito; `executor.map(..., chunksize=k)`
  reduz overhead de pickling; nunca `list(executor.map(...))` de resultados gordos — itere e descarte.
- Processos **copiam**: cada worker tem sua cópia do que importou e carregou. Carregue o pesado **antes** do
  fork (herda por copy-on-write) ou compartilhe (§3), nunca uma cópia por worker.

## 3. fork, copy-on-write e `gc.freeze()` (MEM-24)

Após `fork`, páginas são compartilhadas até alguém escrever nelas. Em CPython **todo acesso escreve**: o
refcount vive no cabeçalho do objeto e o GC marca bits em `gc_refs` — páginas inteiras são copiadas só por
*ler* um objeto. Instagram mediu isso e criou `gc.freeze()`: mover tudo que existe para uma geração permanente
que o coletor não toca.

```python
carregar_modelo_e_caches()        # no processo pai, antes de forkar
import gc; gc.freeze()            # objetos atuais ficam fora das coletas → páginas permanecem compartilhadas
# workers: multiprocessing.get_context("fork").Pool(..., maxtasksperchild=500)
```
- Medido pelo Instagram: sem isso, ~600 MB extras após 3 000 requests só de páginas sujas pelo GC; com
  `gc.freeze()`, crescimento médio de memória por request **−50 %**. Fechamento lento após `gc.disable()`:
  `atexit.register(os._exit, 0)`. Diagnóstico de COW quebrado: `Shared_Dirty`/`Private_Dirty` em `/proc/PID/smaps`.
- **Método de início padrão mudou no 3.14**: `forkserver` em POSIX (era `fork` no Linux); `spawn` em macOS/Windows.
  `fork` com threads vivas emite `DeprecationWarning` desde o 3.12. `forkserver`/`spawn` não herdam o heap do pai:
  pai gordo = N cópias carregadas do zero — carregue **dentro** do worker com `initializer=`, uma vez por processo,
  ou `set_forkserver_preload(["app.modelos"])` para o servidor de fork importar o pesado uma vez e herdá-lo por COW.
  Se precisar de `fork` explícito (`get_context("fork")`), é com a receita acima.
- Dados grandes entre processos: `multiprocessing.shared_memory.SharedMemory` + `np.ndarray(buffer=shm.buf)`,
  ou `np.memmap`/arquivo parquet em `/dev/shm`; nunca enviar DataFrame por `Queue`/pickle a cada tarefa.
  Disciplina: `close()` em **cada** processo, `unlink()` **uma** vez; entre processos independentes use
  `track=False` (3.13+) — senão o resource tracker do primeiro a sair apaga o bloco dos outros;
  `SharedMemoryManager` como context manager resolve o pareamento.
- `pickle` protocolo 5 (`buffer_callback=`/`buffers=`, `PickleBuffer`) transfere numpy/bytes **sem cópia** (out-of-band).
- `Pool(maxtasksperchild=N)` (MEM-17): worker que vaza morre e renasce — prazo de validade para o vazamento.

## 4. Servidores e workers de longa vida (MEM-22)

| Runtime | Teto | Reciclagem |
|---|---|---|
| gunicorn | `--workers` (2×CPU+1 é para sync; async precisa de menos) + `--max-requests 1000` | `--max-requests-jitter 50` (~5 %) evita todos reiniciarem juntos; `preload_app` + `gc.freeze()` em `when_ready` |
| uvicorn | `--limit-max-requests`, `--workers` | idem; `--limit-concurrency` para backpressure HTTP |
| celery | `--concurrency`; `worker_prefetch_multiplier = 1` para tarefas longas/payloads grandes (o padrão 4 mantém 4× mensagens por processo em memória; `0` = ilimitado) | `worker_max_tasks_per_child`, `worker_max_memory_per_child` (**KB**; ponto de partida: 75 % da RAM ÷ concorrência) — baixo demais faz o worker só reiniciar |
| Lambda | 1 invocação por ambiente; estado de módulo persiste entre invocações **warm** | cuidado com cache de módulo que cresce (MEM-12): `deque(maxlen)`/limpar por invocação |

Reciclar não corrige o vazamento — compra tempo. O conserto é achar a retenção (`medicao-profiling.md`).

## 5. Checklist de concorrência (review P2.MEM)

- [ ] Fan-out assíncrono com `Semaphore`/`TaskGroup`/lotes; filas com `maxsize` (MEM-16/17).
- [ ] Pools com `max_workers`/`maxtasksperchild`; resultados consumidos em stream, não `list()` inteira.
- [ ] Pai gordo + fork → `gc.freeze()`; spawn → `initializer` carrega uma vez por worker; dados compartilhados via `shared_memory`/mmap (MEM-24).
- [ ] Servidor/worker com reciclagem e limite de memória declarados (MEM-22).
- [ ] Teste de orçamento cobre o cenário "N tarefas concorrentes".

## Fontes

- `asyncio.Semaphore`/`TaskGroup`/`Queue(maxsize)`: https://docs.python.org/3/library/asyncio-sync.html · https://docs.python.org/3/library/asyncio-task.html#task-groups · https://docs.python.org/3/library/asyncio-queue.html
- `concurrent.futures`: https://docs.python.org/3/library/concurrent.futures.html · `multiprocessing` 3.14 (forkserver padrão em POSIX, `set_forkserver_preload`, `maxtasksperchild`): https://docs.python.org/3.14/library/multiprocessing.html · `shared_memory` (`track`, `close`/`unlink`, `SharedMemoryManager`): https://docs.python.org/3/library/multiprocessing.shared_memory.html · pickle protocolo 5 out-of-band: https://docs.python.org/3/library/pickle.html#out-of-band-buffers
- Celery — Optimizing (`worker_prefetch_multiplier`, `worker_max_memory_per_child`): https://docs.celeryq.dev/en/stable/userguide/optimizing.html · Adam Johnson — reciclagem gunicorn/Celery contra vazamentos: https://adamj.eu/tech/2019/09/19/working-around-memory-leaks-in-your-django-app/
- `gc.freeze()`: https://docs.python.org/3/library/gc.html#gc.freeze · Instagram Engineering — "Copy-on-write friendly Python garbage collection": https://instagram-engineering.com/copy-on-write-friendly-python-garbage-collection-ad6ed5233ddf · "Dismissing Python Garbage Collection at Instagram": https://instagram-engineering.com/dismissing-python-garbage-collection-at-instagram-4dca40b29172
- gunicorn settings (`max_requests`, `max_requests_jitter`): https://docs.gunicorn.org/en/stable/settings.html · uvicorn: https://www.uvicorn.org/settings/ · celery `worker_max_memory_per_child`: https://docs.celeryq.dev/en/stable/userguide/configuration.html#worker-max-memory-per-child
- Free-threading (PEP 703) e consumo: https://docs.python.org/3/howto/free-threading-python.html
