"""M5 — dashboard: volume, contenção, leads, custo por conversa, top sem-resposta.

Taxa de contenção = conversas resolvidas sem humano ÷ conversas totais.
Conversa (não interação) é a unidade: uma sessão que escalou uma vez conta
como não contida, mesmo que tenha tido dez turnos bons antes.
"""

from __future__ import annotations

import sqlite3
from typing import Any


def _um(conexao: sqlite3.Connection, sql: str, parametros: tuple[Any, ...]) -> Any:
    linha = conexao.execute(sql, parametros).fetchone()
    return linha[0] if linha else 0


def metricas(conexao: sqlite3.Connection, tenant: str, *, dias: int = 30) -> dict[str, Any]:
    janela = (tenant, f"-{dias} days")

    conversas = _um(
        conexao,
        "SELECT COUNT(DISTINCT sessao) FROM interacoes "
        "WHERE tenant = ? AND ts >= datetime('now', ?)",
        janela,
    )
    interacoes = _um(
        conexao,
        "SELECT COUNT(*) FROM interacoes WHERE tenant = ? AND ts >= datetime('now', ?)",
        janela,
    )
    escaladas = _um(
        conexao,
        "SELECT COUNT(DISTINCT sessao) FROM interacoes "
        "WHERE tenant = ? AND ts >= datetime('now', ?) AND escalonado = 1",
        janela,
    )
    custo_total = float(
        _um(
            conexao,
            "SELECT COALESCE(SUM(custo_brl), 0) FROM interacoes "
            "WHERE tenant = ? AND ts >= datetime('now', ?)",
            janela,
        )
    )
    sem_fonte = _um(
        conexao,
        "SELECT COUNT(*) FROM interacoes "
        "WHERE tenant = ? AND ts >= datetime('now', ?) AND sem_fonte = 1",
        janela,
    )
    leads = _um(
        conexao,
        "SELECT COUNT(*) FROM leads WHERE tenant = ? AND ts >= datetime('now', ?)",
        janela,
    )
    leads_quentes = _um(
        conexao,
        "SELECT COUNT(*) FROM leads WHERE tenant = ? AND ts >= datetime('now', ?) "
        "AND qualificacao = 'quente'",
        janela,
    )
    latencia = float(
        _um(
            conexao,
            "SELECT COALESCE(AVG(latencia_ms), 0) FROM interacoes "
            "WHERE tenant = ? AND ts >= datetime('now', ?)",
            janela,
        )
    )

    return {
        "janela_dias": dias,
        "conversas": conversas,
        "interacoes": interacoes,
        "conversas_escaladas": escaladas,
        "taxa_contencao": round((conversas - escaladas) / conversas, 4) if conversas else 0.0,
        "leads": leads,
        "leads_quentes": leads_quentes,
        "custo_total_brl": round(custo_total, 4),
        "custo_por_conversa_brl": round(custo_total / conversas, 4) if conversas else 0.0,
        "interacoes_sem_fonte": sem_fonte,
        "taxa_sem_fonte": round(sem_fonte / interacoes, 4) if interacoes else 0.0,
        "latencia_media_ms": round(latencia, 1),
    }


def top_sem_resposta(
    conexao: sqlite3.Connection, tenant: str, *, dias: int = 30, limite: int = 10
) -> list[dict[str, Any]]:
    """Top-10 perguntas sem resposta boa — a fila de trabalho do M4."""
    cursor = conexao.execute(
        "SELECT pergunta, COUNT(*) AS ocorrencias, MAX(ts) AS ultima, "
        "MAX(id) AS interacao_id, intencao "
        "FROM interacoes WHERE tenant = ? AND ts >= datetime('now', ?) "
        "AND (sem_fonte = 1 OR recusado <> '') "
        "GROUP BY lower(trim(pergunta)) ORDER BY ocorrencias DESC, ultima DESC LIMIT ?",
        (tenant, f"-{dias} days", limite),
    )
    return [dict(linha) for linha in cursor.fetchall()]


def custo_por_tenant(conexao: sqlite3.Connection, *, dias: int = 30) -> list[dict[str, Any]]:
    cursor = conexao.execute(
        "SELECT tenant, COUNT(DISTINCT sessao) AS conversas, "
        "COALESCE(SUM(custo_brl), 0) AS custo_brl, "
        "COALESCE(SUM(tokens_entrada + tokens_saida), 0) AS tokens "
        "FROM interacoes WHERE ts >= datetime('now', ?) "
        "GROUP BY tenant ORDER BY custo_brl DESC",
        (f"-{dias} days",),
    )
    return [dict(linha) for linha in cursor.fetchall()]
