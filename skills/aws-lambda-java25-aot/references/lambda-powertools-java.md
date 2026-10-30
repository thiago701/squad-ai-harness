# Lambda PowerTools for Java — Observability + Idempotency

PowerTools é a suite oficial AWS para boas práticas em Lambda Java.
Cobre logging estruturado, métricas via EMF, tracing X-Ray, idempotency,
parameters, validation e batch processing — tudo AOT-friendly.

## Índice

1. [Por que PowerTools](#por-que-powertools)
2. [Logging estruturado](#logging-estruturado)
3. [Metrics via EMF](#metrics-via-emf)
4. [Tracing com X-Ray](#tracing-com-x-ray)
5. [Idempotency — DynamoDB Streams](#idempotency--dynamodb-streams)
6. [Parameters — fetch de SSM/Secrets](#parameters--fetch-de-ssmsecrets)
7. [Configuração no Spring Boot 4](#configuração-no-spring-boot-4)

## Por que PowerTools

Reescrever logging estruturado, EMF custom metrics e idempotency manual em
toda Lambda é desperdício. PowerTools resolve isso com anotações
declarativas:

```java
@Logging(logEvent = true)
@Metrics(namespace = "MyApp", captureColdStart = true)
@Tracing(captureMode = CaptureMode.RESPONSE_AND_ERROR)
@Idempotent(idempotencyConfig = @IdempotencyConfig(eventKeyJMESPath = "Records[0].eventID"))
public Void handle(DynamodbEvent event) { ... }
```

Cada anotação adiciona ~zero overhead em runtime nativo (interceptors são
expandidos em build-time pelo AOT processing).

## Logging estruturado

`@Logging` enriquece automaticamente cada log com:

- `correlationId` — extraído do header (configurável)
- `awsRequestId`, `functionName`, `functionVersion`, `coldStart`
- Custom keys via `LoggingUtils.appendKey(key, value)`

```java
import software.amazon.lambda.powertools.logging.Logging;
import software.amazon.lambda.powertools.logging.LoggingUtils;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

public class MyHandler {
    private static final Logger log = LogManager.getLogger();

    @Logging(logEvent = true, correlationIdPath = "headers.x-correlation-id")
    public APIGatewayV2HTTPResponse handle(APIGatewayV2HTTPEvent event, Context ctx) {
        LoggingUtils.appendKey("userId", extractUserId(event));
        log.info("Processing get-user request");
        // ...
    }
}
```

**Configuração mínima** (`src/main/resources/log4j2.xml`):

```xml
<Configuration status="WARN">
  <Appenders>
    <Lambda name="Lambda">
      <JsonLayout
        complete="false"
        compact="true"
        eventEol="true"
        objectMessageAsJsonObject="true"
        properties="true"/>
    </Lambda>
  </Appenders>
  <Loggers>
    <Root level="info">
      <AppenderRef ref="Lambda"/>
    </Root>
  </Loggers>
</Configuration>
```

PowerTools fornece o appender `Lambda` que escreve em stdout no formato
esperado pelo CloudWatch Logs Insights.

## Metrics via EMF

EMF (Embedded Metric Format) é a forma de emitir métricas custom sem
chamar a API do CloudWatch — basta logar JSON num formato específico no
stdout, e o CloudWatch extrai automaticamente.

`@Metrics` injeta um `MetricsLogger` no contexto:

```java
import software.amazon.lambda.powertools.metrics.Metrics;
import software.amazon.lambda.powertools.metrics.MetricsUtils;
import software.amazon.cloudwatchlogs.emf.model.Unit;

public class CheckoutHandler {

    @Metrics(namespace = "Ecommerce", service = "checkout", captureColdStart = true)
    public APIGatewayV2HTTPResponse handle(APIGatewayV2HTTPEvent event, Context ctx) {
        var metrics = MetricsUtils.metricsLogger();
        metrics.putDimensions(DimensionSet.of("Region", System.getenv("AWS_REGION")));
        metrics.putMetric("OrderCount", 1, Unit.COUNT);
        metrics.putMetric("OrderValue", order.total(), Unit.NONE);
        // ...
    }
}
```

Métricas obrigatórias por convenção (a skill sugere ao gerar):

- `ColdStart` — automática via `captureColdStart = true`
- `<Endpoint>Count` — invocações por endpoint
- `<Endpoint>LatencyMs` — duração da invocação
- `<Endpoint>Errors` — erros por endpoint

## Tracing com X-Ray

`@Tracing` captura subsegmentos automaticamente:

```java
@Tracing(captureMode = CaptureMode.RESPONSE_AND_ERROR)
public Order findOrder(String id) {
    return repository.findById(id);
}

@Tracing(segmentName = "validate-payment")
public boolean validatePayment(Payment p) {
    // este método aparece como segmento separado no X-Ray timeline
}
```

Para Tracing funcionar:
- `template.yaml` → `Tracing: Active` na função Lambda
- `template.yaml` → `Policies: AWSXRayDaemonWriteAccess` no Role da função
- AWS SDK v2 → `TracingInterceptor` adiciona spans automáticos para chamadas DDB/HTTP

## Idempotency — DynamoDB Streams

Streams entregam at-least-once. Sem idempotency, processar o mesmo record
2x pode duplicar eventos downstream.

`@Idempotent` usa DynamoDB para armazenar hash do request + resposta. Se
mesmo hash chegar antes do TTL, retorna a resposta cacheada:

```java
import software.amazon.lambda.powertools.idempotency.Idempotent;
import software.amazon.lambda.powertools.idempotency.persistence.dynamodb.DynamoDBPersistenceStore;

public class StreamHandler {

    static {
        Idempotency.config().withConfig(
            IdempotencyConfig.builder()
                .withEventKeyJMESPath("Records[0].eventID")  // chave única por record
                .withExpiration(Duration.ofHours(1))
                .build())
            .withPersistenceStore(
                DynamoDBPersistenceStore.builder()
                    .withTableName(System.getenv("IDEMPOTENCY_TABLE"))
                    .build())
            .configure();
    }

    @Idempotent
    public Void apply(DynamodbStreamRecord record) {
        // processado exatamente 1x por eventID, mesmo se Lambda reentregar
        publishToEventBridge(record);
        return null;
    }
}
```

**Tabela auxiliar de idempotency** no template SAM:

```yaml
IdempotencyTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: !Sub ${AWS::StackName}-idempotency
    AttributeDefinitions:
      - AttributeName: id
        AttributeType: S
    KeySchema:
      - AttributeName: id
        KeyType: HASH
    BillingMode: PAY_PER_REQUEST
    TimeToLiveSpecification:
      AttributeName: expiration
      Enabled: true
```

## Parameters — fetch de SSM/Secrets

Em vez de fazer `SsmClient.getParameter()` na mão (com cache manual), use
o módulo Parameters:

```java
import software.amazon.lambda.powertools.parameters.SSMProvider;
import software.amazon.lambda.powertools.parameters.cache.CacheManager;

public class Handler {
    private static final SSMProvider ssm = ParamManager.getSsmProvider();

    public APIGatewayV2HTTPResponse handle(...) {
        String apiKey = ssm
            .withMaxAge(5, ChronoUnit.MINUTES)   // cache 5min
            .withTransformation(Transformer.json)
            .get("/myapp/external-api-key");
        // ...
    }
}
```

Cache em memória respeita o ciclo de vida da Lambda (instância warm
reutiliza). Reduz custo de SSM calls em ~95%.

## Configuração no Spring Boot 4

PowerTools usa AspectJ para interceptar anotações. Configure no `pom.xml`:

```xml
<plugin>
    <groupId>dev.aspectj</groupId>
    <artifactId>aspectj-maven-plugin</artifactId>
    <version>1.14</version>
    <configuration>
        <complianceLevel>${java.version}</complianceLevel>
        <aspectLibraries>
            <aspectLibrary>
                <groupId>software.amazon.lambda</groupId>
                <artifactId>powertools-logging</artifactId>
            </aspectLibrary>
            <aspectLibrary>
                <groupId>software.amazon.lambda</groupId>
                <artifactId>powertools-metrics</artifactId>
            </aspectLibrary>
            <aspectLibrary>
                <groupId>software.amazon.lambda</groupId>
                <artifactId>powertools-tracing</artifactId>
            </aspectLibrary>
        </aspectLibraries>
    </configuration>
    <executions>
        <execution>
            <goals>
                <goal>compile</goal>
                <goal>test-compile</goal>
            </goals>
        </execution>
    </executions>
</plugin>
```

GraalVM Native processa AspectJ via build-time weaving — não há overhead
em runtime. O `aspectj-maven-plugin` gera bytecode com aspectos já
incorporados antes do GraalVM compilar.

`application.properties`:

```properties
powertools.logger.log-event=true
powertools.metrics.namespace=${POWERTOOLS_METRICS_NAMESPACE:MyApp}
powertools.tracing.service=${POWERTOOLS_SERVICE_NAME:lambda-java}
```

Variáveis de ambiente correspondentes no `template.yaml`:

```yaml
Environment:
  Variables:
    POWERTOOLS_SERVICE_NAME: !Ref AWS::StackName
    POWERTOOLS_METRICS_NAMESPACE: !Ref AWS::StackName
    POWERTOOLS_LOG_LEVEL: INFO
    POWERTOOLS_LOGGER_LOG_EVENT: true
    POWERTOOLS_TRACER_CAPTURE_RESPONSE: true
    POWERTOOLS_TRACER_CAPTURE_ERROR: true
```
