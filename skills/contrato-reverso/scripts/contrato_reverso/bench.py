# -*- coding: utf-8 -*-
"""Bench antes × depois com regressões CONTROLADAS — genérico, para qualquer projeto.

Mutações (numa cópia temporária, nunca no projeto):
  • AUTOMÁTICAS, derivadas do que o consumidor usa: OpenAPI (required removido, enum novo em enum
    fechado, tipo trocado, null novo, status removido, rota renomeada) e Gateway SAM (rota removida
    sem sombra, autorizador removido, CORS removido, payload 1.0, path renomeado) + COMPATÍVEIS
    (campo opcional novo, query opcional nova, texto, rota nova, throttling).
  • DO PROJETO: `mutacoes.yaml` ao lado do contrato (ex.: serialização, isolamento, status no código).

  ANTES  = proteção que já existia: `provedor.suite_existente` (sem o verificador novo)
  DEPOIS = níveis rápido (A+B) e direcionado (A+B+C1)
  AUTO   = nível que a seleção por impacto escolheria para o arquivo mutado
Detecção "depois" = chaves de QUEBRA novas em relação à linha de base sem mutação.
Mudança compatível que gera quebra nova = FALSO POSITIVO. Linha de base repetida = estabilidade.
"""
from __future__ import annotations

import json
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import QUEBRA
from . import impacto as imp_mod
from .camada_b import carregar_gateway
from .execucao import _resolver_comando
from .modelo import Contrato, carregar_contrato, ler_yaml, substituir  # noqa: F401
from .nucleo import pasta_trabalho
from .openapi import OpenApi, casa_template

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

CR = Path(__file__).resolve().parents[1] / "cr.py"
IGNORAR = shutil.ignore_patterns("target", "node_modules", ".git", "__pycache__", ".contrato-reverso", "build", ".gradle")
VALOR_NOVO = "VALOR_NOVO_CDC"


@dataclass
class Mutacao:
    id: str
    tipo: str               # quebra | compativel
    alvo: str               # contrato | gateway | implementacao
    arquivo: str            # relativo à raiz
    descricao: str
    aplicar: Callable[[Path], None] = field(repr=False, default=lambda p: None)
    origem: str = "automatica"


# --------------------------------------------------------------------------- utilitários
def _dump(doc) -> str:
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=1000)


def _editar_yaml(rel: str, fn: Callable[[dict], None]) -> Callable[[Path], None]:
    def aplicar(raiz: Path) -> None:
        arq = raiz / rel
        doc = ler_yaml(arq)
        fn(doc)
        arq.write_text(_dump(doc), encoding="utf-8")
    return aplicar


def _trocas(rel: str, trocas: list[dict]) -> Callable[[Path], None]:
    def aplicar(raiz: Path) -> None:
        arq = raiz / rel
        texto = arq.read_text(encoding="utf-8")
        for t in trocas:
            i = texto.find(t.get("ancora", ""))
            j = texto.find(t["antigo"], max(i, 0))
            if i < 0 or j < 0:
                raise RuntimeError(f"mutação em {rel}: trecho não encontrado (âncora {t.get('ancora')!r})")
            texto = texto[:j] + t["novo"] + texto[j + len(t["antigo"]):]
        arq.write_text(texto, encoding="utf-8")
    return aplicar


def _ref_alvo(doc: dict, no: dict) -> dict:
    """Devolve o dict REAL a mutar (segue $ref local até o componente)."""
    for _ in range(16):
        if isinstance(no, dict) and "$ref" in no and str(no["$ref"]).startswith("#/"):
            alvo = doc
            for parte in str(no["$ref"])[2:].split("/"):
                alvo = alvo[parte.replace("~1", "/").replace("~0", "~")]
            no = alvo
        else:
            break
    return no


def _caminho_amostra(c: Contrato, caminho: str) -> str:
    var = c.variaveis_base()
    for it in c.interacoes:
        for n in it.capturar:
            var.setdefault(n, "valor-amostra")
    return substituir(caminho, var)


