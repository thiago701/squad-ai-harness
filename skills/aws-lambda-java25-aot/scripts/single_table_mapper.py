#!/usr/bin/env python3
"""Gera o Item (@DynamoDbBean) + ItemMapper single-table a partir da domain-spec.

Segundo pedaço manual do caso `calendario-lambda`: depois dos value objects, ainda
se escreve à mão o `PagamentoItem` (bean flat com anotações do Enhanced Client) e o
`PagamentoItemMapper` (construção de chave PK/SK/GSI + toItem/toDomain). Este gerador
emite ambos a partir do bloco `single_table` da spec — reusa os arquétipos de VO já
declarados em `value_objects` para saber como cada campo serializa para coluna(s).

Uso:
    python single_table_mapper.py domain-spec.json -o <project>/src/main/java

Bloco `single_table` da spec (ver examples/calendario-domain.json):

    "single_table": {
      "table_name": "calendario_pagamentos",
      "type_discriminator": "PAGAMENTO",
      "pk": "{pais}#{escopo}#{id}",
      "sk": {"field": "data", "attribute": "DATA"},
      "gsi": {"name": "GSI1", "pk_attribute": "GSI1PK", "pk": "{pais}#{escopo}"},
      "columns": {
        "id": "ID", "pais": "PAIS", "escopo": "ESCOPO",
        "horario": {"inicio": "HoraInicio", "fim": "HoraFim"},
        "descricao": "Descricao"
      }
    }

Requer também o bloco `aggregate` (a ordem dos campos vem dele) e `value_objects`
(os kinds). O GSI reaproveita a SK base (DATA) como sort key do índice.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


HEADER = "/// Gerado por scripts/single_table_mapper.py a partir da domain-spec.\n/// Regenere a partir da spec — evite editar a mao."


def pascal(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def lower_camel(s: str) -> str:
    return s[:1].lower() + s[1:] if s else s


def split_typed(entry: str) -> tuple[str, str]:
    parts = entry.split()
    if len(parts) != 2:
        raise SystemExit(f"[erro] entrada de agregado invalida: '{entry}' (use 'Tipo nome').")
    return parts[0], parts[1]


def column_java_type(kind: str) -> str:
    return "Integer" if kind == "integer_range" else "String"


# --------------------------------------------------------------------------- #
# Serializacao por arquetipo                                                    #
# --------------------------------------------------------------------------- #

def key_expr(kind: str, param: str) -> str | None:
    """Forma-string do VO num componente de chave composta (param = variavel do VO)."""
    return {
        "string_pattern": f"{param}.value()",
        "bounded_string": f"{param}.value()",
        "identifier": f"{param}.value()",
        "enum": f"{param}.name()",
        "local_date": f"{param}.asKey()",
        "local_time": f"{param}.asText()",
        "instant": f"{param}.asKey()",
        "integer_range": f"String.valueOf({param}.value())",
        "decimal": f"{param}.value().toString()",
    }.get(kind)  # time_range -> None (nao serve como componente de chave)


def write_stmts(kind: str, getter: str, field: str, col: Any, vo: dict[str, Any]) -> list[str]:
    """Statements que setam a(s) coluna(s) do item a partir do campo do agregado."""
    if kind in ("string_pattern", "bounded_string", "identifier"):
        return [f"item.set{pascal(field)}({getter}.value());"]
    if kind == "enum":
        return [f"item.set{pascal(field)}({getter}.name());"]
    if kind in ("local_date", "instant"):
        return [f"item.set{pascal(field)}({getter}.asKey());"]
    if kind == "local_time":
        return [f"item.set{pascal(field)}({getter}.asText());"]
    if kind == "integer_range":
        return [f"item.set{pascal(field)}({getter}.value());"]
    if kind == "decimal":
        return [f"item.set{pascal(field)}({getter}.value().toString());"]
    if kind == "time_range":
        start = vo.get("start", "inicio")
        end = vo.get("end", "fim")
        prop_i = lower_camel(col["inicio"])
        prop_f = lower_camel(col["fim"])
        return [f"item.set{pascal(prop_i)}({getter}.{start}AsText());",
                f"item.set{pascal(prop_f)}({getter}.{end}AsText());"]
    raise SystemExit(f"[erro] arquetipo sem mapping de persistencia: {kind}")


def read_expr(kind: str, vo_type: str, field: str, col: Any) -> str:
    """Expressao que reconstroi o VO a partir da(s) coluna(s) do item."""
    getter = f"item.get{pascal(field)}()"
    if kind in ("string_pattern", "bounded_string", "identifier", "integer_range"):
        return f"{vo_type}.of({getter})"
    if kind in ("enum", "local_date", "local_time", "instant", "decimal"):
        return f"{vo_type}.parse({getter})"
    if kind == "time_range":
        gi = f"item.get{pascal(lower_camel(col['inicio']))}()"
        gf = f"item.get{pascal(lower_camel(col['fim']))}()"
        return f"{vo_type}.parse({gi}, {gf})"
    raise SystemExit(f"[erro] arquetipo sem read de persistencia: {kind}")


# --------------------------------------------------------------------------- #
# Modelo de colunas do bean                                                     #
# --------------------------------------------------------------------------- #

def bean_columns(spec: dict[str, Any], type_map: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Lista ordenada de colunas do @DynamoDbBean (prop, attribute, jtype, annotations)."""
    st = spec["single_table"]
    sort_field = st["sk"]["field"]
    sort_attr = st["sk"]["attribute"]
    gsi = st["gsi"]
    gsi_name = gsi["name"]
    gsi_pk_attr = gsi.get("pk_attribute", "GSI1PK")
    columns = st.get("columns", {})

    cols: list[dict[str, Any]] = []
    # 1. PK
    cols.append({"prop": "pk", "attribute": "PK", "jtype": "String",
                 "ann": ["@DynamoDbPartitionKey"]})
    # 2. Sort field (SK base + SK do GSI reaproveitada)
    cols.append({"prop": sort_field, "attribute": sort_attr, "jtype": "String",
                 "ann": ["@DynamoDbSortKey", f"@DynamoDbSecondarySortKey(indexNames = {gsi_name}_NAME)"]})
    # 3. GSI PK
    cols.append({"prop": lower_camel(gsi_pk_attr), "attribute": gsi_pk_attr, "jtype": "String",
                 "ann": [f"@DynamoDbSecondaryPartitionKey(indexNames = {gsi_name}_NAME)"]})
    # 4. type discriminator
    cols.append({"prop": "type", "attribute": "_type", "jtype": "String", "ann": []})

    agg = spec["aggregate"]
    fields = [split_typed(e) for e in agg.get("identity", [])]
    if agg.get("sort"):
        fields.append(split_typed(agg["sort"]))
    fields += [split_typed(e) for e in agg.get("mutable", [])]

    for ftype, fname in fields:
        if fname == sort_field:
            continue  # ja modelado como SK
        vo = type_map.get(ftype, {})
        kind = vo.get("kind")
        col = columns.get(fname)
        if col is None:
            raise SystemExit(f"[erro] single_table.columns nao mapeia o campo '{fname}'.")
        if kind == "time_range":
            for side in ("inicio", "fim"):
                attr = col[side]
                cols.append({"prop": lower_camel(attr), "attribute": attr, "jtype": "String", "ann": []})
        else:
            cols.append({"prop": fname, "attribute": col, "jtype": column_java_type(kind), "ann": []})

    if agg.get("timestamps", True):
        cols.append({"prop": "createdAt", "attribute": "createdAt", "jtype": "String", "ann": []})
        cols.append({"prop": "updatedAt", "attribute": "updatedAt", "jtype": "String", "ann": []})
    if agg.get("version", True):
        cols.append({"prop": "version", "attribute": "version", "jtype": "Long",
                     "ann": ["@DynamoDbVersionAttribute"]})
    return cols


