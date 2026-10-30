# -*- coding: utf-8 -*-
"""Leitor mínimo de HCL (Terraform) — stdlib, só o necessário para extrair a config do API Gateway.

Entende: blocos `tipo "rótulo" "rótulo" { ... }`, atributos `chave = valor`, blocos aninhados,
strings (com `${...}` preservado), heredoc, números, booleanos, listas, objetos e expressões
(referências como `aws_apigatewayv2_api.api.id`, `var.x`, chamadas de função) — estas ficam como
`Expr("texto")`, nunca avaliadas. O que não for literal vira PENDENTE na camada B, não chute.
Para valores calculados, prefira `terraform show -json <plan>` (leitor JSON, exato).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Expr:
    texto: str

    def referencia(self) -> str | None:
        """'aws_apigatewayv2_api.api.id' -> 'aws_apigatewayv2_api.api' (endereço do recurso)."""
        m = re.match(r"^\s*(?:data\.)?([a-z0-9_]+)\.([A-Za-z0-9_\-]+)", self.texto)
        return f"{m.group(1)}.{m.group(2)}" if m else None


@dataclass
class Bloco:
    tipo: str
    rotulos: list[str]
    corpo: dict = field(default_factory=dict)      # atributo -> valor
    filhos: dict = field(default_factory=dict)     # nome do bloco aninhado -> [Bloco]

    def bloco(self, nome: str) -> "Bloco | None":
        return (self.filhos.get(nome) or [None])[0]


_TOKEN = re.compile(r"""
    (?P<espaco>[ \t\r]+) | (?P<nl>\n) |
    (?P<comentario>\#[^\n]*|//[^\n]*|/\*.*?\*/) |
    (?P<heredoc><<-?(?P<marca>[A-Za-z_]+)\n.*?\n[ \t]*(?P=marca)(?=\n|$)) |
    (?P<string>"(?:[^"\\]|\\.|\$\{(?:[^{}]|\{[^{}]*\})*\})*") |
    (?P<numero>-?\d+(?:\.\d+)?(?![A-Za-z_])) |
    (?P<ident>[A-Za-z_][A-Za-z0-9_\-]*) |
    (?P<simbolo>[{}\[\]=,():.?*!<>+/%&|-])
""", re.S | re.X)


def _tokens(texto: str) -> list[tuple[str, str]]:
    out = []
    pos = 0
    while pos < len(texto):
        m = _TOKEN.match(texto, pos)
        if not m:
            out.append(("simbolo", texto[pos]))
            pos += 1
            continue
        tipo = m.lastgroup if m.lastgroup != "marca" else "heredoc"
        if m.group("heredoc"):
            tipo = "heredoc"
        if tipo not in ("espaco", "comentario"):
            out.append((tipo, m.group(0)))
        pos = m.end()
    return out


class _Parser:
    def __init__(self, tokens):
        self.t = tokens
        self.i = 0

    def ver(self, k=0):
        j = self.i + k
        return self.t[j] if j < len(self.t) else ("fim", "")

    def pular_nl(self):
        while self.ver()[0] == "nl":
            self.i += 1

    def corpo(self, fim: str | None) -> tuple[dict, dict]:
        attrs: dict = {}
        filhos: dict = {}
        while True:
            self.pular_nl()
            tipo, val = self.ver()
            if tipo == "fim" or (fim and val == fim):
                if fim:
                    self.i += 1
                return attrs, filhos
            if val == ",":
                self.i += 1
                continue
            if tipo in ("ident", "string"):
                nome = val.strip('"')
                self.i += 1
                if self.ver()[1] in ("=", ":"):
                    self.i += 1
                    attrs[nome] = self.valor()
                    continue
                rotulos = []
                while self.ver()[0] in ("string", "ident") and self.ver()[1] != "{":
                    rotulos.append(self.ver()[1].strip('"'))
                    self.i += 1
                if self.ver()[1] == "{":
                    self.i += 1
                    a, f = self.corpo("}")
                    filhos.setdefault(nome, []).append(Bloco(nome, rotulos, a, f))
                    continue
            self.i += 1  # token inesperado: ignora (leitor tolerante)

    def valor(self):
        self.pular_nl()
        tipo, val = self.ver()
        if tipo == "string" and self._fim_de_valor(1):
            self.i += 1
            texto = val[1:-1]
            return Expr(texto[2:-1].strip()) if re.fullmatch(r"\$\{[^}]*\}", texto) else texto.replace('\\"', '"')
        if tipo == "heredoc" and self._fim_de_valor(1):
            self.i += 1
            return val.split("\n", 1)[1].rsplit("\n", 1)[0]
        if tipo == "numero" and self._fim_de_valor(1):
            self.i += 1
            return float(val) if "." in val else int(val)
        if tipo == "ident" and val in ("true", "false", "null") and self._fim_de_valor(1):
            self.i += 1
            return {"true": True, "false": False, "null": None}[val]
        if val == "[":
            self.i += 1
            itens = []
            while True:
                self.pular_nl()
                if self.ver()[1] == "]":
                    self.i += 1
                    return itens
                if self.ver()[1] == ",":
                    self.i += 1
                    continue
                if self.ver()[0] == "fim":
                    return itens
                itens.append(self.valor())
        if val == "{":
            self.i += 1
            a, f = self.corpo("}")
            return a
        return Expr(self._expressao())

    def _fim_de_valor(self, k: int) -> bool:
        return self.ver(k)[0] in ("nl", "fim") or self.ver(k)[1] in (",", "]", "}")

    def _expressao(self) -> str:
        partes, prof = [], 0
        while True:
            tipo, val = self.ver()
            if tipo == "fim":
                break
            if prof == 0 and (tipo == "nl" or val in (",", "]", "}")):
                break
            if val in ("(", "[", "{"):
                prof += 1
            elif val in (")", "]", "}"):
                prof -= 1
            partes.append(val if tipo != "nl" else " ")
            self.i += 1
        return "".join(partes).strip()


def ler(texto: str) -> list[Bloco]:
    attrs, filhos = _Parser(_tokens(texto)).corpo(None)
    return [b for lista in filhos.values() for b in lista]


def resolver_variaveis(valor, variaveis: dict):
    """`var.x` com default literal vira o literal; o resto fica como está."""
    if isinstance(valor, Expr):
        m = re.fullmatch(r"\s*var\.([A-Za-z0-9_]+)\s*", valor.texto)
        if m and m.group(1) in variaveis:
            return variaveis[m.group(1)]
        return valor
    if isinstance(valor, list):
        return [resolver_variaveis(v, variaveis) for v in valor]
    if isinstance(valor, dict):
        return {k: resolver_variaveis(v, variaveis) for k, v in valor.items()}
    return valor
