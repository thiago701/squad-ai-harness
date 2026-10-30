#!/usr/bin/env python3
"""Gera um projeto de chatbot comercial multi-tenant a partir da skill.

A skill é o gerador; o produto é o que sai daqui. Nada é gerado por string
concatenada: os arquivos vivem em `assets/projeto/` como código real e são
copiados com substituição de placeholders.

Uso:
    python scripts/scaffold.py --destino ../pousada-serra-viva \\
        --nome pousada-serra-viva --tenant serra-viva --vertical pousada \\
        --estabelecimento "Pousada Serra Viva" --canais whatsapp,web --porta 8080

    # levando o n7-ai-core junto (para `docker compose build` funcionar offline)
    python scripts/scaffold.py --destino ../cliente --n7-core ../n7-ai-core
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
ASSETS = SKILL / "assets"
MODELO = ASSETS / "projeto"

TEXTUAIS = {".py", ".toml", ".md", ".yml", ".yaml", ".json", ".html", ".txt", ".example", ""}
IGNORAR = {"__pycache__", ".pytest_cache", ".ruff_cache", "var", ".git"}


def renderizar(texto: str, valores: dict[str, str]) -> str:
    for chave, valor in valores.items():
        texto = texto.replace("{{" + chave + "}}", valor)
    return texto


def copiar_arvore(origem: Path, destino: Path, valores: dict[str, str]) -> int:
    total = 0
    for item in sorted(origem.rglob("*")):
        if any(parte in IGNORAR for parte in item.parts):
            continue
        alvo = destino / item.relative_to(origem)
        if item.is_dir():
            alvo.mkdir(parents=True, exist_ok=True)
            continue
        alvo.parent.mkdir(parents=True, exist_ok=True)
        if item.suffix.lower() in TEXTUAIS:
            alvo.write_text(
                renderizar(item.read_text(encoding="utf-8"), valores), encoding="utf-8"
            )
        else:
            shutil.copy2(item, alvo)
        total += 1
    return total


def rotulo_do_vertical(destino: Path, vertical: str) -> str:
    pack = destino / "verticais" / f"{vertical}.json"
    if pack.exists():
        return json.loads(pack.read_text(encoding="utf-8")).get("rotulo", vertical)
    return vertical


def verificar_vertical(vertical: str) -> None:
    pack = MODELO / "verticais" / f"{vertical}.json"
    if pack.exists():
        return
    disponiveis = sorted(p.stem for p in (MODELO / "verticais").glob("*.json"))
    raise SystemExit(
        f"vertical '{vertical}' não tem pack em assets/projeto/verticais/.\n"
        f"Disponíveis: {', '.join(disponiveis)}.\n"
        "Para criar um novo: adicione o .json, os documentos em dados/<vertical>/, "
        "o golden set em golden/<vertical>.json e a seção em references/verticais.md."
    )


def main() -> int:
    p = argparse.ArgumentParser(description="scaffold de chatbot comercial")
    p.add_argument("--destino", type=Path, required=True)
    p.add_argument("--nome", default="", help="nome do projeto (default: nome da pasta)")
    p.add_argument("--tenant", default="")
    p.add_argument("--vertical", default="pousada")
    p.add_argument("--estabelecimento", default="")
    p.add_argument("--canais", default="whatsapp,web")
    p.add_argument("--porta", default="8080")
    p.add_argument("--volume", default="até 1k conversas/mês por tenant")
    p.add_argument("--n7-core", type=Path, help="caminho do n7-ai-core para vendorizar")
    p.add_argument("--forcar", action="store_true", help="sobrescreve destino existente")
    a = p.parse_args()

    verificar_vertical(a.vertical)

    destino = a.destino.resolve()
    if destino.exists() and any(destino.iterdir()) and not a.forcar:
        raise SystemExit(f"{destino} já existe e não está vazio. Use --forcar.")
    destino.mkdir(parents=True, exist_ok=True)

    nome = a.nome or destino.name
    estabelecimento = a.estabelecimento or nome.replace("-", " ").title()
    valores = {
        "PROJETO": nome,
        "TENANT": a.tenant or nome,
        "VERTICAL": a.vertical,
        "VERTICAL_ROTULO": rotulo_do_vertical(MODELO, a.vertical),
        "ESTABELECIMENTO": estabelecimento,
        "CANAIS": a.canais,
        "PORTA": str(a.porta),
        "VOLUME": a.volume,
    }

    arquivos = copiar_arvore(MODELO, destino, valores)

    pasta_scripts = destino / "scripts"
    pasta_scripts.mkdir(exist_ok=True)
    for script in ("seed_rag.py", "eval_rag.py"):
        shutil.copy2(SKILL / "scripts" / script, pasta_scripts / script)
        (pasta_scripts / script).chmod(0o755)
        arquivos += 1

    readme = renderizar((ASSETS / "README.md.tmpl").read_text(encoding="utf-8"), valores)
    (destino / "README.md").write_text(readme, encoding="utf-8")

    exemplo = destino / ".env.example"
    if exemplo.exists() and not (destino / ".env").exists():
        shutil.copy2(exemplo, destino / ".env")

    (destino / ".gitignore").write_text(
        "\n".join([
            "var/", "*.db", "*.db-wal", "*.db-shm", ".env",
            "__pycache__/", ".pytest_cache/", ".ruff_cache/", ".coverage",
            "htmlcov/", "vendor/", "golden/relatorio.json",
        ]) + "\n",
        encoding="utf-8",
    )
    (destino / "docs" / "adr").mkdir(parents=True, exist_ok=True)
    (destino / "docs" / "adr" / "README.md").write_text(
        "# ADRs\n\nMonólito modular é o default. Quebrar um módulo em serviço próprio\n"
        "exige um ADR aqui, com o número que justifica a separação.\n",
        encoding="utf-8",
    )

    vendor = destino / "vendor"
    vendor.mkdir(exist_ok=True)
    (vendor / "README.md").write_text(
        "# vendor\n\n"
        "`docker compose build` procura `vendor/n7-ai-core` aqui. Gere com:\n\n"
        "    python scripts/scaffold.py --destino . --forcar --n7-core ../n7-ai-core\n\n"
        "Sem isso, o Dockerfile cai para `pip install n7-ai-core` (exige índice privado).\n",
        encoding="utf-8",
    )

    if a.n7_core:
        origem = a.n7_core.resolve()
        if not (origem / "pyproject.toml").exists():
            raise SystemExit(f"{origem} não parece o n7-ai-core (sem pyproject.toml).")
        alvo = vendor / "n7-ai-core"
        shutil.rmtree(alvo, ignore_errors=True)
        shutil.copytree(
            origem, alvo,
            ignore=shutil.ignore_patterns(*IGNORAR, "*.pyc", ".coverage", "tests"),
        )

    print(f"projeto gerado em {destino} ({arquivos} arquivos)")
    print(f"  vertical.....: {valores['VERTICAL_ROTULO']} ({a.vertical})")
    print(f"  tenant.......: {valores['TENANT']}")
    print(f"  canais.......: {a.canais}")
    print("\npróximos passos:")
    print(f"  cd {destino}")
    print("  make instalar && make up")
    print("  make eval      # publica a taxa de acerto no README")
    return 0


if __name__ == "__main__":
    sys.exit(main())
