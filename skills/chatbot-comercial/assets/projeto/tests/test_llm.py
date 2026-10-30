"""Fronteira com o LLM — modo extrativo, resiliência e contrato do llm-gateway."""

from __future__ import annotations

import importlib.util

import pytest
from conversation_core.resilience import LlmUnavailableError

from app.llm import (
    MODELO_EXTRATIVO,
    GatewayIndisponivel,
    LlmGateway,
    LlmResiliente,
    RespostaExtrativa,
    construir_llm,
)

TEM_GATEWAY = importlib.util.find_spec("llm_gateway") is not None


class Trecho:
    def __init__(self, texto: str, fonte: str):
        self.text = texto
        self.source = fonte
        self.chunk_id = f"{fonte}#0"


class GatewayFalso:
    """Duplo do pacote llm-gateway com a MESMA forma do contrato documentado."""

    class _R:
        text = "A diária do Chalé Standard é R$ 380,00 (fonte: tarifas)."
        model = "gpt-mini"
        input_tokens = 700
        output_tokens = 40
        cost_brl = 0.012

    def __init__(self, falhar: bool = False):
        self.falhar = falhar
        self.chamadas = 0

    def complete(self, *, prompt, system, tenant, task):
        del prompt, system, tenant, task
        self.chamadas += 1
        if self.falhar:
            raise RuntimeError("provider fora do ar")
        return self._R()


def test_extrativo_cita_a_fonte():
    r = RespostaExtrativa().responder(
        sistema="", pergunta="quanto custa", trechos=[Trecho("Diária R$ 380.", "tarifas")],
        tenant="t", tarefa="tarifa",
    )
    assert "fonte: tarifas" in r.texto
    assert r.modelo == MODELO_EXTRATIVO
    assert r.custo_brl == 0.0


def test_extrativo_recorta_a_frase_que_responde():
    """Chunk grande não pode enterrar a resposta no meio do parágrafo."""
    chunk = (
        "# Estrutura e serviços "
        "A pousada aceita animais de pequeno porte mediante taxa. "
        "O estacionamento é gratuito e coberto. "
        "Não há quadra de tênis na pousada."
    )
    r = RespostaExtrativa().responder(
        sistema="", pergunta="tem quadra de tenis", trechos=[Trecho(chunk, "estrutura")],
        tenant="t", tarefa="estrutura",
    )
    assert "quadra de tênis" in r.texto
    assert "animais de pequeno porte" not in r.texto
    assert not r.texto.startswith("#")


def test_extrativo_sem_termo_util_devolve_o_inicio():
    r = RespostaExtrativa().responder(
        sistema="", pergunta="e ai", trechos=[Trecho("Primeira frase. Segunda frase.", "f")],
        tenant="t", tarefa="",
    )
    assert "Primeira frase" in r.texto


def test_extrativo_sem_trecho_admite_desconhecimento():
    r = RespostaExtrativa().responder(
        sistema="", pergunta="x", trechos=[], tenant="t", tarefa=""
    )
    assert "não encontrei" in r.texto.lower()


def test_gateway_traduz_campos_do_contrato():
    gateway = LlmGateway(GatewayFalso())
    r = gateway.responder(
        sistema="persona", pergunta="quanto custa", trechos=[Trecho("Diária R$ 380.", "tarifas")],
        tenant="t1", tarefa="tarifa",
    )
    assert r.modelo == "gpt-mini"
    assert r.tokens_entrada == 700
    assert r.custo_brl == 0.012


def test_gateway_erro_vira_llm_unavailable():
    with pytest.raises(LlmUnavailableError):
        LlmGateway(GatewayFalso(falhar=True)).responder(
            sistema="", pergunta="x", trechos=[], tenant="t", tarefa=""
        )


def test_resiliente_cai_para_extrativo():
    falso = GatewayFalso(falhar=True)
    resiliente = LlmResiliente(LlmGateway(falso), timeout_s=1.0, tentativas=2)
    r = resiliente.responder(
        sistema="", pergunta="quanto custa", trechos=[Trecho("Diária R$ 380.", "tarifas")],
        tenant="t", tarefa="",
    )
    assert r.modelo == MODELO_EXTRATIVO
    assert falso.chamadas == 2, "deve ter usado o retry do conversation_core"


def test_resiliente_usa_primario_quando_saudavel():
    resiliente = LlmResiliente(LlmGateway(GatewayFalso()))
    r = resiliente.responder(
        sistema="", pergunta="x", trechos=[Trecho("t", "f")], tenant="t", tarefa=""
    )
    assert r.modelo == "gpt-mini"
    assert resiliente.breaker is not None


def test_construir_llm_default_e_extrativo(config, monkeypatch):
    monkeypatch.delenv("LLM_GATEWAY_ATIVO", raising=False)
    assert isinstance(construir_llm(config), RespostaExtrativa)


@pytest.mark.skipif(TEM_GATEWAY, reason="pacote llm-gateway instalado")
def test_gateway_ausente_falha_com_mensagem_clara(config, monkeypatch):
    monkeypatch.setenv("LLM_GATEWAY_ATIVO", "1")
    with pytest.raises(GatewayIndisponivel, match="llm-gateway"):
        construir_llm(config)


@pytest.mark.gateway
@pytest.mark.skipif(not TEM_GATEWAY, reason="pacote llm-gateway não instalado")
def test_contrato_do_llm_gateway_real():
    """Teste de contrato: falha alto se o pacote real divergir do esperado."""
    from llm_gateway import Gateway  # type: ignore[import-not-found]

    assert hasattr(Gateway, "from_env"), "Gateway.from_env() faz parte do contrato"
    gateway = Gateway.from_env()
    assert callable(getattr(gateway, "complete", None))
    resposta = gateway.complete(prompt="ping", system="responda 'pong'", tenant="teste", task="rapido")
    for campo in ("text", "model", "input_tokens", "output_tokens", "cost_brl"):
        assert hasattr(resposta, campo), f"resposta do gateway sem `{campo}`"