def _schema_resposta(doc: dict, metodo: str, caminho_oas: str, status: int, content: str | None) -> dict | None:
    op = doc["paths"][caminho_oas][metodo.lower()]
    resp = _ref_alvo(doc, (op.get("responses") or {}).get(str(status)) or (op.get("responses") or {}).get(status) or {})
    conteudo = resp.get("content") or {}
    chave = content if content in conteudo else next(iter(conteudo), None)
    if not chave:
        return None
    return _ref_alvo(doc, conteudo[chave].get("schema") or {})


def _campo(doc: dict, raiz_schema: dict, caminho: list[str]) -> tuple[dict, str] | None:
    """(schema-pai, nome) para caminho ['items', '[]', 'status'] ou ['createdAt']."""
    pai = raiz_schema
    for i, parte in enumerate(caminho):
        if parte == "[]":
            continue
        props = pai.get("properties") or {}
        if parte not in props:
            return None
        if i == len(caminho) - 1:
            return pai, parte
        filho = _ref_alvo(doc, props[parte])
        if i + 1 < len(caminho) and caminho[i + 1] == "[]":
            filho = _ref_alvo(doc, filho.get("items") or {})
        pai = filho
    return None


# --------------------------------------------------------------------------- mutações automáticas
def mutacoes_automaticas(c: Contrato, max_por_operador: int = 2) -> list[Mutacao]:
    muts: list[Mutacao] = []
    if c.openapi and c.openapi.is_file():
        muts += _mutacoes_openapi(c, max_por_operador)
    if c.template_gateway and c.template_gateway.is_file():
        muts += _mutacoes_gateway(c, max_por_operador)
    return muts


def _usos(c: Contrato, oas: OpenApi):
    """(interação, operação, status, content, [(caminho_campo, exp)]) do que o consumidor lê."""
    for it in c.interacoes:
        if it.metodo == "OPTIONS":
            continue
        op = oas.achar(it.metodo, _caminho_amostra(c, it.caminho))
        if op is None:
            continue
        campos: list[tuple[list[str], dict]] = []
        for nome, exp in (it.resposta.get("campos") or {}).items():
            campos.append(([nome], exp or {}))
            for sub, e2 in ((exp or {}).get("itens") or {}).items():
                campos.append(([nome, "[]", sub], e2 or {}))
        yield it, op, it.status_esperados[0], (it.content_types[0] if it.content_types else None), campos


