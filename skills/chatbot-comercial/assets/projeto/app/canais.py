"""Canais — WhatsApp (Meta Cloud API) e widget web.

Canal não tem lógica de IA: só traduz protocolo. Ambos entram pelo mesmo
`MessageOrchestrator` do `conversation_core`, que dá idempotência (retry de
webhook), sessão e métricas de graça. Não reimplementamos nada disso.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from channels.whatsapp import WhatsAppAdapter
from conversation_core import MessageOrchestrator
from conversation_core.models import ChannelMessage, OutboundMessage

from .agente import Entrada


class PonteCore:
    """`CoreHandlerPort` do conversation_core → `Servico` do produto."""

    def __init__(self, servico: Any):
        self._servico = servico

    def handle_channel(self, mensagem: ChannelMessage) -> OutboundMessage:
        resposta = self._servico.responder(
            Entrada(
                texto=mensagem.text,
                sessao=mensagem.session_id,
                usuario=mensagem.user_id,
                canal=mensagem.channel,
                message_id=mensagem.message_id,
                tenant=mensagem.tenant or self._servico.config.tenant,
            )
        )
        return OutboundMessage(
            text=resposta.texto,
            user_id=mensagem.user_id,
            session_id=mensagem.session_id,
            channel=mensagem.channel,
            correlation_id=mensagem.message_id,
            escalated=resposta.escalonado,
            intent=resposta.intencao,
            sources=resposta.fontes,
            rejected=bool(resposta.recusado),
            reason=resposta.motivo,
            metadata={
                "modelo": resposta.modelo,
                "custo_brl": resposta.custo_brl,
                "sem_fonte": resposta.sem_fonte,
                "ferramenta": resposta.ferramenta,
            },
        )


def montar_orquestrador(servico: Any) -> MessageOrchestrator:
    return MessageOrchestrator(PonteCore(servico))


def montar_whatsapp(servico: Any, orquestrador: MessageOrchestrator) -> WhatsAppAdapter:
    cfg = servico.config
    return WhatsAppAdapter(
        orquestrador,
        app_secret=cfg.whatsapp_app_secret,
        tenant=cfg.tenant,
        verify_signatures=cfg.whatsapp_verificar_assinatura,
    )


def mensagem_do_widget(corpo: dict[str, Any], *, tenant: str) -> ChannelMessage:
    """Payload do widget web → ChannelMessage. Mesma porta do WhatsApp."""
    texto = str(corpo.get("mensagem") or corpo.get("texto") or "").strip()
    if not texto:
        raise ValueError("campo `mensagem` é obrigatório.")
    sessao = str(corpo.get("sessao") or "web:anonimo")
    # Sem `id`, cada turno ganha um correlation id próprio — senão a trilha
    # inteira da sessão sai com a mesma correlação. Quem quiser idempotência
    # de retry no widget manda o próprio `id`.
    return ChannelMessage(
        message_id=str(corpo.get("id") or f"web-{uuid.uuid4().hex}"),
        text=texto,
        user_id=str(corpo.get("usuario") or sessao),
        session_id=sessao,
        tenant=tenant,
        channel="web",
        metadata={"origem": corpo.get("origem", "widget")},
    )


def resposta_json(saida: OutboundMessage) -> bytes:
    return json.dumps(
        {
            "resposta": saida.text,
            "intencao": saida.intent,
            "fontes": list(saida.sources),
            "escalonado": saida.escalated,
            "motivo": saida.reason,
            "correlacao": saida.correlation_id,
            "duplicada": saida.duplicate,
            **{k: v for k, v in saida.metadata.items() if k != "custo_brl"},
        },
        ensure_ascii=False,
    ).encode("utf-8")
