# -*- coding: utf-8 -*-
"""`cr.py iniciar` — prepara um projeto NOVO para testes reversos.

1. Detecta o contrato publicado (OpenAPI) e o Gateway (template SAM com HttpApi).
2. Gera `contracts/consumidores/<api>/<consumidor>.cdc.yaml` em RASCUNHO: uma interação por
   operação, jornada ordenada (POST → GET → PATCH/PUT → DELETE) com capturas de id.
   Toda origem nasce `openapi-exemplo` (mesma fonte do provedor) e o arquivo traz `rascunho: true`:
   enquanto não for revisado contra o consumidor real, o veredito é no máximo INCONCLUSIVO.
3. Stack Java/Maven: copia o verificador C1 (JUnit) para o pacote do handler e lista as
   dependências de teste que faltam no pom (não edita o pom — decisão do projeto).
4. Gera `mutacoes.yaml` vazio e diz os próximos passos.
"""
from __future__ import annotations

import re
from pathlib import Path

from .modelo import ler_yaml
from .openapi import OpenApi

IGNORAR = {"target", "node_modules", ".git", "build", ".gradle", ".contrato-reverso", "__pycache__", ".venv", "venv"}
TEMPLATE_JAVA = Path(__file__).resolve().parents[2] / "templates" / "java-junit" / "ConsumerContractVerificationTest.java.tmpl"
DEPS_JAVA = {"aws-lambda-java-events": "com.amazonaws:aws-lambda-java-events",
             "aws-lambda-java-core": "com.amazonaws:aws-lambda-java-core",
             "jackson-databind": "com.fasterxml.jackson.core:jackson-databind",
             "junit-jupiter": "org.junit.jupiter:junit-jupiter (test)",
             "assertj-core": "org.assertj:assertj-core (test)"}
_CORPO_V2_ADAPTE = ('        throw new UnsupportedOperationException(\n'
                    '            "ADAPTE criarHandler(): devolva __CLASSE_HANDLER__ montado com dublês (veja o README da skill contrato-reverso)");\n')
ORDEM = {"POST": 0, "GET": 1, "PUT": 2, "PATCH": 2, "DELETE": 3}


def _arquivos(raiz: Path, padrao: re.Pattern) -> list[Path]:
    achados = []
    for p in raiz.rglob("*"):
        if any(parte in IGNORAR for parte in p.relative_to(raiz).parts):
            continue
        if p.is_file() and padrao.search(p.name):
            achados.append(p)
    preferidos = {"template.yaml", "template.yml", "openapi.yaml", "openapi.yml", "openapi.json"}
    return sorted(achados, key=lambda p: (len(p.parts), p.name.lower() not in preferidos, str(p)))


def _detectar_gateway(raiz: Path):
    """Primeiro Gateway legível: SAM (HTTP/REST) > CloudFormation/CDK (cdk.out) > Terraform. (caminho, modelo)"""
    from .gateway import carregar
    candidatos: list[Path] = []
    candidatos += _arquivos(raiz, re.compile(r"^template.*\.ya?ml$", re.I))
    candidatos += sorted({p.parent for p in _arquivos(raiz, re.compile(r"\.template\.json$", re.I))})
    candidatos += sorted({p.parent for p in _arquivos(raiz, re.compile(r"\.tf$", re.I))})
    for c in candidatos:
        try:
            modelo = carregar(c)
        except Exception:  # noqa: BLE001 - arquivo que não é Gateway (ou malformado): tenta o próximo
            continue
        if modelo.rotas:
            return c, modelo
    return None


def _stack(prov_raiz: Path, handler: str) -> str:
    if (prov_raiz / "pom.xml").is_file() or (prov_raiz / "build.gradle").is_file() or "::" in handler:
        return "java"
    if (prov_raiz / "package.json").is_file() or any((prov_raiz / (handler.rsplit(".", 1)[0] + ext)).is_file()
                                                     for ext in (".mjs", ".js", ".cjs")):
        return "node"
    if (prov_raiz / "pyproject.toml").is_file() or (prov_raiz / "requirements.txt").is_file() or list(prov_raiz.rglob("*.py")):
        return "python"
    return "desconhecido"


