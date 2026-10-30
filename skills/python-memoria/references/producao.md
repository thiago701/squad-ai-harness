# python-memoria · reference — Produção: Lambda, containers, modelos e agentes de IA

> Hub: `../SKILL.md`. Regras: MEM-22, MEM-23 (leitura). Em produção o número que importa é o **RSS/HWM** do
> processo contra o **limite declarado** — e o limite é uma decisão de engenharia medida, não um default.

## 1. AWS Lambda (Python) — memória é CPU é custo (MEM-23)

- `MemorySize` (128 MB – 10 240 MB, passos de 1 MB) também aloca CPU proporcional — **1 769 MB = 1 vCPU** (doc
  oficial): subir memória costuma **baixar** duração e, muitas vezes, o custo total (GB-s). Decida com **AWS Lambda
  Power Tuning** (state machine que executa a função em várias configurações e plota custo × duração; estratégias
  cost/speed/balanced) — nunca por palpite; 128 MB com pandas/numpy é dimensionamento errado, não bug.
- Ambiente **warm** reaproveita o processo: estado de módulo (clientes, modelos, caches) persiste → carregue
  **fora do handler** uma vez; cache de módulo que cresce entre invocações é MEM-12 (`deque(maxlen)`/limpar).
- Arquivos grandes em `/tmp` (512 MB – 10 GB efêmero) em blocos, não em memória; `download_fileobj` direto para
  `/tmp`.
- Pacote menor = cold start menor: só dependências necessárias (layers para pandas/pyarrow), sem `tests/`,
  `__pycache__` e docs; `-O`/`PYTHONDONTWRITEBYTECODE` conforme o runtime. **SnapStart para Python** (GA 11/2024,
  runtimes 3.12+): snapshot Firecracker de memória + disco tirado **após o init** ao publicar a versão; o que está
  em memória no snapshot conta para o pico. Hooks `snapshot_restore_py`: `@register_before_snapshot` (feche
  conexões) e `@register_after_restore` (recrie conexões; gere `uuid4()`/seeds/caches de DNS **aqui**, nunca no
  init — senão todas as restaurações repetem o mesmo valor). Cobra cache de snapshot por versão + restauração.
- Observabilidade: `REPORT ... Max Memory Used` no log de cada invocação (Powertools/CloudWatch Insights
  `stats max(@maxMemoryUsed)`) — é o HWM real; alarme quando passa de ~80 % do `MemorySize`.
- Métrica: EMF/Powertools para `memoria_pico_mb` por caminho crítico quando o handler processa lotes variáveis.

## 2. Containers (ECS/Kubernetes/Docker) (MEM-22)

- Limite explícito: Kubernetes `resources.limits.memory` (cgroup v2 `memory.max`); ECS `memory`/`memoryReservation`.
  Sem limite, o processo vizinho é quem morre. OOMKilled = exit code **137** (128 + SIGKILL 9) com
  `Reason: OOMKilled`; desde o K8s 1.28 (cgroup v2) `memory.oom.group=1` mata **todos** os processos do container.
  Dimensione o limite em **pico de RSS medido + 10-20 %**; `requests = limits` (QoS Guaranteed) protege do eviction.
  De dentro do container, o teto está em `/sys/fs/cgroup/memory.max` — leia-o para calibrar `memory_limit` do DuckDB,
  tamanho de lote e `max_workers`, em vez de `os.cpu_count()`/RAM da máquina.
- Python não "vê" o cgroup: `os.cpu_count()` e heurísticas de workers mentem — passe `--workers` explícito.
- Reciclagem: gunicorn `--max-requests N --max-requests-jitter M`, uvicorn `--limit-max-requests`, celery
  `worker_max_memory_per_child` — teto temporal para vazamento; não substitui corrigir.
- Alocador: RSS alto com heap Python estável → fragmentação do glibc malloc com várias threads/arenas:
  `MALLOC_ARENA_MAX=2` (ou `1`), `MALLOC_TRIM_THRESHOLD_`; alternativa jemalloc via `LD_PRELOAD` (ou mimalloc).
  `PYTHONMALLOC=malloc` só para diagnóstico (perde pymalloc). Meça com e sem — não copie flags de blog.
- Imagem: `python:3.x-slim`, sem compiladores no runtime; `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`.
- Health/readiness não devem alocar; endpoint de métricas expõe RSS (`psutil`/`/proc/self/status`) para o
  autoscaler e o alarme.

## 3. Import e inicialização

- `python -X importtime -c "import app"` (`-X importtime=2` no 3.14 marca também os já em cache) mostra o custo de
  cada import; importe pesado (pandas, torch, boto3 clients) **uma vez**, no lugar certo (módulo para warm reuse;
  função para caminhos raros).
- Import preguiçoso para dependências opcionais: `importlib.util.LazyLoader` ou import dentro da função. **PEP 810
  (Python 3.15)** oficializa `lazy import x` / `lazy from x import y` (`-X lazy_imports=normal|all`,
  `PYTHON_LAZY_IMPORTS`): a PEP reporta **−30 a −40 % de memória** e −50 a −70 % de startup em serviços reais — ao
  migrar para 3.15, é o primeiro ganho de cold start a colher.
