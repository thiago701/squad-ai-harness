#!/usr/bin/env python3
"""DBML parser — transforma um schema DBML em modelo intermediário JSON.

Uso:
    python dbml_parser.py <schema.dbml>           # imprime JSON em stdout
    python dbml_parser.py <schema.dbml> -o out.json

O modelo intermediário tem este formato:

    {
      "domain": "ecommerce",                    # nome inferido (ou via --domain)
      "tables": [
        {
          "name": "users",
          "entity": "User",                      # singular PascalCase
          "columns": [
            {"name": "id", "java_type": "String", "pk": true, "unique": true, "nullable": false},
            {"name": "email", "java_type": "String", "unique": true, "nullable": false},
            ...
          ],
          "indexes": [
            {"columns": ["email"], "unique": true}
          ]
        },
        ...
      ],
      "refs": [
        {"from": {"table": "orders", "column": "user_id"},
         "to":   {"table": "users",  "column": "id"},
         "cardinality": "many-to-one"}
      ]
    }

Suporta:
- Tabelas e colunas com tipos
- Modificadores: [pk], [primary key], [unique], [not null], [increment], [default: ...]
- Refs inline: [ref: > users.id]
- Refs explícitos: Ref: orders.user_id > users.id
- Indexes block: Indexes { (col1, col2) [unique] }
- Comentários // e /* ... */
- Project name (vira o domain)

Não suporta (out of scope, mas avisa):
- Composite primary keys com `Indexes { (a, b) [pk] }` — apenas single PK
- Enums DBML
- Notas/Project meta diferentes do nome
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SQL_TO_JAVA = {
    "varchar": "String", "char": "String", "text": "String", "string": "String",
    "uuid": "String", "char(36)": "String",
    "int": "Integer", "integer": "Integer",
    "bigint": "Long", "long": "Long",
    "smallint": "Short",
    "decimal": "BigDecimal", "numeric": "BigDecimal", "money": "BigDecimal",
    "float": "Double", "double": "Double", "real": "Double",
    "boolean": "Boolean", "bool": "Boolean",
    "timestamp": "Instant", "datetime": "Instant", "timestamptz": "Instant",
    "date": "LocalDate",
    "time": "LocalTime",
    "json": "Map<String,Object>", "jsonb": "Map<String,Object>",
    "binary": "byte[]", "blob": "byte[]", "bytea": "byte[]",
}


def strip_comments(src: str) -> str:
    """Remove comentários // e /* ... */ preservando linhas para erro de parse."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    src = re.sub(r"//[^\n]*", "", src)
    return src


def to_pascal_case(snake: str) -> str:
    """users → User, order_items → OrderItem, line_item → LineItem."""
    base = snake.rstrip("s") if snake.endswith("s") and not snake.endswith("ss") else snake
    return "".join(p.capitalize() for p in base.split("_"))


def java_type_for(sql_type: str) -> str:
    base = re.sub(r"\(.*?\)", "", sql_type).strip().lower()
    return SQL_TO_JAVA.get(base, "String")


def parse_modifiers(mod_block: str) -> dict[str, Any]:
    """Parse o conteúdo entre [...] de uma coluna.

    Exemplo: '[pk, not null, ref: > users.id]'
    Retorna: {'pk': True, 'nullable': False, 'ref': {'op': '>', 'table': 'users', 'column': 'id'}}
    """
    result: dict[str, Any] = {}
    if not mod_block:
        return result
    inner = mod_block.strip().strip("[]").strip()
    parts = split_modifiers(inner)
    for part in parts:
        p = part.strip()
        low = p.lower()
        if low in ("pk", "primary key"):
            result["pk"] = True
        elif low == "unique":
            result["unique"] = True
        elif low == "not null":
            result["nullable"] = False
        elif low == "increment":
            result["increment"] = True
        elif low.startswith("ref:"):
            m = re.match(r"ref:\s*([<>\-])\s*(\w+)\.(\w+)", p, re.IGNORECASE)
            if m:
                result["ref"] = {"op": m.group(1), "table": m.group(2), "column": m.group(3)}
        elif low.startswith("default:"):
            result["default"] = p.split(":", 1)[1].strip().strip("'\"")
        elif low.startswith("note:"):
            result["note"] = p.split(":", 1)[1].strip().strip("'\"")
    return result


def split_modifiers(s: str) -> list[str]:
    """Split por vírgula respeitando colchetes e quotes."""
    parts, buf, depth, in_quote = [], [], 0, None
    for ch in s:
        if in_quote:
            buf.append(ch)
            if ch == in_quote:
                in_quote = None
        elif ch in ("'", '"'):
            in_quote = ch
            buf.append(ch)
        elif ch == "[":
            depth += 1
            buf.append(ch)
        elif ch == "]":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return parts


