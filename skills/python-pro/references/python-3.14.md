# Python 3.14 — fatos de versão (verificado jul/2026)

> Fonte: docs.python.org/3/whatsnew/3.14 · python.org/downloads · blog.python.org.
> Absorvido pelo Skill Harvester em 2026-07-15. Revalidar a cada patch.

## Linha do tempo / suporte

| Release | Data | Situação (jul/2026) |
|---|---|---|
| 3.14 | 2025-10-07 | **Estável atual.** Último patch **3.14.6** (2026-06-10) |
| 3.13 | 2024-10 | Bugfix; patch 3.13.12 (fev/2026) |
| 3.12 | 2023-10 | Security-only em breve |

Cadência: uma minor/ano (out). Cada minor tem ~2 anos de bugfix + ~3 de security (5 no total).

## Recursos-chave

- **PEP 779 — Free-threaded oficial.** Build sem GIL saiu de experimental para **oficialmente
  suportado**. Ainda é um **build separado** (não o default). Habilita paralelismo real CPU-bound.
  Caveat: código/lib que assumia atomicidade do GIL pode ter corrida.
- **PEP 750 — Template strings (t-strings).** `t"..."` retorna `string.templatelib.Template`, não `str`.
  Permite processamento seguro (SQL/HTML/shell) interceptando interpolações antes de virar texto.
- **PEP 649/749 — Deferred annotations.** Anotações avaliadas preguiçosamente via `__annotate__`.
  Use `annotationlib` / `inspect.get_annotations(...)`. Reduz necessidade de `from __future__ import annotations`.
- **PEP 734 — Multiple interpreters na stdlib** (`concurrent.interpreters`): isolamento por interpretador,
  concorrência sem overhead de processo.
- **`compression.zstd`** (Zstandard na stdlib). REPL com **syntax highlighting**. Cores em CLIs
  (`unittest`, `argparse`, `json`, `calendar`). Introspecção de asyncio melhorada.
- **JIT experimental** nos binários oficiais macOS/Windows (off por padrão). Ganho geomean ~3–5% no pyperformance.

## Armadilhas / migração

- **Free-threaded não é grátis:** só troque se medir ganho e todas as libs C forem thread-safe. Muitas
  wheels ainda não publicam variante `cp314t`.
- **Deferred annotations** muda quem lê `__annotations__` diretamente — migre para `annotationlib`.
  Frameworks que inspecionam hints (pydantic, dataclasses) já se adaptaram; libs próprias podem quebrar.
- **t-strings ≠ f-strings:** `t"..."` NÃO é `str`; passar direto onde se espera texto falha. É recurso
  de biblioteca (o processador decide o resultado).

## Ferramentas do ecossistema (2026)

- Ambiente/packaging: **uv** (resolver+lock+run, muito rápido), `pyproject.toml` como fonte única.
- Lint+format: **ruff** (substitui flake8/black/isort). Tipos: **mypy** / **pyright** (`--strict`).
- Teste: **pytest** (+ pytest-asyncio, hypothesis, coverage). Fake time: time-machine/freezegun.
- Web: **FastAPI** (async), **Litestar**; ASGI (uvicorn/hypercorn). Segurança: `pip-audit`, lockfiles.