def _mutacoes_openapi(c: Contrato, maximo: int) -> list[Mutacao]:
    rel = str(c.openapi.relative_to(c.raiz_repo)).replace("\\", "/")
    doc0 = ler_yaml(c.openapi)
    oas = OpenApi(doc0)
    cont: dict[str, int] = {}
    vistos: set[str] = set()
    muts: list[Mutacao] = []

    def add(op_id: str, m: Mutacao) -> None:
        if m.id in vistos or cont.get(op_id, 0) >= maximo:
            return
        vistos.add(m.id)
        cont[op_id] = cont.get(op_id, 0) + 1
        muts.append(m)

    for it, op, status, ct, campos in _usos(c, oas):
        sch = _schema_resposta(doc0, op.metodo, op.caminho, status, ct)
        for caminho, exp in campos:
            achado = _campo(doc0, sch or {}, caminho) if sch else None
            if not achado:
                continue
            pai, nome = achado
            rot = ".".join(p for p in caminho if p != "[]")
            def fn_gen(acao, op=op, status=status, ct=ct, caminho=caminho):
                def fn(doc):
                    s = _schema_resposta(doc, op.metodo, op.caminho, status, ct)
                    p, n = _campo(doc, s, caminho)
                    acao(doc, p, n)
                return fn
            obrig = exp.get("presenca", "obrigatoria") == "obrigatoria" and not exp.get("nulo")
            if obrig and nome in (pai.get("required") or []):
                add("req", Mutacao(f"oas-required-sem-{rot}", "quebra", "contrato", rel,
                                   f"contrato deixa de prometer '{rot}' ({op.metodo} {op.caminho})",
                                   _editar_yaml(rel, fn_gen(lambda d, p, n: p["required"].remove(n)))))
            prop = _ref_alvo(doc0, pai["properties"][nome])
            if nome in c.enums_fechados and isinstance(prop.get("enum"), list):
                add("enum", Mutacao(f"oas-enum-novo-{rot}", "quebra", "contrato", rel,
                                    f"valor novo no enum '{rot}' — consumidor com switch exaustivo",
                                    _editar_yaml(rel, fn_gen(lambda d, p, n: _ref_alvo(d, p["properties"][n])["enum"].append(VALOR_NOVO)))))
            tipo = prop.get("type")
            base = [t for t in (tipo if isinstance(tipo, list) else [tipo]) if t and t != "null"]
            if exp.get("tipo") in ("string", "integer") and base == [exp.get("tipo")] and "enum" not in prop:
                novo = "integer" if base == ["string"] else "string"
                def trocar_tipo(d, p, n, novo=novo):
                    alvo = _ref_alvo(d, p["properties"][n])
                    t = alvo.get("type")
                    alvo["type"] = [novo, "null"] if isinstance(t, list) and "null" in t else novo
                    alvo.pop("format", None)
                add("tipo", Mutacao(f"oas-tipo-{rot}", "quebra", "contrato", rel,
                                    f"'{rot}' muda de {base[0]} para {novo}", _editar_yaml(rel, fn_gen(trocar_tipo))))
            if not exp.get("nulo") and base and not (isinstance(tipo, list) and "null" in tipo) and not prop.get("nullable"):
                def anular(d, p, n):
                    alvo = _ref_alvo(d, p["properties"][n])
                    t = alvo.get("type")
                    alvo["type"] = (list(t) if isinstance(t, list) else [t]) + ["null"]
                    if isinstance(alvo.get("enum"), list):
                        alvo["enum"].append(None)
                add("nulo", Mutacao(f"oas-nulo-{rot}", "quebra", "contrato", rel,
                                    f"'{rot}' passa a aceitar null", _editar_yaml(rel, fn_gen(anular))))
        if str(status) in {str(k) for k in (op.dados.get("responses") or {})} and status != 401:
            def sem_status(d, op=op, status=status):
                r = d["paths"][op.caminho][op.metodo.lower()]["responses"]
                r.pop(str(status), None)
                r.pop(status, None)
            add("status", Mutacao(
                f"oas-sem-{status}-{op.metodo.lower()}{op.caminho.replace('/', '_')}", "quebra", "contrato", rel,
                f"contrato deixa de declarar {status} em {op.metodo} {op.caminho}", _editar_yaml(rel, sem_status)))
        if "rota" not in cont or cont["rota"] < maximo:
            def renomear(d, op=op):
                d["paths"][op.caminho.rstrip("/") + "-v2"] = d["paths"].pop(op.caminho)
            add("rota", Mutacao(f"oas-rota-renomeada{op.caminho.replace('/', '_')}", "quebra", "contrato", rel,
                                f"{op.caminho} renomeada só no OpenAPI", _editar_yaml(rel, renomear)))
    # compatíveis
    primeiro = next(_usos(c, oas), None)
    if primeiro:
        it, op, status, ct, _ = primeiro
        def campo_novo(d, op=op, status=status, ct=ct):
            s = _schema_resposta(d, op.metodo, op.caminho, status, ct)
            s.setdefault("properties", {})["campoNovoCdc"] = {"type": "string"}
        muts.append(Mutacao("ok-oas-campo-opcional-novo", "compativel", "contrato", rel,
                            "campo opcional novo na resposta", _editar_yaml(rel, campo_novo)))
        def query_nova(d, op=op):
            o = d["paths"][op.caminho][op.metodo.lower()]
            o.setdefault("parameters", []).append({"name": "cdcFiltroNovo", "in": "query", "required": False,
                                                   "schema": {"type": "string"}})
        muts.append(Mutacao("ok-oas-query-opcional-nova", "compativel", "contrato", rel,
                            "parâmetro de query opcional novo", _editar_yaml(rel, query_nova)))
        def texto(d, op=op):
            d["paths"][op.caminho][op.metodo.lower()]["summary"] = "texto revisado (cdc)"
        muts.append(Mutacao("ok-oas-texto", "compativel", "contrato", rel, "só documentação", _editar_yaml(rel, texto)))
    return muts


