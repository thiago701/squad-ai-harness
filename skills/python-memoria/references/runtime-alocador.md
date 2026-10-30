# python-memoria · reference — Runtime e alocador do CPython (o que o código não vê)

> Hub: `../SKILL.md`. Regras: MEM-13 (+ contexto para MEM-20/22). Saber **onde** a memória vai é o que separa
> otimização de superstição. Valores abaixo são de CPython 64-bit (3.12/3.13); confirme com `sys.getsizeof`
> (raso) e `pympler.asizeof` (profundo) na sua versão.

## 1. Quanto custa um objeto

| Objeto | Bytes (aprox.) | Comentário |
|---|---|---|
| `int` pequeno | 28 | –5..256 são singletons; cada inteiro "grande" é um objeto novo |
| `float` | 24 | numpy `float64` em array: 8 |
| `str` ASCII de n chars | 41 + n | latin-1 1 B/char, UCS-2 2 B, UCS-4 4 B — **um** emoji quadruplica a string |
| `tuple` de n | 40 + 8n | imutável, sem over-allocation |
| `list` de n | 56 + 8n (+ ~12 % de folga) | os itens são **ponteiros**: os objetos apontados contam à parte |
| `dict` vazio / pequeno | 64 / ~200+ | tabela compacta (3.6+); instâncias compartilham chaves (*key-sharing*) |
| instância comum (`__dict__`) | ~48 + dict | o `__dict__` é criado preguiçosamente (3.11+), mas aparece ao atribuir |
| instância com `__slots__`/`dataclass(slots=True)` | ~48 + 8 por slot | sem `__dict__` nem `__weakref__`; **−30 %** com 3 atributos (medido via tracemalloc: 128 → 96 B por instância, 3.12) a **−60 %** com 1 M de `Point` (207 → 86 MB, pythonspeed); atributo mais rápido |
| `dict` de 3 chaves como registro | ~224 B por registro (medido) | ~2,3× uma instância com slots — "lista de dicts" é a forma mais cara de registro |
| `list` de 1 M `int` | 40 MB (8 MB de ponteiros + 28 MB de ints, medido) | `array("q")`: 8,2 MB · numpy `int64`: 8,0 MB — **5× menos** |

Consequências: milhões de objetos pequenos custam mais em **cabeçalhos e ponteiros** do que em dados → colunas
homogêneas (`array`/numpy/arrow), `slots`, `msgspec.Struct(gc=False, array_like=True)` (sem `__dict__`, fora do
GC) ou `NamedTuple` para registros em massa; `sys.intern()` para strings repetidas (chaves, enums como texto).
Benchmark oficial do msgspec (mesmos dados): classe comum 211,7 MiB / 80 ms de pausa de GC → `__slots__` 120,1 MiB
→ `Struct` 120,1 MiB / 14 ms → `Struct(gc=False)` **104,9 MiB / 1 ms** (só quando não há ciclos). Pydantic v2 valida
bem na **borda**; como modelo de domínio em massa é pesado — converta para dataclass/Struct.
Key-sharing dicts (PEP 412): instâncias da mesma classe compartilham a tabela de chaves (−10 a −20 % em programas
OO) **enquanto** os atributos forem criados na mesma ordem — atribua todos no `__init__`, nunca "quando precisar".

## 2. pymalloc, arenas e "o RSS não volta"

- Objetos ≤ 512 bytes saem do **pymalloc**: pools de 16 KiB dentro de arenas de 1 MiB (3.10+); objetos maiores
  vão ao `malloc` do sistema.
- Uma arena só é devolvida ao SO quando **todos** os seus pools estão vazios. Um objeto vivo segura 1 MiB.
  Por isso `del` + `gc.collect()` reduz o *heap rastreado* e **não** reduz o RSS — isso **não** é vazamento.
- Picos transitórios ficam: se um passo alocou 2 GB uma vez, o RSS tende a ficar perto disso (fragmentação).
  Remédio é não ter o pico (streaming) ou isolar o passo em **subprocesso** que morre (devolve tudo).
