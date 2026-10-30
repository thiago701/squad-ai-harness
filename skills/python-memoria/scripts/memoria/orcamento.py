"""Orçamento de memória — medir o pico e falhar quando o código gasta mais do que o combinado.

Duas réguas, sempre juntas:
  * **heap Python** — `tracemalloc` (só objetos Python; preciso, por linha, independente de SO);
  * **RSS do processo** — o que o SO/cgroup/Lambda realmente cobra (inclui numpy/pandas/C, pymalloc, fragmentação).
    Linux: /proc/self/status (VmRSS, VmHWM) · macOS: resource.ru_maxrss (bytes) · Windows: psapi via ctypes.

Uso em teste (stdlib, sem plugin):

    from memoria.orcamento import orcamento

    def test_processa_lote_dentro_do_orcamento(tmp_path):
        with orcamento(max_pico_mb=64, rotulo="processar_lote") as m:
            processar_lote(tmp_path / "entrada.csv")
        assert m.pico_mb < 64          # redundante: o `with` já levanta OrcamentoExcedido

Uso como decorador: `@orcamento(max_pico_mb=32)` · CLI: `lint_memoria.py medir --script x.py -- args`.
Para profiling fino (quem alocou, nativo, flamegraph) use memray/scalene — references/medicao-profiling.md.
"""
from __future__ import annotations

import contextlib
import functools
import os
import platform
import sys
import time
import tracemalloc
from dataclasses import dataclass, field

_MB = 1024 * 1024


class OrcamentoExcedido(AssertionError):
    """Pico de memória acima do orçamento — AssertionError para o pytest tratar como falha de teste."""


# --------------------------------------------------------------------------- #
# RSS por plataforma (stdlib)
# --------------------------------------------------------------------------- #
def _rss_linux() -> tuple[float | None, float | None]:
    try:
        with open("/proc/self/status", encoding="ascii", errors="replace") as fh:
            rss = hwm = None
            for linha in fh:
                if linha.startswith("VmRSS:"):
                    rss = int(linha.split()[1]) / 1024
                elif linha.startswith("VmHWM:"):
                    hwm = int(linha.split()[1]) / 1024
            return rss, hwm
    except OSError:
        return None, None


def _rss_resource() -> tuple[float | None, float | None]:
    try:
        import resource
        ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        hwm = ru / _MB if sys.platform == "darwin" else ru / 1024   # macOS: bytes · Linux/BSD: KB
        return None, hwm
    except (ImportError, OSError, AttributeError):
        return None, None


def _rss_windows() -> tuple[float | None, float | None]:
    try:
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        proc = ctypes.windll.kernel32.GetCurrentProcess()
        if not ctypes.windll.psapi.GetProcessMemoryInfo(proc, ctypes.byref(pmc), pmc.cb):
            return None, None
        return pmc.WorkingSetSize / _MB, pmc.PeakWorkingSetSize / _MB
    except Exception:  # noqa: BLE001 — medição é best-effort
        return None, None


def rss_mb() -> tuple[float | None, float | None]:
    """(RSS atual em MB, pico/high-water mark em MB) — None quando a plataforma não expõe."""
    if sys.platform.startswith("linux"):
        atual, hwm = _rss_linux()
        if hwm is not None:
            return atual, hwm
    if sys.platform == "win32":
        return _rss_windows()
    return _rss_resource()


# --------------------------------------------------------------------------- #
# Medição
# --------------------------------------------------------------------------- #
@dataclass
class Medicao:
    rotulo: str = ""
    pico_mb: float = 0.0            # pico do heap Python (tracemalloc) durante o bloco
    atual_mb: float = 0.0           # heap Python ainda vivo ao sair (vazamento se cresce entre repetições)
    rss_antes_mb: float | None = None
    rss_depois_mb: float | None = None
    rss_pico_mb: float | None = None   # high-water mark do processo (só sobe; inclui C/numpy)
    duracao_s: float = 0.0
    plataforma: str = field(default_factory=lambda: f"{platform.system()} {platform.python_version()}")

    @property
    def rss_delta_mb(self) -> float | None:
        if self.rss_antes_mb is None or self.rss_depois_mb is None:
            return None
        return round(self.rss_depois_mb - self.rss_antes_mb, 2)

    def resumo(self) -> str:
        rss = (f" rss={self.rss_antes_mb:.1f}→{self.rss_depois_mb:.1f} MB (pico {self.rss_pico_mb:.1f})"
               if self.rss_antes_mb is not None and self.rss_depois_mb is not None and self.rss_pico_mb is not None else " rss=n/d")
        return (f"[memoria] {self.rotulo or 'bloco'}: heap pico={self.pico_mb:.2f} MB vivo={self.atual_mb:.2f} MB"
                f"{rss} · {self.duracao_s:.3f}s · {self.plataforma}")