def _eventos(doc: dict, api: str):
    for nome, rec in (doc.get("Resources") or {}).items():
        if (rec or {}).get("Type") != "AWS::Serverless::Function":
            continue
        for ev_nome, ev in ((rec.get("Properties") or {}).get("Events") or {}).items():
            props = (ev or {}).get("Properties") or {}
            tipo = (ev or {}).get("Type")
            ref = props.get("ApiId" if tipo == "HttpApi" else "RestApiId")
            ref = ref.get("Ref") if isinstance(ref, dict) else ref
            padrao = "ServerlessHttpApi" if tipo == "HttpApi" else "ServerlessRestApi"
            if tipo in ("HttpApi", "Api") and (ref or padrao) == api:
                yield nome, ev_nome, props


def _mutacoes_gateway(c: Contrato, maximo: int) -> list[Mutacao]:
    rel = str(c.template_gateway.relative_to(c.raiz_repo)).replace("\\", "/")
    if c.template_gateway.is_dir() or "AWS::Serverless" not in c.template_gateway.read_text(encoding="utf-8"):
        return []  # mutações automáticas de Gateway: só SAM por ora (CloudFormation/CDK/Terraform: use mutacoes.yaml)
    doc0 = ler_yaml(c.template_gateway)
    gw0 = carregar_gateway(c.template_gateway, c.gateway.get("recurso_api"))
    api = gw0.api
    usados = [(it.metodo, _caminho_amostra(c, it.caminho)) for it in c.interacoes if it.metodo != "OPTIONS"]
    muts: list[Mutacao] = []
    n_rota = 0
    for fn_nome, ev_nome, props in list(_eventos(doc0, api)):
        metodo, caminho = str(props.get("Method", "ANY")).upper(), str(props.get("Path", ""))
        atendidos = [(m, p) for m, p in usados if m == metodo and casa_template(caminho, p)]
        if not atendidos or n_rota >= maximo:
            continue
        restantes = [r for r in gw0.rotas if not (r.metodo == metodo and r.caminho == caminho)]
        sombra = any(r.casa(m, p) for m, p in atendidos for r in restantes)
        if sombra:
            continue  # remoção ambígua (outra rota atende): não é quebra certa
        n_rota += 1
        def remover(d, fn_nome=fn_nome, ev_nome=ev_nome):
            del d["Resources"][fn_nome]["Properties"]["Events"][ev_nome]
        muts.append(Mutacao(f"sam-sem-rota-{ev_nome}", "quebra", "gateway", rel,
                            f"rota {metodo} {caminho} removida do Gateway", _editar_yaml(rel, remover)))
        def renomear(d, fn_nome=fn_nome, ev_nome=ev_nome):
            p = d["Resources"][fn_nome]["Properties"]["Events"][ev_nome]["Properties"]
            p["Path"] = str(p["Path"]).rstrip("/") + "-v2"
        muts.append(Mutacao(f"sam-path-renomeado-{ev_nome}", "quebra", "gateway", rel,
                            f"path {caminho} renomeado só no Gateway", _editar_yaml(rel, renomear)))
    api_props = ((doc0.get("Resources") or {}).get(api) or {}).get("Properties") or {}
    oas = OpenApi(ler_yaml(c.openapi)) if c.openapi and c.openapi.is_file() else None
    if (api_props.get("Auth") or {}).get("DefaultAuthorizer") and oas and any(oas.seguranca_exigida(o) for o in oas.operacoes()):
        muts.append(Mutacao("sam-sem-autorizador-padrao", "quebra", "gateway", rel, "Gateway sem autorizador padrão",
                            _editar_yaml(rel, lambda d: d["Resources"][api]["Properties"]["Auth"].pop("DefaultAuthorizer"))))
    chave_cors = "CorsConfiguration" if api_props.get("CorsConfiguration") else ("Cors" if api_props.get("Cors") else None)
    if c.navegador and chave_cors:
        muts.append(Mutacao("sam-sem-cors", "quebra", "gateway", rel, "CORS removido (consumidor de navegador)",
                            _editar_yaml(rel, lambda d: d["Resources"][api]["Properties"].pop(chave_cors))))
    if oas and gw0.tipo_api == "http":
        for fn_nome, ev_nome, props in _eventos(doc0, api):
            metodo, caminho = str(props.get("Method", "ANY")).upper(), str(props.get("Path", ""))
            op = next((o for o in oas.operacoes() if o.metodo == metodo and o.caminho == caminho), None)
            integ = (op.dados.get("x-amazon-apigateway-integration") or {}) if op else {}
            if str(integ.get("payloadFormatVersion", "")) == "2.0" and any(m == metodo and casa_template(caminho, p) for m, p in usados):
                def v1(d, fn_nome=fn_nome, ev_nome=ev_nome):
                    d["Resources"][fn_nome]["Properties"]["Events"][ev_nome]["Properties"]["PayloadFormatVersion"] = "1.0"
                muts.append(Mutacao(f"sam-payload-1.0-{ev_nome}", "quebra", "gateway", rel,
                                    f"{metodo} {caminho} passa a entregar evento 1.0", _editar_yaml(rel, v1)))
                break
    # compatíveis
    eventos = list(_eventos(doc0, api))
    if eventos:
        fn_nome = eventos[0][0]
        def rota_nova(d, fn_nome=fn_nome):
            tipo = "HttpApi" if gw0.tipo_api == "http" else "Api"
            d["Resources"][fn_nome]["Properties"]["Events"]["RotaNovaCdc"] = {
                "Type": tipo, "Properties": {("ApiId" if tipo == "HttpApi" else "RestApiId"): api,
                                             "Path": "/__cdc_rota_nova__", "Method": "GET"}}
        muts.append(Mutacao("ok-sam-rota-nova", "compativel", "gateway", rel, "rota nova no Gateway", _editar_yaml(rel, rota_nova)))
    if gw0.tipo_api == "http" and (api_props.get("DefaultRouteSettings") or {}).get("ThrottlingBurstLimit"):
        def throttling(d):
            rs = d["Resources"][api]["Properties"]["DefaultRouteSettings"]
            rs["ThrottlingBurstLimit"] = int(rs["ThrottlingBurstLimit"]) + 10
        muts.append(Mutacao("ok-sam-throttling", "compativel", "gateway", rel, "ajuste de throttling", _editar_yaml(rel, throttling)))
    return muts


