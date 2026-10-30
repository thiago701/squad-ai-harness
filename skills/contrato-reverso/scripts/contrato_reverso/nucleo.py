# -*- coding: utf-8 -*-
"""Orquestra uma verificação reversa: níveis, cache, aceites, veredito e correlação de versões."""
from __future__ import annotations

import json
import subprocess
import time
from dataclasses import fields
from datetime import date, datetime, timezone
from pathlib import Path

from . import CODIGO_SAIDA, INFO, PENDENTE, QUEBRA, RISCO, Achado, ResultadoCamada
from . import camada_a, camada_b, execucao
from .modelo import (ArquivoMalformado, Contrato, ContratoInvalido, DependenciaAusente, carregar_contrato, hash_arquivos, ler_yaml,
                     substituir)
from .openapi import OpenApi

CAMADAS_POR_NIVEL = {
    "rapido": ("A", "B"),
    "direcionado": ("A", "B", "C1"),
    "ampliado": ("A", "B", "C1", "SUITE", "C2"),
}
ALCANCE_ESTATICO = {
    "A": "o contrato publicado (OpenAPI) promete o que o consumidor usa — conformidade da especificação; "
         "não executa nada",
    "B": "a configuração do Gateway (template SAM) atende o contrato e o consumidor — rotas, autorizador, CORS, "
         "limites; não prova o Gateway implantado",
}
ORCAMENTO_PADRAO_S = {"rapido": 2.0, "direcionado": 30.0, "ampliado": 300.0}


def _achado_de(d: dict) -> Achado:
    nomes = {f.name for f in fields(Achado)}
    return Achado(**{k: v for k, v in d.items() if k in nomes})


def _git(raiz: Path, *args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=raiz, capture_output=True, text=True, timeout=20)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def pasta_trabalho(raiz: Path) -> Path:
    """Cache, trava e relatórios da ferramenta no projeto (sugira `.contrato-reverso/` no .gitignore)."""
    return raiz / ".contrato-reverso"


def pasta_saida_padrao(raiz: Path) -> Path:
    return pasta_trabalho(raiz) / "relatorios"


def _orcamentos(raiz: Path) -> dict:
    """Orçamento por nível: contracts/consumidores/orcamento.json (projeto) ou o padrão medido."""
    for arq in (raiz / "contracts" / "consumidores" / "orcamento.json",
                raiz / "quality" / "orcamento-contrato-reverso.json"):
        try:
            dados = json.loads(arq.read_text(encoding="utf-8"))
            return {**ORCAMENTO_PADRAO_S, **{k: float(v) for k, v in dados.get("segundos", {}).items()}}
        except (OSError, ValueError):
            continue
    return dict(ORCAMENTO_PADRAO_S)


def escrever_entrada(contrato: Contrato, gw) -> Path:
    """Contrato já parseado + Gateway normalizado em JSON: o verificador do provedor (Java, Python, Node)
    lê só isto — nenhum stack precisa de parser YAML nem saber ler SAM/CloudFormation/Terraform."""
    from .execucao import hash_contrato
    destino = pasta_trabalho(contrato.raiz_repo) / "entrada" / f"{contrato.nome}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps({"contrato_hash": hash_contrato(contrato), "contrato": contrato.bruto,
                                   "gateway": gw.para_dict() if gw is not None else None},
                                  ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return destino


def _aceites(contrato: Contrato) -> tuple[dict[str, dict], list[Achado]]:
    arq = contrato.arquivo.parent / "divergencias-aceitas.yaml"
    if not arq.is_file():
        return {}, []
    dados = ler_yaml(arq) or {}
    validos: dict[str, dict] = {}
    avisos: list[Achado] = []
    hoje = date.today()
    for item in dados.get("aceites") or []:
        chave = (item or {}).get("chave")
        faltam = [c for c in ("chave", "justificativa", "responsavel", "aprovado_em", "expira_em") if not item.get(c)]
        if faltam:
            avisos.append(Achado("infra", RISCO, "ACEITE-INCOMPLETO", None, f"aceite {chave!r} ignorado: falta {faltam}"))
            continue
        expira = item["expira_em"]
        expira = expira if isinstance(expira, date) else date.fromisoformat(str(expira))
        if expira < hoje:
            avisos.append(Achado("infra", RISCO, "ACEITE-EXPIRADO", None, f"aceite {chave} expirou em {expira}"))
            continue
        validos[chave] = item
    return validos, avisos


