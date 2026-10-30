import pytest

from taskbox.dominio.colecao import Tarefas
from taskbox.dominio.tarefa import Tarefa, TarefaInexistente, TituloInvalido, TituloTarefa


def test_titulo_valida_na_construcao():
    assert TituloTarefa("  comprar cafe  ").valor == "comprar cafe"
    with pytest.raises(TituloInvalido):
        TituloTarefa("ab")
    with pytest.raises(TituloInvalido):
        TituloTarefa("x" * 121)


def test_tarefa_imutavel_concluir_devolve_nova():
    original = Tarefa.nova("estudar go")
    concluida = original.concluir()
    assert not original.concluida and concluida.concluida
    assert concluida.identificador == original.identificador
    assert concluida.descrever().startswith("[x]")


def test_colecao_de_primeira_classe():
    tarefas = Tarefas()
    tarefa = Tarefa.nova("revisar pr")
    tarefas.adicionar(tarefa)
    assert tarefas.total() == 1 and len(tarefas.pendentes()) == 1
    tarefas.concluir(tarefa.identificador)
    assert tarefas.pendentes() == []
    with pytest.raises(TarefaInexistente):
        tarefas.concluir("nao-existe")
