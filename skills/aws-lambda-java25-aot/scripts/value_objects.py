#!/usr/bin/env python3
"""Gerador de VALUE OBJECTS a partir de uma domain-spec (JSON) — zero-dep.

O gargalo medido no caso `calendario-lambda`: depois do `generate_vanilla_lambda.py`
copiar o blueprint verbatim, o dev ainda escreve A MAO os value objects validados
do dominio real (Pais, Escopo, DataEvento, Horario, Descricao...) — ~7 min. Este
gerador aceita uma spec declarativa e emite esses VOs (records com validacao no
compact constructor + fabricas) + a excecao base, cortando a adaptacao para ~2-3 min.

Uso:
    python value_objects.py domain-spec.json -o <project>/src/main/java
    python value_objects.py domain-spec.json -o out --aggregate --emit-base

Formato da spec (ver examples/calendario-domain.json e references/domain-spec.md):

    {
      "package": "com.squadai.calendario.domain",     # base; VOs->.model, exc->.exception
      "value_objects": [
        {"name": "Pais",    "kind": "string_pattern", "pattern": "^[A-Z]{2,3}$",
         "normalize": "upper", "message": "Pais deve ser um codigo ISO de 2 ou 3 letras"},
        {"name": "Escopo",  "kind": "enum", "values": ["NACIONAL","INTERNACIONAL","ESTADUAL"]},
        {"name": "EventoId","kind": "identifier", "max_length": 128},
        {"name": "DataEvento","kind": "local_date"},
        {"name": "Horario", "kind": "time_range"},
        {"name": "Descricao","kind": "bounded_string", "min_length": 1, "max_length": 500}
      ],
      "aggregate": {                                   # opcional (--aggregate)
        "name": "PagamentoCalendario",
        "identity": ["EventoId id", "Pais pais", "Escopo escopo"],
        "sort":     "DataEvento data",
        "mutable":  ["Horario horario", "Descricao descricao"],
        "timestamps": true, "version": true
      }
    }

Arquetipos suportados (kind): string_pattern, bounded_string, enum, identifier,
local_date, local_time, time_range, integer_range, decimal, instant.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable


# --------------------------------------------------------------------------- #
# Helpers                                                                       #
# --------------------------------------------------------------------------- #

def pascal_to_kebab(name: str) -> str:
    """DataEvento -> data-evento, EventoId -> evento-id, Pais -> pais."""
    s = re.sub(r"(?<!^)(?=[A-Z])", "-", name)
    return s.lower()


def code_for(name: str) -> str:
    return "invalid-" + pascal_to_kebab(name)


def escape_java(s: str) -> str:
    """Escapa uma string Python para caber num string literal Java."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def subst(template: str, **kw: str) -> str:
    out = template
    for key, val in kw.items():
        out = out.replace("@" + key + "@", str(val))
    return out


def field_name_lower(name: str) -> str:
    return name[:1].lower() + name[1:] if name else name


HEADER = "/// Gerado por scripts/value_objects.py a partir da domain-spec.\n/// Regenere a partir da spec — evite editar a mao."


# --------------------------------------------------------------------------- #
# Arquetipos de value object                                                    #
# --------------------------------------------------------------------------- #

def emit_string_pattern(vo: dict[str, Any], model_pkg: str, exc_pkg: str) -> str:
    name = vo["name"]
    normalize = vo.get("normalize", "none")
    norm_expr = {
        "upper": "value.strip().toUpperCase()",
        "lower": "value.strip().toLowerCase()",
        "none": "value.strip()",
    }[normalize]
    tmpl = """package @model_pkg@;

import @exc_pkg@.InvalidValueObject;
import java.util.regex.Pattern;

@header@
public record @name@(String value) {

    private static final Pattern PATTERN = Pattern.compile("@pattern@");

    public @name@ {
        if (value == null) {
            throw new InvalidValueObject("@code@", "@name@ nao pode ser nulo");
        }
        String normalized = @norm_expr@;
        if (!PATTERN.matcher(normalized).matches()) {
            throw new InvalidValueObject("@code@", "@message@");
        }
        value = normalized;
    }

    public static @name@ of(String value) {
        return new @name@(value);
    }
}
"""
    return subst(
        tmpl, model_pkg=model_pkg, exc_pkg=exc_pkg, name=name, header=HEADER,
        pattern=escape_java(vo["pattern"]), code=code_for(name), norm_expr=norm_expr,
        message=escape_java(vo.get("message", name + " invalido")),
    )


