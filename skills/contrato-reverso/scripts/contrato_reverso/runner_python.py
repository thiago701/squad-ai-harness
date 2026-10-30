# -*- coding: utf-8 -*-
"""Runner do verificador C1 para handlers Lambda em Python (stdlib).

Roda no ambiente do PROVEDOR (cwd e PYTHONPATH do projeto), carrega o handler e responde, uma
linha JSON por vez: entrada `{"evento": {...}}` → saída `{"resposta": {...}}` ou `{"erro": "..."}`.

  --fabrica pacote.modulo:criar_handler   função SEM argumentos que devolve o handler já montado com
                                          dublês nas portas de saída (recomendado: isola banco/filas)
  --handler pacote.modulo:lambda_handler  o handler do Lambda direto (só se ele não tocar nuvem)
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import traceback
import uuid


class _Contexto:
    function_name = "cdc-verificador"
    memory_limit_in_mb = 512
    invoked_function_arn = "arn:aws:lambda:local:000000000000:function:cdc-verificador"

    def __init__(self):
        self.aws_request_id = str(uuid.uuid4())

    @staticmethod
    def get_remaining_time_in_millis() -> int:
        return 30_000


def _carregar(alvo: str):
    modulo, _, nome = alvo.partition(":")
    obj = getattr(importlib.import_module(modulo), nome or "handler")
    return obj


def main() -> int:
    ap = argparse.ArgumentParser()
    grupo = ap.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--fabrica")
    grupo.add_argument("--handler")
    args = ap.parse_args()
    saida = sys.stdout
    sys.stdout = sys.stderr  # print() do handler não pode sujar o protocolo
    try:
        handler = _carregar(args.fabrica)() if args.fabrica else _carregar(args.handler)
    except Exception:  # noqa: BLE001
        saida.write(json.dumps({"erro": traceback.format_exc()}) + "\n")
        saida.flush()
        return 1
    saida.write(json.dumps({"runner": "python", "versao": sys.version.split()[0],
                            "modo": "fabrica" if args.fabrica else "handler"}) + "\n")
    saida.flush()
    for linha in sys.stdin:
        if not linha.strip():
            continue
        try:
            evento = json.loads(linha)["evento"]
            resposta = handler(evento, _Contexto())
            saida.write(json.dumps({"resposta": resposta}, ensure_ascii=False, default=str) + "\n")
        except Exception:  # noqa: BLE001 - exceção do handler vira 502 do Gateway, como na AWS
            saida.write(json.dumps({"erro": traceback.format_exc()}) + "\n")
        saida.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
