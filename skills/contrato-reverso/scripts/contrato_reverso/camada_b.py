# -*- coding: utf-8 -*-
"""Camada B — consumidor/OpenAPI ↔ configuração do API Gateway. Estática.

O backend nunca vê o que o Gateway responde sozinho: rota inexistente (404 no HTTP API, 403
"Missing Authentication Token" no REST API), token inválido (401 do autorizador), preflight
CORS, throttling (429) e timeout de integração (503/504). Esta camada lê a configuração do
Gateway — SAM (HTTP/REST), CloudFormation/CDK ou Terraform, já normalizada em `gateway.py` —
e a confronta com o contrato publicado e com o consumidor.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import INFO, PENDENTE, QUEBRA, RISCO, Achado
from .gateway import ModeloGateway, Rota, carregar  # noqa: F401 - Rota reexportada
from .modelo import METODOS_SEGUROS, Contrato, substituir
from .openapi import OpenApi

CAMADA = "B"


def carregar_gateway(template: Path, recurso_api: str | None, tipo: str | None = None) -> ModeloGateway:
    return carregar(template, recurso_api, tipo)


def _caminho_concreto(contrato: Contrato, caminho: str) -> str:
    variaveis = contrato.variaveis_base()
    for it in contrato.interacoes:
        for nome in it.capturar:
            variaveis.setdefault(nome, "valor-amostra")
    return substituir(caminho, variaveis)


def verificar(contrato: Contrato, oas: OpenApi | None, gw: ModeloGateway) -> list[Achado]:
    a: list[Achado] = []
    evid = f"{contrato.gateway.get('template')} ({gw.fonte}, {gw.tipo_api.upper()} API)"
    sem_rota = gw.respostas["sem_rota"]
    for p in gw.pendencias:
        a.append(Achado(CAMADA, PENDENTE, "B-LEITURA-PARCIAL", None,
                        f"o leitor não resolveu estaticamente: {p} — use `terraform show -json` ou confirme em C2", evid))
    funcao = contrato.gateway.get("funcao")
    if funcao and gw.rotas and not any(r.funcao == funcao or r.funcao.endswith("." + funcao) for r in gw.rotas):
        a.append(Achado(CAMADA, RISCO, "B-FUNCAO-SEM-ROTA", None, f"nenhuma rota do {gw.api} aponta para {funcao}", evid))

    # --- OpenAPI ↔ Gateway -----------------------------------------------------------
    if oas is not None:
        tem_default = any(r.caminho == "$default" or "+}" in r.caminho for r in gw.rotas)
        for op in oas.operacoes():
            if op.metodo == "OPTIONS":
                continue
            rota = gw.rota_para(op.metodo, re.sub(r"{[^}]+}", "valor-amostra", op.caminho))
            if rota is None:
                a.append(Achado(CAMADA, QUEBRA, "B-ROTA-OPENAPI-SEM-GATEWAY", None,
                                f"{op.metodo} {op.caminho} está no OpenAPI, mas o Gateway não tem a rota "
                                f"({sem_rota[0]} do Gateway)", evid))
                continue
            if ("{" not in op.caminho and rota.caminho != op.caminho and rota.caminho != "$default"
                    and "+}" not in rota.caminho):
                a.append(Achado(CAMADA, RISCO, "B-ROTA-SOMBREADA", None,
                                f"{op.metodo} {op.caminho} não tem rota própria no Gateway e cai em {rota.metodo} "
                                f"{rota.caminho}: só funciona se o backend rotear pelo path (C1/C2 dizem se funciona)", evid))
            if oas.seguranca_exigida(op) and not rota.autorizador:
                a.append(Achado(CAMADA, QUEBRA, "B-AUTH-AUSENTE", None,
                                f"{op.metodo} {op.caminho}: o contrato exige autenticação e a rota do Gateway não tem "
                                "autorizador (claims nunca chegam ao backend; rota pública)", evid))
            integ = op.dados.get("x-amazon-apigateway-integration") or {}
            pfv = integ.get("payloadFormatVersion")
            if pfv and str(pfv) != rota.payload:
                a.append(Achado(CAMADA, QUEBRA, "B-PAYLOAD-FORMAT", None,
                                f"{op.metodo} {op.caminho}: OpenAPI integra com payload {pfv}, Gateway com "
                                f"{rota.payload} — o backend recebe outro formato de evento", evid))
        if not tem_default:
            documentadas = {f"{op.metodo} {re.sub(r'{[^}]+}', '{}', op.caminho)}" for op in oas.operacoes()}
            for sig in sorted({r.assinatura for r in gw.rotas} - documentadas):
                if not sig.startswith("ANY"):
                    a.append(Achado(CAMADA, RISCO, "B-ROTA-NAO-DOCUMENTADA", None,
                                    f"rota {sig} existe no Gateway e não no OpenAPI", evid))
        a.extend(_respostas_do_gateway(contrato, oas, gw, evid))

    # --- Consumidor ↔ Gateway --------------------------------------------------------
    for it in contrato.interacoes:
        if it.metodo == "OPTIONS":
            continue
        caminho = _caminho_concreto(contrato, it.caminho)
        rota = gw.rota_para(it.metodo, caminho)
        if rota is None:
            a.append(Achado(CAMADA, QUEBRA, "B-ROTA-CONSUMIDOR", it.id,
                            f"{it.metodo} {it.caminho} não tem rota no Gateway: o consumidor recebe "
                            f"{sem_rota[0]} {sem_rota[2]} do Gateway", evid))
            continue
        if it.token is None and 401 in it.status_esperados and not rota.autorizador:
            a.append(Achado(CAMADA, RISCO, "B-401-SO-NO-BACKEND", it.id,
                            "o 401 sem token só existe se o backend se defender; o Gateway não autentica esta rota", evid))
        if it.token is None and 401 in it.status_esperados and rota.autorizador:
            aceitos = it.content_types
            ct_gw = gw.respostas["nao_autorizado"][1]
            if aceitos and ct_gw not in aceitos:
                a.append(Achado(CAMADA, QUEBRA, "B-401-FORMATO-CONSUMIDOR", it.id,
                                f"o autorizador do Gateway responde 401 em {ct_gw}; o consumidor só aceita {aceitos}", evid))

    a.extend(_cors(contrato, gw, evid))
    a.extend(_tempos(contrato, gw, evid))
    if gw.tipo_api == "http" and gw.estagio not in ("$default", ""):
        a.append(Achado(CAMADA, PENDENTE, "B-ESTAGIO-NOMEADO", None,
                        f"estágio nomeado '{gw.estagio}': confirme pelo endpoint implantado (camada C2) que o backend "
                        "roteia corretamente o path recebido — o Gateway simulado não prova isso", evid))
    return a


def _respostas_do_gateway(contrato: Contrato, oas: OpenApi, gw: ModeloGateway, evid: str) -> list[Achado]:
    a: list[Achado] = []
    tem_autorizador = any(gw.tipos_autorizador.get(r.autorizador or "") in ("jwt", "lambda", "cognito") for r in gw.rotas)
    if tem_autorizador:
        ct_gw, corpo_gw = gw.respostas["nao_autorizado"][1:]
        promete: dict[str, int] = {}
        for op in oas.operacoes():
            r401 = oas.resposta_para(op, 401)
            tipos_401 = [c.lower() for c in ((r401 or {}).get("content") or {})]
            if tipos_401 and ct_gw not in tipos_401:
                for t in tipos_401:
                    promete[t] = promete.get(t, 0) + 1
        if promete:
            a.append(Achado(CAMADA, RISCO, "B-401-FORMATO-CONTRATO", None,
                            f"o contrato promete 401 em {sorted(promete)} ({max(promete.values())} operações), mas o "
                            f"401 do autorizador do Gateway é {ct_gw} {corpo_gw} (gerado antes do backend)", evid))
    if gw.throttling:
        declara_429 = any({"429", "4XX", "4xx"} & set(oas.respostas(op)) for op in oas.operacoes())
        if not declara_429:
            trata = 429 in (contrato.consumidor.get("trata_genericamente") or [])
            a.append(Achado(CAMADA, RISCO, "B-429-NAO-DECLARADO", None,
                            f"throttling ativo no Gateway ({gw.throttling}) e nenhum 429 no contrato"
                            + ("; o consumidor trata 429 genericamente" if trata else "; o consumidor não trata 429"), evid))
    return a


def _cors(contrato: Contrato, gw: ModeloGateway, evid: str) -> list[Achado]:
    if not contrato.navegador:
        return []
    origem = str(contrato.consumidor.get("origem_navegador", ""))
    alvo = next((it.id for it in contrato.interacoes if it.metodo == "OPTIONS"), None)
    if not gw.tem_cors():
        return [Achado(CAMADA, QUEBRA, "B-CORS-AUSENTE", alvo,
                       f"consumidor de navegador e o {gw.tipo_api.upper()} API não tem CORS configurado: o preflight "
                       f"falha e o navegador bloqueia as chamadas de {origem or 'outra origem'}", evid)]
    a: list[Achado] = []
    caminhos = sorted({_caminho_concreto(contrato, it.caminho) for it in contrato.interacoes if it.metodo != "OPTIONS"})
    sem, origens_ruins, metodos_faltando, headers_faltando, cred = [], set(), set(), set(), False
    usados_headers = {h.lower() for it in contrato.interacoes for h in (it.requisicao.get("headers") or {})
                      if h.lower() != "origin" and not h.lower().startswith("access-control-")}
    if any(it.token for it in contrato.interacoes):
        usados_headers.add("authorization")
    for caminho in caminhos:
        cfg = gw.cors_para(caminho)
        if not cfg:
            sem.append(caminho)
            continue
        origens = [o.lower() for o in cfg.get("AllowOrigins") or []]
        metodos = [m.upper() for m in cfg.get("AllowMethods") or []]
        headers = [h.lower() for h in cfg.get("AllowHeaders") or []]
        if "*" not in origens and origem.lower() not in origens:
            origens_ruins.add(tuple(origens))
        cred |= bool(cfg.get("AllowCredentials")) and "*" in origens
        usados = {it.metodo for it in contrato.interacoes if it.metodo != "OPTIONS"
                  and _caminho_concreto(contrato, it.caminho) == caminho}
        metodos_faltando |= {m for m in usados if "*" not in metodos and m not in metodos}
        headers_faltando |= {h for h in usados_headers if "*" not in headers and h not in headers}
    if sem:
        a.append(Achado(CAMADA, QUEBRA, "B-CORS-AUSENTE", alvo, f"sem preflight CORS para {sem}", evid))
    if origens_ruins:
        a.append(Achado(CAMADA, QUEBRA, "B-CORS-ORIGEM", alvo,
                        f"origem {origem} fora de AllowOrigins {sorted(set(o for t in origens_ruins for o in t))}", evid))
    if cred:
        a.append(Achado(CAMADA, QUEBRA, "B-CORS-CREDENCIAIS", alvo,
                        "AllowCredentials com AllowOrigins '*' é rejeitado pelos navegadores", evid))
    if metodos_faltando:
        a.append(Achado(CAMADA, QUEBRA, "B-CORS-METODO", alvo, f"AllowMethods não cobre {sorted(metodos_faltando)}", evid))
    if headers_faltando:
        a.append(Achado(CAMADA, QUEBRA, "B-CORS-HEADER", alvo, f"AllowHeaders não cobre {sorted(headers_faltando)}", evid))
    if gw.tipo_api == "rest":
        a.append(Achado(CAMADA, PENDENTE, "B-CORS-RESPOSTA-PROXY", alvo,
                        "REST API com integração proxy: o Gateway só responde o preflight; a resposta real precisa trazer "
                        "Access-Control-Allow-Origin vindo da Lambda — C1/C2 verificam", evid))
    return a


def _tempos(contrato: Contrato, gw: ModeloGateway, evid: str) -> list[Achado]:
    a: list[Achado] = []
    limite = gw.respostas["timeout_integracao_s"]
    timeouts = [r.timeout_funcao_s for r in gw.rotas if r.timeout_funcao_s]
    maior = max(timeouts, default=0)
    if maior > limite:
        a.append(Achado(CAMADA, RISCO, "B-TIMEOUT-INTEGRACAO", None,
                        f"função com timeout {maior:g}s acima do limite de integração do {gw.tipo_api.upper()} API "
                        f"({limite}s): o consumidor recebe 503/504 do Gateway", evid))
    timeout_cliente = contrato.consumidor.get("timeout_ms")
    if timeout_cliente and maior and float(timeout_cliente) / 1000 < min(maior, limite):
        escrita = any(it.metodo not in METODOS_SEGUROS for it in contrato.interacoes)
        a.append(Achado(CAMADA, RISCO, "B-TIMEOUT-CLIENTE", None,
                        f"cliente desiste em {timeout_cliente} ms e o backend pode levar até {maior:g}s"
                        + ("; retry de escrita sem idempotência pode duplicar" if escrita else ""), evid))
    return a


def resumo_info(gw: ModeloGateway) -> Achado:
    return Achado(CAMADA, INFO, "B-MODELO", None,
                  f"{gw.fonte} · {gw.tipo_api.upper()} API · {len(gw.rotas)} rotas, estágio {gw.estagio}, "
                  f"autorizador padrão {gw.autorizador_padrao}, CORS {'sim' if gw.tem_cors() else 'não'}, "
                  f"throttling {gw.throttling or 'não'}")