def emit_bounded_string(vo: dict[str, Any], model_pkg: str, exc_pkg: str) -> str:
    name = vo["name"]
    minl = int(vo.get("min_length", 1))
    maxl = int(vo.get("max_length", 255))
    code = code_for(name)
    required = minl >= 1
    imports = f"import {exc_pkg}.InvalidValueObject;"
    lines = [f"package {model_pkg};", "", imports]
    if not required:
        lines.append("import java.util.Optional;")
    lines += ["", HEADER, f"public record {name}(String value) {{", "",
              f"    private static final int MAX_LENGTH = {maxl};"]
    if minl > 1:
        lines.append(f"    private static final int MIN_LENGTH = {minl};")
    lines += ["", f"    public {name} {{"]
    if required:
        lines += [
            "        if (value == null) {",
            f'            throw new InvalidValueObject("{code}", "{name} nao pode ser nulo");',
            "        }",
            "        String trimmed = value.strip();",
            "        if (trimmed.isEmpty()) {",
            f'            throw new InvalidValueObject("{code}", "{name} nao pode ser vazio");',
            "        }",
        ]
        if minl > 1:
            lines += [
                "        if (trimmed.length() < MIN_LENGTH) {",
                f'            throw new InvalidValueObject("{code}", "{name} deve ter no minimo " + MIN_LENGTH + " caracteres");',
                "        }",
            ]
    else:
        lines.append("        String trimmed = value == null ? \"\" : value.strip();")
    lines += [
        "        if (trimmed.length() > MAX_LENGTH) {",
        f'            throw new InvalidValueObject("{code}", "{name} deve ter no maximo " + MAX_LENGTH + " caracteres");',
        "        }",
        "        value = trimmed;",
        "    }",
        "",
        f"    public static {name} of(String value) {{",
        f"        return new {name}(value);",
        "    }",
    ]
    if not required:
        lines += [
            "",
            f"    public static {name} empty() {{",
            f'        return new {name}("");',
            "    }",
            "",
            "    public Optional<String> asOptional() {",
            "        return value.isEmpty() ? Optional.empty() : Optional.of(value);",
            "    }",
        ]
    lines += ["}", ""]
    return "\n".join(lines)


def emit_enum(vo: dict[str, Any], model_pkg: str, exc_pkg: str) -> str:
    name = vo["name"]
    values = ",\n    ".join(vo["values"])
    tmpl = """package @model_pkg@;

import @exc_pkg@.InvalidValueObject;
import java.util.Arrays;

@header@
public enum @name@ {
    @values@;

    public static @name@ parse(String raw) {
        if (raw == null) {
            throw new InvalidValueObject("@code@", "@name@ nao pode ser nulo");
        }
        String candidate = raw.strip().toUpperCase();
        return Arrays.stream(values())
            .filter(item -> item.name().equals(candidate))
            .findFirst()
            .orElseThrow(() -> new InvalidValueObject("@code@", "@name@ desconhecido: " + raw));
    }
}
"""
    return subst(tmpl, model_pkg=model_pkg, exc_pkg=exc_pkg, name=name,
                 header=HEADER, values=values, code=code_for(name))


