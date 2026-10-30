"""Eval de `roteamento-modelo-adaptativo` v1.1.0 -- JEV Fork Layer (`sharp -> code` vs `split -> LLM`).

Valida:
1. Corte calibrado `sharp` (p1 >= 0.75 e margem >= 0.20) executando em `code` vs `split` escalando para `sonnet 5.5`.
2. Resolucao deterministica do fork `retry or stop` (`retry once` | `switch tool` | `stop + ask`).
3. Calculo da taxa de bypass de LLM (`resumir_economia_forks`) e presenca da doutrina no hub/reference.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

_RAIZ = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("jev_fork_layer", _RAIZ / "scripts" / "jev_fork_layer.py")
mod = importlib.util.module_from_spec(_spec)
sys.modules["jev_fork_layer"] = mod
_spec.loader.exec_module(mod)


def test_fork_sharp_roda_em_codigo_sem_llm():
    dec = mod.avaliar_fork("which agent", {"reviewer": 0.94, "planner": 0.04, "fixer": 0.02})
    assert dec.escolhido == "reviewer"
    assert dec.regime == "sharp"
    assert dec.executor == "code"
    assert "p=0.94 sharp -> code" in dec.log


def test_fork_split_escala_para_sonnet():
    dec = mod.avaliar_fork("which skill", {"review-pr": 0.52, "research": 0.38, "commit-msg": 0.10})
    assert dec.escolhido == "review-pr"
    assert dec.regime == "split"
    assert dec.executor == "sonnet 5.5"
    assert "p=0.52 split -> sonnet 5.5" in dec.log


def test_margem_estreita_mesmo_com_p_alto_vira_split():
    dec = mod.avaliar_fork("which agent", {"reviewer": 0.76, "fixer": 0.65}, limiar_sharp=0.75, margem_min=0.20)
    assert dec.regime == "split"
    assert dec.executor == "sonnet 5.5"


def test_retry_or_stop_para_em_erro_deterministico_ou_terminal():
    for erro in ("teste_falhou", "arquivo_nao_existe", "exit_2_hook", "credito_esgotado"):
        dec = mod.decidir_retry_or_stop(erro, tentativa=0)
        assert dec.escolhido == "stop + ask"
        assert dec.regime == "sharp"
        assert dec.executor == "code"


def test_retry_or_stop_troca_ferramenta_quando_alternativa_disponivel():
    dec = mod.decidir_retry_or_stop("timeout", tentativa=1, tem_tool_alternativa=True)
    assert dec.escolhido == "switch tool"
    assert dec.regime == "sharp"
    assert dec.executor == "code"


def test_retry_or_stop_tenta_uma_vez_em_erro_transitorio_inicial():
    dec = mod.decidir_retry_or_stop("429", tentativa=0, tem_tool_alternativa=False)
    assert dec.escolhido == "retry once"
    assert dec.regime == "sharp"
    assert dec.executor == "code"


def test_resumo_economia_calcula_bypass_correto():
    d1 = mod.avaliar_fork("which agent", {"reviewer": 0.94, "planner": 0.06})
    d2 = mod.avaliar_fork("which skill", {"commit-msg": 0.89, "research": 0.11})
    d3 = mod.avaliar_fork("which agent", {"planner": 0.54, "fixer": 0.46})
    resumo = mod.resumir_economia_forks([d1, d2, d3])
    assert resumo == {"total_forks": 3, "sharp_code": 2, "split_llm": 1, "bypass_llm_pct": 66.7}


def test_skill_documenta_jev_fork_layer():
    hub = (_RAIZ / "SKILL.md").read_text(encoding="utf-8")
    ref = (_RAIZ / "references" / "estrategias-e-score.md").read_text(encoding="utf-8")
    assert "version: 1.1.0" in hub
    for trecho in ("which agent", "which skill", "retry or stop", "sharp", "split"):
        assert trecho in hub and trecho in ref