- glibc `malloc` com threads cria várias **arenas** (até 8 × núcleos): RSS cresce com fragmentação →
  `MALLOC_ARENA_MAX=2`, `MALLOC_TRIM_THRESHOLD_`, ou jemalloc/mimalloc por `LD_PRELOAD` — **medido**.
  Defaults do glibc (`mallopt(3)`): `M_TRIM_THRESHOLD` e `M_MMAP_THRESHOLD` começam em 128 KiB mas o mmap threshold
  **sobe dinamicamente até 32 MiB** (64-bit) — blocos grandes liberados deixam de voltar ao SO. Fixar
  `MALLOC_MMAP_THRESHOLD_=65536 MALLOC_TRIM_THRESHOLD_=65536` desliga o ajuste dinâmico: caso público (troca de
  modelos PyTorch) saiu de +3 GB por troca e OOM em ~17 h para RSS estável, onde `del`+`gc.collect()` não tinham
  efeito. Quando nem isso resolve, jemalloc (`LD_PRELOAD=libjemalloc.so.2`, `MALLOC_CONF="narenas:1,tcache:false"`).
- `PYTHONMALLOC=malloc` desliga o pymalloc (diagnóstico com valgrind/ASan; custa ~15-20 % de desempenho — não é
  remédio de produção); `PYTHONMALLOC=mimalloc` existe desde o 3.13 (obrigatório no build free-threaded);
  `PYTHONMALLOCSTATS=1` imprime estatísticas do pymalloc no exit. `sys._debugmallocstats()` idem em runtime.
- Free lists internas (floats, tuplas pequenas, frames) reutilizam blocos — também não devolvem.

## 3. Garbage collector

- Refcount libera a maioria dos objetos na hora; o **GC cíclico** só existe para ciclos (`a.b = b; b.a = a`).
- Gerações: limiares `gc.get_threshold()` = (700, 10, 10) no 3.12 e **(2000, 10, 10) a partir do 3.13**; coleta
  da geração 2 percorre **tudo** — com milhões de objetos, pausas longas e páginas tocadas.
- **GC incremental do 3.14 foi revertido.** 3.14.0–3.14.4 trouxeram o coletor incremental (pausas ~10× menores),
  mas ele causou "significant memory pressure" em produção (gh-142516; pior caso ~5× a memória do geracional,
  RSS de pico 2,7× num caso relatado) e **3.14.5 (05/2026) voltou ao GC geracional do 3.13**; o 3.15 também
  não o traz (volta só por PEP, 3.16+). Regra da casa: serviços de longa vida exigem **≥ 3.14.5** ou 3.13.x —
  `3.14.[0-4]` em `Dockerfile`/`.python-version`/`requires-python` é achado 🟡 de leitura (MEM-22).
- Instagram (Django pré-fork): `gc.set_threshold(0)` elevou a memória **compartilhada** por worker de 140 para
  225 MB (~8 GB/host, +10 % throughput) e `gc.freeze()` cortou ~50 % do crescimento de memória por request —
  é a origem do padrão `gc.disable()` → `gc.freeze()` → fork → `gc.enable()` documentado no próprio `gc`.
- Objetos sem referências a outros objetos (ints, strs, tuplas de atômicos) nem entram no GC; `msgspec.Struct(gc=False)`
  e `__slots__` reduzem o que o coletor percorre.
- `gc.freeze()` após a inicialização (pai gordo + fork) move tudo para a geração permanente: coletas menores e
  copy-on-write preservado (`concorrencia-processos.md` §3). `gc.disable()` só com `gc.collect()` manual em
  pontos conhecidos — ciclos vazam sem ele.
- `__del__` em objetos cíclicos atrasa a liberação; `weakref` quebra ciclos de cache/observador.

## 4. Free-threading (3.13t/3.14) e JIT

- Build free-threaded (`python3.14t`) remove o GIL: estruturas por objeto crescem (refcount biased, locks) —
  objetos não-GC **dobram** (`None`: 32 B vs 16 B; dict/list mantêm o tamanho), strings internadas viram imortais,
  mimalloc é obrigatório com 4 heaps, e a liberação é adiada por QSBR (`gc.collect()` força;
  `MIMALLOC_PURGE_DELAY=0` devolve páginas antes, pagando desempenho). Penalidade single-thread 5-10 %. Só vale
  para CPU-bound com threads; detecte com `sys._is_gil_enabled()` e **meça RSS antes de migrar**.
