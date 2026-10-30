# python-memoria · reference — Medição, profiling e orçamento em teste

> Hub: `../SKILL.md`. Regras: MEM-21 (leitura). Ferramenta da Squad: `scripts/memoria/orcamento.py` e
> `lint_memoria.py medir`. Lei da casa: **nenhuma otimização de memória entra sem número antes/depois**.

## 1. Os dois números — e por que divergem

| Régua | O que mede | Quando usar |
|---|---|---|
| `tracemalloc` (`get_traced_memory()` → atual, **pico**) | só alocações feitas pelo alocador do CPython (objetos Python), com traceback por bloco | **localizar** e **testar**: por linha/arquivo, `snapshot.compare_to(anterior, "lineno")` |
| **RSS / HWM do processo** (`/proc/self/status` VmRSS/VmHWM, `ru_maxrss`, psapi no Windows, `psutil.memory_info()`) | o que o SO entrega ao processo: Python + numpy/pandas/C + pymalloc/arenas + fragmentação | **dimensionar** (cgroup/Lambda/Kubernetes cobram isso) e detectar vazamento real |

Divergência normal: tracemalloc 38 MB para `list(range(10**6))` e RSS +130 MB **com** tracemalloc ligado
(ele guarda um traceback por bloco) — e +38 MB **sem** (`orcamento(heap=False)`). Número de produção =
`heap=False`. RSS que não desce após `del` não é vazamento: pymalloc devolve arenas só quando 100 % vazias
(`runtime-alocador.md`).

## 2. Orçamento em teste (stdlib) — `scripts/memoria/orcamento.py`

```python
from memoria.orcamento import orcamento, medir

def test_processar_lote_dentro_do_orcamento(tmp_path):
    with orcamento(max_pico_mb=64, rotulo="processar_lote") as m:     # OrcamentoExcedido é AssertionError
        processar_lote(gerar_csv(tmp_path, linhas=200_000))
    assert m.pico_mb < 64 and (m.rss_delta_mb is None or m.rss_delta_mb < 128)

def test_sem_vazamento_entre_lotes():
    ms = medir(processar_lote, lote_pequeno(), repeticoes=5)
    assert ms[-1].atual_mb - ms[1].atual_mb < 1.0      # "vivo" crescendo a cada volta = retenção
```
Pytest: `templates/pytest/conftest_memoria.py` dá a fixture `orcamento_memoria` e o marker
`@pytest.mark.memoria(max_pico_mb=32)`. Com `pytest-memray` (`pytest --memray`, Linux/macOS):
`@pytest.mark.limit_memory("32 MB")` falha se o **pico** (Python + nativo) exceder;
`@pytest.mark.limit_leaks("1 MB")` conta alocações vivas ao fim do teste (rode a função em loop; overhead alto);
`@pytest.mark.limit_leaked_objects()` exige Python ≥ 3.13.3; `--memray-bin-path` guarda o `.bin` para análise.
Para medir o pico de **um trecho** com a stdlib: `tracemalloc.reset_peak()` antes do trecho e
`get_traced_memory()[1]` depois.
CLI: `lint_memoria.py medir --script etl.py --max-rss-mb 512 --so-rss -- entrada.csv` (roda o script no processo,
imprime heap pico/vivo, RSS antes→depois e HWM; reprova acima do teto).

Regra do orçamento: defina-o pelo **contrato** ("N linhas em ≤ X MB", "Lambda de 512 MB → pico ≤ 350 MB"), não
pelo valor atual + folga; grave o número no teste e no PR.

## 2b. Árvore de processos — `scripts/memoria/arvore.py` (quando o "programa" é um sistema de processos)

`orcamento`/`tracemalloc` medem **um** processo Python. Harness, pipelines, hooks e agentes são **árvores**:
pai + filhos + netos (`git`, `java`, `claude`, outros Pythons). `lint_memoria.py arvore -- <comando>` amostra a
árvore inteira (psutil em qualquer SO; `/proc` no Linux sem psutil) e devolve, por processo, RSS/USS/PSS máximo,
vida e cmdline; e, da árvore, **pico de RSS e de PSS** (PSS rateia páginas compartilhadas — é o custo real),
processos simultâneos, série temporal e `ru_maxrss` do maior filho. `--execs` (Linux + strace) conta **todos**
os `execve` por programa — processos de 10 ms que a amostragem não vê. Regras de leitura:

