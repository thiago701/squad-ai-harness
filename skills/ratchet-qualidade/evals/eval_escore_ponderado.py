"""Eval de `ratchet-qualidade` — escore agregado ponderado, com bloqueio FORA da média.

"Sem a técnica" = média simples de checagens: nove verdes "compensam" uma falha de
segurança e o conjunto passa. "Com a técnica" = checagem bloqueante decide sozinha,
o resto vira um escore ponderado (peso 0 só mede) com limiar e catraca própria.

Técnica adaptada (reescrita, sem código copiado) de promptfoo/promptfoo,
src/assertions/assertionsResult.ts @ c0b88a32 (MIT). O acréscimo da Squad é manter
bloqueantes fora da média e pôr o escore agregado sob catraca (direction/eps).
"""

import math
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SKILL = (RAIZ / "SKILL.md").read_text(encoding="utf-8")
CATALOGO = (RAIZ / "references" / "catalogo-gates.md").read_text(encoding="utf-8")


def media_simples(checks: list[dict]) -> float:
    """Baseline SEM a técnica: tudo entra na média, inclusive segurança."""
    return sum(c["escore"] for c in checks) / len(checks)


def veredito(checks: list[dict], limiar: float | None = None) -> tuple[bool, float]:
    """Função de referência da seção 'Escore agregado ponderado' do catálogo."""
    if any(c.get("bloqueante") and not c["passou"] for c in checks):
        return False, 0.0                                   # bloqueio não negocia com média
    ponderaveis = [c for c in checks if not c.get("bloqueante")]
    soma_pesos = sum(c.get("peso", 1) for c in ponderaveis)
    soma = sum(c["escore"] * c.get("peso", 1) for c in ponderaveis)
    if not (math.isfinite(soma) and math.isfinite(soma_pesos)):
        return False, 0.0                                   # fail-closed
    escore = soma / soma_pesos if soma_pesos > 0 else 0.0
    if limiar is None:                                      # sem limiar: qualquer falha reprova
        return all(c["passou"] for c in ponderaveis), escore
    return escore >= limiar, escore                         # com limiar: o agregado decide


def catraca(baseline: dict, atual: float) -> bool:
    """Mesma semântica de `avalia` do eval_ratchet.py (direction/eps)."""
    if baseline["direction"] == "up":
        return atual >= baseline["value"] - baseline.get("eps", 0)
    return atual <= baseline["value"] + baseline.get("eps", 0)


def _verde(nome, peso=1):
    return {"nome": nome, "escore": 1.0, "passou": True, "peso": peso}


SEGURANCA_FALHOU = {"nome": "sast", "escore": 0.0, "passou": False, "bloqueante": True}


# ------------------------------------------------------- com x sem

def test_media_simples_deixa_seguranca_ser_compensada():
    checks = [_verde(f"c{i}") for i in range(9)] + [SEGURANCA_FALHOU]
    assert media_simples(checks) >= 0.8, "sem a técnica, 0.9 passa no limiar 0.8"
    passou, _ = veredito(checks, limiar=0.8)
    assert passou is False, "bloqueante falhando precisa reprovar, qualquer que seja a média"


def test_peso_zero_mede_sem_mover_o_agregado():
    base = [_verde("lint", 2), {"nome": "estilo", "escore": 0.5, "passou": False, "peso": 1}]
    com_consultivo = base + [{"nome": "novo", "escore": 0.0, "passou": False, "peso": 0}]
    assert veredito(base, 0.8)[1] == pytest.approx(veredito(com_consultivo, 0.8)[1])


def test_limiar_decide_quando_definido():
    checks = [_verde("a", 3), {"nome": "b", "escore": 0.4, "passou": False, "peso": 1}]
    assert veredito(checks)[0] is False             # sem limiar, a falha individual reprova
    passou, escore = veredito(checks, limiar=0.8)
    assert escore == pytest.approx(0.85) and passou is True


def test_nao_finito_falha_fechado():
    checks = [{"nome": "x", "escore": float("inf"), "passou": True, "peso": 1}]
    assert veredito(checks, limiar=0.0) == (False, 0.0)


def test_agregado_sob_catraca_pega_queda_acima_do_limiar():
    """O agregado é métrica de catraca: cair de 0.95 para 0.85 reprova mesmo acima de 0.8."""
    base = {"value": 0.95, "direction": "up", "eps": 0.02}
    checks = [_verde("a", 3), {"nome": "b", "escore": 0.4, "passou": False, "peso": 1}]
    passou, escore = veredito(checks, limiar=0.8)
    assert passou is True and catraca(base, escore) is False


# ------------------------------------------------------- doutrina no texto

@pytest.mark.parametrize(
    "trecho",
    ["Escore agregado ponderado", "fora da média", "peso 0", "limiar", "fail-closed",
     "promptfoo", "c0b88a32", "MIT"],
)
def test_catalogo_declara_a_tecnica(trecho):
    assert trecho in CATALOGO, f"catalogo-gates.md não cobre: {trecho!r}"


def test_hub_aponta_para_a_tecnica():
    assert "escore agregado" in SKILL.lower(), "SKILL.md precisa citar o escore agregado"