class _Contexto:
    def __init__(self, max_pico_mb: float | None, max_rss_delta_mb: float | None, rotulo: str, imprimir: bool,
                 heap: bool = True):
        self.max_pico_mb, self.max_rss_delta_mb, self.rotulo, self.imprimir = max_pico_mb, max_rss_delta_mb, rotulo, imprimir
        self.heap = heap                 # False = só RSS (tracemalloc infla o RSS em ~2-4x o heap rastreado)
        self.medicao = Medicao(rotulo=rotulo)
        self._ja_rodava = False

    def __enter__(self) -> Medicao:
        self._ja_rodava = tracemalloc.is_tracing()
        if self.heap and not self._ja_rodava:
            tracemalloc.start()
        elif self.heap:
            tracemalloc.reset_peak()
        self.medicao.rss_antes_mb, _ = rss_mb()
        self._t0 = time.perf_counter()
        return self.medicao

    def __exit__(self, exc_type, exc, tb):
        m = self.medicao
        m.duracao_s = round(time.perf_counter() - self._t0, 4)
        if self.heap:
            atual, pico = tracemalloc.get_traced_memory()
            m.atual_mb, m.pico_mb = round(atual / _MB, 3), round(pico / _MB, 3)
            if not self._ja_rodava:
                tracemalloc.stop()
        m.rss_depois_mb, m.rss_pico_mb = rss_mb()
        if self.imprimir:
            print(m.resumo())
        if exc_type is not None:
            return False
        if self.max_pico_mb is not None and m.pico_mb > self.max_pico_mb:
            raise OrcamentoExcedido(f"{m.rotulo or 'bloco'}: heap pico {m.pico_mb:.2f} MB > orçamento {self.max_pico_mb} MB")
        if self.max_rss_delta_mb is not None and m.rss_delta_mb is not None and m.rss_delta_mb > self.max_rss_delta_mb:
            raise OrcamentoExcedido(f"{m.rotulo or 'bloco'}: RSS cresceu {m.rss_delta_mb:.1f} MB > orçamento {self.max_rss_delta_mb} MB")
        return False


def orcamento(max_pico_mb: float | None = None, *, max_rss_delta_mb: float | None = None,
              rotulo: str = "", imprimir: bool = False, heap: bool = True):
    """Context manager OU decorador. Levanta OrcamentoExcedido (AssertionError) ao estourar.

    `heap=False` desliga o tracemalloc e mede só RSS — use para números de produção (o tracemalloc
    guarda um traceback por bloco alocado e infla o RSS); `heap=True` para localizar e testar."""
    ctx = _Contexto(max_pico_mb, max_rss_delta_mb, rotulo, imprimir, heap)

    def decorador(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            with _Contexto(max_pico_mb, max_rss_delta_mb, rotulo or fn.__name__, imprimir, heap):
                return fn(*a, **kw)
        return wrapper

    class _Ambos:
        def __enter__(self_):
            return ctx.__enter__()

        def __exit__(self_, *exc):
            return ctx.__exit__(*exc)

        def __call__(self_, fn):
            return decorador(fn)

    return _Ambos()


def medir(fn, *args, repeticoes: int = 1, **kwargs) -> list[Medicao]:
    """Roda `fn` N vezes medindo cada uma — `atual_mb` crescendo entre repetições é o sinal clássico de vazamento."""
    saida = []
    for i in range(repeticoes):
        with orcamento(rotulo=f"{getattr(fn, '__name__', 'fn')}#{i + 1}") as m:
            fn(*args, **kwargs)
        saida.append(m)
    return saida


def medir_script(caminho: str, argv: list[str] | None = None, heap: bool = True) -> Medicao:
    """Executa um script Python no processo atual sob medição (runpy) — para a CLI `medir`."""
    import runpy
    argv_antigo = sys.argv
    sys.argv = [caminho] + list(argv or [])
    try:
        with orcamento(rotulo=os.path.basename(caminho), heap=heap) as m:
            with contextlib.suppress(SystemExit):
                runpy.run_path(caminho, run_name="__main__")
    finally:
        sys.argv = argv_antigo
    return m
