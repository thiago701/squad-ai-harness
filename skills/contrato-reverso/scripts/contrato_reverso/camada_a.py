# -*- coding: utf-8 -*-
"""Camada A — expectativa do consumidor ↔ contrato publicado (OpenAPI). Estática.

Pergunta: "o contrato PROMETE tudo de que este consumidor depende?". Um campo que o
consumidor lê como obrigatório mas o OpenAPI marca como opcional é quebra mesmo que a
implementação de hoje sempre o envie — a promessa é o que sobrevive a refatorações.
"""
from __future__ import annotations

from . import INFO, QUEBRA, RISCO, Achado
from .modelo import Contrato, Interacao, substituir
from .openapi import OpenApi, enum_valores, tipos

CAMADA = "A"
_AMOSTRA = "valor-amostra"


def _caminho_amostra(interacao: Interacao, contrato: Contrato) -> str:
    variaveis = contrato.variaveis_base()
    for nome in _nomes_captura(contrato):
        variaveis.setdefault(nome, _AMOSTRA)
    return substituir(interacao.caminho, variaveis)


def _nomes_captura(contrato: Contrato) -> set[str]:
    return {n for i in contrato.interacoes for n in i.capturar}


def verificar(contrato: Contrato, oas: OpenApi) -> list[Achado]:
    achados: list[Achado] = []
    for interacao in contrato.interacoes:
        if interacao.metodo == "OPTIONS":
            continue  # preflight é responsabilidade do Gateway (camada B)
        achados.extend(_verificar_interacao(contrato, oas, interacao))
    return achados


def _verificar_interacao(contrato: Contrato, oas: OpenApi, it: Interacao) -> list[Achado]:
    saida: list[Achado] = []
    caminho = _caminho_amostra(it, contrato)
    op = oas.achar(it.metodo, caminho)
    if op is None:
        return [Achado(CAMADA, QUEBRA, "A-ROTA-AUSENTE", it.id,
                       f"{it.metodo} {it.caminho} não existe no OpenAPI publicado", "paths")]
    ref = f"{op.metodo} {op.caminho}"
    exige_auth = oas.seguranca_exigida(op)
    sucesso = any(s < 400 for s in it.status_esperados)

    if it.token is None and sucesso and exige_auth:
        saida.append(Achado(CAMADA, QUEBRA, "A-AUTH-EXIGIDA", it.id,
                            f"consumidor chama {ref} sem token esperando sucesso, mas o contrato exige autenticação",
                            f"{ref} security"))
    if it.token is None and 401 in it.status_esperados and not exige_auth:
        saida.append(Achado(CAMADA, QUEBRA, "A-AUTH-NAO-PROMETIDA", it.id,
                            f"consumidor depende de 401 sem token, mas {ref} não declara segurança",
                            f"{ref} security"))

    saida.extend(_verificar_requisicao(oas, op, it, ref, sucesso))

    respostas_ok = [(s, oas.resposta_para(op, s)) for s in it.status_esperados]
    declaradas = [(s, r) for s, r in respostas_ok if r is not None]
    if not declaradas:
        status = "/".join(str(s) for s in it.status_esperados)
        if it.status_esperados == [401] and exige_auth:
            saida.append(Achado(CAMADA, RISCO, "A-STATUS-IMPLICITO", it.id,
                                f"401 não declarado em {ref} (implícito pela segurança)", f"{ref} responses"))
        else:
            saida.append(Achado(CAMADA, QUEBRA, "A-STATUS-NAO-PROMETIDO", it.id,
                                f"o consumidor trata {status} em {ref}, mas o contrato não declara esse status",
                                f"{ref} responses"))
        return saida
    status, resposta = declaradas[0]
    conteudo = (resposta or {}).get("content") or {}
    tipos_declarados = [c.lower() for c in conteudo]
    if it.resposta.get("corpo_vazio") and tipos_declarados:
        saida.append(Achado(CAMADA, RISCO, "A-CORPO-DECLARADO", it.id,
                            f"consumidor espera corpo vazio em {status}, contrato declara {tipos_declarados}",
                            f"{ref} {status}"))
    if it.content_types:
        comuns = [c for c in it.content_types if c in tipos_declarados]
        if not comuns:
            sev = RISCO if status == 401 and exige_auth and not tipos_declarados else QUEBRA
            saida.append(Achado(CAMADA, sev, "A-CONTENT-TYPE", it.id,
                                f"consumidor aceita {it.content_types} em {status}; contrato declara "
                                f"{tipos_declarados or 'nenhum corpo'}", f"{ref} {status} content"))
            return saida
        esquema = oas.esquema(conteudo[next(k for k in conteudo if k.lower() == comuns[0])].get("schema"))
    else:
        primeiro = next(iter(conteudo.values()), {})
        esquema = oas.esquema(primeiro.get("schema"))
    campos = it.resposta.get("campos") or {}
    if campos:
        saida.extend(_checar_campos(contrato, oas, it, campos, esquema, prefixo="",
                                    evidencia=f"{ref} {status}"))
    return saida


