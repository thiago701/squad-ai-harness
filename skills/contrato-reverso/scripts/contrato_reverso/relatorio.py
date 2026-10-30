# -*- coding: utf-8 -*-
"""Relatório legível (Markdown) + JSON. Sem credenciais: só nomes, hashes e códigos."""
from __future__ import annotations

import json
from pathlib import Path

ICONE = {"aprovado": "🟢 APROVADO", "reprovado": "🔴 REPROVADO", "inconclusivo": "🟡 INCONCLUSIVO"}
NOME_CAMADA = {"A": "A · consumidor ↔ OpenAPI", "B": "B · contrato/consumidor ↔ Gateway (SAM)",
               "C1": "C1 · provedor in-process (Gateway simulado)", "SUITE": "Suíte completa do provedor",
               "C2": "C2 · replay pelo Gateway implantado", "infra": "Execução"}


def _tabela(linhas: list[list[str]], cabecalho: list[str]) -> str:
    def cel(x: object) -> str:
        return str(x).replace("|", "\\|").replace("\n", " ")
    out = ["| " + " | ".join(cabecalho) + " |", "|" + "---|" * len(cabecalho)]
    out += ["| " + " | ".join(cel(c) for c in l) + " |" for l in linhas]
    return "\n".join(out)


def markdown(r: dict) -> str:
    p: list[str] = []
    p.append(f"# Contrato reverso — {r.get('consumidor') or r['contrato']}\n")
    p.append(f"**{ICONE[r['veredito']]}** · nível `{r['nivel']}` · escopo {', '.join(r['escopo'])} · "
             f"{r['duracao_s']}s (orçamento {r.get('orcamento_s')}s) · exit {r['codigo_saida']}\n")
    v = r["versoes"]
    p.append("## Versões avaliadas\n")
    linhas = [["commit", (v.get("commit") or "—")[:12] + (" (+ alterações não commitadas)" if v.get("working_tree_suja") else "")]]
    for nome, e in (v.get("entradas") or {}).items():
        linhas.append([nome, f"`{e['caminho']}` · {e['hash']}"])
    if v.get("provedor_observado"):
        o = v["provedor_observado"]
        linhas.append(["provedor (C1)", f"{o.get('transporte')} · gateway {o.get('gateway')} · persistência {o.get('persistencia')}"])
    if v.get("gateway_implantado"):
        g = v["gateway_implantado"]
        linhas.append(["gateway implantado (C2)", f"{g.get('ambiente')} · host {g.get('alvo_host')} · "
                                                 f"req-ids {g.get('ids_requisicao_gateway')}"])
    p.append(_tabela(linhas, ["item", "versão"]) + "\n")
    p.append("## Camadas de evidência\n")
    linhas = []
    for nome, c in r["camadas"].items():
        estado = ("executada" + (" (cache)" if c["cache"] else "")) if c["executada"] else f"NÃO executada — {c['motivo_nao_execucao']}"
        linhas.append([NOME_CAMADA.get(nome, nome), estado, c["quebras"], c["duracao_s"], c["alcance"]])
    p.append(_tabela(linhas, ["camada", "estado", "quebras", "s", "o que comprova"]) + "\n")
    for titulo, sev in (("Quebras (reprovam)", "quebra"), ("Riscos (relatados, não reprovam)", "risco"),
                        ("Pendente de comprovação", "pendente")):
        itens = [a for a in r["achados"] if a["severidade"] == sev]
        if not itens:
            continue
        p.append(f"## {titulo}\n")
        p.append(_tabela([[a["camada"], a["codigo"], a["interacao"] or "*", a["mensagem"]
                           + (" **(ACEITO)**" if a.get("aceito") else "")] for a in itens],
                         ["camada", "código", "interação", "detalhe"]) + "\n")
    if r.get("aceites_aplicados"):
        p.append("## Divergências aceitas (processo de aceite)\n")
        p.append(_tabela([[a["chave"], a["responsavel"], a["expira_em"], a["justificativa"]]
                          for a in r["aceites_aplicados"]], ["chave", "responsável", "expira", "justificativa"]) + "\n")
    if r.get("matriz"):
        p.append("## Matriz de rastreabilidade\n")
        p.append("consumidor → expectativa → endpoint → Gateway → serviço → teste → evidência\n")
        p.append(_tabela([[m["interacao"], m["expectativa"], m["origem"], m["endpoint"], m["gateway"], m["servico"],
                           "; ".join(f"{k}: {v}" for k, v in m["evidencia"].items())] for m in r["matriz"]],
                         ["interação", "expectativa (risco)", "origem", "endpoint", "Gateway", "serviço", "evidência"]) + "\n")
    p.append("## Limitações\n")
    p.extend(f"- {l}" for l in r.get("limitacoes") or [])
    p.append("")
    return "\n".join(p)


def gravar(resultado: dict, pasta: Path) -> tuple[Path, Path]:
    pasta.mkdir(parents=True, exist_ok=True)
    base = resultado.get("consumidor") or "contrato"
    js = pasta / f"{base}.json"
    md = pasta / f"{base}.md"
    js.write_text(json.dumps(resultado, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    md.write_text(markdown(resultado), encoding="utf-8")
    return js, md
