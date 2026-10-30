# Trace2Local — Lambda + Station (modo Companion) na stack serverless

> Validado na stack alvo `examples/finance-pix` do repositório `trace2local`: API Gateway (OpenAPI) → Lambda Java 25
> (JVM jlink **e** GraalVM nativo, runtime `provided.al2023`) → DynamoDB · Postgres · SQS → Lambda · SNS → Lambda ·
> 5 parceiros; Terraform no LocalStack 4.9. Jornadas 61/61 em JVM e nativo; cold start nativo 808 ms × JVM 2 191 ms.
> Caso mínimo: `examples/lambda-sqs` (Lambda + SQS por *event source mapping* + CloudWatch, `docker compose up`).

## Topologia

```
cliente ─► API Gateway ─► λ (Trace2LocalLambdaHandler) ──OTLP + Δ + logs (Bearer)──► Station ──► UI Resonance
                              │ SQS/SNS com traceparent nos atributos                  ▲ tail CloudWatch (LocalStack)
                              └► λ consumidor (mesma árvore) ──────────────────────────┘ Mock Connect (porta própria)
```

## Station

Direto no host (depois do `./mvnw -B install -DskipTests` da lib):

```bash
java -jar trace2local-station/target/trace2local-station-0.1.0-SNAPSHOT.jar   # UI :9876, mocks :9877
```

No host o bind é `127.0.0.1` e o ingest pode ficar sem token. Em contêiner (as Lambdas precisam alcançá-lo pela
rede do compose), defina `TRACE2LOCAL_STATION_TOKEN` — sem ele o Station loga um aviso — e publique as portas
**só em 127.0.0.1**:

```yaml
trace2local-station:
  build: { context: ../.., dockerfile: examples/finance-pix/Dockerfile.station }
  ports: ["127.0.0.1:19877:19877", "127.0.0.1:19878:19878"]
  environment:
    - TRACE2LOCAL_STATION_TOKEN=devtoken                     # Bearer do ingest (demo; troque)
    - TRACE2LOCAL_ALLOWED_HOSTS=localhost,127.0.0.1
    - TRACE2LOCAL_CLOUDWATCH_ENDPOINT=http://localstack:4566 # logs das funções na linha do tempo
    - TRACE2LOCAL_CLOUDWATCH_REGION=us-east-1
    - TRACE2LOCAL_CLOUDWATCH_LOG_GROUP_PREFIX=/aws/lambda/
    - TRACE2LOCAL_BUSINESS_FILE=/business/trace2local-business.md
    - TRACE2LOCAL_INFRA_SCAN_DIRS=/infra                     # Terraform × uso real (aba Infra)
    - TRACE2LOCAL_MOCKS_DIR=/mocks                           # contratos OpenAPI dos parceiros
    - TRACE2LOCAL_MOCKS_STATE_FILE=/data/mocks-state.json
    - TRACE2LOCAL_MOCKS_ADVERTISED_URL=http://trace2local-station:19878
    - TRACE2LOCAL_OPENAPI_SPEC=/infra/openapi/pix-api.yaml   # aba API dispara pelo contrato
    - TRACE2LOCAL_OPENAPI_BASE_URL=http://localstack:4566/restapis/pixapi/local/_user_request_
```

Outras variáveis do Station: `TRACE2LOCAL_PORT` (padrão `9876`), `TRACE2LOCAL_MOCKS_PORT` (`9877`),
`TRACE2LOCAL_DATA_DIR` e `TRACE2LOCAL_HISTORY=off` (baseline por fluxo persistido),
`TRACE2LOCAL_PROJECT_DIRS` + `TRACE2LOCAL_QUALITY_GATE_COVERAGE` (cobertura × gate nas regras preditivas).
As funções falam com o Station pela rede interna do compose (`LAMBDA_DOCKER_NETWORK` no LocalStack).

## Função

```java
public final class LiquidacaoHandler extends Trace2LocalLambdaHandler<Map<String, Object>, Map<String, Object>> {
    @Override protected SpanContext remoteParentOf(Map<String, Object> e, Context c) { return Trace2LocalTraceContext.fromSqsEvent(e); }
    @Override protected Baggage baggageOf(Map<String, Object> e, Context c)       { return Trace2LocalTraceContext.baggageFromMessageEvent(e); }
    @Override protected Map<String, Object> handle(Map<String, Object> e, Context c) throws Exception {
        return step("Liquidar no SPI", () -> spi.settle(...));
    }
}
```

`remoteParentOf` e `baggageOf` são opcionais (padrão: nova árvore, sem baggage) — sobrescreva para não nascer raiz
órfã e para a variação de mock sob demanda funcionar.