def _cache_ler(arq: Path) -> dict:
    try:
        return json.loads(arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _cache_gravar(arq: Path, dados: dict) -> None:
    try:
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass  # cache é otimização: falha nunca muda o veredito


def verificar(arquivo: Path, raiz: Path, nivel: str = "rapido", suite_completa: bool = False,
              alvo: str | None = None, ambiente: str | None = None, permitir_escrita: bool = False,
              usar_cache: bool = True, dir_saida: Path | None = None) -> dict:
    inicio = time.monotonic()
    escopo = list(CAMADAS_POR_NIVEL[nivel])
    if suite_completa and "SUITE" not in escopo and "C1" in escopo:
        escopo.insert(escopo.index("C1") + 1, "SUITE")
    camadas: dict[str, ResultadoCamada] = {}
    erro_entrada: Achado | None = None
    contrato: Contrato | None = None
    try:
        contrato = carregar_contrato(arquivo, raiz)
    except ContratoInvalido as exc:
        erro_entrada = Achado("infra", QUEBRA, "CONTRATO-INVALIDO", None, str(exc))
    except DependenciaAusente as exc:
        erro_entrada = Achado("infra", PENDENTE, "DEPENDENCIA-AUSENTE", None, str(exc))
    if contrato is None:
        return _fechar(arquivo, raiz, nivel, escopo, None, camadas, [erro_entrada], {}, inicio, dir_saida, [])
    avisos_escopo: list[Achado] = []
    if "SUITE" in escopo and not (contrato.provedor.get("suite_ampliada") or {}).get("comando"):
        escopo.remove("SUITE")
        avisos_escopo.append(Achado("infra", RISCO, "SUITE-NAO-DECLARADA", None,
                                    "pediu-se a suíte completa (mudança transversal ou nível ampliado), mas o contrato "
                                    "não declara provedor.suite_ampliada — só o verificador do consumidor rodou"))

    oas = gw = None
    for camada in ("A", "B"):
        t0 = time.monotonic()
        res = ResultadoCamada(camada=camada, executada=False, alcance=ALCANCE_ESTATICO[camada])
        try:
            if oas is None:
                oas = OpenApi(ler_yaml(contrato.openapi)) if contrato.openapi else None
            if camada == "A":
                if oas is None:
                    res.executada = True  # a ausência de contrato publicado É o achado desta camada
                    res.achados = [Achado("A", RISCO, "A-SEM-CONTRATO-PUBLICADO", None,
                                          "o provedor não publica OpenAPI: nenhuma promessa a conferir — o consumidor "
                                          "depende só do comportamento atual (C1/C2). Publique o contrato.")]
                else:
                    res.achados = camada_a.verificar(contrato, oas)
                    res.executada = True
            else:
                if not contrato.template_gateway:
                    res.motivo_nao_execucao = "contrato não aponta provedor.gateway.template"
                else:
                    gw = camada_b.carregar_gateway(contrato.template_gateway, contrato.gateway.get("recurso_api"),
                                                   contrato.gateway.get("tipo"))
                    res.achados = camada_b.verificar(contrato, oas, gw)
                    res.extras["gateway"] = gw.para_dict()
                    res.executada = True
        except DependenciaAusente as exc:
            res.motivo_nao_execucao = str(exc)
        except ArquivoMalformado as exc:
            res.executada = True  # ler e falhar É a evidência: o deploy desse arquivo também falharia
            res.achados = [Achado(camada, QUEBRA, f"{camada}-ARQUIVO-MALFORMADO", None, str(exc))]
        res.duracao_s = round(time.monotonic() - t0, 3)
        camadas[camada] = res

    cache_arq = pasta_trabalho(raiz) / "cache.json"
    cache = _cache_ler(cache_arq) if usar_cache else {}
    if "C1" in escopo:
        chave_cmd = "suite_ampliada" if "SUITE" in escopo else "verificador_inprocess"
        entradas = [contrato.arquivo, contrato.openapi, contrato.template_gateway,
                    contrato.caminho_repo(contrato.provedor.get("raiz"))]
        hash_entradas = hash_arquivos([p for p in entradas if p]) + ":" + chave_cmd
        chave_cache = f"{contrato.nome}:C1"
        anterior = cache.get(chave_cache)
        if usar_cache and anterior and anterior.get("hash") == hash_entradas:
            res = ResultadoCamada(camada="C1", executada=True, alcance=anterior["alcance"], cache=True,
                                  duracao_s=0.0, achados=[_achado_de(a) for a in anterior["achados"]],
                                  extras=anterior.get("extras", {}))
        else:
            entrada = escrever_entrada(contrato, gw)
            res = execucao.rodar_verificador(contrato, chave_cmd, "C1", entrada=entrada, gateway=gw)
            if res.executada:
                cache[chave_cache] = {"hash": hash_entradas, "alcance": res.alcance,
                                      "achados": [a.para_dict() for a in res.achados],
                                      "extras": {k: v for k, v in res.extras.items() if k != "saida_final"},
                                      "gravado_em": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                if usar_cache:
                    _cache_gravar(cache_arq, cache)
        res.extras["comando"] = chave_cmd
        camadas["C1"] = res
        if "SUITE" in escopo:
            camadas["SUITE"] = ResultadoCamada(camada="SUITE", executada=res.executada, cache=res.cache,
                                               motivo_nao_execucao=res.motivo_nao_execucao,
                                               alcance="suíte completa do provedor (mesma execução que gerou C1)")
    if "C2" in escopo:
        camadas["C2"] = execucao.replay_http(contrato, alvo, ambiente, permitir_escrita, gateway=gw)

    aceites, avisos = _aceites(contrato)
    avisos = avisos_escopo + avisos
    if contrato.bruto.get("rascunho"):
        avisos.append(Achado("infra", PENDENTE, "CONTRATO-RASCUNHO", None,
                             "contrato em rascunho (gerado do OpenAPI do provedor): revise contra o consumidor real e "
                             "remova `rascunho: true` — até lá o veredito é no máximo inconclusivo"))
    return _fechar(arquivo, raiz, nivel, escopo, contrato, camadas, avisos, aceites, inicio, dir_saida,
                   [] if oas is None else _matriz(contrato, oas, gw, camadas))


def _fechar(arquivo: Path, raiz: Path, nivel: str, escopo: list[str], contrato: Contrato | None,
            camadas: dict[str, ResultadoCamada], extras: list[Achado], aceites: dict, inicio: float,
            dir_saida: Path | None, matriz: list[dict]) -> dict:
    todos: list[Achado] = [a for c in camadas.values() for a in c.achados] + [a for a in extras if a]
    aceitos = [a for a in todos if a.chave in aceites]
    usados = {a.chave for a in aceitos}
    for chave in sorted(set(aceites) - usados):
        todos.append(Achado("infra", INFO, "ACEITE-OBSOLETO", None,
                            f"aceite {chave} não corresponde a nenhum achado atual — remova do arquivo"))
    quebras = [a for a in todos if a.severidade == QUEBRA and a.chave not in aceites]
    nao_executadas = [c for c in escopo if c in camadas and not camadas[c].executada] + \
                     [c for c in escopo if c not in camadas]
    if quebras:
        veredito = "reprovado"
    elif nao_executadas or any(a.codigo in ("DEPENDENCIA-AUSENTE", "CONTRATO-RASCUNHO") for a in todos):
        veredito = "inconclusivo"
    else:
        veredito = "aprovado"
    duracao = round(time.monotonic() - inicio, 3)
    orc = _orcamentos(raiz)
    limite = orc.get(nivel)
    if limite and duracao > limite and veredito != "inconclusivo":
        todos.append(Achado("infra", RISCO, "ORCAMENTO-EXCEDIDO", None,
                            f"nível {nivel} levou {duracao}s (orçamento {limite}s): justifique a proteção extra "
                            "ou compense"))
    entradas = {}
    if contrato is not None:
        for nome, p in (("contrato", contrato.arquivo), ("openapi", contrato.openapi),
                        ("gateway", contrato.template_gateway),
                        ("provedor", contrato.caminho_repo(contrato.provedor.get("raiz")))):
            if p:
                entradas[nome] = {"caminho": str(p.relative_to(raiz)).replace("\\", "/"), "hash": hash_arquivos([p])}
    resultado = {
        "ferramenta": "contrato-reverso/1",
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "contrato": str(arquivo.relative_to(raiz)).replace("\\", "/") if arquivo.is_relative_to(raiz) else str(arquivo),
        "consumidor": contrato.nome if contrato else None,
        "nivel": nivel,
        "escopo": escopo,
        "veredito": veredito,
        "codigo_saida": CODIGO_SAIDA[veredito],
        "duracao_s": duracao,
        "orcamento_s": limite,
        "versoes": {
            "commit": _git(raiz, "rev-parse", "HEAD") or None,
            "working_tree_suja": bool(_git(raiz, "status", "--porcelain", "--untracked-files=no")),
            "entradas": entradas,
            "provedor_observado": (camadas.get("C1").extras.get("observado") if camadas.get("C1") else None),
            "gateway_implantado": ({k: v for k, v in camadas["C2"].extras.items()} if "C2" in camadas else None),
        },
        "camadas": {nome: {"executada": c.executada, "motivo_nao_execucao": c.motivo_nao_execucao,
                           "duracao_s": c.duracao_s, "cache": c.cache, "alcance": c.alcance,
                           "extras": {k: v for k, v in c.extras.items() if k not in ("gateway",)},
                           "quebras": sum(1 for a in c.achados if a.severidade == QUEBRA)}
                    for nome, c in camadas.items()},
        "achados": [dict(a.para_dict(), aceito=a.chave in aceites) for a in todos],
        "aceites_aplicados": [dict(aceites[a.chave], chave=a.chave) for a in aceitos],
        "limitacoes": _limitacoes(contrato, camadas, escopo),
        "matriz": matriz,
    }
    if contrato is not None and "B" in camadas and camadas["B"].extras.get("gateway"):
        resultado["gateway_modelo"] = camadas["B"].extras["gateway"]
    if dir_saida is not None:
        from .relatorio import gravar
        gravar(resultado, dir_saida)
    return resultado


def _limitacoes(contrato: Contrato | None, camadas: dict[str, ResultadoCamada], escopo: list[str]) -> list[str]:
    if contrato is None:
        return ["contrato não carregado"]
    lim: list[str] = []
    if contrato.consumidor.get("limitacao"):
        lim.append(str(contrato.consumidor["limitacao"]))
    if contrato.consumidor.get("hipotetico"):
        lim.append("perfil do consumidor marcado como hipótese: achados que dependem dele (ex.: CORS) valem sob "
                   "essa hipótese")
    mesma = [it.id for it in contrato.interacoes if it.mesma_fonte_do_provedor]
    if mesma:
        lim.append(f"expectativas tiradas do próprio OpenAPI (mesma fonte do provedor, podem herdar o mesmo erro): {mesma}")
    for nome in ("C1", "C2"):
        if nome not in escopo:
            lim.append(f"camada {nome} fora do escopo do nível — não comprovada nesta execução")
        elif nome in camadas and not camadas[nome].executada:
            lim.append(f"camada {nome} não executada: {camadas[nome].motivo_nao_execucao}")
    if "C2" not in camadas or not camadas["C2"].executada:
        lim.append("compatibilidade de ponta a ponta pelo Gateway implantado NÃO declarada (sem evidência C2)")
    return lim


def _matriz(contrato: Contrato, oas: OpenApi, gw, camadas: dict[str, ResultadoCamada]) -> list[dict]:
    linhas = []
    var = contrato.variaveis_base()
    for it in contrato.interacoes:
        for n in it.capturar:
            var.setdefault(n, "valor-amostra")
    for it in contrato.interacoes:
        caminho = substituir(it.caminho, var)
        op = oas.achar(it.metodo, caminho) if it.metodo != "OPTIONS" else None
        rota = gw.rota_para(it.metodo, caminho) if gw else None
        evid = {}
        for nome, c in camadas.items():
            if nome == "SUITE":
                continue
            if not c.executada:
                evid[nome] = "não executada"
                continue
            proprios = [a for a in c.achados if a.interacao == it.id]
            q = sorted({a.codigo for a in proprios if a.severidade == QUEBRA})
            r = sorted({a.codigo for a in proprios if a.severidade in (RISCO, PENDENTE)})
            evid[nome] = ("QUEBRA " + ",".join(q)) if q else (("risco " + ",".join(r)) if r else "ok")
        if it.metodo == "OPTIONS":
            gateway = "CORS: " + ("configurado" if gw and gw.cors else "AUSENTE")
        elif rota:
            gateway = f"{rota.metodo} {rota.caminho} · autorizador={rota.autorizador or 'nenhum'}"
        else:
            gateway = "SEM ROTA"
        linhas.append({
            "consumidor": contrato.nome, "interacao": it.id, "expectativa": it.risco,
            "origem": f"{it.origem.get('tipo')}: {it.origem.get('ref', '')}",
            "endpoint": f"{op.metodo} {op.caminho}" if op else ("preflight" if it.metodo == "OPTIONS" else "AUSENTE"),
            "gateway": gateway,
            "servico": f"{rota.funcao} ({rota.handler})" if rota else "—",
            "teste": ["A" if it.metodo != "OPTIONS" else None, "B",
                      f"C1 verificador-provedor[{it.id}]", f"C2 replay[{it.id}]"],
            "evidencia": evid,
        })
        linhas[-1]["teste"] = [t for t in linhas[-1]["teste"] if t]
    return linhas


def veredito_agregado(resultados: list[dict]) -> str:
    vs = {r["veredito"] for r in resultados}
    if "reprovado" in vs:
        return "reprovado"
    if "inconclusivo" in vs or not resultados:
        return "inconclusivo"
    return "aprovado"
