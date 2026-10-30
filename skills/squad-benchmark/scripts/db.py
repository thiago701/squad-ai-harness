#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""db.py — camada de dados da skill `squad-benchmark` (stdlib apenas).

Cria/abre o banco SQLite único em ~/.squad-ai/benchmark/benchmark.db, cria o
schema (3 tabelas + 1 view), faz o seed da tabela `metas` e expõe os helpers
de CRUD + normalização usados por `registrar.py` e `dashboard.py`.

Zero dependências externas: só `sqlite3`, `os`, `json`, `csv`, `argparse`.

Constituição: P1-Simplicidade > P2-Performance > P3-CustoBaixo.
Um arquivo .db + um arquivo .html — nada de servidor, ORM, Docker ou Postgres.

Uso direto:
    python db.py init          # cria o banco + schema + seed (idempotente)
    python db.py path          # imprime o caminho do banco
    python db.py metas         # imprime o seed de metas (JSON)
"""
import argparse
import json
import os
import sqlite3
import sys

# ---------------------------------------------------------------------------
# Localização do banco
# ---------------------------------------------------------------------------
# Permite override por env para testes/CI sem tocar no HOME do usuário.
DB_DIR = os.environ.get(
    "SQUAD_BENCHMARK_DIR",
    os.path.join(os.path.expanduser("~"), ".squad-ai", "benchmark"),
)
DB_PATH = os.path.join(DB_DIR, "benchmark.db")

# ---------------------------------------------------------------------------
# Definição das 5 métricas (fonte: caderno / seção 2 do prompt)
# ---------------------------------------------------------------------------
# Cada métrica: nome, meta (valor bruto), baseline sem Squad AI (ou None),
# unidade padrão, descrição curta da fórmula de normalização e uma cor
# distinta para o gráfico. As fórmulas exatas vivem em references/metricas.md
# e são reproduzidas no rodapé do dashboard.
METRICAS = {
    "A": {
        "nome": "Entregas com menos retrabalho",
        "valor_meta": 90.0,
        "baseline_sem_squad": None,
        "unidade": "%",
        "formula_normalizacao": "direto (já é 0–100)",
        "cor": "#2563eb",  # azul
    },
    "B": {
        "nome": "Redução de custos/tokens",
        "valor_meta": 60.0,
        "baseline_sem_squad": None,
        "unidade": "%",
        "formula_normalizacao": "min(100, valor_bruto)",
        "cor": "#16a34a",  # verde
    },
    "C": {
        "nome": "Qualidade do código e testes",
        "valor_meta": 85.0,
        "baseline_sem_squad": None,
        "unidade": "pts",
        "formula_normalizacao": "direto (já é 0–100)",
        "cor": "#9333ea",  # roxo
    },
    "D": {
        "nome": "Velocidade de entrega",
        "valor_meta": 7.0,          # 7x = 100 normalizado
        "baseline_sem_squad": 1.0,  # 1x = baseline manual sem Squad AI
        "unidade": "x",
        "formula_normalizacao": "min(100, valor/7 × 100)",
        "cor": "#ea580c",  # laranja
    },
    "E": {
        "nome": "Capacidade cognitiva do Cérebro",
        "valor_meta": 80.0,
        "baseline_sem_squad": None,
        "unidade": "pts",
        "formula_normalizacao": "direto (já é 0–100)",
        "cor": "#dc2626",  # vermelho
    },
}

ORDEM = ["A", "B", "C", "D", "E"]

# Rótulos de procedência de uma medição (selo no dashboard). Ordem = mais forte
# para mais fraco. 'solido' = medido diretamente; 'proxy' = medido, mas de um
# sinal correlato (não a definição literal); 'estimativa' = projeção fundamentada.
CONFIANCAS = ("solido", "proxy", "estimativa")

SCHEMA = """
CREATE TABLE IF NOT EXISTS marcos (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    versao    TEXT NOT NULL UNIQUE,              -- 'v1', 'v2', ...
    data      TEXT NOT NULL DEFAULT (date('now')),
    contexto  TEXT                                -- o que mudou no Squad AI neste marco
);

CREATE TABLE IF NOT EXISTS medicoes (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    marco_id           INTEGER NOT NULL REFERENCES marcos(id) ON DELETE CASCADE,
    metrica            TEXT NOT NULL CHECK (metrica IN ('A','B','C','D','E')),
    valor_bruto        REAL NOT NULL,
    valor_normalizado  REAL NOT NULL CHECK (valor_normalizado BETWEEN 0 AND 100),
    unidade            TEXT NOT NULL,
    observacao         TEXT,
    UNIQUE (marco_id, metrica)
);

