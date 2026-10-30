# -*- coding: utf-8 -*-
"""Modelo NORMALIZADO do API Gateway + leitores (SAM HTTP/REST, CloudFormation/CDK, Terraform).

Todos os formatos viram o mesmo `ModeloGateway`; a camada B, o simulador (C1 Python/Node) e o
verificador Java (via JSON) só conhecem o modelo — nunca o formato de origem.

| fonte              | como é lido                                                              |
|--------------------|--------------------------------------------------------------------------|
| sam (HttpApi/Api)  | template.yaml; `!Ref` a Parameters resolvido pelo Default                |
| cloudformation     | template CFN puro ou saída do `cdk synth` (cdk.out/*.template.json)      |
| terraform-json     | `terraform show -json <plan>` (valores calculados, exato)                |
| terraform-hcl      | *.tf estático: literais e `var.x` com default; expressões → pendente     |
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import hcl
from .modelo import DependenciaAusente, ler_yaml
from .openapi import regex_template

RESPOSTAS_GATEWAY = {
    # (status, content-type, corpo) que o Gateway devolve SEM chamar o backend
    "http": {"sem_rota": (404, "application/json", '{"message":"Not Found"}'),
             "nao_autorizado": (401, "application/json", '{"message":"Unauthorized"}'),
             "proibido": (403, "application/json", '{"message":"Forbidden"}'),
             "timeout_integracao_s": 30},
    "rest": {"sem_rota": (403, "application/json", '{"message":"Missing Authentication Token"}'),
             "nao_autorizado": (401, "application/json", '{"message":"Unauthorized"}'),
             "proibido": (403, "application/json", '{"message":"Forbidden"}'),
             "timeout_integracao_s": 29},
}


@dataclass
class Rota:
    metodo: str                 # GET | ... | ANY
    caminho: str                # /tasks/{taskId} | /{proxy+} | $default
    funcao: str = ""
    handler: str = ""
    autorizador: str | None = None
    payload: str = "2.0"
    timeout_funcao_s: float | None = None
    inferido: bool = False      # algum campo veio de expressão não resolvida (HCL)

    def casa(self, metodo: str, caminho_concreto: str) -> bool:
        if self.caminho == "$default":
            return True
        if self.metodo not in ("ANY", metodo):
            return False
        return re.fullmatch(regex_template(self.caminho), caminho_concreto.split("?")[0]) is not None

    @property
    def assinatura(self) -> str:
        return f"{self.metodo} {re.sub(r'{[^}]+}', '{}', self.caminho)}"


@dataclass
class ModeloGateway:
    api: str
    tipo_api: str = "http"                    # http (HTTP API v2) | rest (REST API v1)
    fonte: str = "sam"
    estagio: str = "$default"
    autorizador_padrao: str | None = None
    tipos_autorizador: dict = field(default_factory=dict)   # nome -> jwt | cognito | lambda | iam
    cors: dict | None = None                  # HTTP API: global {AllowOrigins, AllowMethods, AllowHeaders, AllowCredentials}
    cors_por_caminho: dict = field(default_factory=dict)    # REST API: caminho -> cors (OPTIONS mock)
    throttling: dict = field(default_factory=dict)
    rotas: list[Rota] = field(default_factory=list)
    pendencias: list[str] = field(default_factory=list)     # o que o leitor não conseguiu resolver

    def rota_para(self, metodo: str, caminho: str) -> Rota | None:
        candidatas = [r for r in self.rotas if r.casa(metodo, caminho)]
        if not candidatas:
            return None
        return sorted(candidatas, key=lambda r: (r.caminho == "$default", "+}" in r.caminho, r.metodo == "ANY",
                                                  r.caminho.count("{")))[0]

    def cors_para(self, caminho: str) -> dict | None:
        if self.tipo_api == "http":
            return self.cors
        for tpl, cfg in self.cors_por_caminho.items():
            if re.fullmatch(regex_template(tpl), caminho.split("?")[0]):
                return cfg
        return self.cors

    def tem_cors(self) -> bool:
        return bool(self.cors) or bool(self.cors_por_caminho)

    @property
    def respostas(self) -> dict:
        return RESPOSTAS_GATEWAY[self.tipo_api]

    def autenticada(self, rota: Rota) -> bool:
        return bool(rota.autorizador)

    def para_dict(self) -> dict:
        d = asdict(self)
        d["respostas"] = {k: (list(v) if isinstance(v, tuple) else v) for k, v in self.respostas.items()}
        return d


# =============================================================================== utilitários
def _lista(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v]
    return [x.strip() for x in str(v).split(",") if x.strip()]


def _cors_normalizado(origens, metodos, headers, credenciais=False, max_age=None) -> dict:
    tirar_aspas = lambda xs: [x.strip().strip("'").strip() for x in xs]  # noqa: E731 - SAM REST usa "'*'"
    return {"AllowOrigins": tirar_aspas(_lista(origens)), "AllowMethods": [m.upper() for m in tirar_aspas(_lista(metodos))],
            "AllowHeaders": [h.lower() for h in tirar_aspas(_lista(headers))], "AllowCredentials": bool(credenciais),
            "MaxAge": max_age}


def _ref(v) -> str | None:
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        if "Ref" in v:
            return str(v["Ref"])
        if "Fn::GetAtt" in v:
            g = v["Fn::GetAtt"]
            return str(g[0] if isinstance(g, list) else str(g).split(".")[0])
    return None


def _texto_cfn(v) -> str:
    """Fn::Sub / Fn::Join achatados para busca de referências."""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        if "Fn::Sub" in v:
            s = v["Fn::Sub"]
            return s if isinstance(s, str) else str(s[0])
        if "Fn::Join" in v:
            sep, partes = v["Fn::Join"]
            return sep.join(_texto_cfn(p) if not isinstance(p, dict) else "${" + (_ref(p) or "") + "}" for p in partes)
        r = _ref(v)
        return "${" + r + "}" if r else json.dumps(v)
    return str(v)


# =============================================================================== detecção
def detectar(caminho: Path) -> str:
    if caminho.is_dir():
        if list(caminho.glob("*.tf")):
            return "terraform-hcl"
        if list(caminho.glob("*.template.json")):
            return "cloudformation"
        raise DependenciaAusente(f"não sei ler o Gateway em {caminho} (esperava *.tf ou cdk.out)")
    nome = caminho.name.lower()
    if nome.endswith(".tf"):
        return "terraform-hcl"
    if nome.endswith(".json"):
        texto = caminho.read_text(encoding="utf-8")
        if '"planned_values"' in texto or '"format_version"' in texto and '"values"' in texto:
            return "terraform-json"
        return "cloudformation" if '"Transform"' not in texto else "sam"
    texto = caminho.read_text(encoding="utf-8")
    return "sam" if "AWS::Serverless" in texto else "cloudformation"


def carregar(caminho: Path, recurso_api: str | None = None, tipo: str | None = None) -> ModeloGateway:
    if not caminho.exists():
        raise DependenciaAusente(f"template do Gateway não encontrado: {caminho}")
    tipo = tipo if tipo and tipo not in ("sam-http-api", "sam-rest-api") else detectar(caminho)
    if tipo == "sam":
        return ler_sam(ler_yaml(caminho) or {}, recurso_api)
    if tipo == "cloudformation":
        if caminho.is_dir():
            docs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(caminho.glob("*.template.json"))]
            doc = {"Resources": {k: v for d in docs for k, v in (d.get("Resources") or {}).items()},
                   "Parameters": {k: v for d in docs for k, v in (d.get("Parameters") or {}).items()}}
        else:
            doc = json.loads(caminho.read_text(encoding="utf-8")) if caminho.suffix == ".json" else (ler_yaml(caminho) or {})
        return ler_cloudformation(doc, recurso_api)
    if tipo == "terraform-json":
        return ler_terraform_json(json.loads(caminho.read_text(encoding="utf-8")), recurso_api)
    if tipo == "terraform-hcl":
        arquivos = sorted(caminho.glob("*.tf")) if caminho.is_dir() else [caminho]
        return ler_terraform_hcl("\n".join(p.read_text(encoding="utf-8") for p in arquivos), recurso_api)
    raise DependenciaAusente(f"tipo de Gateway desconhecido: {tipo}")


# =============================================================================== SAM
def ler_sam(doc: dict, recurso_api: str | None) -> ModeloGateway:
    recursos = doc.get("Resources") or {}
    globais = doc.get("Globals") or {}
    params = doc.get("Parameters") or {}

    def resolver(v):
        nome = _ref(v) if isinstance(v, (str, dict)) else None
        if nome in params:
            d = params[nome].get("Default")
            return _lista(d) if params[nome].get("Type") == "CommaDelimitedList" else d
        return v

    timeout_global = float((globais.get("Function") or {}).get("Timeout", 3))
    tem_http = any((r or {}).get("Type") == "AWS::Serverless::HttpApi" for r in recursos.values())
    tem_rest = any((r or {}).get("Type") == "AWS::Serverless::Api" for r in recursos.values())
    eventos_http = eventos_rest = False
    for r in recursos.values():
        for ev in (((r or {}).get("Properties") or {}).get("Events") or {}).values():
            eventos_http |= (ev or {}).get("Type") == "HttpApi"
            eventos_rest |= (ev or {}).get("Type") == "Api"
    if recurso_api and recurso_api in recursos:
        rest = recursos[recurso_api].get("Type") == "AWS::Serverless::Api"
    else:
        rest = (tem_rest or eventos_rest) and not (tem_http or eventos_http)
    tipo_evento = "Api" if rest else "HttpApi"
    api_nome = recurso_api or next((n for n, r in recursos.items() if (r or {}).get("Type") ==
                                    ("AWS::Serverless::Api" if rest else "AWS::Serverless::HttpApi")),
                                   "ServerlessRestApi" if rest else "ServerlessHttpApi")
    props = {**(globais.get("Api" if rest else "HttpApi") or {}),
             **(((recursos.get(api_nome) or {}).get("Properties")) or {})}
    auth = props.get("Auth") or {}
    tipos = {}
    for nome, cfg in (auth.get("Authorizers") or {}).items():
        cfg = cfg or {}
        tipos[nome] = ("jwt" if "JwtConfiguration" in cfg else "cognito" if "UserPoolArn" in cfg
                       else "lambda" if "FunctionArn" in cfg else "outro")
    if auth.get("EnableIamAuthorizer") or auth.get("DefaultAuthorizer") == "AWS_IAM":
        tipos["AWS_IAM"] = "iam"
    padrao = auth.get("DefaultAuthorizer")
    modelo = ModeloGateway(api=api_nome, tipo_api="rest" if rest else "http", fonte="sam",
                           estagio=str(props.get("StageName", "Prod" if rest else "$default")),
                           autorizador_padrao=padrao, tipos_autorizador=tipos)
    if rest:
        cors = props.get("Cors")
        if isinstance(cors, str):
            modelo.cors = _cors_normalizado(resolver(cors), "GET,POST,PUT,PATCH,DELETE,OPTIONS", "content-type,authorization")
        elif isinstance(cors, dict):
            modelo.cors = _cors_normalizado(resolver(cors.get("AllowOrigin")), resolver(cors.get("AllowMethods", "'*'")),
                                            resolver(cors.get("AllowHeaders", "''")), cors.get("AllowCredentials"),
                                            cors.get("MaxAge"))
        for ms in props.get("MethodSettings") or []:
            for k in ("ThrottlingBurstLimit", "ThrottlingRateLimit"):
                if k in (ms or {}):
                    modelo.throttling[k] = ms[k]
    else:
        cors = props.get("CorsConfiguration")
        if cors is True:
            modelo.cors = _cors_normalizado("*", "*", "*")
        elif isinstance(cors, dict):
            modelo.cors = _cors_normalizado(resolver(cors.get("AllowOrigins")), resolver(cors.get("AllowMethods")),
                                            resolver(cors.get("AllowHeaders")), cors.get("AllowCredentials"),
                                            cors.get("MaxAge"))
        rr = props.get("DefaultRouteSettings") or {}
        modelo.throttling = {k: rr[k] for k in ("ThrottlingBurstLimit", "ThrottlingRateLimit") if k in rr}
    for nome, recurso in recursos.items():
        if (recurso or {}).get("Type") != "AWS::Serverless::Function":
            continue
        fp = recurso.get("Properties") or {}
        timeout = float(fp.get("Timeout", timeout_global))
        for evento in (fp.get("Events") or {}).values():
            if (evento or {}).get("Type") != tipo_evento:
                continue
            ep = evento.get("Properties") or {}
            api_ev = _ref(ep.get("RestApiId" if rest else "ApiId")) or ("ServerlessRestApi" if rest else "ServerlessHttpApi")
            if api_ev != api_nome:
                continue
            aut = (ep.get("Auth") or {}).get("Authorizer", padrao)
            metodo = str(ep.get("Method", "ANY")).upper()
            modelo.rotas.append(Rota(metodo="ANY" if metodo in ("ANY", "X-AMAZON-APIGATEWAY-ANY-METHOD") else metodo,
                                     caminho=str(ep.get("Path", "$default")), funcao=nome,
                                     handler=str(fp.get("Handler", "")), autorizador=None if aut == "NONE" else aut,
                                     payload="1.0" if rest else str(ep.get("PayloadFormatVersion", "2.0")),
                                     timeout_funcao_s=timeout))
    return modelo


# =============================================================================== CloudFormation / CDK
def ler_cloudformation(doc: dict, recurso_api: str | None) -> ModeloGateway:
    rec = doc.get("Resources") or {}
    params = doc.get("Parameters") or {}
    por_tipo = lambda t: {n: (r.get("Properties") or {}) for n, r in rec.items() if (r or {}).get("Type") == t}  # noqa: E731
    apis_v2 = {n: p for n, p in por_tipo("AWS::ApiGatewayV2::Api").items() if p.get("ProtocolType", "HTTP") == "HTTP"}
    apis_v1 = por_tipo("AWS::ApiGateway::RestApi")
    lambdas = por_tipo("AWS::Lambda::Function")

    def resolver(v):
        nome = _ref(v)
        if nome in params:
            d = params[nome].get("Default")
            return _lista(d) if params[nome].get("Type") == "CommaDelimitedList" else d
        return v

    def funcao_de(uri) -> tuple[str, str, float | None]:
        texto = _texto_cfn(uri)
        for nome, p in lambdas.items():
            if "${" + nome in texto or f'"{nome}"' in texto or nome in re.findall(r"\$\{([A-Za-z0-9]+)", texto):
                return nome, str(p.get("Handler", "")), (float(p["Timeout"]) if "Timeout" in p else 3.0)
        return "", "", None

    if (recurso_api in apis_v1) or (not recurso_api and apis_v1 and not apis_v2):
        nome_api = recurso_api or next(iter(apis_v1))
        return _ler_cfn_rest(rec, nome_api, por_tipo, funcao_de, resolver)
    if not apis_v2:
        raise DependenciaAusente("nenhum AWS::ApiGatewayV2::Api (HTTP) nem AWS::ApiGateway::RestApi no template")
    nome_api = recurso_api if recurso_api in apis_v2 else next(iter(apis_v2))
    api = apis_v2[nome_api]
    modelo = ModeloGateway(api=nome_api, tipo_api="http", fonte="cloudformation")
    cors = api.get("CorsConfiguration")
    if isinstance(cors, dict):
        modelo.cors = _cors_normalizado(resolver(cors.get("AllowOrigins")), resolver(cors.get("AllowMethods")),
                                        resolver(cors.get("AllowHeaders")), cors.get("AllowCredentials"), cors.get("MaxAge"))
    for n, p in por_tipo("AWS::ApiGatewayV2::Authorizer").items():
        if _ref(p.get("ApiId")) == nome_api:
            modelo.tipos_autorizador[n] = "jwt" if p.get("AuthorizerType") == "JWT" else "lambda"
    for n, p in por_tipo("AWS::ApiGatewayV2::Stage").items():
        if _ref(p.get("ApiId")) == nome_api:
            modelo.estagio = str(p.get("StageName", "$default"))
            rs = p.get("DefaultRouteSettings") or {}
            modelo.throttling = {k: rs[k] for k in ("ThrottlingBurstLimit", "ThrottlingRateLimit") if k in rs}
    integracoes = {n: p for n, p in por_tipo("AWS::ApiGatewayV2::Integration").items() if _ref(p.get("ApiId")) == nome_api}
    for n, p in por_tipo("AWS::ApiGatewayV2::Route").items():
        if _ref(p.get("ApiId")) != nome_api:
            continue
        chave = str(p.get("RouteKey", "$default"))
        metodo, _, caminho = chave.partition(" ")
        if chave == "$default":
            metodo, caminho = "ANY", "$default"
        alvo = _texto_cfn(p.get("Target", ""))
        integ_nome = next((i for i in integracoes if i in alvo), None)
        integ = integracoes.get(integ_nome, {})
        fn, handler, timeout = funcao_de(integ.get("IntegrationUri", ""))
        tipo_aut = str(p.get("AuthorizationType", "NONE"))
        aut = _ref(p.get("AuthorizerId")) if tipo_aut in ("JWT", "CUSTOM") else ("AWS_IAM" if tipo_aut == "AWS_IAM" else None)
        if aut == "AWS_IAM":
            modelo.tipos_autorizador["AWS_IAM"] = "iam"
        modelo.rotas.append(Rota(metodo=metodo.upper(), caminho=caminho or "$default", funcao=fn, handler=handler,
                                 autorizador=aut, payload=str(integ.get("PayloadFormatVersion", "2.0")),
                                 timeout_funcao_s=timeout))
    return modelo


def _ler_cfn_rest(rec, nome_api, por_tipo, funcao_de, resolver) -> ModeloGateway:
    modelo = ModeloGateway(api=nome_api, tipo_api="rest", fonte="cloudformation", estagio="")
    recursos = {n: p for n, p in por_tipo("AWS::ApiGateway::Resource").items() if _ref(p.get("RestApiId")) == nome_api}

    def caminho_de(ref) -> str:
        if not isinstance(ref, str) or ref not in recursos:
            return ""  # raiz (GetAtt RestApi.RootResourceId)
        p = recursos[ref]
        return caminho_de(_ref_pai(p.get("ParentId"))) + "/" + str(p.get("PathPart"))

    def _ref_pai(v):
        if isinstance(v, dict) and "Fn::GetAtt" in v:
            return None
        return _ref(v)

    for n, p in por_tipo("AWS::ApiGateway::Authorizer").items():
        if _ref(p.get("RestApiId")) == nome_api:
            modelo.tipos_autorizador[n] = {"COGNITO_USER_POOLS": "cognito", "TOKEN": "lambda", "REQUEST": "lambda"}.get(
                str(p.get("Type")), "outro")
    for n, p in {**por_tipo("AWS::ApiGateway::Stage"), **por_tipo("AWS::ApiGateway::Deployment")}.items():
        if _ref(p.get("RestApiId")) == nome_api and p.get("StageName"):
            modelo.estagio = str(p["StageName"])
            for ms in p.get("MethodSettings") or []:
                for k_cfn, k in (("ThrottlingBurstLimit", "ThrottlingBurstLimit"), ("ThrottlingRateLimit", "ThrottlingRateLimit")):
                    if k_cfn in (ms or {}):
                        modelo.throttling[k] = ms[k_cfn]
    for n, p in por_tipo("AWS::ApiGateway::Method").items():
        if _ref(p.get("RestApiId")) != nome_api:
            continue
        caminho = caminho_de(_ref_pai(p.get("ResourceId"))) or "/"
        metodo = str(p.get("HttpMethod", "ANY")).upper()
        integ = p.get("Integration") or {}
        if metodo == "OPTIONS" and str(integ.get("Type")) == "MOCK":
            hdrs = {}
            for ir in integ.get("IntegrationResponses") or []:
                for k, v in (ir.get("ResponseParameters") or {}).items():
                    hdrs[k.rsplit(".", 1)[-1].lower()] = resolver(v)
            if "access-control-allow-origin" in hdrs:
                modelo.cors_por_caminho[caminho] = _cors_normalizado(
                    hdrs.get("access-control-allow-origin"), hdrs.get("access-control-allow-methods", ""),
                    hdrs.get("access-control-allow-headers", ""), hdrs.get("access-control-allow-credentials") == "'true'")
            continue
        tipo_aut = str(p.get("AuthorizationType", "NONE"))
        aut = _ref(p.get("AuthorizerId")) if tipo_aut in ("COGNITO_USER_POOLS", "CUSTOM") else (
            "AWS_IAM" if tipo_aut == "AWS_IAM" else None)
        if aut == "AWS_IAM":
            modelo.tipos_autorizador["AWS_IAM"] = "iam"
        fn, handler, timeout = funcao_de(integ.get("Uri", ""))
        modelo.rotas.append(Rota(metodo=metodo, caminho=caminho, funcao=fn, handler=handler, autorizador=aut,
                                 payload="1.0", timeout_funcao_s=timeout))
    return modelo


# =============================================================================== Terraform
def ler_terraform_hcl(texto: str, recurso_api: str | None) -> ModeloGateway:
    blocos = hcl.ler(texto)
    variaveis = {}
    for b in blocos:
        if b.tipo == "variable" and b.rotulos and "default" in b.corpo:
            variaveis[b.rotulos[0]] = b.corpo["default"]
    recursos: dict[str, dict] = {}
    for b in blocos:
        if b.tipo == "resource" and len(b.rotulos) == 2:
            corpo = hcl.resolver_variaveis(b.corpo, variaveis)
            for nome, filhos in b.filhos.items():
                corpo[nome] = [hcl.resolver_variaveis(f.corpo, variaveis) for f in filhos]
            recursos[f"{b.rotulos[0]}.{b.rotulos[1]}"] = corpo
    return _ler_terraform(recursos, recurso_api, fonte="terraform-hcl")


def ler_terraform_json(doc: dict, recurso_api: str | None) -> ModeloGateway:
    """`terraform show -json plan` (planned_values) ou `terraform show -json` do state (values)."""
    raiz = (doc.get("planned_values") or doc.get("values") or {}).get("root_module") or {}
    recursos: dict[str, dict] = {}

    def coletar(mod):
        for r in mod.get("resources") or []:
            vals = dict(r.get("values") or {})
            vals["__id__"] = r.get("address")
            recursos[r["address"]] = vals
        for filho in mod.get("child_modules") or []:
            coletar(filho)
    coletar(raiz)
    # no JSON, referências viram valores calculados (ids conhecidos só após apply) → liga pelo address via configuration
    refs = {}
    for r in ((doc.get("configuration") or {}).get("root_module") or {}).get("resources") or []:
        exprs = r.get("expressions") or {}
        refs[r["address"]] = {k: (v.get("references") or [None])[0] for k, v in exprs.items() if isinstance(v, dict)}
    for addr, mapa in refs.items():
        if addr in recursos:
            for k, ref in mapa.items():
                if ref and (recursos[addr].get(k) in (None, "") or k in ("api_id", "rest_api_id", "resource_id",
                                                                          "parent_id", "authorizer_id", "target",
                                                                          "integration_uri", "uri")):
                    recursos[addr][k] = hcl.Expr(ref)
    return _ler_terraform(recursos, recurso_api, fonte="terraform-json")


def _ref_tf(v) -> str | None:
    if isinstance(v, hcl.Expr):
        return v.referencia()
    if isinstance(v, str):
        m = re.search(r"\$\{\s*([a-z0-9_]+\.[A-Za-z0-9_\-]+)", v)
        if m:
            return m.group(1)
    return None


_THROTTLING_TF = (("throttling_burst_limit", "ThrottlingBurstLimit"), ("throttling_rate_limit", "ThrottlingRateLimit"))


def _ler_terraform(recursos: dict[str, dict], recurso_api: str | None, fonte: str) -> ModeloGateway:
    tipo = lambda t: {a: v for a, v in recursos.items() if a.split(".")[0] == t}  # noqa: E731
    apis_v2 = {a: v for a, v in tipo("aws_apigatewayv2_api").items() if str(v.get("protocol_type", "HTTP")) == "HTTP"}
    apis_v1 = tipo("aws_api_gateway_rest_api")
    rest = (recurso_api in apis_v1) if recurso_api else (bool(apis_v1) and not apis_v2)
    if not apis_v1 and not apis_v2:
        raise DependenciaAusente("nenhum aws_apigatewayv2_api (HTTP) nem aws_api_gateway_rest_api nos arquivos Terraform")
    nome_api = recurso_api if recurso_api else next(iter(apis_v1 if rest else apis_v2))
    funcao_de = _funcao_de_tf(tipo("aws_lambda_function"))
    if rest:
        return _ler_tf_rest(tipo, nome_api, funcao_de, fonte)
    return _ler_tf_http(tipo, nome_api, apis_v2[nome_api], funcao_de, fonte)


def _funcao_de_tf(lambdas: dict[str, dict]):
    """Resolvedor uri → (função, handler, timeout, inferido); `inferido` quando a URI não aponta para uma Lambda conhecida."""
    def funcao_de(uri) -> tuple[str, str, float | None, bool]:
        ref = _ref_tf(uri)
        if ref and ref.startswith("aws_lambda_function.") and ref in lambdas:
            l = lambdas[ref]
            h = l.get("handler")
            return ref, (h if isinstance(h, str) else ""), (float(l["timeout"]) if isinstance(l.get("timeout"), (int, float)) else 3.0), False
        return "", "", None, True
    return funcao_de


def _ler_tf_http(tipo, nome_api: str, api: dict, funcao_de, fonte: str) -> ModeloGateway:
    modelo = ModeloGateway(api=nome_api, tipo_api="http", fonte=fonte)
    cors = (api.get("cors_configuration") or [None])[0]
    if isinstance(cors, dict):
        modelo.cors = _cors_normalizado(_lit(cors.get("allow_origins"), modelo), _lit(cors.get("allow_methods"), modelo),
                                        _lit(cors.get("allow_headers"), modelo), cors.get("allow_credentials") is True,
                                        cors.get("max_age"))
    for a, v in tipo("aws_apigatewayv2_authorizer").items():
        if _ref_tf(v.get("api_id")) == nome_api:
            modelo.tipos_autorizador[a] = "jwt" if v.get("authorizer_type") == "JWT" else "lambda"
    for a, v in tipo("aws_apigatewayv2_stage").items():
        if _ref_tf(v.get("api_id")) == nome_api:
            nome = v.get("name")
            modelo.estagio = nome if isinstance(nome, str) else "?"
            if not isinstance(nome, str):
                modelo.pendencias.append(f"{a}.name não é literal")
            rs = (v.get("default_route_settings") or [{}])[0] or {}
            for k_tf, k in _THROTTLING_TF:
                if rs.get(k_tf) is not None:
                    modelo.throttling[k] = rs[k_tf]
    integracoes = {a: v for a, v in tipo("aws_apigatewayv2_integration").items() if _ref_tf(v.get("api_id")) == nome_api}
    for a, v in tipo("aws_apigatewayv2_route").items():
        if _ref_tf(v.get("api_id")) != nome_api:
            continue
        chave = v.get("route_key")
        if not isinstance(chave, str):
            modelo.pendencias.append(f"{a}.route_key não é literal ({chave})")
            continue
        metodo, _, caminho = chave.partition(" ")
        if chave == "$default":
            metodo, caminho = "ANY", "$default"
        integ = integracoes.get(_ref_tf(v.get("target")) or "", {})
        fn, handler, timeout, inferido = funcao_de(integ.get("integration_uri"))
        tipo_aut = v.get("authorization_type", "NONE")
        aut = _ref_tf(v.get("authorizer_id")) if tipo_aut in ("JWT", "CUSTOM") else ("AWS_IAM" if tipo_aut == "AWS_IAM" else None)
        if aut == "AWS_IAM":
            modelo.tipos_autorizador["AWS_IAM"] = "iam"
        pfv = integ.get("payload_format_version", "2.0")
        modelo.rotas.append(Rota(metodo=metodo.upper(), caminho=caminho, funcao=fn, handler=handler, autorizador=aut,
                                 payload=pfv if isinstance(pfv, str) else "2.0", timeout_funcao_s=timeout,
                                 inferido=inferido))
    return modelo


def _do_api(tipo, t: str, chave_api: str, nome_api: str) -> list[tuple[str, dict]]:
    return [(a, v) for a, v in tipo(t).items() if _ref_tf(v.get(chave_api)) == nome_api]


def _rest_config_api(modelo: ModeloGateway, tipo, nome_api: str) -> None:
    """Autorizadores, estágio e throttling da API REST."""
    for a, v in _do_api(tipo, "aws_api_gateway_authorizer", "rest_api_id", nome_api):
        modelo.tipos_autorizador[a] = {"COGNITO_USER_POOLS": "cognito"}.get(str(v.get("type")), "lambda")
    for a, v in _do_api(tipo, "aws_api_gateway_stage", "rest_api_id", nome_api):
        nome = v.get("stage_name")
        modelo.estagio = nome if isinstance(nome, str) else "?"
    for a, v in _do_api(tipo, "aws_api_gateway_method_settings", "rest_api_id", nome_api):
        s = (v.get("settings") or [{}])[0] or {}
        for k_tf, k in _THROTTLING_TF:
            if s.get(k_tf) is not None:
                modelo.throttling[k] = s[k_tf]


def _rest_caminho_de(modelo: ModeloGateway, recursos_api: dict[str, dict], ref) -> str:
    if not ref or ref not in recursos_api:
        return ""
    v = recursos_api[ref]
    parte = v.get("path_part")
    if not isinstance(parte, str):
        modelo.pendencias.append(f"{ref}.path_part não é literal")
        parte = "{?}"
    return _rest_caminho_de(modelo, recursos_api, _ref_tf(v.get("parent_id"))) + "/" + parte


def _rest_cors_options(modelo: ModeloGateway, caminho: str, respostas: dict) -> None:
    hdrs = {k.rsplit(".", 1)[-1].lower(): val for k, val in respostas.items()}
    if "access-control-allow-origin" in hdrs:
        modelo.cors_por_caminho[caminho] = _cors_normalizado(
            _lit(hdrs.get("access-control-allow-origin"), modelo), _lit(hdrs.get("access-control-allow-methods", ""), modelo),
            _lit(hdrs.get("access-control-allow-headers", ""), modelo))


def _rest_rota(modelo: ModeloGateway, v: dict, caminho: str, metodo: str, integ: dict, funcao_de) -> None:
    tipo_aut = str(v.get("authorization", "NONE"))
    aut = _ref_tf(v.get("authorizer_id")) if tipo_aut in ("COGNITO_USER_POOLS", "CUSTOM") else (
        "AWS_IAM" if tipo_aut == "AWS_IAM" else None)
    if aut == "AWS_IAM":
        modelo.tipos_autorizador["AWS_IAM"] = "iam"
    fn, handler, timeout, inferido = funcao_de(integ.get("uri"))
    modelo.rotas.append(Rota(metodo=metodo, caminho=caminho, funcao=fn, handler=handler, autorizador=aut,
                             payload="1.0", timeout_funcao_s=timeout, inferido=inferido))


def _ler_tf_rest(tipo, nome_api: str, funcao_de, fonte: str) -> ModeloGateway:
    modelo = ModeloGateway(api=nome_api, tipo_api="rest", fonte=fonte, estagio="")
    recursos_api = dict(_do_api(tipo, "aws_api_gateway_resource", "rest_api_id", nome_api))
    _rest_config_api(modelo, tipo, nome_api)
    integracoes = {(_ref_tf(v.get("resource_id")), str(v.get("http_method"))): v
                   for _, v in _do_api(tipo, "aws_api_gateway_integration", "rest_api_id", nome_api)}
    respostas = {_ref_tf(v.get("resource_id")): v.get("response_parameters") or {}
                 for _, v in _do_api(tipo, "aws_api_gateway_integration_response", "rest_api_id", nome_api)}
    for a, v in _do_api(tipo, "aws_api_gateway_method", "rest_api_id", nome_api):
        res_ref = _ref_tf(v.get("resource_id"))
        caminho = _rest_caminho_de(modelo, recursos_api, res_ref) or "/"
        metodo = str(v.get("http_method", "ANY")).upper()
        integ = integracoes.get((res_ref, metodo)) or next((i for (r, m), i in integracoes.items() if r == res_ref
                                                            and _ref_tf(i.get("http_method")) == a), {})
        if metodo == "OPTIONS" and str(integ.get("type")) == "MOCK":
            _rest_cors_options(modelo, caminho, respostas.get(res_ref) or {})
            continue
        _rest_rota(modelo, v, caminho, metodo, integ, funcao_de)
    return modelo


def _lit(v, modelo: ModeloGateway):
    if isinstance(v, hcl.Expr):
        modelo.pendencias.append(f"valor calculado não resolvido estaticamente: {v.texto}")
        return []
    if isinstance(v, list):
        return [x for x in v if not isinstance(x, hcl.Expr)]
    return v
