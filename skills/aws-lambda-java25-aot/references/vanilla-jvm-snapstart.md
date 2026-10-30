# Vanilla JVM / SnapStart — caminho leve e testável

> Quando ler: o pedido é uma **Lambda Java performante e testável** sem o custo de
> build/observabilidade do GraalVM Native, ou o alvo de cold start é **sub-segundo**
> (não sub-100 ms). Este é o blueprint **medido** na entrega Task Manager da Squad
> (cobertura de linha 100%, 220 testes, build `./mvnw verify` ~25–31 s, integração
> DynamoDB real). Templates: `assets/templates/*-vanilla-jvm.*.tmpl` +
> `checkstyle-structural.xml.tmpl` + `checkstyle-suppressions.xml.tmpl`.

## 1. Por que este caminho existe

A skill nasceu **Spring Boot 4 + GraalVM Native first**. Native é o caminho certo
quando o requisito é cold start <100 ms consistente ou footprint mínimo — e custa:
`reflect-config`, build +minutos, divergência JVM↔nativo, tooling de observabilidade
nativo. Para a maioria das cargas de negócio (CRUD, fluxos de domínio) esse custo
não se paga, e ele **atrapalha o loop de feedback** (cada teste em modo nativo é caro).

O caminho vanilla troca −100 ms de cold start por:

- **Testabilidade total na JVM** — sem agente de tracing, sem `@RegisterReflection`,
  testes unitários em milissegundos, mutação/cobertura triviais.
- **Build de um comando** (`./mvnw verify`) que **falha em regressão de qualidade**.
- **Zero mudança de build para mitigar cold start** — SnapStart é só config SAM.

## 2. Matriz de decisão (escolha pelo alvo, não por reflexo)

| Caminho | Cold start | Esforço/custo | Papel |
|---|---|---|---|
| Runtime gerenciado `java25` + AOT caches | ~1–2 s | zero | baseline; cargas tolerantes a cold start |
| **Vanilla + GraalVM Native** (`template-native.yaml`) | **~30–150 ms** | reflect-config + build +min; **testável na JVM** (profile native opt-in) | **PADRÃO Java 25** (decisão 2026-07-05) |
| Vanilla JVM + SnapStart (este doc, `java21`) | 200–500 ms (P99 −90%) | zero mudança de build; **grátis p/ Java**; só config SAM | **override**: SLA ≥ 200 ms, deploy contínuo, time-to-market |
| Spring Boot 4 + GraalVM Native (`pom.xml.tmpl`) | ~30–150 ms | idem Native + AOT do Spring | alternativa Spring-first |

**Regra (Java 25 novo):** o padrão é **GraalVM Native** sobre esta **mesma base vanilla
testável** (blueprint vivo: `lambda-aot-benchmark/graalvm-native/`). A testabilidade que este
doc defende é **preservada** mantendo o profile `native` **opt-in** (`-Pnative`) — assim
`mvn verify` roda na JVM em ms, e o binário nativo é construído só no `sam build`. Faça
**override para SnapStart (`java21`)** quando o SLA tolerar 200–500 ms, o deploy for contínuo,
ou o time priorizar time-to-market. A arquitetura hexagonal, os gates e os defaults de
auth/lock/timeouts deste doc valem para **ambos** os empacotamentos — só muda o runtime/pom/template.

## 3. Arquitetura do blueprint (hexagonal, domínio puro)

```
src/main/java/<base_package>/
├── domain/
│   ├── model/        Aggregate rico + Value Objects (TaskId, OwnerId, ...), máquina de estados
│   ├── exception/    Erros de DOMÍNIO (≠ HTTP); ex. InvalidStatusTransition, TaskNotFound
│   └── port/         Interface do repositório (porta) — domínio não conhece DynamoDB
├── application/      Use cases (1 por operação), Clock; orquestram domínio + porta
├── infrastructure/
│   ├── persistence/  Adapter DynamoDB (Enhanced Client), mapper item↔domínio, single-table
│   └── config/       DynamoDbClientFactory (timeouts/retry)
└── api/
    ├── (handler)     Entrypoint FINO: roteia, delega, serializa, mapeia erro
    ├── dto/          DTOs de transporte (records) — NUNCA entram no domínio
    └── (mapper)      DTO → command; explícito e testado
```

