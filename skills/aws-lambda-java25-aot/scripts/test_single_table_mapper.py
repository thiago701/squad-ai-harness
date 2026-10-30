#!/usr/bin/env python3
"""Testes do gerador Item + ItemMapper single-table (stdlib unittest, zero-dep).

Rodar:
    cd skills/aws-lambda-java25-aot/scripts
    python -m unittest test_single_table_mapper -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import single_table_mapper as stm  # noqa: E402


def load_calendario():
    path = Path(__file__).resolve().parent.parent / "examples" / "calendario-domain.json"
    return json.loads(path.read_text(encoding="utf-8"))


class DogfoodCalendario(unittest.TestCase):
    def setUp(self):
        self.spec = load_calendario()
        self._tmp = tempfile.TemporaryDirectory()
        out = Path(self._tmp.name)
        stm.generate(self.spec, out)
        infra = out / "com/squadai/calendario/infrastructure/persistence"
        self.item = (infra / "PagamentoItem.java").read_text(encoding="utf-8")
        self.mapper = (infra / "PagamentoItemMapper.java").read_text(encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_bean_annotations(self):
        for needle in (
            "@DynamoDbBean",
            "public class PagamentoItem {",
            'public static final String GSI1_NAME = "GSI1";',
            "@DynamoDbPartitionKey",
            '@DynamoDbAttribute("PK")',
            "@DynamoDbSortKey",
            "@DynamoDbSecondarySortKey(indexNames = GSI1_NAME)",
            '@DynamoDbAttribute("DATA")',
            "@DynamoDbSecondaryPartitionKey(indexNames = GSI1_NAME)",
            '@DynamoDbAttribute("GSI1PK")',
            '@DynamoDbAttribute("PAIS")',
            '@DynamoDbAttribute("ESCOPO")',
            '@DynamoDbAttribute("HoraInicio")',
            '@DynamoDbAttribute("HoraFim")',
            '@DynamoDbAttribute("Descricao")',
            "@DynamoDbVersionAttribute",
            "private Long version;",
        ):
            self.assertIn(needle, self.item, f"bean sem: {needle}")

    def test_mapper_imports_aggregate(self):
        # regressao: o mapper usa o agregado (outro pacote) e precisa importa-lo.
        self.assertIn("import com.squadai.calendario.domain.model.PagamentoCalendario;", self.mapper)

    def test_mapper_keys_and_roundtrip(self):
        for needle in (
            "public static String partitionKey(Pais pais, Escopo escopo, EventoId id)",
            'return pais.value() + "#" + escopo.name() + "#" + id.value();',
            "public static String indexPartitionKey(Pais pais, Escopo escopo)",
            'return pais.value() + "#" + escopo.name();',
            "public PagamentoItem toItem(PagamentoCalendario agg)",
            "item.setPk(partitionKey(agg.pais(), agg.escopo(), agg.id()));",
            "item.setData(agg.data().asKey());",
            "item.setGsi1pk(indexPartitionKey(agg.pais(), agg.escopo()));",
            "item.setType(TYPE);",
            "item.setHoraInicio(agg.horario().inicioAsText());",
            "item.setHoraFim(agg.horario().fimAsText());",
            "item.setVersion(agg.version());",
            "public PagamentoCalendario toDomain(PagamentoItem item)",
            "return PagamentoCalendario.rehydrate(",
            "EventoId.of(item.getId())",
            "Escopo.parse(item.getEscopo())",
            "DataEvento.parse(item.getData())",
            "Horario.parse(item.getHoraInicio(), item.getHoraFim())",
            "Timestamps.of(Instant.parse(item.getCreatedAt()), Instant.parse(item.getUpdatedAt()))",
            "item.getVersion()",
        ):
            self.assertIn(needle, self.mapper, f"mapper sem: {needle}")

    def test_braces_balanced(self):
        for name, text in (("PagamentoItem", self.item), ("PagamentoItemMapper", self.mapper)):
            self.assertTrue(text.startswith("package "), f"{name} sem package")
            self.assertEqual(text.count("{"), text.count("}"), f"{name} chaves desbalanceadas")


class Guards(unittest.TestCase):
    def test_requires_single_table_and_aggregate(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                stm.generate({"package": "com.x.y.domain", "value_objects": []}, Path(tmp))

    def test_unmapped_column_raises(self):
        spec = load_calendario()
        spec["single_table"]["columns"].pop("descricao")  # remove um mapeamento obrigatorio
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                stm.generate(spec, Path(tmp))


if __name__ == "__main__":
    unittest.main(verbosity=2)
