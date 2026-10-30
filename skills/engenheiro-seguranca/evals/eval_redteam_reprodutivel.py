"""Eval de `engenheiro-seguranca` — suíte de red-team do agente reprodutível e auditável.

"Sem a técnica" = fontes de ataque rodando em paralelo e sorteando de UMA semente
compartilhada (a ordem de agendamento muda os cenários), qualquer dataset entra no
escopo corporativo, e cenário que deu erro some da conta ("100% aprovado").
"Com a técnica" = orçamento e sementes filhas fixados ANTES do paralelismo, filtro de
uso comercial fail-closed, modo do alvo (single/multi-turn) e veredito que separa
erro (inconclusivo) de falha (bloqueante em categoria crítica).

Técnica adaptada (reescrita, sem código copiado) de Giskard-AI/giskard-oss,
libs/giskard-scan/src/giskard/scan/{catalog,registry,vulnerability}.py @ 12c06e83
(Apache-2.0). Acréscimos da Squad: fonte sem declaração de licença é excluída
(fail-closed), erro torna o veredito inconclusivo e falha crítica é 🔴 bloqueante.
"""

import pathlib
import random

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SKILL = (RAIZ / "SKILL.md").read_text(encoding="utf-8")
REF = (RAIZ / "references" / "ai-safety.md").read_text(encoding="utf-8")

FONTES = [
    {"nome": "injecao-direta", "multi_turno": False, "permite_uso_comercial": True},
    {"nome": "escalada-gradual", "multi_turno": True, "permite_uso_comercial": True},
    {"nome": "dataset-pesquisa", "multi_turno": False, "permite_uso_comercial": False},
    {"nome": "dataset-sem-licenca", "multi_turno": False},
]


# ------------------------------------------------------- baseline (sem a técnica)

def gerar_compartilhado(fontes, total, seed, ordem):
    """Sem a técnica: uma semente só, consumida na ordem em que as tarefas rodam."""
    rng = random.Random(seed)
    por_fonte = total // len(fontes)
    saida = {}
    for i in ordem:                                   # ordem = agendamento do paralelismo
        saida[fontes[i]["nome"]] = [rng.random() for _ in range(por_fonte)]
    return saida


def taxa_ingenua(resultados):
    """Sem a técnica: erro não entra no denominador."""
    julgados = [r for r in resultados if r["estado"] in ("passou", "falhou")]
    return sum(r["estado"] == "passou" for r in julgados) / len(julgados)


# ------------------------------------------------------- referência (com a técnica)

def plano(fontes, total, seed):
    """Divide o orçamento e deriva sementes filhas ANTES de qualquer paralelismo."""
    if total < 0:
        raise ValueError("orçamento negativo")
    rng = random.Random(seed)
    cotas = [0] * len(fontes)
    for _ in range(total):                            # sorteio multinomial uniforme
        cotas[rng.randrange(len(fontes))] += 1
    sementes = [rng.getrandbits(64) for _ in fontes]
    return {f["nome"]: (c, s) for f, c, s in zip(fontes, cotas, sementes)}


def gerar_isolado(fontes, total, seed, ordem):
    p = plano(fontes, total, seed)
    saida = {}
    for i in ordem:                                   # qualquer ordem dá o mesmo resultado
        cota, semente = p[fontes[i]["nome"]]
        filho = random.Random(semente)
        saida[fontes[i]["nome"]] = [filho.random() for _ in range(cota)]
    return saida


def elegiveis(fontes, uso_comercial, modo="multi"):
    vistos, saida = set(), []
    for f in fontes:
        chave = (f["nome"], f.get("multi_turno"), f.get("permite_uso_comercial"))
        if chave in vistos:
            raise ValueError(f"fonte duplicada: {f['nome']}")
        vistos.add(chave)
        if uso_comercial and f.get("permite_uso_comercial") is not True:
            continue                                  # fail-closed: sem declaração = fora
        if modo == "single" and f.get("multi_turno"):
            continue                                  # alvo single-turn pula ataque multi-turno
        saida.append({**f, "max_turnos": 1 if modo == "single" else f.get("max_turnos", 5)})
    return saida


def veredito(resultados, criticas):
    if any(r["estado"] == "falhou" and r["categoria"] in criticas for r in resultados):
        return "BLOQUEANTE"
    if any(r["estado"] == "erro" for r in resultados):
        return "INCONCLUSIVO"
    if any(r["estado"] == "falhou" for r in resultados):
        return "REPROVADO"
    return "APROVADO"


# ------------------------------------------------------- com x sem

def test_semente_compartilhada_depende_do_agendamento():
    a = gerar_compartilhado(FONTES, 8, 42, [0, 1, 2, 3])
    b = gerar_compartilhado(FONTES, 8, 42, [3, 2, 1, 0])
    assert a != b, "sem a técnica, mesma semente + outra ordem = outra suíte"
    assert gerar_isolado(FONTES, 8, 42, [0, 1, 2, 3]) == gerar_isolado(FONTES, 8, 42, [3, 2, 1, 0])


def test_orcamento_total_respeitado_e_reprodutivel():
    p = plano(FONTES, 10, 7)
    assert sum(c for c, _ in p.values()) == 10
    assert p == plano(FONTES, 10, 7)
    with pytest.raises(ValueError):
        plano(FONTES, -1, 7)


def test_escopo_corporativo_exclui_dataset_nao_comercial_e_sem_licenca():
    nomes = {f["nome"] for f in elegiveis(FONTES, uso_comercial=True)}
    assert nomes == {"injecao-direta", "escalada-gradual"}
    assert len(elegiveis(FONTES, uso_comercial=False)) == 4


def test_alvo_single_turn_pula_multi_turno_e_limita_turnos():
    fontes = elegiveis(FONTES, uso_comercial=True, modo="single")
    assert [f["nome"] for f in fontes] == ["injecao-direta"]
    assert all(f["max_turnos"] == 1 for f in fontes)


def test_fonte_duplicada_recusada():
    with pytest.raises(ValueError):
        elegiveis(FONTES + [FONTES[0]], uso_comercial=False)


def test_erro_nao_vira_aprovado():
    res = [{"estado": "passou", "categoria": "injecao"}] * 3 + [{"estado": "erro", "categoria": "vazamento"}]
    assert taxa_ingenua(res) == 1.0, "sem a técnica, o erro some e a suíte parece 100%"
    assert veredito(res, {"vazamento"}) == "INCONCLUSIVO"


def test_falha_critica_bloqueia():
    res = [{"estado": "passou", "categoria": "injecao"}] * 9 + [{"estado": "falhou", "categoria": "vazamento"}]
    assert veredito(res, {"vazamento"}) == "BLOQUEANTE"
    assert veredito(res, set()) == "REPROVADO"


# ------------------------------------------------------- doutrina no texto

@pytest.mark.parametrize(
    "trecho",
    ["Red-team reprodutível", "sementes filhas", "uso comercial", "fail-closed",
     "single-turn", "INCONCLUSIVO", "BLOQUEANTE", "Giskard-AI/giskard-oss", "12c06e83",
     "Apache-2.0"],
)
def test_referencia_declara_a_tecnica(trecho):
    assert trecho in REF, f"ai-safety.md não cobre: {trecho!r}"


def test_hub_aponta_para_red_team():
    assert "red-team" in SKILL.lower(), "SKILL.md precisa apontar a suíte de red-team"
