#!/usr/bin/env python3
"""Testes do gerador de value objects (stdlib unittest, zero-dep).

Rodar:
    cd skills/aws-lambda-java25-aot/scripts
    python -m unittest test_value_objects -v
    # ou: python test_value_objects.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import value_objects as vo  # noqa: E402

MODEL_PKG = "com.acme.demo.domain.model"
EXC_PKG = "com.acme.demo.domain.exception"


class Helpers(unittest.TestCase):
    def test_pascal_to_kebab(self):
        self.assertEqual(vo.pascal_to_kebab("Pais"), "pais")
        self.assertEqual(vo.pascal_to_kebab("DataEvento"), "data-evento")
        self.assertEqual(vo.pascal_to_kebab("EventoId"), "evento-id")

    def test_code_for(self):
        self.assertEqual(vo.code_for("Pais"), "invalid-pais")
        self.assertEqual(vo.code_for("DataEvento"), "invalid-data-evento")

    def test_escape_java(self):
        self.assertEqual(vo.escape_java(r"a\d"), r"a\\d")
        self.assertEqual(vo.escape_java('x"y'), 'x\\"y')


class Archetypes(unittest.TestCase):
    def emit(self, kind, spec):
        return vo.ARCHETYPES[kind]({**spec, "kind": kind}, MODEL_PKG, EXC_PKG)

    def test_string_pattern(self):
        src = self.emit("string_pattern", {"name": "Pais", "pattern": "^[A-Z]{2,3}$",
                                           "normalize": "upper", "message": "codigo ISO"})
        self.assertIn("public record Pais(String value)", src)
        self.assertIn('Pattern.compile("^[A-Z]{2,3}$")', src)
        self.assertIn("value.strip().toUpperCase()", src)
        self.assertIn('new InvalidValueObject("invalid-pais"', src)
        self.assertIn("public static Pais of(String value)", src)

    def test_enum(self):
        src = self.emit("enum", {"name": "Escopo", "values": ["NACIONAL", "INTERNACIONAL", "ESTADUAL"]})
        self.assertIn("public enum Escopo", src)
        for v in ("NACIONAL", "INTERNACIONAL", "ESTADUAL"):
            self.assertIn(v, src)
        self.assertIn("public static Escopo parse(String raw)", src)
        self.assertIn('"invalid-escopo"', src)

    def test_identifier(self):
        src = self.emit("identifier", {"name": "EventoId", "max_length": 128})
        self.assertIn("MAX_LENGTH = 128", src)
        self.assertIn("UUID.randomUUID().toString()", src)
        self.assertIn("public static EventoId generate()", src)
        self.assertIn('"invalid-evento-id"', src)

    def test_local_date(self):
        src = self.emit("local_date", {"name": "DataEvento"})
        self.assertIn("implements Comparable<DataEvento>", src)
        self.assertIn("LocalDate.parse(raw.strip())", src)
        self.assertIn("public String asKey()", src)
        self.assertIn("public int compareTo(DataEvento other)", src)

    def test_time_range(self):
        src = self.emit("time_range", {"name": "Horario"})
        self.assertIn("public record Horario(LocalTime inicio, LocalTime fim)", src)
        self.assertIn("!fim.isAfter(inicio)", src)
        self.assertIn("public String inicioAsText()", src)
        self.assertIn("public String fimAsText()", src)
        self.assertIn("private static LocalTime parseTime(", src)

    def test_bounded_string_required(self):
        src = self.emit("bounded_string", {"name": "Descricao", "min_length": 1, "max_length": 500})
        self.assertIn("MAX_LENGTH = 500", src)
        self.assertIn("nao pode ser vazio", src)
        self.assertIn("no maximo", src)
        self.assertNotIn("asOptional", src)

    def test_bounded_string_optional(self):
        src = self.emit("bounded_string", {"name": "Observacao", "min_length": 0, "max_length": 1000})
        self.assertIn("import java.util.Optional;", src)
        self.assertIn("public Optional<String> asOptional()", src)
        self.assertIn("public static Observacao empty()", src)

    def test_integer_range(self):
        src = self.emit("integer_range", {"name": "Estoque", "min": 0, "max": 1000000})
        self.assertIn("MIN = 0", src)
        self.assertIn("MAX = 1000000", src)
        self.assertIn("public record Estoque(int value)", src)

    def test_decimal_positive(self):
        src = self.emit("decimal", {"name": "Preco", "positive": True})
        self.assertIn("import java.math.BigDecimal;", src)
        self.assertIn("value.signum() <= 0", src)
        self.assertIn("new BigDecimal(raw.strip())", src)
        self.assertIn('"invalid-preco"', src)

    def test_instant(self):
        src = self.emit("instant", {"name": "CriadoEm"})
        self.assertIn("Instant.parse(raw.strip())", src)
        self.assertIn("public String asKey()", src)


class Generation(unittest.TestCase):
    def _spec(self):
        path = Path(__file__).resolve().parent.parent / "examples" / "calendario-domain.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_dogfood_calendario(self):
        spec = self._spec()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            vo.generate(spec, out, with_aggregate=True, emit_base=True)
            model = out / "com/squadai/calendario/domain/model"
            exc = out / "com/squadai/calendario/domain/exception"
            for f in ("Pais", "Escopo", "EventoId", "DataEvento", "Horario", "Descricao",
                      "Timestamps", "PagamentoCalendario"):
                self.assertTrue((model / f"{f}.java").exists(), f"faltou {f}.java")
            self.assertTrue((exc / "InvalidValueObject.java").exists())
            self.assertTrue((exc / "DomainException.java").exists())

            # todo .java gerado: balanceamento de chaves + header de package
            for java in list(model.glob("*.java")) + list(exc.glob("*.java")):
                text = java.read_text(encoding="utf-8")
                self.assertTrue(text.startswith("package "), f"{java.name} sem package")
                self.assertEqual(text.count("{"), text.count("}"), f"{java.name} chaves desbalanceadas")

            agg = (model / "PagamentoCalendario.java").read_text(encoding="utf-8")
            for needle in ("public static PagamentoCalendario criar(",
                           "public static PagamentoCalendario rehydrate(",
                           "public PagamentoCalendario alterarHorario(",
                           "public PagamentoCalendario alterarDescricao(",
                           "private PagamentoCalendario copyWith("):
                self.assertIn(needle, agg)

    def test_domain_exception_not_clobbered(self):
        spec = self._spec()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            exc_dir = out / "com/squadai/calendario/domain/exception"
            exc_dir.mkdir(parents=True)
            sentinel = "// SENTINELA — blueprint existente\n"
            (exc_dir / "DomainException.java").write_text(sentinel, encoding="utf-8")
            vo.generate(spec, out, with_aggregate=False, emit_base=False)
            preserved = (exc_dir / "DomainException.java").read_text(encoding="utf-8")
            self.assertEqual(preserved, sentinel, "DomainException do blueprint foi sobrescrito")

    def test_unknown_kind_raises(self):
        spec = {"package": "com.x.y", "value_objects": [{"name": "Z", "kind": "bogus"}]}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                vo.generate(spec, Path(tmp), with_aggregate=False, emit_base=False)

    def test_bad_aggregate_entry_raises(self):
        spec = {"package": "com.x.y", "value_objects": [],
                "aggregate": {"name": "A", "identity": ["SoUmToken"], "mutable": []}}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                vo.generate(spec, Path(tmp), with_aggregate=True, emit_base=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
