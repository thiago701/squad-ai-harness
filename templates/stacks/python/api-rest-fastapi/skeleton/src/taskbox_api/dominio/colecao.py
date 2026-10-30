"""Colecao de primeira classe: comportamento mora aqui, nao em list solta."""
from __future__ import annotations

from taskbox_api.dominio.tarefa import Tarefa, TarefaInexistente


class Tarefas:
    """Agrupa tarefas e responde pelas operacoes do conjunto."""

    def __init__(self) -> None:
        self._itens: dict[str, Tarefa] = {}

    def adicionar(self, tarefa: Tarefa) -> None:
        self._itens[tarefa.identificador] = tarefa

    def concluir(self, identificador: str) -> Tarefa:
        existente = self._itens.get(identificador)
        if existente is None:
            raise TarefaInexistente(f"tarefa {identificador} nao encontrada")
        concluida = existente.concluir()
        self._itens[identificador] = concluida
        return concluida

    def pendentes(self) -> list[Tarefa]:
        return [t for t in self._itens.values() if not t.concluida]

    def total(self) -> int:
        return len(self._itens)
