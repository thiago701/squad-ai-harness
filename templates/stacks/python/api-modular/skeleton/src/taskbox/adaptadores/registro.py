"""Logging estruturado (JSON) — observabilidade minima."""
from __future__ import annotations

import json
import logging
import sys


class FormatoJson(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        corpo = {"nivel": record.levelname, "quando": self.formatTime(record),
                 "mensagem": record.getMessage(), "origem": record.name}
        return json.dumps(corpo, ensure_ascii=False)


def registrador(nome: str) -> logging.Logger:
    logger = logging.getLogger(nome)
    if not logger.handlers:
        saida = logging.StreamHandler(sys.stdout)
        saida.setFormatter(FormatoJson())
        logger.addHandler(saida)
        logger.setLevel(logging.INFO)
    return logger
