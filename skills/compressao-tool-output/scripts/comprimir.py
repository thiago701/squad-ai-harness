#!/usr/bin/env python3
"""Compressão determinística de saída de ferramenta por filtros declarativos.

Sem dependência externa. Sem LLM no caminho. Mesma entrada => mesma saída.

Uso:
    comprimir.py --cmd "pytest -q" -- pytest -q          # executa e comprime
    comprimir.py --cmd "mvn verify" --file build.log     # comprime arquivo
    cat x.log | comprimir.py --cmd "mvn verify"          # comprime stdin
    comprimir.py --cmd "pytest -q" --file t.log --verify # não pode mudar o veredito
    comprimir.py --self-test                             # roda os tests[] dos filtros

Procedência: padrão adaptado do OmniRoute (MIT, © 2026 diegosouzapw). Código original.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
DIR_GLOBAL = Path(__file__).resolve().parent.parent / "filtros"
DIR_PROJETO = Path(".squad/filtros")
TAMANHO_MAX_FILTRO = 256 * 1024
METRICAS = Path("_local-artifacts/compressao-metricas.jsonl")
MAX_CHARS_PADRAO = 10_000  # teto duro da saida (rules.maxChars sobrescreve)
PALAVRAS_DE_SUCESSO = ("OK", "passed", "SUCCESS", "sucesso", "limpo")
VEREDITO_VERMELHO = re.compile(
    r"(?i)\b(fail(ed|ure)?|error|erro|exception|BUILD FAILURE|to destroy|denied|refused)\b"
)


class FiltroInvalido(Exception):
    """Filtro rejeitado no carregamento — pulado, nunca fatal (fail-open)."""


# --------------------------------------------------------------------------- modelo


@dataclass
class Filtro:
    id: str
    prioridade: int
    match: dict
    regras: dict
    preserva: dict
    testes: list = field(default_factory=list)

    @staticmethod
    def de_json(dados: dict) -> "Filtro":
        if not dados.get("id"):
            raise FiltroInvalido("filtro sem 'id'")
        if not dados.get("tests"):
            raise FiltroInvalido(f"{dados['id']}: filtro sem tests[] inline")
        regras = dados.get("rules", {})
        if not regras.get("onEmpty"):
            raise FiltroInvalido(f"{dados['id']}: 'rules.onEmpty' é obrigatório")
        _validar_atalhos(dados["id"], regras.get("matchOutput", []))
        _compilar_todos(dados)
        return Filtro(
            id=dados["id"],
            prioridade=int(dados.get("priority", 50)),
            match=dados.get("match", {}),
            regras=regras,
            preserva=dados.get("preserve", {}),
            testes=dados["tests"],
        )

    def casa(self, comando: str, texto: str) -> bool:
        for padrao in self.match.get("commands", []):
            if comando and re.search(padrao, comando):
                return True
        cabeca = "\n".join(texto.splitlines()[:200])
        return any(re.search(p, cabeca, re.M) for p in self.match.get("patterns", []))


def _validar_atalhos(ident: str, atalhos: list) -> None:
    """Atalho que anuncia sucesso SEM cláusula `unless` é o bug perigoso desta skill."""
    for atalho in atalhos:
        anuncia_verde = any(p in atalho.get("then", "") for p in PALAVRAS_DE_SUCESSO)
        if anuncia_verde and not atalho.get("unless"):
            raise FiltroInvalido(f"{ident}: matchOutput de sucesso sem 'unless'")


def _compilar_todos(dados: dict) -> None:
    regras, preserva, match = dados.get("rules", {}), dados.get("preserve", {}), dados.get("match", {})
    grupos = [
        match.get("commands", []),
        match.get("patterns", []),
        regras.get("dropPatterns", []),
        regras.get("includePatterns", []),
        regras.get("collapsePatterns", []),
        preserva.get("errorPatterns", []),
        preserva.get("summaryPatterns", []),
        [a["when"] for a in regras.get("matchOutput", [])],
        [u for a in regras.get("matchOutput", []) for u in a.get("unless", [])],
        [s["from"] for s in regras.get("replace", [])],
    ]
    for padrao in (p for grupo in grupos for p in grupo):
        try:
            re.compile(padrao)
        except re.error as erro:
            raise FiltroInvalido(f"{dados.get('id')}: regex inválida {padrao!r} ({erro})") from erro


# --------------------------------------------------------------------------- carga


def carregar_filtros(avisos: list[str]) -> list[Filtro]:
    return _carregar(DIR_GLOBAL, avisos) + _carregar(DIR_PROJETO, avisos, confiavel=False)


def _carregar(diretorio: Path, avisos: list[str], confiavel: bool = True) -> list[Filtro]:
    if not diretorio.is_dir():
        return []
    confianca = _ler_confianca(diretorio)
    filtros = []
    for caminho in sorted(diretorio.glob("*.json")):
        if caminho.name == "trust.json":
            continue
        try:
            if not confiavel and not _confiavel(caminho, confianca):
                raise FiltroInvalido(f"{caminho.name}: hash ausente/divergente em trust.json")
            if caminho.stat().st_size > TAMANHO_MAX_FILTRO:
                raise FiltroInvalido(f"{caminho.name}: acima de 256 KB")
            filtros.append(Filtro.de_json(json.loads(caminho.read_text(encoding="utf-8"))))
        except (FiltroInvalido, json.JSONDecodeError, OSError) as erro:
            avisos.append(f"filtro ignorado — {erro}")
    return filtros


def _ler_confianca(diretorio: Path) -> dict:
    arquivo = diretorio / "trust.json"
    if not arquivo.is_file():
        return {}
    try:
        return json.loads(arquivo.read_text(encoding="utf-8")).get("filtros", {})
    except (json.JSONDecodeError, OSError):
        return {}


def _confiavel(caminho: Path, confianca: dict) -> bool:
    esperado = confianca.get(caminho.name, "").removeprefix("sha256:")
    if not esperado:
        return False
    real = hashlib.sha256(caminho.read_bytes()).hexdigest()
    return real == esperado


def escolher(filtros: list[Filtro], comando: str, texto: str, tipo: str | None) -> Filtro | None:
    if tipo:
        candidatos = [f for f in filtros if f.id == tipo]
    else:
        candidatos = [f for f in filtros if f.casa(comando, texto)]
    return max(candidatos, key=lambda f: f.prioridade, default=None)


# --------------------------------------------------------------------------- pipeline


def comprimir(texto: str, filtro: Filtro) -> str:
    regras = filtro.regras
    if regras.get("stripAnsi"):
        texto = ANSI.sub("", texto)
    for troca in regras.get("replace", []):
        texto = re.sub(troca["from"], troca["to"], texto)

    atalho = _tentar_atalho(texto, regras.get("matchOutput", []))
    if atalho is not None:
        return atalho

    linhas = texto.splitlines()
    protegidas = _protegidas(linhas, filtro.preserva)
    linhas = _descartar(linhas, protegidas, regras.get("dropPatterns", []))
    linhas = _colapsar(linhas, protegidas, regras)
    linhas = _truncar_linhas(linhas, regras.get("truncateLineAt"))
    # indices mudaram depois de descartar/colapsar: a protecao e recalculada sobre as linhas atuais
    linhas = _cortar(linhas, _protegidas(linhas, filtro.preserva), regras)
    saida = "\n".join(linhas) if linhas else regras["onEmpty"]
    return teto_caracteres(saida, regras.get("maxChars", MAX_CHARS_PADRAO))


def _tentar_atalho(texto: str, atalhos: list) -> str | None:
    for atalho in atalhos:
        if any(re.search(bloqueio, texto, re.M | re.I) for bloqueio in atalho.get("unless", [])):
            continue
        achado = re.search(atalho["when"], texto, re.M)
        if achado:
            resultado = atalho["then"]
            for indice, grupo in enumerate(achado.groups(), start=1):
                resultado = resultado.replace(f"${indice}", grupo or "")
            return resultado
    return None


def _protegidas(linhas: list[str], preserva: dict) -> set[int]:
    padroes = preserva.get("errorPatterns", []) + preserva.get("summaryPatterns", [])
    return {i for i, linha in enumerate(linhas) if any(re.search(p, linha) for p in padroes)}


def _descartar(linhas: list[str], protegidas: set[int], padroes: list[str]) -> list[str]:
    return [
        linha
        for i, linha in enumerate(linhas)
        if i in protegidas or not any(re.search(p, linha) for p in padroes)
    ]


def _colapsar(linhas: list[str], protegidas: set[int], regras: dict) -> list[str]:
    padroes = regras.get("collapsePatterns", [])
    dedup = regras.get("deduplicate", False)
    saida: list[str] = []
    for linha in linhas:
        if not saida:
            saida.append(linha)
            continue
        anterior = saida[-1]
        igual = dedup and linha == anterior
        mesma_classe = any(re.search(p, linha) and re.search(p, anterior) for p in padroes)
        if igual or mesma_classe:
            saida[-1] = _marcar_repeticao(anterior)
        else:
            saida.append(linha)
    return saida


def _marcar_repeticao(linha: str) -> str:
    achado = re.search(r" \(×(\d+)\)$", linha)
    if achado:
        return re.sub(r" \(×\d+\)$", f" (×{int(achado.group(1)) + 1})", linha)
    return f"{linha} (×2)"


def _truncar_linhas(linhas: list[str], limite: int | None) -> list[str]:
    if not limite:
        return linhas
    return [l if len(l) <= limite else f"{l[:limite]}…" for l in linhas]


def _cortar(linhas: list[str], protegidas: set[int], regras: dict) -> list[str]:
    """Corte de tamanho — sinal (linha protegida) sempre vence tamanho."""
    maximo = regras.get("maxLines")
    if not maximo or len(linhas) <= maximo:
        return linhas
    cabeca, cauda = regras.get("headLines", maximo // 2), regras.get("tailLines", maximo // 2)
    padroes = regras.get("includePatterns", [])
    manter = {i for i in range(len(linhas)) if i < cabeca or i >= len(linhas) - cauda}
    manter |= {i for i, l in enumerate(linhas) if any(re.search(p, l) for p in padroes)}
    manter |= protegidas
    elididas = len(linhas) - len(manter)
    saida, vazio_aberto = [], False
    for i, linha in enumerate(linhas):
        if i in manter:
            saida.append(linha)
            vazio_aberto = False
        elif not vazio_aberto:
            saida.append(f"… ({elididas} linhas elididas)")
            vazio_aberto = True
    return saida


def teto_caracteres(texto: str, maximo: int | None) -> str:
    """Ultimo corte, o unico que vence o sinal: cabeca + cauda e a contagem exata do omitido.

    Tecnica reescrita do SWE-agent/mini-swe-agent (commit 04d809c, MIT). Mantem o inicio (comando,
    contexto) e o fim (resumo, veredito) e diz ao agente como pedir de novo, em vez de truncar mudo.
    """
    if not maximo or len(texto) <= maximo:
        return texto
    metade = maximo // 2
    omitidos = len(texto) - 2 * metade
    aviso = (f"\n… ({omitidos} caracteres omitidos; refaça o comando de forma mais seletiva: "
             "grep, head/tail ou filtro por arquivo)\n")
    return texto[:metade] + aviso + texto[-metade:]


# --------------------------------------------------------------------------- verify


def veredito(texto: str) -> str:
    return "VERMELHO" if VEREDITO_VERMELHO.search(texto) else "VERDE"


def registrar(comando: str, filtro: str, antes: int, depois: int) -> None:
    try:
        METRICAS.parent.mkdir(parents=True, exist_ok=True)
        linha = {"cmd": comando, "filtro": filtro, "linhas_antes": antes, "linhas_depois": depois}
        with METRICAS.open("a", encoding="utf-8") as arquivo:
            arquivo.write(json.dumps(linha, ensure_ascii=False) + "\n")
    except OSError:
        pass  # métrica nunca derruba o comando


# --------------------------------------------------------------------------- self-test


def autoteste() -> int:
    avisos: list[str] = []
    falhas = 0
    for filtro in carregar_filtros(avisos):
        for teste in filtro.testes:
            saida = comprimir(teste["input"], filtro)
            for esperado in teste.get("expectedContains", []):
                if esperado not in saida:
                    print(f"✗ {filtro.id}/{teste['name']}: faltou {esperado!r}")
                    falhas += 1
            for proibido in teste.get("expectedNotContains", []):
                if proibido in saida:
                    print(f"✗ {filtro.id}/{teste['name']}: vazou {proibido!r}")
                    falhas += 1
            if "expected" in teste and saida.strip() != teste["expected"].strip():
                print(f"✗ {filtro.id}/{teste['name']}: saída diferente do esperado")
                falhas += 1
    for aviso in avisos:
        print(f"! {aviso}")
    print("self-test: OK" if not falhas else f"self-test: {falhas} falha(s)")
    return 1 if falhas else 0


# --------------------------------------------------------------------------- cli


def ler_entrada(args, resto: list[str]) -> tuple[str, int]:
    if resto:
        execucao = subprocess.run(resto, capture_output=True, text=True)  # noqa: S603
        return (execucao.stdout or "") + (execucao.stderr or ""), execucao.returncode
    if args.file:
        return Path(args.file).read_text(encoding="utf-8", errors="replace"), 0
    return sys.stdin.read(), 0


def main() -> int:
    analisador = argparse.ArgumentParser(description="Comprime saída de ferramenta.")
    analisador.add_argument("--cmd", default="", help="linha de comando (usada para escolher o filtro)")
    analisador.add_argument("--file", help="arquivo com a saída já capturada")
    analisador.add_argument("--tipo", help="força o id do filtro")
    analisador.add_argument("--verify", action="store_true", help="falha se o veredito mudar")
    analisador.add_argument("--self-test", action="store_true", help="roda os tests[] dos filtros")
    args, resto = analisador.parse_known_args()
    resto = [a for a in resto if a != "--"]

    if args.self_test:
        return autoteste()

    bruto, codigo = ler_entrada(args, resto)
    avisos: list[str] = []
    filtro = escolher(carregar_filtros(avisos), args.cmd, bruto, args.tipo)
    if filtro is None:
        print(bruto, end="")
        return codigo

    saida = comprimir(bruto, filtro)
    if args.verify and veredito(bruto) != veredito(saida):
        print(bruto, end="")
        print(f"\n[compressao-tool-output] ABORTADO: filtro={filtro.id} mudaria o veredito", file=sys.stderr)
        return 2

    antes, depois = len(bruto.splitlines()), len(saida.splitlines())
    reducao = 0 if not antes else round(100 * (1 - depois / antes))
    registrar(args.cmd, filtro.id, antes, depois)
    print(saida)
    for aviso in avisos:
        print(f"[compressao-tool-output] ! {aviso}", file=sys.stderr)
    print(
        f"[compressao-tool-output] filtro={filtro.id} linhas {antes}→{depois} "
        f"(-{reducao}%) veredito={veredito(bruto)}",
        file=sys.stderr,
    )
    return codigo


if __name__ == "__main__":
    sys.exit(main())
