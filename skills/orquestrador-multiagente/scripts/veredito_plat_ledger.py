#!/usr/bin/env python3
"""Veredito out-of-sample, detector de plato em grade e guarda de ledger anti-reteste (stdlib).

Implementa os mecanismos absorvidos do padrao de equipe de pesquisa multiagente (v1.2.0):
1. `avaliar_veredito`: contrato de 3 estados (DATA_VALIDATED, TRADE_OFF, NO_EDGE) exigindo split temporal.
2. `classificar_grade`: distingue plato robusto (`plateau`) de pico isolado de sorte (`isolated_peak`).
3. `validar_transicao_ledger`: aplica as 4 leis do ledger (`research.md`), bloqueando reteste de item
   `dead` sem razao nova e exigindo sobrevivencia ao `skeptic` antes de `accepted`.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any

DATA_VALIDATED = "DATA_VALIDATED"
TRADE_OFF = "TRADE_OFF"
NO_EDGE = "NO_EDGE"


@dataclass(frozen=True)
class JanelaMetrica:
    crescimento: float
    risco_ajustado: float
    ano_inicio: int
    ano_fim: int


class ViolacaoSplitTemporal(ValueError):
    """Split aleatorio ou com sobreposicao temporal vaza futuro no passado."""


class ViolacaoLedger(ValueError):
    """Transicao invalida segundo as 4 leis invariantes do ledger."""


def _validar_ordem_temporal(treino: JanelaMetrica, held_out: JanelaMetrica, modo_split: str) -> None:
    if modo_split != "temporal":
        raise ViolacaoSplitTemporal(f"split '{modo_split}' recusado: exige corte temporal estrito")
    if treino.ano_inicio > treino.ano_fim or held_out.ano_inicio > held_out.ano_fim:
        raise ViolacaoSplitTemporal("intervalo de anos invalido na janela")
    if treino.ano_fim >= held_out.ano_inicio:
        raise ViolacaoSplitTemporal("janela held-out deve ser estritamente posterior ao treino")


def _bate_eixos(janela: JanelaMetrica, bench: JanelaMetrica) -> tuple[bool, bool]:
    return janela.crescimento > bench.crescimento, janela.risco_ajustado > bench.risco_ajustado


def avaliar_veredito(treino: JanelaMetrica, held_out: JanelaMetrica,
                     bench_treino: JanelaMetrica, bench_held_out: JanelaMetrica,
                     modo_split: str = "temporal") -> str:
    """Calcula o veredito imutavel entre treino e held-out contra os respectivos benchmarks."""
    _validar_ordem_temporal(treino, held_out, modo_split)
    t_cresc, t_risco = _bate_eixos(treino, bench_treino)
    h_cresc, h_risco = _bate_eixos(held_out, bench_held_out)
    bateu_cresc = t_cresc and h_cresc
    bateu_risco = t_risco and h_risco
    if bateu_cresc and bateu_risco:
        return DATA_VALIDATED
    if bateu_cresc or bateu_risco:
        return TRADE_OFF
    return NO_EDGE


def _vizinhos_validados(grade: list[list[str]], lin: int, col: int) -> int:
    linhas, cols = len(grade), len(grade[0])
    deltas = ((-1, 0), (1, 0), (0, -1), (0, 1))
    total = 0
    for dl, dc in deltas:
        nl, nc = lin + dl, col + dc
        if 0 <= nl < linhas and 0 <= nc < cols and grade[nl][nc] == DATA_VALIDATED:
            total += 1
    return total


def classificar_grade(grade: list[list[str]], min_celulas_plato: int = 3) -> dict[str, Any]:
    """Classifica uma grade 2D de vereditos em `plateau`, `isolated_peak` ou `none`."""
    if not grade or not grade[0]:
        return {"forma": "none", "validados": 0, "conectados": 0}
    validados = 0
    conectados = 0
    for r, linha in enumerate(grade):
        for c, celula in enumerate(linha):
            if celula == DATA_VALIDATED:
                validados += 1
                if _vizinhos_validados(grade, r, c) > 0:
                    conectados += 1
    if validados == 0:
        forma = "none"
    elif conectados >= min_celulas_plato:
        forma = "plateau"
    else:
        forma = "isolated_peak"
    return {"forma": forma, "validados": validados, "conectados": conectados}


def validar_transicao_ledger(registro_atual: dict[str, Any] | None,
                             novo_registro: dict[str, Any]) -> dict[str, Any]:
    """Aplica as 4 leis do ledger antes de persistir ou promover uma hipotese."""
    veredito = novo_registro.get("verdict")
    if veredito not in {DATA_VALIDATED, TRADE_OFF, NO_EDGE}:
        raise ViolacaoLedger("Lei 1 violada: todo registro exige veredito valido antes do resumo")
    if registro_atual and registro_atual.get("status") == "dead":
        if not str(novo_registro.get("new_reason", "")).strip():
            raise ViolacaoLedger("Lei 3 violada: item dead/NO_EDGE nao pode ser retestado sem razao nova")
    novo_status = novo_registro.get("status", "open")
    if novo_status == "accepted":
        _validar_promocao_aceite(novo_registro, veredito)
    if veredito == NO_EDGE and novo_status not in {"dead"}:
        raise ViolacaoLedger("Lei 3 violada: veredito NO_EDGE deve ser gravado com status='dead'")
    return dict(novo_registro)


def _validar_promocao_aceite(registro: dict[str, Any], veredito: str) -> None:
    if veredito != DATA_VALIDATED:
        raise ViolacaoLedger("Lei 2 violada: apenas DATA_VALIDATED pode avancar para accepted")
    if registro.get("sweep_forma") != "plateau":
        raise ViolacaoLedger("Lei 2/3 violada: pico isolado nao pode ser aceito; exige plateau")
    relato_cetico = str(registro.get("skeptic", "")).strip()
    if not relato_cetico or registro.get("skeptic_broke", False):
        raise ViolacaoLedger("Lei 4 violada: exige ataque do skeptic sem quebrar a hipotese")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    with open(sys.argv[1], encoding="utf-8") as fh:
        dados = json.load(fh)
    print(json.dumps(classificar_grade(dados.get("grade", []))))
