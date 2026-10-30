#!/usr/bin/env python3
"""Tripwire tipado + filtro de handoff para pipelines multiagente (so stdlib).

Tecnica reescrita a partir do openai/openai-agents-python (MIT, commit 9abc918): guardrails cujo
veredito com `disparou=True` interrompe o fluxo com excecao tipada, e filtro de entrada de handoff que
entrega ao agente seguinte so a conversa, sem chamadas/saidas de ferramenta nem raciocinio.

Uso:
    from handoff_guard import executar_com_guardas, filtrar_handoff, Veredito, TripwireDisparado
    python handoff_guard.py historico.json      # imprime a medida de economia do filtro
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, Callable, Iterable

# Itens que nao atravessam o handoff: trabalho intermediario do agente anterior.
TIPOS_PODADOS = frozenset({
    "chamada_ferramenta", "saida_ferramenta", "raciocinio", "handoff", "aprovacao",
    "function_call", "function_call_output", "reasoning", "tool_call", "tool_result",
})


@dataclass(frozen=True)
class Veredito:
    disparou: bool
    info: Any = None


class TripwireDisparado(Exception):
    """Base: um guarda reprovou; o pipeline para aqui (nao ha 'segue com aviso')."""

    fase = "?"

    def __init__(self, guarda: str, info: Any, resultados: list):
        super().__init__(f"tripwire de {self.fase} disparado por '{guarda}': {info}")
        self.guarda = guarda
        self.info = info
        self.resultados = resultados  # todos os vereditos ate o disparo (auditoria)


class TripwireEntrada(TripwireDisparado):
    fase = "entrada"


class TripwireSaida(TripwireDisparado):
    fase = "saida"


def _rodar(guardas: Iterable[Callable], valor: Any, erro: type, resultados: list) -> None:
    for guarda in guardas:
        nome = getattr(guarda, "__name__", repr(guarda))
        try:
            veredito = guarda(valor)
        except Exception as exc:  # fail-closed: guarda quebrada = veredito desconhecido = para
            veredito = Veredito(True, f"guarda falhou: {exc!r}")
        resultados.append((erro.fase, nome, veredito))
        if veredito.disparou:
            raise erro(nome, veredito.info, list(resultados))


def executar_com_guardas(agente: Callable[[Any], Any], entrada_valor: Any,
                         entrada: Iterable[Callable] = (), saida: Iterable[Callable] = ()):
    """Modo bloqueante: guardas de entrada rodam ANTES do agente (zero tokens gastos se disparar);
    guardas de saida rodam sobre o resultado final. Devolve (saida, vereditos)."""
    resultados: list = []
    _rodar(entrada, entrada_valor, TripwireEntrada, resultados)
    resultado = agente(entrada_valor)
    _rodar(saida, resultado, TripwireSaida, resultados)
    return resultado, resultados


def tokens(itens: list) -> int:
    return len(json.dumps(itens, ensure_ascii=False)) // 4


def filtrar_handoff(historico: list, max_mensagens: int | None = None):
    """Devolve (historico_podado, medida). Nao muta a entrada. Mantem a ordem e sempre a ultima
    mensagem (a tarefa atual); `max_mensagens` limita a janela de mensagens mais recentes."""
    podado = [dict(i) for i in historico if i.get("tipo") not in TIPOS_PODADOS]
    if max_mensagens is not None and max_mensagens > 0:
        podado = podado[-max_mensagens:]
    antes, depois = tokens(historico), tokens(podado)
    economia = round(100 * (antes - depois) / antes, 1) if antes else 0.0
    return podado, {"tokens_antes": antes, "tokens_depois": depois, "economia_pct": economia}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    with open(sys.argv[1], encoding="utf-8") as fh:
        _, medida = filtrar_handoff(json.load(fh))
    print(json.dumps(medida))
