"""Canais e HTTP — widget web, webhook WhatsApp e rotas do painel."""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
import urllib.error
import urllib.request
from dataclasses import replace

import pytest

from app.canais import mensagem_do_widget, montar_orquestrador, montar_whatsapp
from app.http_app import criar_servidor


def payload_whatsapp(texto: str, message_id: str = "wamid.1") -> bytes:
    return json.dumps(
        {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "123"},
                                "contacts": [{"wa_id": "5511999998888", "profile": {"name": "Ana"}}],
                                "messages": [
                                    {
                                        "id": message_id,
                                        "from": "5511999998888",
                                        "type": "text",
                                        "timestamp": "1770000000",
                                        "text": {"body": texto},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
    ).encode()


def assinar(corpo: bytes, segredo: str) -> str:
    return "sha256=" + hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()


def test_widget_normaliza_mensagem():
    mensagem = mensagem_do_widget({"mensagem": "oi", "sessao": "web:1"}, tenant="t")
    assert mensagem.channel == "web" and mensagem.session_id == "web:1"
    with pytest.raises(ValueError):
        mensagem_do_widget({}, tenant="t")


def test_widget_gera_correlacao_por_turno():
    primeira = mensagem_do_widget({"mensagem": "a", "sessao": "s"}, tenant="t")
    segunda = mensagem_do_widget({"mensagem": "b", "sessao": "s"}, tenant="t")
    assert primeira.message_id != segunda.message_id
    fixa = mensagem_do_widget({"mensagem": "a", "sessao": "s", "id": "m1"}, tenant="t")
    assert fixa.message_id == "m1"


def test_orquestrador_responde_e_deduplica(servico):
    orquestrador = montar_orquestrador(servico)
    mensagem = mensagem_do_widget(
        {"mensagem": "que horas serve o cafe da manha", "sessao": "w1", "id": "m1"}, tenant="teste"
    )
    primeira = orquestrador.handle(mensagem)
    assert primeira.sources
    segunda = orquestrador.handle(mensagem)
    assert segunda.duplicate, "retry do canal não pode reprocessar (idempotência)"


def test_whatsapp_exige_assinatura(servico):
    servico.config = replace(servico.config, whatsapp_app_secret="segredo")
    adapter = montar_whatsapp(servico, montar_orquestrador(servico))
    corpo = payload_whatsapp("a piscina e aquecida")
    with pytest.raises(PermissionError):
        adapter.handle_webhook(corpo, signature_header="sha256=errado")
    envios = adapter.handle_webhook(corpo, signature_header=assinar(corpo, "segredo"))
    assert envios and envios[0].to == "5511999998888"
    assert "piscina" in envios[0].text.lower()


@pytest.fixture
def servidor(servico):
    servico.config = replace(servico.config, porta=0, host="127.0.0.1")
    httpd = criar_servidor(servico)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def pegar(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as resposta:  # noqa: S310
        return json.loads(resposta.read())


def postar(url: str, corpo: dict) -> dict:
    requisicao = urllib.request.Request(  # noqa: S310
        url, data=json.dumps(corpo).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(requisicao, timeout=10) as resposta:  # noqa: S310
        return json.loads(resposta.read())


def test_saude(servidor):
    saude = pegar(f"{servidor}/saude")
    assert saude["ok"] and saude["chunks"] > 0


def test_chat_responde_de_verdade_com_fonte(servidor):
    resposta = postar(f"{servidor}/chat", {"mensagem": "posso levar meu cachorro", "sessao": "http1"})
    assert resposta["fontes"] == ["estrutura"]
    assert "10 quilos" in resposta["resposta"] or "pequeno porte" in resposta["resposta"]


def test_chat_sem_mensagem_da_400(servidor):
    with pytest.raises(urllib.error.HTTPError) as erro:
        postar(f"{servidor}/chat", {"sessao": "x"})
    assert erro.value.code == 400


def test_painel_e_api(servidor):
    postar(f"{servidor}/chat", {"mensagem": "tem estacionamento coberto", "sessao": "http2"})
    painel = pegar(f"{servidor}/api/painel")
    assert painel["metricas"]["conversas"] >= 1
    with urllib.request.urlopen(f"{servidor}/painel", timeout=10) as html:  # noqa: S310
        assert b"Painel do atendimento" in html.read()


def test_timeline_da_sessao(servidor):
    postar(f"{servidor}/chat", {"mensagem": "qual o endereco da pousada", "sessao": "http3"})
    contexto = pegar(f"{servidor}/api/sessao/http3")
    assert contexto["turnos"] == 1
    assert "localizacao" in contexto["fontes_usadas"]


def test_toda_api_exige_token(servico):
    """A timeline de uma sessão é a conversa inteira — não pode ficar aberta."""
    servico.config = replace(servico.config, porta=0, host="127.0.0.1",
                             painel_token="segredo")
    httpd = criar_servidor(servico)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        for rota in ("/api/painel", "/api/leads.csv", "/api/versoes", "/api/sessao/x"):
            with pytest.raises(urllib.error.HTTPError) as erro:
                pegar(base + rota)
            assert erro.value.code == 401, f"{rota} respondeu sem token"
        assert pegar(f"{base}/saude")["ok"], "/saude continua público (health check)"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_rota_inexistente(servidor):
    with pytest.raises(urllib.error.HTTPError) as erro:
        pegar(f"{servidor}/nao-existe")
    assert erro.value.code == 404


def test_webhook_verify_token(servidor, servico):
    with pytest.raises(urllib.error.HTTPError) as erro:
        pegar(f"{servidor}/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=errado")
    assert erro.value.code == 403


def test_curadoria_via_http_exige_aprovacao(servidor):
    criado = postar(
        f"{servidor}/api/curadoria", {"pergunta": "tem heliponto", "motivo": "sem_fonte"}
    )
    item = criado["id"]
    postar(
        f"{servidor}/api/curadoria/{item}/propor",
        {"fonte_alvo": "estrutura", "texto_proposto": "Não há heliponto na pousada."},
    )
    with pytest.raises(urllib.error.HTTPError) as erro:
        postar(f"{servidor}/api/curadoria/{item}/aplicar", {})
    assert erro.value.code == 409, "aplicar sem aprovação humana tem que falhar"

    postar(f"{servidor}/api/curadoria/{item}/aprovar", {"aprovado_por": "thiago"})
    aplicado = postar(f"{servidor}/api/curadoria/{item}/aplicar", {})
    assert aplicado["versao_id"] > 0