def _campos(oas: OpenApi, esquema: dict, profundidade: int = 0) -> dict:
    saida = {}
    obrig = set(esquema.get("required") or [])
    for nome, prop in (esquema.get("properties") or {}).items():
        prop = oas.esquema(prop)
        t = prop.get("type")
        tipos = t if isinstance(t, list) else [t]
        base = next((x for x in tipos if x and x != "null"), None)
        exp: dict = {}
        if base:
            exp["tipo"] = base
        if nome not in obrig:
            exp["presenca"] = "opcional"
        if "null" in tipos or prop.get("nullable"):
            exp["nulo"] = True
        if isinstance(prop.get("enum"), list):
            exp["enum"] = [v for v in prop["enum"] if v is not None]
        if prop.get("format") == "date-time":
            exp["formato"] = "date-time"
        if base == "array" and profundidade == 0:
            itens = oas.esquema(prop.get("items"))
            if itens.get("properties"):
                exp["itens"] = _campos(oas, itens, 1)
        saida[nome] = exp
    return saida


def _code_uri(tpl: Path | None, funcao: str | None) -> str | None:
    if not tpl or tpl.is_dir() or not funcao:
        return None
    try:
        props = ((ler_yaml(tpl) or {}).get("Resources") or {}).get(funcao, {}).get("Properties") or {}
        return str(props.get("CodeUri", ".")).rstrip("/") or "."
    except Exception:  # noqa: BLE001
        return None


def _amostra(oas: OpenApi, prop: dict):
    """Valor de exemplo válido pelo schema (o consumidor real substitui na revisão)."""
    prop = oas.esquema(prop)
    if isinstance(prop.get("enum"), list) and prop["enum"]:
        return next(v for v in prop["enum"] if v is not None)
    if "example" in prop:
        return prop["example"]
    t = prop.get("type")
    t = next((x for x in (t if isinstance(t, list) else [t]) if x and x != "null"), "string")
    if t == "integer":
        return max(int(prop.get("minimum", 1)), 1)
    if t == "number":
        return 1.0
    if t == "boolean":
        return True
    if prop.get("format") == "date-time":
        return "2030-01-01T10:00:00Z"
    return "exemplo"


def _yaml_inline(valor) -> str:
    import json
    return json.dumps(valor, ensure_ascii=False)


def _rel(raiz: Path, p: Path) -> str:
    return str(p.relative_to(raiz)).replace("\\", "/")


def _oas_das_rotas(gw) -> OpenApi:
    """Sem contrato publicado: paths sintéticos a partir das ROTAS do Gateway (sem campos)."""
    paths: dict = {}
    for r in gw.rotas:
        if r.caminho == "$default" or "+}" in r.caminho or r.metodo == "ANY":
            continue
        paths.setdefault(r.caminho, {})[r.metodo.lower()] = {
            "responses": {"201" if r.metodo == "POST" else ("204" if r.metodo == "DELETE" else "200"): {"description": "ADAPTE"}},
            **({"security": [{"auth": []}]} if r.autorizador else {"security": []})}
    return OpenApi({"info": {"title": gw.api}, "paths": paths})


def _carregar_oas(raiz: Path, oas_arqs: list[Path], detectado):
    """(oas, oas_arq|None, fonte_ref) — OpenAPI publicado, ou derivado das rotas do Gateway."""
    if oas_arqs:
        oas_arq = oas_arqs[0]
        if len(oas_arqs) > 1:
            print(f"  ⚠ {len(oas_arqs)} OpenAPI encontrados; usando {oas_arq.relative_to(raiz)} (rode por API com --raiz)")
        return OpenApi(ler_yaml(oas_arq)), oas_arq, _rel(raiz, oas_arq)
    # as interações saem das ROTAS do Gateway (sem campos) — e a camada A vai registrar o risco
    fonte_ref = f"rota do Gateway ({_rel(raiz, detectado[0]) or '.'}) — SEM OpenAPI"
    print("  ⚠ nenhum OpenAPI: interações derivadas das rotas do Gateway, sem campos — publique o contrato")
    return _oas_das_rotas(detectado[1]), None, fonte_ref


