"""Eval de `ai-evaluation` -- acerto de ferramentas (tool correctness) em trajetoria de agente.

Lacuna medida: a skill escolhe a regua (programatica x LLM-juiz) e tem painel de juizes, mas nao
tem regua PROGRAMATICA para agente que chama ferramentas: "chamou as tools certas, na ordem
certa, com os argumentos certos?" acaba indo para um juiz LLM caro e instavel. Tecnica absorvida
(confident-ai/deepeval, `metrics/tool_correctness/tool_correctness.py`, Apache-2.0, @5410e382;
modos de trajetoria de langchain-ai/agentevals, MIT, @946ad15b) e reescrita aqui:

1. tres modos: exato (mesma lista, mesma ordem), sem ordem (casamento guloso por nome, cada
   chamada usada uma vez) e com ordem (LCS ponderado);
2. subscore por par = similaridade dos argumentos (chaves iguais / uniao das chaves, recursiva);
3. score = soma dos subscores / numero de esperadas -> e RECALL: chamada extra nao penaliza;
4. contribuicao propria: precisao = casadas / chamadas, publicada ao lado (agente que chama
   tudo tira recall 1 e precisao baixa).

Criterio de ganho (definido antes): os testes de conteudo saem de falha para verde e o exemplo
publicado na referencia bate com o oraculo abaixo; evals antigos da skill seguem verdes.
"""

import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SKILL = (RAIZ / "SKILL.md").read_text(encoding="utf-8")
REFS = "\n".join(p.read_text(encoding="utf-8") for p in sorted((RAIZ / "references").glob("*.md")))
TUDO = SKILL + "\n" + REFS


def sim_args(a: dict, b: dict) -> float:
    if a == b:
        return 1.0
    chaves = set(a) | set(b)
    if not chaves:
        return 1.0
    s = 0.0
    for k in set(a) & set(b):
        if a[k] == b[k]:
            s += 1
        elif isinstance(a[k], dict) and isinstance(b[k], dict):
            s += sim_args(a[k], b[k])
    return s / len(chaves)


def _sub(e, c, args):
    if e[0] != c[0]:
        return 0.0
    return sim_args(e[1], c[1]) if args else 1.0


def acerto(esperadas, chamadas, modo="sem_ordem", args=False):
    """esperadas/chamadas: lista de (nome, dict_args). Devolve (recall, precisao)."""
    if not esperadas:
        r = 1.0 if not chamadas else 0.0
        return r, r
    if modo == "exato":
        ok = len(esperadas) == len(chamadas) and all(_sub(e, c, True) == 1 for e, c in zip(esperadas, chamadas))
        return float(ok), float(ok)
    if modo == "sem_ordem":
        usadas, total, casadas = set(), 0.0, 0
        for e in esperadas:
            melhor, idx = 0.0, None
            for i, c in enumerate(chamadas):
                if i not in usadas and _sub(e, c, args) > melhor:
                    melhor, idx = _sub(e, c, args), i
            if idx is not None:
                usadas.add(idx)
                total += melhor
                casadas += 1
    else:  # com_ordem: LCS ponderado
        n, m = len(esperadas), len(chamadas)
        dp = [[(0.0, 0)] * (m + 1) for _ in range(n + 1)]
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                s = _sub(esperadas[i - 1], chamadas[j - 1], args)
                diag = (dp[i - 1][j - 1][0] + s, dp[i - 1][j - 1][1] + 1) if s > 0 else (-1, 0)
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1], diag)
        total, casadas = dp[n][m]
    return total / len(esperadas), (casadas / len(chamadas) if chamadas else 0.0)


A, B, C = ("A", {}), ("B", {}), ("C", {})


def test_oraculo_modos():
    assert acerto([A, B], [A]) == (0.5, 1.0)
    assert acerto([A, B], [A, B, C]) == (1.0, pytest.approx(2 / 3))   # extra nao baixa o recall
    assert acerto([A, B], [B, A], "exato") == (0.0, 0.0)
    assert acerto([A, B, C], [C, A, B], "com_ordem")[0] == pytest.approx(2 / 3)
    assert acerto([("A", {"q": "x", "n": 1})], [("A", {"q": "x", "n": 2})], args=True)[0] == 0.5
    assert acerto([], []) == (1.0, 1.0) and acerto([], [A]) == (0.0, 0.0)


def test_skill_define_regua_programatica_de_ferramentas():
    t = TUDO.lower()
    assert "acerto de ferramentas" in t
    for modo in ("exato", "sem ordem", "com ordem"):
        assert modo in t
    assert "lcs" in t and "uni" in t          # LCS ponderado e uniao das chaves


def test_skill_avisa_que_e_recall_e_publica_precisao():
    t = TUDO.lower()
    assert "recall" in t and "precis" in t and "chamada extra" in t


def test_exemplo_publicado_bate_com_oraculo():
    # a referencia publica: esperadas [busca, reservar, confirmar], chamadas [busca, listar, reservar, listar]
    m = re.search(r"exemplo de acerto de ferramentas.*?recall\s*=\s*([\d,]+).*?precis\w*\s*=\s*([\d,]+)",
                  TUDO, re.I | re.S)
    assert m, "exemplo numerico ausente"
    rec, prec = (float(x.replace(",", ".")) for x in m.groups())
    E = [("busca", {}), ("reservar", {}), ("confirmar", {})]
    Ch = [("busca", {}), ("listar", {}), ("reservar", {}), ("listar", {})]
    r, p = acerto(E, Ch, "com_ordem")
    assert rec == pytest.approx(r, abs=0.01) and prec == pytest.approx(p, abs=0.01)


def test_skill_indexa_a_referencia():
    assert "acerto de ferramentas" in SKILL.lower()
