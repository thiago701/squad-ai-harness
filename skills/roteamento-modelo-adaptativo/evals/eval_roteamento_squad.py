"""Evals de `roteamento-modelo-adaptativo` — com skill x sem skill.

"Sem skill" = tabela fixa do AGENTS.md §3.1: certa, porém cega a disponibilidade
e sem plano B. Quando o alvo cai, o pipeline para.
"Com skill" = a mesma tabela como PISO + saúde + fallback + aderência.

O teste que mais importa é o do piso: nenhuma otimização de custo pode rotear
design/review/segurança abaixo de `opus`.
"""

import pathlib

import pytest

SKILL = (pathlib.Path(__file__).resolve().parent.parent / "SKILL.md").read_text(encoding="utf-8")

ORDEM = {"haiku": 0, "sonnet": 1, "opus": 2}
PISO = {
    "DISCOVERY": "haiku",
    "BUILD": "sonnet",
    "TEST": "sonnet",
    "DESIGN": "opus",
    "REVIEW": "opus",
    "SEGURANCA": "opus",
}
PESOS = {
    "saude": 0.35, "fitTarefa": 0.25, "costInv": 0.15,
    "contexto": 0.10, "estabilidade": 0.10, "latenciaInv": 0.05,
}
SAUDE = {"FECHADO": 1.0, "MEIO_ABERTO": 0.5, "ABERTO": 0.0}


def score(candidato: dict, pesos: dict = PESOS) -> float:
    if candidato["saude"] == 0.0:          # ABERTO elimina, não desconta
        return 0.0
    total = sum(pesos.values())
    return sum(candidato[f] * p / total for f, p in pesos.items())


def rotear(fase: str, candidatos: list, tier: str | None = None) -> dict | None:
    """Função de referência — piso da §1 + score da §2 + fail-open da §6."""
    piso = PISO[fase]
    elegiveis = [c for c in candidatos if ORDEM[c["modelo"]] >= ORDEM[piso]]
    if not elegiveis:
        return None                        # piso não é filtro de otimização: para e escala
    pool = [c for c in elegiveis if not tier or c.get("tier") == tier] or elegiveis  # fail-open
    vivos = [c for c in pool if c["saude"] > 0.0]
    if not vivos:
        return None
    return max(vivos, key=score)


def cand(modelo, saude="FECHADO", fit=1.0, custo=0.5, ctx=1.0, estab=1.0, lat=0.5, tier=None):
    return {"modelo": modelo, "saude": SAUDE[saude], "fitTarefa": fit, "costInv": custo,
            "contexto": ctx, "estabilidade": estab, "latenciaInv": lat, "tier": tier}


# ------------------------------------------------------- o piso (a trava crítica)

@pytest.mark.parametrize("fase", ["DESIGN", "REVIEW", "SEGURANCA"])
def test_fase_critica_nunca_abaixo_de_opus(fase):
    barato = cand("haiku", custo=1.0, lat=1.0)
    escolhido = rotear(fase, [barato, cand("opus", custo=0.1, lat=0.1)])
    assert escolhido["modelo"] == "opus"


@pytest.mark.parametrize("fase", ["DESIGN", "REVIEW", "SEGURANCA"])
def test_tier_cheap_nao_fura_o_piso(fase):
    pesos_cheap = {**PESOS, "costInv": 0.35, "fitTarefa": 0.10}
    elegiveis = [c for c in [cand("haiku", custo=1.0), cand("opus", custo=0.05)]
                 if ORDEM[c["modelo"]] >= ORDEM[PISO[fase]]]
    assert all(c["modelo"] == "opus" for c in elegiveis)
    assert max(elegiveis, key=lambda c: score(c, pesos_cheap))["modelo"] == "opus"


def test_sem_candidato_no_piso_para_e_escala():
    """Degradação nunca vira 'revisão de segurança em haiku'."""
    assert rotear("SEGURANCA", [cand("haiku"), cand("sonnet")]) is None


# ------------------------------------------------------- saúde x custo

def test_saude_elimina_candidato_aberto():
    aberto = cand("opus", saude="ABERTO", custo=1.0, fit=1.0)
    assert score(aberto) == 0.0


def test_com_skill_desvia_do_especialista_doente():
    """SEM skill (tabela fixa) o pipeline pararia; COM skill ele degrada."""
    escolhido = rotear("BUILD", [cand("sonnet", saude="ABERTO"), cand("opus", saude="FECHADO")])
    assert escolhido is not None and escolhido["modelo"] == "opus"


def test_meio_aberto_perde_para_fechado_equivalente():
    sonda = cand("sonnet", saude="MEIO_ABERTO")
    sadio = cand("sonnet", saude="FECHADO")
    assert score(sadio) > score(sonda)


def test_custo_nao_vence_fit_da_tarefa():
    """P3 é a última prioridade: custo empata, não decide."""
    assert PESOS["fitTarefa"] > PESOS["costInv"]
    barato_ruim = cand("opus", fit=0.3, custo=1.0)
    caro_certo = cand("opus", fit=1.0, custo=0.0)
    assert score(caro_certo) > score(barato_ruim)


def test_saude_tem_o_maior_peso():
    assert PESOS["saude"] == max(PESOS.values())


def test_pesos_somam_um():
    assert abs(sum(PESOS.values()) - 1.0) < 1e-9


# ------------------------------------------------------- fail-open

def test_filtro_que_zera_o_pool_usa_o_pool_inteiro():
    """Roteador nunca pode ser o gargalo (§6)."""
    escolhido = rotear("BUILD", [cand("sonnet", tier="pro")], tier="free")
    assert escolhido is not None, "fail-open falhou: virou indisponibilidade"


# ------------------------------------------------------- doutrina no texto

@pytest.mark.parametrize(
    "trecho",
    ["Piso por fase", "fail-open", "último caminho bom", "Máximo de 2 saltos",
     "painel", "preteridos"],
)
def test_skill_declara_o_mecanismo(trecho):
    assert trecho in SKILL, f"o SKILL.md perdeu o mecanismo: {trecho!r}"


def test_skill_reduz_por_p1_e_justifica():
    """A absorção precisa dizer o que descartou e por quê."""
    assert "13 das 19" in SKILL or "treze estratégias" in SKILL.lower() or "6 fatores, não 14" in SKILL