# --------------------------------------------------------------------------- #
# Emissao do bean                                                               #
# --------------------------------------------------------------------------- #

def emit_item_bean(spec: dict[str, Any], infra_pkg: str, item_name: str,
                   type_map: dict[str, dict[str, Any]]) -> str:
    st = spec["single_table"]
    gsi_name = st["gsi"]["name"]
    cols = bean_columns(spec, type_map)

    imports = [
        "import software.amazon.awssdk.enhanced.dynamodb.extensions.annotations.DynamoDbVersionAttribute;",
        "import software.amazon.awssdk.enhanced.dynamodb.mapper.annotations.DynamoDbAttribute;",
        "import software.amazon.awssdk.enhanced.dynamodb.mapper.annotations.DynamoDbBean;",
        "import software.amazon.awssdk.enhanced.dynamodb.mapper.annotations.DynamoDbPartitionKey;",
        "import software.amazon.awssdk.enhanced.dynamodb.mapper.annotations.DynamoDbSecondaryPartitionKey;",
        "import software.amazon.awssdk.enhanced.dynamodb.mapper.annotations.DynamoDbSecondarySortKey;",
        "import software.amazon.awssdk.enhanced.dynamodb.mapper.annotations.DynamoDbSortKey;",
    ]

    lines = [f"package {infra_pkg};", ""]
    lines += imports
    lines += ["", HEADER, "@DynamoDbBean", f"public class {item_name} {{", "",
              f'    public static final String {gsi_name}_NAME = "{gsi_name}";', ""]
    # campos
    for c in cols:
        lines.append(f"    private {c['jtype']} {c['prop']};")
    lines.append("")
    # getters/setters
    for c in cols:
        getter = f"get{pascal(c['prop'])}"
        setter = f"set{pascal(c['prop'])}"
        for ann in c["ann"]:
            lines.append(f"    {ann}")
        lines.append(f'    @DynamoDbAttribute("{c["attribute"]}")')
        lines.append(f"    public {c['jtype']} {getter}() {{")
        lines.append(f"        return {c['prop']};")
        lines.append("    }")
        lines.append("")
        lines.append(f"    public void {setter}({c['jtype']} {c['prop']}) {{")
        lines.append(f"        this.{c['prop']} = {c['prop']};")
        lines.append("    }")
        lines.append("")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Emissao do mapper                                                             #
