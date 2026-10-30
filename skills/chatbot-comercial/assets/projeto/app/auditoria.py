"""M5 — trilha de auditoria, custo por tenant/conversa e LGPD.

Restrição 3: custo observável por tenant e por conversa, com teto.
Restrição 5: nada aqui grava dado pessoal em claro — tudo passa por
`privacidade.redigir` antes de tocar o banco ou o log.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .privacidade import redigir

logger = logging.getLogger("chatbot.auditoria")


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True, slots=True)
class Custos:
    conversa_brl: float
    mes_brl: float
    teto_conversa_brl: float
    teto_mes_brl: float

    @property
    def conversa_estourada(self) -> bool:
        return self.conversa_brl >= self.teto_conversa_brl

    @property
    def mes_estourado(self) -> bool:
        return self.mes_brl >= self.teto_mes_brl


class Trilha:
    """Uma linha por interação: prompt, contexto, resposta, modelo, custo, latência."""

    def __init__(self, conexao: sqlite3.Connection, config: Any):
        self._conexao = conexao
        self._config = config

    def registrar(
        self,
        *,
        sessao: str,
        correlacao: str,
        canal: str,
        pergunta: str,
        resposta: Any,
    ) -> int:
        cursor = self._conexao.execute(
            "INSERT INTO interacoes (ts, tenant, sessao, correlacao, canal, intencao, "
            "pergunta, contexto, resposta, fontes, modelo, tokens_entrada, tokens_saida, "
            "custo_brl, latencia_ms, escalonado, sem_fonte, recusado) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                agora(),
                self._config.tenant,
                sessao,
                correlacao,
                canal,
                resposta.intencao,
                redigir(pergunta),
                "|".join(resposta.contexto),
                redigir(resposta.texto),
                "|".join(resposta.fontes),
                resposta.modelo,
                resposta.tokens_entrada,
                resposta.tokens_saida,
                round(resposta.custo_brl, 6),
                round(resposta.latencia_ms, 2),
                int(resposta.escalonado),
                int(resposta.sem_fonte),
                resposta.recusado,
            ),
        )
        self._conexao.commit()
        logger.info(
            "interacao registrada",
            extra={
                "tenant": self._config.tenant,
                "sessao": sessao,
                "intencao": resposta.intencao,
                "modelo": resposta.modelo,
                "custo_brl": round(resposta.custo_brl, 6),
                "fontes": len(resposta.fontes),
            },
        )
        return int(cursor.lastrowid or 0)

    def timeline(self, sessao: str, *, limite: int = 50) -> list[dict[str, Any]]:
        cursor = self._conexao.execute(
            "SELECT ts, canal, intencao, pergunta, resposta, fontes, escalonado, "
            "sem_fonte, recusado, modelo, custo_brl "
            "FROM interacoes WHERE tenant = ? AND sessao = ? ORDER BY id ASC LIMIT ?",
            (self._config.tenant, sessao, limite),
        )
        return [dict(linha) for linha in cursor.fetchall()]

    def custos(self, sessao: str) -> Custos:
        conversa = self._conexao.execute(
            "SELECT COALESCE(SUM(custo_brl), 0) AS total FROM interacoes "
            "WHERE tenant = ? AND sessao = ?",
            (self._config.tenant, sessao),
        ).fetchone()["total"]
        inicio_mes = datetime.now(timezone.utc).replace(day=1).isoformat(timespec="seconds")
        mes = self._conexao.execute(
            "SELECT COALESCE(SUM(custo_brl), 0) AS total FROM interacoes "
            "WHERE tenant = ? AND ts >= ?",
            (self._config.tenant, inicio_mes),
        ).fetchone()["total"]
        return Custos(
            conversa_brl=float(conversa),
            mes_brl=float(mes),
            teto_conversa_brl=self._config.teto_custo_conversa_brl,
            teto_mes_brl=self._config.teto_custo_mes_brl,
        )

    def contexto_para_humano(self, sessao: str) -> dict[str, Any]:
        """Handoff sem perda: o atendente recebe a conversa inteira e as fontes."""
        historico = self.timeline(sessao)
        return {
            "sessao": sessao,
            "turnos": len(historico),
            "intencoes": sorted({t["intencao"] for t in historico if t["intencao"]}),
            "fontes_usadas": sorted(
                {f for t in historico for f in (t["fontes"] or "").split("|") if f}
            ),
            "houve_recusa": any(t["recusado"] for t in historico),
            "historico": historico,
        }


class Lgpd:
    """Consentimento e retenção configuráveis."""

    def __init__(self, conexao: sqlite3.Connection, config: Any):
        self._conexao = conexao
        self._config = config

    def registrar_consentimento(
        self, contato_hash: str, *, consentido: bool, base_legal: str = "consentimento"
    ) -> None:
        self._conexao.execute(
            "INSERT INTO consentimentos (contato_hash, tenant, consentido, base_legal, ts) "
            "VALUES (?,?,?,?,?) ON CONFLICT(tenant, contato_hash) DO UPDATE SET "
            "consentido=excluded.consentido, base_legal=excluded.base_legal, ts=excluded.ts",
            (contato_hash, self._config.tenant, int(consentido), base_legal, agora()),
        )
        self._conexao.commit()

    def consentido(self, contato_hash: str) -> bool:
        if not self._config.exigir_consentimento:
            return True
        linha = self._conexao.execute(
            "SELECT consentido FROM consentimentos WHERE tenant = ? AND contato_hash = ?",
            (self._config.tenant, contato_hash),
        ).fetchone()
        return bool(linha and linha["consentido"])

    def expurgar(self) -> dict[str, int]:
        """Apaga interações e leads além do prazo de retenção."""
        corte = (
            datetime.now(timezone.utc) - timedelta(days=self._config.retencao_dias)
        ).isoformat(timespec="seconds")
        interacoes = self._conexao.execute(
            "DELETE FROM interacoes WHERE tenant = ? AND ts < ?",
            (self._config.tenant, corte),
        ).rowcount
        leads = self._conexao.execute(
            "DELETE FROM leads WHERE tenant = ? AND atualizado_em < ?",
            (self._config.tenant, corte),
        ).rowcount
        self._conexao.commit()
        return {"interacoes": interacoes or 0, "leads": leads or 0, "corte": corte}

    def esquecer(self, contato_hash: str) -> dict[str, int]:
        """Direito à eliminação (art. 18, VI). Remove lead e consentimento."""
        leads = self._conexao.execute(
            "DELETE FROM leads WHERE tenant = ? AND contato_hash = ?",
            (self._config.tenant, contato_hash),
        ).rowcount
        self._conexao.execute(
            "DELETE FROM consentimentos WHERE tenant = ? AND contato_hash = ?",
            (self._config.tenant, contato_hash),
        )
        self._conexao.commit()
        return {"leads": leads or 0}


def exportar_trilha(conexao: sqlite3.Connection, tenant: str, destino: Any) -> int:
    """Dump JSONL da trilha — evidência para auditoria externa."""
    cursor = conexao.execute(
        "SELECT * FROM interacoes WHERE tenant = ? ORDER BY id", (tenant,)
    )
    total = 0
    with open(destino, "w", encoding="utf-8") as arquivo:
        for linha in cursor:
            arquivo.write(json.dumps(dict(linha), ensure_ascii=False) + "\n")
            total += 1
    return total
