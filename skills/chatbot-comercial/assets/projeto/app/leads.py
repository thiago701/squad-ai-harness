"""M3 — leads: captura, qualificação, timeline, dedupe e exportação.

Dedupe é por `(tenant, hash do contato)` — chave única no banco. O contato
nunca é gravado em claro (restrição 5): guarda-se hash + máscara.
"""

from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from .agente import extrair_slots
from .auditoria import agora
from .privacidade import hash_contato, mascarar_contato, redigir

_NOME = re.compile(
    r"(?:meu nome (?:é|eh|e)|aqui (?:é|eh|e) o?a?|sou o|sou a|me chamo)\s+"
    r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ']{1,20}(?:\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ']{1,20}){0,2})",
    re.I,
)
_CONTATO = re.compile(
    r"[\w.+-]+@[\w-]+\.[\w.]+|(?<!\d)(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}[-\s.]?\d{4}(?!\d)"
)


@dataclass(frozen=True, slots=True)
class Lead:
    nome: str
    contato_hash: str
    contato_mask: str
    canal: str
    sessao: str
    intencao: str
    qualificacao: str
    dados: dict[str, Any]


def qualificar(dados: dict[str, Any], regras: dict[str, Any]) -> str:
    """Qualificação declarada no vertical-pack, do nível mais alto ao mais baixo.

        "qualificacao": {"quente": ["data_entrada", "hospedes"],
                         "morno":  ["data_entrada"],
                         "padrao": "frio"}

    Cada nível lista os campos que precisam estar preenchidos. O primeiro que
    fechar vence — por isso a ordem no JSON importa.
    """
    padrao = str(regras.get("padrao", "frio")) if regras else "frio"
    for nivel, campos in (regras or {}).items():
        if nivel == "padrao" or not isinstance(campos, (list, tuple)):
            continue
        if all(dados.get(campo) for campo in campos):
            return nivel
    return padrao


def extrair_lead(
    texto: str,
    *,
    sessao: str,
    canal: str,
    intencao: str,
    usuario: str,
    pack: Any,
) -> Lead | None:
    """Captura oportunista: só vira lead quando há contato e intenção comercial."""
    captura = pack.captura_lead or {}
    intencoes_alvo = set(captura.get("intencoes_que_geram_lead", ()))
    if intencoes_alvo and intencao not in intencoes_alvo:
        return None

    # Lead sem contato real não é lead — é ruído no painel do atendente.
    # `usuario` só vale quando o próprio canal já entrega um contato
    # (WhatsApp manda o telefone); id de sessão do widget não conta.
    achado = _CONTATO.search(texto)
    do_canal = usuario if _CONTATO.fullmatch(usuario or "") else ""
    contato = achado.group(0) if achado else do_canal
    if not contato:
        return None

    nome_achado = _NOME.search(texto)
    dados = extrair_slots(texto)
    dados["origem"] = canal
    return Lead(
        nome=(nome_achado.group(1).strip() if nome_achado else ""),
        contato_hash=hash_contato(contato),
        contato_mask=mascarar_contato(contato),
        canal=canal,
        sessao=sessao,
        intencao=intencao,
        qualificacao=qualificar(dados, captura.get("qualificacao", {})),
        dados=dados,
    )


_ORDEM = {"frio": 0, "morno": 1, "quente": 2}


class RepositorioLeads:
    def __init__(self, conexao: sqlite3.Connection, tenant: str):
        self._conexao = conexao
        self._tenant = tenant

    def salvar(self, lead: Lead) -> int:
        """Upsert com dedupe. Nunca rebaixa a qualificação nem apaga dado já obtido."""
        existente = self._conexao.execute(
            "SELECT id, nome, qualificacao, dados FROM leads "
            "WHERE tenant = ? AND contato_hash = ?",
            (self._tenant, lead.contato_hash),
        ).fetchone()

        if existente is None:
            cursor = self._conexao.execute(
                "INSERT INTO leads (ts, atualizado_em, tenant, nome, contato_hash, "
                "contato_mask, canal, sessao, intencao, qualificacao, dados, status) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,'novo')",
                (
                    agora(), agora(), self._tenant, redigir(lead.nome), lead.contato_hash,
                    lead.contato_mask, lead.canal, lead.sessao, lead.intencao,
                    lead.qualificacao, json.dumps(lead.dados, ensure_ascii=False),
                ),
            )
            self._conexao.commit()
            return int(cursor.lastrowid or 0)

        dados = {**json.loads(existente["dados"] or "{}"), **lead.dados}
        qualificacao = max(
            existente["qualificacao"], lead.qualificacao, key=lambda q: _ORDEM.get(q, 0)
        )
        self._conexao.execute(
            "UPDATE leads SET atualizado_em = ?, nome = ?, intencao = ?, "
            "qualificacao = ?, dados = ?, sessao = ? WHERE id = ?",
            (
                agora(), redigir(lead.nome or existente["nome"]), lead.intencao,
                qualificacao, json.dumps(dados, ensure_ascii=False), lead.sessao,
                existente["id"],
            ),
        )
        self._conexao.commit()
        return int(existente["id"])

    def listar(self, *, qualificacao: str = "", limite: int = 200) -> list[dict[str, Any]]:
        sql = "SELECT * FROM leads WHERE tenant = ?"
        parametros: list[Any] = [self._tenant]
        if qualificacao:
            sql += " AND qualificacao = ?"
            parametros.append(qualificacao)
        sql += " ORDER BY atualizado_em DESC LIMIT ?"
        parametros.append(limite)
        return [dict(linha) for linha in self._conexao.execute(sql, parametros).fetchall()]

    def marcar(self, lead_id: int, status: str) -> None:
        self._conexao.execute(
            "UPDATE leads SET status = ?, atualizado_em = ? WHERE id = ? AND tenant = ?",
            (status, agora(), lead_id, self._tenant),
        )
        self._conexao.commit()

    def exportar_csv(self) -> str:
        """CSV pronto para CRM. Contato mascarado — o hash permite reconciliar."""
        colunas = [
            "id", "ts", "atualizado_em", "nome", "contato_mask", "contato_hash",
            "canal", "intencao", "qualificacao", "status", "dados",
        ]
        buffer = io.StringIO()
        escritor = csv.DictWriter(buffer, fieldnames=colunas, extrasaction="ignore")
        escritor.writeheader()
        for lead in self.listar(limite=100_000):
            escritor.writerow({c: lead.get(c, "") for c in colunas})
        return buffer.getvalue()
