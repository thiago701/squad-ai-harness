"""Caso de uso: orquestra dominio atraves de uma porta de repositorio."""
from __future__ import annotations

from typing import Protocol

from taskbox.dominio.tarefa import Tarefa


class PortaDeTarefas(Protocol):
    def guardar(self, tarefa: Tarefa) -> None: ...
    def concluir(self, identificador: str) -> Tarefa: ...
    def pendentes(self) -> list[Tarefa]: ...


class ServicoDeTarefas:
    """API de aplicacao: unica dependencia e a porta (invertida)."""

    def __init__(self, repositorio: PortaDeTarefas) -> None:
        self._repositorio = repositorio

    def criar(self, titulo: str) -> str:
        tarefa = Tarefa.nova(titulo)
        self._repositorio.guardar(tarefa)
        return tarefa.identificador

    def concluir(self, identificador: str) -> str:
        return self._repositorio.concluir(identificador).descrever()

    def pendentes(self) -> list[str]:
        return [t.descrever() for t in self._repositorio.pendentes()]
