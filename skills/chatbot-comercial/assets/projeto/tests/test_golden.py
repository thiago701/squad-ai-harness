"""Golden set — a régua. Falha aqui é regressão de qualidade, não flake."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

MINIMO = {"hit_1": 0.70, "hit_3": 0.85, "cobertura": 0.85, "disciplina": 1.00}


@pytest.fixture(scope="module")
def golden_bruto():
    return json.loads(
        (RAIZ / "golden" / "pousada.json").read_text(encoding="utf-8")
    )


def test_golden_tem_no_minimo_30_perguntas(golden_bruto):
    assert len(golden_bruto["casos"]) >= 30
    assert golden_bruto["negativos"], "sem negativos não dá para medir disciplina"


def test_toda_fonte_do_golden_existe(golden_bruto, config):
    arquivos = {p.stem for p in config.dados_do_vertical.glob("*")}
    for caso in golden_bruto["casos"]:
        assert caso["fonte"] in arquivos, f"fonte inexistente: {caso['fonte']}"


@pytest.mark.golden
def test_metricas_acima_do_minimo(servico):
    from eval_rag import avaliar

    relatorio = avaliar(servico)
    ruins = {m: relatorio[m] for m, alvo in MINIMO.items() if relatorio[m] < alvo}
    assert not ruins, (
        f"regressão: {ruins} (mínimos: {MINIMO})\n"
        f"falhas: {[f['pergunta'] for f in relatorio['falhas']]}\n"
        f"indisciplina: {relatorio['indisciplina']}"
    )


def test_baseline_compara_as_cinco_metricas():
    """O check que manda do loop promete cinco métricas — o script tem que ter cinco."""
    from eval_rag import METRICAS

    assert set(METRICAS) == {"hit_1", "hit_3", "cobertura", "intencao", "disciplina"}


@pytest.mark.golden
def test_negativos_nunca_recebem_resposta_afirmativa(servico, golden_bruto):
    from app.agente import Entrada

    for i, caso in enumerate(golden_bruto["negativos"]):
        resposta = servico.agente.responder(
            Entrada(texto=caso["pergunta"], sessao=f"neg{i}", usuario="u")
        )
        assert resposta.sem_fonte or resposta.recusado or resposta.escalonado, (
            f"{caso['pergunta']!r} recebeu resposta afirmativa: {resposta.texto!r}"
        )
