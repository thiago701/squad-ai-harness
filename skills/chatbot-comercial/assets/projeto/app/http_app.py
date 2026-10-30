"""Camada HTTP — `http.server` da stdlib. Zero framework, zero dependência.

Por quê: até ~10k conversas/mês o gargalo é o LLM, não o servidor web. Um
framework aqui seria complexidade acidental (P1). Trocar por FastAPI é
reescrever só este arquivo — nenhum módulo de negócio importa HTTP.
"""

from __future__ import annotations

import json
import logging
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from channels.whatsapp.webhook import WebhookParseError

from .canais import mensagem_do_widget, montar_orquestrador, montar_whatsapp, resposta_json
from .curadoria import AprovacaoAusente

logger = logging.getLogger("chatbot.http")
_ROTA_ID = re.compile(r"^/api/(curadoria|versoes|sessao)/([^/]+)(?:/(\w+))?$")
LIMITE_CORPO = 512 * 1024


class Rotas:
    """Mapeia HTTP → serviço. Sem regra de negócio aqui."""

    def __init__(self, servico: Any):
        self.servico = servico
        self.orquestrador = montar_orquestrador(servico)
        self.whatsapp = montar_whatsapp(servico, self.orquestrador)
        self.painel_html = (Path(__file__).parent / "painel.html").read_text(
            encoding="utf-8"
        )

    def autorizado(self, cabecalhos: Any) -> bool:
        esperado = self.servico.config.painel_token
        if not esperado:
            return True
        return cabecalhos.get("X-Painel-Token", "") == esperado


