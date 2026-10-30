"""Adaptador: repositorio em memoria sobre a colecao de primeira classe."""
from __future__ import annotations

from taskbox.dominio.colecao import Tarefas
from taskbox.dominio.tarefa import Tarefa


class RepositorioEmMemoria:
    """Implementa a PortaDeTarefas para testes e uso local."""

    def __init__(self) -> None:
        self._tarefas = Tarefas()

    def guardar(self, tarefa: Tarefa) -> None:
        self._tarefas.adicionar(tarefa)

    def concluir(self, identificador: str) -> Tarefa:
        return self._tarefas.concluir(identificador)

    def pendentes(self) -> list[Tarefa]:
        return self._tarefas.pendentes()
