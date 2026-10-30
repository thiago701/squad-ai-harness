from taskbox.adaptadores.repositorio_memoria import RepositorioEmMemoria
from taskbox.aplicacao.servico import ServicoDeTarefas


def test_fluxo_completo_criar_listar_concluir():
    servico = ServicoDeTarefas(RepositorioEmMemoria())
    identificador = servico.criar("escrever adr")
    assert servico.pendentes() == ["[ ] escrever adr"]
    assert servico.concluir(identificador) == "[x] escrever adr"
    assert servico.pendentes() == []
