"""Árvore de processos sob medição — RSS/USS/PSS por processo, pico da árvore, spawns e vida.

Responde à pergunta que `orcamento.py` (in-process) não responde: **quantos processos um comando cria, o que
cada um custa e por quanto tempo vive**. É o instrumento da Fase 1 (observabilidade) da auditoria de memória da
Squad AI, mas é genérico: serve para qualquer comando (`pytest`, `ops/run.py gate`, um hook, um `claude -p`).

Uso (CLI via `lint_memoria.py arvore -- <cmd> [args]`):

    python lint_memoria.py arvore --rotulo gate --intervalo-ms 50 -- python ops/run.py gate
    python lint_memoria.py arvore --execs -- python hooks/scan_secrets.py        # Linux: conta execve via strace

Como mede
  * Lança o comando e, a cada `intervalo_ms`, amostra a árvore (processo + descendentes) com `psutil`
    (qualquer SO) ou `/proc` (Linux sem psutil). Para cada processo acumula RSS máximo, USS/PSS quando o SO
    expõe (Linux: `smaps_rollup`; Windows: USS via psutil; macOS: só RSS), 1ª/última amostra (vida) e cmdline.
  * **Pico da árvore** = maior soma, numa mesma amostra, de RSS (e de PSS quando há — PSS evita contar duas
    vezes páginas compartilhadas entre pai e filho após fork; é a régua correta para "quanto a máquina gastou").
  * `--execs` (Linux, exige `strace`): conta TODOS os execve, inclusive processos que vivem menos que um
    intervalo de amostragem (um `git rev-parse` de 15 ms some da amostragem, mas não do strace). Sem strace,
    `spawns_vistos` é um piso, nunca o total.
  * `entrada`/`--stdin`: texto entregue ao stdin do comando (hooks do Claude Code e `graphify hook-guard`
    leem o JSON da chamada de ferramenta no stdin; sem isso medem o caminho vazio). Sem `entrada`, stdin
    fica fechado (DEVNULL) para nada travar esperando EOF.
  * Timeout mata a ÁRVORE inteira (psutil `children(recursive=True)`; Windows sem psutil: `taskkill /T /F`),
    não só o processo raiz — senão a medição deixaria órfãos (JVM, `git`, `java`) vivos na máquina.
Limites declarados: amostragem não vê processos de vida < intervalo (use `--execs`); PSS não existe no
Windows/macOS (ficam RSS/USS); o próprio amostrador custa ~1 % de CPU; threads não são processos (ficam
dentro do RSS do pai). **Pico da árvore é sensível ao fork**: quando um processo grande (ex.: `pytest` com
500 MB) faz fork para lançar `git`, por alguns ms existe um filho com o mesmo RSS (copy-on-write) — a soma
de RSS da amostra dobra e até a soma de PSS sobe (as páginas compartilhadas são rateadas, mas as duas metades
entram na soma). Para "quanto custou o maior processo", a régua é `maxrss_maior_filho_mb` (HWM do kernel);
`pico_rss_arvore_mb` responde "quanto a máquina precisou ter livre naquele instante" e inclui esses
transitórios. Com `--execs`, o `strace` é filho do medidor e entra no `ru_maxrss` (piso ≈ 19 MB).
Nada sai da máquina: saída é JSON local.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

try:  # opcional — sem ele só Linux via /proc
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None  # type: ignore

_MB = 1024 * 1024


@dataclass(slots=True)          # milhares de instâncias numa suíte grande (MEM-13)
class Proc:
    pid: int
    ppid: int
    nome: str
    cmdline: str
    primeiro_s: float
    ultimo_s: float
    rss_max_mb: float = 0.0
    uss_max_mb: float | None = None
    pss_max_mb: float | None = None
    amostras: int = 0

    @property
    def vida_s(self) -> float:
        return round(self.ultimo_s - self.primeiro_s, 3)


@dataclass
class Relatorio:
    rotulo: str
    argv: list[str]
    rc: int | None
    dur_s: float
    intervalo_ms: int
    amostras: int
    pico_rss_arvore_mb: float          # maior soma de RSS numa amostra
    pico_pss_arvore_mb: float | None   # idem PSS (Linux) — sem dupla contagem de páginas compartilhadas
    pico_processos_simultaneos: int
    spawns_vistos: int                 # pids distintos vistos na amostragem (piso)
    execs_strace: int | None           # execve contados (Linux + strace), None se não medido
    maxrss_maior_filho_mb: float | None = None   # POSIX ru_maxrss(RUSAGE_CHILDREN): maior processo, mesmo de vida curta
    execs_por_programa: dict[str, int] = field(default_factory=dict)
    processos: list[dict] = field(default_factory=list)
    so: str = sys.platform
    python: str = sys.version.split()[0]
    notas: list[str] = field(default_factory=list)
    serie: list[list[float]] = field(default_factory=list)   # [[t_s, rss_total_mb, n_proc], ...] — até ~240 pontos (reamostrada)
    rss_media_mb: float | None = None   # média/p50/p90 da soma de RSS por amostra, calculadas sobre TODAS as amostras
    rss_p50_mb: float | None = None     # (não sobre a `serie` reamostrada, que guarda máximos e enviesaria para cima)
    rss_p90_mb: float | None = None
    orfaos_apos_saida: list[dict] = field(default_factory=list)   # processos vistos na árvore ainda vivos após a raiz sair


# --------------------------------------------------------------------------- #
# amostragem
# --------------------------------------------------------------------------- #
def _ler_proc_linux(pid: int) -> tuple[int, str, str, float, float | None, float | None] | None:
    """(ppid, nome, cmdline, rss_mb, uss_mb, pss_mb) via /proc — sem psutil."""
    base = Path(f"/proc/{pid}")
    try:
        status = (base / "status").read_text(encoding="utf-8", errors="replace")
        ppid = int(re.search(r"^PPid:\s+(\d+)", status, re.M).group(1))  # type: ignore[union-attr]
        nome = re.search(r"^Name:\s+(.*)$", status, re.M).group(1).strip()  # type: ignore[union-attr]
        m = re.search(r"^VmRSS:\s+(\d+)\s+kB", status, re.M)
        rss = int(m.group(1)) / 1024 if m else 0.0
        cmd = (base / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace").strip()
        uss = pss = None
        try:
            roll = (base / "smaps_rollup").read_text(encoding="utf-8", errors="replace")
            mp = re.search(r"^Pss:\s+(\d+)\s+kB", roll, re.M)
            pss = int(mp.group(1)) / 1024 if mp else None
            priv = sum(int(x) for x in re.findall(r"^Private_(?:Clean|Dirty):\s+(\d+)\s+kB", roll, re.M))
            uss = priv / 1024
        except OSError:
            pass
        return ppid, nome, cmd or nome, rss, uss, pss
    except (OSError, AttributeError, ValueError):
        return None


def _descendentes_linux(raiz: int) -> list[int]:
    filhos: dict[int, list[int]] = {}
    try:
        for d in os.scandir("/proc"):
            if not d.name.isdigit():
                continue
            try:
                stat = Path(d.path, "stat").read_text(encoding="utf-8", errors="replace")
                ppid = int(stat[stat.rindex(")") + 2:].split()[1])
            except (OSError, ValueError):
                continue
            filhos.setdefault(ppid, []).append(int(d.name))
    except OSError:
        return []
    fila, vistos = [raiz], []
    while fila:
        p = fila.pop()
        vistos.append(p)
        fila.extend(filhos.get(p, []))
    return vistos


def _amostrar(raiz: int) -> list[tuple[int, int, str, str, float, float | None, float | None]]:
    """[(pid, ppid, nome, cmdline, rss_mb, uss_mb, pss_mb)] da árvore viva."""
    saida = []
    if psutil is not None:
        try:
            raiz_p = psutil.Process(raiz)
            procs = [raiz_p] + raiz_p.children(recursive=True)
        except psutil.Error:
            return []
        for p in procs:
            try:
                with p.oneshot():
                    mi = p.memory_info()
                    uss = pss = None
                    try:
                        mf = p.memory_full_info()
                        uss = getattr(mf, "uss", None)
                        pss = getattr(mf, "pss", None)
                        uss = uss / _MB if uss is not None else None
                        pss = pss / _MB if pss is not None else None
                    except (psutil.Error, OSError):
                        pass
                    cmd = " ".join(p.cmdline()) or p.name()
                    saida.append((p.pid, p.ppid(), p.name(), cmd, mi.rss / _MB, uss, pss))
            except psutil.Error:
                continue
        return saida
    if sys.platform.startswith("linux"):
        for pid in _descendentes_linux(raiz):
            r = _ler_proc_linux(pid)
            if r:
                ppid, nome, cmd, rss, uss, pss = r
                saida.append((pid, ppid, nome, cmd, rss, uss, pss))
    return saida


def _strace_disponivel() -> bool:
    return sys.platform.startswith("linux") and shutil.which("strace") is not None


def amostragem_disponivel() -> bool:
    """Linux amostra por /proc mesmo sem psutil; Windows/macOS só com psutil — sem ele `_amostrar` devolve
    vazio e o relatório sairia com zeros (pior que não medir)."""
    return psutil is not None or sys.platform.startswith("linux")


_RE_EXECVE = re.compile(r'execve\("([^"]+)"')


def _contar_execs(arquivo: Path) -> tuple[int, dict[str, int]]:
    total, por_prog = 0, {}
    try:
        for linha in arquivo.read_text(encoding="utf-8", errors="replace").splitlines():
            if "execve(" not in linha or "= -1" in linha:   # execve que falhou (ENOENT no PATH) não conta
                continue
            m = _RE_EXECVE.search(linha)
            if not m:
                continue
            total += 1
            prog = Path(m.group(1)).name
            por_prog[prog] = por_prog.get(prog, 0) + 1
    except OSError:
        pass
    return total, dict(sorted(por_prog.items(), key=lambda kv: -kv[1]))


# --------------------------------------------------------------------------- #
# execução
# --------------------------------------------------------------------------- #
def matar_arvore(pid: int) -> int:
    """Mata o processo e TODOS os descendentes (ordem: filhos primeiro). Devolve quantos sinais enviou.

    psutil (qualquer SO) → `/proc` (Linux sem psutil) → `taskkill /T /F` (Windows sem psutil). Nunca levanta:
    é chamado em caminho de erro (timeout) e não pode piorar a situação."""
    enviados = 0
    if psutil is not None:
        try:
            raiz = psutil.Process(pid)
            filhos = raiz.children(recursive=True)
        except psutil.Error:
            return 0
        for p in list(reversed(filhos)) + [raiz]:
            try:
                p.kill()
                enviados += 1
            except psutil.Error:
                pass
        return enviados
    if sys.platform.startswith("linux"):
        import signal
        for p in reversed(_descendentes_linux(pid)):
            try:
                os.kill(p, signal.SIGKILL)
                enviados += 1
            except OSError:
                pass
        return enviados
    if os.name == "nt":  # pragma: no cover - só Windows sem psutil
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=30)
            enviados = 1
        except (OSError, subprocess.SubprocessError):
            pass
        return enviados
    try:
        os.kill(pid, 9)
        enviados = 1
    except OSError:
        pass
    return enviados


def medir_arvore(argv: list[str], *, rotulo: str = "", intervalo_ms: int = 50, cwd: str | None = None,
                 env: dict | None = None, execs: bool = False, timeout_s: float | None = None,
                 silencioso: bool = True, entrada: str | None = None) -> Relatorio:
    notas: list[str] = []
    if psutil is None:
        notas.append("psutil ausente — amostragem via /proc (Linux); USS/PSS de smaps_rollup")
    strace_log: Path | None = None
    cmd = list(argv)
    if execs:
        if _strace_disponivel():
            fd, nome_log = tempfile.mkstemp(prefix="arvore-strace-", suffix=".txt")
            os.close(fd)                                   # o strace abre o arquivo por nome; o fd vazaria por medição
            strace_log = Path(nome_log)
            cmd = ["strace", "-f", "-qq", "-e", "trace=execve", "-s", "0", "-o", str(strace_log)] + cmd
            notas.append("execve contados com strace -f (processos de vida curta incluídos)")
        else:
            notas.append("--execs pedido mas strace indisponível/não-Linux — spawns_vistos é só o piso da amostragem")
    saida = subprocess.DEVNULL if silencioso else None
    ambiente = {**os.environ, **(env or {})}
    t0 = time.perf_counter()
    # stdin fechado por padrão: hooks e CLIs que leem stdin (ex.: hooks do Claude Code) travariam esperando EOF.
    # Com `entrada`, o texto é escrito de uma vez e o stdin fechado (payload JSON de hook, prompt de `claude -p`).
    # POSIX: sessão própria (como o ops/run.py) — no fim, todo processo com esse `sid` ainda vivo é órfão, mesmo que
    # tenha nascido e sido reparentado entre duas amostras (a amostragem por ppid não o veria).
    proc = subprocess.Popen(cmd, cwd=cwd, env=ambiente, stdout=saida, stderr=saida,
                            stdin=subprocess.PIPE if entrada is not None else subprocess.DEVNULL,
                            start_new_session=(os.name == "posix"))
    if entrada is not None and proc.stdin is not None:
        try:
            proc.stdin.write(entrada.encode("utf-8"))
            proc.stdin.close()
        except (OSError, ValueError):   # comando saiu antes de ler (fail-open: ainda medimos o que viveu)
            notas.append("stdin fechado pelo comando antes de consumir a entrada")
    vistos: dict[int, Proc] = {}
    pico_rss = 0.0
    pico_pss: float | None = None
    pico_n = 0
    n_amostras = 0
    intervalo = max(5, intervalo_ms) / 1000.0
    serie: list[list[float]] = []
    todas_rss: list[float] = []                            # 1 float por amostra: média/p50/p90 sem viés da reamostragem
    MAX_PONTOS = 240
    while True:
        agora = time.perf_counter() - t0
        amostra = _amostrar(proc.pid)
        if strace_log is not None:                         # o strace é o pai: não faz parte da árvore medida
            amostra = [a for a in amostra if a[0] != proc.pid]
        n_amostras += 1
        soma_rss = sum(a[4] for a in amostra)
        pss_vals = [a[6] for a in amostra if a[6] is not None]
        soma_pss = sum(pss_vals) if pss_vals and len(pss_vals) == len(amostra) else None
        pico_rss = max(pico_rss, soma_rss)
        if soma_pss is not None:
            pico_pss = soma_pss if pico_pss is None else max(pico_pss, soma_pss)
        pico_n = max(pico_n, len(amostra))
        serie.append([round(agora, 3), round(soma_rss, 1), len(amostra)])
        todas_rss.append(soma_rss)
        if len(serie) > 2 * MAX_PONTOS:                    # reamostra por pares guardando o máximo (não perde o pico)
            serie = _reamostrar(serie)
        for pid, ppid, nome, cmdl, rss, uss, pss in amostra:
            p = vistos.get(pid)
            if p is None:
                p = vistos[pid] = Proc(pid, ppid, nome, cmdl[:200], agora, agora)
            p.ultimo_s = agora
            p.amostras += 1
            p.rss_max_mb = max(p.rss_max_mb, rss)
            if uss is not None:
                p.uss_max_mb = max(p.uss_max_mb or 0.0, uss)
            if pss is not None:
                p.pss_max_mb = max(p.pss_max_mb or 0.0, pss)
        if proc.poll() is not None:
            break
        if timeout_s is not None and agora > timeout_s:
            n_mortos = matar_arvore(proc.pid)
            notas.append(f"timeout {timeout_s}s — árvore morta ({n_mortos} processo(s) sinalizados)")
            break
        time.sleep(intervalo)
    rc = proc.wait()
    dur = time.perf_counter() - t0
    # Varredura de órfãos: a raiz saiu — quem da árvore continua vivo? (o `ppid` já foi reparentado, por isso a
    # amostragem normal não os veria; aqui a lista é a dos pids que a árvore teve). PID reciclado em 0,3 s é improvável.
    time.sleep(0.3)
    orfaos: list[dict] = []
    candidatos: dict[int, Proc | None] = {pid: p for pid, p in vistos.items() if pid != proc.pid}
    for pid in _pids_da_sessao_linux(proc.pid):           # Linux: quem herdou a sessão, visto ou não pela amostragem
        candidatos.setdefault(pid, None)
    for pid, p in candidatos.items():
        if not _vivo(pid):
            continue
        if p is None:
            nome, cmdl = _identificar(pid)
            orfaos.append({"pid": pid, "nome": nome, "cmdline": cmdl, "rss_max_mb": None, "visto_na_amostragem": False})
        else:
            orfaos.append({"pid": pid, "nome": p.nome, "cmdline": p.cmdline, "rss_max_mb": round(p.rss_max_mb, 1),
                           "visto_na_amostragem": True})
    if orfaos:
        notas.append(f"ÓRFÃOS: {len(orfaos)} processo(s) da árvore continuam vivos após a raiz sair "
                     f"({', '.join(o['nome'] for o in orfaos[:5])}{'…' if len(orfaos) > 5 else ''})")
    maxrss_filhos: float | None = None
    if os.name == "posix":
        try:
            import resource
            ru = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
            maxrss_filhos = round(ru / (1024 if sys.platform.startswith("linux") else _MB), 1)
        except (ImportError, OSError):
            pass
    execs_total, por_prog = (None, {})
    if strace_log is not None:
        execs_total, por_prog = _contar_execs(strace_log)
        try:
            strace_log.unlink()
        except OSError:
            pass
    procs = sorted(vistos.values(), key=lambda p: (-p.rss_max_mb, p.primeiro_s))
    return Relatorio(
        rotulo=rotulo or " ".join(argv)[:80], argv=list(argv), rc=rc, dur_s=round(dur, 3),
        intervalo_ms=intervalo_ms, amostras=n_amostras,
        pico_rss_arvore_mb=round(pico_rss, 1),
        pico_pss_arvore_mb=round(pico_pss, 1) if pico_pss is not None else None,
        pico_processos_simultaneos=pico_n, spawns_vistos=len(vistos),
        execs_strace=execs_total, execs_por_programa=por_prog, maxrss_maior_filho_mb=maxrss_filhos,
        processos=[{**asdict(p), "vida_s": p.vida_s,
                    "rss_max_mb": round(p.rss_max_mb, 1),
                    "uss_max_mb": round(p.uss_max_mb, 1) if p.uss_max_mb is not None else None,
                    "pss_max_mb": round(p.pss_max_mb, 1) if p.pss_max_mb is not None else None}
                   for p in procs],
        notas=notas, serie=serie,
        rss_media_mb=round(statistics.fmean(todas_rss), 1) if todas_rss else None,
        rss_p50_mb=round(_quantil(todas_rss, 0.5), 1) if todas_rss else None,
        rss_p90_mb=round(_quantil(todas_rss, 0.9), 1) if todas_rss else None,
        orfaos_apos_saida=orfaos,
    )


def _reamostrar(serie: list[list[float]]) -> list[list[float]]:
    """Funde pares consecutivos guardando o máximo (pico preservado) e o carimbo do 2º; contagem ímpar mantém o
    último ponto. Só para o gráfico — média/p50/p90 vêm de `todas_rss`, nunca desta série."""
    pares = [[b[0], max(a[1], b[1]), max(a[2], b[2])] for a, b in zip(serie[0::2], serie[1::2])]
    if len(serie) % 2:
        pares.append(serie[-1])
    return pares


def _quantil(valores: list[float], q: float) -> float:
    ordenados = sorted(valores)
    k = min(len(ordenados) - 1, max(0, int(round(q * (len(ordenados) - 1)))))
    return ordenados[k]


def _pids_da_sessao_linux(sid: int) -> list[int]:
    """Pids vivos cuja sessão (campo 6 de /proc/<pid>/stat) é `sid` — descendentes da raiz, reparentados ou não."""
    if not sys.platform.startswith("linux"):
        return []
    achados = []
    for d in Path("/proc").iterdir():
        if not d.name.isdigit() or int(d.name) == sid:
            continue
        try:
            stat = (d / "stat").read_text(encoding="utf-8", errors="replace")
            campos = stat[stat.rindex(")") + 2:].split()
            if int(campos[3]) == sid:                      # campos: state ppid pgrp session ...
                achados.append(int(d.name))
        except (OSError, ValueError, IndexError):
            continue
    return achados


def _identificar(pid: int) -> tuple[str, str]:
    if psutil is not None:
        try:
            p = psutil.Process(pid)
            return p.name(), " ".join(p.cmdline())[:200]
        except psutil.Error:
            return "?", ""
    r = _ler_proc_linux(pid) if sys.platform.startswith("linux") else None
    return (r[1], r[2][:200]) if r else ("?", "")


def _vivo(pid: int) -> bool:
    """Processo existe e não é zumbi. psutil em qualquer SO; /proc no Linux; senão `os.kill(pid, 0)`."""
    if psutil is not None:
        try:
            return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
        except psutil.Error:
            return False
    if sys.platform.startswith("linux"):
        try:
            with open(f"/proc/{pid}/stat", encoding="utf-8", errors="replace") as fh:
                stat = fh.read()
            return stat[stat.rindex(")") + 2:].split()[0] != "Z"
        except OSError:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def resumo_texto(r: Relatorio, top: int = 8) -> str:
    pss = f" · PSS pico {r.pico_pss_arvore_mb} MB" if r.pico_pss_arvore_mb is not None else ""
    execs = f" · execve {r.execs_strace}" if r.execs_strace is not None else ""
    maior = f" · maior filho (ru_maxrss) {r.maxrss_maior_filho_mb} MB" if r.maxrss_maior_filho_mb is not None else ""
    regime = f" · RSS média/p90 {r.rss_media_mb}/{r.rss_p90_mb} MB" if r.rss_media_mb is not None and r.amostras >= 10 else ""
    linhas = [f"[{r.rotulo}] rc={r.rc} · {r.dur_s}s · RSS pico da árvore {r.pico_rss_arvore_mb} MB{pss}{maior}{regime}"
              f" · {r.pico_processos_simultaneos} proc simultâneos · {r.spawns_vistos} pids vistos{execs}"]
    for o in r.orfaos_apos_saida[:top]:
        linhas.append(f"   ÓRFÃO vivo após a raiz sair: pid {o['pid']} {o['nome']} {o['cmdline'][:60]}")
    for p in r.processos[:top]:
        linhas.append(f"   {p['rss_max_mb']:8.1f} MB  vida {p['vida_s']:6.2f}s  {p['nome']:<14} {p['cmdline'][:70]}")
    if r.execs_por_programa:
        top_e = ", ".join(f"{k}×{v}" for k, v in list(r.execs_por_programa.items())[:8])
        linhas.append(f"   execve por programa: {top_e}")
    for n in r.notas:
        linhas.append(f"   nota: {n}")
    return "\n".join(linhas)


def para_json(r: Relatorio) -> str:
    return json.dumps(asdict(r), ensure_ascii=False, indent=1)
