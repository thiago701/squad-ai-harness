"""Confianca deterministica de instintos (stdlib, sem LLM, sem hooks).

Tecnica reescrita do continuous-learning-v2 do affaan-m/everything-claude-code (licenca MIT,
commit 90606c8): a confianca deixa de ser palpite e passa a ser calculada a partir da
evidencia. Uso no `/aprender` (atribuir/reforcar) e no `/evoluir` (promover, podar, agrupar).

    python scripts/confianca.py 6 --contradicoes 3      # -> 0.4 hipotese
"""

from __future__ import annotations

import argparse
import re

TETO = 0.9  # escala da skill: 0.9 = regra firme
FAIXAS_INICIAIS = ((11, 0.85), (6, 0.7), (3, 0.5), (1, 0.3))
REFORCO, CONTRADICAO, DECAIMENTO_SEMANA = 0.05, 0.10, 0.02
PROMOCAO_MEDIA, PROMOCAO_PROJETOS = 0.8, 2
AVISO_DIAS, EXPIRA_DIAS = 23, 30
STOPWORDS = frozenset(
    "a o as os ao aos de da do das dos e em no na nos nas um uma para por com sem que se "
    "sempre the an and or of to in on for with when while is be".split()
)


def confianca(observacoes: int, confirmacoes: int = 0, contradicoes: int = 0,
              semanas_sem_ver: int = 0) -> float:
    """Inicial pela contagem de observacoes; ajustes lineares; limitada a [0, TETO]."""
    if observacoes < 1:
        raise ValueError("instinto exige ao menos 1 observacao")
    base = next(c for minimo, c in FAIXAS_INICIAIS if observacoes >= minimo)
    valor = (base + REFORCO * confirmacoes - CONTRADICAO * contradicoes
             - DECAIMENTO_SEMANA * semanas_sem_ver)
    return round(min(TETO, max(0.0, valor)), 2)


def faixa(c: float) -> str:
    if c < 0.5:
        return "hipotese"
    if c < 0.7:
        return "sugerir"
    if c < PROMOCAO_MEDIA:
        return "aplicar_com_revisao"
    return "candidato_promocao"


def promover_global(ocorrencias: list[tuple[str, float]]) -> bool:
    """2+ projetos distintos (maior confianca por projeto) com media >= 0.8."""
    por_projeto: dict[str, float] = {}
    for projeto, c in ocorrencias:
        por_projeto[projeto] = max(c, por_projeto.get(projeto, 0.0))
    if len(por_projeto) < PROMOCAO_PROJETOS:
        return False
    return sum(por_projeto.values()) / len(por_projeto) >= PROMOCAO_MEDIA - 1e-9


def estado_pendente(dias_sem_revisao: int) -> str:
    if dias_sem_revisao >= EXPIRA_DIAS:
        return "expirado"
    return "aviso" if dias_sem_revisao >= AVISO_DIAS else "ok"


def _palavras(texto: str) -> set[str]:
    return {p for p in re.findall(r"\w+", texto.lower()) if p not in STOPWORDS}


def parecidos(a: str, b: str) -> bool:
    """Sobreposicao |A&B|/min(|A|,|B|) >= 0.5 e 2+ palavras em comum.

    Jaccard puniria o gatilho curto contido no longo; a sobreposicao nao."""
    pa, pb = _palavras(a), _palavras(b)
    comum = len(pa & pb)
    return comum >= 2 and comum / max(1, min(len(pa), len(pb))) >= 0.5


def agrupar(gatilhos: list[str]) -> list[list[int]]:
    """Grupos (indices) por fecho transitivo de `parecidos`; ordem deterministica."""
    pai = list(range(len(gatilhos)))

    def raiz(i: int) -> int:
        while pai[i] != i:
            pai[i] = pai[pai[i]]
            i = pai[i]
        return i

    for i in range(len(gatilhos)):
        for j in range(i + 1, len(gatilhos)):
            if parecidos(gatilhos[i], gatilhos[j]):
                pai[raiz(j)] = raiz(i)
    grupos: dict[int, list[int]] = {}
    for i in range(len(gatilhos)):
        grupos.setdefault(raiz(i), []).append(i)
    return sorted(grupos.values())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("observacoes", type=int)
    ap.add_argument("--confirmacoes", type=int, default=0)
    ap.add_argument("--contradicoes", type=int, default=0)
    ap.add_argument("--semanas-sem-ver", type=int, default=0)
    a = ap.parse_args()
    c = confianca(a.observacoes, a.confirmacoes, a.contradicoes, a.semanas_sem_ver)
    print(c, faixa(c))


if __name__ == "__main__":
    main()
