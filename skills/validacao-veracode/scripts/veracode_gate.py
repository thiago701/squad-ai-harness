#!/usr/bin/env python3
"""Gate Veracode — normaliza resultados, aplica o perfil e emite o veredito da lente Veracode
do code review (formato de worker do tech-lead-review). Só stdlib (Python >= 3.10).

Entradas aceitas (autodetectadas; várias podem ser combinadas):
  * results.json do Pipeline Scan / `veracode static scan`      (chave `findings`)
  * resposta da Findings REST API v2 — Policy/Sandbox             (`_embedded.findings`)
  * saída do veracode_precheck.py                                 (`ferramenta: veracode_precheck`)

Uso:
  python veracode_gate.py <resultado.json> [<outro.json> ...] [--perfil maximo|padrao|bancario]
         [--baseline baseline.json] [--fail-on-cwe 89,78] [--status-politica "Did Not Pass"]
         [--release] [--sla-dias "5=1,4=7,3=30,2=90"] [--hoje AAAA-MM-DD]
         [--json veredito.json] [--md veredito.md]

Exit: 0 = APROVADO / APROVADO_COM_RESSALVAS · 1 = BLOQUEADO · 2 = entrada inválida.
Fail-closed: scan incompleto, arquivo ilegível ou formato desconhecido NUNCA aprovam.
Mitigação só vale APROVADA: proposta pendente conta como flaw aberto.
Perfil bancario: SLA vencido bloqueia mesmo herdado; --release exige evidência do Policy Scan.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from veracode_precheck import ORDEM_SQUAD, PERFIS, ROTULO_SEV, classificar, saida_utf8  # noqa: E402

VERSAO = "1.0.0"
CAMPOS_MATCH = ("procedure_hash", "prototype_hash", "flaw_hash", "flaw_hash_count",
                "flaw_hash_ordinal", "cause_hash", "cause_hash_count", "cause_hash_ordinal")
TIPO_WORKER = {"🔴": "bloqueante", "🟡": "necessario", "🔵": "sugestao", "⚪": "observacao"}
TAG = re.compile(r"<[^>]+>")
# SLA canônico da squad (dias desde a 1ª detecção), alinhado a engenheiro-seguranca/references/secrets-cripto.md.
# Ajuste à política da instituição com --sla-dias.
SLA_PADRAO = {5: 1, 4: 7, 3: 30, 2: 90}


class EntradaInvalida(Exception):
    pass


def _int(valor) -> int | None:
    try:
        return int(str(valor).strip().upper().removeprefix("CWE-"))
    except (TypeError, ValueError):
        return None


def _texto(valor, limite: int = 200) -> str:
    return " ".join(html.unescape(TAG.sub(" ", str(valor or ""))).split())[:limite]


def _norm_arquivo(arquivo: str | None) -> str:
    return (arquivo or "").replace("\\", "/").lstrip("./").lower()


def _item(origem: str, cwe, sev, arquivo, linha, funcao, titulo, *, flaw_match=None,
          mitigacao=None, viola_politica=None, regra=None, correcao=None,
          primeira_deteccao=None, tipo_scan=None) -> dict:
    fm = tuple((flaw_match or {}).get(k) for k in CAMPOS_MATCH)
    return {
        "origem": origem, "cwe": _int(cwe), "sev": _int(sev), "arquivo": arquivo or "?",
        "linha": _int(linha), "funcao": funcao, "titulo": _texto(titulo), "regra": regra,
        "correcao": correcao, "mitigacao": mitigacao, "viola_politica": viola_politica,
        "flaw_match": fm if any(v is not None for v in fm) else None,
        "primeira_deteccao": str(primeira_deteccao)[:10] if primeira_deteccao else None,
        "tipo_scan": tipo_scan,
    }


def _de_pipeline(dados: dict) -> tuple[list[dict], list[str]]:
    motivos = []
    status = dados.get("scan_status")
    if status is not None and str(status).upper() != "SUCCESS":
        motivos.append(f"scan não concluído (scan_status={status}) — fail-closed")
    itens = []
    for f in dados.get("findings") or []:
        src = ((f.get("files") or {}).get("source_file")) or {}
        itens.append(_item(
            "pipeline", f.get("cwe_id"), f.get("severity"), src.get("file"), src.get("line"),
            src.get("qualified_function_name") or src.get("function_name"),
            f.get("issue_type") or f.get("title"), flaw_match=f.get("flaw_match"),
        ))
    return itens, motivos


def _de_findings_api(dados: dict) -> tuple[list[dict], list[str], int]:
    itens, aprovadas = [], 0
    for f in (dados.get("_embedded") or {}).get("findings") or []:
        st = f.get("finding_status") or {}
        if str(st.get("status", "")).upper() == "CLOSED":
            continue
        resolucao = str(st.get("resolution", "")).upper()
        estado = str(st.get("resolution_status", "")).upper()
        mitigacao = None
        if resolucao not in ("", "UNRESOLVED", "NONE"):
            if estado == "APPROVED":
                aprovadas += 1
                continue
            mitigacao = {"PROPOSED": "proposta", "": "proposta", "REJECTED": "rejeitada"}.get(estado, estado.lower())
        fd = f.get("finding_details") or {}
        cwe = (fd.get("cwe") or {}).get("id") if isinstance(fd.get("cwe"), dict) else fd.get("cwe")
        nome_cwe = (fd.get("cwe") or {}).get("name") if isinstance(fd.get("cwe"), dict) else None
        tipo = str(f.get("scan_type") or "STATIC").upper()
        if tipo == "SCA":  # componente vulnerável: arquivo = componente, título = CVE
            cve = fd.get("cve") if isinstance(fd.get("cve"), dict) else {}
            arquivo = fd.get("component_filename") or fd.get("component_id")
            titulo = " ".join(x for x in (cve.get("name"), arquivo) if x) or nome_cwe or f.get("description")
        else:
            arquivo = fd.get("file_path") or fd.get("file_name")
            titulo = nome_cwe or f.get("description")
        itens.append(_item(
            "findings-api", cwe, fd.get("severity"), arquivo,
            fd.get("file_line_number"), fd.get("procedure"), titulo,
            mitigacao=mitigacao, viola_politica=f.get("violates_policy"),
            primeira_deteccao=st.get("first_found_date"), tipo_scan=tipo,
        ))
    return itens, [], aprovadas


def _de_precheck(dados: dict) -> list[dict]:
    return [
        _item("precheck", a.get("cwe"), a.get("severidade_veracode"), a.get("arquivo"), a.get("linha"),
              None, a.get("titulo"), regra=a.get("regra"), correcao=a.get("correcao"))
        for a in dados.get("achados") or []
    ]


def carregar(caminho: Path) -> dict:
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EntradaInvalida(f"{caminho}: ilegível ({exc})") from exc
    if not isinstance(dados, dict):
        raise EntradaInvalida(f"{caminho}: JSON não é objeto")
    if dados.get("ferramenta") == "veracode_precheck":
        return {"fonte": "precheck", "itens": _de_precheck(dados), "motivos": [], "aprovadas": 0,
                "arquivos": dados.get("arquivos_analisados"), "perfil": dados.get("perfil")}
    if isinstance(dados.get("_embedded"), dict) and "findings" in dados["_embedded"]:
        itens, motivos, aprovadas = _de_findings_api(dados)
        return {"fonte": "findings-api", "itens": itens, "motivos": motivos, "aprovadas": aprovadas}
    if isinstance(dados.get("findings"), list):
        itens, motivos = _de_pipeline(dados)
        return {"fonte": "pipeline", "itens": itens, "motivos": motivos, "aprovadas": 0}
    raise EntradaInvalida(f"{caminho}: formato desconhecido (esperado findings, _embedded.findings ou precheck)")


def chaves(item: dict) -> set[tuple]:
    loc = item["funcao"] or item["linha"]
    out = {("loc", item["cwe"], _norm_arquivo(item["arquivo"]), str(loc))}
    if item["flaw_match"]:
        out.add(("fm",) + item["flaw_match"])
    return out


def consolidar(fontes: list[dict]) -> list[dict]:
    """Scan real primeiro; achado do precheck no mesmo CWE+arquivo+linha vira confirmação."""
    reais: dict[tuple, dict] = {}
    saida = []
    for fonte in sorted(fontes, key=lambda f: f["fonte"] == "precheck"):
        for it in fonte["itens"]:
            k = (it["cwe"], Path(_norm_arquivo(it["arquivo"])).name, it["linha"])
            if it["origem"] != "precheck":
                reais.setdefault(k, it)
            elif k in reais:
                reais[k]["confirmado_pelo_precheck"] = True
                continue
            saida.append(it)
    return saida


def _idade_dias(item: dict, hoje: date) -> int | None:
    try:
        return (hoje - date.fromisoformat(item["primeira_deteccao"])).days if item.get("primeira_deteccao") else None
    except ValueError:
        return None


def avaliar(fontes: list[dict], perfil: str = "maximo", baseline: list[dict] | None = None,
            fail_on_cwe: frozenset[int] = frozenset(), status_politica: str | None = None, *,
            release: bool = False, sla: dict[int, int] | None = None, hoje: date | None = None) -> dict:
    itens = consolidar(fontes)
    chaves_base: set[tuple] = set()
    for it in baseline or []:
        chaves_base |= chaves(it)
    motivos = [m for f in fontes for m in f["motivos"]]
    for it in itens:
        it["severidade_squad"] = "🔴" if it["cwe"] in fail_on_cwe else classificar(it["sev"], it["cwe"], perfil)
        it["herdado"] = bool(chaves(it) & chaves_base)
        idade = _idade_dias(it, hoje or date.today())
        prazo = (sla or SLA_PADRAO).get(it["sev"]) if it["sev"] is not None else None
        it["sla_vencido"] = idade - prazo if idade is not None and prazo is not None and idade > prazo else None
    itens.sort(key=lambda x: (x["herdado"], ORDEM_SQUAD[x["severidade_squad"]], -(x["sev"] or 0), x["arquivo"], x["linha"] or 0))

    novos_bloq = [i for i in itens if i["severidade_squad"] == "🔴" and not i["herdado"]]
    herdados_bloq = [i for i in itens if i["severidade_squad"] == "🔴" and i["herdado"]]
    pendentes = [i for i in itens if i["mitigacao"]]
    necessarios = [i for i in itens if i["severidade_squad"] == "🟡"]
    sp = (status_politica or "").strip().lower()

    if novos_bloq:
        motivos.append(f"{len(novos_bloq)} flaw(s) 🔴 novo(s) no perfil {perfil}")
    if sp in ("did not pass", "did_not_pass"):
        motivos.append("política Veracode = Did Not Pass")
    ressalvas = []
    if pendentes:
        ressalvas.append(f"{len(pendentes)} mitigação(ões) sem aprovação — o flaw segue aberto e conta no veredito")
    if herdados_bloq:
        ressalvas.append(f"{len(herdados_bloq)} 🔴 herdado(s) do baseline — card de dívida com prazo obrigatório")
    if necessarios:
        ressalvas.append(f"{len(necessarios)} 🟡 a corrigir antes do merge")
    if sp in ("conditional pass", "conditional_pass"):
        ressalvas.append("política Veracode = Conditional Pass (dentro do grace period)")

    vencidos = [i for i in itens if i["sla_vencido"] and i["severidade_squad"] == "🔴"]
    if vencidos and perfil == "bancario":
        motivos.append(f"{len(vencidos)} 🔴 com SLA de correção vencido — no perfil bancário herdado não salva")
    elif vencidos:
        ressalvas.append(f"{len(vencidos)} 🔴 com SLA de correção vencido — escalar ao dono do risco")
    fontes_reais = {f["fonte"] for f in fontes} & {"pipeline", "findings-api"}
    if release and "findings-api" not in fontes_reais and sp not in ("passed", "conditional pass", "conditional_pass"):
        motivos.append("release sem evidência do Policy Scan (export da Findings API ou --status-politica) — fail-closed")
    if perfil == "bancario" and not fontes_reais and not release:
        ressalvas.append("sem scan real do Veracode (só pré-scan heurístico) — compliance não atestada")
    divergentes = sorted({f["perfil"] for f in fontes if f.get("perfil") and f["perfil"] != perfil})
    if divergentes:
        ressalvas.append(f"pré-scan rodou no perfil {', '.join(divergentes)} e o gate no {perfil} — regras do perfil podem ter ficado de fora")

    bloqueia = (bool(novos_bloq) or sp in ("did not pass", "did_not_pass")
                or any("fail-closed" in m for m in motivos) or (bool(vencidos) and perfil == "bancario"))
    veredito = "BLOQUEADO" if bloqueia else ("APROVADO_COM_RESSALVAS" if ressalvas else "APROVADO")
    sevs = [i["severidade_squad"] for i in itens]
    return {
        "ferramenta": "veracode_gate", "versao": VERSAO, "perfil": perfil, "veredito": veredito,
        "motivos": motivos, "ressalvas": ressalvas,
        "fontes": [{"fonte": f["fonte"], "itens": len(f["itens"]), "mitigacoes_aprovadas_excluidas": f["aprovadas"]}
                   for f in fontes],
        "resumo": {
            "total": len(itens), "por_severidade": {s: sevs.count(s) for s in ("🔴", "🟡", "🔵", "⚪")},
            "novos_bloqueantes": len(novos_bloq), "herdados_bloqueantes": len(herdados_bloq),
            "mitigacoes_pendentes": len(pendentes), "sla_vencidos": len(vencidos),
        },
        "achados": itens,
        "review_worker": worker(itens, veredito, motivos + ressalvas),
    }


def _descricao(i: dict) -> str:
    cwe = f"CWE-{i['cwe']}" if i["cwe"] else "Empacotamento"
    rot = ROTULO_SEV.get(i["sev"], "—") if i["sev"] is not None else "cobertura"
    extra = []
    if i["herdado"]:
        extra.append("herdado do baseline")
    if i["mitigacao"]:
        extra.append(f"mitigação {i['mitigacao']}, não aprovada")
    if i.get("confirmado_pelo_precheck"):
        extra.append("antecipado pelo precheck")
    if i.get("sla_vencido"):
        extra.append(f"SLA vencido há {i['sla_vencido']} dia(s)")
    if i.get("regra"):
        extra.append(i["regra"])
    sufixo = f" [{'; '.join(extra)}]" if extra else ""
    return f"{cwe} ({rot}) {i['titulo']} — origem {i['origem']}{sufixo}"


def worker(itens: list[dict], veredito: str, notas: list[str]) -> dict:
    """Contrato de worker do tech-lead-review (references/review-multi-dimensao.md)."""
    return {
        "worker": "rev-veracode",
        "status": "success",
        "findings": [{
            "arquivo": i["arquivo"], "linha": str(i["linha"] or "?"),
            "tipo": TIPO_WORKER[i["severidade_squad"]], "descricao": _descricao(i),
            "sugestao": i["correcao"] or f"ver references/catalogo-cwe-veracode.md (CWE-{i['cwe']})",
        } for i in itens],
        "veredito_dimensao": veredito,
        "resumo": "; ".join(notas)[:300] or "sem achados acima do corte",
    }


def para_markdown(v: dict) -> str:
    r = v["resumo"]
    ps = r["por_severidade"]
    fontes = " · ".join(f"{f['fonte']} ({f['itens']})" for f in v["fontes"])
    linhas = [
        f"### Lente Veracode — {v['veredito']} (perfil: {v['perfil']})", "",
        f"Fontes: {fontes} | 🔴 {ps['🔴']} (novos {r['novos_bloqueantes']}, herdados {r['herdados_bloqueantes']})"
        f" · 🟡 {ps['🟡']} · 🔵 {ps['🔵']} · ⚪ {ps['⚪']} · mitigações pendentes {r['mitigacoes_pendentes']}", "",
    ]
    linhas += [f"- ⛔ {m}" for m in v["motivos"]] + [f"- ⚠️ {m}" for m in v["ressalvas"]]
    if v["achados"]:
        linhas += ["", "| Sev | CWE | Local | Achado | Origem | Situação | Ação |", "|---|---|---|---|---|---|---|"]
        for i in v["achados"]:
            cwe = f"CWE-{i['cwe']}" if i["cwe"] else "—"
            sit = "herdado" if i["herdado"] else "novo"
            if i["mitigacao"]:
                sit += f" · mitigação {i['mitigacao']}"
            if i.get("sla_vencido"):
                sit += f" · SLA vencido +{i['sla_vencido']}d"
            acao = i["correcao"] or "ver catálogo CWE"
            linhas.append(f"| {i['severidade_squad']} | {cwe} | `{i['arquivo']}:{i['linha'] or '?'}` | {i['titulo']} "
                          f"| {i['origem']} | {sit} | {acao} |")
    return "\n".join(linhas) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gate Veracode: veredito da lente de segurança do code review.")
    ap.add_argument("entradas", nargs="+", help="results.json / findings API / saída do precheck")
    ap.add_argument("--perfil", choices=PERFIS, default="maximo")
    ap.add_argument("--baseline", metavar="ARQ", help="baseline (mesmo formato de uma entrada)")
    ap.add_argument("--fail-on-cwe", default="", help="CWEs que bloqueiam em qualquer severidade (ex.: 89,78)")
    ap.add_argument("--status-politica", help="Passed | Did Not Pass | Conditional Pass | Not Assessed")
    ap.add_argument("--release", action="store_true", help="gate de release: exige evidência do Policy Scan")
    ap.add_argument("--sla-dias", default="", help='SLA por severidade, ex.: "5=1,4=7,3=30,2=90"')
    ap.add_argument("--hoje", help="data de referência AAAA-MM-DD (reprodutibilidade)")
    ap.add_argument("--json", dest="saida_json", metavar="ARQ")
    ap.add_argument("--md", dest="saida_md", metavar="ARQ")
    args = ap.parse_args(argv)
    saida_utf8()
    try:
        fontes = [carregar(Path(e)) for e in args.entradas]
        base = carregar(Path(args.baseline))["itens"] if args.baseline else None
        cwes = frozenset(c for c in (_int(x) for x in args.fail_on_cwe.split(",") if x.strip()) if c is not None)
        sla = {**SLA_PADRAO, **{int(k): int(v) for k, v in (x.split("=") for x in args.sla_dias.split(",") if x.strip())}}
        hoje = date.fromisoformat(args.hoje) if args.hoje else None
    except (EntradaInvalida, ValueError) as exc:
        print(f"[gate] BLOQUEADO — entrada inválida: {exc}", file=sys.stderr)
        return 2
    v = avaliar(fontes, args.perfil, base, cwes, args.status_politica, release=args.release, sla=sla, hoje=hoje)
    texto = json.dumps(v, ensure_ascii=False, indent=2)
    if args.saida_json:
        Path(args.saida_json).write_text(texto + "\n", encoding="utf-8")
    else:
        print(texto)
    if args.saida_md:
        Path(args.saida_md).write_text(para_markdown(v), encoding="utf-8")
    print(f"[gate] {v['veredito']} · perfil {args.perfil} · {'; '.join(v['motivos'] + v['ressalvas']) or 'ok'}",
          file=sys.stderr)
    return 1 if v["veredito"] == "BLOQUEADO" else 0


if __name__ == "__main__":
    sys.exit(main())