- 3.13+ já grava `.pyc` ~5 % menores (docstrings sem indentação); `-OO` remove asserts e docstrings em imagem final.
- `sys.flags`/`-X frozen_modules`, `.pyc` em imagem já compilada (`python -m compileall`) reduzem CPU, não RSS.

## 4. Modelos e agentes de IA

- **Um modelo por processo**, carregado no startup (ou no `initializer` do worker), nunca por request; em
  processos forkados, `gc.freeze()` após carregar (`concorrencia-processos.md`).
- Inferência: `torch.inference_mode()`/`no_grad()` (sem grafo de autograd), `fp16`/`bf16`/int8 quando a
  precisão permite, `del tensor; gc.collect(); torch.cuda.empty_cache()` entre lotes grandes; batch size
  dimensionado pela VRAM/RAM medida.
- Embeddings: `float32` → `float16` (metade) ou **quantização** — `sentence_transformers.quantization.quantize_embeddings`
  com `precision="int8"` (**4×** menos, ~99 % do desempenho de recuperação com rescoring) ou `"binary"` (**32×**
  menos, ~96 % com rescoring; varia por modelo); 250 M vetores × 1024 dims: 954 GB float32 → 238 GB int8 → 30 GB
  binário. No FAISS, bytes por vetor: `IndexFlatL2/IP` = 4·d, `IndexIVFFlat` = 4·d + 8, `IndexHNSWFlat` =
  4·d + 8·M (M maior = mais RAM), `IndexScalarQuantizer` SQ8 = d, `IndexIVFPQ` = ⌈M·nbits/8⌉ + 8. Não carregue o
  corpus inteiro para reindexar — stream.
- **Agentes**: contexto/transcripts em `deque(maxlen)` ou sumarização por janela; respostas em **streaming**
  (não acumule o texto inteiro antes de repassar); tool outputs grandes truncados/compactados antes de entrar
  no histórico (`compressao-tool-output`); sessões longas persistem em disco, não em listas vivas.
- Harness da própria Squad: scripts de longa duração (harvester, batman) seguem as mesmas regras — `ops/run.py
  mem-lint` mede a densidade de achados e `medir --so-rss` o pico por rotina.

## 5. Checklist de produção (review P2.MEM)

- [ ] Limite de memória declarado (Lambda `MemorySize` via Power Tuning; container `limits.memory`) e alarme a ~80 %.
- [ ] Reciclagem/`max-requests` em servidores e workers; `maxtasksperchild` em pools.
- [ ] Carregamento pesado uma vez por processo; cache de módulo com teto.
- [ ] `MALLOC_ARENA_MAX`/jemalloc **medidos** quando RSS ≠ heap; `-X importtime` revisado em cold start sensível.
- [ ] IA: modelo único por processo, precisão reduzida onde cabe, contexto com janela, streaming de saída.

## Fontes

- Lambda memória/CPU (1 769 MB = 1 vCPU): https://docs.aws.amazon.com/lambda/latest/dg/configuration-memory.html · Power Tuning: https://github.com/alexcasalboni/aws-lambda-power-tuning · `/tmp` e ambiente de execução: https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtime-environment.html · SnapStart (Python): https://docs.aws.amazon.com/lambda/latest/dg/snapstart.html · anúncio GA SnapStart Python/.NET (hooks, cobrança): https://aws.amazon.com/blogs/aws/aws-lambda-snapstart-for-python-and-net-functions-is-now-generally-available/ · Powertools Python Logger/Metrics: https://docs.aws.amazon.com/powertools/python/latest/
- PEP 810 — Explicit lazy imports (3.15): https://peps.python.org/pep-0810/ · `-X importtime=2` (What's New 3.14): https://docs.python.org/3.14/whatsnew/3.14.html
- OOMKilled em Kubernetes (137, `memory.oom.group`, dimensionamento): https://www.netdata.cloud/guides/kubernetes/kubernetes-pod-oomkilled/
- Quantização de embeddings (int8/binário, números): https://huggingface.co/blog/embedding-quantization · FAISS — memória por tipo de índice: https://github.com/facebookresearch/faiss/wiki/Faiss-indexes
- Kubernetes resources/limits: https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/ · cgroup v2 `memory.max`: https://docs.kernel.org/admin-guide/cgroup-v2.html
- glibc `MALLOC_ARENA_MAX`/mallopt: https://www.gnu.org/software/libc/manual/html_node/Memory-Allocation-Tunables.html · `PYTHONMALLOC`: https://docs.python.org/3/using/cmdline.html#envvar-PYTHONMALLOC · jemalloc: https://jemalloc.net/
- gunicorn `max_requests`: https://docs.gunicorn.org/en/stable/settings.html#max-requests · `-X importtime`: https://docs.python.org/3/using/cmdline.html#cmdoption-X
- PyTorch memória: https://pytorch.org/docs/stable/notes/cuda.html#memory-management · FAISS quantização: https://github.com/facebookresearch/faiss/wiki/Faiss-indexes