CREATE TABLE IF NOT EXISTS metas (
    metrica               TEXT PRIMARY KEY CHECK (metrica IN ('A','B','C','D','E')),
    nome                  TEXT NOT NULL,
    valor_meta            REAL NOT NULL,
    baseline_sem_squad    REAL,
    formula_normalizacao  TEXT NOT NULL
);

CREATE VIEW IF NOT EXISTS historico_comparativo AS
SELECT m.versao, m.data, md.metrica, md.valor_bruto, md.valor_normalizado,
       md.valor_normalizado
         - LAG(md.valor_normalizado) OVER (PARTITION BY md.metrica ORDER BY m.id)
         AS delta_vs_anterior
FROM medicoes md JOIN marcos m ON m.id = md.marco_id;
"""


# ---------------------------------------------------------------------------
# Normalização (0–100) — escala comum do gráfico
# ---------------------------------------------------------------------------
def normalizar(metrica, valor_bruto):
    """Converte o valor bruto de uma métrica para a escala comum 0–100.

    A, C, E: valor direto (já vem 0–100).
    B: teto em 100 (% de redução acima de 100 não faz sentido).
    D: multiplicador x → min(100, valor/7 × 100), onde 7x = meta = 100.

    Sempre clampeado em [0, 100] para respeitar o CHECK do schema.
    """
    if metrica == "D":
        norm = min(100.0, (valor_bruto / 7.0) * 100.0)
    elif metrica == "B":
        norm = min(100.0, valor_bruto)
    else:  # A, C, E
        norm = valor_bruto
    return round(max(0.0, min(100.0, norm)), 2)


def meta_normalizada(metrica):
    """Meta da métrica já convertida para a escala 0–100 do gráfico.

    Aplica a mesma normalização ao `valor_meta`, então:
      A=90, B=60, C=85, D=100 (7x), E=80.
    Usada para o cálculo de "% da meta atingida" nos cards.
    """
    return normalizar(metrica, METRICAS[metrica]["valor_meta"])


def pct_meta(metrica, valor_normalizado):
    """% da meta atingida = valor_normalizado / meta_normalizada × 100."""
    alvo = meta_normalizada(metrica)
    if alvo <= 0:
        return 0.0
    return round((valor_normalizado / alvo) * 100.0, 1)


# ---------------------------------------------------------------------------
# Conexão / init
# ---------------------------------------------------------------------------
def connect():
    """Abre (criando se preciso) o banco e garante schema + seed.

    Idempotente: pode ser chamado a cada execução da skill sem efeito colateral.
    """
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    _migrate(conn)
    _seed_metas(conn)
    conn.commit()
    return conn


def _migrate(conn):
    """Migrações idempotentes e retrocompatíveis (bancos antigos continuam válidos).

    `confianca`: rótulo opcional da procedência de cada medição
    ('solido' | 'proxy' | 'estimativa'), usado pelos selos do dashboard.
    Adicionado via ALTER TABLE só se ainda não existir — não quebra dados.
    """
    cols = [r[1] for r in conn.execute("PRAGMA table_info(medicoes)").fetchall()]
    if "confianca" not in cols:
        conn.execute("ALTER TABLE medicoes ADD COLUMN confianca TEXT")


def _seed_metas(conn):
    """Popula `metas` com os valores da seção 2 (uma vez; não sobrescreve)."""
    for metrica in ORDEM:
        m = METRICAS[metrica]
        conn.execute(
            """INSERT OR IGNORE INTO metas
               (metrica, nome, valor_meta, baseline_sem_squad, formula_normalizacao)
               VALUES (?, ?, ?, ?, ?)""",
            (metrica, m["nome"], m["valor_meta"],
             m["baseline_sem_squad"], m["formula_normalizacao"]),
        )


# ---------------------------------------------------------------------------
# CRUD — marcos
# ---------------------------------------------------------------------------
def get_marco(conn, versao):
    """Retorna a linha do marco (Row) ou None."""
    return conn.execute(
        "SELECT * FROM marcos WHERE versao = ?", (versao,)
    ).fetchone()


def listar_marcos(conn):
    """Todos os marcos em ordem cronológica (data e, em empate, ordem de registro).

    Ordenar por `data` conserta o eixo X quando marcos históricos são importados
    depois de um registro mais recente. `id` é o desempate estável.
    """
    return conn.execute("SELECT * FROM marcos ORDER BY data, id").fetchall()


def is_legado(versao):
    """Marco histórico importado (não é um checkpoint real do timeline)."""
    return str(versao).strip().lower().endswith("-legado")


def upsert_marco(conn, versao, contexto=None, data=None):
    """Insere ou atualiza um marco. Retorna o id.

    Nunca duplica (versao é UNIQUE). Se já existe, atualiza contexto/data.
    A decisão de *permitir* sobrescrever (confirmação) é de `registrar.py`.
    """
    existente = get_marco(conn, versao)
    if existente is None:
        if data:
            cur = conn.execute(
                "INSERT INTO marcos (versao, data, contexto) VALUES (?, ?, ?)",
                (versao, data, contexto),
            )
        else:
            cur = conn.execute(
                "INSERT INTO marcos (versao, contexto) VALUES (?, ?)",
                (versao, contexto),
            )
        return cur.lastrowid
    # Atualiza os campos fornecidos, preservando os demais.
    conn.execute(
        "UPDATE marcos SET contexto = COALESCE(?, contexto), "
        "data = COALESCE(?, data) WHERE id = ?",
        (contexto, data, existente["id"]),
    )
    return existente["id"]


# ---------------------------------------------------------------------------
# CRUD — medições
# ---------------------------------------------------------------------------
def upsert_medicao(conn, marco_id, metrica, valor_bruto, unidade=None,
                   observacao=None, confianca=None):
    """Insere/atualiza a medição de uma métrica para um marco.

    Calcula `valor_normalizado` a partir de `valor_bruto`. UNIQUE(marco_id,
    metrica) garante uma medição por métrica por marco. `confianca` (opcional)
    rotula a procedência: 'solido' | 'proxy' | 'estimativa'.
    """
    if unidade is None:
        unidade = METRICAS[metrica]["unidade"]
    if confianca is not None and confianca not in CONFIANCAS:
        raise ValueError(
            f"confianca invalida: {confianca!r} (use {', '.join(CONFIANCAS)})")
    norm = normalizar(metrica, valor_bruto)
    conn.execute(
        """INSERT INTO medicoes
             (marco_id, metrica, valor_bruto, valor_normalizado, unidade,
              observacao, confianca)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(marco_id, metrica) DO UPDATE SET
             valor_bruto       = excluded.valor_bruto,
             valor_normalizado = excluded.valor_normalizado,
             unidade           = excluded.unidade,
             observacao        = excluded.observacao,
             confianca         = excluded.confianca""",
        (marco_id, metrica, valor_bruto, norm, unidade, observacao, confianca),
    )
    return norm


def medicoes_do_marco(conn, marco_id):
    """dict metrica -> Row das medições de um marco."""
    rows = conn.execute(
        "SELECT * FROM medicoes WHERE marco_id = ?", (marco_id,)
    ).fetchall()
    return {r["metrica"]: r for r in rows}


# ---------------------------------------------------------------------------
# Consultas de leitura (usadas pelo dashboard, compare, histórico)
# ---------------------------------------------------------------------------
def historico(conn):
    """Todas as linhas da view `historico_comparativo`, ordenadas."""
    return conn.execute(
        "SELECT * FROM historico_comparativo "
        "ORDER BY metrica, versao"
    ).fetchall()


def series_por_metrica(conn):
    """Estrutura pronta para o gráfico e para exportação.

    Retorna:
      marcos  -> lista de versões na ordem cronológica
      series  -> { metrica: [ {versao, bruto, norm, delta} ... ] }
    """
    marcos = listar_marcos(conn)
    versoes = [m["versao"] for m in marcos]
    series = {metrica: [] for metrica in ORDEM}
    for marco in marcos:
        meds = medicoes_do_marco(conn, marco["id"])
        for metrica in ORDEM:
            med = meds.get(metrica)
            serie = series[metrica]
            if med is None:
                serie.append({"versao": marco["versao"], "bruto": None,
                              "norm": None, "delta": None})
                continue
            anterior = None
            for item in reversed(serie):
                if item["norm"] is not None:
                    anterior = item["norm"]
                    break
            delta = None if anterior is None else round(
                med["valor_normalizado"] - anterior, 2)
            chaves = med.keys()
            serie.append({
                "versao": marco["versao"],
                "bruto": med["valor_bruto"],
                "norm": med["valor_normalizado"],
                "delta": delta,
                "unidade": med["unidade"],
                "observacao": med["observacao"],
                "confianca": med["confianca"] if "confianca" in chaves else None,
            })
    return versoes, series


def get_metas(conn):
    """dict metrica -> Row da tabela metas."""
    rows = conn.execute("SELECT * FROM metas").fetchall()
    return {r["metrica"]: r for r in rows}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _main(argv=None):
    parser = argparse.ArgumentParser(description="Camada de dados squad-benchmark")
    parser.add_argument("cmd", choices=["init", "path", "metas"],
                        help="init: cria banco+schema+seed; path: caminho do .db; "
                             "metas: imprime o seed de metas")
    args = parser.parse_args(argv)

    if args.cmd == "path":
        print(DB_PATH)
        return 0
    if args.cmd == "metas":
        print(json.dumps(METRICAS, ensure_ascii=False, indent=2))
        return 0
    # init
    conn = connect()
    conn.close()
    print(f"OK — banco pronto em {DB_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
