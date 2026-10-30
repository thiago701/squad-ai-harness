"""Borda FastAPI fina: Pydantic v2 valida, handler central traduz dominio->HTTP."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from taskbox_api.adaptadores.repositorio_memoria import RepositorioEmMemoria
from taskbox_api.aplicacao.servico import ServicoDeTarefas
from taskbox_api.dominio.tarefa import ErroDeDominio, TarefaInexistente


class NovaTarefaCorpo(BaseModel):
    """Contrato de entrada (validacao declarativa na borda)."""

    titulo: str = Field(min_length=1, max_length=200)


class TarefaCriada(BaseModel):
    identificador: str


def criar_aplicacao() -> FastAPI:
    aplicacao = FastAPI(title="{{project_name}}", version="0.1.0")
    servico = ServicoDeTarefas(RepositorioEmMemoria())
    _registrar_rotas(aplicacao, servico)
    _registrar_erros(aplicacao)
    return aplicacao


def _registrar_rotas(aplicacao: FastAPI, servico: ServicoDeTarefas) -> None:
    @aplicacao.get("/health")
    def saude() -> dict[str, str]:
        return {"situacao": "ok"}

    @aplicacao.get("/tarefas")
    def pendentes() -> list[str]:
        return servico.pendentes()

    @aplicacao.post("/tarefas", status_code=201)
    def criar(corpo: NovaTarefaCorpo) -> TarefaCriada:
        return TarefaCriada(identificador=servico.criar(corpo.titulo))

    @aplicacao.post("/tarefas/{identificador}/concluir")
    def concluir(identificador: str) -> dict[str, str]:
        return {"tarefa": servico.concluir(identificador)}


def _registrar_erros(aplicacao: FastAPI) -> None:
    @aplicacao.exception_handler(ErroDeDominio)
    def traduzir(_pedido: Request, erro: ErroDeDominio) -> JSONResponse:
        status = 404 if isinstance(erro, TarefaInexistente) else 422
        return JSONResponse(status_code=status, content={"erro": str(erro)})


aplicacao = criar_aplicacao()
