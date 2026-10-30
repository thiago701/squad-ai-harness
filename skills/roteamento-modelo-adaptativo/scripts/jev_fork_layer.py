#!/usr/bin/env python3
"""Camada JEV de bifurcacao (fork layer): corte calibrado `sharp -> code` vs `split -> LLM` (stdlib).

Absorvido da arquitetura de roteamento multiagente de `@thedelost` (`JEV · fork layer`):
intercepta as 3 bifurcacoes operacionais do orquestrador (`which agent`, `which skill`,
`retry or stop`). Quando a distribuicao de probabilidade e nitida (`sharp`), executa direto
em codigo (zero tokens de LLM); quando e dividida (`split`), escala para o modelo (`Sonnet`).
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any

FORKS_VALIDOS = frozenset({"which agent", "which skill", "retry or stop"})
ERROS_DETERMINISTICOS = frozenset({
    "arquivo_nao_existe", "prompt_invalido", "teste_falhou", "json_malformado", "exit_2_hook",
})
ERROS_TERMINAIS = frozenset({"credito_esgotado", "conta_banida", "credencial_expirada"})
ERROS_TRANSITORIOS = frozenset({"429", "rate_limit", "quota_janela", "503", "502"})


@dataclass(frozen=True)
class DecisaoFork:
    fork: str
    escolhido: str
    probabilidade: float
    margem: float
    regime: str
    executor: str
    log: str


def _ordenar_candidatos(probabilidades: dict[str, float]) -> list[tuple[str, float]]:
    if not probabilidades:
        raise ValueError("mapa de probabilidades vazio no fork layer")
    return sorted(probabilidades.items(), key=lambda par: par[1], reverse=True)


def avaliar_fork(fork: str, probabilidades: dict[str, float],
                 limiar_sharp: float = 0.75, margem_min: float = 0.20,
                 modelo_split: str = "sonnet 5.5") -> DecisaoFork:
    """Classifica um fork em `sharp -> code` ou `split -> <modelo_split>`."""
    if fork not in FORKS_VALIDOS:
        raise ValueError(f"fork desconhecido: {fork!r}")
    ordenados = _ordenar_candidatos(probabilidades)
    escolhido, p1 = ordenados[0]
    p2 = ordenados[1][1] if len(ordenados) > 1 else 0.0
    margem = round(p1 - p2, 4)
    eh_sharp = p1 >= limiar_sharp and margem >= margem_min
    regime = "sharp" if eh_sharp else "split"
    executor = "code" if eh_sharp else modelo_split
    linha_log = f"jev: {fork:<14} -> {escolhido:<12} p={p1:.2f} {regime} -> {executor}"
    return DecisaoFork(fork, escolhido, round(p1, 4), margem, regime, executor, linha_log)


def decidir_retry_or_stop(erro: str, tentativa: int = 0,
                          tem_tool_alternativa: bool = False,
                          modelo_split: str = "sonnet 5.5") -> DecisaoFork:
    """Resolve o fork `retry or stop` em (`retry once`, `switch tool`, `stop + ask`)."""
    if erro in ERROS_TERMINAIS or erro in ERROS_DETERMINISTICOS or tentativa >= 2:
        probs = {"stop + ask": 0.97, "retry once": 0.02, "switch tool": 0.01}
    elif tem_tool_alternativa and tentativa >= 1:
        probs = {"switch tool": 0.90, "stop + ask": 0.06, "retry once": 0.04}
    elif erro in ERROS_TRANSITORIOS and tentativa == 0:
        probs = {"retry once": 0.86, "stop + ask": 0.09, "switch tool": 0.05}
    else:
        probs = {"retry once": 0.48, "stop + ask": 0.44, "switch tool": 0.08}
    return avaliar_fork("retry or stop", probs, modelo_split=modelo_split)


def resumir_economia_forks(decisoes: list[DecisaoFork]) -> dict[str, Any]:
    """Mede a taxa de bypass de LLM (decisoes `sharp` resolvidas em codigo)."""
    total = len(decisoes)
    em_codigo = sum(1 for d in decisoes if d.regime == "sharp")
    em_llm = total - em_codigo
    taxa = round(100.0 * em_codigo / total, 1) if total else 0.0
    return {"total_forks": total, "sharp_code": em_codigo, "split_llm": em_llm, "bypass_llm_pct": taxa}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    with open(sys.argv[1], encoding="utf-8") as fh:
        payload = json.load(fh)
    dec = avaliar_fork(payload["fork"], payload["probs"])
    print(dec.log)
