"""Template de logging estruturado da Squad para serviços/scripts Python (stdlib pura).

- JSON por linha (timestamp RFC3339 UTC, level, service, env, version, message, correlation_id, trace_id, extras)
- correlation_id/trace_id por contextvars (threads e asyncio preservam)
- FiltroSegredos: segredo é NEGADO (e vira evento `log.segredo.bloqueado` no logger "seguranca")
- MascaraFilter: PII é MASCARADA com os formatos canônicos (logs_obs.mascara, a mesma biblioteca do linter)
- exceções: use logger.exception(...) — stack vai em `error.stack`, tipo em `error.kind`

Uso:
    from logging_json import configurar, correlation_id
    configurar(service="pedidos", env="prod", version="1.4.2", nivel="INFO")
    correlation_id.set(request.headers.get("X-Correlation-Id") or uuid4().hex)
    logger.info("pedido.criado", extra={"pedido_id": pid, "cliente_id": cid})
"""
from __future__ import annotations

import contextvars
import datetime as _dt
import json
import logging
import re
import sys
import traceback

try:
    from logs_obs.mascara import mascarar_texto, DETECTORES   # skills/logs-observabilidade/scripts no PYTHONPATH
except ImportError:                                           # fallback mínimo (sem validação de DV/Luhn)
    def mascarar_texto(t: str) -> str:
        return re.sub(r"(?i)\b(senha|password|secret|token|api[_-]?key)\s*[=:]\s*\S+", r"\1=****", t)
    DETECTORES = ()

correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="-")
trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")

_CAMPOS_PADRAO = set(logging.LogRecord("x", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}
_SEGREDO = re.compile(
    r"(?i)(?:authorization\s*[:=]\s*(?:bearer|basic)\s+\S{8,}|\beyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{8,}\b|"
    r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b|-----BEGIN [A-Z ]*PRIVATE KEY-----|[a-z][a-z0-9+.-]*://[^/\s:@]+:[^@\s/]{3,}@|"
    r"\b(?:senha|password|passwd|secret|client_secret|api[_-]?key|access[_-]?key|private[_-]?key|"
    r"access[_-]?token|refresh[_-]?token|authorization|cvv)\b\s*[:=]\s*[\"']?(?![*\[<$]|null\b|none\b)[^\s\"',;&)}\]]{3,})")


class FiltroSegredos(logging.Filter):
    """Barreira: segredo não sai — e o bloqueio é auditável (sem o conteúdo)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name == "seguranca":
            return True
        alvos = [str(record.msg)] + [str(a) for a in (record.args or ())] + \
                [str(v) for k, v in record.__dict__.items() if k not in _CAMPOS_PADRAO and isinstance(v, str)]
        for onde, texto in zip(["formato", "argumento", "extra"], ["|".join(alvos[:1]), "|".join(alvos[1:1 + len(record.args or ())]), "|".join(alvos[1 + len(record.args or ()):])]):
            if texto and _SEGREDO.search(texto):
                logging.getLogger("seguranca").warning("log.segredo.bloqueado logger=%s onde=%s", record.name, onde)
                return False
        return True


class MascaraFilter(logging.Filter):
    """Rede de segurança: PII validada é mascarada em msg, args e extras."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mascarar_texto(str(record.msg))
        if record.args:
            record.args = tuple(mascarar_texto(str(a)) if isinstance(a, str) else a for a in record.args)
        for k, v in list(record.__dict__.items()):
            if k not in _CAMPOS_PADRAO and isinstance(v, str):
                record.__dict__[k] = mascarar_texto(v)
        return True


class ContextoFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id.get()
        record.trace_id = trace_id.get()
        return True


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str, env: str, version: str):
        super().__init__()
        self.base = {"service": service, "env": env, "version": version}

    def format(self, record: logging.LogRecord) -> str:
        evento = {
            "timestamp": _dt.datetime.fromtimestamp(record.created, _dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            **self.base,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", "-"),
            "trace_id": getattr(record, "trace_id", "-"),
        }
        for k, v in record.__dict__.items():
            if k not in _CAMPOS_PADRAO and k not in evento and not k.startswith("_"):
                evento[k] = v
        if record.exc_info:
            exc_type, exc, tb = record.exc_info
            evento["error"] = {"kind": getattr(exc_type, "__name__", str(exc_type)),
                               "message": mascarar_texto(str(exc)),
                               "stack": mascarar_texto("".join(traceback.format_exception(exc_type, exc, tb))[-4000:])}
        return json.dumps(evento, ensure_ascii=False, default=str)


def configurar(*, service: str, env: str = "local", version: str = "dev", nivel: str = "INFO",
               stream=None) -> logging.Logger:
    raiz = logging.getLogger()
    raiz.handlers.clear()
    h = logging.StreamHandler(stream or sys.stdout)
    h.setFormatter(JsonFormatter(service, env, version))
    for f in (ContextoFilter(), FiltroSegredos(), MascaraFilter()):   # ordem: contexto → negar segredo → mascarar PII
        h.addFilter(f)
    raiz.addHandler(h)
    raiz.setLevel(nivel.upper())
    # loggers barulhentos/perigosos
    for nome in ("urllib3", "botocore", "boto3", "httpx", "httpcore"):
        logging.getLogger(nome).setLevel("WARNING")
    return raiz


if __name__ == "__main__":  # demonstração: python logging_json.py
    configurar(service="demo", env="local", version="0")
    log = logging.getLogger("demo")
    correlation_id.set("c0ffee-0001")
    from logs_obs.mascara import mascarar_cpf                                                # camada 1: origem
    log.info("pedido.criado", extra={"pedido_id": "p-1", "cpf_mascarado": mascarar_cpf("529.982.247-25")})
    log.info("cliente.consultado documento=%s", "529.982.247-25")   # camada 2: MascaraFilter pega o que escapou
    log.info("auth.token.recebido token_presente=%s", True)
    log.info("vazamento token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.YWJjZGVmZ2hpamtsbW5vcA")  # NEGADO + evento seguranca
    try:
        raise RuntimeError("gateway indisponivel senha=hunter2")
    except RuntimeError:
        log.exception("pagamento.falhou pedido_id=%s", "p-1")                              # stack com segredo mascarado
