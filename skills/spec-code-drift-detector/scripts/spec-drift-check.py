#!/usr/bin/env python3
"""spec-drift-check — pré-check mecânico de drift spec<->código (skill spec-code-drift-detector).

Checa (forward, mecânico, stdlib-only):
  1) Requisitos da SPEC contra a matriz de rastreabilidade — cada ReqID tem linha (código+teste)?
  2) Operações do contrato OpenAPI contra os testes — cada operationId é referenciado por algum teste?

NÃO é a prova autoritativa de conformidade (essa é rodar o teste de contrato). É um pré-check rápido
que trava o gate cedo. Reverse/scope-creep (código não rastreado) é julgamento do agente (ver SKILL.md).

  3) Convergencia (--src/--tasks/--achado): classifica cada divergencia em ausente/parcial/
     contradiz/nao-pedido, trata [x] de tasks.md como alegacao (nao evidencia) e, com --backlog,
     anexa os itens a um backlog append-only e idempotente (ver scripts/convergencia.py).

Inputs são OPCIONAIS: roda os checks possíveis com o que for fornecido.
Saída: drift-report.md + exit code 3 se houver drift, 0 se limpo.
"""
import argparse
import glob
import os
import re
import sys

from convergencia import (CLASSES, anexar_backlog, classificar_requisitos, parse_achado_manual,
                          tarefas_sem_evidencia)

REQ_RE = re.compile(r"\b(FR\d+|RN\d+|AC\d+|US\d+|REQ[-_]?[A-Za-z0-9]+)\b")
OPID_RE = re.compile(r"operationId:\s*([A-Za-z0-9_]+)")
CODE_EXT = (".java", ".py", ".ts", ".kt", ".md", ".yaml", ".yml", ".json")


def read(path):
    try:
        with open(path, encoding="utf-8-sig") as handle:  # utf-8-sig: strip BOM se houver
            return handle.read()
    except OSError:
        return None


def collect_text(directory):
    if not directory or not os.path.isdir(directory):
        return ""
    parts = []
    for path in glob.glob(os.path.join(directory, "**", "*.*"), recursive=True):
        if path.lower().endswith(CODE_EXT):
            text = read(path)
            if text:
                parts.append(text)
    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description="Pré-check mecânico de drift spec<->código.")
    parser.add_argument("--spec")
    parser.add_argument("--traceability")
    parser.add_argument("--openapi")
    parser.add_argument("--tests")
    parser.add_argument("--src")
    parser.add_argument("--tasks", help="tasks.md: [x] e alegacao; exige evidencia em codigo/teste")
    parser.add_argument("--backlog", help="backlog append-only/idempotente de divergencias")
    parser.add_argument("--achado", action="append", default=[], help="REQ:classe:motivo (julgamento)")
    parser.add_argument("--out", default="drift-report.md")
    args = parser.parse_args()

    body = []
    drift = 0

    # 1) Requisitos da SPEC vs matriz de rastreabilidade
    spec_text = read(args.spec) if args.spec else None
    trace_text = read(args.traceability) if args.traceability else None
    if spec_text:
        reqs = sorted(set(REQ_RE.findall(spec_text)))
        body.append(f"## 1. Requisitos na SPEC: {len(reqs)}")
        if trace_text:
            orphans = [r for r in reqs if r not in trace_text]
            body.append(f"- Requisitos SEM linha na matriz de rastreabilidade: **{len(orphans)}**")
            body += [f"  - 🔴 {r} — sem código/teste rastreado" for r in orphans]
            drift += len(orphans)
        else:
            body.append("- ⚠️ `--traceability` não fornecida — check de requisitos PULADO (veredito inconclusivo).")
    else:
        body.append("## 1. Requisitos: `--spec` não fornecida — check PULADO.")
    body.append("")

    # 2) Operações OpenAPI vs testes (contract coverage — heurística de presença)
    openapi_text = read(args.openapi) if args.openapi else None
    tests_text = collect_text(args.tests)
    if openapi_text:
        ops = sorted(set(OPID_RE.findall(openapi_text)))
        body.append(f"## 2. Operações no contrato OpenAPI (operationId): {len(ops)}")
        if tests_text:
            uncovered = [o for o in ops if o not in tests_text]
            body.append(f"- Operações SEM teste que as referencie: **{len(uncovered)}**")
            body += [f"  - 🟡 {o} — operationId não citado em nenhum teste" for o in uncovered]
            drift += len(uncovered)
            body.append("- Nota: heurística de presença; a PROVA é o teste de contrato passar (`OpenApiContractTest`).")
        else:
            body.append("- ⚠️ `--tests` não fornecido — check de contrato PULADO.")
    else:
        body.append("## 2. Contrato: `--openapi` não fornecido — check PULADO.")
    body.append("")

    # 3) Convergencia: taxonomia de 4 classes + [x] nao e evidencia + backlog append-only
    src_text = collect_text(args.src)
    tasks_text = read(args.tasks) if args.tasks else None
    achados = [parse_achado_manual(v) for v in args.achado]
    if spec_text and src_text:  # forward/reverse por ID exige o codigo (--src)
        achados += classificar_requisitos(spec_text, src_text, tests_text)
    if tasks_text:
        achados += tarefas_sem_evidencia(tasks_text, src_text + "\n" + tests_text)
    contagem = {c: sum(a["classe"] == c for a in achados) for c in CLASSES}
    body.append("## 3. Convergencia: " + " / ".join(f"{c}={n}" for c, n in contagem.items()))
    body += [f"- {a['req']} ({a['classe']}) {a['motivo']}" for a in achados]
    drift += len(achados)
    novos = anexar_backlog(args.backlog, achados) if args.backlog else 0
    body.append("")

    verdict = "DRIFT-FREE ✅" if drift == 0 else f"DRIFT-DETECTED 🔴 ({drift} item(ns))"
    header = [
        "# Drift Report — spec-code-drift-detector",
        "",
        f"**Veredito:** {verdict} · bloqueia GATE B se DRIFT-DETECTED.",
        "> Pré-check mecânico. Reverse/scope-creep e a prova de contrato (rodar os testes) são complementares — ver SKILL.md.",
        "",
    ]
    report = "\n".join(header + body) + "\n"
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(report)
    # stdout ASCII-safe (Windows cp1252 nao encoda emoji); relatorio rico fica no arquivo utf-8.
    summary = "DRIFT-FREE" if drift == 0 else f"DRIFT-DETECTED ({drift} item(ns))"
    print(f"Veredito: {summary}")
    print("Classes: " + " ".join(f"{c}={n}" for c, n in contagem.items()))
    if args.backlog:
        print(f"Backlog: +{novos} item(ns) em {args.backlog}")
    print(f"Relatorio: {args.out}")
    sys.exit(3 if drift else 0)


if __name__ == "__main__":
    main()