- JIT experimental (`PYTHON_JIT=1`, 3.13+; `sys._jit.is_enabled()` no 3.14): PEP 744 reporta **+10-20 % de
  memória** nos benchmarks — não habilite em limite apertado (Lambda pequeno, sidecar).
- Nenhum dos dois substitui os padrões desta skill: o maior ganho continua sendo **não materializar**.

## 5. Strings, bytes e buffers

- `str` é imutável: `s += x` cria nova string (MEM-05); `"".join` ou `io.StringIO`.
- `bytes` imutável, `bytearray` mutável, `memoryview` = **view** sem cópia (fatiar, passar a `write`, `struct`).
- `pickle` protocolo 5 + `buffer_callback`/`PickleBuffer` para transferir numpy/bytes grandes sem cópia (out-of-band).
- `struct`/`array` para registros binários fixos; `dataclass(slots=True)` + `array` de colunas para milhões de linhas.

## 6. Checklist (review P2.MEM)

- [ ] Registros em massa: `slots`/`Struct`/colunas homogêneas, não dicts/instâncias com `__dict__` (MEM-13).
- [ ] Expectativa certa sobre RSS: pico transitório isolado em subprocesso quando precisa devolver memória.
- [ ] GC: `freeze()` pós-init em workers forkados; sem `gc.disable()` solto; ciclos conhecidos com `weakref`.
- [ ] Buffers binários com `memoryview`/`bytearray`; strings com `join`/`intern`.
- [ ] Decisão de free-threading/JIT acompanhada de medição de RSS.

## Fontes

- Memory Management (pymalloc, arenas, domínios): https://docs.python.org/3/c-api/memory.html · `PYTHONMALLOC`/`PYTHONMALLOCSTATS`: https://docs.python.org/3/using/cmdline.html#envvar-PYTHONMALLOC · `sys.getsizeof`: https://docs.python.org/3/library/sys.html#sys.getsizeof · `sys.intern`: https://docs.python.org/3/library/sys.html#sys.intern
- `gc` (gerações, `freeze`, thresholds): https://docs.python.org/3/library/gc.html · Design do GC (devguide): https://devguide.python.org/internals/garbage-collector/ · What's New 3.14 (GC incremental e sua reversão no 3.14.5): https://docs.python.org/3.14/whatsnew/3.14.html#garbage-collection · Discussão oficial da reversão (3.14.5/3.15): https://discuss.python.org/t/reverting-the-incremental-gc-in-python-3-14-and-3-15/107014
- Instagram Engineering — "Dismissing Python Garbage Collection": https://instagram-engineering.com/dismissing-python-garbage-collection-at-instagram-4dca40b29172 · "Copy-on-write friendly Python GC": https://instagram-engineering.com/copy-on-write-friendly-python-garbage-collection-ad6ed5233ddf
- Custo por objeto medido: pythonspeed — "Too many objects: reducing memory overhead": https://pythonspeed.com/articles/python-object-memory/ · benchmark de memória/GC do msgspec: https://jcristharif.com/msgspec/benchmarks.html
- glibc `mallopt(3)` (`M_TRIM_THRESHOLD`, `M_MMAP_THRESHOLD` dinâmico até 32 MiB, `M_ARENA_MAX`): https://man7.org/linux/man-pages/man3/mallopt.3.html · caso `MALLOC_*_THRESHOLD_` (HF Forum): https://discuss.huggingface.co/t/found-the-fix-for-memory-not-being-freed-when-switching-models-on-linux-its-not-python-or-pytorch/174750
- `__slots__`: https://docs.python.org/3/reference/datamodel.html#slots · `dataclass(slots=True)`: https://docs.python.org/3/library/dataclasses.html · PEP 412 key-sharing dicts: https://peps.python.org/pep-0412/ · PEP 393 strings compactas: https://peps.python.org/pep-0393/
- Free-threading HOWTO: https://docs.python.org/3/howto/free-threading-python.html · JIT (PEP 744): https://peps.python.org/pep-0744/
- `memoryview`/buffer protocol: https://docs.python.org/3/c-api/buffer.html · pickle protocolo 5 (PEP 574): https://peps.python.org/pep-0574/
- msgspec Struct (`gc=False`, `array_like`): https://jcristharif.com/msgspec/structs.html · pythonspeed — "Why your Python process doesn't release memory": https://pythonspeed.com/articles/python-memory-not-released/ (fragmentação/arenas)