Princípios não negociáveis (selados por ArchUnit, ver §5):

- **Handler fino** — só roteia/delega/serializa. Zero regra de negócio. (demo: `doHandle` ~9 linhas)
- **Domínio puro** — sem `software.amazon.*`, `com.amazonaws.*`, `jackson`. Erros de
  domínio ≠ erros HTTP. Mapeamento `Exception → ProblemDetail` (RFC 9457) num único
  ponto via *pattern matching for switch*, testável isolado.
- **Value Objects** encapsulam primitivos com invariante no construtor compacto
  (ex. `OwnerId`/`TaskId`: `maxLength` + charset → vira `PK/SK`; bound espelhado no OpenAPI).
- **Aggregate imutável** — mutações retornam nova instância validando invariantes.

## 4. Defaults de "primeira entrega" (nascem com o template)

A entrega Squad mediu **~42 min de retrabalho evitável** porque estes itens só
apareceram no review/rodada-4. No template eles nascem por padrão:

| # | Default | Por quê |
|---|---|---|
| S3 | **Auth por padrão** — Cognito JWT authorizer + `owner == caller (sub)` → 404 em outro dono | um BOLA/IDOR HIGH só foi pego no review; fechar no template elimina a classe |
| — | **Optimistic locking** — `@DynamoDbVersionAttribute` → 409 em conflito | guarda lost-update sob concorrência |
| — | **Timeouts/retry do SDK** — apiCall 3 s / attempt 1 s / conn 500 ms / socket 2 s + standard retry | evita Lambda pendurada esperando DynamoDB |
| — | **Audit log estruturado sem PII** — 1 linha por mutação; nada do corpo | observabilidade de segurança; anti-injeção testado |
| — | **IAM mínimo** — só Get/Put/Delete/Query na tabela+GSI; sem `*`, sem DescribeTable | least privilege no template SAM |
| — | **Throttling** na API pública (burst/rate) | teto de custo + keyspace numa API pay-per-request |

## 5. Gates de qualidade (um comando: `./mvnw verify`)

Provados no blueprint; copiados pelo `pom-vanilla-jvm.xml.tmpl`:

- **JaCoCo** — gate LINE ≥ 97% em `domain`/`application`/`api` (exclui `api/dto` e
  `config`: carriers/wiring sem branch). Falha o build abaixo disso.
- **ArchUnit (conjunto COMPLETO)** — domínio isolado de AWS/infra; handler sem regra
  de negócio; repos em `infrastructure`; DTOs fora do domínio; `api ↛ infrastructure`;
  `infrastructure ↛ api/config`; `application ↛ config`; bootstrap local confinado.
- **Checkstyle estrutural (Object Calisthenics)** — `checkstyle-structural.xml.tmpl`:
  MethodLength≤35, ParameterNumber≤5 (métodos), Cyclomatic≤12, BooleanExpr≤4,
  FileLength≤300, OneStatementPerLine. Só `src/main`. As regras **arquiteturais** de
  OC ficam no ArchUnit; aqui só as **métricas estruturais**. Exceções justificadas
  (factories de aggregate) vão em `suppressions.xml`, sem afrouxar o limite global.

## 6. Integração DynamoDB SEM Testcontainers (S2 — recurso recorrente)

Testcontainers quebra no Docker Desktop 29 (bug npipe). Receita provada que mantém
o build verde **sem** Docker e roda integração real **quando** há endpoint:

1. O teste de integração é um `*Test` (roda no Surefire, cobertura no relatório principal).
2. Ele **self-skips** via `Assumptions.assumeTrue(...)` quando `DDB_ENDPOINT` está
   inalcançável → build verde em CI sem Docker.
