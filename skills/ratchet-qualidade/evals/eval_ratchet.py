"""Evals de `ratchet-qualidade` — com skill x sem skill.

"Sem skill" = gate de valor absoluto (`está acima de 60%?`). Passa em retrocesso.
"Com skill" = catraca (`está pior do que estava?`). Reprova retrocesso.

Os testes abaixo provam que a diferença é real e que as travas anti-afrouxamento
descritas no SKILL.md são executáveis, não retórica.
"""

import json
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SKILL = (RAIZ / "SKILL.md").read_text(encoding="utf-8")
SEMENTE = RAIZ / "templates" / "quality-baseline.seed.json"


class BaselineIncompleto(Exception):
    """Regra-zero: catraca sobre número não medido é palpite congelado."""


def avalia(metrica: dict, atual: float) -> bool:
    """Função de referência — a semântica de catraca da §1 do SKILL.md."""
    base = metrica.get("value")
    if base is None:
        raise BaselineIncompleto("baseline não medido")
    eps = metrica.get("eps", 0)
    if metrica["direction"] == "up":
        return atual >= base - eps
    return atual <= base + eps


def gate_absoluto(piso: float, atual: float) -> bool:
    """Baseline SEM skill: só checa o piso."""
    return atual >= piso


# ------------------------------------------------------- com x sem

def test_catraca_pega_regressao_que_o_piso_deixa_passar():
    """O caso que justifica a skill inteira."""
    metrica = {"value": 80.8, "direction": "up", "eps": 0}
    caiu_mas_acima_do_piso = 72.0
    assert gate_absoluto(60.0, caiu_mas_acima_do_piso) is True, "piso aprova o retrocesso"
    assert avalia(metrica, caiu_mas_acima_do_piso) is False, "catraca precisa reprovar"


def test_direcao_down_para_metrica_de_menos_e_melhor():
    violacoes = {"value": 88, "direction": "down", "eps": 0}
    assert avalia(violacoes, 80) is True     # melhorou
    assert avalia(violacoes, 88) is True     # empatou
    assert avalia(violacoes, 95) is False    # piorou


def test_eps_absorve_ruido_mas_nao_regressao_real():
    m = {"value": 78.1, "direction": "up", "eps": 1.5}
    assert avalia(m, 77.0) is True      # dentro do ruído do medidor
    assert avalia(m, 70.0) is False     # regressão real


def test_baseline_nao_medido_recusa_rodar():
    """Regra-zero da V3: estimativa nunca é apresentada como medição."""
    with pytest.raises(BaselineIncompleto):
        avalia({"value": None, "direction": "up"}, 90.0)


# ------------------------------------------------------- a semente

def test_semente_existe_e_e_json_valido():
    assert SEMENTE.is_file(), "template de baseline sumiu"
    json.loads(SEMENTE.read_text(encoding="utf-8"))


def test_semente_marca_o_que_ainda_nao_foi_medido():
    d = json.loads(SEMENTE.read_text(encoding="utf-8"))
    pendentes = [k for k, v in d["metrics"].items() if v.get("value") is None]
    assert pendentes, "a semente precisa declarar o que falta medir"
    for k in pendentes:
        assert any(campo.startswith("_pendente_medicao") for campo in d["metrics"][k]), \
            f"{k}: valor nulo sem justificativa de pendência"


def test_toda_metrica_tem_direcao_valida():
    d = json.loads(SEMENTE.read_text(encoding="utf-8"))
    for nome, m in d["metrics"].items():
        assert m.get("direction") in ("up", "down"), f"{nome}: direction ausente/inválida"


def test_metricas_medidas_da_semente_avaliam():
    """As que já têm número precisam funcionar de ponta a ponta."""
    d = json.loads(SEMENTE.read_text(encoding="utf-8"))
    medidas = {k: v for k, v in d["metrics"].items() if v.get("value") is not None}
    assert medidas, "a semente precisa ter ao menos uma métrica realmente medida"
    for nome, m in medidas.items():
        pior = m["value"] + 50 if m["direction"] == "up" else m["value"] - 50
        melhor = m["value"] - 50 if m["direction"] == "up" else m["value"] + 50
        assert avalia(m, pior) is True, f"{nome}: melhora foi reprovada"
        assert avalia(m, melhor) is False, f"{nome}: piora foi aprovada"


# ------------------------------------------------------- doutrina no texto

@pytest.mark.parametrize(
    "trecho",
    [
        "genuinamente melhorou",        # --update só quando melhora (N2)
        "anti-Goodhart",                # as 4 defesas
        "anti-alucinação",              # a categoria rara
        # o incidente concreto que motiva o gate — citado SEM o nome literal da skill fantasma:
        # a limpeza de drift de 22/09 (0 ocorrencias de `arquiteto-finops` em SKILL.md) e deliberada,
        # e o eval exigir o literal tornava o gate vermelho por uma decisao correta (84d51c9).
        "skill de FinOps que nunca",
        "consultivo",                   # ciclo consultivo -> bloqueante
        "Pulo gracioso",                # infra faltando não bloqueia PR
        "expira_em",                    # allowlist com validade
    ],
)
def test_skill_declara_a_trava(trecho):
    assert trecho in SKILL, f"o SKILL.md perdeu a trava: {trecho!r}"


def test_skill_proibe_afrouxar_para_passar():
    assert "Afrouxar baseline" in SKILL or "afrouxar" in SKILL.lower()
    assert "N2" in SKILL, "precisa amarrar a proibição à regra N2 do RULES.md"