- **custo para a máquina = pico de PSS da árvore**, nunca a soma dos RSS (pai e filho após fork compartilham;
  3 hooks simultâneos: 94 MB RSS → 52 MB PSS);
- muitos processos de vida curta = problema de **CPU/latência de criação de processo**, não de RAM (13 261
  `execve` numa suíte de testes custaram 6 min de `sys` sob strace e 0 MB residente);
- **crescimento** aparece na série (`serie`), não no pico: suba no tempo = retenção; platô = regime;
- compare sempre a mesma máquina, 3+ repetições, mediana e faixa (`ops/bench_memoria.py` faz isso).

## 3. Achar a linha — ferramentas

| Ferramenta | Para quê | Comando |
|---|---|---|
| `tracemalloc` (stdlib) | top alocações por linha, diff entre snapshots | `tracemalloc.start(25)`; `s2.compare_to(s1, "lineno")[:10]`; `tracemalloc.get_traced_memory()` |
| **memray** (Bloomberg, Apache-2.0, Linux/macOS) | perfil completo (Python + nativo), flamegraph, live, por thread; `--native` (frames C), `--trace-python-allocators` (cada bloco do pymalloc — arquivo muito maior), `--follow-fork`, `--aggregate` (sem linha do tempo, arquivo menor) | `memray run -o out.bin app.py` · `memray flamegraph out.bin` · `memray run --live -m modulo` · `memray tree/summary/stats` |
| **Scalene** (Apache-2.0; 2.4 em 10/2026, suporta 3.14 e 3.14t, memória também no Windows) | CPU (Python/nativo/sistema) + memória por linha separando Python vs nativo + **copy volume** (MB/s — flagra cópias acidentais) + GPU; overhead ~10-20 %; `--memory-leak-detector` experimental | `scalene --memory app.py` · `scalene view --html` |
| **Fil** (pythonspeed) | pico de memória de job batch, por linha de origem | `fil-profile run etl.py` |
| ~~`memory_profiler`/`mprof`~~ | **não mantido** (aviso no README); mede RSS via psutil, não aloca por linha com confiança | não adote em projeto novo — memray/scalene/tracemalloc |
| `sys.remote_exec(pid, script)` (3.14, PEP 768) | anexa um script (ex.: `tracemalloc` snapshot) a um processo **vivo** sem reiniciar; desligue em produção com `PYTHON_DISABLE_REMOTE_DEBUG=1` se a política exigir | `sys.remote_exec(pid, "dump_mem.py")` |
| `pympler` | tamanho real de objetos (`asizeof`, recursivo), `tracker.SummaryTracker` entre pontos | `asizeof.asizeof(obj)`; `tr.print_diff()` |
| `objgraph` | quem segura a referência (grafo de retenção) | `objgraph.show_most_common_types()`; `show_backrefs(obj, max_depth=5)` |
| `sys.getsizeof` | tamanho **raso** (não segue referências) — útil só para tipos simples | `sys.getsizeof(x)` |
| `gc` | ciclos não coletados, `gc.get_stats()`, `gc.get_referrers` | `gc.collect()` antes de medir; `gc.set_debug(gc.DEBUG_SAVEALL)` em investigação |
| `psutil` (opcional) | `rss/uss/pss`, por processo filho | `psutil.Process().memory_full_info()` |
| py-spy / perf (3.12+ `-X perf`) | CPU; útil para ver GC consumindo tempo | `py-spy top --pid` |

Roteiro de vazamento: (1) `medir(fn, repeticoes=N)` — vivo cresce? (2) sim → `tracemalloc.compare_to` entre a
3ª e a N-ésima volta mostra **onde** (3) `objgraph.show_backrefs` mostra **quem segura** (4) corrija pela doutrina
(`padroes-codigo.md` §3-4) (5) trave com teste `test_sem_vazamento_*`. Vivo estável e RSS alto → fragmentação/
arenas → `runtime-alocador.md` §3 (`MALLOC_ARENA_MAX`, jemalloc) e revisão de picos transitórios.

