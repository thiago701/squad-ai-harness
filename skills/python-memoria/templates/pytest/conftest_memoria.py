"""conftest de orçamento de memória — copie para o `tests/` do projeto (ou importe de lá).

Dá ao projeto duas coisas, sem plugin externo:

  1. fixture `orcamento_memoria` — context manager já ligado ao tracemalloc + RSS:

         def test_processar_lote(orcamento_memoria, tmp_path):
             with orcamento_memoria(max_pico_mb=64, rotulo="processar_lote"):
                 processar_lote(tmp_path / "entrada.csv")

  2. marker `@pytest.mark.memoria(max_pico_mb=…, max_rss_delta_mb=…)` — mede o teste inteiro:

         @pytest.mark.memoria(max_pico_mb=32)
         def test_parser_streaming(): ...

Com `pytest-memray` instalado, prefira `@pytest.mark.limit_memory("32 MB")` (mede alocações nativas e
gera flamegraph); este conftest é a rede mínima, stdlib, que roda em qualquer CI/Lambda-like.
Localização da biblioteca: `skills/python-memoria/scripts` (Squad instalada) — ajuste `SQUAD_AI_HOME`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_CANDIDATOS = [Path(__file__).resolve().parents[1] / "skills" / "python-memoria" / "scripts"]
if os.environ.get("SQUAD_AI_HOME"):
    _CANDIDATOS.append(Path(os.environ["SQUAD_AI_HOME"]) / "skills" / "python-memoria" / "scripts")
for _c in _CANDIDATOS:
    if (_c / "memoria" / "orcamento.py").is_file() and str(_c) not in sys.path:
        sys.path.insert(0, str(_c))

from memoria.orcamento import orcamento  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "memoria(max_pico_mb, max_rss_delta_mb): orçamento de memória do teste (python-memoria)")


@pytest.fixture
def orcamento_memoria():
    """Fixture: `with orcamento_memoria(max_pico_mb=64) as m: ...` — `m.pico_mb`, `m.rss_delta_mb` após o bloco."""
    return orcamento


@pytest.hookimpl(wrapper=True)          # new-style wrapper (pytest ≥ 8): pode levantar OrcamentoExcedido
def pytest_runtest_call(item):
    marker = item.get_closest_marker("memoria")
    if marker is None:
        return (yield)
    with orcamento(marker.kwargs.get("max_pico_mb"), max_rss_delta_mb=marker.kwargs.get("max_rss_delta_mb"),
                   rotulo=item.name, imprimir=bool(marker.kwargs.get("imprimir"))):
        return (yield)
