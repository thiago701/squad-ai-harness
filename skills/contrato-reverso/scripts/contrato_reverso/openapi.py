# -*- coding: utf-8 -*-
"""Leitura mínima e determinística de OpenAPI 3.0/3.1 — só o que a verificação reversa usa."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Operacao:
    caminho: str            # template do OpenAPI, ex.: /tasks/{taskId}
    metodo: str
    dados: dict
    parametros: tuple       # parâmetros do path-item + da operação, já resolvidos


class OpenApi:
    def __init__(self, documento: dict):
        self.doc = documento or {}

    # ------------------------------------------------------------------ refs
    def resolver(self, no: Any, _profundidade: int = 0) -> Any:
        if _profundidade > 32:
            return {}
        if isinstance(no, dict) and "$ref" in no:
            ref = str(no["$ref"])
            if not ref.startswith("#/"):
                return {}
            alvo: Any = self.doc
            for parte in ref[2:].split("/"):
                parte = parte.replace("~1", "/").replace("~0", "~")
                alvo = alvo.get(parte, {}) if isinstance(alvo, dict) else {}
            return self.resolver(alvo, _profundidade + 1)
        return no

    def esquema(self, no: Any) -> dict:
        """Resolve $ref e achata allOf (merge de properties/required)."""
        no = self.resolver(no)
        if not isinstance(no, dict):
            return {}
        if "allOf" not in no:
            return no
        mesclado: dict = {k: v for k, v in no.items() if k != "allOf"}
        props = dict(mesclado.get("properties") or {})
        req = list(mesclado.get("required") or [])
        for sub in no["allOf"]:
            sub = self.esquema(sub)
            props.update(sub.get("properties") or {})
            req.extend(sub.get("required") or [])
            for chave in ("type", "enum", "format", "items", "nullable", "additionalProperties"):
                if chave in sub and chave not in mesclado:
                    mesclado[chave] = sub[chave]
        mesclado["properties"] = props
        mesclado["required"] = req
        return mesclado

    # ------------------------------------------------------------ operações
    def operacoes(self) -> list[Operacao]:
        saida = []
        for caminho, item in (self.doc.get("paths") or {}).items():
            item = self.resolver(item) or {}
            comuns = [self.resolver(p) for p in item.get("parameters") or []]
            for metodo, dados in item.items():
                if metodo.upper() in ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"):
                    proprios = [self.resolver(p) for p in (dados or {}).get("parameters") or []]
                    saida.append(Operacao(caminho, metodo.upper(), dados or {}, tuple(comuns + proprios)))
        return saida

    def achar(self, metodo: str, caminho_concreto: str) -> Operacao | None:
        """Casa caminho concreto com templates; estático vence parametrizado (igual ao Gateway)."""
        candidatos = [op for op in self.operacoes()
                      if op.metodo == metodo and casa_template(op.caminho, caminho_concreto)]
        if not candidatos:
            return None
        return sorted(candidatos, key=lambda op: op.caminho.count("{"))[0]

    def seguranca_exigida(self, op: Operacao) -> bool:
        seg = op.dados.get("security", self.doc.get("security"))
        if not seg:
            return False
        return not any(item == {} for item in seg)  # [{}] = segurança opcional

    def respostas(self, op: Operacao) -> dict:
        return {str(k): self.resolver(v) for k, v in (op.dados.get("responses") or {}).items()}

    def resposta_para(self, op: Operacao, status: int) -> dict | None:
        resp = self.respostas(op)
        for chave in (str(status), f"{str(status)[0]}XX", f"{str(status)[0]}xx", "default"):
            if chave in resp:
                return resp[chave]
        return None

    def corpo_requisicao(self, op: Operacao) -> tuple[bool, dict]:
        rb = self.resolver(op.dados.get("requestBody")) or {}
        conteudo = rb.get("content") or {}
        json_like = next((v for k, v in conteudo.items() if "json" in k), None)
        return bool(rb.get("required")), self.esquema((json_like or {}).get("schema"))


# ------------------------------------------------------------------ helpers
def casa_template(template: str, concreto: str) -> bool:
    return re.fullmatch(regex_template(template), concreto.split("?")[0]) is not None


def regex_template(template: str) -> str:
    """`{x}` casa um segmento; `{x+}` (proxy guloso do API Gateway) casa um ou mais."""
    partes = re.split(r"(\{[^}/]+\})", template.rstrip("/") or "/")
    regex = "".join((".+" if p.endswith("+}") else "[^/]+") if p.startswith("{") and p.endswith("}") else re.escape(p)
                    for p in partes)
    return regex + "/?"


def tipos(esquema: dict) -> set[str]:
    """Conjunto de tipos JSON aceitos (3.1 `type: [x, 'null']` e 3.0 `nullable: true`)."""
    t = esquema.get("type")
    conjunto = set(t) if isinstance(t, list) else ({t} if t else set())
    if esquema.get("nullable") is True:
        conjunto.add("null")
    enum = esquema.get("enum")
    if isinstance(enum, list) and None in enum:
        conjunto.add("null")
    for chave in ("oneOf", "anyOf"):
        for sub in esquema.get(chave) or []:
            if isinstance(sub, dict):
                conjunto |= tipos(sub)
    return {str(x) for x in conjunto}


def enum_valores(esquema: dict) -> list | None:
    enum = esquema.get("enum")
    if isinstance(enum, list):
        return [v for v in enum if v is not None]
    return None
