"""Eval de `ai-evaluation` -- confiabilidade do painel de juizes (flip rate e entropia).

Lacuna medida: a skill decide o veredito do painel (maioria estrita, abstencao no denominador),
mas nao mede QUAO estavel e esse veredito. Um 2x1 e um 3x0 viram a mesma nota. A tecnica
absorvida (truera/trulens 2.16.0, `feedback/jury.py`, MIT, @a7f242b) e reescrita aqui:

1. sobre os votos VALIDOS (abstencao fica fora e e contada a parte), dividir em passa/nao passa
   pelo limiar (>=);
2. flip_rate = 1 - max(passa, nao_passa) / validos  -> 0 unanime, 0,5 empate;
3. entropia = -sum(p * log2 p) sobre as duas contagens -> 0 a 1 bit;
4. o mesmo juiz repetido com temperatura 0 da flip 0 por construcao: isso nao prova estabilidade.

Criterio de ganho (definido antes): os testes de conteudo saem de falha para verde e o exemplo
numerico publicado bate com o oraculo abaixo.
"""

import math
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SKILL = (RAIZ / "SKILL.md").read_text(encoding="utf-8")
REFS = "\n".join(p.read_text(encoding="utf-8") for p in sorted((RAIZ / "references").glob("*.md")))
TUDO = SKILL + "\n" + REFS


def confiabilidade(notas: list, limiar: float = 0.5) -> dict:
    """None = abstencao (fora do calculo, contada a parte)."""
    validos = [n for n in notas if n is not None]
    if not validos:
        return {"validos": 0, "abstencoes": len(notas), "flip_rate": None, "entropia": None}
    passa = sum(1 for n in validos if n >= limiar)
    contagens = (len(validos) - passa, passa)
    ent = -sum((c / len(validos)) * math.log2(c / len(validos)) for c in contagens if c)
    return {"validos": len(validos), "abstencoes": len(notas) - len(validos),
            "flip_rate": 1 - max(contagens) / len(validos), "entropia": ent}


def test_oraculo_unanime_empate_e_dois_a_um():
    assert confiabilidade([0.9, 0.8, 0.7])["flip_rate"] == 0
    r = confiabilidade([0.2, 0.4, 0.6, 0.9])
    assert r["flip_rate"] == 0.5 and r["entropia"] == pytest.approx(1.0)
    r = confiabilidade([0.2, 0.7, 0.9])
    assert r["flip_rate"] == pytest.approx(1 / 3) and r["entropia"] == pytest.approx(0.9183, abs=1e-4)


def test_oraculo_abstencao_fica_fora_e_e_contada():
    r = confiabilidade([0.8, None, 1.0])
    assert r["validos"] == 2 and r["abstencoes"] == 1 and r["flip_rate"] == 0
    assert confiabilidade([None, None])["flip_rate"] is None
    assert confiabilidade([0.5])["flip_rate"] == 0          # limiar e inclusivo (>=)


def test_skill_define_flip_rate_e_entropia():
    assert "flip_rate" in TUDO and "entropia" in TUDO.lower()
    assert "1 − max" in TUDO or "1 - max" in TUDO


def test_skill_publica_exemplo_que_bate_com_oraculo():
    r = confiabilidade([0.2, 0.7, 0.9])
    assert f"{r['flip_rate']:.3f}".replace(".", ",") in TUDO     # 0,333
    assert f"{r['entropia']:.3f}".replace(".", ",") in TUDO      # 0,918


def test_skill_separa_veredito_de_confiabilidade_e_alerta_temperatura_zero():
    baixo = TUDO.lower()
    assert "abstenç" in baixo and "contada à parte" in baixo
    assert "temperatura 0" in baixo and "não prova" in baixo