## 4. Benchmark reproduzível

- Mesmo dado sintético (gerado por seed), mesmo Python, `gc.collect()` antes, 3+ repetições, reporte **mediana** do
  pico e do RSS; nunca compare com tracemalloc ligado numa medição e desligado na outra.
- Registre no PR: `antes: heap pico X MB / RSS Y MB · depois: … · comando usado`. O `relatorio.json` da lente guarda a
  densidade de achados/1k linhas — SLI do repositório ao longo do tempo (`ops/logs/python-memoria`).

## 5. Skills da comunidade avaliadas (padrões absorvidos, não cópias)

Levantamento de 28/10/2026 (`docs/relatorios/pesquisa-memoria-python-2026-10-28.md`, §7): **não existe skill
open-source dedicada e madura de memória em Python** — o que há são skills genéricas de performance, quase todas
cópias da mesma origem. Por relevância × estrelas:

| Skill (repo) | ★ / licença | Avaliação |
|---|---|---|
| `python-performance-optimization` — wshobson/agents | 41,9 k · MIT | mais instalada; cobre `timeit`/cProfile/geradores/`"".join`, mas recomenda **`memory_profiler` (não mantido)** e não cita memray/tracemalloc/`__slots__` — rasa para memória |
| `python-performance-optimization` — sickn33/agentic-awesome-skills | 48,7 k · MIT | catálogo que **redistribui** a skill acima (mesmo conteúdo) — índice, não fonte |
| `python-performance` — athola/claude-night-market | 343 · MIT | 3 módulos (profiling com py-spy, 11 padrões, memória com `tracemalloc` + `weakref`) |
| `python-profiling` — fgmacedo/agent-skills | 10 · MIT | a mais correta tecnicamente: árvore de decisão (py-spy processo vivo → scalene CPU+memória → tracemalloc rápido → memray flamegraph), `__slots__` em classes de massa |

Padrões incorporados nesta skill (reescritos, com fonte primária): "measure first" com memray/scalene/tracemalloc,
generators-first, slots em modelos de domínio, chunked I/O, Power Tuning no Lambda. Padrão **rejeitado**:
`memory_profiler` como ferramenta oficial.

## Fontes

- `tracemalloc`: https://docs.python.org/3/library/tracemalloc.html · `resource.getrusage` (`ru_maxrss` em KB no Linux, bytes no macOS): https://docs.python.org/3/library/resource.html · `sys.getsizeof` (raso): https://docs.python.org/3/library/sys.html#sys.getsizeof · `gc`: https://docs.python.org/3/library/gc.html
- memray (`run`, `--native`, `--follow-fork`, `--aggregate`): https://bloomberg.github.io/memray/run.html · pytest-memray (`limit_memory`, `limit_leaks`, `limit_leaked_objects`): https://pytest-memray.readthedocs.io/en/stable/usage.html
- Scalene (PyPI, versões/suporte): https://pypi.org/project/scalene/ · Fil: https://github.com/pythonspeed/filprofiler · `memory_profiler` README ("no longer actively maintained"): https://github.com/pythonprofilers/memory_profiler · pympler: https://pympler.readthedocs.io/ · objgraph: https://mg.pov.lt/objgraph/ · psutil: https://psutil.readthedocs.io/
- `sys.remote_exec` (PEP 768, 3.14): https://docs.python.org/3.14/whatsnew/3.14.html#pep-768-safe-external-debugger-interface-for-cpython · `-X perf`/`-X perf_jit`: https://docs.python.org/3/howto/perf_profiling.html
- pythonspeed — "Measuring memory usage in Python: it's tricky" (RSS vs heap): https://pythonspeed.com/articles/measuring-memory-python/ · "The Fil memory profiler / peak memory": https://pythonspeed.com/fil/
- Windows `GetProcessMemoryInfo` (psapi): https://learn.microsoft.com/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo
