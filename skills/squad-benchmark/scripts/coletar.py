#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""coletar.py — auto-preenchimento dos parâmetros A–E a partir de evidência do repo.

Varre o repositório do Squad AI atrás de sinais MEDIDOS e PROPÕE valores para as
5 métricas (com fonte e nível de confiança). **Não grava nada** — só imprime a
sugestão e um comando `registrar.py` pronto para você revisar e rodar.

Filosofia: "medir, não sentir". Cada valor vem com a fonte e um selo
(solido | proxy | estimativa). O que não puder ser medido fica em branco (??)
para preenchimento manual — o coletor nunca inventa um número silenciosamente.

Sinais coletados (best-effort; o que faltar é degradado com aviso):
  A  proxy    — taxa de testes verdes (reports/evidencias*.md)
  B  solido   — maior redução de tokens medida (skills/SKILL_INDEX.md; fallback benchmark)
  C  proxy    — conformidade das skills auditadas (relatórios de auditoria)
  D  solido/estimativa — multiplicador de velocidade dos benchmarks (empírico > estimado)
  E  proxy    — índice composto: skills ativas + índice RAG do Cérebro + taxa de delegação

Stdlib apenas. Uso:
  python coletar.py                         # detecta o repo pela pasta atual/ancestrais
  python coletar.py --repo /caminho/do/repo
  python coletar.py --teto-skills 60 --teto-vault 300 --delegacao 85
