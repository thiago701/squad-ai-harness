#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Grader objetivo do eval held-out de clean-code-craftsman (piloto SkillOpt-Sleep, ADR-004).

Por que existe: o gate held-out do SkillOpt so aceita uma edicao da skill se ela MELHORA
um score de validacao — e isso exige um **sinal de recompensa objetivo** (hard reward), nao
um julgamento de prosa. Aqui o sinal e: dado um trecho com um code smell dominante, a skill
acerta o **codigo do catalogo** (F1/N1/G5/G30/G6/C5...)? O grader extrai o 1o codigo da
resposta e compara com a referencia. Stdlib pura (P1), sem rede, sem API — pode rodar no gate.

Uso:
  python grade.py --self-check                      # CI: valida o dataset (exit 0/1), sem API
  python grade.py --score answers.jsonl             # score no split heldout (default)
  python grade.py --score answers.jsonl --split train
      answers.jsonl: uma linha JSON por tarefa -> {"id": <int>, "answer": "<texto da skill>"}
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skillopt-pilot.json")

# Codigo do catalogo Clean Code: letra de area (C/E/F/G/N/T) + numero. Ex.: F1, G30, N1.
_CODE = re.compile(r"\b([CEFGNT][0-9]{1,2})\b")
# Os 6 smells mais comuns que a skill declara cacar (SKILL.md "2. Detectar smells").
COMMON = {"F1", "N1", "G5", "G30", "G6", "C5"}


def load(path: str = DATA) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def first_code(answer: str) -> str | None:
    """Primeiro codigo de catalogo na resposta (o 'smell dominante' pelo contrato)."""
    m = _CODE.search(answer or "")
    return m.group(1).upper() if m else None


def score(tasks: list[dict], answers: dict[int, str], split: str | None = None) -> dict:
    """Acuracia exact-match do codigo dominante. split=None -> todas; senao filtra."""
    sel = [t for t in tasks if split is None or t.get("split") == split]
    hits, total, detail = 0, 0, []
    for t in sel:
        total += 1
        got = first_code(answers.get(t["id"], ""))
        ok = (got == t["reference"].upper())
        hits += 1 if ok else 0
        detail.append({"id": t["id"], "reference": t["reference"], "got": got, "ok": ok})
    return {"split": split or "all", "accuracy": (hits / total if total else 0.0),
            "hits": hits, "total": total, "detail": detail}


def self_check(data: dict) -> list[str]:
    """Invariantes do dataset — o que faz dele um held-out util. Retorna lista de problemas."""
    problems = []
    tasks = data.get("tasks", [])
    if not tasks:
        return ["dataset sem 'tasks'"]
    ids = [t.get("id") for t in tasks]
    if len(ids) != len(set(ids)):
        problems.append("ids duplicados")
    for t in tasks:
        for field in ("id", "reference", "split", "prompt"):
            if field not in t:
                problems.append(f"task {t.get('id')}: falta '{field}'")
        if not _CODE.fullmatch(str(t.get("reference", ""))):
            problems.append(f"task {t.get('id')}: reference '{t.get('reference')}' nao e codigo de catalogo")
        if t.get("split") not in ("train", "heldout"):
            problems.append(f"task {t.get('id')}: split invalido '{t.get('split')}'")
    train = [t for t in tasks if t.get("split") == "train"]
    held = [t for t in tasks if t.get("split") == "heldout"]
    if not train:
        problems.append("sem tarefas de train (nada para propor edicoes)")
    if not held:
        problems.append("sem tarefas heldout (sem gate)")
    # held-out precisa exercer cada smell comum, senao o gate tem ponto cego.
    held_refs = {t.get("reference") for t in held}
    missing = COMMON - held_refs
    if missing:
        problems.append(f"heldout nao cobre smells comuns: {sorted(missing)}")
    return problems


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Grader do eval held-out (clean-code-craftsman / SkillOpt).")
    ap.add_argument("--self-check", action="store_true", help="valida o dataset; exit 1 se quebrado")
    ap.add_argument("--score", metavar="ANSWERS.jsonl", help="arquivo de respostas da skill (jsonl)")
    ap.add_argument("--split", default="heldout", choices=["train", "heldout", "all"])
    args = ap.parse_args(argv)

    data = load()

    if args.self_check or not args.score:
        problems = self_check(data)
        if problems:
            print("NAO PRONTO — dataset invalido:")
            for p in problems:
                print(f"  - {p}")
            return 1
        n = len(data["tasks"])
        held = sum(1 for t in data["tasks"] if t["split"] == "heldout")
        print(f"OK: dataset valido — {n} tarefas ({held} heldout), smells comuns cobertos.")
        return 0

    answers = {}
    with open(args.score, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            answers[int(row["id"])] = row.get("answer", "")
    split = None if args.split == "all" else args.split
    res = score(data["tasks"], answers, split=split)
    print(f"score[{res['split']}] = {res['accuracy']:.3f}  ({res['hits']}/{res['total']})")
    for d in res["detail"]:
        flag = "ok" if d["ok"] else "MISS"
        print(f"  [{flag}] task {d['id']}: ref={d['reference']} got={d['got']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
