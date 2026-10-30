# -*- coding: utf-8 -*-
"""contrato-reverso — testes reversos dirigidos pelo consumidor, para QUALQUER projeto.

    iniciar     projeto novo: detecta OpenAPI + Gateway (SAM), gera o rascunho do contrato do
                consumidor e copia o verificador do provedor para o stack detectado
    verificar   roda o nível pedido (rapido | direcionado | ampliado | auto)
                saída: 0 aprovado · 1 reprovado · 2 inconclusivo
    impacto     mostra o nível que o diff atual exige, por contrato (não roda nada)
    observar    modo contínuo local (debounce, cancelamento, trava, nível por impacto)
    bench       regressões controladas (mutações automáticas + do projeto): detecção,
                falsos positivos e tempo, antes × depois

Use `--raiz <projeto>` (padrão: diretório atual). Contratos em <raiz>/contracts/consumidores/.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import CODIGO_SAIDA, QUEBRA
from . import impacto as imp_mod
from .modelo import carregar_contrato, descobrir_contratos
from .nucleo import pasta_saida_padrao, veredito_agregado, verificar


def _raiz(args) -> Path:
    return Path(args.raiz).resolve() if getattr(args, "raiz", None) else Path.cwd().resolve()


def _contratos(raiz: Path, args) -> list[Path]:
    if getattr(args, "contrato", None):
        return [Path(c).resolve() for c in args.contrato]
    return descobrir_contratos(raiz)


def _resumo(r: dict) -> str:
    quebras = [a for a in r["achados"] if a["severidade"] == QUEBRA and not a.get("aceito")]
    riscos = sum(1 for a in r["achados"] if a["severidade"] == "risco")
    pend = sum(1 for a in r["achados"] if a["severidade"] == "pendente")
    camadas = " ".join(f"{n}={'ok' if c['executada'] and not c['quebras'] else ('✗' if c['executada'] else '∅')}"
                       f"{'(cache)' if c['cache'] else ''}" for n, c in r["camadas"].items())
    linhas = [f"[{r['veredito'].upper()}] {r.get('consumidor')} · nível {r['nivel']} · {r['duracao_s']}s · {camadas} · "
              f"quebras={len(quebras)} riscos={riscos} pendentes={pend}"]
    linhas += [f"   ✗ {a['camada']} {a['codigo']} [{a['interacao'] or '*'}] {a['mensagem']}" for a in quebras[:12]]
    for nome, c in r["camadas"].items():
        if not c["executada"] and c["motivo_nao_execucao"]:
            linhas.append(f"   ∅ {nome}: {c['motivo_nao_execucao']}")
    return "\n".join(linhas)


def cmd_verificar(args) -> int:
    raiz = _raiz(args)
    contratos = _contratos(raiz, args)
    if not contratos:
        print(f"nenhum contrato em {raiz / 'contracts' / 'consumidores'} — nada verificado (inconclusivo). "
              "Projeto novo? rode `cr.py iniciar`.")
        print("::inconclusivo::sem-contrato")
        return CODIGO_SAIDA["inconclusivo"]
    resultados = []
    saida = Path(args.saida).resolve() if args.saida else pasta_saida_padrao(raiz)
    alterados, base_desc = (imp_mod.arquivos_alterados(raiz, args.base) if args.nivel == "auto" else ([], ""))
    for arq in contratos:
        nivel, suite = args.nivel, args.suite_completa
        if nivel == "auto":
            imp = imp_mod.avaliar(carregar_contrato(arq, raiz), alterados)
            if imp.nivel == "nenhum":
                print(f"[SEM IMPACTO] {arq.name}: nenhum arquivo do fluxo mudou ({base_desc}) — vazio legítimo")
                continue
            nivel, suite = imp.nivel, suite or imp.suite_completa
            print(f"impacto {arq.name}: {nivel}{' + suíte completa' if suite else ''}"
                  f"{' (INCERTO → amplia)' if imp.incerto else ''}"
                  f"{' · recomenda ampliado (Gateway mudou)' if imp.recomenda_ampliado else ''}")
        r = verificar(arq, raiz, nivel=nivel, suite_completa=suite, alvo=args.alvo, ambiente=args.ambiente,
                      permitir_escrita=args.permitir_escrita, usar_cache=not args.sem_cache, dir_saida=saida)
        resultados.append(r)
        print(_resumo(r) if args.resumo else _resumo(r) + f"\n   relatório: {saida / (r.get('consumidor') or 'contrato')}.md")
    if not resultados:
        return 0
    veredito = veredito_agregado(resultados)
    if args.json:
        print(json.dumps(resultados, ensure_ascii=False, indent=2, default=str))
    if veredito == "inconclusivo":
        print("::inconclusivo::contrato-reverso")  # marcador de harness: inconclusivo nunca vira sucesso
    return CODIGO_SAIDA[veredito]


def cmd_impacto(args) -> int:
    raiz = _raiz(args)
    alterados, base_desc = imp_mod.arquivos_alterados(raiz, args.base)
    if args.alterado:
        alterados, base_desc = args.alterado, "lista informada"
    saida = {"base": base_desc, "alterados": len(alterados), "contratos": {}}
    for arq in _contratos(raiz, args):
        saida["contratos"][arq.name] = imp_mod.avaliar(carregar_contrato(arq, raiz), alterados).__dict__
    print(json.dumps(saida, ensure_ascii=False, indent=2))
    return 0


def cmd_observar(args) -> int:
    from .observar import observar
    raiz = _raiz(args)
    return observar(raiz, _contratos(raiz, args), intervalo=args.intervalo, debounce=args.debounce,
                    saida_relatorios=Path(args.saida).resolve() if args.saida else None)


def cmd_bench(args) -> int:
    from .bench import executar
    raiz = _raiz(args)
    return executar(raiz, _contratos(raiz, args), Path(args.saida).resolve() if args.saida else None,
                    repeticoes=args.repeticoes, incluir_dinamico=not args.so_estatico,
                    max_por_operador=args.max_por_operador)


def cmd_iniciar(args) -> int:
    from .iniciar import iniciar
    return iniciar(_raiz(args), consumidor=args.consumidor, tipo=args.tipo, origem=args.origem_navegador,
                   sobrescrever=args.sobrescrever)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="cr.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def comum(p):
        p.add_argument("--raiz", help="raiz do projeto (padrão: diretório atual)")
        p.add_argument("--contrato", action="append", help="contrato específico (padrão: todos em contracts/consumidores)")
        return p

    v = comum(sub.add_parser("verificar"))
    v.add_argument("--nivel", choices=("rapido", "direcionado", "ampliado", "auto"), default="rapido")
    v.add_argument("--base", help="ref git para o diff do nível auto (ex.: origin/main)")
    v.add_argument("--suite-completa", action="store_true")
    v.add_argument("--alvo", help="URL base do Gateway para C2")
    v.add_argument("--ambiente", help="ambiente declarado no contrato (local | dev | ...)")
    v.add_argument("--permitir-escrita", action="store_true", help="autoriza POST/PATCH/DELETE na replay C2")
    v.add_argument("--sem-cache", action="store_true")
    v.add_argument("--saida", help="pasta dos relatórios (padrão: <raiz>/.contrato-reverso/relatorios)")
    v.add_argument("--resumo", action="store_true")
    v.add_argument("--json", action="store_true")
    v.set_defaults(func=cmd_verificar)
    i = comum(sub.add_parser("impacto"))
    i.add_argument("--base")
    i.add_argument("--alterado", action="append", help="simula arquivos alterados")
    i.set_defaults(func=cmd_impacto)
    o = comum(sub.add_parser("observar"))
    o.add_argument("--intervalo", type=float, default=0.5)
    o.add_argument("--debounce", type=float, default=0.4)
    o.add_argument("--saida")
    o.set_defaults(func=cmd_observar)
    b = comum(sub.add_parser("bench"))
    b.add_argument("--saida")
    b.add_argument("--repeticoes", type=int, default=3)
    b.add_argument("--so-estatico", action="store_true", help="sem C1/suíte (máquina sem JDK/Maven)")
    b.add_argument("--max-por-operador", type=int, default=2)
    b.set_defaults(func=cmd_bench)
    n = sub.add_parser("iniciar")
    n.add_argument("--raiz")
    n.add_argument("--consumidor", default="consumidor-principal")
    n.add_argument("--tipo", choices=("navegador", "servico"), default="servico")
    n.add_argument("--origem-navegador", default="")
    n.add_argument("--sobrescrever", action="store_true")
    n.set_defaults(func=cmd_iniciar)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
