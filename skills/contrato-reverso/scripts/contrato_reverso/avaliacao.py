# -*- coding: utf-8 -*-
"""Avaliador ÚNICO das respostas observadas (camadas C1 e C2).

Os dois transportes — JUnit in-process (Gateway simulado) e replay HTTP pelo Gateway
real — produzem o mesmo formato de "observado"; este módulo julga ambos com as mesmas
regras. Uma regra, dois transportes: a evidência muda de alcance, não de critério.
"""
from __future__ import annotations

import json
import re
from datetime import datetime

from . import INFO, QUEBRA, Achado
from .modelo import Interacao, placeholders, substituir

_DATA_HORA = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")
_TIPOS_PY = {"string": (str,), "integer": (int,), "number": (int, float), "boolean": (bool,),
             "array": (list,), "object": (dict,)}


def _tipo_ok(valor, tipo: str) -> bool:
    if tipo in ("integer", "number") and isinstance(valor, bool):
        return False
    return isinstance(valor, _TIPOS_PY.get(tipo, (object,)))


def _data(valor: str) -> datetime | None:
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _headers_minusculos(headers: dict | None) -> dict[str, str]:
    return {str(k).lower(): str(v) for k, v in (headers or {}).items()}


def avaliar(camada: str, it: Interacao, observado: dict, variaveis: dict[str, str],
            enums_fechados: set[str]) -> tuple[list[Achado], dict[str, str]]:
    """Julga uma resposta observada. Devolve (achados, novas capturas)."""
    faltando = (placeholders(it.requisicao) | placeholders(it.resposta)) - set(variaveis)
    if faltando:
        return [Achado(camada, INFO, "C-DEPENDENCIA", it.id,
                       f"não avaliada: depende de {sorted(faltando)}, não capturado antes (veja a causa acima)")], {}
    resposta = substituir(it.resposta, variaveis)
    status = observado.get("status")
    esperados = resposta["status"] if isinstance(resposta["status"], list) else [resposta["status"]]
    esperados = [int(s) for s in esperados]
    headers = _headers_minusculos(observado.get("headers"))
    origem = observado.get("origem_resposta", "")
    sufixo = f" (resposta gerada por: {origem})" if origem else ""
    if status not in esperados:
        return [Achado(camada, QUEBRA, "C-STATUS", it.id,
                       f"esperado {esperados}, observado {status}{sufixo}")], {}
    achados: list[Achado] = []
    tipos = resposta.get("content_type")
    if tipos:
        aceitos = [t.lower() for t in (tipos if isinstance(tipos, list) else [tipos])]
        ct = headers.get("content-type", "").split(";")[0].strip().lower()
        if ct not in aceitos:
            achados.append(Achado(camada, QUEBRA, "C-CONTENT-TYPE", it.id,
                                  f"Content-Type '{ct or 'ausente'}' fora de {aceitos}{sufixo}"))
    for nome, esperado in (resposta.get("headers") or {}).items():
        valor = headers.get(nome.lower())
        opcoes = esperado if isinstance(esperado, list) else [esperado]
        if valor is None or valor not in [str(o) for o in opcoes]:
            achados.append(Achado(camada, QUEBRA, "C-HEADER", it.id,
                                  f"header {nome}: esperado {opcoes}, observado {valor!r}{sufixo}"))
    corpo_txt = observado.get("corpo") or ""
    if resposta.get("corpo_vazio") and corpo_txt.strip():
        achados.append(Achado(camada, QUEBRA, "C-CORPO-NAO-VAZIO", it.id, "consumidor espera corpo vazio"))
    campos = resposta.get("campos") or {}
    capturas: dict[str, str] = {}
    if campos or it.capturar:
        try:
            corpo = json.loads(corpo_txt) if corpo_txt.strip() else None
        except ValueError:
            achados.append(Achado(camada, QUEBRA, "C-JSON", it.id, "corpo não é JSON válido"))
            return achados, {}
        if not isinstance(corpo, dict):
            achados.append(Achado(camada, QUEBRA, "C-JSON", it.id, "corpo não é um objeto JSON"))
            return achados, {}
        corpo_req = substituir(it.requisicao.get("corpo") or {}, variaveis)
        achados.extend(_campos(camada, it.id, campos, corpo, "", corpo_req, variaveis, enums_fechados))
        for var, campo in it.capturar.items():
            valor = corpo.get(campo)
            if valor is None:
                achados.append(Achado(camada, QUEBRA, "C-CAPTURA", it.id,
                                      f"campo '{campo}' ausente: '{var}' não pôde ser capturado"))
            else:
                capturas[var] = str(valor)
    return achados, capturas