def mutacoes_do_projeto(c: Contrato) -> list[Mutacao]:
    arq = c.arquivo.parent / "mutacoes.yaml"
    if not arq.is_file():
        return []
    dados = ler_yaml(arq) or {}
    saida = []
    for m in dados.get("mutacoes") or []:
        saida.append(Mutacao(m["id"], m["tipo"], m.get("alvo", "implementacao"), m["arquivo"], m.get("descricao", ""),
                             _trocas(m["arquivo"], m["trocas"]), origem="projeto"))
    return saida


# --------------------------------------------------------------------------- execução
def _copiar(c: Contrato, destino: Path) -> Path:
    raiz = c.raiz_repo
    alvos = {raiz / "contracts" / "consumidores"}
    for p in (c.openapi, c.template_gateway, c.caminho_repo(c.provedor.get("raiz"))):
        if p:
            alvos.add(p)
    for p in sorted(alvos):
        rel = p.relative_to(raiz)
        if p.is_dir():
            if str(rel) in ("", "."):
                for filho in p.iterdir():
                    if filho.name in (".git", ".contrato-reverso", "target", "node_modules"):
                        continue
                    (shutil.copytree(filho, destino / filho.name, ignore=IGNORAR, dirs_exist_ok=True)
                     if filho.is_dir() else shutil.copy2(filho, destino / filho.name))
            else:
                shutil.copytree(p, destino / rel, ignore=IGNORAR, dirs_exist_ok=True)
        elif p.is_file():
            (destino / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, destino / rel)
    return destino / c.arquivo.relative_to(raiz)