def _provedor(raiz: Path, detectado, oas_arq: Path | None):
    """(tpl, api, funcao, handler, gw, prov_raiz) — descreve o provedor e imprime o que achou."""
    if not detectado:
        prov_raiz = oas_arq.parent.parent if oas_arq.parent.name == "openapi" else oas_arq.parent  # type: ignore[union-attr]
        print("  ⚠ nenhum Gateway legível (SAM, CloudFormation/CDK synth, Terraform): camada B ficará NÃO executada")
        return None, None, None, None, None, prov_raiz
    tpl, gw = detectado
    rota0 = next((r for r in gw.rotas if r.handler), gw.rotas[0])
    api, funcao, handler = gw.api, rota0.funcao, rota0.handler
    prov_raiz = tpl if tpl.is_dir() else tpl.parent
    if prov_raiz.name in ("cdk.out", "terraform", "infra", "iac") and prov_raiz != raiz:
        prov_raiz = prov_raiz.parent
    print(f"  ✓ Gateway {gw.fonte} ({gw.tipo_api.upper()} API): {_rel(raiz, tpl)} · API {api} · função {funcao} · handler {handler or '?'}")
    for pend in gw.pendencias:
        print(f"    ⚠ não resolvido estaticamente: {pend}")
    return tpl, api, funcao, handler, gw, prov_raiz


def _bloco_interacao(oas: OpenApi, op, caminho: str, oas_arq: Path | None, fonte_ref: str, capturas: dict[str, str]) -> str:
    """Um bloco YAML de interação; registra em `capturas` o id que um POST de criação devolve."""
    sucesso = sorted(s for s in oas.respostas(op) if s[:1] == "2") or ["200"]
    status = int(sucesso[0]) if sucesso[0].isdigit() else 200
    resp = oas.resposta_para(op, status) or {}
    conteudo = resp.get("content") or {}
    ct = next(iter(conteudo), None)
    esquema = oas.esquema((conteudo.get(ct) or {}).get("schema")) if ct else {}
    campos = _campos(oas, esquema) if esquema else {}
    _, corpo_esq = oas.corpo_requisicao(op)
    corpo = ({n: _amostra(oas, (corpo_esq.get("properties") or {}).get(n, {})) for n in (corpo_esq.get("required") or [])}
             if corpo_esq else None)
    captura = ""
    if op.metodo == "POST" and "id" in campos and "{" not in op.caminho:
        var = "id_" + re.sub(r"[^A-Za-z0-9]+", "_", op.caminho.strip("/").split("/")[-1] or "recurso")
        capturas[op.caminho.rstrip("/")] = var
        captura = f"\n    capturar: {{{var}: id}}"
    id_ = f"{op.metodo.lower()}{re.sub(r'[^A-Za-z0-9]+', '-', op.caminho).rstrip('-')}"
    linhas = [f"  - id: {id_}",
              f"    risco: \"ADAPTE: o que quebra para o usuário se {op.metodo} {op.caminho} falhar\"",
              f"    origem: {{tipo: {'openapi-exemplo' if oas_arq else 'hipotese'}, ref: \"{fonte_ref} {op.metodo} {op.caminho} — SUBSTITUA pela fonte do consumidor\"}}",
              "    requisicao:", f"      metodo: {op.metodo}", f"      caminho: \"{caminho}\""]
    if oas.seguranca_exigida(op):
        linhas.append("      token: usuario-a")
    query = {p["name"]: _amostra(oas, p.get("schema") or {}) for p in op.parametros
             if p.get("in") == "query" and p.get("required")}
    if query:
        linhas.append(f"      query: {_yaml_inline(query)}")
    if corpo is not None:
        linhas += ["      headers: {Content-Type: application/json}", f"      corpo: {_yaml_inline(corpo)}"]
    linhas += ["    resposta:", f"      status: {status}"]
    if ct:
        linhas.append(f"      content_type: {ct}")
    if campos:
        linhas.append("      campos:  # PODE: mantenha só o que o consumidor LÊ (tolerant reader)")
        for nome, exp in campos.items():
            linhas.append(f"        {nome}: {_yaml_inline(exp)}")
    elif status == 204:
        linhas.append("      corpo_vazio: true")
    return "\n".join(linhas) + captura


