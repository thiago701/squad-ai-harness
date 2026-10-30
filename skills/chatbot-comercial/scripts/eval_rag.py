#!/usr/bin/env python3
"""Avaliação do RAG contra o golden set — a régua que autoriza subir versão.

Mede três coisas, todas honestas:

  hit@1 / hit@3   a fonte certa aparece em 1º lugar / no top-3.
  cobertura       % das perguntas do golden que o agente respondeu com fonte.
  disciplina      % dos negativos em que o agente admitiu não saber ou recusou.

`disciplina` é o número que impede o loop de trapacear: baixar o
`score_minimo` sobe hit@k e derruba disciplina. Um ganho só conta se as três
métricas não regredirem.

Uso:
    python scripts/eval_rag.py
    python scripts/eval_rag.py --publicar         # grava no README
    python scripts/eval_rag.py --baseline golden/baseline.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.agente import Entrada  # noqa: E402
from app.config import Config  # noqa: E402
from app.servico import Servico  # noqa: E402

INICIO = "<!-- eval-rag:inicio -->"
FIM = "<!-- eval-rag:fim -->"

# As CINCO métricas comparadas contra o baseline. `intencao` faz parte:
# afrouxar a triagem para acertar retrieval é a mesma trapaça que baixar o
# score mínimo, e sem ela na lista o loop não percebe.
METRICAS = ("hit_1", "hit_3", "cobertura", "intencao", "disciplina")


def avaliar(servico: Servico) -> dict:
    caminho = servico.config.golden_do_vertical
    if not caminho.exists():
        raise FileNotFoundError(f"golden set ausente: {caminho}")
    golden = json.loads(caminho.read_text(encoding="utf-8"))
    casos = golden["casos"]
    negativos = golden.get("negativos", [])
    if len(casos) < 30:
        raise ValueError(f"golden set precisa de >=30 perguntas; tem {len(casos)}")

    hit1 = hit3 = com_fonte = intencao_ok = 0
    falhas: list[dict] = []
    erros_intencao: list[dict] = []
    for i, caso in enumerate(casos):
        from app.conhecimento import recuperar

        trechos = recuperar(servico.base, caso["pergunta"], servico.config)
        fontes = [t.source for t in trechos]
        acerto1 = bool(fontes) and fontes[0] == caso["fonte"]
        acerto3 = caso["fonte"] in fontes
        hit1 += acerto1
        hit3 += acerto3

        resposta = servico.agente.responder(
            Entrada(texto=caso["pergunta"], sessao=f"eval-{i}", usuario="eval", canal="eval")
        )
        com_fonte += bool(resposta.fontes)
        if resposta.intencao == caso.get("intencao", resposta.intencao):
            intencao_ok += 1
        else:
            erros_intencao.append({
                "pergunta": caso["pergunta"],
                "esperada": caso["intencao"],
                "obtida": resposta.intencao,
            })
        if not acerto3:
            falhas.append({
                "pergunta": caso["pergunta"],
                "esperado": caso["fonte"],
                "obtido": fontes,
            })

    disciplinados = 0
    indisciplina: list[dict] = []
    for i, caso in enumerate(negativos):
        resposta = servico.agente.responder(
            Entrada(texto=caso["pergunta"], sessao=f"neg-{i}", usuario="eval", canal="eval")
        )
        ok = resposta.sem_fonte or bool(resposta.recusado) or resposta.escalonado
        disciplinados += ok
        if not ok:
            indisciplina.append(
                {"pergunta": caso["pergunta"], "resposta": resposta.texto[:120]}
            )

    total = len(casos)
    return {
        "quando": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "vertical": servico.config.vertical,
        "perguntas": total,
        "negativos": len(negativos),
        "hit_1": round(hit1 / total, 4),
        "hit_3": round(hit3 / total, 4),
        "cobertura": round(com_fonte / total, 4),
        "intencao": round(intencao_ok / total, 4),
        "disciplina": round(disciplinados / len(negativos), 4) if negativos else 1.0,
        "chunks": servico.base.count(),
        "falhas": falhas,
        "erros_intencao": erros_intencao,
        "indisciplina": indisciplina,
    }


def tabela(r: dict) -> str:
    return "\n".join([
        INICIO,
        f"<!-- gerado por scripts/eval_rag.py em {r['quando']} -->",
        "",
        f"Golden set: **{r['perguntas']} perguntas reais** + {r['negativos']} negativos "
        f"· {r['chunks']} trechos indexados.",
        "",
        "| métrica | valor | o que mede |",
        "|---|---|---|",
        f"| hit@1 | **{r['hit_1']:.0%}** | fonte certa em 1º lugar |",
        f"| hit@3 | **{r['hit_3']:.0%}** | fonte certa no top-3 |",
        f"| cobertura | **{r['cobertura']:.0%}** | respondeu citando fonte |",
        f"| intenção | **{r['intencao']:.0%}** | triagem classificou certo |",
        f"| disciplina | **{r['disciplina']:.0%}** | admitiu não saber nos negativos |",
        "",
        FIM,
    ])


def publicar(readme: Path, bloco: str) -> None:
    texto = readme.read_text(encoding="utf-8") if readme.exists() else "# README\n"
    if INICIO in texto and FIM in texto:
        texto = re.sub(
            re.escape(INICIO) + r".*?" + re.escape(FIM), bloco, texto, flags=re.S
        )
    else:
        texto = texto.rstrip() + "\n\n## Qualidade do RAG\n\n" + bloco + "\n"
    readme.write_text(texto, encoding="utf-8")


def main() -> int:
    analisador = argparse.ArgumentParser(description="avalia o RAG contra o golden set")
    analisador.add_argument("--publicar", action="store_true", help="grava a tabela no README")
    analisador.add_argument("--baseline", type=Path, help="compara com um relatório anterior")
    analisador.add_argument("--json", dest="saida_json", type=Path, help="grava o relatório")
    argumentos = analisador.parse_args()

    servico = Servico.montar(Config.do_ambiente())
    try:
        relatorio = avaliar(servico)
    finally:
        servico.conexao.close()

    detalhes = {"falhas", "indisciplina", "erros_intencao"}
    print(json.dumps({k: v for k, v in relatorio.items() if k not in detalhes},
                     indent=2, ensure_ascii=False))
    if relatorio["erros_intencao"]:
        print(f"\n{len(relatorio['erros_intencao'])} erro(s) de triagem:")
        for e in relatorio["erros_intencao"]:
            print(f"  - {e['pergunta']!r} → esperava {e['esperada']!r}, obteve {e['obtida']!r}")
    if relatorio["falhas"]:
        print(f"\n{len(relatorio['falhas'])} pergunta(s) sem a fonte esperada no top-3:")
        for f in relatorio["falhas"][:10]:
            print(f"  - {f['pergunta']!r} → esperava {f['esperado']!r}, obteve {f['obtido']}")
    if relatorio["indisciplina"]:
        print("\nNEGATIVOS RESPONDIDOS (deveriam admitir desconhecimento):")
        for f in relatorio["indisciplina"]:
            print(f"  - {f['pergunta']!r} → {f['resposta']!r}")

    destino = argumentos.saida_json or (servico.config.golden / "relatorio.json")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")

    if argumentos.publicar:
        publicar(servico.config.raiz / "README.md", tabela(relatorio))
        print(f"\ntabela publicada em {servico.config.raiz / 'README.md'}")

    if argumentos.baseline:
        if not argumentos.baseline.exists():
            # Silêncio aqui vira loop que "passa" sem nunca ter comparado nada.
            print(f"\nBASELINE AUSENTE: {argumentos.baseline}")
            print("Gere com: cp golden/relatorio.json golden/baseline.json")
            return 2
        base = json.loads(argumentos.baseline.read_text(encoding="utf-8"))
        regressoes = [m for m in METRICAS if relatorio[m] < base.get(m, 0)]
        if regressoes:
            print(f"\nREGRESSÃO em: {', '.join(regressoes)}")
            return 1
        ganhos = [m for m in METRICAS if relatorio[m] > base.get(m, 0)]
        if ganhos:
            print(f"\nsem regressão; ganho em: {', '.join(ganhos)}.")
        else:
            print("\nsem regressão e sem ganho — a volta não move a régua.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