def _verificar(raiz: Path, contrato: Path, nivel: str, suite: bool = False) -> tuple[dict, float]:
    cmd = [sys.executable, str(CR), "verificar", "--raiz", str(raiz), "--contrato", str(contrato), "--nivel", nivel,
           "--sem-cache", "--json", "--resumo", "--saida", str(raiz / ".contrato-reverso" / "bench-saida")]
    if suite:
        cmd.append("--suite-completa")
    t0 = time.monotonic()
    p = subprocess.run(cmd, cwd=raiz, capture_output=True, text=True, encoding="utf-8", errors="replace")
    dur = round(time.monotonic() - t0, 2)
    inicio = p.stdout.find("[\n  {")
    if inicio < 0:
        raise RuntimeError(f"verificar ({nivel}) não devolveu JSON: {p.stdout[-400:]} {p.stderr[-400:]}")
    return json.loads(p.stdout[inicio:p.stdout.rfind("]") + 1])[0], dur


def _antes(c: Contrato, raiz: Path) -> tuple[int, float] | None:
    cfg = c.provedor.get("suite_existente") or {}
    if not cfg.get("comando"):
        return None
    cwd = raiz / cfg.get("cwd", ".")
    cmd = _resolver_comando([str(x) for x in cfg["comando"]], cwd)
    if cmd is None:
        return None
    t0 = time.monotonic()
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, round(time.monotonic() - t0, 2)


def _quebras(r: dict) -> set[str]:
    return {a["chave"] for a in r["achados"] if a["severidade"] == QUEBRA}


def _p(valores: list[float], q: int) -> float | None:
    if not valores:
        return None
    if len(valores) == 1:
        return valores[0]
    return round(statistics.quantiles(valores, n=100, method="inclusive")[q - 1], 2)


