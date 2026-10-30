#!/usr/bin/env python3
"""Scaffolder — gera projeto Maven completo a partir do schema JSON.

Uso:
    python scaffold_lambda.py schema.json -o /target/path \\
        --group com.example --artifact orders-lambda \\
        --base-package com.example.orders

O scaffolder NÃO inventa access patterns. Espera que o schema JSON tenha
o bloco "single_table" populado (gerado interativamente com o usuário, não
pelo dbml_parser puro). Estrutura esperada:

    {
      "domain": "ecommerce",
      "tables": [...],
      "refs": [...],
      "single_table": {
        "table_name": "EcommerceSingleTable",
        "entities": [
          {
            "name": "User",
            "pk_template": "USER#{id}",
            "sk_template": "USER#{id}",
            "type_discriminator": "USER",
            "gsi": {
              "GSI1": {"pk": "EMAIL#{email}", "sk": "USER#{id}"}
            },
            "fields": [
              {"name": "id", "java_type": "String"},
              {"name": "email", "java_type": "String"},
              {"name": "name", "java_type": "String"}
            ]
          },
          ...
        ],
        "gsi_count": 2
      },
      "endpoints": [
        {"method": "GET", "path": "/users/{id}", "handler": "getUser"},
        ...
      ],
      "stream_handlers": [
        {"name": "OrderStreamHandler", "filter_type": "ORDER"}
      ]
    }
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = SCRIPT_DIR.parent / "assets" / "templates"


def render(template: str, ctx: dict[str, Any]) -> str:
    """Substituição minimalista {{ var }} sem dependência externa.

    Suporta:
      {{ key }}                — substituição simples
      {{#each items}} ... {{/each}}  — loop sobre lista, item disponível como {{ . }} ou {{ field }}
      {{#if key}} ... {{/if}}  — condicional truthy
    """
    out = template

    # {{#each xs}}...{{/each}}
    def each_replace(match: re.Match[str]) -> str:
        var = match.group(1).strip()
        body = match.group(2)
        items = ctx.get(var, [])
        result = []
        for item in items:
            sub_ctx = {**ctx}
            if isinstance(item, dict):
                sub_ctx.update(item)
            sub_ctx["."] = item
            result.append(render(body, sub_ctx))
        return "".join(result)

    out = re.sub(r"\{\{#each\s+(\w+)\}\}(.*?)\{\{/each\}\}", each_replace, out, flags=re.DOTALL)

    # {{#if xs}}...{{/if}}
    def if_replace(match: re.Match[str]) -> str:
        var = match.group(1).strip()
        body = match.group(2)
        return body if ctx.get(var) else ""

    out = re.sub(r"\{\{#if\s+(\w+)\}\}(.*?)\{\{/if\}\}", if_replace, out, flags=re.DOTALL)

    # {{ key }} — incluindo nested.path
    def var_replace(match: re.Match[str]) -> str:
        path = match.group(1).strip()
        if path == ".":
            v = ctx.get(".", "")
            return str(v)
        parts = path.split(".")
        v: Any = ctx
        for p in parts:
            if isinstance(v, dict):
                v = v.get(p, "")
            else:
                v = ""
                break
        return str(v) if v is not None else ""

    out = re.sub(r"\{\{\s*([\w.]+)\s*\}\}", var_replace, out)
    return out


def write_file(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def package_to_path(pkg: str) -> str:
    return pkg.replace(".", "/")


def render_template(name: str, ctx: dict[str, Any]) -> str:
    tmpl_path = TEMPLATES_DIR / name
    if not tmpl_path.exists():
        raise FileNotFoundError(f"Template não encontrado: {tmpl_path}")
    return render(tmpl_path.read_text(encoding="utf-8"), ctx)


def build_context(schema: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    domain = schema.get("domain", "app")
    base_pkg = args.base_package or f"{args.group}.{re.sub(r'[^a-z]', '', domain.lower())}"

    single_table = schema.get("single_table", {})
    raw_entities = single_table.get("entities", [])

    # Preprocessa fields:
    # - name_pascal: para getters/setters JavaBeans (id → Id, userId → UserId)
    # - comma: separador entre params do record (vazio no último)
    # - imports: lista de imports java.* necessários (BigDecimal, Instant, ...)
    # O template engine é minimalista (sem {{#if}}{{else}}{{/if}}); este
    # preprocess evita complicar o engine.
    JAVA_TYPE_IMPORTS = {
        "BigDecimal": "java.math.BigDecimal",
        "Instant": "java.time.Instant",
        "LocalDate": "java.time.LocalDate",
        "LocalDateTime": "java.time.LocalDateTime",
        "LocalTime": "java.time.LocalTime",
        "Map<String,Object>": "java.util.Map",
    }
    entities = []
    for ent in raw_entities:
        fields = ent.get("fields", [])
        new_fields = []
        types_used = set()
        for i, f in enumerate(fields):
            f = {**f}
            f["name_pascal"] = f["name"][:1].upper() + f["name"][1:] if f["name"] else f["name"]
            f["comma"] = "" if i == len(fields) - 1 else ","
            types_used.add(f.get("java_type", ""))
            new_fields.append(f)
        imports = sorted({JAVA_TYPE_IMPORTS[t] for t in types_used if t in JAVA_TYPE_IMPORTS})
        entities.append({
            **ent,
            "fields": new_fields,
            "imports": [{"path": p} for p in imports],
        })

    # Agrega imports de todas as entidades para o SingleTableItem (que tem
    # fields wide-row de qualquer tipo do domínio). Garante que o JavaBean
    # gerado compile mesmo quando entidades distintas usam tipos diferentes
    # (ex: Order tem BigDecimal + Instant; User não tem nenhum).
    aggregated_imports = sorted({
        imp["path"] for ent in entities for imp in ent.get("imports", [])
    })

    # Uniao (dedup por nome, preserva ordem) dos fields de todas as entidades:
    # o SingleTableItem e um wide-row e precisa de UM campo por atributo do
    # dominio. Antes, o template iterava {{#each entities}}{{#each fields}}
    # (each aninhado, nao suportado pelo engine) -> Java invalido. Agora o
    # engine recebe uma lista plana e itera uma vez so.
    _seen = set()
    single_table_fields = []
    for ent in entities:
        for f in ent.get("fields", []):
            if f["name"] not in _seen:
                _seen.add(f["name"])
                single_table_fields.append(f)

    return {
        "domain": domain,
        "domain_pascal": "".join(p.capitalize() for p in domain.split("_")),
        "group_id": args.group,
        "artifact_id": args.artifact,
        "version": args.version,
        "base_package": base_pkg,
        "base_package_path": package_to_path(base_pkg),
        "java_version": "25",
        "stack_name": args.stack_name or args.artifact,
        "single_table_name": single_table.get("table_name", f"{args.artifact}-single-table"),
        "gsi_count": single_table.get("gsi_count", 2),
        "entities": entities,
        "single_table_imports": [{"path": p} for p in aggregated_imports],
        "single_table_fields": single_table_fields,
        "endpoints": schema.get("endpoints", []),
        "stream_handlers": schema.get("stream_handlers", []),
        "has_streams": bool(schema.get("stream_handlers")),
        "tables": schema.get("tables", []),
        "refs": schema.get("refs", []),
    }


def scaffold(schema: dict[str, Any], target: Path, args: argparse.Namespace) -> None:
    ctx = build_context(schema, args)
    pkg_path = ctx["base_package_path"]

    # Estrutura de arquivos a gerar — (template_filename, target_relative_path)
    plan: list[tuple[str, str]] = [
        ("pom.xml.tmpl", "pom.xml"),
        ("Makefile.tmpl", "Makefile"),
        ("template.yaml.tmpl", "template.yaml"),
        ("samconfig.toml.tmpl", "samconfig.toml"),
        ("README.md.tmpl", "README.md"),
        ("application.properties.tmpl", "src/main/resources/application.properties"),
        ("log4j2.xml.tmpl", "src/main/resources/log4j2.xml"),
        ("Application.java.tmpl", f"src/main/java/{pkg_path}/Application.java"),
        ("NativeHints.java.tmpl", f"src/main/java/{pkg_path}/config/NativeHints.java"),
        ("DynamoDbConfig.java.tmpl", f"src/main/java/{pkg_path}/config/DynamoDbConfig.java"),
        ("SingleTableItem.java.tmpl", f"src/main/java/{pkg_path}/model/SingleTableItem.java"),
        ("SingleTableRepository.java.tmpl", f"src/main/java/{pkg_path}/repository/SingleTableRepository.java"),
        ("ApiGatewayHandler.java.tmpl", f"src/main/java/{pkg_path}/handler/ApiGatewayHandler.java"),
        ("reflect-config.json.tmpl", f"src/main/resources/META-INF/native-image/{ctx['group_id']}/{ctx['artifact_id']}/reflect-config.json"),
        ("resource-config.json.tmpl", f"src/main/resources/META-INF/native-image/{ctx['group_id']}/{ctx['artifact_id']}/resource-config.json"),
    ]

    if ctx["has_streams"]:
        plan.append(("DynamoDbStreamHandler.java.tmpl", f"src/main/java/{pkg_path}/handler/DynamoDbStreamHandler.java"))

    # Records de entidades — um por entity
    for entity in ctx["entities"]:
        ent_ctx = {**ctx, **entity}
        out_path = target / f"src/main/java/{pkg_path}/model/{entity['name']}.java"
        rendered = render_template("Entity.java.tmpl", ent_ctx)
        write_file(out_path, rendered)

    # Demais arquivos
    for tmpl, rel in plan:
        rendered = render_template(tmpl, ctx)
        write_file(target / rel, rendered)

    # events/ samples para sam local invoke
    samples_dir = target / "events"
    samples_dir.mkdir(parents=True, exist_ok=True)
    write_file(samples_dir / "get-user.json", render_template("event-get-user.json.tmpl", ctx))
    write_file(samples_dir / "create-order.json", render_template("event-create-order.json.tmpl", ctx))
    if ctx["has_streams"]:
        write_file(samples_dir / "dynamodb-stream.json", render_template("event-dynamodb-stream.json.tmpl", ctx))

    print(f"[ok] Projeto gerado em: {target}")
    print(f"     Próximos passos:")
    print(f"       cd {target}")
    print(f"       mvn -Pnative native:compile         # compila binário GraalVM")
    print(f"       sam build --use-container           # build dentro de al2023")
    print(f"       sam deploy --guided                 # primeiro deploy")


def main() -> int:
    ap = argparse.ArgumentParser(description="Scaffolder Lambda Java 25 + Spring Boot 4 + Native + DDB single-table")
    ap.add_argument("schema", help="Caminho do schema JSON (output do dbml_parser + bloco single_table)")
    ap.add_argument("-o", "--output", required=True, help="Diretório de saída do projeto")
    ap.add_argument("--group", default="com.example", help="Maven groupId (default: com.example)")
    ap.add_argument("--artifact", required=True, help="Maven artifactId (kebab-case)")
    ap.add_argument("--version", default="1.0.0-SNAPSHOT", help="Maven version")
    ap.add_argument("--base-package", help="Java base package (default: <group>.<domain>)")
    ap.add_argument("--stack-name", help="CloudFormation stack name (default: artifactId)")
    args = ap.parse_args()

    schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))
    target = Path(args.output).resolve()
    target.mkdir(parents=True, exist_ok=True)

    scaffold(schema, target, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