def _blocos_jornada(oas: OpenApi, oas_arq: Path | None, fonte_ref: str) -> list[str]:
    """Interações ordenadas em jornada (POST → GET → PUT/PATCH → DELETE), ids capturados do POST."""
    ops = sorted((o for o in oas.operacoes() if o.metodo != "OPTIONS"),
                 key=lambda o: (ORDEM.get(o.metodo, 9), o.caminho.count("/"), o.caminho))
    capturas: dict[str, str] = {}
    blocos: list[str] = []
    for op in ops:
        caminho = op.caminho
        for param in re.findall(r"{([^}]+)}", caminho):
            base = caminho.split("/{" + param + "}")[0]
            var = capturas.get(base)
            caminho = caminho.replace("{" + param + "}", "{{" + var + "}}" if var else "EXEMPLO-" + param)
        blocos.append(_bloco_interacao(oas, op, caminho, oas_arq, fonte_ref, capturas))
    return blocos


def _verificador_yaml(stack: str, prov_rel: str, obs: str, tpl: Path | None, funcao: str | None) -> str:
    if stack == "java":
        return f"""  verificador_inprocess:
    comando: [mvn, -q, -B, -ntp, test, -Dtest=ConsumerContractVerificationTest, -Dsurefire.failIfNoSpecifiedTests=false]
    cwd: {prov_rel}
    observado: {obs}
  suite_ampliada:
    comando: [mvn, -q, -B, -ntp, test]
    cwd: {prov_rel}
  suite_existente:
    comando: [mvn, -q, -B, -ntp, test, "-Dtest=!ConsumerContractVerificationTest", -Dsurefire.failIfNoSpecifiedTests=false]
    cwd: {prov_rel}
"""
    if stack == "python":
        code_uri = _code_uri(tpl, funcao) or "."
        return f"""  verificador_inprocess:
    runner: python
    fabrica: cdc_fabrica:criar_handler
    pythonpath: [{code_uri}, tests]
    cwd: {prov_rel}
    persistencia: "ADAPTE: descreva os dublês da fábrica"
  suite_existente:
    comando: [python, -m, pytest, -q]
    cwd: {prov_rel}
"""
    if stack == "node":
        return f"""  verificador_inprocess:
    runner: node
    fabrica: "test/cdc-fabrica.mjs#criarHandler"
    cwd: {prov_rel}
    persistencia: "ADAPTE: descreva os dublês da fábrica"
  suite_existente:
    comando: [npm, test, --silent]
    cwd: {prov_rel}
"""
    return "  # verificador_inprocess: stack não reconhecido — declare comando/runner à mão\n"


def _texto_contrato(consumidor: str, tipo: str, origem: str, nome_api: str, prov_rel: str, openapi_rel: str | None,
                    gateway: str, verificador: str, blocos: list[str]) -> str:
    return f"""# Contrato dirigido pelo consumidor — RASCUNHO gerado por `cr.py iniciar`.
# Próximo passo obrigatório: substituir cada expectativa pela do CONSUMIDOR REAL (código do
# cliente, SDK, testes, exemplos aprovados) e trocar `origem`. Derivar tudo do OpenAPI reproduz
# o erro que ele compartilhe com a implementação. Remova `rascunho: true` só depois da revisão.
versao_formato: 1
rascunho: true

consumidor:
  nome: {consumidor}
  tipo: {tipo}
{f"  origem_navegador: {origem}" if tipo == "navegador" else "  # origem_navegador: https://... (se navegador)"}
  hipotetico: true
  acesso_ao_codigo: false
  trata_genericamente: ["5xx"]
  leitor:
    ignora_campos_desconhecidos: true
    enums_fechados: []        # campos com switch exaustivo no consumidor (valor novo QUEBRA)
  limitacao: >-
    Rascunho derivado do OpenAPI do provedor (mesma fonte): ainda não reflete o consumidor real.

provedor:
  nome: {nome_api}
  raiz: {prov_rel}
{f"  openapi: {openapi_rel}" if openapi_rel else "  # openapi: (o provedor não publica — a camada A registra o risco)"}
{gateway}{verificador}
ambientes:
  local:
    url_base_padrao: "http://127.0.0.1:3000"
    producao: false

identidades: [usuario-a, usuario-b]

interacoes:
""" + "\n\n".join(blocos) + "\n"