def emit_identifier(vo: dict[str, Any], model_pkg: str, exc_pkg: str) -> str:
    name = vo["name"]
    maxl = int(vo.get("max_length", 128))
    tmpl = """package @model_pkg@;

import @exc_pkg@.InvalidValueObject;
import java.util.UUID;
import java.util.regex.Pattern;

@header@
public record @name@(String value) {

    private static final int MAX_LENGTH = @maxl@;
    private static final Pattern ALLOWED = Pattern.compile("^[A-Za-z0-9_-]+$");

    public @name@ {
        if (value == null) {
            throw new InvalidValueObject("@code@", "@name@ nao pode ser nulo");
        }
        String trimmed = value.strip();
        if (trimmed.isEmpty()) {
            throw new InvalidValueObject("@code@", "@name@ nao pode ser vazio");
        }
        if (trimmed.length() > MAX_LENGTH) {
            throw new InvalidValueObject("@code@", "@name@ deve ter no maximo " + MAX_LENGTH + " caracteres");
        }
        if (!ALLOWED.matcher(trimmed).matches()) {
            throw new InvalidValueObject("@code@", "@name@ deve casar " + ALLOWED.pattern());
        }
        value = trimmed;
    }

    public static @name@ of(String value) {
        return new @name@(value);
    }

    public static @name@ generate() {
        return new @name@(UUID.randomUUID().toString());
    }
}
"""
    return subst(tmpl, model_pkg=model_pkg, exc_pkg=exc_pkg, name=name,
                 header=HEADER, maxl=maxl, code=code_for(name))


def emit_local_date(vo: dict[str, Any], model_pkg: str, exc_pkg: str) -> str:
    name = vo["name"]
    tmpl = """package @model_pkg@;

import @exc_pkg@.InvalidValueObject;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;

@header@
public record @name@(LocalDate value) implements Comparable<@name@> {

    public @name@ {
        if (value == null) {
            throw new InvalidValueObject("@code@", "@name@ nao pode ser nulo");
        }
    }

    public static @name@ of(LocalDate value) {
        return new @name@(value);
    }

    public static @name@ parse(String raw) {
        if (raw == null) {
            throw new InvalidValueObject("@code@", "@name@ nao pode ser nulo");
        }
        try {
            return new @name@(LocalDate.parse(raw.strip()));
        } catch (DateTimeParseException invalid) {
            throw new InvalidValueObject("@code@", "@name@ deve estar no formato yyyy-MM-dd: " + raw);
        }
    }

    /// Chave textual estavel (`yyyy-MM-dd`), ordena cronologicamente. Boa como SK/GSI-SK.
    public String asKey() {
        return value.toString();
    }

    @Override
    public int compareTo(@name@ other) {
        return value.compareTo(other.value);
    }
}
"""
    return subst(tmpl, model_pkg=model_pkg, exc_pkg=exc_pkg, name=name,
                 header=HEADER, code=code_for(name))


def emit_local_time(vo: dict[str, Any], model_pkg: str, exc_pkg: str) -> str:
    name = vo["name"]
    tmpl = """package @model_pkg@;

import @exc_pkg@.InvalidValueObject;
import java.time.LocalTime;
import java.time.format.DateTimeParseException;

@header@
public record @name@(LocalTime value) {

    public @name@ {
        if (value == null) {
            throw new InvalidValueObject("@code@", "@name@ nao pode ser nulo");
        }
    }

    public static @name@ of(LocalTime value) {
        return new @name@(value);
    }

    public static @name@ parse(String raw) {
        if (raw == null) {
            throw new InvalidValueObject("@code@", "@name@ nao pode ser nulo");
        }
        try {
            return new @name@(LocalTime.parse(raw.strip()));
        } catch (DateTimeParseException invalid) {
            throw new InvalidValueObject("@code@", "@name@ deve estar no formato HH:mm: " + raw);
        }
    }

    public String asText() {
        return value.toString();
    }
}
"""
    return subst(tmpl, model_pkg=model_pkg, exc_pkg=exc_pkg, name=name,
                 header=HEADER, code=code_for(name))


