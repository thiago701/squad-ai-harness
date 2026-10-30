#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""registrar.py — registra um marco + as 5 medições (A–E) da skill `squad-benchmark`.

Recebe os valores BRUTOS já parseados pela skill (a partir da frase do usuário,
inline ou por entrevista), valida faixas, calcula normalização, grava e
**regenera o dashboard automaticamente** (OA-12). Ao final imprime um resumo
com os deltas vs. o marco anterior.

Regra de sobrescrita (OA-3): se o marco já existir, NÃO sobrescreve sem `--force`.
Sem `--force` retorna exit code 2 e uma mensagem — cabe à skill pedir confirmação
explícita ao humano e só então repetir o comando com `--force`.

Valores brutos por métrica:
  A, C, E : 0–100          B : 0–100 (% de redução)          D : multiplicador x (>0)
O parser aceita D como "5.2" ou "5.2x".

Stdlib apenas. Exemplo:
  python registrar.py --versao v5 --contexto "novo cérebro" \\
    --A 82 --B 76 --C 88 --D 5.2x --E 71
  python registrar.py --versao v5 ... --force      # sobrescreve após confirmação
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db          # noqa: E402
import dashboard   # noqa: E402

# Faixa válida do valor BRUTO por métrica (D é multiplicador, sem teto rígido).
FAIXAS = {"A": (0, 100), "B": (0, 100), "C": (0, 100), "E": (0, 100)}


def parse_valor(metrica, texto):
    """Converte a string do valor bruto em float, tolerando o sufixo 'x' do D."""
    t = str(texto).strip().lower().replace(",", ".")
    if metrica == "D" and t.endswith("x"):
        t = t[:-1].strip()
    try:
        return float(t)
    except ValueError:
        raise SystemExit(f"ERRO: valor inválido para métrica {metrica}: {texto!r}")


def validar(metrica, valor):
    """Valida a faixa do valor bruto; lança SystemExit(1) se fora."""
    if metrica == "D":
        if valor <= 0:
            raise SystemExit(f"ERRO: D (velocidade) deve ser > 0 (recebido {valor}).")
        return
    lo, hi = FAIXAS[metrica]
    if not (lo <= valor <= hi):
        raise SystemExit(
            f"ERRO: {metrica} fora da faixa [{lo}, {hi}] (recebido {valor})."
        )


def registrar(versao, valores, contexto=None, observacoes=None,
              confiancas=None, data=None, force=False):
    """Grava marco + medições. Retorna (exit_code, mensagem, resumo|None).

    exit_code 2 = marco existe e force=False (pedir confirmação).
    `confiancas`: dict metrica -> 'solido'|'proxy'|'estimativa' (opcional).
    """
    versao = versao.strip()
    if not versao:
        raise SystemExit("ERRO: versão do marco é obrigatória (ex.: v1).")

    # Parse + valida os 5 valores ANTES de tocar no banco.
    brutos = {}
    for m in db.ORDEM:
        if m not in valores or valores[m] in (None, ""):
            raise SystemExit(f"ERRO: métrica {m} não informada. As 5 (A–E) são obrigatórias.")
        v = parse_valor(m, valores[m])
        validar(m, v)
        brutos[m] = v

    conn = db.connect()
    try:
        existente = db.get_marco(conn, versao)
        if existente is not None and not force:
            # OA-3: nunca sobrescreve em silêncio.
            atuais = db.medicoes_do_marco(conn, existente["id"])
            resumo_atual = ", ".join(
                f"{m}={atuais[m]['valor_bruto']:g}{atuais[m]['unidade']}"
                for m in db.ORDEM if m in atuais
            )
            msg = (
                f"CONFIRMACAO_NECESSARIA: o marco '{versao}' já existe "
                f"(data {existente['data']}).\n"
                f"  Valores atuais: {resumo_atual or '(sem medições)'}\n"
                f"  Para sobrescrever, confirme e rode novamente com --force."
            )
            return 2, msg, None

        marco_id = db.upsert_marco(conn, versao, contexto=contexto, data=data)
        observacoes = observacoes or {}
        confiancas = confiancas or {}
        for m in db.ORDEM:
            db.upsert_medicao(conn, marco_id, m, brutos[m],
                              observacao=observacoes.get(m),
                              confianca=confiancas.get(m))
        conn.commit()

        # Resumo com deltas vs. marco anterior (mesmo banco/conn).
        _, series = db.series_por_metrica(conn)
        resumo = []
        for m in db.ORDEM:
            atual = series[m][-1]
            resumo.append({
                "metrica": m,
                "nome": db.METRICAS[m]["nome"],
                "bruto": atual["bruto"],
                "unidade": atual.get("unidade") or db.METRICAS[m]["unidade"],
                "norm": atual["norm"],
                "delta": atual["delta"],
                "pct_meta": db.pct_meta(m, atual["norm"]),
            })

        # OA-12: regenera o dashboard automaticamente após cada registro.
        dash_path = dashboard.render(conn)
    finally:
        conn.close()

    acao = "sobrescrito" if (existente is not None) else "registrado"
    return 0, f"Marco '{versao}' {acao}.", {"resumo": resumo, "dashboard": dash_path}


def _print_resumo(versao, msg, extra):
    print(msg)
    resumo = extra["resumo"]
    print(f"\n  {'Métrica':<40} {'Bruto':>10} {'Norm':>7} {'Δ ant.':>8} {'% meta':>8}")
    print("  " + "-" * 76)
    for r in resumo:
        d = r["delta"]
        dtxt = "novo" if d is None else (f"+{d:g}" if d > 0 else f"{d:g}")
        seta = "" if d is None else (" ▲" if d > 0 else (" ▼" if d < 0 else " ="))
        nome = f"{r['metrica']} · {r['nome']}"
        print(f"  {nome:<40} {r['bruto']:>8g}{r['unidade']:<2} "
              f"{r['norm']:>7g} {dtxt+seta:>8} {r['pct_meta']:>7g}%")
    print(f"\n  Dashboard: {extra['dashboard']}")


def _main(argv=None):
    p = argparse.ArgumentParser(description="Registra um marco do squad-benchmark")
    p.add_argument("--versao", required=True, help="ex.: v1, v2, v3")
    p.add_argument("--contexto", default=None, help="o que mudou no Squad AI")
    p.add_argument("--data", default=None, help="YYYY-MM-DD (default: hoje)")
    p.add_argument("--force", action="store_true",
                   help="sobrescreve um marco existente (após confirmação humana)")
    for m in db.ORDEM:
        p.add_argument(f"--{m}", required=True,
                       help=f"valor bruto da métrica {m} "
                            f"({db.METRICAS[m]['nome']})")
        p.add_argument(f"--obs-{m}", default=None, dest=f"obs_{m}",
                       help=f"observação opcional da métrica {m}")
        p.add_argument(f"--conf-{m}", default=None, dest=f"conf_{m}",
                       choices=db.CONFIANCAS,
                       help=f"confiança da métrica {m}: {'|'.join(db.CONFIANCAS)}")
    args = p.parse_args(argv)

    valores = {m: getattr(args, m) for m in db.ORDEM}
    observacoes = {m: getattr(args, f"obs_{m}") for m in db.ORDEM}
    confiancas = {m: getattr(args, f"conf_{m}") for m in db.ORDEM}

    code, msg, extra = registrar(
        args.versao, valores, contexto=args.contexto,
        observacoes=observacoes, confiancas=confiancas,
        data=args.data, force=args.force,
    )
    if code == 0:
        _print_resumo(args.versao, msg, extra)
    else:
        print(msg)
    return code


if __name__ == "__main__":
    sys.exit(_main())
