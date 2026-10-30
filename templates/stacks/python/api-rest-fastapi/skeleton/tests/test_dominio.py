import pytest

from taskbox_api.dominio.colecao import Tarefas
from taskbox_api.dominio.tarefa import Tarefa, TarefaInexistente, TituloInvalido, TituloTarefa


def test_dominio_puro_sem_framework():
    assert TituloTarefa(" ler docs ").valor == "ler docs"
    with pytest.raises(TituloInvalido):
        TituloTarefa("ab")
    tarefas = Tarefas()
    tarefa = Tarefa.nova("estudar pydantic")
    tarefas.adicionar(tarefa)
    assert tarefas.concluir(tarefa.identificador).concluida
    with pytest.raises(TarefaInexistente):
        tarefas.concluir("fantasma")