def _escrever_verificador_java(raiz: Path, prov_raiz: Path, handler: str | None, gw, sobrescrever: bool) -> None:
    pacote, classe = (handler.split("::")[0].rsplit(".", 1) + [""])[:2] if handler and "." in handler else ("", "")
    if not pacote:
        print("  ⚠ handler Java não identificado no SAM: copie o template manualmente "
              f"({TEMPLATE_JAVA.relative_to(TEMPLATE_JAVA.parents[3])})")
    else:
        destino = prov_raiz / "src" / "test" / "java" / Path(*pacote.split(".")) / "ConsumerContractVerificationTest.java"
        if destino.exists() and not sobrescrever:
            print(f"  = verificador C1 já existe: {_rel(raiz, destino)}")
        else:
            destino.parent.mkdir(parents=True, exist_ok=True)
            fonte = TEMPLATE_JAVA.read_text(encoding="utf-8")
            if gw is not None and gw.tipo_api == "rest":  # REST API (payload 1.0): a adaptação vai no V1
                v1_nulo = ("    private static RequestHandler<APIGatewayProxyRequestEvent, APIGatewayProxyResponseEvent> "
                           "criarHandlerV1() {\n        return null;\n")
                assert _CORPO_V2_ADAPTE in fonte and v1_nulo in fonte, "template Java mudou: ajuste iniciar.py"
                fonte = fonte.replace(_CORPO_V2_ADAPTE, "        return null;\n").replace(
                    v1_nulo, v1_nulo.replace("        return null;\n", _CORPO_V2_ADAPTE))
            fonte = fonte.replace("__PACOTE__", pacote).replace("__IMPORT_HANDLER__", "").replace("__CLASSE_HANDLER__", classe)
            destino.write_text(fonte, encoding="utf-8")
            print(f"  ✓ verificador C1 (JUnit): {_rel(raiz, destino)} — edite só o bloco ADAPTAÇÃO DO PROJETO")
    pom_txt = (prov_raiz / "pom.xml").read_text(encoding="utf-8")
    faltam = [coord for art, coord in DEPS_JAVA.items() if f"<artifactId>{art}</artifactId>" not in pom_txt]
    if faltam:
        print(f"  ⚠ dependências que o verificador usa e o pom não declara: {faltam}")


def _escrever_fabrica_python(raiz: Path, prov_raiz: Path, handler: str | None) -> None:
    fab = prov_raiz / "tests" / "cdc_fabrica.py"
    if fab.exists():
        return
    fab.parent.mkdir(parents=True, exist_ok=True)
    fab.write_text('''"""Fábrica do verificador C1 (skill contrato-reverso) — o ÚNICO arquivo a adaptar.

Devolva o handler REAL do Lambda montado com dublês nas portas de saída (repositórios em memória,
fila falsa, relógio fixo). Nunca nuvem. Handler original: {handler}
"""


def criar_handler():
    raise NotImplementedError("ADAPTE criarHandler: monte o handler real com dublês nas portas de saída")
'''.replace("{handler}", handler or "?"), encoding="utf-8")
    print(f"  ✓ fábrica C1 (Python): {_rel(raiz, fab)} — adapte criar_handler()")


def _escrever_fabrica_node(raiz: Path, prov_raiz: Path, handler: str | None) -> None:
    fab = prov_raiz / "test" / "cdc-fabrica.mjs"
    if fab.exists():
        return
    fab.parent.mkdir(parents=True, exist_ok=True)
    fab.write_text(f"""// Fábrica do verificador C1 (skill contrato-reverso) — o ÚNICO arquivo a adaptar.
// Devolva o handler REAL do Lambda montado com dublês (repositório em memória, relógio fixo). Nunca nuvem.
// Handler original: {handler or '?'}
export function criarHandler() {{
  throw new Error("ADAPTE criarHandler: monte o handler real com dublês nas portas de saída");
}}
""", encoding="utf-8")
    print(f"  ✓ fábrica C1 (Node): {_rel(raiz, fab)} — adapte criarHandler()")