def emit_time_range(vo: dict[str, Any], model_pkg: str, exc_pkg: str) -> str:
    name = vo["name"]
    start = vo.get("start", "inicio")
    end = vo.get("end", "fim")
    start_pascal = start[:1].upper() + start[1:]
    end_pascal = end[:1].upper() + end[1:]
    tmpl = """package @model_pkg@;

import @exc_pkg@.InvalidValueObject;
import java.time.LocalTime;
import java.time.format.DateTimeParseException;

@header@
public record @name@(LocalTime @start@, LocalTime @end@) {

    public @name@ {
        if (@start@ == null || @end@ == null) {
            throw new InvalidValueObject("@code@", "@start@ e @end@ sao obrigatorios");
        }
        if (!@end@.isAfter(@start@)) {
            throw new InvalidValueObject("@code@", "@end@ deve ser apos @start@");
        }
    }

    public static @name@ of(LocalTime @start@, LocalTime @end@) {
        return new @name@(@start@, @end@);
    }

    public static @name@ parse(String @start@, String @end@) {
        return new @name@(parseTime(@start@, "@start@"), parseTime(@end@, "@end@"));
    }

    private static LocalTime parseTime(String raw, String campo) {
        if (raw == null) {
            throw new InvalidValueObject("@code@", campo + " e obrigatorio");
        }
        try {
            return LocalTime.parse(raw.strip());
        } catch (DateTimeParseException invalid) {
            throw new InvalidValueObject("@code@", campo + " deve estar no formato HH:mm: " + raw);
        }
    }

    public String @start@AsText() {
        return @start@.toString();
    }

    public String @end@AsText() {
        return @end@.toString();
    }
}
"""
    return subst(tmpl, model_pkg=model_pkg, exc_pkg=exc_pkg, name=name, header=HEADER,
                 start=start, end=end, start_pascal=start_pascal, end_pascal=end_pascal,
                 code=code_for(name))


def emit_integer_range(vo: dict[str, Any], model_pkg: str, exc_pkg: str) -> str:
    name = vo["name"]
    minv = int(vo.get("min", 0))
    maxv = int(vo.get("max", 2147483647))
    tmpl = """package @model_pkg@;

import @exc_pkg@.InvalidValueObject;

@header@
public record @name@(int value) {

    private static final int MIN = @minv@;
    private static final int MAX = @maxv@;

    public @name@ {
        if (value < MIN || value > MAX) {
            throw new InvalidValueObject("@code@", "@name@ deve estar entre " + MIN + " e " + MAX);
        }
    }

    public static @name@ of(int value) {
        return new @name@(value);
    }
}
"""
    return subst(tmpl, model_pkg=model_pkg, exc_pkg=exc_pkg, name=name,
                 header=HEADER, minv=minv, maxv=maxv, code=code_for(name))


def emit_decimal(vo: dict[str, Any], model_pkg: str, exc_pkg: str) -> str:
    name = vo["name"]
    positive = bool(vo.get("positive", True))
    check = ""
    if positive:
        check = (
            "        if (value.signum() <= 0) {\n"
            f'            throw new InvalidValueObject("{code_for(name)}", "@name@ deve ser positivo");\n'
            "        }\n"
        )
    tmpl = """package @model_pkg@;

import @exc_pkg@.InvalidValueObject;
import java.math.BigDecimal;

@header@
public record @name@(BigDecimal value) {

    public @name@ {
        if (value == null) {
            throw new InvalidValueObject("@code@", "@name@ nao pode ser nulo");
        }
@check@    }

    public static @name@ of(BigDecimal value) {
        return new @name@(value);
    }

    public static @name@ parse(String raw) {
        if (raw == null) {
            throw new InvalidValueObject("@code@", "@name@ nao pode ser nulo");
        }
        try {
            return new @name@(new BigDecimal(raw.strip()));
        } catch (NumberFormatException invalid) {
            throw new InvalidValueObject("@code@", "@name@ nao e um numero decimal: " + raw);
        }
    }
}
"""
    return subst(tmpl, model_pkg=model_pkg, exc_pkg=exc_pkg, name=name,
                 header=HEADER, code=code_for(name), check=subst(check, name=name))