def executar(raiz: Path, contratos: list[Path], pasta_saida: Path | None, repeticoes: int = 3,
             incluir_dinamico: bool = True, max_por_operador: int = 2) -> int:
    if yaml is None:
        print("PyYAML ausente — bench inconclusivo")
        return 2
    pasta_saida = pasta_saida or pasta_trabalho(raiz) / "bench"
    pasta_saida.mkdir(parents=True, exist_ok=True)
    codigo = 0
    for arq in contratos:
        c = carregar_contrato(arq, raiz)
        r = _bench_contrato(c, repeticoes, incluir_dinamico, max_por_operador)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        base = pasta_saida / f"bench-{c.nome}-{stamp}"
        base.with_suffix(".json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
        base.with_suffix(".md").write_text(_markdown(r), encoding="utf-8")
        print(f"\nbench {c.nome}: {'APROVADO' if r['aceite']['aprovado'] else 'REPROVADO'} → {base}.md")
        codigo = max(codigo, 0 if r["aceite"]["aprovado"] else 1)
    return codigo


def _bench_contrato(c: Contrato, repeticoes: int, dinamico: bool, max_por_operador: int) -> dict:
    niveis = ["rapido", "direcionado"] if dinamico else ["rapido"]
    muts = mutacoes_automaticas(c, max_por_operador) + mutacoes_do_projeto(c)
    with tempfile.TemporaryDirectory(prefix="cdc-bench-") as tmp:
        limpo = Path(tmp) / "limpo"
        limpo.mkdir()
        contrato_limpo = _copiar(c, limpo)
        if dinamico:
            _verificar(limpo, contrato_limpo, "direcionado")  # aquece compilação (fora da medição)
            _antes(c, limpo)
        base: dict[str, list] = {n: [] for n in niveis}
        tempos: dict[str, list[float]] = {n: [] for n in niveis + ["antes"]}
        tem_antes = False
        for _ in range(repeticoes):
            for n in niveis:
                r, d = _verificar(limpo, contrato_limpo, n)
                base[n].append(sorted(_quebras(r)))
                tempos[n].append(d)
            if dinamico:
                a = _antes(c, limpo)
                if a is not None:
                    tem_antes = True
                    tempos["antes"].append(a[1])
                    if a[0] != 0:
                        raise RuntimeError("linha de base: a suíte existente já falha sem mutação")
        estavel = all(len({json.dumps(x) for x in base[n]}) == 1 for n in niveis)
        quebras_base = {n: set(base[n][0]) for n in niveis}
        linhas = []
        for m in muts:
            dest = Path(tmp) / "mut"
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(limpo, dest, ignore=shutil.ignore_patterns(".contrato-reverso"))
            try:
                m.aplicar(dest)
            except Exception as exc:  # noqa: BLE001 - mutação inválida vira linha "erro", não derruba o bench
                linhas.append({"id": m.id, "tipo": m.tipo, "alvo": m.alvo, "descricao": m.descricao,
                               "origem": m.origem, "erro": str(exc)})
                continue
            contrato_mut = dest / contrato_limpo.relative_to(limpo)
            linha = {"id": m.id, "tipo": m.tipo, "alvo": m.alvo, "descricao": m.descricao, "origem": m.origem}
            if tem_antes:
                rc, d = _antes(c, dest)
                linha["antes"] = {"detectou": rc != 0, "s": d}
            for n in niveis:
                r, d = _verificar(dest, contrato_mut, n)
                novas = sorted(_quebras(r) - quebras_base[n])
                linha[n] = {"detectou": bool(novas), "s": d, "novas_quebras": novas}
            imp = imp_mod.avaliar(carregar_contrato(contrato_mut, dest), [m.arquivo])
            nivel_auto = "direcionado" if imp.nivel in ("direcionado", "ampliado") else imp.nivel
            if nivel_auto in niveis:
                if nivel_auto == "direcionado" and imp.suite_completa:
                    r, d = _verificar(dest, contrato_mut, "direcionado", suite=True)
                    det = bool(_quebras(r) - quebras_base["direcionado"])
                    linha["auto"] = {"nivel": "direcionado + suíte", "detectou": det, "s": d}
                else:
                    linha["auto"] = {"nivel": nivel_auto, "detectou": linha[nivel_auto]["detectou"],
                                     "s": linha[nivel_auto]["s"]}
            linhas.append(linha)
            print(f"  {m.id:<44} " + " ".join(f"{k}={'✓' if linha[k]['detectou'] else '·'}({linha[k]['s']}s)"
                                              for k in ("antes", *niveis, "auto") if k in linha), flush=True)
    return _consolidar(c, linhas, niveis, tem_antes, estavel, tempos, quebras_base, repeticoes)


def _consolidar(c, linhas, niveis, tem_antes, estavel, tempos, quebras_base, repeticoes) -> dict:
    validas = [l for l in linhas if "erro" not in l]
    quebras = [l for l in validas if l["tipo"] == "quebra"]
    compat = [l for l in validas if l["tipo"] == "compativel"]
    colunas = (["antes"] if tem_antes else []) + niveis + ["auto"]
    resumo = {}
    for col in colunas:
        tempos_col = [l[col]["s"] for l in validas if col in l]
        resumo[col] = {
            "detectadas": sum(1 for l in quebras if l.get(col, {}).get("detectou")),
            "total_quebras": len(quebras),
            "falsos_positivos": sum(1 for l in compat if l.get(col, {}).get("detectou")),
            "total_compativeis": len(compat),
            "por_alvo": {alvo: f"{sum(1 for l in quebras if l['alvo'] == alvo and l.get(col, {}).get('detectou'))}/"
                               f"{sum(1 for l in quebras if l['alvo'] == alvo)}"
                         for alvo in ("contrato", "gateway", "implementacao")},
            "tempo_mediano_s": round(statistics.median(tempos_col), 2) if tempos_col else None,
            "tempo_p90_s": _p(tempos_col, 90),
        }
    melhor = niveis[-1]
    aceite = {
        "detecta_todas_as_quebras": resumo[melhor]["detectadas"] == resumo[melhor]["total_quebras"],
        "zero_falsos_positivos": resumo[melhor]["falsos_positivos"] == 0 and resumo["auto"]["falsos_positivos"] == 0,
        "auto_nao_perde_deteccao": resumo["auto"]["detectadas"] >= resumo[melhor]["detectadas"],
        "estavel_em_repeticoes": estavel,
        "mutacoes_validas": len(validas) == len(linhas),
    }
    if tem_antes:
        aceite["nao_perde_o_que_antes_detectava"] = all(l[melhor]["detectou"] for l in quebras if l["antes"]["detectou"])
        aceite["feedback_mais_rapido_que_antes"] = (resumo["auto"]["tempo_mediano_s"] or 0) < (resumo["antes"]["tempo_mediano_s"] or 0)
    aceite["aprovado"] = all(aceite.values())
    return {"consumidor": c.nome, "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "repeticoes_linha_de_base": repeticoes,
            "quebras_da_linha_de_base": {n: sorted(v) for n, v in quebras_base.items()},
            "tempos_linha_de_base_s": {k: {"mediana": round(statistics.median(v), 2) if v else None, "p90": _p(v, 90),
                                           "amostras": v} for k, v in tempos.items() if v},
            "resumo": resumo, "aceite": aceite, "mutacoes": linhas}


def _markdown(r: dict) -> str:
    cols = list(r["resumo"])
    nome = {"antes": "ANTES (suíte existente)", "rapido": "DEPOIS rápido (A+B)",
            "direcionado": "DEPOIS direcionado (A+B+C1)", "auto": "DEPOIS seleção por impacto"}
    p = [f"# Bench — contrato reverso · {r['consumidor']}\n",
         f"Gerado em {r['gerado_em']} · linha de base repetida {r['repeticoes_linha_de_base']}× "
         f"(estável: {r['aceite']['estavel_em_repeticoes']})\n",
         "## Resumo\n", "| proteção | quebras detectadas | contrato | gateway | implementação | falsos positivos | "
         "tempo mediano (s) | p90 (s) |", "|---|---|---|---|---|---|---|---|"]
    for col in cols:
        s = r["resumo"][col]
        p.append(f"| {nome.get(col, col)} | {s['detectadas']}/{s['total_quebras']} | {s['por_alvo']['contrato']} | "
                 f"{s['por_alvo']['gateway']} | {s['por_alvo']['implementacao']} | "
                 f"{s['falsos_positivos']}/{s['total_compativeis']} | {s['tempo_mediano_s']} | {s['tempo_p90_s']} |")
    p += ["", "## Critérios de aceite\n"] + [f"- {'✅' if v else '❌'} {k}" for k, v in r["aceite"].items()]
    p += ["", "## Linha de base (sem mutação)\n"]
    for k, v in r["tempos_linha_de_base_s"].items():
        p.append(f"- {nome.get(k, k)}: mediana {v['mediana']} s · p90 {v['p90']} s · amostras {v['amostras']}")
    for n, ks in r["quebras_da_linha_de_base"].items():
        p.append(f"- quebras já presentes ({n}, não contam como detecção): {', '.join(ks) or 'nenhuma'}")
    p += ["", "## Por mutação\n", "| mutação | origem | tipo | alvo | " + " | ".join(nome.get(col, col) for col in cols) + " |",
          "|---|---|---|---|" + "---|" * len(cols)]
    for l in r["mutacoes"]:
        if "erro" in l:
            p.append(f"| `{l['id']}` — {l['descricao']} | {l['origem']} | {l['tipo']} | {l['alvo']} | ERRO: {l['erro']} |")
            continue
        cel = []
        for col in cols:
            if col not in l:
                cel.append("—")
                continue
            ok = l[col]["detectou"]
            marca = ("✅" if ok else "❌") if l["tipo"] == "quebra" else ("⚠️ FP" if ok else "✅")
            cel.append(f"{marca} {l[col]['s']}s" + (f" {l[col]['nivel']}" if col == "auto" else ""))
        p.append(f"| `{l['id']}` — {l['descricao']} | {l['origem']} | {l['tipo']} | {l['alvo']} | " + " | ".join(cel) + " |")
    return "\n".join(p) + "\n"