def _campos(camada: str, iid: str, campos: dict, obj: dict, prefixo: str, corpo_req: dict,
            variaveis: dict, fechados: set[str]) -> list[Achado]:
    a: list[Achado] = []
    for nome, exp in campos.items():
        exp = exp or {}
        rot = f"{prefixo}{nome}"
        presente = nome in obj
        valor = obj.get(nome)
        if not presente:
            if exp.get("presenca", "obrigatoria") == "obrigatoria":
                a.append(Achado(camada, QUEBRA, "C-CAMPO-AUSENTE", iid, f"'{rot}' ausente na resposta"))
            continue
        if valor is None:
            if not exp.get("nulo", False):
                a.append(Achado(camada, QUEBRA, "C-NULO", iid, f"'{rot}' veio null e o consumidor não aceita null"))
            continue
        tipo = exp.get("tipo")
        if tipo and not _tipo_ok(valor, tipo):
            a.append(Achado(camada, QUEBRA, "C-TIPO", iid,
                            f"'{rot}': esperado {tipo}, observado {type(valor).__name__} ({valor!r})"))
            continue
        if exp.get("formato") == "date-time" and (not isinstance(valor, str) or not _DATA_HORA.match(valor)):
            a.append(Achado(camada, QUEBRA, "C-FORMATO", iid, f"'{rot}' não é date-time RFC 3339: {valor!r}"))
        enum = exp.get("enum")
        if enum and valor not in enum:
            a.append(Achado(camada, QUEBRA if nome in fechados else INFO, "C-ENUM", iid,
                            f"'{rot}' = {valor!r} fora dos valores conhecidos pelo consumidor {enum}"))
        if "igual" in exp and str(valor) != str(exp["igual"]):
            a.append(Achado(camada, QUEBRA, "C-VALOR", iid, f"'{rot}': esperado {exp['igual']!r}, observado {valor!r}"))
        if "eco" in exp and exp["eco"] in corpo_req and valor != corpo_req[exp["eco"]]:
            a.append(Achado(camada, QUEBRA, "C-ECO", iid,
                            f"'{rot}' devia ecoar o enviado ({corpo_req[exp['eco']]!r}), observado {valor!r}"))
        if "padrao" in exp and isinstance(valor, str) and not re.search(str(exp["padrao"]), valor):
            a.append(Achado(camada, QUEBRA, "C-PADRAO", iid, f"'{rot}' = {valor!r} não casa /{exp['padrao']}/"))
        if "igual_tamanho_de" in exp:
            irmao = obj.get(exp["igual_tamanho_de"])
            if isinstance(irmao, list) and valor != len(irmao):
                a.append(Achado(camada, QUEBRA, "C-CONTAGEM", iid,
                                f"'{rot}' = {valor}, mas '{exp['igual_tamanho_de']}' tem {len(irmao)} itens"))
        if "soma_de" in exp:
            parcelas = [obj.get(p) for p in exp["soma_de"]]
            if all(isinstance(p, int) for p in parcelas) and sum(parcelas) != valor:
                a.append(Achado(camada, QUEBRA, "C-SOMA", iid,
                                f"'{rot}' = {valor}, soma de {exp['soma_de']} = {sum(parcelas)}"))
        if isinstance(valor, list):
            a.extend(_lista(camada, iid, exp, valor, rot, corpo_req, variaveis, fechados))
        if isinstance(valor, dict) and isinstance(exp.get("campos"), dict):
            a.extend(_campos(camada, iid, exp["campos"], valor, f"{rot}.", corpo_req, variaveis, fechados))
    return a


def _lista(camada: str, iid: str, exp: dict, valor: list, rot: str, corpo_req: dict, variaveis: dict,
           fechados: set[str]) -> list[Achado]:
    a: list[Achado] = []
    if isinstance(exp.get("itens"), dict):
        for i, item in enumerate(valor):
            if isinstance(item, dict):
                a.extend(_campos(camada, iid, exp["itens"], item, f"{rot}[{i}].", corpo_req, variaveis, fechados))
    ordem = exp.get("ordenado_por")
    if ordem:
        campo = ordem["campo"]
        chaves = [(_data(x.get(campo)) or x.get(campo)) for x in valor if isinstance(x, dict)]
        crescente = ordem.get("ordem", "asc") == "asc"
        try:
            ok = all((chaves[i] <= chaves[i + 1]) if crescente else (chaves[i] >= chaves[i + 1])
                     for i in range(len(chaves) - 1))
        except TypeError:
            ok = False
        if not ok:
            a.append(Achado(camada, QUEBRA, "C-ORDENACAO", iid, f"'{rot}' fora da ordem {campo} {ordem.get('ordem')}"))
    todos = exp.get("todos")
    if todos:
        fora = [x.get(todos["campo"]) for x in valor if isinstance(x, dict) and x.get(todos["campo"]) != todos["igual"]]
        if fora:
            a.append(Achado(camada, QUEBRA, "C-FILTRO", iid,
                            f"'{rot}' contém {todos['campo']} fora do filtro {todos['igual']!r}: {fora[:3]}"))
    for var in exp.get("contem_capturas") or []:
        alvo = variaveis.get(var)
        if alvo and not any(isinstance(x, dict) and str(x.get("id")) == alvo for x in valor):
            a.append(Achado(camada, QUEBRA, "C-ITEM-AUSENTE", iid, f"'{rot}' não contém o item capturado '{var}'"))
    return a
