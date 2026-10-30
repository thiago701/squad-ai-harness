#!/usr/bin/env python3
"""Planeja ONDE compactar um historico de agente (stdlib, sem LLM).

Tecnica reescrita a partir do condenser do OpenHands/software-agent-sdk (commit 4fedb7e, MIT);
nenhum codigo copiado. O resumo em si continua sendo escrito pelo modelo (T1/T2 da skill);
este modulo so decide a fatia [inicio, fim) a esquecer.

Regras:
  - motivos: EVENTOS (soft: len > max_eventos), TOKENS (hard: soma > max_tokens), PEDIDO (hard:
    pedido explicito ou erro de janela de contexto);
  - preserva o system inicial + keep_first eventos e sempre o evento mais recente;
  - alvo: ~metade (max_eventos/2, max_tokens/2 ou len/2); varios motivos -> corte mais agressivo;
  - fronteiras validas: o corte nunca separa uma acao da sua observacao (mesmo id);
  - progresso minimo: a fatia leva >= 10% da visao;
  - sem corte valido: soft -> "adiar"; hard -> "reset" (resume tudo depois do system).
  - acao ABERTA (sem observacao) do turno atual e intocavel: o corte para antes dela; acao
    aberta seguida de nova mensagem do usuario e considerada morta e nao bloqueia;
  - custo-beneficio: com resumo anterior e sem PEDIDO, so compacta se a fatia pesar mais
    tokens que o ultimo resumo (senao "nao_compensa");
  - fail-open: `aplicar` devolve o historico intacto se o resumo vier vazio/None.
  (Pendencias, custo-beneficio e fail-open: ideia de google/adk-python@47e613d, Apache-2.0.)

Uso: ponto_de_corte.py eventos.json [--max-eventos N] [--max-tokens N] [--keep-first N] [--pedido]
"""
import argparse
import json
import math
import sys

PROGRESSO_MINIMO = 0.10


def _pares(eventos):
    abertos, pares = {}, []
    for i, ev in enumerate(eventos):
        if ev.get("tipo") == "acao":
            abertos[ev.get("id")] = i
        elif ev.get("tipo") == "observacao" and ev.get("id") in abertos:
            pares.append((abertos.pop(ev.get("id")), i))
    return pares


def _primeira_aberta(eventos):
    """Indice da primeira acao viva sem observacao (ou None). Morta = houve user depois."""
    respondidas = {ev.get("id") for ev in eventos if ev.get("tipo") == "observacao"}
    ultimo_user = max((i for i, ev in enumerate(eventos) if ev.get("tipo") == "user"), default=-1)
    for i, ev in enumerate(eventos):
        if ev.get("tipo") == "acao" and ev.get("id") not in respondidas and i > ultimo_user:
            return i
    return None


def _ultimo_resumo(eventos):
    for ev in reversed(eventos):
        if ev.get("tipo") == "resumo":
            return int(ev.get("tokens", 0))
    return None


def _valido(k, pares):
    return all(not (a < k <= b) for a, b in pares)


def _tokens(eventos):
    return sum(int(ev.get("tokens", 0)) for ev in eventos)


def _fim_minimo(eventos, inicio, motivo, max_eventos, max_tokens):
    n = len(eventos)
    if motivo == "EVENTOS":
        return n + inicio + 1 - max_eventos // 2
    if motivo == "PEDIDO":
        return n + inicio + 1 - n // 2
    teto = max_tokens // 2 - _tokens(eventos[:inicio])
    fim = inicio
    while fim < n and _tokens(eventos[fim:]) > teto:
        fim += 1
    return fim


def planejar(eventos, max_eventos=None, max_tokens=None, keep_first=2, pedido=False):
    n = len(eventos)
    motivos = []
    if max_eventos is not None and n > max_eventos:
        motivos.append("EVENTOS")
    if max_tokens is not None and _tokens(eventos) > max_tokens:
        motivos.append("TOKENS")
    if pedido:
        motivos.append("PEDIDO")
    if not motivos:
        return {"decisao": "nada", "motivos": []}
    hard = any(m in ("TOKENS", "PEDIDO") for m in motivos)
    base = 1 if eventos and eventos[0].get("tipo") == "system" else 0
    pares = _pares(eventos)
    inicio = min(base + keep_first, n)
    while inicio < n and not _valido(inicio, pares):
        inicio += 1
    fim = max(_fim_minimo(eventos, inicio, m, max_eventos, max_tokens) for m in motivos)
    fim = max(fim, inicio + 1)
    while fim < n and not _valido(fim, pares):
        fim += 1
    aberta = _primeira_aberta(eventos)
    if aberta is not None and fim > aberta:
        fim = aberta  # nunca esquecer acao em voo; corte parcial ou adiar
        while fim > inicio and not _valido(fim, pares):
            fim -= 1
        if fim - inicio < 1 or (not hard and fim - inicio < math.ceil(PROGRESSO_MINIMO * n)):
            return {"decisao": "adiar", "motivos": motivos + ["PENDENTE"]}
    elif not (fim < n and fim - inicio >= math.ceil(PROGRESSO_MINIMO * n)):
        if not hard or aberta is not None:
            return {"decisao": "adiar", "motivos": motivos}
        return {"decisao": "reset", "motivos": motivos, "inicio": base, "fim": n,
                "esquecidos": n - base}
    anterior = _ultimo_resumo(eventos)
    if anterior is not None and not pedido and _tokens(eventos[inicio:fim]) <= anterior:
        return {"decisao": "nao_compensa", "motivos": motivos}
    return {"decisao": "condensar", "motivos": motivos, "inicio": inicio, "fim": fim,
            "esquecidos": fim - inicio}


def visao_resultante(eventos, plano):
    if plano["decisao"] not in ("condensar", "reset"):
        return list(eventos)
    resumo = {"tipo": "resumo", "tokens": 0, "esquecidos": plano["esquecidos"]}
    return eventos[:plano["inicio"]] + [resumo] + eventos[plano["fim"]:]


def aplicar(eventos, plano, resumo_texto):
    """Fail-open: sem resumo utilizavel, devolve o historico original intacto."""
    if plano["decisao"] not in ("condensar", "reset") or not (resumo_texto or "").strip():
        return list(eventos)
    resumo = {"tipo": "resumo", "tokens": max(1, len(resumo_texto) // 4),
              "texto": resumo_texto, "esquecidos": plano["esquecidos"]}
    return eventos[:plano["inicio"]] + [resumo] + eventos[plano["fim"]:]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("eventos")
    p.add_argument("--max-eventos", type=int)
    p.add_argument("--max-tokens", type=int)
    p.add_argument("--keep-first", type=int, default=2)
    p.add_argument("--pedido", action="store_true")
    a = p.parse_args(argv)
    with open(a.eventos, encoding="utf-8") as f:
        eventos = json.load(f)
    plano = planejar(eventos, a.max_eventos, a.max_tokens, a.keep_first, a.pedido)
    sys.stdout.write(json.dumps(plano, ensure_ascii=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