def emit_instant(vo: dict[str, Any], model_pkg: str, exc_pkg: str) -> str:
    name = vo["name"]
    tmpl = """package @model_pkg@;

import @exc_pkg@.InvalidValueObject;
import java.time.Instant;
import java.time.format.DateTimeParseException;

@header@
public record @name@(Instant value) {

    public @name@ {
        if (value == null) {
            throw new InvalidValueObject("@code@", "@name@ nao pode ser nulo");
        }
    }

    public static @name@ of(Instant value) {
        return new @name@(value);
    }

    public static @name@ parse(String raw) {
        if (raw == null) {
            throw new InvalidValueObject("@code@", "@name@ nao pode ser nulo");
        }
        try {
            return new @name@(Instant.parse(raw.strip()));
        } catch (DateTimeParseException invalid) {
            throw new InvalidValueObject("@code@", "@name@ deve ser um instante ISO-8601: " + raw);
        }
    }

    public String asKey() {
        return value.toString();
    }
}
"""
    return subst(tmpl, model_pkg=model_pkg, exc_pkg=exc_pkg, name=name,
                 header=HEADER, code=code_for(name))


ARCHETYPES: dict[str, Callable[[dict[str, Any], str, str], str]] = {
    "string_pattern": emit_string_pattern,
    "bounded_string": emit_bounded_string,
    "enum": emit_enum,
    "identifier": emit_identifier,
    "local_date": emit_local_date,
    "local_time": emit_local_time,
    "time_range": emit_time_range,
    "integer_range": emit_integer_range,
    "decimal": emit_decimal,
    "instant": emit_instant,
}


# --------------------------------------------------------------------------- #
# Excecoes base                                                                 #
# --------------------------------------------------------------------------- #

DOMAIN_EXCEPTION = """package @exc_pkg@;

/// Base de toda violacao de regra de dominio. Carrega um codigo estavel de
/// maquina para a camada de API mapear em RFC 9457 sem cadeias de instanceof.
public abstract class DomainException extends RuntimeException {

    private final String code;

    protected DomainException(String code, String message) {
        super(message);
        this.code = code;
    }

    public String code() {
        return code;
    }
}
"""

INVALID_VALUE_OBJECT = """package @exc_pkg@;

@header@
public final class InvalidValueObject extends DomainException {

    public InvalidValueObject(String code, String message) {
        super(code, message);
    }
}
"""


# --------------------------------------------------------------------------- #
# Agregado (opcional)                                                           #
# --------------------------------------------------------------------------- #

def _split_typed(entry: str) -> tuple[str, str]:
    """'EventoId id' -> ('EventoId', 'id'). Exige exatamente 'Tipo nome' (2 tokens)."""
    parts = entry.split()
    if len(parts) != 2:
        raise SystemExit(
            f"[erro] entrada de agregado invalida: '{entry}'. Use exatamente "
            "'Tipo nome' (2 tokens, tipo sem espaco). Para um tipo composto, "
            "declare um value object e referencie-o pelo nome."
        )
    return parts[0], parts[1]