_PROXIMOS_PASSOS = """
Próximos passos (skill contrato-reverso, fase CODIFICAR):
  1. Revise o contrato contra o consumidor real: troque origem/risco, pode campos que ele não lê,
     marque enums_fechados, ajuste a jornada; então remova `rascunho: true`.
  2. Adapte criarHandler() do verificador C1 (dublês nas portas de saída).
  3. cr.py verificar --nivel rapido  →  --nivel direcionado  →  cr.py bench
  4. Adicione `.contrato-reverso/` ao .gitignore."""


def iniciar(raiz: Path, consumidor: str = "consumidor-principal", tipo: str = "servico", origem: str = "",
            sobrescrever: bool = False) -> int:
    print(f"🔎 projeto: {raiz}")
    oas_arqs = _arquivos(raiz, re.compile(r"(openapi|swagger).*\.(ya?ml|json)$", re.I))
    detectado = _detectar_gateway(raiz)
    if not oas_arqs and not detectado:
        print("✗ nem OpenAPI nem Gateway legível. Contrato primeiro: escreva o OpenAPI (ou o contrato do consumidor à "
              "mão a partir do código do cliente) e rode de novo.")
        return 2
    oas, oas_arq, fonte_ref = _carregar_oas(raiz, oas_arqs, detectado)
    nome_api = re.sub(r"[^a-z0-9]+", "-", str((oas.doc.get("info") or {}).get("title", "api")).lower()).strip("-") or "api"
    tpl, api, funcao, handler, gw, prov_raiz = _provedor(raiz, detectado, oas_arq)
    stack = _stack(prov_raiz, handler or "")
    print(f"  ✓ stack do provedor: {stack}")

    blocos = _blocos_jornada(oas, oas_arq, fonte_ref)

    pasta = raiz / "contracts" / "consumidores" / nome_api
    pasta.mkdir(parents=True, exist_ok=True)
    arq = pasta / f"{consumidor}.cdc.yaml"
    if arq.exists() and not sobrescrever:
        print(f"✗ {_rel(raiz, arq)} já existe (use --sobrescrever)")
        return 1
    prov_rel = _rel(raiz, prov_raiz) or "."
    obs = f"{prov_rel}/target/contrato-reverso/observado-{consumidor}.json" if prov_rel != "." else \
        f"target/contrato-reverso/observado-{consumidor}.json"
    gateway = (f"  gateway: {{template: {_rel(raiz, tpl) or '.'}, recurso_api: {api}, funcao: {funcao}}}\n"
               if tpl else "  # gateway: {template: ..., recurso_api: ..., funcao: ...}\n")
    texto = _texto_contrato(consumidor, tipo, origem, nome_api, prov_rel, _rel(raiz, oas_arq) if oas_arq else None,
                            gateway, _verificador_yaml(stack, prov_rel, obs, tpl, funcao), blocos)
    arq.write_text(texto, encoding="utf-8")
    print(f"  ✓ contrato (rascunho): {_rel(raiz, arq)} — {len(blocos)} interações")
    mut = pasta / "mutacoes.yaml"
    if not mut.exists():
        mut.write_text("# Mutações do projeto para `cr.py bench` (as de OpenAPI/Gateway são automáticas).\n"
                       "# - {id: ..., tipo: quebra|compativel, alvo: implementacao, arquivo: ..., descricao: ...,\n"
                       "#    trocas: [{ancora: ..., antigo: ..., novo: ...}]}\nmutacoes: []\n", encoding="utf-8")

    if stack == "java":
        _escrever_verificador_java(raiz, prov_raiz, handler, gw, sobrescrever)
    elif stack == "python":
        _escrever_fabrica_python(raiz, prov_raiz, handler)
    elif stack == "node":
        _escrever_fabrica_node(raiz, prov_raiz, handler)
    print(_PROXIMOS_PASSOS)
    return 0
