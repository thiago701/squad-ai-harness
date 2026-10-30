#!/usr/bin/env python3
"""Ingestão inicial / reindexação da base de conhecimento.

Roda incremental por default: só reprocessa arquivo cujo conteúdo mudou
(sha256 por fonte). `--forcar` reindexa tudo.

Uso:
    python scripts/seed_rag.py
    python scripts/seed_rag.py --forcar
    python scripts/seed_rag.py --de /caminho/para/arquivos   # copia e indexa
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.config import Config  # noqa: E402
from app.conhecimento import EXTENSOES, baixar_site  # noqa: E402
from app.servico import Servico  # noqa: E402


def _slug(url: str) -> str:
    from urllib.parse import urlparse

    partes = urlparse(url)
    bruto = f"{partes.netloc}{partes.path}".strip("/")
    limpo = re.sub(r"[^a-zA-Z0-9]+", "-", bruto).strip("-").lower()
    return limpo or "site"


def importar(origem: Path, destino: Path) -> list[str]:
    destino.mkdir(parents=True, exist_ok=True)
    copiados = []
    candidatos = [origem] if origem.is_file() else sorted(origem.rglob("*"))
    for arquivo in candidatos:
        if arquivo.is_file() and arquivo.suffix.lower() in EXTENSOES:
            shutil.copy2(arquivo, destino / arquivo.name)
            copiados.append(arquivo.name)
    return copiados


def main() -> int:
    analisador = argparse.ArgumentParser(description="indexa a base de conhecimento")
    analisador.add_argument("--forcar", action="store_true", help="reindexa tudo")
    analisador.add_argument(
        "--de", type=Path, help="arquivo ou pasta a importar antes de indexar"
    )
    analisador.add_argument(
        "--url", action="append", default=[],
        help="página do cliente a baixar e indexar (repetível)",
    )
    analisador.add_argument(
        "--nome-fonte", default="",
        help="nome da fonte citada na resposta ao usar --url (default: host+caminho)",
    )
    argumentos = analisador.parse_args()

    config = Config.do_ambiente()
    for url in argumentos.url:
        try:
            texto = baixar_site(url)
        except Exception as exc:
            print(f"falhou baixar {url}: {exc}")
            return 2
        if not texto.strip():
            print(f"{url}: página sem texto (provavelmente renderizada por JavaScript).")
            return 2
        destino = config.dados_do_vertical / f"{argumentos.nome_fonte or _slug(url)}.md"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(f"<!-- origem: {url} -->\n\n{texto}\n", encoding="utf-8")
        print(f"baixado {url} → {destino.name} ({len(texto)} chars)")

    if argumentos.de:
        if not argumentos.de.exists():
            print(f"origem não encontrada: {argumentos.de}")
            return 2
        copiados = importar(argumentos.de, config.dados_do_vertical)
        print(f"importados {len(copiados)} arquivo(s): {', '.join(copiados) or '—'}")

    servico = Servico.montar(config)
    try:
        relatorio = servico.reindexar(forcar=argumentos.forcar)
    finally:
        servico.conexao.close()

    print(f"novas.........: {', '.join(relatorio['novas']) or '—'}")
    print(f"atualizadas...: {', '.join(relatorio['atualizadas']) or '—'}")
    print(f"inalteradas...: {', '.join(relatorio['inalteradas']) or '—'}")
    print(f"trechos.......: {relatorio['total_chunks']}")
    if relatorio["erros"]:
        print("\nerros:")
        for erro in relatorio["erros"]:
            print(f"  - {erro}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
