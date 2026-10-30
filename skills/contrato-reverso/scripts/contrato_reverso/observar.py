# -*- coding: utf-8 -*-
"""Modo contínuo local: observa arquivos e roda o nível escolhido pelo impacto.

- polling por mtime (stdlib, funciona em Windows/Linux sem watchdog);
- debounce: espera a edição "assentar" antes de rodar;
- cancelamento: mudança nova durante uma execução mata a execução superada e reinicia;
- uma execução por vez (paralelismo 1 para Maven; as camadas estáticas levam ms);
- trava exclusiva: um segundo observador na mesma pasta sai na hora;
- nunca escala para o Gateway implantado (C2): isso é do nível ampliado, explícito.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from . import impacto
from .modelo import carregar_contrato
from .nucleo import pasta_trabalho

CR = Path(__file__).resolve().parents[1] / "cr.py"


class Trava:
    def __init__(self, arquivo: Path):
        self.arquivo = arquivo
        self._fh = None

    def __enter__(self) -> "Trava":
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.arquivo, "a+")  # noqa: SIM115 - mantido aberto enquanto o observador vive
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._fh.close()
            raise SystemExit(f"já existe um observador ativo ({self.arquivo}) — evitando processo duplicado") from exc
        return self

    def __exit__(self, *exc) -> None:
        if self._fh:
            self._fh.close()


def _alvos(raiz: Path, contratos: list[Path]) -> list[Path]:
    alvos: set[Path] = set()
    for arq in contratos:
        c = carregar_contrato(arq, raiz)
        alvos.add(arq.parent)
        for p in (c.openapi, c.template_gateway):
            if p:
                alvos.add(p)
        prov = c.caminho_repo(c.provedor.get("raiz"))
        if prov:
            for sub in ("src", "pom.xml", "build.gradle"):
                if (prov / sub).exists():
                    alvos.add(prov / sub)
    return sorted(alvos)


def _foto(alvos: list[Path]) -> dict[str, float]:
    estado: dict[str, float] = {}
    for alvo in alvos:
        arquivos = [alvo] if alvo.is_file() else [p for p in alvo.rglob("*") if p.is_file() and "target" not in p.parts]
        for f in arquivos:
            try:
                estado[str(f)] = f.stat().st_mtime
            except OSError:
                pass
    return estado


def observar(raiz: Path, contratos: list[Path], intervalo: float = 0.5, debounce: float = 0.4,
             max_ciclos: int | None = None, saida=sys.stdout, saida_relatorios: Path | None = None) -> int:
    alvos = _alvos(raiz, contratos)
    anterior = _foto(alvos)
    pendentes: set[str] = set()
    ultima_mudanca = 0.0
    proc: subprocess.Popen | None = None
    ciclos = 0
    with Trava(pasta_trabalho(raiz) / "observar.lock"):
        print(f"👀 observando {len(anterior)} arquivos em {len(alvos)} alvos (Ctrl+C para sair)", file=saida, flush=True)
        try:
            while max_ciclos is None or ciclos < max_ciclos:
                time.sleep(intervalo)
                atual = _foto(alvos)
                mudou = {k for k in set(atual) | set(anterior) if atual.get(k) != anterior.get(k)}
                anterior = atual
                if mudou:
                    pendentes |= {str(Path(m).resolve().relative_to(raiz.resolve())).replace(os.sep, '/') for m in mudou}
                    ultima_mudanca = time.monotonic()
                    if proc and proc.poll() is None:
                        _cancelar(proc)
                        print("⏹  execução superada cancelada", file=saida, flush=True)
                        proc = None
                if pendentes and time.monotonic() - ultima_mudanca >= debounce and (proc is None or proc.poll() is not None):
                    proc = _disparar(raiz, contratos, sorted(pendentes), saida, saida_relatorios)
                    pendentes = set()
                    ciclos += 1
                if proc and proc.poll() is not None:
                    proc = None
        except KeyboardInterrupt:
            pass
        finally:
            if proc and proc.poll() is None:
                proc.wait()
    return 0


def _disparar(raiz: Path, contratos: list[Path], alterados: list[str], saida,
              saida_relatorios: Path | None = None) -> subprocess.Popen | None:
    nivel, suite = "nenhum", False
    for arq in contratos:
        imp = impacto.avaliar(carregar_contrato(arq, raiz), alterados)
        if impacto.NIVEIS.index(imp.nivel) > impacto.NIVEIS.index(nivel):
            nivel = imp.nivel
        suite = suite or imp.suite_completa
    if nivel == "nenhum":
        return None
    nivel = "direcionado" if nivel == "ampliado" else nivel  # C2 nunca é disparado pelo observador
    cmd = [sys.executable, str(CR), "verificar", "--raiz", str(raiz), "--nivel", nivel, "--resumo"]
    if saida_relatorios:
        cmd += ["--saida", str(saida_relatorios)]
    if suite:
        cmd.append("--suite-completa")
    print(f"▶  {len(alterados)} alteração(ões) → nível {nivel}{' + suíte completa' if suite else ''}",
          file=saida, flush=True)
    if os.name == "nt":
        return subprocess.Popen(cmd, cwd=raiz, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    return subprocess.Popen(cmd, cwd=raiz, start_new_session=True)


def _cancelar(proc: subprocess.Popen) -> None:
    """Mata a ÁRVORE inteira (verificar → Maven/JVM): cancelar só o pai deixaria processo órfão."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    else:
        import signal
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