class Manipulador(BaseHTTPRequestHandler):
    rotas: Rotas

    server_version = "chatbot-comercial"

    def log_message(self, formato: str, *args: Any) -> None:  # noqa: A003
        logger.info("%s %s", self.command, self.path.split("?")[0])

    # -- utilidades ---------------------------------------------------------

    def _responder(self, status: int, corpo: bytes, tipo: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", f"{tipo}; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Painel-Token")
        self.end_headers()
        self.wfile.write(corpo)

    def _json(self, status: int, dados: Any) -> None:
        self._responder(status, json.dumps(dados, ensure_ascii=False, default=str).encode())

    def _erro(self, status: int, mensagem: str) -> None:
        self._json(status, {"erro": mensagem})

    def _corpo(self) -> bytes:
        tamanho = int(self.headers.get("Content-Length") or 0)
        if tamanho > LIMITE_CORPO:
            raise ValueError("corpo muito grande")
        return self.rfile.read(tamanho) if tamanho else b""

    def _corpo_json(self) -> dict[str, Any]:
        bruto = self._corpo()
        return json.loads(bruto.decode("utf-8")) if bruto else {}

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._responder(204, b"")

    # -- GET ----------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        caminho = urlparse(self.path).path
        consulta = parse_qs(urlparse(self.path).query)
        servico = self.rotas.servico
        try:
            if caminho in {"/saude", "/health"}:
                self._json(200, {"ok": True, "tenant": servico.config.tenant,
                                 "vertical": servico.config.vertical,
                                 "chunks": servico.base.count()})
            elif caminho == "/webhook/whatsapp":
                self._verificar_webhook(consulta)
            elif caminho == "/painel":
                self._responder(200, self.rotas.painel_html.encode(), "text/html")
            elif caminho == "/api/painel":
                if not self.rotas.autorizado(self.headers):
                    return self._erro(401, "token do painel ausente ou inválido")
                dias = int((consulta.get("dias") or ["30"])[0])
                self._json(200, servico.painel(dias=dias))
            elif caminho == "/api/leads.csv":
                if not self.rotas.autorizado(self.headers):
                    return self._erro(401, "token do painel ausente ou inválido")
                self._responder(200, servico.leads.exportar_csv().encode(), "text/csv")
            elif caminho == "/api/lgpd/expurgo":
                self._erro(405, "use POST")
            elif caminho.startswith("/api/"):
                # Tudo sob /api/ exige token. `/api/sessao/<id>` devolve a
                # conversa inteira — deixá-la aberta era vazamento silencioso.
                if not self.rotas.autorizado(self.headers):
                    return self._erro(401, "token do painel ausente ou inválido")
                if caminho == "/api/versoes":
                    return self._json(200, servico.curadoria.versoes())
                achado = _ROTA_ID.match(caminho)
                if achado and achado.group(1) == "sessao":
                    return self._json(
                        200, servico.trilha.contexto_para_humano(achado.group(2))
                    )
                self._erro(404, "rota não encontrada")
            else:
                self._erro(404, "rota não encontrada")
        except Exception as exc:  # noqa: BLE001 — borda HTTP não derruba servidor
            logger.exception("falha no GET %s", caminho)
            self._erro(500, type(exc).__name__)

    def _verificar_webhook(self, consulta: dict[str, list[str]]) -> None:
        cfg = self.rotas.servico.config
        modo = (consulta.get("hub.mode") or [""])[0]
        token = (consulta.get("hub.verify_token") or [""])[0]
        desafio = (consulta.get("hub.challenge") or [""])[0]
        if modo == "subscribe" and token and token == cfg.whatsapp_verify_token:
            self._responder(200, desafio.encode(), "text/plain")
        else:
            self._erro(403, "verify_token inválido")

    # -- POST ---------------------------------------------------------------

    def do_POST(self) -> None:  # noqa: N802
        caminho = urlparse(self.path).path
        servico = self.rotas.servico
        try:
            if caminho == "/chat":
                self._chat()
            elif caminho == "/webhook/whatsapp":
                self._whatsapp()
            elif caminho == "/api/lgpd/expurgo":
                if not self.rotas.autorizado(self.headers):
                    return self._erro(401, "token do painel ausente ou inválido")
                self._json(200, servico.lgpd.expurgar())
            elif caminho == "/api/curadoria":
                corpo = self._corpo_json()
                item = servico.curadoria.marcar_ruim(
                    interacao_id=corpo.get("interacao_id"),
                    pergunta=corpo.get("pergunta", ""),
                    resposta_ruim=corpo.get("resposta_ruim", ""),
                    motivo=corpo.get("motivo", ""),
                )
                self._json(201, {"id": item})
            else:
                self._rota_com_id(caminho)
        except AprovacaoAusente as exc:
            self._erro(409, str(exc))
        except (ValueError, WebhookParseError) as exc:
            self._erro(400, str(exc))
        except PermissionError:
            self._erro(401, "assinatura inválida")
        except Exception as exc:  # noqa: BLE001
            logger.exception("falha no POST %s", caminho)
            self._erro(500, type(exc).__name__)

    def _rota_com_id(self, caminho: str) -> None:
        achado = _ROTA_ID.match(caminho)
        if not achado:
            return self._erro(404, "rota não encontrada")
        if not self.rotas.autorizado(self.headers):
            return self._erro(401, "token do painel ausente ou inválido")

        recurso, identificador, acao = achado.groups()
        servico = self.rotas.servico
        corpo = self._corpo_json()

        if recurso == "curadoria":
            item = int(identificador)
            if acao == "propor":
                servico.curadoria.propor(
                    item,
                    fonte_alvo=corpo.get("fonte_alvo", ""),
                    texto_proposto=corpo.get("texto_proposto", ""),
                )
                return self._json(200, {"id": item, "status": "proposto"})
            if acao == "aprovar":
                servico.curadoria.aprovar(item, aprovado_por=corpo.get("aprovado_por", ""))
                return self._json(200, {"id": item, "status": "aprovado"})
            if acao == "rejeitar":
                servico.curadoria.rejeitar(item, aprovado_por=corpo.get("aprovado_por", ""))
                return self._json(200, {"id": item, "status": "rejeitado"})
            if acao == "aplicar":
                relatorio = servico.curadoria.aplicar(
                    item, servico.base, reindexar=servico.reindexar
                )
                return self._json(200, relatorio)
        if recurso == "versoes" and acao == "rollback":
            relatorio = servico.curadoria.rollback(
                int(identificador), servico.base, reindexar=servico.reindexar
            )
            return self._json(200, relatorio)
        return self._erro(404, "ação desconhecida")

    def _chat(self) -> None:
        corpo = self._corpo_json()
        mensagem = mensagem_do_widget(corpo, tenant=self.rotas.servico.config.tenant)
        saida = self.rotas.orquestrador.handle(mensagem)
        self._responder(200, resposta_json(saida))

    def _whatsapp(self) -> None:
        bruto = self._corpo()
        envios = self.rotas.whatsapp.handle_webhook(
            bruto, signature_header=self.headers.get("X-Hub-Signature-256", "")
        )
        self._json(
            200,
            {
                "enviar": [
                    {"para": e.to, "texto": e.text, "correlacao": e.correlation_id}
                    for e in envios
                ]
            },
        )


def criar_servidor(servico: Any) -> ThreadingHTTPServer:
    Manipulador.rotas = Rotas(servico)
    cfg = servico.config
    return ThreadingHTTPServer((cfg.host, cfg.porta), Manipulador)
