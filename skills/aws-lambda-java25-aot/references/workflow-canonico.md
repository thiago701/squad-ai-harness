# aws-lambda-java25-aot · Workflow canônico

> Reference da skill `aws-lambda-java25-aot` (movida da SKILL.md em 11/10/2026 — hub + references, I3). Carregue só quando a tarefa pedir este tema.

## Workflow canônico

Siga estes passos em ordem. Cada etapa tem um arquivo de referência denso
em `references/` — leia o relevante quando chegar lá, não antes.

### 1. Capturar input (DBML)

O DBML pode vir de 4 formas:

1. **Arquivo `.dbml` anexado** ao prompt — leia direto.
2. **Bloco DBML inline** no prompt (entre ` ```dbml ... ``` `) — extraia.
3. **SQL DDL** (CREATE TABLE…) — converta mentalmente para DBML antes de aplicar
   o resto da skill. O parser aceita ambos.
4. **Linguagem natural** ("preciso de uma tabela de pedidos com items") — peça
   ao usuário um DBML mínimo OU rascunhe um e confirme antes de prosseguir.
   Não prossiga sem schema explícito — single-table design exige formalismo.

### 2. Parse + análise do schema

Rode `scripts/dbml_parser.py` para transformar o DBML em modelo intermediário
JSON com entidades, atributos, relações e cardinalidades. O parser detecta:

- Tabelas e colunas com tipos (varchar → String, int → Integer, timestamp → Instant)
- Primary keys (single ou composite)
- Foreign keys (1:1, 1:N, N:N) — base para inferir GSIs
- Índices declarados explicitamente

### 3. Mapping single-table

Aplique as regras documentadas em `references/dbml-to-ddb.md`. Os pilares:

- **Tabela única** chamada `<DomainName>SingleTable` (ex: `EcommerceSingleTable`).
- **PK** = `<EntityType>#<id>` (ex: `USER#42`, `ORDER#abc-123`).
- **SK** = `<EntityType>#<id>` para entidades raiz, ou `<RelatedType>#<sortAttr>`
  para sub-entidades (ex: `ORDER#2026-04-28T10:00`).
- **GSIs** inferidos das FKs reversas — ex: query "todos os pedidos de um user"
  → `GSI1PK = USER#<id>`, `GSI1SK = ORDER#<date>`.
- **Type discriminator** na coluna `_type` para deserialização polimórfica.

**Antes de gerar código, mostre o mapping ao usuário e peça confirmação.**
Single-table sem confirmação de access patterns gera Lambdas que não escalam.

### 4. Geração do projeto

Rode `scripts/scaffold_lambda.py` passando o JSON do schema + escolhas do
usuário. O scaffolder gera:

```
<project-name>/
├── pom.xml                                    (Spring Boot 4 + Native + SDK v2 + PowerTools)
├── Makefile                                   (sam build, sam deploy, native:compile)
├── template.yaml                              (SAM: Lambda + API + Streams + DDB)
├── samconfig.toml                             (sam deploy --guided cache)
├── README.md                                  (setup + deploy + curl examples)
├── src/main/java/<pkg>/
│   ├── Application.java                       (Spring Boot entrypoint)
│   ├── handler/
│   │   ├── ApiGatewayHandler.java             (HTTP routing por endpoint)
│   │   └── DynamoDbStreamHandler.java         (CDC handler)
│   ├── model/
│   │   ├── <Entity>.java                      (1 record por entidade DBML)
│   │   └── SingleTableItem.java               (mapping helper)
│   ├── repository/
│   │   └── SingleTableRepository.java         (Enhanced Client + queries por GSI)
│   └── config/
│       ├── DynamoDbConfig.java                (cliente + table schema)
│       └── NativeHints.java                   (@RegisterReflectionForBinding)
├── src/main/resources/
│   ├── application.properties                 (Spring + virtual threads)
│   └── META-INF/native-image/
│       └── <group>/<artifact>/
│           ├── reflect-config.json            (Enhanced Client + entities)
│           ├── resource-config.json
│           └── proxy-config.json
└── src/test/java/<pkg>/
    ├── handler/
    │   ├── ApiGatewayHandlerTest.java         (Testcontainers + LocalStack)
    │   └── DynamoDbStreamHandlerTest.java
    └── repository/
        └── SingleTableRepositoryTest.java
```

### 5. Validação local

Antes de declarar pronto, oriente o usuário a rodar:

```bash
mvn -Pnative native:compile         # gera bootstrap binary
mvn -Pnative test                   # roda testes em modo nativo
sam local invoke ApiGatewayFunction --event events/get-user.json
```

Se algum passo falhar, consulte `references/spring-boot-4-graalvm-lambda.md`
seção "Debugging native build failures". Para investigar bug em runtime/nativo (não só build), use `references/troubleshooting-aot.md`.

### 6. Deploy

```bash
sam build --use-container          # build dentro de container al2023
sam deploy --guided                # primeira vez; cria samconfig.toml
sam deploy                         # subsequentes
```