3. Integração real, local:
   ```bash
   docker run -d -p 8000:8000 amazon/dynamodb-local
   DDB_ENDPOINT=http://localhost:8000 ./mvnw verify
   ```
4. `LocalDdbBootstrap` (nunca o repo de produção) cria a tabela só sob flag no INIT.

## 7. Layout de saída + scaffolding

```
<project>/
├── pom.xml                      ← pom-vanilla-jvm.xml.tmpl
├── template.yaml                ← template-vanilla-jvm.yaml.tmpl (SnapStart + Cognito JWT)
├── samconfig.toml
├── openapi/openapi.yaml         ← contrato 3.1; bounds dos VOs espelhados (maxLength/pattern)
├── config/checkstyle/
│   ├── checkstyle.xml           ← checkstyle-structural.xml.tmpl
│   └── suppressions.xml         ← checkstyle-suppressions.xml.tmpl ({{ entity }})
├── mvnw / mvnw.cmd / .mvn/      ← Maven wrapper SEMPRE (S4: `mvn` ausente foi custo recorrente)
└── src/{main,test}/java/...     ← camadas da §3 + ArchitectureTest + OpenApiContractTest
```

Placeholders dos templates (convenção `{{ snake_case }}`, substituição simples):
`group_id`, `artifact_id`, `version`, `base_package`, `base_package_path` (pontos→barras),
`entity` (PascalCase), `table_name`, `function_name`, `handler_class`, `table_env_var`,
`resource_path` (plural, ex. `tasks`), `id_path` (segmento com chaves, ex. `{taskId}`).

> **Gerador (S1 fechado e provado):** `scripts/generate_vanilla_lambda.py` faz **cópia
> verbatim do blueprint provado + rename uniforme de identificadores** (pacote/entidade/
> tabela). Como a MESMA substituição vale para main, testes, resources e OpenAPI, o projeto
> renomeado fica internamente consistente e passa `./mvnw verify` **VERDE de primeira**
> (mesmos 220 testes, 100% cobertura, gates JaCoCo+ArchUnit+Checkstyle). Maven wrapper (S4)
> sai por padrão (vem no blueprint).
>
> ```bash
> python aws-lambda-java25-aot/scripts/generate_vanilla_lambda.py \
>   --blueprint <repo>/app --entity Widget --package com.acme.widget \
>   --table WidgetSingleTable --app-dir ./widget-lambda
> cd widget-lambda && ./mvnw verify     # BUILD SUCCESS, 220 testes, gate MET (provado)
> ```
>
> O projeto nasce com os **campos de exemplo** do blueprint (title/priority/status/dueDate)
> sob o seu nome de entidade — é um **ponto de partida endurecido**: substitua os campos pelo
> seu DBML e **mantenha o cross-cutting** (build, gates, handler, error mapping, auth, repo,
> testes). Os arquivos `*-vanilla-jvm.*.tmpl` são os artefatos endurecidos **standalone**
> (build+gates+SAM) para adoção avulsa num projeto existente; o gerador é o caminho completo.

## 8. Evidência medida (entrega Task Manager da Squad)

| Métrica | Valor | Como |
|---|---|---|
| Cobertura de linha | **100% (653/653)** | JaCoCo, gate ≥97% MET |
| Testes | **220** verdes | Surefire (unit + ArchUnit + contrato + integração self-skip) |
| Build | `./mvnw verify` **~25–31 s** | re-rodado pelo orquestrador |
| Regras ArchUnit | **11** | ArchitectureTest |
| Gate estrutural OC | verde | Checkstyle 10.21.0 (parseia Java 25 sem erro) |
| Cold start | sub-segundo **(E, SnapStart)** | não medido em deploy real; rótulo honesto |

**Honestidade:** cold start/P99 reais exigem deploy AWS (não medidos aqui). O ganho
deste caminho é **testabilidade + qualidade travada por gates + zero custo de build
para SnapStart** — não um número de cold start. Não confunda código limpo com runtime
mais rápido. Trajetória/medições completas em `docs/metrics.jsonl` e
`docs/first-delivery-checklist.md` do repositório.
