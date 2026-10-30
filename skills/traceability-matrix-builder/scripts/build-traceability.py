#!/usr/bin/env python3
"""build-traceability — gera/atualiza a matriz de rastreabilidade SDD (skill traceability-matrix-builder).

Liga cada ReqID da SPEC ao codigo + testes que o CITAM (por tag), com criterio e status. Detecta tags
orfas (ReqID no codigo/teste, ausente da spec). Stdlib-only, stdout ASCII, arquivo utf-8.

CONVENCAO: codigo e testes devem citar o ReqID que cobrem (comentario, @DisplayName, @Tag, // @covers FRx).
Sem tag nao ha rastreabilidade mecanica -- a skill exige a tag.
"""
import argparse
import glob
import os
import re
import sys

REQ_RE = re.compile(r"\b(FR\d+|RN\d+|AC\d+|US\d+|REQ[-_]?[A-Za-z0-9]+)\b")
CODE_EXT = (".java", ".py", ".ts", ".kt")


def read(path):
    try:
        with open(path, encoding="utf-8-sig") as handle:  # utf-8-sig: strip BOM se houver
            return handle.read()
    except OSError:
        return None


def spec_reqs(text):
    out = {}
    for line in (text or "").splitlines():
        for req in REQ_RE.findall(line):
            if req not in out:
                out[req] = line.strip().replace("|", "/")[:80]
    return out


def files_in(directory, exts):
    if not directory or not os.path.isdir(directory):
        return []
    return [p for p in glob.glob(os.path.join(directory, "**", "*.*"), recursive=True)
            if p.lower().endswith(exts)]


def tags_in(path):
    text = read(path)
    return set(REQ_RE.findall(text)) if text else set()


def main():
    parser = argparse.ArgumentParser(description="Gera a matriz de rastreabilidade SDD.")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--src")
    parser.add_argument("--tests")
    parser.add_argument("--out", default="traceability.md")
    args = parser.parse_args()

    spec_text = read(args.spec)
    if spec_text is None:
        print(f"ERRO: SPEC nao encontrada: {args.spec}")
        sys.exit(2)
    reqs = spec_reqs(spec_text)

    code_map = {r: set() for r in reqs}
    test_map = {r: set() for r in reqs}
    seen = set()
    for path in files_in(args.src, CODE_EXT):
        for req in tags_in(path):
            seen.add(req)
            if req in code_map:
                code_map[req].add(os.path.basename(path))
    for path in files_in(args.tests, CODE_EXT):
        for req in tags_in(path):
            seen.add(req)
            if req in test_map:
                test_map[req].add(os.path.basename(path))

    rows, ok = [], 0
    for req, criterion in reqs.items():
        code = sorted(code_map[req])
        test = sorted(test_map[req])
        if code and test:
            status, ok = "OK", ok + 1
        elif not code and not test:
            status = "ORFAO(sem codigo/teste)"
        elif not test:
            status = "SEM-TESTE"
        else:
            status = "SEM-CODIGO"
        rows.append((req, criterion, ", ".join(code)[:40] or "-", ", ".join(test)[:40] or "-", status))

    stale = sorted(seen - set(reqs))
    total = len(reqs)
    cov = round(ok * 100 / total, 1) if total else 0.0

    lines = ["# Matriz de Rastreabilidade — traceability-matrix-builder", ""]
    lines.append(f"**Cobertura:** {ok}/{total} requisitos com codigo+teste = {cov}%")
    if stale:
        lines.append(f"**Tags orfas (no codigo/teste, ausentes da spec):** {', '.join(stale)}")
    lines += ["", "| ReqID | Criterio | Codigo | Teste | Status |", "|---|---|---|---|---|"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")

    print(f"Requisitos: {total} | com codigo+teste: {ok} ({cov}%) | tags orfas: {len(stale)}")
    print(f"Relatorio: {args.out}")
    sys.exit(0)


if __name__ == "__main__":
    main()