# --------------------------------------------------------------------------- #

def key_method(name: str, template: str, type_map: dict[str, dict[str, Any]]) -> tuple[str, list[str]]:
    """Constroi o corpo de partitionKey/indexPartitionKey a partir de um template
    '{campo}#{campo}'. Retorna (expressao_java, params_ordenados)."""
    tokens = re.split(r"(\{[^}]+\})", template)
    expr_parts: list[str] = []
    params: list[tuple[str, str]] = []
    seen: set[str] = set()
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith("{") and tok.endswith("}"):
            field = tok[1:-1]
            vo = _vo_for_field(field, type_map)
            kind = vo["kind"]
            ke = key_expr(kind, field)
            if ke is None:
                raise SystemExit(f"[erro] arquetipo '{kind}' do campo '{field}' nao pode compor chave.")
            expr_parts.append(ke)
            if field not in seen:
                seen.add(field)
                params.append((vo["name"], field))
        else:
            expr_parts.append('"' + tok.replace('"', '\\"') + '"')
    return " + ".join(expr_parts), params


_FIELD_TYPE_CACHE: dict[str, str] = {}


def _vo_for_field(field: str, type_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    vtype = _FIELD_TYPE_CACHE.get(field)
    if vtype is None:
        raise SystemExit(f"[erro] campo '{field}' referenciado numa chave nao existe no agregado.")
    return type_map[vtype]


def _index_fields(spec: dict[str, Any]) -> None:
    """Preenche _FIELD_TYPE_CACHE com field->VO type a partir do agregado."""
    _FIELD_TYPE_CACHE.clear()
    agg = spec["aggregate"]
    entries = list(agg.get("identity", []))
    if agg.get("sort"):
        entries.append(agg["sort"])
    entries += list(agg.get("mutable", []))
    for e in entries:
        vtype, fname = split_typed(e)
        _FIELD_TYPE_CACHE[fname] = vtype


def emit_item_mapper(spec: dict[str, Any], infra_pkg: str, model_pkg: str,
                     item_name: str, mapper_name: str, type_map: dict[str, dict[str, Any]]) -> str:
    st = spec["single_table"]
    agg = spec["aggregate"]
    agg_name = agg["name"]
    type_disc = st.get("type_discriminator", agg_name.upper())
    sort_field = st["sk"]["field"]
    gsi = st["gsi"]

    _index_fields(spec)
    pk_expr, pk_params = key_method("partitionKey", st["pk"], type_map)
    gsi_expr, gsi_params = key_method("indexPartitionKey", gsi["pk"], type_map)

    # ordem dos campos do agregado (= assinatura do rehydrate)
    ctor: list[tuple[str, str]] = [split_typed(e) for e in agg.get("identity", [])]
    if agg.get("sort"):
        ctor.append(split_typed(agg["sort"]))
    ctor += [split_typed(e) for e in agg.get("mutable", [])]

    # imports dos VOs usados + o proprio agregado (usado em toItem/toDomain/rehydrate,
    # e mora em .model — pacote diferente do mapper) + Instant/Timestamps.
    vo_types = sorted({t for t, _ in ctor} | {agg_name})
    imports = [f"import {model_pkg}.{t};" for t in vo_types]
    if agg.get("timestamps", True):
        imports.append(f"import {model_pkg}.Timestamps;")
        imports.append("import java.time.Instant;")

    def params_decl(params):
        return ", ".join(f"{t} {n}" for t, n in params)

    lines = [f"package {infra_pkg};", ""]
    lines += imports
    lines += ["", HEADER, f"public final class {mapper_name} {{", "",
              f'    private static final String TYPE = "{type_disc}";', "",
              f"    public static String partitionKey({params_decl(pk_params)}) {{",
              f"        return {pk_expr};", "    }", "",
              f"    public static String indexPartitionKey({params_decl(gsi_params)}) {{",
              f"        return {gsi_expr};", "    }", ""]

    # toItem
    lines.append(f"    public {item_name} toItem({agg_name} agg) {{")
    lines.append(f"        {item_name} item = new {item_name}();")
    lines.append(f"        item.setPk(partitionKey({', '.join('agg.' + n + '()' for _, n in pk_params)}));")
    sort_vo = type_map[_FIELD_TYPE_CACHE[sort_field]]
    sort_write = write_stmts(sort_vo["kind"], f"agg.{sort_field}()", sort_field, None, sort_vo)
    for s in sort_write:
        lines.append(f"        {s}")
    lines.append(f"        item.setGsi1pk(indexPartitionKey({', '.join('agg.' + n + '()' for _, n in gsi_params)}));")
    lines.append("        item.setType(TYPE);")
    columns = st.get("columns", {})
    for ftype, fname in ctor:
        if fname == sort_field:
            continue
        vo = type_map[ftype]
        for s in write_stmts(vo["kind"], f"agg.{fname}()", fname, columns.get(fname), vo):
            lines.append(f"        {s}")
    if agg.get("timestamps", True):
        lines.append("        item.setCreatedAt(agg.timestamps().createdAt().toString());")
        lines.append("        item.setUpdatedAt(agg.timestamps().updatedAt().toString());")
    if agg.get("version", True):
        lines.append("        item.setVersion(agg.version());")
    lines.append("        return item;")
    lines.append("    }")
    lines.append("")

    # toDomain
    lines.append(f"    public {agg_name} toDomain({item_name} item) {{")
    lines.append(f"        return {agg_name}.rehydrate(")
    read_lines = []
    for ftype, fname in ctor:
        vo = type_map[ftype]
        read_lines.append("            " + read_expr(vo["kind"], ftype, fname, columns.get(fname)))
    if agg.get("timestamps", True):
        read_lines.append("            Timestamps.of(Instant.parse(item.getCreatedAt()), "
                          "Instant.parse(item.getUpdatedAt()))")
    if agg.get("version", True):
        read_lines.append("            item.getVersion()")
    lines.append(",\n".join(read_lines))
    lines.append("        );")
    lines.append("    }")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Geracao                                                                       #
# --------------------------------------------------------------------------- #

def pkg_to_path(pkg: str) -> str:
    return pkg.replace(".", "/")


def infra_package(base_pkg: str) -> str:
    root = base_pkg[:-len(".domain")] if base_pkg.endswith(".domain") else base_pkg
    return root + ".infrastructure.persistence"


def generate(spec: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    if "single_table" not in spec or "aggregate" not in spec:
        raise SystemExit("[erro] a spec precisa dos blocos 'single_table' e 'aggregate'.")
    base_pkg = spec["package"]
    model_pkg = base_pkg + ".model"
    infra_pkg = infra_package(base_pkg)
    type_map = {vo["name"]: vo for vo in spec.get("value_objects", [])}

    agg_name = spec["aggregate"]["name"]
    item_name = spec["single_table"].get("item_name", agg_name + "Item")
    mapper_name = spec["single_table"].get("mapper_name", agg_name + "ItemMapper")

    infra_dir = out_dir / pkg_to_path(infra_pkg)
    infra_dir.mkdir(parents=True, exist_ok=True)

    bean = emit_item_bean(spec, infra_pkg, item_name, type_map)
    mapper = emit_item_mapper(spec, infra_pkg, model_pkg, item_name, mapper_name, type_map)
    (infra_dir / f"{item_name}.java").write_text(bean, encoding="utf-8")
    (infra_dir / f"{mapper_name}.java").write_text(mapper, encoding="utf-8")

    return {"infra_pkg": infra_pkg, "item": item_name, "mapper": mapper_name,
            "written": [str(infra_dir / f"{item_name}.java"), str(infra_dir / f"{mapper_name}.java")]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gera Item (@DynamoDbBean) + ItemMapper single-table da domain-spec.")
    ap.add_argument("spec", help="Caminho da domain-spec (.json) ou - para stdin")
    ap.add_argument("-o", "--output", required=True, help="Raiz de fontes Java (ex.: <proj>/src/main/java)")
    args = ap.parse_args(argv)

    raw = sys.stdin.read() if args.spec == "-" else Path(args.spec).read_text(encoding="utf-8")
    spec = json.loads(raw)
    result = generate(spec, Path(args.output).resolve())

    print(f"[ok] {result['item']} + {result['mapper']} gerados em {result['infra_pkg']}")
    for w in result["written"]:
        print(f"     - {w}")
    print(f"[nota] {result['item']} e um bean wide-row; em dominios grandes pode passar de 300 "
          "linhas (gate FileLength). Se ocorrer, suprima FileLength para *Item.java. O "
          "repositorio (queries/access patterns) NAO e gerado — confirme-o a mao.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
