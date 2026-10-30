"""Eval de `ai-evaluation` -- repeticoes (epocas) e reducao de notas.

Lacuna medida: a skill so conhece "seed fixa por caso". Agente/LLM com temperatura > 0 nao tem
seed reprodutivel; uma unica execucao por caso mede sorte. A tecnica absorvida (inspect_ai,
reducers `pass_at`/`pass_k`/`majority`, MIT) e:

1. rodar k >= 2 repeticoes por caso quando a saida nao e deterministica;
2. reduzir com estimador sem vies -- pass@k (>= 1 acerto) para capacidade e pass^k (todas as k
   acertam) para confiabilidade; o gate de agente usa pass^k;
3. repeticoes sem nota (erro/NaN) reduzindo o total abaixo de k => resultado INDEFINIDO, nunca 1.0;
4. painel de juizes: maioria ESTRITA, abstencao conta no denominador, sem maioria => sem nota.

Criterio de ganho (definido antes): os testes de conteudo saem de falha para verde e o exemplo
numerico publicado na skill bate com o oraculo abaixo (math.comb).
"""

import math
import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SKILL = (RAIZ / "SKILL.md").read_text(encoding="utf-8")
REFS = "\n".join(p.read_text(encoding="utf-8") for p in sorted((RAIZ / "references").glob("*.md")))
TUDO = SKILL + "\n" + REFS


# ---------- oraculo (estimadores sem vies, so stdlib) ----------

def pass_at_k(n: int, c: int, k: int) -> float:
    """P(>=1 acerto em k tiradas sem reposicao de n execucoes com c acertos) -- Chen et al. 2021."""
    if n < k:
        return float("nan")
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """P(todas as k tiradas acertam) = C(c,k)/C(n,k) -- tau-bench."""
    if n < k:
        return float("nan")
    return math.comb(c, k) / math.comb(n, k)


def maioria_estrita(votos: list):
    """None = abstencao (conta no total). Sem valor com > metade => None (sem nota)."""
    total = len(votos)
    for v in set(x for x in votos if x is not None):
        if votos.count(v) * 2 > total:
            return v
    return None


def test_oraculo_pass_at_k():
    assert pass_at_k(10, 7, 3) == pytest.approx(1 - 1 / 120)
    assert pass_at_k(5, 5, 3) == 1.0
    assert math.isnan(pass_at_k(2, 2, 3))          # menos repeticoes validas que k: indefinido


def test_oraculo_pass_hat_k():
    assert pass_hat_k(10, 7, 3) == pytest.approx(35 / 120)
    # o atalho p**k superestima a confiabilidade com n pequeno
    assert (7 / 10) ** 3 > pass_hat_k(10, 7, 3)


def test_oraculo_maioria():
    assert maioria_estrita(["ok", "ok", None]) == "ok"      # 2/3
    assert maioria_estrita(["ok", None, None]) is None      # abstencao nao baixa a regua
    assert maioria_estrita(["ok", "falha"]) is None         # empate: sem nota


# ---------- conteudo da skill (o que o agente vai ler) ----------

def _tem(padrao: str, texto: str = TUDO) -> bool:
    return re.search(padrao, texto, re.I | re.S) is not None


def test_skill_exige_repeticoes_quando_nao_deterministico():
    assert _tem(r"(repeti[cç][aãoõ]|[eé]poca)"), "sem regra de repeticoes por caso"
    assert _tem(r"temperatura|n[aã]o[- ]determin"), "nao diz QUANDO repetir"


def test_skill_define_pass_at_k_e_pass_hat_k():
    assert _tem(r"pass@k"), "pass@k ausente"
    assert _tem(r"pass\^k"), "pass^k ausente"
    assert _tem(r"pass\^k[^\n]{0,160}(todas|confiabilidade)"), "pass^k sem semantica"


def test_skill_gate_de_agente_usa_pass_hat_k():
    assert _tem(r"gate[^\n]{0,200}pass\^k|pass\^k[^\n]{0,200}gate", SKILL), \
        "SKILL.md nao diz que o gate de confiabilidade usa pass^k"


def test_skill_indefinido_quando_faltam_repeticoes():
    assert _tem(r"(menos (de|que) k|< ?k)[^\n]{0,200}indefinid"), \
        "nao trata repeticoes sem nota (NaN) -> indefinido"


def test_skill_painel_maioria_estrita_com_abstencao():
    assert _tem(r"maioria estrita"), "painel de juizes sem regra de maioria estrita"
    assert _tem(r"absten[cç][aã]o[^\n]{0,160}(denominador|total)"), "abstencao fora do denominador"


NUM = r"([0-9]+[.,][0-9]+)"


def test_exemplo_numerico_bate_com_oraculo():
    m = re.search(r"n ?= ?(\d+)[^\n]{0,20}c ?= ?(\d+)[^\n]{0,20}k ?= ?(\d+)[^\n]*?pass@\d ?= ?" + NUM
                  + r"[^\n]*?pass\^\d ?= ?" + NUM, TUDO)
    assert m, "sem exemplo numerico n/c/k -> pass@k / pass^k"
    n, c, k = (int(m.group(i)) for i in (1, 2, 3))
    pa, ph = (float(m.group(i).replace(",", ".")) for i in (4, 5))
    assert pa == pytest.approx(pass_at_k(n, c, k), abs=5e-3)
    assert ph == pytest.approx(pass_hat_k(n, c, k), abs=5e-3)
