# -*- coding: utf-8 -*-
"""Gateway SIMULADO a partir do modelo normalizado + condução da jornada do consumidor (C1 Python/Node).

O simulador decide o que o Gateway responderia SOZINHO (sem rota, sem token, preflight CORS) e,
quando a chamada passa, monta o evento que o Lambda recebe — HTTP API v2 ou REST API v1, conforme
o `payload` da rota. O handler roda num processo do próprio stack (runner Python ou Node), falando
JSON por linha (stdin/stdout); o julgamento é do avaliador único (`avaliacao.py`).

Alcance (vai para o relatório): comprova a implementação com o Gateway SIMULADO; não comprova o
Gateway implantado, o autorizador real nem dependências reais.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.parse
from pathlib import Path

from .modelo import Contrato, substituir


class GatewaySimulado:
    def __init__(self, gw: dict | None, origem_navegador: str = ""):
        self.gw = gw or {}
        self.origem = origem_navegador
        self.tipo_api = self.gw.get("tipo_api", "http")
        self.respostas = self.gw.get("respostas") or {
            "sem_rota": [404, "application/json", '{"message":"Not Found"}'],
            "nao_autorizado": [401, "application/json", '{"message":"Unauthorized"}']}

    # ---------------------------------------------------------------- roteamento
    def _rota(self, metodo: str, caminho: str):
        from .gateway import Rota  # import tardio: o simulador também roda a partir do JSON
        if not self.gw:
            return {"metodo": metodo, "caminho": caminho, "autorizador": None, "payload": "2.0"}, {}
        candidatas = []
        for r in self.gw.get("rotas") or []:
            rota = Rota(**{k: r.get(k) for k in ("metodo", "caminho", "funcao", "handler", "autorizador", "payload",
                                                 "timeout_funcao_s", "inferido") if k in r})
            if rota.casa(metodo, caminho):
                candidatas.append((rota, r))
        if not candidatas:
            return None, {}
        rota, bruto = sorted(candidatas, key=lambda x: (x[0].caminho == "$default", "+}" in x[0].caminho,
                                                         x[0].metodo == "ANY", x[0].caminho.count("{")))[0]
        return bruto, _parametros(rota.caminho, caminho)

    def _cors(self, caminho: str) -> dict | None:
        from .openapi import regex_template
        import re
        if self.tipo_api == "http":
            return self.gw.get("cors")
        for tpl, cfg in (self.gw.get("cors_por_caminho") or {}).items():
            if re.fullmatch(regex_template(tpl), caminho):
                return cfg
        return self.gw.get("cors")

    def _resposta_gateway(self, chave: str) -> dict:
        status, ct, corpo = self.respostas[chave][:3]
        return {"status": status, "headers": {"Content-Type": ct}, "corpo": corpo, "origem_resposta": "gateway-simulado"}

    def encaminhar(self, req: dict) -> tuple[str, dict]:
        """('gateway', observado) quando o Gateway responde sozinho; ('handler', evento) quando chama o Lambda."""
        metodo = str(req.get("metodo", "GET")).upper()
        caminho = str(req.get("caminho", "/"))
        headers = {str(k).lower(): str(v) for k, v in (req.get("headers") or {}).items()}
        if self.origem and "origin" not in headers:
            headers["origin"] = self.origem  # navegador sempre manda Origin
        cors = self._cors(caminho)
        if metodo == "OPTIONS" and "access-control-request-method" in headers and cors:
            origens = cors.get("AllowOrigins") or []
            h = {}
            if "*" in origens or headers.get("origin") in origens:
                h = {"Access-Control-Allow-Origin": "*" if "*" in origens else headers["origin"],
                     "Access-Control-Allow-Methods": ",".join(cors.get("AllowMethods") or []),
                     "Access-Control-Allow-Headers": ",".join(cors.get("AllowHeaders") or [])}
            return "gateway", {"status": 204, "headers": h, "corpo": "", "origem_resposta": "gateway-simulado"}
        rota, params = self._rota(metodo, caminho)
        if rota is None:
            return "gateway", self._resposta_gateway("sem_rota")
        token = req.get("token")
        if rota.get("autorizador") and (token is None or token == "invalido"):
            return "gateway", self._resposta_gateway("nao_autorizado")
        self._ultima = (rota, headers)
        return "handler", self._evento(metodo, caminho, rota, params, headers, req,
                                       token if rota.get("autorizador") else None)

    def _evento(self, metodo, caminho, rota, params, headers, req, token) -> dict:
        query = {k: str(v) for k, v in (req.get("query") or {}).items()}
        corpo = json.dumps(req["corpo"], ensure_ascii=False) if req.get("corpo") is not None else None
        estagio = self.gw.get("estagio") or "$default"
        req_id = f"cdc-{abs(hash((metodo, caminho, time.monotonic_ns()))) % 10**10}"
        if str(rota.get("payload", "2.0")) == "1.0":
            ctx = {"resourcePath": rota.get("caminho"), "httpMethod": metodo, "path": f"/{estagio}{caminho}",
                   "stage": estagio, "requestId": req_id, "identity": {"sourceIp": "127.0.0.1", "userAgent": "cdc"}}
            if token:
                ctx["authorizer"] = {"claims": {"sub": token}, "principalId": token}
            return {"resource": rota.get("caminho"), "path": caminho, "httpMethod": metodo, "headers": headers,
                    "multiValueHeaders": {k: [v] for k, v in headers.items()},
                    "queryStringParameters": query or None,
                    "multiValueQueryStringParameters": {k: [v] for k, v in query.items()} or None,
                    "pathParameters": params or None, "stageVariables": None, "requestContext": ctx,
                    "body": corpo, "isBase64Encoded": False}
        chave = f"{metodo} {rota.get('caminho')}" if rota.get("caminho") != "$default" else "$default"
        ctx = {"routeKey": chave, "stage": estagio, "requestId": req_id,
               "http": {"method": metodo, "path": caminho, "protocol": "HTTP/1.1", "sourceIp": "127.0.0.1",
                        "userAgent": "cdc"}}
        if token:
            ctx["authorizer"] = {"jwt": {"claims": {"sub": token}, "scopes": None}}
        evento = {"version": "2.0", "routeKey": chave, "rawPath": caminho,
                  "rawQueryString": urllib.parse.urlencode(query), "headers": headers, "requestContext": ctx,
                  "body": corpo, "isBase64Encoded": False}
        if query:
            evento["queryStringParameters"] = query
        if params:
            evento["pathParameters"] = params
        return evento

    def resposta_do_handler(self, resposta) -> dict:
        """Normaliza o retorno do Lambda e aplica o que o Gateway acrescenta (CORS no HTTP API)."""
        rota, headers_req = getattr(self, "_ultima", ({}, {}))
        if not isinstance(resposta, dict) or ("statusCode" not in resposta and str(rota.get("payload")) != "1.0"):
            obs = {"status": 200, "headers": {"Content-Type": "application/json"},
                   "corpo": json.dumps(resposta, ensure_ascii=False)}   # inferência do payload 2.0
        else:
            hdrs = {str(k): str(v) for k, v in (resposta.get("headers") or {}).items()}
            for k, vs in (resposta.get("multiValueHeaders") or {}).items():
                hdrs.setdefault(str(k), ",".join(str(v) for v in vs))
            corpo = resposta.get("body")
            obs = {"status": int(resposta.get("statusCode", 200)), "headers": hdrs,
                   "corpo": corpo if isinstance(corpo, str) else ("" if corpo is None else json.dumps(corpo))}
        cors = self._cors(str(rota.get("caminho", "")))
        origem = headers_req.get("origin")
        if self.tipo_api == "http" and cors and origem and ("*" in (cors.get("AllowOrigins") or [])
                                                             or origem in (cors.get("AllowOrigins") or [])):
            obs["headers"].setdefault("Access-Control-Allow-Origin", "*" if "*" in cors["AllowOrigins"] else origem)
        obs["origem_resposta"] = "handler"
        return obs


def _parametros(template: str, caminho: str) -> dict:
    import re
    nomes = re.findall(r"{([^}/]+)}", template)
    from .openapi import regex_template
    padrao = regex_template(template)
    padrao = re.sub(r"\[\^/\]\+|\.\+", lambda m: "(" + m.group(0) + ")", padrao)
    m = re.fullmatch(padrao, caminho)
    if not m or not nomes:
        return {}
    return {n.rstrip("+"): v for n, v in zip(nomes, m.groups())}


# --------------------------------------------------------------------------- runners
RUNNER_NODE = Path(__file__).resolve().parents[2] / "templates" / "node" / "runner.mjs"


def comando_runner(contrato: Contrato, cfg: dict) -> tuple[list[str], Path, dict]:
    raiz = contrato.raiz_repo / cfg.get("cwd", contrato.provedor.get("raiz", "."))
    env = dict(os.environ)
    if cfg.get("runner") == "python":
        alvo = cfg.get("fabrica") or cfg.get("handler")
        modo = "fabrica" if cfg.get("fabrica") else "handler"
        interprete = [str(x) for x in (cfg.get("interprete") or [os.environ.get("CDC_PYTHON", "python3")])]
        caminhos = [str((raiz / p).resolve()) for p in (cfg.get("pythonpath") or ["."])]
        env["PYTHONPATH"] = os.pathsep.join(caminhos + [str(Path(__file__).resolve().parents[1])]
                                            + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
        return [*interprete, "-m", "contrato_reverso.runner_python", f"--{modo}", alvo], raiz, env
    if cfg.get("runner") == "node":
        alvo = cfg.get("fabrica") or cfg.get("handler")
        modo = "fabrica" if cfg.get("fabrica") else "handler"
        return [str(x) for x in (cfg.get("interprete") or ["node"])] + [str(RUNNER_NODE), f"--{modo}", alvo], raiz, env
    raise ValueError(f"runner desconhecido: {cfg.get('runner')}")


def conduzir(contrato: Contrato, gw: dict | None, cfg: dict, timeout_s: float = 60) -> tuple[list[dict], dict]:
    """Roda a jornada inteira: substitui capturas, simula o Gateway, chama o runner. Devolve (observados, meta)."""
    from .avaliacao import avaliar
    cmd, cwd, env = comando_runner(contrato, cfg)
    sim = GatewaySimulado(gw, str(contrato.consumidor.get("origem_navegador", "")) if contrato.navegador else "")
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
    variaveis = contrato.variaveis_base()
    observados: list[dict] = []
    try:
        pronto = proc.stdout.readline()
        if not pronto.strip().startswith("{"):
            raise RuntimeError(f"runner não iniciou: {pronto.strip() or proc.stderr.read()[-800:]}")
        meta = json.loads(pronto)
        if meta.get("erro"):
            raise RuntimeError(f"runner não carregou o handler: {meta['erro']}")
        for it in contrato.interacoes:
            req = substituir(it.requisicao, variaveis)
            destino, carga = sim.encaminhar(req)
            if destino == "gateway":
                obs = carga
            else:
                proc.stdin.write(json.dumps({"evento": carga}, ensure_ascii=False) + "\n")
                proc.stdin.flush()
                linha = proc.stdout.readline()
                if not linha:
                    raise RuntimeError(f"runner encerrou em '{it.id}': {proc.stderr.read()[-800:]}")
                msg = json.loads(linha)
                if "erro" in msg:
                    obs = {"status": 502, "headers": {"Content-Type": "application/json"},
                           "corpo": json.dumps({"message": "Internal server error"}),
                           "origem_resposta": "gateway-simulado (handler lançou exceção)", "erro_handler": msg["erro"][-600:]}
                else:
                    obs = sim.resposta_do_handler(msg.get("resposta"))
            obs["id"] = it.id
            obs["requisicao"] = {k: v for k, v in req.items() if k != "token"}
            observados.append(obs)
            _, capturas = avaliar("C1", it, obs, variaveis, contrato.enums_fechados)
            variaveis.update(capturas)
        return observados, meta
    finally:
        try:
            proc.stdin.close()
            proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            proc.kill()
