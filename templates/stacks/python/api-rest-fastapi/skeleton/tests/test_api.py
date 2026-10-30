from fastapi.testclient import TestClient

from taskbox_api.adaptadores.api import criar_aplicacao


def cliente() -> TestClient:
    return TestClient(criar_aplicacao())


def test_health_e_openapi():
    api = cliente()
    assert api.get("/health").json() == {"situacao": "ok"}
    assert api.get("/openapi.json").status_code == 200


def test_fluxo_completo_pela_borda():
    api = cliente()
    criada = api.post("/tarefas", json={"titulo": "integrar fastapi"})
    assert criada.status_code == 201
    identificador = criada.json()["identificador"]
    assert api.get("/tarefas").json() == ["[ ] integrar fastapi"]
    conclusao = api.post(f"/tarefas/{identificador}/concluir")
    assert conclusao.status_code == 200
    assert api.get("/tarefas").json() == []


def test_handler_central_traduz_erros():
    api = cliente()
    dominio_invalido = api.post("/tarefas", json={"titulo": "ab"})
    assert dominio_invalido.status_code == 422
    pydantic_invalido = api.post("/tarefas", json={})
    assert pydantic_invalido.status_code == 422
    fantasma = api.post("/tarefas/nao-existe/concluir")
    assert fantasma.status_code == 404
