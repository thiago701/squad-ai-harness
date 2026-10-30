#!/usr/bin/env python3
"""lint_memoria — CLI da skill `python-memoria` (stdlib pura).

Subcomandos:
  verificar   lente AST de memória em código Python → achados MEM-xx + relatório JSON + código de saída
  medir       executa um script sob medição (pico de heap Python + RSS do processo) e imprime o resumo
  arvore      executa QUALQUER comando e mede a árvore de processos (RSS/USS/PSS por processo, pico da árvore,
              processos simultâneos, spawns, vida de cada um; --execs conta execve via strace no Linux)
  selftest    prova que a lente funciona: exemplos/ruim reprova (todas as regras mecânicas), exemplos/bom aprova
  catalogo    imprime o catálogo MEM-xx em Markdown (fonte: memoria/regras.py)

Códigos de saída: 0 aprovado · 1 reprovado (só com --falhar-em necessario) · 2 inconclusivo.

Exemplos:
  python -X utf8 skills/python-memoria/scripts/lint_memoria.py verificar --raiz . --diff origin/master --falhar-em necessario
  python -X utf8 skills/python-memoria/scripts/lint_memoria.py verificar --raiz . --perfil observacional --saida ops/logs/python-memoria
  python -X utf8 skills/python-memoria/scripts/lint_memoria.py medir --script scripts/relatorio_dora.py -- --help
  python -X utf8 skills/python-memoria/scripts/lint_memoria.py arvore --rotulo gate --execs -- python ops/run.py gate
  python -X utf8 skills/python-memoria/scripts/lint_memoria.py selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from memoria import arvore, lint, orcamento, regras  # noqa: E402

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
    rel = lint.executar(raiz, arquivos=arquivos, diff=args.diff, perfil=args.perfil, ignorar=args.ignorar,
                        incluir_testes=args.incluir_testes)
    falhar = args.falhar_em == "necessario"
    if args.formato == "json":
        print(json.dumps(lint.para_json(rel, falhar), ensure_ascii=False, indent=2))
    else:
        lint.imprimir(rel, falhar, maximo=args.maximo)
    if args.saida:
        destino = Path(args.saida)
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "relatorio.json").write_text(json.dumps(lint.para_json(rel, falhar), ensure_ascii=False, indent=2),
                                                encoding="utf-8")
        if args.formato != "json":
            print(f"relatório: {destino / 'relatorio.json'}")
    codigo, _ = rel.veredito(falhar)
    return codigo


def cmd_medir(args: argparse.Namespace) -> int:
    script = Path(args.script)
    if not script.is_file():
        print(f"::inconclusivo:: script inexistente: {script}")
        return 2
    m = orcamento.medir_script(str(script), args.argv, heap=not args.so_rss)
    print(m.resumo())
    if args.max_pico_mb is not None and m.pico_mb > args.max_pico_mb:
        print(f"RESULTADO: REPROVADO (heap pico {m.pico_mb:.2f} MB > {args.max_pico_mb} MB)")
        return 1
    if args.max_rss_mb is not None and m.rss_pico_mb is not None and m.rss_pico_mb > args.max_rss_mb:
        print(f"RESULTADO: REPROVADO (RSS pico {m.rss_pico_mb:.1f} MB > {args.max_rss_mb} MB)")
        return 1
    print("RESULTADO: APROVADO")
    return 0


def cmd_arvore(args: argparse.Namespace) -> int:
    if not args.argv:
        print("::inconclusivo:: informe o comando após `--`")
        return 2
    if not arvore.amostragem_disponivel():
        print("::inconclusivo:: fora do Linux a amostragem da árvore exige `psutil` (pip install psutil) — nada medido")
        return 2
    entrada = args.stdin
    if args.stdin_arquivo:
        entrada = Path(args.stdin_arquivo).read_text(encoding="utf-8")
    r = arvore.medir_arvore(args.argv, rotulo=args.rotulo or "", intervalo_ms=args.intervalo_ms,
                            execs=args.execs, timeout_s=args.timeout_s, silencioso=not args.mostrar_saida,
                            entrada=entrada)
    print(arvore.resumo_texto(r, top=args.top))
    if args.saida:
        destino = Path(args.saida)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(arvore.para_json(r), encoding="utf-8")
        print(f"json: {destino}")
    if args.max_pico_mb is not None and r.pico_rss_arvore_mb > args.max_pico_mb:
        print(f"RESULTADO: REPROVADO (RSS pico da árvore {r.pico_rss_arvore_mb} MB > {args.max_pico_mb} MB)")
        return 1
    print("RESULTADO: APROVADO" if r.rc == 0 else f"RESULTADO: INCONCLUSIVO (comando saiu com rc={r.rc})")
    return 0 if r.rc == 0 else 2


def cmd_selftest(_: argparse.Namespace) -> int:
    ruim, bom = EXEMPLOS / "ruim", EXEMPLOS / "bom"
    if not ruim.is_dir() or not bom.is_dir():
        print("::inconclusivo:: exemplos/ruim ou exemplos/bom ausentes")
        return 2
    rel_ruim = lint.executar(ruim, perfil="review", incluir_testes=True)
    rel_bom = lint.executar(bom, perfil="review", incluir_testes=True)
    esperadas = set(regras.IDS_MECANICAS)
    vistas = {a.regra for a in rel_ruim.ativos()}
    faltam = sorted(esperadas - vistas)
    sobras = rel_bom.ativos()
    print(f"selftest · ruim: {len(rel_ruim.ativos())} achados em {rel_ruim.arquivos_analisados} arquivos "
          f"· bom: {len(sobras)} achados em {rel_bom.arquivos_analisados} arquivos")
    ok = True
    if faltam:
        ok = False
        print(f"  ✗ regras mecânicas que não dispararam em exemplos/ruim: {', '.join(faltam)}")
    if sobras:
        ok = False
        print("  ✗ exemplos/bom não pode ter achados:")
        for a in sobras:
            print(f"     {a.severidade} {a.regra} {a.arquivo}:{a.linha} — {a.detalhe}")
    # o medidor também é provado aqui
    with orcamento.orcamento(rotulo="selftest") as m:
        _ = [0] * 200_000
    if m.pico_mb <= 0:
        ok = False
        print("  ✗ orçamento: tracemalloc não mediu pico")
    print("RESULTADO: " + ("APROVADO" if ok else "REPROVADO"))
    return 0 if ok else 1


def cmd_catalogo(_: argparse.Namespace) -> int:
    print(regras.tabela_markdown())
    return 0


def main(argv: list[str] | None = None) -> int:
    _utf8()
    ap = argparse.ArgumentParser(prog="lint_memoria", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("verificar", help="lente AST de memória em código Python")
    v.add_argument("--raiz", default=".")
    v.add_argument("--arquivos", nargs="*", help="lista explícita (relativa à raiz); default: árvore (via git ls-files)")
    v.add_argument("--diff", help="ref git: só arquivos .py alterados/novos em relação a ela")
    v.add_argument("--perfil", choices=("review", "observacional"), default="review",
                   help="review = 🟡+🔵 (PR); observacional = só 🟡 (SLI/nightly, nunca bloqueia)")
    v.add_argument("--falhar-em", choices=("bloqueante", "necessario"), default="bloqueante",
                   help="necessario reprova com 🟡 (modo review); default nunca reprova (memória não tem veto)")
    v.add_argument("--incluir-testes", action="store_true", help="também analisa tests/ e test_*.py")
    v.add_argument("--ignorar", nargs="*", default=[], help="globs relativos a ignorar")
    v.add_argument("--saida", help="diretório para relatorio.json")
    v.add_argument("--formato", choices=("texto", "json"), default="texto")
    v.add_argument("--maximo", type=int, default=80, help="máximo de achados impressos")
    v.set_defaults(fn=cmd_verificar)

    m = sub.add_parser("medir", help="executa um script sob medição de memória")
    m.add_argument("--script", required=True)
    m.add_argument("--max-pico-mb", type=float, help="reprova se o heap Python passar disso")
    m.add_argument("--max-rss-mb", type=float, help="reprova se o RSS pico passar disso")
    m.add_argument("--so-rss", action="store_true", help="sem tracemalloc (número de produção; tracemalloc infla o RSS)")
    m.add_argument("argv", nargs=argparse.REMAINDER, help="argumentos do script (após --)")
    m.set_defaults(fn=cmd_medir)

    a = sub.add_parser("arvore", help="mede a árvore de processos de um comando (RSS/USS/PSS, pico, spawns, vida)")
    a.add_argument("--rotulo", default="")
    a.add_argument("--intervalo-ms", type=int, default=50)
    a.add_argument("--execs", action="store_true", help="Linux: conta execve com strace -f (vê processos de vida curta)")
    a.add_argument("--timeout-s", type=float)
    a.add_argument("--top", type=int, default=8, help="quantos processos listar no resumo")
    a.add_argument("--saida", help="arquivo JSON com o relatório completo")
    a.add_argument("--max-pico-mb", type=float, help="reprova se o RSS pico da árvore passar disso")
    a.add_argument("--mostrar-saida", action="store_true", help="deixa stdout/stderr do comando passarem")
    a.add_argument("--stdin", help="texto entregue ao stdin do comando (ex.: JSON de um hook do Claude Code)")
    a.add_argument("--stdin-arquivo", help="arquivo cujo conteúdo vai para o stdin do comando")
    a.add_argument("argv", nargs=argparse.REMAINDER, help="comando a medir (após --)")
    a.set_defaults(fn=cmd_arvore)

    s = sub.add_parser("selftest", help="prova a lente com exemplos/ruim e exemplos/bom")
    s.set_defaults(fn=cmd_selftest)

    c = sub.add_parser("catalogo", help="catálogo MEM-xx em Markdown")
    c.set_defaults(fn=cmd_catalogo)

    args = ap.parse_args(argv)
    if getattr(args, "argv", None) and args.argv[:1] == ["--"]:
        args.argv = args.argv[1:]
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
