"""FIXTURE SINTÉTICA — tudo aqui está ERRADO de propósito (selftest da lente LOG-xx).

Nenhum valor é credencial real. Versão correta: ../bom/pagamento_worker.py
"""
import logging
import os

logger = logging.getLogger(__name__)


def conectar(usuario: str, password: str, api_key: str) -> None:
    logger.info(f"conectando usuario={usuario} password={password}")   # LOG-01 + LOG-12
    logger.debug("api_key=%s", api_key)                                  # LOG-01
    logger.info("ambiente: %s", dict(os.environ))                       # LOG-03


def processar(cliente: dict, pedido_id: str) -> None:
    logger.info("processando pedido %s", pedido_id, extra={"cpf": cliente["cpf"], "email": cliente["email"]})  # LOG-02
    print(f"cliente {cliente['nome']} telefone={cliente['telefone']}")  # LOG-02
    try:
        cobrar(cliente, pedido_id)
    except Exception as e:
        logger.error("falha ao cobrar: %s", str(e))                      # LOG-11


def receber(request) -> None:
    logger.info("payload recebido: %s", request.data)                    # LOG-13
    logger.info("headers: {}".format(request.headers))                   # LOG-12 + LOG-13


def cobrar(cliente, pedido_id):  # pragma: no cover
    raise RuntimeError("gateway indisponível")
