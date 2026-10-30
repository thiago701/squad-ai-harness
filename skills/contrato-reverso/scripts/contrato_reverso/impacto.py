# -*- coding: utf-8 -*-
"""Seleção por impacto: arquivos alterados → nível de verificação por contrato.

Regras (fail-safe: na dúvida, amplia — nunca reduz o que roda):
  contrato do consumidor / OpenAPI ............. direcionado (a expectativa ou a promessa mudou: provar na implementação)
  aceites de divergência ....................... rápido
  template do Gateway .......................... rápido + recomenda ampliado (só o Gateway implantado prova)
  código do provedor, núcleo de domínio ........ direcionado
  código TRANSVERSAL (serialização, auth, borda,
  config, DTOs, roteamento) .................... direcionado + suíte completa
  build (pom/gradle/wrapper) ................... direcionado + suíte completa
  testes do provedor ........................... direcionado
  documentação dentro do provedor (*.md) ....... rápido (pode ser fonte de expectativa)
  outro arquivo dentro do provedor ............. INCERTO → direcionado + suíte completa
  fora do provedor e dos contratos ............. nada (vazio legítimo)
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .modelo import Contrato

NIVEIS = ("nenhum", "rapido", "direcionado", "ampliado")
TRANSVERSAL_PADRAO = (r"/api/", r"Json", r"Serializ", r"Auth", r"Secur", r"/config/", r"HttpRequests",
                      r"/dto/", r"RouteKey", r"Handler", r"handler\.", r"/adapters/", r"serializ", r"middleware")
BUILD = ("pom.xml", "build.gradle", "build.gradle.kts", "mvnw", "mvnw.cmd", "settings.gradle",
         "requirements.txt", "pyproject.toml", "package.json")


@dataclass
class Impacto:
    nivel: str = "nenhum"
    suite_completa: bool = False
    recomenda_ampliado: bool = False
    incerto: bool = False
    motivos: list[str] = field(default_factory=list)

    def subir(self, nivel: str, motivo: str) -> None:
        if NIVEIS.index(nivel) > NIVEIS.index(self.nivel):
            self.nivel = nivel
        self.motivos.append(motivo)


def _rel(p: str) -> str:
    return p.replace("\\", "/").lstrip("./")


def avaliar(contrato: Contrato, alterados: list[str]) -> Impacto:
    imp = Impacto()
    raiz = contrato.raiz_repo
    contrato_rel = _rel(str(contrato.arquivo.resolve().relative_to(raiz.resolve())))
    pasta_contrato = contrato_rel.rsplit("/", 1)[0] + "/"
    openapi = _rel(contrato.provedor.get("openapi", "") or "")
    template = _rel(contrato.gateway.get("template", "") or "")
    prov_raiz = _rel(contrato.provedor.get("raiz", "") or "").rstrip("/")
    prov = "" if prov_raiz in ("", ".") else prov_raiz + "/"      # "" = o provedor é o repositório inteiro
    padroes = tuple(contrato.provedor.get("transversal") or TRANSVERSAL_PADRAO)
    for bruto in alterados:
        arq = _rel(bruto)
        nome = arq.rsplit("/", 1)[-1]
        if arq == contrato_rel:
            imp.subir("direcionado", f"{arq}: expectativa do consumidor mudou")
        elif arq.startswith(pasta_contrato) and "aceit" in nome:
            imp.subir("rapido", f"{arq}: aceites de divergência")
        elif arq.startswith(pasta_contrato) and nome == "mutacoes.yaml":
            continue  # só o bench usa
        elif arq == openapi:
            imp.subir("direcionado", f"{arq}: contrato publicado mudou")
        elif template and (arq == template or (not template.endswith((".yaml", ".yml", ".json")) and arq.startswith(template.rstrip("/") + "/"))):
            imp.subir("rapido", f"{arq}: configuração do Gateway mudou")
            imp.recomenda_ampliado = True
            imp.motivos.append("Gateway alterado: só a replay pelo endpoint implantado (C2) comprova")
        elif arq.startswith("contracts/consumidores/") or arq.startswith(".contrato-reverso/"):
            continue  # outro contrato / artefato da ferramenta
        elif arq.startswith(prov):
            interno = arq[len(prov):]
            partes = set(interno.split("/")[:-1])
            if interno.startswith(("target/", "node_modules/", "build/", ".gradle/", "__pycache__/")) or "__pycache__" in partes:
                continue
            if nome in BUILD or interno.startswith(".mvn/"):
                imp.subir("direcionado", f"{arq}: build do provedor")
                imp.suite_completa = True
            elif partes & {"test", "tests", "__tests__"} or re.search(r"(\.test\.|\.spec\.|^test_|_test\.)", nome):
                imp.subir("direcionado", f"{arq}: teste do provedor")
            elif nome.lower().endswith(".md"):
                imp.subir("rapido", f"{arq}: documentação do provedor (fonte de expectativas)")
            elif re.search(r"\.(java|kt|py|mjs|cjs|js|ts|go|rs|cs)$", nome):
                if any(re.search(p, arq) for p in padroes):
                    imp.subir("direcionado", f"{arq}: código transversal (amplia para suíte completa)")
                    imp.suite_completa = True
                else:
                    imp.subir("direcionado", f"{arq}: código do provedor")
            elif prov:  # dentro de uma pasta de provedor declarada e sem regra: incerto, amplia
                imp.subir("direcionado", f"{arq}: arquivo do provedor sem regra — INCERTO, amplia")
                imp.suite_completa = True
                imp.incerto = True
    return imp


def arquivos_alterados(raiz: Path, base: str | None) -> tuple[list[str], str]:
    """Diff vs. base (ou HEAD) + working tree + não rastreados. Devolve (arquivos, descrição da base)."""
    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=raiz, capture_output=True, text=True)

    if git("rev-parse", "--is-inside-work-tree").returncode != 0:
        return [], "sem-git"
    arquivos: set[str] = set()
    descricao = "working-tree vs HEAD"
    if base:
        r = git("diff", "--name-only", f"{base}...HEAD")
        if r.returncode == 0:
            arquivos |= set(r.stdout.split())
            descricao = f"{base}...HEAD + working-tree"
    for args in (("diff", "--name-only", "HEAD"), ("ls-files", "--others", "--exclude-standard")):
        r = git(*args)
        if r.returncode == 0:
            arquivos |= set(r.stdout.split())
    return sorted(arquivos), descricao