def _verificar_requisicao(oas: OpenApi, op, it: Interacao, ref: str, sucesso: bool) -> list[Achado]:
    saida: list[Achado] = []
    corpo = it.requisicao.get("corpo")
    exigido, esquema = oas.corpo_requisicao(op)
    if exigido and corpo is None and sucesso:
        saida.append(Achado(CAMADA, QUEBRA, "A-CORPO-EXIGIDO", it.id,
                            f"{ref} exige corpo e o consumidor não envia", f"{ref} requestBody"))
    if isinstance(corpo, dict) and esquema:
        props = esquema.get("properties") or {}
        if sucesso:
            for nome in esquema.get("required") or []:
                if nome not in corpo:
                    saida.append(Achado(CAMADA, QUEBRA, "A-REQ-CAMPO-OBRIGATORIO", it.id,
                                        f"contrato passou a exigir '{nome}' em {ref}; o consumidor não envia",
                                        f"{ref} requestBody.required"))
        for nome, valor in corpo.items():
            if nome not in props:
                fechado = esquema.get("additionalProperties") is False
                saida.append(Achado(CAMADA, QUEBRA if fechado else INFO, "A-REQ-CAMPO-DESCONHECIDO", it.id,
                                    f"consumidor envia '{nome}', que o contrato não declara"
                                    + (" (additionalProperties: false)" if fechado else " (será ignorado)"),
                                    f"{ref} requestBody"))
                continue
            sub = oas.esquema(props[nome])
            valores = enum_valores(sub)
            if sucesso and valores is not None and valor is not None and valor not in valores:
                saida.append(Achado(CAMADA, QUEBRA, "A-REQ-ENUM", it.id,
                                    f"consumidor envia {nome}={valor!r}; contrato aceita {valores}",
                                    f"{ref} requestBody.{nome}"))
            if valor is None and "null" not in tipos(sub):
                saida.append(Achado(CAMADA, QUEBRA if sucesso else INFO, "A-REQ-NULO", it.id,
                                    f"consumidor envia {nome}=null; contrato não aceita null",
                                    f"{ref} requestBody.{nome}"))
    enviados = set((it.requisicao.get("query") or {}).keys())
    for p in op.parametros:
        if p.get("in") == "query" and p.get("required") and p.get("name") not in enviados and sucesso:
            saida.append(Achado(CAMADA, QUEBRA, "A-QUERY-OBRIGATORIA", it.id,
                                f"{ref} exige ?{p.get('name')}= e o consumidor não envia", f"{ref} parameters"))
    for nome, valor in (it.requisicao.get("query") or {}).items():
        decl = next((p for p in op.parametros if p.get("in") == "query" and p.get("name") == nome), None)
        if decl is None:
            saida.append(Achado(CAMADA, QUEBRA, "A-QUERY-DESCONHECIDA", it.id,
                                f"consumidor usa ?{nome}=, que {ref} não declara", f"{ref} parameters"))
            continue
        valores = enum_valores(oas.esquema(decl.get("schema")))
        if sucesso and valores is not None and valor not in valores:
            saida.append(Achado(CAMADA, QUEBRA, "A-QUERY-ENUM", it.id,
                                f"consumidor usa ?{nome}={valor}; contrato aceita {valores}", f"{ref} parameters"))
    return saida


