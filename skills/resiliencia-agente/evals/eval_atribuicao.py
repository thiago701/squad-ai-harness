"""
Eval de atribuição de culpa no disjuntor — resiliencia-agente.

Critério de ganho (definido ANTES da edição, 15/10/2026):
  1. Parte executável: a regra descrita na v1.0 (abre ao atingir N falhas sistêmicas na
     janela, contando todo timeout) é comparada com a regra nova (timeout que estoura o
     orçamento imposto pelo PRÓPRIO orquestrador não conta; e N falhas só abrem se a taxa
     de falha na janela passar de 50%) em 8 cenários. Métrica: decisões erradas
     (abertura indevida de especialista saudável ou disjuntor que não abre).
     Ingênua: 4/8 erradas; nova: 0/8.
  2. Parte textual: o hub declara as duas regras e a procedência.

Técnica reescrita a partir de BerriAI/litellm router_utils/cooldown_handlers.py @d36b66e (MIT).
Rodar: python -m pytest skills/resiliencia-agente/evals/eval_atribuicao.py -q
"""
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
HUB = (RAIZ / "SKILL.md").read_text(encoding="utf-8")
BASELINE_BYTES = 12024  # SKILL.md 1.0.0 medido em 15/10/2026
ORCAMENTO_BYTES = 1400
LIMIAR = {"opus": 3, "sonnet": 5, "haiku": 8}
SISTEMICOS = {"timeout", "indisponivel", "erro_interno"}


def _f(tipo, dur=None):
    return {"tipo": tipo, "dur_s": dur}


def abre_ingenuo(perfil, falhas, sucessos, orcamento_s):
    sistemicas = [f for f in falhas if f["tipo"] in SISTEMICOS]
    return len(sistemicas) >= LIMIAR[perfil]


def abre(perfil, falhas, sucessos, orcamento_s):
    def culpa_do_chamador(f):
        return f["tipo"] == "timeout" and f["dur_s"] is not None and f["dur_s"] >= orcamento_s
    sistemicas = [f for f in falhas if f["tipo"] in SISTEMICOS and not culpa_do_chamador(f)]
    total = len(sistemicas) + sucessos
    return len(sistemicas) >= LIMIAR[perfil] and len(sistemicas) / total > 0.5


T_ORC = [_f("timeout", 30.0)] * 3          # estourou o orçamento de 30 s do orquestrador
T_PROV = [_f("timeout", 4.0)] * 3          # o provedor desistiu antes do orçamento
CASOS = [
    ("timeout do proprio orcamento", "opus", T_ORC, 0, False),
    ("timeout do provedor", "opus", T_PROV, 0, True),
    ("3 falhas em 40 tentativas", "opus", [_f("erro_interno")] * 3, 37, False),
    ("3 falhas em 4 tentativas", "opus", [_f("indisponivel")] * 3, 1, True),
    ("5 de 10 (50% nao passa de 50%)", "sonnet", [_f("erro_interno")] * 5, 5, False),
    ("6 de 7", "sonnet", [_f("erro_interno")] * 6, 1, True),
    ("2 falhas so", "opus", [_f("indisponivel")] * 2, 0, False),
    ("orcamento misto: 2 do chamador + 1 do provedor", "opus",
     [_f("timeout", 30.0)] * 2 + [_f("timeout", 3.0)], 0, False),
]


@pytest.mark.parametrize("nome,perfil,falhas,sucessos,certo", CASOS, ids=[c[0] for c in CASOS])
def test_regra_nova_decide_certo(nome, perfil, falhas, sucessos, certo):
    assert abre(perfil, falhas, sucessos, 30.0) is certo


def _erros(fn):
    return sum(fn(p, f, s, 30.0) is not c for _, p, f, s, c in CASOS)


def test_placar_decisoes_erradas():
    assert (_erros(abre_ingenuo), _erros(abre)) == (4, 0)


def _secao():
    return HUB.split("## 1. Camada 1", 1)[1].split("\n## ", 1)[0]


def test_hub_timeout_do_orcamento_nao_conta():
    s = _secao().lower()
    assert "orçamento" in s and "chamador" in s


def test_hub_taxa_minima():
    assert "50%" in _secao()


def test_hub_registra_procedencia():
    assert "BerriAI/litellm" in HUB and "MIT" in HUB


def test_orcamento_de_tokens():
    assert len(HUB.encode("utf-8")) - BASELINE_BYTES <= ORCAMENTO_BYTES


def test_linha_de_defesa_intacta():
    assert HUB.count("## 🛡️ Linha de Defesa de Prompt") == 1
