# Tutorial — Do prompt ao deploy AWS

Walkthrough completo de uso da skill `aws-lambda-java25-aot`. Sai do prompt
inicial e termina com a Lambda nativa rodando em produção, respondendo
chamadas HTTP e processando eventos do DynamoDB Streams.

Tempo estimado: 30–45 minutos na primeira vez (a maior parte é o build
nativo + primeiro deploy SAM). Depois dos prereqs, ciclos de iteração
caem para 3–5 minutos.

## Sumário

1. [Pré-requisitos](#1-pré-requisitos)
2. [O prompt inicial](#2-o-prompt-inicial)
3. [Etapa 1 — Schema DBML](#3-etapa-1--schema-dbml)
4. [Etapa 2 — Confirmar access patterns + GSIs](#4-etapa-2--confirmar-access-patterns--gsis)
5. [Etapa 3 — Geração do projeto](#5-etapa-3--geração-do-projeto)
6. [Etapa 4 — Build nativo](#6-etapa-4--build-nativo)
7. [Etapa 5 — Teste local com SAM](#7-etapa-5--teste-local-com-sam)
8. [Etapa 6 — Deploy AWS](#8-etapa-6--deploy-aws)
9. [Etapa 7 — Validação em produção](#9-etapa-7--validação-em-produção)
10. [Iterando: novos endpoints, novas entidades](#10-iterando-novos-endpoints-novas-entidades)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Pré-requisitos

Instale uma vez na sua máquina (Linux/macOS/WSL2):

```bash
# Java 25 + GraalVM via SDKMAN
sdk install java 25-graalce
sdk use java 25-graalce
java --version            # OpenJDK 25 (GraalVM CE) ...

# native-image (geralmente já vem no GraalVM CE; se não:)
gu install native-image
native-image --version    # 22+

# Maven 4
sdk install maven 3.9.9

# AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip awscliv2.zip && sudo ./aws/install
aws configure             # access key + secret + região default

# AWS SAM CLI 1.131+
brew install aws-sam-cli  # macOS
# ou: pip install aws-sam-cli

# Docker (para sam build --use-container)
# https://docs.docker.com/engine/install/
docker --version
```

Conta AWS com permissões para criar:

- Lambda functions + execution roles
- API Gateway HTTP APIs
- DynamoDB tables (com Streams)
- IAM roles
- CloudFormation stacks
- S3 bucket (para o pacote SAM)

---

## 2. O prompt inicial

Abra o Claude (Claude Code, Cowork, ou Web) e use **um destes prompts** —
todos disparam a skill `aws-lambda-java25-aot`:

### Prompt curto (DBML inline)

```
Use a skill aws-lambda-java25-aot. Gere uma Lambda Java 25 + Spring Boot 4 +
GraalVM Native a partir do DBML abaixo, com endpoints CRUD para User e
listagem de Orders por User, e um handler de DynamoDB Streams para eventos
de Order. Single-table design, AWS SAM como IaC.

```dbml
Project ecommerce {}

Table users {
  id varchar [pk]
  email varchar [unique, not null]
  name varchar [not null]
  created_at timestamp
}

Table orders {
  id varchar [pk]
  user_id varchar [ref: > users.id, not null]
  status varchar [not null]
  total decimal
  created_at timestamp
}

Table order_items {
  id varchar [pk]
  order_id varchar [ref: > orders.id]
  sku varchar
  quantity int
  price decimal
}
```
```

### Prompt longo (com requisitos de performance)

```
Preciso de uma Lambda Java na AWS com cold start agressivo (sub-100ms) para
o domínio de e-commerce. As entidades são User, Order e OrderItem (DBML em
anexo). Os endpoints HTTP devem cobrir: GET /users/{id}, GET /users/{id}/orders,
POST /orders, GET /orders/{id}. Também preciso de um handler de DynamoDB
Streams que reage a INSERT de Order para publicar evento downstream. Use
single-table design no DynamoDB e SAM como IaC. Build com Maven e deploy
em arm64.
```

A skill detecta o pedido, lê o DBML, e antes de gerar código **conduz uma
entrevista curta** sobre access patterns para confirmar os GSIs.

---

## 3. Etapa 1 — Schema DBML

A skill aceita 4 formas de input:

| Forma | Como entregar |
|---|---|
| Arquivo `.dbml` anexado | "use o arquivo schema.dbml em anexo" |
| DBML inline no prompt | bloco ` ```dbml ... ``` ` (como no exemplo acima) |
| SQL DDL | a skill converte mentalmente para DBML antes de prosseguir |
| Linguagem natural | a skill rascunha um DBML e pede confirmação |

Para este tutorial, vamos usar o DBML inline do exemplo curto.

A skill executa internamente:

```bash
python scripts/dbml_parser.py schema.dbml > schema.json
```

Output (resumido):

```json
{
  "domain": "ecommerce",
  "tables": [
    { "name": "users", "entity": "User", "columns": [...] },
    { "name": "orders", "entity": "Order", "columns": [...] },
    { "name": "order_items", "entity": "OrderItem", "columns": [...] }
  ],
  "refs": [
    { "from": {"table":"orders","column":"user_id"}, "to": {"table":"users","column":"id"}, "cardinality":"many-to-one" },
    { "from": {"table":"order_items","column":"order_id"}, "to": {"table":"orders","column":"id"}, "cardinality":"many-to-one" }
  ]
}
```

---

## 4. Etapa 2 — Confirmar access patterns + GSIs

Esta é a etapa **mais crítica** — single-table design exige planejamento
explícito dos access patterns. A skill apresenta uma proposta e pergunta:

> Encontrei 3 entidades no DBML: User, Order, OrderItem. Para o single-table
> design eu preciso saber quais access patterns serão usados. Confirme:
>
> 1. Buscar User por id ✓ (PK base)
> 2. Buscar User por email — preciso de **GSI1** com PK=`EMAIL#{email}`?
> 3. Listar Orders de um User (mais recente primeiro) ✓ (PK base + SK begins_with)
> 4. Buscar Order por id global — preciso de **GSI2** com PK=`ORDER#{id}`?
> 5. Listar OrderItems de uma Order ✓ (mesma partição)
> 6. Existe outro access pattern? (ex: orders por status, top customers)

**Você responde** confirmando ou ajustando. Exemplo de resposta:

```
Confirmo 1-5. Adiciona um GSI3 para "listar orders por status, ordenadas
por data" (vai ser usado no admin dashboard). Não preciso de outros.
```

A skill consolida:

| Entidade | PK | SK | GSI1PK | GSI1SK | GSI2PK | GSI2SK | GSI3PK | GSI3SK |
|---|---|---|---|---|---|---|---|---|
| User | `USER#{id}` | `USER#{id}` | `EMAIL#{email}` | `USER#{id}` | — | — | — | — |
| Order | `USER#{userId}` | `ORDER#{createdAt}#{id}` | — | — | `ORDER#{id}` | `ORDER#{id}` | `STATUS#{status}` | `ORDER#{createdAt}` |
| OrderItem | `ORDER#{orderId}` | `ITEM#{id}` | — | — | — | — | — | — |

Você aprova → próxima etapa.

---

## 5. Etapa 3 — Geração do projeto

A skill executa:

```bash
python scripts/scaffold_lambda.py schema.json \
    -o ./ecommerce-lambda \
    --group com.example \
    --artifact ecommerce-lambda \
    --base-package com.example.ecommerce \
    --stack-name ecommerce
```

E gera a estrutura completa:

```
ecommerce-lambda/
├── pom.xml                                ← Spring Boot 4 + Native + SDK v2 + PowerTools
├── Makefile                               ← build-ApiGatewayFunction, build-StreamHandlerFunction
├── template.yaml                          ← SAM: 2 Lambdas + DDB + GSI1/2/3 + Streams
├── samconfig.toml                         ← envs dev/stg/prd
├── README.md                              ← setup + deploy + curl examples
├── events/
│   ├── get-user.json
│   ├── create-order.json
│   └── dynamodb-stream.json
└── src/
    ├── main/java/com/example/ecommerce/
    │   ├── Application.java
    │   ├── config/
    │   │   ├── DynamoDbConfig.java
    │   │   └── NativeHints.java          ← reflect-config para User, Order, OrderItem + SDK v2
    │   ├── handler/
    │   │   ├── ApiGatewayHandler.java    ← roteia GET /users/{id}, POST /orders, etc.
    │   │   └── DynamoDbStreamHandler.java ← reage a INSERT/MODIFY/REMOVE
    │   ├── model/
    │   │   ├── SingleTableItem.java      ← @DynamoDbBean wide-row
    │   │   ├── User.java                 ← record com toItem/fromItem
    │   │   ├── Order.java
    │   │   └── OrderItem.java
    │   └── repository/
    │       └── SingleTableRepository.java ← getUserById, listOrdersByUser, etc.
    ├── main/resources/
    │   ├── application.properties        ← virtual threads, banner off, function bean
    │   ├── log4j2.xml                    ← Lambda appender JSON
    │   └── META-INF/native-image/com.example/ecommerce-lambda/
    │       ├── reflect-config.json       ← entidades + SDK v2
    │       └── resource-config.json
    └── test/java/com/example/ecommerce/   ← Testcontainers + LocalStack
```

A skill imprime no chat:

> Projeto gerado em `./ecommerce-lambda/`. Próximos passos:
> 1. `cd ecommerce-lambda`
> 2. Revisar `README.md`
> 3. `mvn -Pnative native:compile` para validar localmente
> 4. `sam build --use-container && sam deploy --guided` para subir em AWS

---

## 6. Etapa 4 — Build nativo

```bash
cd ecommerce-lambda

# Build local (rápido — só funciona se o host for Linux x86_64/arm64)
mvn -Pnative native:compile -DskipTests
# → gera target/bootstrap (binário ELF ~40-60 MB)

# Build via container al2023 (lento — ~5-15 min na primeira vez por causa do
# download da imagem; ~2-3 min nas subsequentes)
sam build --use-container
# → gera .aws-sam/build/ApiGatewayFunction/bootstrap (compatível com Lambda)
```

Sintomas comuns na primeira build:

- `out of memory during native-image` → aumente heap com `MAVEN_OPTS="-Xmx4g"`.
- `glibc version mismatch` → use `sam build --use-container` (resolve).
- `ClassNotFoundException` listada no log → adicione classe ao `NativeHints.java`
  e rebuild.

Build bem-sucedido produz:

```
[INFO] Image build for 'bootstrap' succeeded.
[INFO] BUILD SUCCESS
```

---

## 7. Etapa 5 — Teste local com SAM

```bash
# Invocar uma Lambda específica com evento mockado
sam local invoke ApiGatewayFunction --event events/get-user.json
# → output JSON com statusCode + body do handler

# Subir API local na porta 3000
sam local start-api --port 3000

# Em outro terminal:
curl http://localhost:3000/users/42
# → {"id":"42","email":"x@y.com","name":"...","createdAt":"..."}

# Para o handler de Streams:
sam local invoke StreamHandlerFunction --event events/dynamodb-stream.json
```

**Importante**: `sam local invoke` usa Docker para emular o runtime al2023.
A primeira vez baixa a imagem (~500MB).

Para testar contra DynamoDB de verdade (ou LocalStack):

```bash
# LocalStack (DynamoDB local)
docker run --rm -d --name localstack -p 4566:4566 localstack/localstack
aws --endpoint http://localhost:4566 dynamodb create-table \
    --table-name ecommerce-dev-single-table \
    --attribute-definitions AttributeName=pk,AttributeType=S AttributeName=sk,AttributeType=S \
    --key-schema AttributeName=pk,KeyType=HASH AttributeName=sk,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST

# Apontar a Lambda local pro LocalStack
sam local invoke ApiGatewayFunction \
    --event events/create-order.json \
    --parameter-overrides "ParameterKey=Stage,ParameterValue=dev" \
    --env-vars '{ "ApiGatewayFunction": { "AWS_ENDPOINT": "http://host.docker.internal:4566" } }'
```

---

## 8. Etapa 6 — Deploy AWS

### Primeiro deploy (interativo)

```bash
sam deploy --guided
```

A SAM faz perguntas:

```
Stack Name [sam-app]: ecommerce-dev
AWS Region [us-east-1]:
Parameter Stage [dev]:
Confirm changes before deploy [y/N]: y
Allow SAM CLI IAM role creation [Y/n]: y
Save arguments to configuration file [Y/n]: y
SAM configuration file [samconfig.toml]:
SAM configuration environment [default]:
```

A SAM cria um S3 bucket de cache, faz upload do binário, e dispara o
CloudFormation stack:

```
Successfully created/updated stack - ecommerce-dev in us-east-1

CloudFormation outputs from deployed stack
─────────────────────────────────────────────
Outputs
─────────────────────────────────────────────
Key                 ApiUrl
Description         Base URL of the HTTP API
Value               https://abc123def.execute-api.us-east-1.amazonaws.com

Key                 SingleTableName
Value               ecommerce-dev-single-table

Key                 SingleTableArn
Value               arn:aws:dynamodb:us-east-1:123456789012:table/ecommerce-dev-single-table
─────────────────────────────────────────────
```

Anote o `ApiUrl` — é o endpoint da sua API.

### Deploys subsequentes

```bash
sam deploy                       # usa samconfig.toml [default]
sam deploy --config-env stg      # deploy stg
sam deploy --config-env prd      # deploy prd
```

---

## 9. Etapa 7 — Validação em produção

```bash
API_URL="https://abc123def.execute-api.us-east-1.amazonaws.com"

# Criar um user via PUT (assumindo endpoint POST /users existe)
curl -X POST "$API_URL/users" \
    -H "Content-Type: application/json" \
    -d '{"id":"42","email":"thiago@example.com","name":"Thiago"}'

# Buscar
curl "$API_URL/users/42"
# → {"id":"42","email":"thiago@example.com","name":"Thiago","createdAt":"..."}

# Listar orders (vazio inicialmente)
curl "$API_URL/users/42/orders"
# → []

# Criar uma order
curl -X POST "$API_URL/orders" \
    -H "Content-Type: application/json" \
    -d '{"userId":"42","items":[{"sku":"ABC","quantity":1,"price":29.90}],"total":29.90}'

# Verificar — esta INSERT também dispara DynamoDB Streams
curl "$API_URL/users/42/orders"
# → [{"id":"...","userId":"42","total":29.90,...}]
```

### Inspecionar logs e métricas

```bash
# Tail dos logs em tempo real
sam logs --stack-name ecommerce-dev --name ApiGatewayFunction --tail

# Métricas custom emitidas via PowerTools (EMF)
aws cloudwatch list-metrics --namespace ecommerce-dev

# Cold start específico
aws cloudwatch get-metric-statistics \
    --namespace ecommerce-dev \
    --metric-name ColdStart \
    --start-time $(date -u -d '1 hour ago' +%FT%TZ) \
    --end-time $(date -u +%FT%TZ) \
    --period 300 \
    --statistics Average,Maximum
```

### Inspecionar traces no X-Ray

Console AWS → X-Ray → Service map. Cada invocação aparece como nó com
latência por subsegmento (init, dynamodb-get, dynamodb-query, etc).

### Verificar Streams handler

```bash
# Logs do StreamHandlerFunction — deve mostrar INSERT processado após cada POST /orders
sam logs --stack-name ecommerce-dev --name StreamHandlerFunction --tail
```

---

## 10. Iterando: novos endpoints, novas entidades

Para adicionar um novo endpoint ou entidade depois do deploy inicial,
**não regenere o projeto inteiro** — peça à skill um patch incremental:

```
Use a skill aws-lambda-java25-aot.

No projeto ecommerce-lambda existente, adicione:
- GET /orders/{id} no ApiGatewayHandler
- Suporte a "cancel order" (status → CANCELLED) no SingleTableRepository
- Métrica EMF custom OrdersCancelled
```

A skill respeita o projeto existente, lê o DBML implícito, identifica
quais arquivos alterar, e propõe os diffs. Você revisa, aplica,
`sam deploy`. Cycle time: 3–5 minutos.

Para adicionar uma **nova entidade** (ex: `Coupon`):

```
No DBML do projeto adicione:

Table coupons {
  id varchar [pk]
  code varchar [unique]
  discount_pct int
  valid_until timestamp
}

E gere os arquivos necessários: model/Coupon.java, ajuste em SingleTableItem,
endpoint POST /coupons + GET /coupons/{code}, e atualize NativeHints.
```

A skill atualiza:
- `model/Coupon.java` (record)
- `model/SingleTableItem.java` (campos novos)
- `repository/SingleTableRepository.java` (métodos `getCouponByCode`)
- `handler/ApiGatewayHandler.java` (rotas)
- `config/NativeHints.java` (Coupon.class)
- `META-INF/native-image/.../reflect-config.json` (Coupon)
- `template.yaml` (rotas no `Events:`)

---

## 11. Troubleshooting

| Sintoma | Causa | Resolução |
|---|---|---|
| `mvn -Pnative` pesa OOM | Heap insuficiente | `MAVEN_OPTS="-Xmx4g -Xss4m"` |
| `bootstrap: cannot execute binary file` em Lambda | glibc host ≠ al2023 | Usar `sam build --use-container` sempre |
| `ClassNotFoundException` em runtime | Reflection unregistered | Adicionar classe em `NativeHints.java` |
| `MissingResourceException: spring.factories` | Resource não copiado | Editar `resource-config.json` |
| Cold start > 500ms | Não está rodando native | Conferir `Runtime: provided.al2023` no template.yaml e que `bootstrap` é o binário (não JAR) |
| `403 Forbidden` em todas chamadas | API Gateway sem auth pública | Conferir `Auth: { ... }` ou ausência dele no template (default = público) |
| DynamoDB throttle | Hot partition | Revisar PK distribuição; considerar adicionar suffix `#shardN` se necessário |
| Stream handler não dispara | Stream não habilitada na tabela | `StreamSpecification: { StreamViewType: NEW_AND_OLD_IMAGES }` |
| `sam deploy` com mudanças em template.yaml falha | Drift do CloudFormation | `sam deploy --force-upload` ou `aws cloudformation continue-update-rollback` |

### Como pedir ajuda à skill durante troubleshooting

Cole o erro inteiro + o arquivo relevante:

```
A Lambda está dando ClassNotFoundException: software.amazon.awssdk.enhanced.dynamodb.OperationContext
em produção (não acontece local). Aqui está meu NativeHints.java:

[paste]
```

A skill identifica a classe ausente, sugere o hint correto, e oferece
o patch.

---

## Resumo do ciclo

```
DBML  →  parse  →  confirma access patterns  →  scaffolder
                                                     ↓
                                              projeto gerado
                                                     ↓
                                       mvn -Pnative native:compile
                                                     ↓
                                             sam build --use-container
                                                     ↓
                                                 sam deploy
                                                     ↓
                                              curl + sam logs
```

Tempo de iteração após primeiro deploy: ~3–5 minutos para mudanças
incrementais. Cold start em produção: ~80–150ms. Custo ARM64 + native:
~50% menor que Java JIT em x86_64 para o mesmo workload.

Bom voo. 🚀