def _checar_campos(contrato: Contrato, oas: OpenApi, it: Interacao, campos: dict, esquema: dict,
                   prefixo: str, evidencia: str) -> list[Achado]:
    saida: list[Achado] = []
    props = esquema.get("properties") or {}
    obrigatorios = set(esquema.get("required") or [])
    for nome, exp in campos.items():
        exp = exp or {}
        rotulo = f"{prefixo}{nome}"
        presenca = exp.get("presenca", "obrigatoria")
        aceita_nulo = bool(exp.get("nulo", False))
        if nome not in props:
            if presenca == "opcional":
                saida.append(Achado(CAMADA, RISCO, "A-CAMPO-NAO-DOCUMENTADO", it.id,
                                    f"consumidor lê '{rotulo}' (opcional), que o contrato não documenta", evidencia))
            else:
                saida.append(Achado(CAMADA, QUEBRA, "A-CAMPO-AUSENTE", it.id,
                                    f"consumidor lê '{rotulo}', que o contrato não declara", evidencia))
            continue
        sub = oas.esquema(props[nome])
        aceitos = tipos(sub)
        if presenca == "obrigatoria" and nome not in obrigatorios:
            if aceita_nulo:
                saida.append(Achado(CAMADA, RISCO, "A-PRESENCA-NAO-GARANTIDA", it.id,
                                    f"consumidor espera '{rotulo}' sempre presente (pode ser null); o contrato não "
                                    "o lista em required — ausência ≠ null", evidencia))
            else:
                saida.append(Achado(CAMADA, QUEBRA, "A-CAMPO-OPCIONAL-NO-CONTRATO", it.id,
                                    f"consumidor depende de '{rotulo}', mas o contrato permite omiti-lo", evidencia))
        if "null" in aceitos and not aceita_nulo:
            saida.append(Achado(CAMADA, QUEBRA, "A-NULO-INESPERADO", it.id,
                                f"contrato permite '{rotulo}' = null; o consumidor não trata null", evidencia))
        tipo = exp.get("tipo")
        concretos = aceitos - {"null"}
        if tipo and concretos and tipo not in concretos:
            if tipo == "number" and "integer" in concretos:
                pass
            elif tipo == "integer" and "number" in concretos:
                saida.append(Achado(CAMADA, RISCO, "A-TIPO-ALARGADO", it.id,
                                    f"'{rotulo}': consumidor espera integer, contrato diz number", evidencia))
            else:
                saida.append(Achado(CAMADA, QUEBRA, "A-TIPO", it.id,
                                    f"'{rotulo}': consumidor espera {tipo}, contrato diz {sorted(concretos)}", evidencia))
                continue
        formato = exp.get("formato")
        if formato and sub.get("format") != formato:
            sev = RISCO if not sub.get("format") else QUEBRA
            saida.append(Achado(CAMADA, sev, "A-FORMATO", it.id,
                                f"'{rotulo}': consumidor espera formato {formato}, contrato diz "
                                f"{sub.get('format') or 'nenhum'}", evidencia))
        saida.extend(_checar_enum(contrato, it, nome, rotulo, exp, sub, evidencia))
        if tipo == "array" and isinstance(exp.get("itens"), dict):
            itens = oas.esquema(sub.get("items"))
            saida.extend(_checar_campos(contrato, oas, it, exp["itens"], itens, f"{rotulo}[].", evidencia))
        if tipo == "object" and isinstance(exp.get("campos"), dict):
            saida.extend(_checar_campos(contrato, oas, it, exp["campos"], sub, f"{rotulo}.", evidencia))
    return saida


def _checar_enum(contrato: Contrato, it: Interacao, nome: str, rotulo: str, exp: dict, sub: dict,
                 evidencia: str) -> list[Achado]:
    saida: list[Achado] = []
    conhecidos = exp.get("enum")
    publicados = enum_valores(sub)
    fechado = nome in contrato.enums_fechados
    if conhecidos and publicados is not None:
        novos = [v for v in publicados if v not in conhecidos]
        if novos:
            saida.append(Achado(CAMADA, QUEBRA if fechado else INFO, "A-ENUM-NOVO", it.id,
                                f"'{rotulo}' ganhou {novos} no contrato; o consumidor "
                                + ("usa switch exaustivo (enum fechado) e quebra" if fechado else "ignora valores novos"),
                                evidencia))
    elif conhecidos and publicados is None and fechado:
        saida.append(Achado(CAMADA, RISCO, "A-ENUM-ABERTO", it.id,
                            f"'{rotulo}' é enum fechado no consumidor, mas o contrato não restringe valores",
                            evidencia))
    igual = exp.get("igual")
    if publicados is not None and isinstance(igual, str) and "{{" not in igual and igual not in publicados:
        saida.append(Achado(CAMADA, QUEBRA, "A-VALOR-FORA-DO-ENUM", it.id,
                            f"consumidor espera '{rotulo}' = {igual!r}, fora do enum publicado {publicados}",
                            evidencia))
    return saida
