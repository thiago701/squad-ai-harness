#!/usr/bin/env python3
"""lint_logs — CLI da skill `logs-observabilidade` (stdlib pura; roda em < 1 s).

Subcomandos:
  verificar   varre código/config/artefatos de log → achados LOG-xx + relatório JSON + código de saída
  mascarar    mostra ANTES → DEPOIS do mascaramento canônico para um texto (prova do formato)
  selftest    prova que a lente funciona: exemplos/ruim deve reprovar, exemplos/bom deve aprovar
  catalogo    imprime o catálogo de regras em Markdown (fonte: logs_obs/regras.py)

Códigos de saída (mesma convenção do contrato-reverso): 0 aprovado · 1 reprovado · 2 inconclusivo.

Exemplos:
  python -X utf8 skills/logs-observabilidade/scripts/lint_logs.py verificar --raiz . --perfil segredos
  python -X utf8 .../lint_logs.py verificar --raiz . --diff origin/master --perfil completo --falhar-em necessario
  python -X utf8 .../lint_logs.py mascarar --texto "cpf=123.456.789-09 token=eyJhbGciOiJIUzI1NiJ9.e30.abc"
  python -X utf8 .../lint_logs.py selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from logs_obs import lint, mascara, regras  # noqa: E402

SKILL = AQUI.parent
EXEMPLOS = SKILL / "exemplos"


def _utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def cmd_verificar(args: argparse.Namespace) -> int:
    raiz = Path(args.raiz)
    if not raiz.is_dir():
        print(f"::inconclusivo:: raiz inexistente: {raiz}")
        return 2
    arquivos = [Path(a) for a in args.arquivos] if args.arquivos else None
    rel = lint.executar(raiz, arquivos=arquivos, diff=args.diff, perfil=args.perfil, ignorar=args.ignorar)
    falhar_nec = args.falhar_em == "necessario"
    if args.formato == "json":
        print(json.dumps(lint.para_json(rel, falhar_nec), ensure_ascii=False, indent=2))
    else:
        lint.imprimir(rel, falhar_nec)
    if args.saida:
        destino = Path(args.saida)
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "relatorio.json").write_text(
            json.dumps(lint.para_json(rel, falhar_nec), ensure_ascii=False, indent=2), encoding="utf-8")
        if args.formato != "json":
            print(f"relatório: {destino / 'relatorio.json'}")
    codigo, _ = rel.veredito(falhar_nec)
    return codigo


def cmd_mascarar(args: argparse.Namespace) -> int:
    texto = args.texto if args.texto is not None else sys.stdin.read()
    achados = mascara.detectar(texto)
    depois = mascara.sanitizar_para_log(texto) if args.crlf else mascara.mascarar_texto(texto)
    if args.formato == "json":
        print(json.dumps({
            "depois": depois,
            "achados": [{"tipo": a.nome, "categoria": a.categoria, "inicio": a.inicio, "fim": a.fim,
                         "mascarado": a.mascarado} for a in achados],
        }, ensure_ascii=False, indent=2))
        return 0
    print("ANTES  (não reimpresso por inteiro — só tipos e posições):")
    for a in achados:
        print(f"  [{a.categoria}] {a.nome:<22} pos {a.inicio}-{a.fim}  → {a.mascarado}")
    if not achados:
        print("  (nenhum dado sensível validado encontrado)")
    print("DEPOIS:")
    print("  " + depois.replace("\n", "\n  "))
    return 0


def cmd_selftest(_: argparse.Namespace) -> int:
    ruim, bom = EXEMPLOS / "ruim", EXEMPLOS / "bom"
    if not ruim.is_dir() or not bom.is_dir():
        print("::inconclusivo:: exemplos/ruim ou exemplos/bom ausentes")
        return 2
    rel_ruim = lint.executar(ruim, perfil="completo")
    rel_bom = lint.executar(bom, perfil="completo")
    esperadas = {"LOG-01", "LOG-02", "LOG-03", "LOG-04", "LOG-05", "LOG-06", "LOG-10", "LOG-11",
                 "LOG-12", "LOG-13", "LOG-20", "LOG-21", "LOG-22"}
    vistas = {a.regra for a in rel_ruim.ativos()}
    faltam = sorted(esperadas - vistas)
    ruins_no_bom = [a for a in rel_bom.ativos() if a.severidade in (regras.BLOQ, regras.NEC)]
    print(f"selftest · ruim: {len(rel_ruim.ativos())} achados em {rel_ruim.arquivos_analisados} arquivos "
          f"· bom: {len(rel_bom.ativos())} achados em {rel_bom.arquivos_analisados} arquivos")
    ok = True
    if faltam:
        ok = False
        print(f"  ✗ regras que deveriam disparar em exemplos/ruim e não dispararam: {', '.join(faltam)}")
    if ruins_no_bom:
        ok = False
        print("  ✗ exemplos/bom não pode ter 🔴/🟡:")
        for a in ruins_no_bom:
            print(f"     {a.severidade} {a.regra} {a.arquivo}:{a.linha} — {a.detalhe}")
    # a biblioteca de máscara também é provada aqui (formato é contrato)
    provas = {
        "cpf=529.982.247-25": "cpf=***.982.247-**",
        "cartao 4111 1111 1111 1111": "cartao **** **** **** 1111",
        "email thiago.silva@exemplo.com": "email t***********@exemplo.com",
        "senha=hunter2": "senha=****",
        "Authorization: Bearer <TOKEN_EXEMPLO>": "Authorization: Bearer [TOKEN:****6789]",
    }
    for antes, esperado in provas.items():
        obtido = mascara.mascarar_texto(antes)
        if obtido != esperado:
            ok = False
            print(f"  ✗ máscara: {antes!r} → {obtido!r} (esperado {esperado!r})")
    print("RESULTADO: " + ("APROVADO" if ok else "REPROVADO"))
    return 0 if ok else 1


def cmd_catalogo(_: argparse.Namespace) -> int:
    print(regras.tabela_markdown())
    return 0


def main(argv: list[str] | None = None) -> int:
    _utf8()
    ap = argparse.ArgumentParser(prog="lint_logs", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("verificar", help="varre código/config/artefatos de log")
    v.add_argument("--raiz", default=".")
    v.add_argument("--arquivos", nargs="*", help="lista explícita (relativa à raiz); default: árvore inteira")
    v.add_argument("--diff", help="ref git: só arquivos alterados/novos em relação a ela")
    v.add_argument("--perfil", choices=("segredos", "completo"), default="segredos",
                   help="segredos = só vazamento (push); completo = todas as regras (review)")
    v.add_argument("--falhar-em", choices=("bloqueante", "necessario"), default="bloqueante",
                   help="necessario também reprova com 🟡 (modo review)")
    v.add_argument("--ignorar", nargs="*", default=[], help="globs relativos a ignorar")
    v.add_argument("--saida", help="diretório para relatorio.json")
    v.add_argument("--formato", choices=("texto", "json"), default="texto")
    v.set_defaults(fn=cmd_verificar)

    m = sub.add_parser("mascarar", help="mostra antes → depois do mascaramento canônico")
    m.add_argument("--texto", help="texto a mascarar (default: stdin)")
    m.add_argument("--crlf", action="store_true", help="também neutraliza \\r\\n (anti log forging)")
    m.add_argument("--formato", choices=("texto", "json"), default="texto")
    m.set_defaults(fn=cmd_mascarar)

    s = sub.add_parser("selftest", help="prova a lente com exemplos/ruim e exemplos/bom")
    s.set_defaults(fn=cmd_selftest)

    c = sub.add_parser("catalogo", help="catálogo LOG-xx em Markdown")
    c.set_defaults(fn=cmd_catalogo)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