def emit_aggregate(agg: dict[str, Any], model_pkg: str) -> str:
    name = agg["name"]
    identity = [_split_typed(e) for e in agg.get("identity", [])]
    sort = [_split_typed(agg["sort"])] if agg.get("sort") else []
    mutable = [_split_typed(e) for e in agg.get("mutable", [])]
    use_ts = bool(agg.get("timestamps", True))
    use_version = bool(agg.get("version", True))

    key_fields = identity + sort            # imutaveis (compoem a chave)
    all_fields = key_fields + mutable
    ctor_fields = list(all_fields)
    if use_ts:
        ctor_fields.append(("Timestamps", "timestamps"))
    if use_version:
        ctor_fields.append(("Long", "version"))

    def decl(fields):
        return ",\n".join(f"                                {t} {n}" for t, n in fields)

    def args(fields):
        return ", ".join(n for _, n in fields)

    fields_block = "\n".join(f"    private final {t} {n};" for t, n in ctor_fields)

    # criar: chave + mutaveis + now (sem version, sem timestamps explicito)
    criar_params = all_fields + [("Instant", "now")]
    criar_args = args(all_fields) + (", Timestamps.createdAt(now)" if use_ts else "") + (", null" if use_version else "")
    rehydrate_args = args(ctor_fields)

    mutators = []
    for t, n in mutable:
        pascal = n[:1].upper() + n[1:]
        other_args = ", ".join(
            ("novo" + pascal if fn == n else fn) for _, fn in mutable
        )
        mutators.append(
            f"    public {name} alterar{pascal}({t} novo{pascal}, Instant now) {{\n"
            f"        return copyWith({other_args}, now);\n"
            f"    }}\n"
        )
    copy_args = ", ".join(f"novo{n[:1].upper() + n[1:]}" for _, n in mutable) or ""
    copy_params = ", ".join(f"{t} novo{n[:1].upper() + n[1:]}" for t, n in mutable)
    copy_body_args = args(key_fields)
    if mutable:
        copy_body_args += ", " + ", ".join(f"novo{n[:1].upper() + n[1:]}" for _, n in mutable)
    if use_ts:
        copy_body_args += ", timestamps.touched(now)"
    if use_version:
        copy_body_args += ", version"

    getters = "\n\n".join(
        f"    public {t} {n}() {{\n        return {n};\n    }}" for t, n in ctor_fields
    )

    imports = ["import java.time.Instant;"]
    header = HEADER
    parts = [f"package {model_pkg};", "", *imports, "", header,
             f"public final class {name} {{", "", fields_block, "",
             f"    private {name}(", decl(ctor_fields), "    ) {"]
    parts += [f"        this.{n} = {n};" for _, n in ctor_fields]
    parts += ["    }", ""]
    # criar
    parts += [f"    public static {name} criar(", decl(criar_params), "    ) {",
              f"        return new {name}({criar_args});", "    }", ""]
    # rehydrate
    parts += [f"    public static {name} rehydrate(", decl(ctor_fields), "    ) {",
              f"        return new {name}({rehydrate_args});", "    }", ""]
    # mutators
    for m in mutators:
        parts.append(m)
    # copyWith
    if mutable:
        parts += [f"    private {name} copyWith({copy_params}, Instant now) {{",
                  f"        return new {name}({copy_body_args});", "    }", ""]
    # getters
    parts += [getters, "}", ""]
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Geracao                                                                       #
# --------------------------------------------------------------------------- #

def pkg_to_path(pkg: str) -> str:
    return pkg.replace(".", "/")