def parse_table(block: str) -> dict[str, Any]:
    """Parse o body de 'Table foo { ... }' (sem o header)."""
    columns = []
    indexes = []
    in_indexes = False
    indexes_buf: list[str] = []

    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.lower().startswith("indexes"):
            in_indexes = True
            continue
        if in_indexes:
            if line == "}":
                in_indexes = False
                continue
            if line == "{":
                continue
            indexes.append(parse_index_line(line))
            continue

        # Linha de coluna: "name type [modifiers]"
        m = re.match(r"(\w+)\s+([\w()]+)(?:\s+(\[.*\]))?", line)
        if not m:
            continue
        name, sql_type, mods = m.group(1), m.group(2), m.group(3) or ""
        modifiers = parse_modifiers(mods)
        columns.append({
            "name": name,
            "sql_type": sql_type,
            "java_type": java_type_for(sql_type),
            "pk": modifiers.get("pk", False),
            "unique": modifiers.get("unique", False),
            "nullable": modifiers.get("nullable", True),
            "increment": modifiers.get("increment", False),
            "default": modifiers.get("default"),
            "note": modifiers.get("note"),
            "ref": modifiers.get("ref"),
        })

    return {"columns": columns, "indexes": indexes}


def parse_index_line(line: str) -> dict[str, Any]:
    """Parse 'email [unique]' ou '(user_id, created_at)' ou '(a, b) [unique]'."""
    m = re.match(r"\(([^)]+)\)\s*(\[.*\])?", line)
    if m:
        cols = [c.strip() for c in m.group(1).split(",")]
        mods = parse_modifiers(m.group(2) or "")
    else:
        m = re.match(r"(\w+)\s*(\[.*\])?", line)
        cols = [m.group(1)] if m else []
        mods = parse_modifiers(m.group(2) or "")
    return {"columns": cols, "unique": mods.get("unique", False)}


def cardinality_from_op(op: str) -> str:
    """DBML ops: > (many-to-one), < (one-to-many), - (one-to-one), <> (many-to-many)."""
    return {">": "many-to-one", "<": "one-to-many", "-": "one-to-one", "<>": "many-to-many"}.get(op, "many-to-one")


def parse_dbml(source: str) -> dict[str, Any]:
    src = strip_comments(source)
    domain: str | None = None
    tables: dict[str, dict[str, Any]] = {}
    refs: list[dict[str, Any]] = []

    # Project name → domain
    proj_match = re.search(r"Project\s+(\w+)\s*\{", src)
    if proj_match:
        domain = proj_match.group(1)

    # Tables — encontra cada bloco Table foo { ... }
    table_pattern = re.compile(r"Table\s+(\w+)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}", re.DOTALL)
    for m in table_pattern.finditer(src):
        tname = m.group(1)
        body = m.group(2)
        parsed = parse_table(body)
        tables[tname] = {
            "name": tname,
            "entity": to_pascal_case(tname),
            "columns": parsed["columns"],
            "indexes": parsed["indexes"],
        }

    # Refs inline (em modificadores de colunas)
    for tname, t in tables.items():
        for col in t["columns"]:
            ref = col.get("ref")
            if ref:
                refs.append({
                    "from": {"table": tname, "column": col["name"]},
                    "to": {"table": ref["table"], "column": ref["column"]},
                    "cardinality": cardinality_from_op(ref["op"]),
                })

    # Refs explícitos: Ref: from > to
    for m in re.finditer(r"Ref(?:\s+\w+)?:\s*(\w+)\.(\w+)\s*([<>\-]+)\s*(\w+)\.(\w+)", src):
        refs.append({
            "from": {"table": m.group(1), "column": m.group(2)},
            "to": {"table": m.group(4), "column": m.group(5)},
            "cardinality": cardinality_from_op(m.group(3)),
        })

    return {
        "domain": domain or "app",
        "tables": list(tables.values()),
        "refs": refs,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="DBML → JSON intermediário")
    ap.add_argument("input", help="Caminho para o arquivo .dbml (ou - para stdin)")
    ap.add_argument("-o", "--output", help="Caminho do JSON de saída (default: stdout)")
    ap.add_argument("--domain", help="Sobrescreve nome do domínio")
    args = ap.parse_args()

    if args.input == "-":
        src = sys.stdin.read()
    else:
        src = Path(args.input).read_text(encoding="utf-8")

    schema = parse_dbml(src)
    if args.domain:
        schema["domain"] = args.domain

    out = json.dumps(schema, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(out + "\n", encoding="utf-8")
        print(f"[ok] {len(schema['tables'])} tabelas, {len(schema['refs'])} refs → {args.output}", file=sys.stderr)
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
