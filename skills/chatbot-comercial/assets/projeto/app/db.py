"""Persistência — SQLite por default (deploy isolado por cliente, VPS).

Por que SQLite: até ~10k conversas/mês o gargalo é o LLM, não o banco. Um
arquivo por cliente casa com "deploy isolado por cliente" sem operar um
Postgres por tenant. Trocar por Postgres é mudar `conectar()` e o DDL — as
consultas são SQL comum. Ver `references/arquitetura-referencia.md`.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger("chatbot.db")

DDL = """
CREATE TABLE IF NOT EXISTS interacoes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT    NOT NULL,
    tenant          TEXT    NOT NULL,
    sessao          TEXT    NOT NULL,
    correlacao      TEXT    NOT NULL,
    canal           TEXT    NOT NULL,
    intencao        TEXT    NOT NULL DEFAULT '',
    pergunta        TEXT    NOT NULL,
    contexto        TEXT    NOT NULL DEFAULT '',
    resposta        TEXT    NOT NULL,
    fontes          TEXT    NOT NULL DEFAULT '',
    modelo          TEXT    NOT NULL DEFAULT '',
    tokens_entrada  INTEGER NOT NULL DEFAULT 0,
    tokens_saida    INTEGER NOT NULL DEFAULT 0,
    custo_brl       REAL    NOT NULL DEFAULT 0.0,
    latencia_ms     REAL    NOT NULL DEFAULT 0.0,
    escalonado      INTEGER NOT NULL DEFAULT 0,
    sem_fonte       INTEGER NOT NULL DEFAULT 0,
    recusado        TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_interacoes_tenant_ts ON interacoes (tenant, ts);
CREATE INDEX IF NOT EXISTS ix_interacoes_sessao    ON interacoes (sessao);

CREATE TABLE IF NOT EXISTS leads (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             TEXT NOT NULL,
    atualizado_em  TEXT NOT NULL,
    tenant         TEXT NOT NULL,
    nome           TEXT NOT NULL DEFAULT '',
    contato_hash   TEXT NOT NULL,
    contato_mask   TEXT NOT NULL DEFAULT '',
    canal          TEXT NOT NULL DEFAULT '',
    sessao         TEXT NOT NULL DEFAULT '',
    intencao       TEXT NOT NULL DEFAULT '',
    qualificacao   TEXT NOT NULL DEFAULT 'frio',
    dados          TEXT NOT NULL DEFAULT '{}',
    status         TEXT NOT NULL DEFAULT 'novo',
    UNIQUE (tenant, contato_hash)
);
CREATE INDEX IF NOT EXISTS ix_leads_tenant_ts ON leads (tenant, ts);

CREATE TABLE IF NOT EXISTS curadoria (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT NOT NULL,
    tenant        TEXT NOT NULL,
    interacao_id  INTEGER,
    pergunta      TEXT NOT NULL,
    resposta_ruim TEXT NOT NULL DEFAULT '',
    motivo        TEXT NOT NULL DEFAULT '',
    fonte_alvo    TEXT NOT NULL DEFAULT '',
    texto_proposto TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'pendente',
    aprovado_por  TEXT NOT NULL DEFAULT '',
    decidido_em   TEXT NOT NULL DEFAULT '',
    versao_id     INTEGER
);
CREATE INDEX IF NOT EXISTS ix_curadoria_status ON curadoria (tenant, status);

CREATE TABLE IF NOT EXISTS base_versoes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    tenant      TEXT NOT NULL,
    rotulo      TEXT NOT NULL,
    descricao   TEXT NOT NULL DEFAULT '',
    caminho     TEXT NOT NULL,
    aprovado_por TEXT NOT NULL DEFAULT '',
    ativo       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_versoes_tenant ON base_versoes (tenant, ts);

CREATE TABLE IF NOT EXISTS consentimentos (
    contato_hash TEXT NOT NULL,
    tenant       TEXT NOT NULL,
    consentido   INTEGER NOT NULL DEFAULT 0,
    base_legal   TEXT NOT NULL DEFAULT 'legitimo_interesse',
    ts           TEXT NOT NULL,
    PRIMARY KEY (tenant, contato_hash)
);

CREATE TABLE IF NOT EXISTS fontes_indexadas (
    tenant     TEXT NOT NULL,
    fonte      TEXT NOT NULL,
    sha256     TEXT NOT NULL,
    chunks     INTEGER NOT NULL DEFAULT 0,
    indexado_em TEXT NOT NULL,
    PRIMARY KEY (tenant, fonte)
);
"""


def conectar(caminho: Path | str) -> sqlite3.Connection:
    destino = Path(caminho)
    destino.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(destino, check_same_thread=False)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys=ON")
    escolher_modo_de_jornal(conexao)
    return conexao


MODOS_DE_JORNAL = ("WAL", "TRUNCATE", "DELETE", "PERSIST", "MEMORY")


def escolher_modo_de_jornal(conexao: sqlite3.Connection) -> str:
    """Primeiro modo de journal que o filesystem realmente aceita.

    WAL precisa de memória compartilhada, que não existe em NFS, SMB e vários
    bind mounts. Nesses casos o `journal_mode=WAL` derruba a aplicação com
    `disk I/O error` no primeiro `CREATE TABLE` — e `DELETE`, que parece o
    fallback óbvio, falha do mesmo jeito quando o mount não suporta o
    `unlink` do journal. `TRUNCATE` costuma passar. Medido, não suposto.

    Em volume Docker (o deploy default) o primeiro da lista vence e nada disso
    importa. `MEMORY` é o último recurso: rápido, mas o banco corrompe se o
    processo morrer no meio de uma transação — por isso vai um aviso no log.
    """
    for modo in MODOS_DE_JORNAL:
        try:
            efetivo = conexao.execute(f"PRAGMA journal_mode={modo}").fetchone()[0]
            if str(efetivo).lower() != modo.lower():
                continue
            # `PRAGMA` sozinho não prova nada: o erro só aparece na escrita.
            conexao.execute("CREATE TABLE IF NOT EXISTS _sonda_jornal (a INTEGER)")
            conexao.execute("DROP TABLE _sonda_jornal")
            conexao.commit()
        except sqlite3.Error:
            continue
        if modo == "MEMORY":
            logger.warning(
                "journal_mode=MEMORY: o filesystem não suporta journal em disco. "
                "O banco pode corromper se o processo cair. Use um volume local."
            )
        return modo.lower()
    raise sqlite3.OperationalError(
        "nenhum journal_mode funciona neste filesystem. "
        "Aponte CHATBOT_BANCO para um disco local (ex.: volume Docker)."
    )


def migrar(conexao: sqlite3.Connection) -> None:
    conexao.executescript(DDL)
    conexao.commit()


@contextmanager
def transacao(conexao: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        yield conexao
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
