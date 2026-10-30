"""Eval de `orquestrador-multiagente` v1.2.0 -- veredito out-of-sample, plato vs pico isolado e ledger.

Valida os tres mecanismos absorvidos em v1.2.0:
1. Contrato de veredito out-of-sample (`DATA_VALIDATED`, `TRADE_OFF`, `NO_EDGE`) com recusa de random split.
2. Classificacao de varredura em grade (`plateau` vs `isolated_peak` vs `none`).
3. Guarda das 4 leis invariantes do ledger (`research.md`), bloqueando reteste de `status: dead` sem
   razao nova e exigindo sobrevivencia ao `skeptic` antes de `accepted`.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

_RAIZ = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "veredito_plat_ledger", _RAIZ / "scripts" / "veredito_plat_ledger.py"
)
mod = importlib.util.module_from_spec(_spec)
sys.modules["veredito_plat_ledger"] = mod
_spec.loader.exec_module(mod)


def test_veredito_data_validated_exige_ambos_eixos_nas_duas_janelas():
    treino = mod.JanelaMetrica(crescimento=8.0, risco_ajustado=0.70, ano_inicio=1999, ano_fim=2014)
    held = mod.JanelaMetrica(crescimento=7.2, risco_ajustado=0.61, ano_inicio=2015, ano_fim=2026)
    b_tr = mod.JanelaMetrica(crescimento=6.8, risco_ajustado=0.44, ano_inicio=1999, ano_fim=2014)
    b_hd = mod.JanelaMetrica(crescimento=6.8, risco_ajustado=0.44, ano_inicio=2015, ano_fim=2026)
    assert mod.avaliar_veredito(treino, held, b_tr, b_hd) == mod.DATA_VALIDATED


def test_veredito_trade_off_quando_bate_so_risco_ajustado():
    treino = mod.JanelaMetrica(crescimento=6.8, risco_ajustado=0.65, ano_inicio=1999, ano_fim=2014)
    held = mod.JanelaMetrica(crescimento=6.8, risco_ajustado=0.61, ano_inicio=2015, ano_fim=2026)
    bench = mod.JanelaMetrica(crescimento=6.8, risco_ajustado=0.44, ano_inicio=1999, ano_fim=2014)
    bench_h = mod.JanelaMetrica(crescimento=6.8, risco_ajustado=0.44, ano_inicio=2015, ano_fim=2026)
    assert mod.avaliar_veredito(treino, held, bench, bench_h) == mod.TRADE_OFF


def test_veredito_no_edge_quando_falha_no_held_out():
    treino = mod.JanelaMetrica(crescimento=12.0, risco_ajustado=1.1, ano_inicio=1999, ano_fim=2014)
    held = mod.JanelaMetrica(crescimento=4.0, risco_ajustado=0.20, ano_inicio=2015, ano_fim=2026)
    bench = mod.JanelaMetrica(crescimento=6.8, risco_ajustado=0.44, ano_inicio=1999, ano_fim=2014)
    bench_h = mod.JanelaMetrica(crescimento=6.8, risco_ajustado=0.44, ano_inicio=2015, ano_fim=2026)
    assert mod.avaliar_veredito(treino, held, bench, bench_h) == mod.NO_EDGE


def test_split_aleatorio_ou_sobreposto_e_recusado():
    treino = mod.JanelaMetrica(8.0, 0.7, 1999, 2016)
    held = mod.JanelaMetrica(8.0, 0.7, 2015, 2026)
    with pytest.raises(mod.ViolacaoSplitTemporal):
        mod.avaliar_veredito(treino, held, treino, held, modo_split="random")
    with pytest.raises(mod.ViolacaoSplitTemporal):
        mod.avaliar_veredito(treino, held, treino, held, modo_split="temporal")


def test_classifica_plato_robusto_vs_pico_isolado():
    v, t, n = mod.DATA_VALIDATED, mod.TRADE_OFF, mod.NO_EDGE
    grade_plato = [
        [n, n, t, n],
        [t, v, v, t],
        [t, v, v, v],
        [n, v, v, t],
    ]
    res_plato = mod.classificar_grade(grade_plato)
    assert res_plato["forma"] == "plateau"
    assert res_plato["conectados"] >= 6

    grade_pico = [
        [n, t, n, n],
        [t, v, t, n],
        [n, t, n, v],
    ]
    res_pico = mod.classificar_grade(grade_pico)
    assert res_pico["forma"] == "isolated_peak"


def test_ledger_bloqueia_reteste_de_dead_sem_razao_nova():
    morto = {"id": "Q-012", "status": "dead", "verdict": mod.NO_EDGE}
    with pytest.raises(mod.ViolacaoLedger, match="Lei 3"):
        mod.validar_transicao_ledger(morto, {"id": "Q-012", "status": "open", "verdict": mod.TRADE_OFF})
    reaberto = mod.validar_transicao_ledger(
        morto,
        {"id": "Q-012", "status": "open", "verdict": mod.TRADE_OFF, "new_reason": "novo dataset 2026"},
    )
    assert reaberto["status"] == "open"


def test_ledger_exige_plato_e_skeptic_antes_de_accepted():
    with pytest.raises(mod.ViolacaoLedger, match="plateau"):
        mod.validar_transicao_ledger(
            None,
            {
                "status": "accepted",
                "verdict": mod.DATA_VALIDATED,
                "sweep_forma": "isolated_peak",
                "skeptic": "testado em held-out",
            },
        )
    with pytest.raises(mod.ViolacaoLedger, match="Lei 4"):
        mod.validar_transicao_ledger(
            None,
            {
                "status": "accepted",
                "verdict": mod.DATA_VALIDATED,
                "sweep_forma": "plateau",
                "skeptic": "",
            },
        )
    aceito = mod.validar_transicao_ledger(
        None,
        {
            "status": "accepted",
            "verdict": mod.DATA_VALIDATED,
            "sweep_forma": "plateau",
            "skeptic": "held-out 2015-2026 + pior drawdown 2022: sobreviveu",
            "skeptic_broke": False,
        },
    )
    assert aceito["status"] == "accepted"


def test_skill_e_reference_documentam_v120():
    hub = (_RAIZ / "SKILL.md").read_text(encoding="utf-8")
    ref = (_RAIZ / "references" / "equipe-pesquisa-vereditos-ledger.md").read_text(encoding="utf-8")
    assert "version: 1.2.0" in hub
    assert "equipe-pesquisa-vereditos-ledger.md" in hub
    for termo in ("DATA_VALIDATED", "isolated_peak", "plateau", "THE LINE", "skeptic", "sweeper"):
        assert termo in hub and termo in ref
