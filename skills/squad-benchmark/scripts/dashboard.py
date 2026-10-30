#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dashboard.py — renderiza o dashboard HTML autocontido da skill `squad-benchmark`.

Lê o banco SQLite (via db.py), monta um payload JSON e injeta no template
`assets/dashboard.template.html` (Chart.js via CDN). O resultado, `dashboard.html`,
é escrito ao lado do `.db` e abre offline no navegador — sem build, sem servidor.

Também exporta os dados em CSV + JSON (comando `export`).

Stdlib apenas: `sqlite3` (via db.py), `json`, `csv`, `os`, `argparse`, `datetime`.
"""
import argparse
import csv
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db  # noqa: E402

TEMPLATE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "assets", "dashboard.template.html",
)
DASHBOARD_PATH = os.path.join(db.DB_DIR, "dashboard.html")
CSV_PATH = os.path.join(db.DB_DIR, "benchmark.csv")
JSON_PATH = os.path.join(db.DB_DIR, "benchmark.json")


# ---------------------------------------------------------------------------
# Montagem do payload
# ---------------------------------------------------------------------------
def _rotulo_meta(metrica):
    """Rótulo humano da meta (ex.: '≥ 90', '7x = 100')."""
    meta = db.METRICAS[metrica]
    if metrica == "D":
        return "7x (= 100)"
    return "≥ " + _fmt(meta["valor_meta"], 0) + " " + meta["unidade"]


def _fmt(v, casas=1):
    if v is None:
        return "—"
    return f"{float(v):.{casas}f}".rstrip("0").rstrip(".") if casas else f"{float(v):.0f}"


def build_payload(conn):
    """Constrói o dicionário que o template consome."""
    versoes, series = db.series_por_metrica(conn)
    marcos = db.listar_marcos(conn)
    ultimo = marcos[-1] if marcos else None

    metricas_meta = {}
    for m in db.ORDEM:
        meta = db.METRICAS[m]
        metricas_meta[m] = {
            "nome": meta["nome"],
            "unidade": meta["unidade"],
            "cor": meta["cor"],
            "formula": meta["formula_normalizacao"],
            "meta_bruta": meta["valor_meta"],
            "meta_norm": db.meta_normalizada(m),
            "meta_rotulo": _rotulo_meta(m),
            "baseline": meta["baseline_sem_squad"],
        }

    payload = {
        "gerado_em": date.today().isoformat(),
        "ultimo_marco": ultimo["versao"] if ultimo else None,
        "ultima_data": ultimo["data"] if ultimo else None,
        "ultimo_contexto": ultimo["contexto"] if ultimo else None,
        "ultimo_legado": db.is_legado(ultimo["versao"]) if ultimo else False,
        "ordem": db.ORDEM,
        "metricas": metricas_meta,
        "marcos": versoes,
        # tipo de cada marco (para distinguir histórico importado do timeline real)
        "marcos_tipo": ["legado" if db.is_legado(v) else "real" for v in versoes],
        "series": {m: [p["norm"] for p in series[m]] for m in db.ORDEM},
        "series_bruto": {m: [p["bruto"] for p in series[m]] for m in db.ORDEM},
        "cards": [],
        "tabela": [],
        "resumo": None,
    }

    if not marcos:
        return payload

    # Cards do último marco: norm atual, delta vs anterior, % da meta, procedência.
    na_meta, abaixo, sem_dado = [], [], []
    for m in db.ORDEM:
        pontos = series[m]
        atual = pontos[-1]
        pct = None if atual["norm"] is None else db.pct_meta(m, atual["norm"])
        bateu = pct is not None and pct >= 100
        if atual["norm"] is None:
            sem_dado.append(m)
        elif bateu:
            na_meta.append(m)
        else:
            abaixo.append(m)
        payload["cards"].append({
            "metrica": m,
            "nome": db.METRICAS[m]["nome"],
            "cor": db.METRICAS[m]["cor"],
            "unidade": atual.get("unidade") or db.METRICAS[m]["unidade"],
            "norm": atual["norm"],
            "bruto": atual["bruto"],
            "delta": atual["delta"],
            "pct_meta": pct,
            "bateu_meta": bateu,
            "meta_norm": metricas_meta[m]["meta_norm"],
            "confianca": atual.get("confianca"),
            "observacao": atual.get("observacao"),
        })

    # Resumo executivo (linguagem natural, foco em "vs meta", não "vs anterior").
    payload["resumo"] = {
        "total": len(db.ORDEM),
        "na_meta": na_meta,
        "abaixo": abaixo,
        "sem_dado": sem_dado,
        "n_na_meta": len(na_meta),
    }

    # Tabela: atual vs anterior vs melhor histórico.
    for m in db.ORDEM:
        pontos = [p for p in series[m] if p["norm"] is not None]
        atual = pontos[-1]["norm"] if pontos else None
        anterior = pontos[-2]["norm"] if len(pontos) >= 2 else None
        melhor = max((p["norm"] for p in pontos), default=None)
        payload["tabela"].append({
            "metrica": m,
            "nome": db.METRICAS[m]["nome"],
            "atual": atual,
            "anterior": anterior,
            "melhor": melhor,
            "delta_ant": (None if atual is None or anterior is None
                          else round(atual - anterior, 2)),
            "delta_melhor": (None if atual is None or melhor is None
                             else round(atual - melhor, 2)),
        })
    return payload


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
def render(conn=None):
    """Gera dashboard.html e retorna o caminho. Abre o banco se não vier um."""
    own = conn is None
    if own:
        conn = db.connect()
    try:
        payload = build_payload(conn)
    finally:
        if own:
            conn.close()

    with open(TEMPLATE, encoding="utf-8") as fh:
        template = fh.read()

    data_json = json.dumps(payload, ensure_ascii=False)
    # O placeholder vive dentro de um comentário JS para manter o template
    # válido/abrível sozinho; substituímos o comentário inteiro pelo JSON.
    html = template.replace("/*{{DATA_JSON}}*/", data_json)

    os.makedirs(db.DB_DIR, exist_ok=True)
    with open(DASHBOARD_PATH, "w", encoding="utf-8") as fh:
        fh.write(html)
    return DASHBOARD_PATH


# ---------------------------------------------------------------------------
# Export CSV + JSON
# ---------------------------------------------------------------------------
def export(conn=None):
    """Exporta o histórico completo para CSV e JSON ao lado do banco."""
    own = conn is None
    if own:
        conn = db.connect()
    try:
        linhas = db.historico(conn)
        payload = build_payload(conn)
    finally:
        if own:
            conn.close()

    os.makedirs(db.DB_DIR, exist_ok=True)
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["versao", "data", "metrica", "valor_bruto",
                         "valor_normalizado", "delta_vs_anterior"])
        for r in linhas:
            writer.writerow([r["versao"], r["data"], r["metrica"],
                             r["valor_bruto"], r["valor_normalizado"],
                             r["delta_vs_anterior"]])
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return CSV_PATH, JSON_PATH


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _main(argv=None):
    parser = argparse.ArgumentParser(description="Dashboard squad-benchmark")
    parser.add_argument("cmd", nargs="?", default="render",
                        choices=["render", "export"],
                        help="render: gera dashboard.html; export: gera CSV + JSON")
    args = parser.parse_args(argv)

    conn = db.connect()
    try:
        if args.cmd == "render":
            path = render(conn)
            print(f"Dashboard gerado em: {path}")
        else:
            csv_p, json_p = export(conn)
            print(f"CSV:  {csv_p}")
            print(f"JSON: {json_p}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(_main())
