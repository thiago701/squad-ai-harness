# Gateways e stacks — o que a skill lê e como verifica o provedor

> Tudo converge num **modelo normalizado do Gateway** (`scripts/contrato_reverso/gateway.py`):
> rotas (método, caminho, autorizador, payload 1.0/2.0, função/handler, timeout), CORS (global no
> HTTP API, por caminho no REST API), estágio, throttling e as respostas que o próprio Gateway dá.
> A camada B, o simulador (C1 Python/Node) e o verificador Java leem só esse modelo — por isso o
> mesmo contrato funciona com SAM, CDK ou Terraform. Paridade provada em `exemplos/gateways/`.

## 1. Leitores

| formato | aponte `provedor.gateway.template` para | detecção | observações |
|---|---|---|---|
| SAM HTTP API | `template.yaml` (`AWS::Serverless::HttpApi` / eventos `HttpApi`) | automática | `!Ref` a `Parameters` resolvido pelo `Default`; API implícita `ServerlessHttpApi` |
| SAM REST API (v1) | `template.yaml` (`AWS::Serverless::Api` / eventos `Api`) | automática | `Cors` com valores `"'*'"`; `Auth.Authorizers` Cognito/Lambda; `MethodSettings` |
| CloudFormation / CDK | template CFN (`.json`/`.yaml`) **ou** a pasta `cdk.out` (`*.template.json`) | automática | `AWS::ApiGatewayV2::*` (Route `RouteKey`, Integration, Authorizer, Stage) e `AWS::ApiGateway::*` (árvore de `Resource`, `Method`, OPTIONS `MOCK` = CORS) |
| Terraform plan | `plan.json` de `terraform show -json <plan>` | `planned_values` | **exato**: valores calculados e ligações por `configuration.*.references` |
| Terraform estático | pasta com `*.tf` | `*.tf` | literais e `var.x` com `default`; qualquer expressão vira **pendente** (`B-LEITURA-PARCIAL`) — nunca chute |

Vários APIs no mesmo template: informe `recurso_api` (nome lógico CFN/SAM ou endereço Terraform
`aws_apigatewayv2_api.nome`). Opcional `tipo:` (`sam`, `cloudformation`, `terraform-json`, `terraform-hcl`).

## 2. HTTP API × REST API — o que muda para o consumidor

| | HTTP API (v2) | REST API (v1) |
|---|---|---|
| rota inexistente | **404** `{"message":"Not Found"}` | **403** `{"message":"Missing Authentication Token"}` |
| token ausente/inválido (autorizador) | 401 `{"message":"Unauthorized"}` | 401 `{"message":"Unauthorized"}` |
| limite de integração | 30 s → 503/504 | 29 s (padrão) → 504 |
| payload para o Lambda | 2.0 (`requestContext.http`, `authorizer.jwt.claims`) | 1.0 (`httpMethod`, `resource`, `authorizer.claims`) |
| CORS na resposta real | o Gateway acrescenta `Access-Control-Allow-Origin` | **o Lambda tem de devolver** (proxy) → C1/C2 checam `C-CORS-RESPOSTA` |
| estágio no path | estágio nomeado pode chegar no `rawPath` → pendente C2 | `path` sem estágio; `requestContext.path` com |

## 3. Verificador do provedor (C1)

O `cr.py` grava `.contrato-reverso/entrada/<consumidor>.json` (contrato já parseado + Gateway
normalizado). Nenhum stack precisa de parser YAML nem saber ler SAM/CDK/Terraform.

| stack | como roda | o que o projeto escreve |
|---|---|---|
| Java (Maven/Gradle) | JUnit `ConsumerContractVerificationTest` (template em `../templates/java-junit/`) lê a entrada, simula o Gateway e grava `target/contrato-reverso/observado-*.json` | só o bloco **ADAPTAÇÃO**: `criarHandlerV2()` (HTTP API) ou `criarHandlerV1()` (REST) com dublês |
| Python | `runner: python` — a skill conduz a jornada e simula o Gateway; o runner (`contrato_reverso.runner_python`) roda no ambiente do projeto | `tests/cdc_fabrica.py` → `criar_handler()` devolve o handler real com dublês |
| Node.js | `runner: node` — `templates/node/runner.mjs` (ESM/CommonJS, async ou callback) | `test/cdc-fabrica.mjs` → `criarHandler()` |

Configuração no contrato:

```yaml
provedor:
  verificador_inprocess:
    runner: python                 # ou node; Java usa `comando` (Maven) + `observado`
    fabrica: cdc_fabrica:criar_handler        # Node: "test/cdc-fabrica.mjs#criarHandler"
    pythonpath: [src, tests]       # Python
    interprete: [python3]          # opcional (ex.: [.venv/bin/python], [node])
    cwd: caminho/do/provedor       # padrão: provedor.raiz
    persistencia: "repositório em memória"    # vai para o relatório como alcance
```

Fábrica não adaptada (o esqueleto lança "ADAPTE criarHandler") → C1 **inconclusivo** com motivo claro.
Exceção do handler vira **502** do Gateway simulado (como na AWS) com o traceback no observado.

## 4. Quando NÃO usar esta camada sozinha

- ALB/ECS sem API Gateway, WebSocket API, integrações não-proxy com VTL: fora do leitor — declare
  a limitação e verifique por C2 (replay HTTP) contra o endpoint real.
- Autorizador Lambda com lógica própria (contexto customizado): o simulador só injeta `sub`; o resto
  só C2 prova.
