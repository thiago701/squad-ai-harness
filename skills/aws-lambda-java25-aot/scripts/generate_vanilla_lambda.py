#!/usr/bin/env python3
"""Generate a hardened **vanilla JVM / SnapStart** Lambda Java 25 project.

Unlike scaffold_lambda.py (Spring/Native, stubs the domain), this generator does
a VERBATIM COPY of a proven blueprint with a uniform identifier rename. Because
the SAME substitutions are applied to main, tests, resources and the OpenAPI
contract, the renamed project stays internally consistent and passes
`./mvnw verify` GREEN on the first build (same tests, same 100% coverage, same
ArchUnit + Checkstyle gates) — the blueprint-reuse lever, proven at ~4.5x.

The output is a hardened STARTING POINT: it carries the blueprint's example
domain fields (title, priority, status, dueDate) under your entity name. Replace
those fields with your DBML and keep the cross-cutting (build, gates, handler,
error mapping, auth, repository, tests). See references/vanilla-jvm-snapstart.md.

Canonical blueprint: the Task Manager demo (`<repo>/app`). Pass --blueprint.

Usage:
    python generate_vanilla_lambda.py \\
        --blueprint ../app \\
        --entity Widget --package com.acme.widget \\
        --table WidgetSingleTable --app-dir ./widget-lambda
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

# Identifiers of the canonical blueprint (the Task Manager demo). The generator
# is paired with that blueprint; if you point --blueprint elsewhere, its source
# identifiers must match these or the rename will be partial.
SRC_PKG_DOT = "com.squadai.taskmanager"
SRC_PKG_PATH = "com/squadai/taskmanager"
SRC_GROUP = "com.squadai"
SRC_TABLE = "TaskManagerSingleTable"
SRC_ENV = "TASKS_TABLE_NAME"
SRC_ARTIFACT = "task-manager-lambda"
SRC_FUNCTION = "task-manager"
SRC_PROJECT_TITLE = "Task Manager"
SRC_PROJECT_PASCAL = "TaskManager"
SRC_ENTITY_PASCAL = "Task"
SRC_ENTITY_PLURAL = "tasks"
SRC_ENTITY_LOWER = "task"

# Files/dirs that never belong in a generated project.
SKIP_DIRS = {"target", ".aws-sam", ".git", ".idea", ".vscode"}
SKIP_SUFFIXES = {".log", ".iml", ".class", ".exec"}


def build_replacements(entity: str, package: str, table: str, function: str) -> list[tuple[str, str]]:
    entity_lower = entity[0].lower() + entity[1:]
    entity_plural = entity_lower + "s"
    env_var = entity_plural.upper() + "_TABLE_NAME"
    group = package.rsplit(".", 1)[0] if "." in package else package
    artifact = function + "-lambda"
    pkg_path = package.replace(".", "/")
    # ORDER MATTERS: longest / most-specific first so a later rule never clobbers
    # a substring a former rule already rewrote.
    return [
        (SRC_PKG_DOT, package),
        (SRC_PKG_PATH, pkg_path),
        (SRC_GROUP, group),
        (SRC_TABLE, table),
        (SRC_ENV, env_var),
        (SRC_ARTIFACT, artifact),
        (SRC_FUNCTION, function),
        (SRC_PROJECT_TITLE, entity),
        (SRC_PROJECT_PASCAL, entity),
        (SRC_ENTITY_PASCAL, entity),
        (SRC_ENTITY_PLURAL, entity_plural),
        (SRC_ENTITY_LOWER, entity_lower),
    ]


def apply(text: str, replacements: list[tuple[str, str]]) -> str:
    for find, repl in replacements:
        text = text.replace(find, repl)
    return text


def should_skip(rel_parts: tuple[str, ...], name: str) -> bool:
    if any(part in SKIP_DIRS for part in rel_parts):
        return True
    return Path(name).suffix in SKIP_SUFFIXES


def generate(blueprint: Path, app_dir: Path, replacements: list[tuple[str, str]]) -> dict:
    if app_dir.exists():
        raise SystemExit(f"--app-dir already exists: {app_dir}")
    stats = {"files": 0, "binary": 0}
    for src in sorted(blueprint.rglob("*")):
        if src.is_dir():
            continue
        rel = src.relative_to(blueprint)
        if should_skip(rel.parts[:-1], rel.name):
            continue
        target_rel = apply(rel.as_posix(), replacements)
        dest = app_dir / target_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            text = src.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            shutil.copy2(src, dest)
            stats["binary"] += 1
            continue
        dest.write_text(apply(text, replacements), encoding="utf-8")
        stats["files"] += 1
    return stats


def apply_domain_spec(app_dir: Path, spec_path: Path, package: str, entity: str) -> None:
    """Após o rename verbatim, gera os value objects + Item/Mapper do domínio REAL a
    partir da domain-spec, substituindo os campos de exemplo do blueprint. Roda os
    dois geradores irmãos (value_objects.py + single_table_mapper.py) num só comando."""
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    import value_objects
    import single_table_mapper

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    agg_name = spec.get("aggregate", {}).get("name")
    if agg_name and agg_name != entity:
        print(f"  domain-spec: AVISO — o agregado da spec ('{agg_name}') difere de --entity "
              f"('{entity}'). A spec manda no domínio; confirme se é intencional (o rename do "
              "blueprint usa --entity; os tipos de domínio vêm da spec).")
    # O domínio do blueprint renomeado é <package>.domain — alinha a spec a ele para
    # os VOs caírem no pacote certo, independentemente do que o arquivo declara.
    spec["package"] = package + ".domain"
    src_root = app_dir / "src" / "main" / "java"

    vo_res = value_objects.generate(spec, src_root, with_aggregate=bool(spec.get("aggregate")), emit_base=False)
    print(f"  domain-spec: {len(spec.get('value_objects', []))} value objects em {vo_res['model_pkg']}")
    if spec.get("single_table") and spec.get("aggregate"):
        st_res = single_table_mapper.generate(spec, src_root)
        print(f"  domain-spec: {st_res['item']} + {st_res['mapper']} em {st_res['infra_pkg']}")
    print("  domain-spec: APAGUE os value objects/DTOs de exemplo do blueprint que sobraram")
    print("               e ligue o repository/handler aos novos tipos; então ./mvnw verify.")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate a hardened vanilla JVM / SnapStart Lambda Java 25 project."
    )
    parser.add_argument("--blueprint", required=True, help="Proven blueprint root (the demo app/)")
    parser.add_argument("--entity", required=True, help="Aggregate name, PascalCase, e.g. Widget")
    parser.add_argument("--package", required=True, help="Base package, e.g. com.acme.widget")
    parser.add_argument("--table", required=True, help="Single-table name, e.g. WidgetSingleTable")
    parser.add_argument("--name", default=None, help="Kebab project/function name (default: entity lowercased)")
    parser.add_argument("--app-dir", required=True, help="Destination directory (must not exist)")
    parser.add_argument("--domain-spec", default=None,
                        help="domain-spec JSON: gera VOs + Item/Mapper do domínio real após o rename (1 comando)")
    args = parser.parse_args(argv)

    blueprint = Path(args.blueprint).resolve()
    if not (blueprint / "pom.xml").exists():
        raise SystemExit(f"blueprint missing pom.xml: {blueprint}")

    function = args.name or (args.entity[0].lower() + args.entity[1:])
    replacements = build_replacements(args.entity, args.package, args.table, function)
    app_dir = Path(args.app_dir).resolve()

    print(f"Generating {args.entity} -> {app_dir}")
    print(f"  package={args.package} table={args.table} function={function} blueprint={blueprint}")
    stats = generate(blueprint, app_dir, replacements)
    print(f"Done: {stats['files']} files rewritten, {stats['binary']} copied verbatim.")
    if args.domain_spec:
        print("Applying domain-spec (value objects + Item/Mapper)...")
        apply_domain_spec(app_dir, Path(args.domain_spec).resolve(), args.package, args.entity)
    else:
        print("Next: cd into the project and run `./mvnw verify` (expected GREEN), then")
        print("replace the example domain fields with yours (see references/domain-spec.md")
        print("to generate them from a spec with scripts/value_objects.py).")


if __name__ == "__main__":
    main()