| peça | API |
|---|---|
| contexto de entrada | `Trace2LocalTraceContext.fromApiGatewayEvent` · `fromSqsEvent` · `fromSnsEvent` · `fromHeaders` · `parse` (+ `AWSTraceHeader`) |
| baggage (variação de mock sob demanda) | `baggageFromApiGatewayEvent` · `baggageFromMessageEvent` · `baggageFromHeaders` |
| handler existente, sem herança | `Trace2LocalLambda.instrument(handler, Trace2LocalLambda.configFromEnv())` |
| passos de negócio | `Trace2LocalBusiness.step("Nome", () -> …)` / `run("Nome", () -> …)` |
| publicar mantendo a árvore | `Trace2LocalMessaging.sqsAttributes()` / `snsAttributes()` nos `messageAttributes` |
| AWS SDK v2 | `Trace2LocalAws.instrument(DynamoDbClient.builder(), cfg)`, `instrument(SqsClient.builder())`, `instrument(SnsClient.builder())` |
| Δ exato também no UpdateItem | `Trace2LocalAws.instrumentWithReadBack(builder, cfg)` — **por último** na cadeia do builder; custa 1 GetItem a mais por UpdateItem |
| JDBC | `Trace2LocalJdbc.wrap(ds, cfg)` (`TRACE2LOCAL_JDBC_MUTATION_CAPTURE=inferred`) |
| parceiros HTTP | `Trace2LocalHttp.instrument(httpClient, "Parceiro")` |
| config por ambiente | `Trace2LocalLambda.configFromEnv()` |

Variáveis da função: `TRACE2LOCAL_STATION_ENDPOINT`, `TRACE2LOCAL_STATION_TOKEN`, `TRACE2LOCAL_FLUSH_TIMEOUT_MS`
(orçamento do flush síncrono no fim da invocação), `TRACE2LOCAL_JDBC_MUTATION_CAPTURE`, `TRACE2LOCAL_MOCKS_ROUTING=on`
(opcional). **Sem endpoint = pass-through** (sem exporter, sem thread): o mesmo artefato vai para produção.

O gatilho dá o rótulo da raiz: `fn · POST /rota` (HTTP ≥ 500 = erro; 4xx é recusa de negócio, não erro),
`fn · SQS fila`, `fn · SNS tópico EVENTO`.

## Spring Boot em Companion

Para ver um app Spring e as Lambdas na mesma árvore, vários serviços Spring juntos, ou usar o Mock Connect a partir
do app, aponte o app para o Station:

```bash
TRACE2LOCAL_STATION_ENDPOINT=http://127.0.0.1:9876 TRACE2LOCAL_STATION_TOKEN=… \
TRACE2LOCAL_MOCKS_ROUTING=on ./mvnw spring-boot:run -Dspring-boot.run.profiles=trace2local
```

As variáveis viram `trace2local.station.*` pelo binding do Spring, e o roteamento de mocks lê as mesmas variáveis.
O app deixa de hospedar UI (log `modo Companion detectado …`) e exporta OTLP/HTTP. **Degradação declarada:**
OTLP não carrega o canal de mutação, então os nós de dados chegam **sem Δ** — para ver antes → depois, use o
embedded (teste `StationJourneyIT` da lib).

## Java 25 no LocalStack

- LocalStack Community não tem runtime `java25`: use **`provided.al2023`** com um laço próprio da Lambda Runtime API
  (bootstrap que chama `java -jar` ou o binário nativo).
- JRE por **jlink** a partir de um Temurin 25 (o JDK GraalVM infla a imagem com JVMCI) + arquivo **CDS**.
- **Nativo**: treine com `native-image-agent` contra o compose real (gera `reachability-metadata.json`); compile em
  `ghcr.io/graalvm/native-image-community:25` (glibc 2.34 = AL2023). Limpe o acervo do Station depois do treino
  (`DELETE /trace2local/api/executions` com `X-Trace2Local: 1`) — senão o conselheiro de mocks vê hosts `localhost`.
- **Terraform**: fixe o provider AWS em `~> 5.100` com LocalStack 4.x (o 6.x trava em `WarmThroughput` do DynamoDB).
- API Gateway a partir do OpenAPI com tag `_custom_id_` para URL estável no LocalStack.
- **Dev no Windows**: o JRE da Lambda precisa ser **Linux** — gere o pacote num contêiner (o `Dockerfile.build` da
  stack alvo faz jlink + zip no Linux) e mantenha o `bootstrap` com **LF** (`.gitattributes`: CRLF quebra o runtime
  custom). Na stack alvo, `examples\finance-pix\scripts\up.cmd` sobe tudo só com o Docker Desktop (`-SkipBuild`,
  `-Down` derruba inclusive os contêineres de Lambda, `-CaBundle` para proxy corporativo com inspeção TLS).

## Validação recomendada (copie da stack alvo)

`examples/finance-pix/scripts/journeys.py`: cada jornada dispara a API real e confere **contra o estado real**
(psql, DynamoDB) em níveis — L1 contrato · L2 árvore · L3 dados · L4 assíncrono · L5 mocks · L6 ferramenta. Comece
o roteiro limpando o acervo e os bindings (estado reprodutível).
