"""Entrypoint. `python -m app.main` sobe tudo: indexa a base e serve HTTP."""

from __future__ import annotations

import logging
import sys

from .config import Config
from .http_app import criar_servidor
from .servico import Servico


def configurar_log() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )


def main() -> int:
    configurar_log()
    log = logging.getLogger("chatbot")

    config = Config.do_ambiente()
    servico = Servico.montar(config)
    log.info(
        "base indexada: %s chunks | tenant=%s vertical=%s",
        servico.base.count(),
        config.tenant,
        config.vertical,
    )

    servidor = criar_servidor(servico)
    log.info("ouvindo em http://%s:%s (painel em /painel)", config.host, config.porta)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        log.info("encerrando")
    finally:
        servidor.server_close()
        servico.conexao.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