"""
import argparse
import glob
import json
import os
import re
import sys

ORDEM = ["A", "B", "C", "D", "E"]


# ---------------------------------------------------------------------------
# Localização do repo
# ---------------------------------------------------------------------------
def achar_repo(cli):
    """Acha a raiz do repo Squad AI (contém skills/ e docs/relatorios/benchmarks)."""
    cands = []
    if cli:
        cands.append(os.path.abspath(cli))
    aqui = os.path.abspath(os.getcwd())
    # sobe até 6 níveis procurando marcadores do repo
    p = aqui
    for _ in range(7):
        cands.append(p)
        p = os.path.dirname(p)
    for base in cands:
        if os.path.isdir(os.path.join(base, "skills")) and \
           os.path.isfile(os.path.join(base, "skills", "SKILL_INDEX.md")):
            return base
    # fallback: a pasta atual, mesmo incompleta
    return aqui


def _read(path):
    try:
        with open(path, encoding="utf-8-sig") as fh:
            return fh.read()
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Coletores por métrica (cada um retorna (valor|None, confianca, fonte))
# ---------------------------------------------------------------------------
def coletar_A(repo):
    """A (retrabalho) — proxy: taxa de testes verdes nos relatórios de evidência."""
    melhor = None
    for path in glob.glob(os.path.join(repo, "reports", "*.md")):
        txt = _read(path) or ""
        # padrão "220 ✓ / 21 ✗" — finditer pega TODAS as ocorrências (antes E depois);
        # ficamos com a maior taxa (o estado "depois"/melhor), não a primeira.
        for m in re.finditer(r"(\d+)\s*✓\s*/\s*(\d+)\s*✗", txt):
            verdes, vermelhos = int(m.group(1)), int(m.group(2))
            total = verdes + vermelhos
            if total:
                pct = round(verdes / total * 100, 1)
                if melhor is None or pct > melhor[0]:
                    melhor = (pct, os.path.basename(path), verdes, total)
    if melhor:
        pct, fonte, v, t = melhor
        return pct, "proxy", f"testes verdes {v}/{t} ({fonte})"
    return None, None, "nao coletado — informe manualmente (% entregas sem retrabalho)"


def coletar_B(repo):
    """B (tokens) — sólido: maior redução de tokens medida no SKILL_INDEX/benchmarks."""
    idx = _read(os.path.join(repo, "skills", "SKILL_INDEX.md")) or ""
    reducoes = [int(x) for x in re.findall(r"[−-](\d{2,3})\s*%", idx)]
    if reducoes:
        v = max(reducoes)
        return float(v), "solido", f"reducao de tokens -{v}% (SKILL_INDEX, hub+references)"
    # fallback: benchmarks
    val = _max_benchmark(repo, ["token_economy_percent"])
    if val is not None:
        return round(abs(val), 1), "solido", f"token_economy_percent {abs(val):g}% (benchmark)"
    return None, None, "nao coletado — informe % de reducao de tokens vs. baseline"


def coletar_C(repo):
    """C (qualidade) — proxy: conformidade das skills auditadas."""
    for path in (glob.glob(os.path.join(repo, "reports", "*.md")) +
                 glob.glob(os.path.join(repo, "docs", "judgments", "*.md"))):
        txt = _read(path) or ""
        m = re.search(r"(\d+)\s+auditad", txt)
        m2 = re.search(r"(\d+)\s+limpas", txt)
        if m and m2:
            auditadas, limpas = int(m.group(1)), int(m2.group(1))
            if auditadas:
                pct = round(limpas / auditadas * 100, 1)
                return pct, "proxy", (f"conformidade {limpas}/{auditadas} skills limpas "
                                      f"({os.path.basename(path)})")
    return None, None, "nao coletado — rode /review ou use a rubrica de quality-score"


def coletar_D(repo):
    """D (velocidade) — multiplicador; prioriza medição empírica sobre estimativa."""
    empirico, estimado = None, None
    for path in glob.glob(os.path.join(repo, "docs", "relatorios", "benchmarks", "*",
                                       "benchmark-data.json")):
        try:
            d = json.loads(_read(path) or "{}")
        except json.JSONDecodeError:
            continue
        mult = _extrair_speedup(d)
        if mult is None:
            continue
        tipo = str(d.get("metadata", {}).get("data_type", "")).lower()
        if "empiric" in tipo:
            if empirico is None or mult > empirico[0]:
                empirico = (mult, os.path.basename(os.path.dirname(path)))
        else:
            if estimado is None or mult > estimado[0]:
                estimado = (mult, os.path.basename(os.path.dirname(path)))
    if empirico:
        return round(empirico[0], 2), "solido", f"speedup empirico {empirico[0]:g}x ({empirico[1]})"
    if estimado:
        return round(estimado[0], 2), "estimativa", f"speedup estimado {estimado[0]:g}x ({estimado[1]})"
    return None, None, "nao coletado — informe o multiplicador x vs. baseline manual"


def coletar_E(repo, teto_skills, teto_vault, delegacao):
    """E (cognição) — composto: skills ativas + índice RAG + taxa de delegação."""
    skills = _contar_skills(repo)
    docs_rag = _rag_docs(repo)
    partes, fontes = [], []

    if skills is not None:
        s_norm = min(100.0, skills / teto_skills * 100)
        partes.append(("skills", 0.40, s_norm))
        fontes.append(f"{skills} skills/{teto_skills}={s_norm:.0f}")
    if docs_rag is not None:
        v_norm = min(100.0, docs_rag / teto_vault * 100)
        partes.append(("vault", 0.30, v_norm))
        fontes.append(f"{docs_rag} docs RAG/{teto_vault}={v_norm:.0f}")
    if delegacao is not None:
        partes.append(("delegacao", 0.30, float(delegacao)))
        fontes.append(f"delegacao={delegacao:g}")

    if not partes:
        return None, None, "nao coletado — sem sinais de skills/vault/delegacao"
    # Renormaliza os pesos pelos termos disponíveis (se algum faltar).
    peso_total = sum(w for _, w, _ in partes)
    E = sum(w * v for _, w, v in partes) / peso_total
    completo = len(partes) == 3
    conf = "proxy" if completo else "estimativa"
    aviso = "" if completo else " [PARCIAL — termo(s) ausente(s)]"
    return round(E, 1), conf, "0.40*skills+0.30*vault+0.30*delegacao → " + \
        "; ".join(fontes) + aviso


# ---------------------------------------------------------------------------
# Helpers de extração
# ---------------------------------------------------------------------------
def _contar_skills(repo):
    nomes = set()
    for base in ("skills", os.path.join(".claude", "skills")):
        for sk in glob.glob(os.path.join(repo, base, "*", "SKILL.md")):
            nomes.add(os.path.basename(os.path.dirname(sk)))
    return len(nomes) or None


def _rag_docs(repo):
    """Maior 'total_documents_indexed' dos metrics.json do laboratório do Cérebro."""
    melhor = None
    for path in glob.glob(os.path.join(repo, "docs", "**", "metrics.json"),
                          recursive=True):
        try:
            d = json.loads(_read(path) or "{}")
        except json.JSONDecodeError:
            continue
        for _, v in _walk(d):
            if isinstance(v, dict) and "total_documents_indexed" in v:
                n = v["total_documents_indexed"]
                if isinstance(n, (int, float)) and (melhor is None or n > melhor):
                    melhor = n
    return melhor


def _extrair_speedup(d):
    """Encontra o multiplicador de velocidade em formatos diferentes de benchmark."""
    r = d.get("results", {})
    if isinstance(r, dict) and isinstance(r.get("speedup_multiplier"), (int, float)):
        return float(r["speedup_multiplier"])
    k = d.get("kpis", {})
    if isinstance(k, dict):
        ve = k.get("velocidade_entrega")
        if isinstance(ve, dict) and isinstance(ve.get("valor_multiplicador"), (int, float)):
            return float(ve["valor_multiplicador"])
    return None


def _max_benchmark(repo, chaves):
    melhor = None
    for path in glob.glob(os.path.join(repo, "docs", "relatorios", "benchmarks", "*",
                                       "benchmark-data.json")):
        try:
            d = json.loads(_read(path) or "{}")
        except json.JSONDecodeError:
            continue
        for _, v in _walk(d):
            for ch in chaves:
                if isinstance(v, dict) and isinstance(v.get(ch), (int, float)):
                    val = v[ch]
                    if melhor is None or abs(val) > abs(melhor):
                        melhor = val
    return melhor


def _walk(obj):
    """Percorre dicts/listas aninhados, emitindo (chave, valor)."""
    if isinstance(obj, dict):
        yield None, obj
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                yield from _walk(v)
            else:
                yield k, v
    elif isinstance(obj, list):
        for it in obj:
            yield from _walk(it)


# ---------------------------------------------------------------------------
# Saída
# ---------------------------------------------------------------------------
def _preview_norm(metrica, valor):
    """Tenta prever o normalizado usando db.py da skill (se disponível)."""
    try:
        sk = os.path.expanduser("~/.claude/skills/squad-benchmark/scripts")
        if os.path.isfile(os.path.join(sk, "db.py")):
            sys.path.insert(0, sk)
            import db  # noqa
            return db.normalizar(metrica, valor)
    except Exception:
        pass
    return None


def main(argv=None):
    p = argparse.ArgumentParser(description="Auto-preenchimento A-E do squad-benchmark")
    p.add_argument("--repo", default=None, help="raiz do repo Squad AI")
    p.add_argument("--versao", default=None, help="versao do marco a sugerir (ex.: v3)")
    p.add_argument("--teto-skills", type=float, default=60.0,
                   help="nº de skills que vale 100 no termo skills de E (default 60)")
    p.add_argument("--teto-vault", type=float, default=300.0,
                   help="nº de docs RAG que vale 100 no termo vault de E (default 300)")
    p.add_argument("--delegacao", type=float, default=85.0,
                   help="taxa de acerto em delegacao 0-100 para E (default 85)")
    args = p.parse_args(argv)

    repo = achar_repo(args.repo)
    print(f"Repo analisado: {repo}\n")

    resultados = {
        "A": coletar_A(repo),
        "B": coletar_B(repo),
        "C": coletar_C(repo),
        "D": coletar_D(repo),
        "E": coletar_E(repo, args.teto_skills, args.teto_vault, args.delegacao),
    }

    print("Sugestao de valores (revise antes de registrar):\n")
    print(f"  {'M':<2} {'bruto':>8} {'norm':>6} {'selo':<11} fonte")
    print("  " + "-" * 92)
    for m in ORDEM:
        valor, conf, fonte = resultados[m]
        bruto = "??" if valor is None else f"{valor:g}"
        norm = "" if valor is None else _preview_norm(m, valor)
        norm_s = "" if norm is None else f"{norm:g}"
        print(f"  {m:<2} {bruto:>8} {norm_s:>6} {(conf or 'MANUAL'):<11} {fonte}")

    # Comando pronto para registrar (o que faltou vira ?? para você preencher).
    versao = args.versao or "vX"
    partes = [f'python registrar.py --versao {versao} --contexto "auto-coletado do repo"']
    for m in ORDEM:
        valor, conf, fonte = resultados[m]
        bruto = "??" if valor is None else (f"{valor:g}x" if m == "D" else f"{valor:g}")
        partes.append(f'--{m} {bruto}')
        if conf:
            partes.append(f'--conf-{m} {conf}')
        obs = fonte.replace('"', "'")
        partes.append(f'--obs-{m} "{obs}"')

    faltando = [m for m in ORDEM if resultados[m][0] is None]
    print("\nComando sugerido (troque os ?? e a versao):\n")
    print("  " + " \\\n    ".join(partes))
    if faltando:
        print(f"\n⚠ Metricas sem dado coletado (preencha ??): {', '.join(faltando)}")
    print("\nNada foi gravado. Rode o comando acima (a partir da pasta scripts/ da "
          "skill) depois de revisar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
