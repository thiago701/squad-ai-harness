"""Versão CORRETA do ../ruim/pagamento_worker.py — passa limpa na lente LOG-xx.

Doutrina aplicada: evento nomeado, `%s` preguiçoso, PII mascarada na origem (templates/python_logging_json.py
tem o filtro de rede de segurança), `logger.exception` com stack trace, campos escolhidos do request,
correlation_id vindo do contextvar populado na borda.
"""
import logging

from logs_obs.mascara import mascarar_cpf, mascarar_email, mascarar_token

logger = logging.getLogger(__name__)


def conectar(usuario: str, token: str) -> None:
    logger.info("auth.token.recebido usuario_id=%s token_presente=%s token_sufixo=%s",
                usuario, bool(token), mascarar_token(token))
    logger.debug("config.carregada vars_presentes=%s", ["DB_URL", "DD_SITE"])  # nomes, nunca valores


def processar(cliente: dict, pedido_id: str) -> None:
    logger.info("pedido.processando pedido_id=%s cliente_id=%s", pedido_id, cliente["id"],
                extra={"cpf_mascarado": mascarar_cpf(cliente["cpf"]),
                       "email_mascarado": mascarar_email(cliente["email"])})
    try:
        cobrar(cliente, pedido_id)
        logger.info("pagamento.autorizado pedido_id=%s", pedido_id)
    except Exception:
        logger.exception("pagamento.falhou pedido_id=%s", pedido_id)
        raise


def receber(request) -> None:
    logger.info("http.request.recebido metodo=%s rota=%s tamanho_bytes=%s correlation_id=%s",
                request.method, request.path, len(request.data), request.headers.get("X-Correlation-Id"))


def cobrar(cliente, pedido_id):  # pragma: no cover
    raise RuntimeError("gateway indisponível")
