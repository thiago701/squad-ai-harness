# -*- coding: utf-8 -*-
"""Leitura de YAML (inclusive templates SAM/CloudFormation) e do contrato do consumidor."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:  # PyYAML já é usada no repo; ausência => inconclusivo, nunca aprovado.
    import yaml
except ImportError:  # pragma: no cover - exercitado só em máquina sem PyYAML
    yaml = None  # type: ignore[assignment]


class DependenciaAusente(RuntimeError):
    """Falta algo para rodar (PyYAML, arquivo). Vira veredito inconclusivo."""


class ArquivoMalformado(ValueError):
    """YAML/JSON que não parseia (ex.: template do Gateway inválido — o deploy também falharia)."""


class ContratoInvalido(ValueError):
    """O arquivo do consumidor não segue o formato. Vira reprovado (erro de autoria)."""


METODOS = ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD")
METODOS_SEGUROS = ("GET", "OPTIONS", "HEAD")
_PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_:\-]+)\s*\}\}")


def _loader_tolerante():
    """SafeLoader que aceita !Ref/!Sub/!GetAtt... devolvendo o valor cru (sem resolver)."""
    if yaml is None:
        raise DependenciaAusente("PyYAML não instalada (pip install pyyaml) — verificação inconclusiva")

    class _Loader(yaml.SafeLoader):
        pass

    def _construir(loader, sufixo, node):  # noqa: ARG001 - assinatura do PyYAML
        if isinstance(node, yaml.ScalarNode):
            return loader.construct_scalar(node)
        if isinstance(node, yaml.SequenceNode):
            return loader.construct_sequence(node, deep=True)
        return loader.construct_mapping(node, deep=True)

    _Loader.add_multi_constructor("!", _construir)
    return _Loader


def ler_yaml(caminho: Path) -> Any:
    if not caminho.is_file():
        raise DependenciaAusente(f"arquivo não encontrado: {caminho}")
    texto = caminho.read_text(encoding="utf-8")
    try:
        return yaml.load(texto, Loader=_loader_tolerante())  # noqa: S506 - loader é SafeLoader
    except yaml.YAMLError as exc:
        marca = getattr(exc, "problem_mark", None)
        onde = f" (linha {marca.line + 1}, coluna {marca.column + 1})" if marca else ""
        raise ArquivoMalformado(f"{caminho.name} não é YAML válido{onde}: {getattr(exc, 'problem', exc)}") from exc


def hash_arquivos(caminhos: list[Path]) -> str:
    """Hash de conteúdo (ordem estável). Base do cache e da correlação de versões."""
    h = hashlib.sha256()
    for caminho in sorted(caminhos, key=lambda p: str(p)):
        h.update(str(caminho).replace("\\", "/").encode())
        if caminho.is_file():
            h.update(caminho.read_bytes())
        elif caminho.is_dir():
            for filho in sorted(p for p in caminho.rglob("*") if p.is_file() and "target" not in p.parts):
                h.update(str(filho.relative_to(caminho)).replace("\\", "/").encode())
                h.update(filho.read_bytes())
    return h.hexdigest()[:16]


def placeholders(valor: Any) -> set[str]:
    achados: set[str] = set()
    if isinstance(valor, str):
        achados.update(_PLACEHOLDER.findall(valor))
    elif isinstance(valor, dict):
        for v in valor.values():
            achados |= placeholders(v)
    elif isinstance(valor, list):
        for v in valor:
            achados |= placeholders(v)
    return achados


def substituir(valor: Any, variaveis: dict[str, str]) -> Any:
    """Troca {{nome}} pelos valores conhecidos; desconhecidos ficam intactos."""
    if isinstance(valor, str):
        return _PLACEHOLDER.sub(lambda m: str(variaveis.get(m.group(1), m.group(0))), valor)
    if isinstance(valor, dict):
        return {k: substituir(v, variaveis) for k, v in valor.items()}
    if isinstance(valor, list):
        return [substituir(v, variaveis) for v in valor]
    return valor


@dataclass
class Interacao:
    id: str
    risco: str
    origem: dict
    requisicao: dict
    resposta: dict
    capturar: dict = field(default_factory=dict)

    @property
    def metodo(self) -> str:
        return str(self.requisicao.get("metodo", "GET")).upper()

    @property
    def caminho(self) -> str:
        return str(self.requisicao.get("caminho", "/"))

    @property
    def token(self) -> str | None:
        valor = self.requisicao.get("token")
        return str(valor) if valor else None

    @property
    def status_esperados(self) -> list[int]:
        status = self.resposta.get("status")
        return [int(s) for s in status] if isinstance(status, list) else [int(status)]

    @property
    def content_types(self) -> list[str]:
        ct = self.resposta.get("content_type")
        if ct is None:
            return []
        return [str(c).lower() for c in ct] if isinstance(ct, list) else [str(ct).lower()]

    @property
    def mesma_fonte_do_provedor(self) -> bool:
        return str(self.origem.get("tipo", "")).startswith("openapi")


@dataclass
class Contrato:
    arquivo: Path
    raiz_repo: Path
    bruto: dict
    interacoes: list[Interacao]

    @property
    def consumidor(self) -> dict:
        return self.bruto.get("consumidor") or {}

    @property
    def provedor(self) -> dict:
        return self.bruto.get("provedor") or {}

    @property
    def nome(self) -> str:
        return str(self.consumidor.get("nome", self.arquivo.stem))

    @property
    def navegador(self) -> bool:
        return self.consumidor.get("tipo") == "navegador"

    @property
    def enums_fechados(self) -> set[str]:
        return set((self.consumidor.get("leitor") or {}).get("enums_fechados") or [])

    def caminho_repo(self, relativo: str | None) -> Path | None:
        return (self.raiz_repo / relativo) if relativo else None

    @property
    def openapi(self) -> Path | None:
        return self.caminho_repo(self.provedor.get("openapi"))

    @property
    def gateway(self) -> dict:
        return self.provedor.get("gateway") or {}

    @property
    def template_gateway(self) -> Path | None:
        return self.caminho_repo(self.gateway.get("template"))

    def variaveis_base(self) -> dict[str, str]:
        return {"origem": str(self.consumidor.get("origem_navegador", ""))}


_OBRIGATORIOS_INTERACAO = ("id", "risco", "origem", "requisicao", "resposta")
_TIPOS_ORIGEM = ("documentacao", "codigo-cliente", "teste-cliente", "sdk", "exemplo-aprovado",
                 "trafego-sanitizado", "incidente", "openapi-exemplo", "hipotese")


def carregar_contrato(arquivo: Path, raiz_repo: Path) -> Contrato:
    bruto = ler_yaml(arquivo)
    if not isinstance(bruto, dict):
        raise ContratoInvalido(f"{arquivo}: raiz deve ser um mapa")
    if bruto.get("versao_formato") != 1:
        raise ContratoInvalido(f"{arquivo}: versao_formato deve ser 1")
    for chave in ("consumidor", "provedor", "interacoes"):
        if not bruto.get(chave):
            raise ContratoInvalido(f"{arquivo}: falta a seção '{chave}'")
    interacoes: list[Interacao] = []
    vistos: set[str] = set()
    capturas_definidas: set[str] = set()
    identidades = set(bruto.get("identidades") or [])
    for indice, item in enumerate(bruto["interacoes"]):
        faltando = [c for c in _OBRIGATORIOS_INTERACAO if c not in (item or {})]
        if faltando:
            raise ContratoInvalido(f"{arquivo}: interação #{indice} sem {faltando}")
        if item["id"] in vistos:
            raise ContratoInvalido(f"{arquivo}: id duplicado '{item['id']}'")
        vistos.add(item["id"])
        tipo_origem = (item["origem"] or {}).get("tipo")
        if tipo_origem not in _TIPOS_ORIGEM:
            raise ContratoInvalido(f"{arquivo}: '{item['id']}' com origem.tipo inválido ({tipo_origem}); "
                                   f"use um de {_TIPOS_ORIGEM}")
        if str(item["requisicao"].get("metodo", "GET")).upper() not in METODOS:
            raise ContratoInvalido(f"{arquivo}: '{item['id']}' com método inválido")
        if "status" not in item["resposta"]:
            raise ContratoInvalido(f"{arquivo}: '{item['id']}' sem resposta.status")
        token = item["requisicao"].get("token")
        if token and identidades and token not in identidades and token != "invalido":
            raise ContratoInvalido(f"{arquivo}: '{item['id']}' usa identidade não declarada '{token}'")
        usados = {p for p in placeholders(item["requisicao"]) | placeholders(item["resposta"])
                  if p != "origem"}
        indefinidos = usados - capturas_definidas
        if indefinidos:
            raise ContratoInvalido(f"{arquivo}: '{item['id']}' usa {sorted(indefinidos)} antes de capturar")
        capturas_definidas |= set((item.get("capturar") or {}).keys())
        interacoes.append(Interacao(id=item["id"], risco=item["risco"], origem=item["origem"],
                                    requisicao=item["requisicao"], resposta=item["resposta"],
                                    capturar=item.get("capturar") or {}))
    return Contrato(arquivo=arquivo, raiz_repo=raiz_repo, bruto=bruto, interacoes=interacoes)


def descobrir_contratos(raiz_repo: Path) -> list[Path]:
    return sorted((raiz_repo / "contracts" / "consumidores").glob("**/*.cdc.yaml"))