def generate(spec: dict[str, Any], out_dir: Path, with_aggregate: bool, emit_base: bool) -> dict[str, Any]:
    base_pkg = spec["package"]
    model_pkg = base_pkg + ".model"
    exc_pkg = base_pkg + ".exception"
    model_dir = out_dir / pkg_to_path(model_pkg)
    exc_dir = out_dir / pkg_to_path(exc_pkg)
    model_dir.mkdir(parents=True, exist_ok=True)
    exc_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []

    # Excecoes base: InvalidValueObject sempre; DomainException so se ausente
    # (nao clobra a do blueprint) — ou forcado por --emit-base.
    dom_path = exc_dir / "DomainException.java"
    if emit_base or not dom_path.exists():
        dom_path.write_text(subst(DOMAIN_EXCEPTION, exc_pkg=exc_pkg), encoding="utf-8")
        written.append(str(dom_path))
    ivo_path = exc_dir / "InvalidValueObject.java"
    ivo_path.write_text(subst(INVALID_VALUE_OBJECT, exc_pkg=exc_pkg, header=HEADER), encoding="utf-8")
    written.append(str(ivo_path))

    # Value objects
    for vo in spec.get("value_objects", []):
        kind = vo["kind"]
        if kind not in ARCHETYPES:
            raise SystemExit(f"[erro] arquetipo desconhecido: '{kind}' (vo {vo.get('name')}). "
                             f"Suportados: {', '.join(sorted(ARCHETYPES))}")
        src = ARCHETYPES[kind](vo, model_pkg, exc_pkg)
        path = model_dir / f"{vo['name']}.java"
        path.write_text(src, encoding="utf-8")
        written.append(str(path))

    # Agregado opcional
    agg = spec.get("aggregate")
    if with_aggregate and agg:
        # Timestamps helper (necessario pelo agregado) se ausente
        if agg.get("timestamps", True):
            ts_path = model_dir / "Timestamps.java"
            if emit_base or not ts_path.exists():
                ts_path.write_text(subst(TIMESTAMPS, model_pkg=model_pkg, header=HEADER), encoding="utf-8")
                written.append(str(ts_path))
        agg_src = emit_aggregate(agg, model_pkg)
        agg_path = model_dir / f"{agg['name']}.java"
        agg_path.write_text(agg_src, encoding="utf-8")
        written.append(str(agg_path))

    return {"written": written, "model_pkg": model_pkg, "exc_pkg": exc_pkg}


TIMESTAMPS = """package @model_pkg@;

import java.time.Instant;

@header@
public record Timestamps(Instant createdAt, Instant updatedAt) {

    public static Timestamps createdAt(Instant moment) {
        return new Timestamps(moment, moment);
    }

    public static Timestamps of(Instant createdAt, Instant updatedAt) {
        return new Timestamps(createdAt, updatedAt);
    }

    public Timestamps touched(Instant moment) {
        return new Timestamps(createdAt, moment);
    }
}
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gera value objects Java a partir de uma domain-spec JSON.")
    ap.add_argument("spec", help="Caminho da domain-spec (.json) ou - para stdin")
    ap.add_argument("-o", "--output", required=True, help="Raiz de fontes Java (ex.: <proj>/src/main/java)")
    ap.add_argument("--aggregate", action="store_true", help="Tambem emite o esqueleto do agregado (bloco 'aggregate')")
    ap.add_argument("--emit-base", action="store_true", help="Forca (re)emitir DomainException/Timestamps mesmo se existirem")
    args = ap.parse_args(argv)

    raw = sys.stdin.read() if args.spec == "-" else Path(args.spec).read_text(encoding="utf-8")
    spec = json.loads(raw)
    if "package" not in spec:
        raise SystemExit("[erro] spec sem campo 'package'")

    out_dir = Path(args.output).resolve()
    result = generate(spec, out_dir, with_aggregate=args.aggregate, emit_base=args.emit_base)

    n_vo = len(spec.get("value_objects", []))
    print(f"[ok] {n_vo} value objects + excecoes gerados em {result['model_pkg']} / {result['exc_pkg']}")
    for w in result["written"]:
        print(f"     - {w}")
    if args.aggregate and spec.get("aggregate"):
        agg_name = spec["aggregate"]["name"]
        print(f"[nota] o agregado {agg_name} tem criar()/rehydrate() de campo-completo "
              "(padrao DDD, imutavel-rico). Se o gate Checkstyle estrutural estiver ativo, "
              f"suprima ParameterNumber E MethodLength para {agg_name}.java em "
              'config/checkstyle/suppressions.xml (checks="ParameterNumber|MethodLength") '
              "— dominios grandes fazem rehydrate() passar de 35 linhas (1 param por linha).")
    print("[proximo] wire o mapper/persistencia aos novos VOs e rode ./mvnw verify.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
