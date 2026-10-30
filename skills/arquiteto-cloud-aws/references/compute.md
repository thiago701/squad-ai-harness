# Referência — Compute (Lambda, ECS Fargate, EC2)

> **[AN] Leitura obrigatória:** os números de cold start, memória e custo desta página são ordens de
> grandeza de referência, não metas nem garantias. Antes de decidir entre ECS e Lambda ou entre
> SnapStart e GraalVM, aplique os critérios e o protocolo de medição de `java-ecs-lambda.md`.

> Parte da skill `arquiteto-cloud-aws`. Carregue este arquivo sob demanda quando a tarefa tocar este eixo. Hub: `../SKILL.md`.
### Compute — Lambda, ECS Fargate, EC2

#### AWS Lambda — Serverless para APIs e Eventos

```
Casos de uso ideais:
  ✓ APIs REST com tráfego irregular ou baixo
  ✓ Processamento de eventos (S3, SQS, SNS, DynamoDB Streams)
  ✓ Jobs agendados (substituir cron servers)
  ✓ Webhooks e integrações
  ✓ ETL e transformações de dados

Free tier Lambda: 1 MILHÃO de invocações/mês + 400.000 GB-segundos — permanente, não expira

Limites importantes:
  - Timeout máximo: 15 minutos
  - Memória: 128MB a 10GB
  - Package size: 50MB zip / 250MB descomprimido (ou container até 10GB)
  - Cold start Java: ordem de grandeza de segundos sem otimização; **SnapStart** ou **GraalVM Native** reduzem —
    o ganho depende do cenário e só vale medido (protocolo em `java-ecs-lambda.md`)
  - Cold start Python: 100-500ms
```

```python
# Python Lambda com FastAPI usando Mangum — mesma API, deploy como Lambda
# pip install fastapi mangum aws-lambda-powertools

from fastapi import FastAPI
from mangum import Mangum
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit

logger  = Logger()   # structured logging para CloudWatch automaticamente
tracer  = Tracer()   # X-Ray tracing automático
metrics = Metrics()  # CloudWatch Metrics customizadas

app = FastAPI(title="Pedidos API")

@app.get("/pedidos/{pedido_id}")
@tracer.capture_method
async def buscar_pedido(pedido_id: int):
    logger.info("Buscando pedido", extra={"pedido_id": pedido_id})
    metrics.add_metric(name="BuscaPedido", unit=MetricUnit.Count, value=1)
    return pedido_service.buscar(pedido_id)

# Handler Lambda — Mangum adapta APIGW para ASGI (FastAPI/Starlette)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics
def handler(event, context):
    asgi_handler = Mangum(app, lifespan="off")
    return asgi_handler(event, context)
```

```java
// Java Lambda com Spring Cloud Function — Spring Boot 4, deploy como Lambda
// Lambda: use **SnapStart** (pouca config, reduz cold start) OU **GraalVM Native** (mais trabalho; meça o ganho no seu cenário)

@SpringBootApplication
public class PedidoLambdaApplication {
    public static void main(String[] args) {
        SpringApplication.run(PedidoLambdaApplication.class, args);
    }

    // Function<Input, Output> — Spring Cloud Function descobre automaticamente
    @Bean
    public Function<PedidoRequest, PedidoResponse> processarPedido(PedidoService service) {
        return request -> service.processar(request);
    }
}

// SAM template para deploy com SnapStart (zero cold start para Java)
/*
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Resources:
  PedidoFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: org.springframework.cloud.function.adapter.aws.FunctionInvoker::handleRequest
      Runtime: java25
      SnapStart:
        ApplyOn: PublishedVersions   # elimina cold start Java
      MemorySize: 512
      Timeout: 30
      Events:
        Api:
          Type: Api
          Properties:
            Path: /pedidos/{id}
            Method: GET
*/
```

#### SnapStart vs GraalVM Native Image — Tabela Comparativa

| Aspecto | SnapStart | GraalVM Native Image |
|---|---|---|
| **Cold start** | 100–300ms | 10–50ms |
| **Build time CI** | ~5min | ~2–5min |
| **Runtime overhead** | ~5% de CPU | 0% (nativo) |
| **Reflection / Proxies dinâmicas** | Sim, automático | Requer `reflect-config.json` + análise estática |
| **Custo memória Lambda** | Normal (512MB típico) | 30–50% menor (256–384MB) |
| **Custo invoke (cold start)** | +2x primeiro invoke (restore penalty) | 0 (sem overhead extra) |
| **Maturidade Spring Boot 4** | Oficial + estável (v3.2+) | Oficial via `native` profile |
| **Java features** | 100% (records, sealed, pattern matching, VT) | 99% (reflection, classloader customizado, JNI limitados) |
| **TTL recomendado** | 300–600s (warm cache) | 30–60s (inicia em < 50ms) |
| **Tipicidade de uso** | **APIs REST gerais, 80% dos casos** | **Latência crítica < 100ms, cost-sensitive** |
| **Exemplo de ROI** | 100k invocações/mês: $0.15 overhead cold start | 100k invocações/mês: $50 economia RAM |

**Decisão rápida:**
- ✓ **SnapStart** → Escolha padrão: zero config, suporta tudo, 100–300ms é aceitável
- ✓ **GraalVM Native** → Latência crítica (< 100ms exigido), cost-sensitive, ou picos de cold starts

**Exemplo SnapStart (sem nenhuma config extra):**

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Resources:
  MyFunction:
    Type: AWS::Serverless::Function
    Properties:
      Runtime: java25
      SnapStart:
        ApplyOn: PublishedVersions    # ← Único necessário — elimina cold start
      # resto da config normal
```

**Exemplo GraalVM Native (build profile Maven):**

```xml
<!-- pom.xml — Profile nativo ativado em CI para build -->
<profiles>
  <profile>
    <id>native</id>
    <activation>
      <property>
        <name>native</name>
      </property>
    </activation>
    <properties>
      <repackage.classifier>exec</repackage.classifier>
      <maven.test.skip>true</maven.test.skip>
    </properties>
    <build>
      <plugins>
        <plugin>
          <groupId>org.graalvm.buildtools</groupId>
          <artifactId>native-maven-plugin</artifactId>
          <version>0.10.1</version>
          <extensions>true</extensions>
          <executions>
            <execution>
              <id>build-native</id>
              <goals>
                <goal>compile-no-fork</goal>
              </goals>
              <phase>package</phase>
            </execution>
          </executions>
        </plugin>
      </plugins>
    </build>
  </profile>
</profiles>
```

```bash
# Build nativo (2–5min CI time)
mvn clean package -Pnative

# Resultado: binário de ~100MB, boot em 10–50ms
```

#### Lambda Response Streaming — Redução de TTFB para APIs generativas

Lambda Response Streaming envia chunks ao cliente antes da função terminar — essencial para
APIs de LLM (Bedrock, OpenAI) e qualquer resposta > 1s. Reduz TTFB (time-to-first-byte) de
segundos para milissegundos. Suporta payload até **20MB** (vs 6MB no modo buffered).

```java
// Java — AWS Lambda Java Events com streaming
public class StreamingHandler implements RequestStreamHandler {
    private final BedrockRuntimeAsyncClient bedrock = BedrockRuntimeAsyncClient.create();

    @Override
    public void handleRequest(InputStream in, OutputStream out, Context ctx) throws IOException {
        var req = MAPPER.readValue(in, ChatRequest.class);
        var request = ConverseStreamRequest.builder()
            .modelId("anthropic.claude-sonnet-4-5-20250929-v1:0")
            .messages(Message.builder().role(ConversationRole.USER).content(ContentBlock.fromText(req.prompt())).build())
            .build();

        bedrock.converseStream(request, ConverseStreamResponseHandler.builder()
            .subscriber(ConverseStreamResponseHandler.Visitor.builder()
                .onContentBlockDelta(delta -> {
                    try {
                        out.write(delta.delta().text().getBytes(UTF_8));
                        out.flush();   // chunk vai para o cliente imediatamente
                    } catch (IOException e) { throw new UncheckedIOException(e); }
                }).build())
            .build())
            .join();
    }
}
```

```yaml
# SAM — habilitar streaming
Resources:
  StreamingFn:
    Type: AWS::Serverless::Function
    Properties:
      InvokeMode: RESPONSE_STREAM    # ← Habilita streaming
      FunctionUrlConfig:
        AuthType: AWS_IAM
        InvokeMode: RESPONSE_STREAM
```

**Quando usar:** chat generativo, relatórios paginados grandes, SSE/EventStream, downloads.

#### CloudWatch Application Signals — APM gerenciado zero-config

CloudWatch Application Signals é o **APM gerenciado** da AWS (equivalente Datadog/New Relic) que
instrumenta Java, Node.js, Python e .NET via OpenTelemetry agent — **zero código** de instrumentação.

```yaml
# ECS Task Definition — habilitar Application Signals
{
  "containerDefinitions": [{
    "name": "app",
    "image": "my-app:v1",
    "environment": [
      { "name": "OTEL_AWS_APPLICATION_SIGNALS_ENABLED", "value": "true" },
      { "name": "OTEL_METRICS_EXPORTER", "value": "none" },
      { "name": "OTEL_EXPORTER_OTLP_PROTOCOL", "value": "http/protobuf" }
    ],
    "dependsOn": [{ "containerName": "otel-agent", "condition": "START" }]
  },
  {
    "name": "otel-agent",
    "image": "public.ecr.aws/aws-observability/aws-otel-collector:latest",
    "essential": true
  }]
}
```

**Saída automática** (sem código):
- Service Map com latência p50/p95/p99 por operação
- SLOs configuráveis (ex: "p99 de `POST /pedidos` < 500ms")
- RED metrics (Rate, Errors, Duration) por serviço
- Correlação automática com CloudWatch Logs e X-Ray Traces

**Por que preferir** a APMs externos: fica no mesmo console, IAM nativo, ~90% mais barato para
workloads AWS, zero egress cost.

#### IAM Identity Center — substitui IAM Users para humanos

**IAM Users para humanos é deprecated em 2025+**. Use sempre **IAM Identity Center** (AWS SSO) para:

- Federação com Google Workspace / Azure AD / Okta
- Permission Sets versionados por conta e role
- Acesso via `aws sso login` (tokens rotacionam automaticamente)
- Acesso CLI/Console unificado com MFA

```bash
# Desenvolvedor loga uma vez, acessa todas as contas
aws configure sso --profile empresa-prod
aws sso login --profile empresa-prod

# CLI/SDK descobre credenciais automaticamente
aws s3 ls --profile empresa-prod
```

**IAM Users** ficam restritos a: credenciais programáticas de serviços legados que não suportam
IRSA/roles. Mesmo CI/CD moderno usa **GitHub Actions Workload Identity Federation** (OIDC
trust policy com role assumida, zero credenciais long-lived).

#### EKS Auto Mode — Kubernetes gerenciado zero-ops

EKS Auto Mode (2024+) é o equivalente Fargate para EKS: AWS gerencia nodes, autoscaling,
networking, balanceamento de carga e upgrade de nós. **Não há EC2 para pagar**, só o pod.

```yaml
# CDK / eksctl — cluster Auto Mode
apiVersion: eksctl.io/v1alpha5
kind: ClusterConfig
metadata:
  name: prod
  region: us-east-1
autoModeConfig:
  enabled: true              # ← EKS Auto Mode
  nodePools: ["general-purpose", "system"]
```

**Quando preferir EKS Auto Mode sobre ECS Fargate:**
- Equipe já domina Kubernetes
- Necessidade de GitOps (ArgoCD/Flux) maduro
- Workloads de múltiplas linguagens com padrões k8s (sidecars, operators, service mesh)
- Migração gradual de EKS self-managed

**Quando preferir ECS Fargate:**
- Equipe não tem expertise k8s
- Workload simples (stateless REST + jobs)
- Menor cognitive load e operational overhead

#### Aurora DSQL — Postgres serverless multi-region ativo-ativo

Aurora DSQL (GA 2025) é Postgres compatível, **serverless**, **multi-região ativo-ativo**, com
consistência forte global (5ms regional, 100ms cross-region). Substitui DynamoDB Global Tables
para casos que precisam de SQL + multi-region.

```java
// Spring Boot — driver Postgres padrão, endpoint DSQL
spring.datasource.url=jdbc:postgresql://<cluster-id>.dsql.us-east-1.on.aws:5432/postgres
spring.datasource.hikari.data-source-properties.sslmode=verify-full

// IAM Database Authentication obrigatória — token rotaciona a cada 15min
```

**Quando usar:** apps multi-região com usuários globais, compliance (dados em região específica
com fallback), operações idempotentes distribuídas.

**Quando NÃO usar:** stored procedures pesados, extensões PostgreSQL específicas (PostGIS, pg_cron
— subset suportado), queries com > 10k rows por transação.

**Runbook operacional canônico (v8.4):** `arquiteto-cloud-aws/references/aurora-dsql-failover.md`
— drill trimestral obrigatório, pré-requisitos do cluster (3 regiões ativas + Route 53 health
checks + kill switch regional + HikariCP com timeouts curtos), 4 cenários de injeção (A kill switch,
B AZ isolation, C região inteira, D latência via AWS FIS), log em `.reviews/failover-log.md`,
diferenças entre drill e incidente real. Cenário T4 do catálogo de tabletop em
`squad-ai/references/incident-response.md` aciona este runbook.

---

#### API Gateway — Rate Limiting, Validação e Versionamento

```
API Gateway é o ponto de entrada para APIs REST/HTTP — rate limiting, autenticação
e validação de request são responsabilidade dele, não do código da aplicação.

Free tier: 1 milhão de chamadas REST API + 1 milhão de chamadas HTTP API/mês (12 meses)
Pós-free: REST $3.50/milhão, HTTP $1.00/milhão (HTTP API é mais barato e suficiente para maioria)
```

```yaml
# SAM — API Gateway HTTP com throttling e autorização Cognito
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Globals:
  Api:
    # Rate limiting global — protege contra abuso sem código
    Throttle:
      BurstLimit: 100       # máximo de requests simultâneos
      RateLimit: 50          # requests por segundo sustentado

Resources:
  PedidosApi:
    Type: AWS::Serverless::HttpApi
    Properties:
      StageName: prod
      Auth:
        DefaultAuthorizer: CognitoAuth
        Authorizers:
          CognitoAuth:
            AuthorizationScopes:
              - pedidos/read
              - pedidos/write
            IdentitySource: $request.header.Authorization
            JwtConfiguration:
              issuer: !Sub "https://cognito-idp.${AWS::Region}.amazonaws.com/${UserPool}"
              audience:
                - !Ref UserPoolClient

  CriarPedidoFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: com.example.FunctionHandler::handleRequest
      Runtime: java21
      SnapStart:
        ApplyOn: PublishedVersions
      Events:
        CriarPedido:
          Type: HttpApi
          Properties:
            ApiId: !Ref PedidosApi
            Path: /v1/pedidos
            Method: POST
```

```yaml
# Request Validation — OpenAPI integrado ao API Gateway
# Rejeita requests inválidos ANTES de chegar na Lambda (economia de custo)
x-amazon-apigateway-request-validators:
  all:
    validateRequestBody: true
    validateRequestParameters: true

paths:
  /v1/pedidos:
    post:
      x-amazon-apigateway-request-validator: all
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [cliente_id, itens]
              properties:
                cliente_id:
                  type: string
                  format: uuid
                itens:
                  type: array
                  minItems: 1
                  items:
                    type: object
                    required: [produto_id, quantidade]
                    properties:
                      produto_id:
                        type: string
                      quantidade:
                        type: integer
                        minimum: 1
                        maximum: 100
```

```
API Versioning — estratégias no API Gateway:

  Recomendado (P1 — Simplicidade):
  ✓ URI Path: /v1/pedidos, /v2/pedidos — claro, fácil de rotear
  ✗ Header versioning: complexo, difícil de testar no browser

  Como rotear no API Gateway:
  - Versão no path → cada versão aponta para Lambda diferente (ou alias)
  - Stage variables → prod-v1, prod-v2 como stages separados
  - Lambda aliases → $LATEST para dev, v1/v2 para prod

Checklist API Gateway:
  □ Rate limiting configurado (Throttle global + por rota se necessário)
  □ Autorização Cognito ou Lambda Authorizer (NUNCA API aberta em prod)
  □ Request validation via OpenAPI schema (rejeita antes da Lambda)
  □ CORS configurado (AllowOrigins restrito, NUNCA '*' em prod)
  □ Custom domain com certificado ACM (HTTPS obrigatório)
  □ Access logs habilitados (CloudWatch)
  □ WAF associado para proteção contra DDoS/injection
```

---

#### ECS Fargate — Containers sem EC2

```
Quando usar ECS Fargate em vez de Lambda:
  ✓ Aplicação com estado de conexão (WebSocket, streaming)
  ✓ Processo > 15 minutos (limite do Lambda)
  ✓ Container existente que você não quer refatorar
  ✓ Carga constante onde Lambda ficaria mais caro

ECS Fargate — Stack recomendada:
  ✓ OpenJDK 25 (JIT) + CDS — startup ~800ms, throughput máximo
  ✗ GraalVM Native — overhead de build não justifica para containers long-running

Free tier Fargate: NÃO tem free tier — cobrado por vCPU/hora e GB/hora
Custo base: ~$10-15/mês por task de 0.25 vCPU + 0.5GB rodando 24/7
```

```yaml
# CDK TypeScript — ECS Fargate com Spring Boot Java
# (infraestrutura como código, não clique no console)
# Equivalente em Python: aws_cdk.aws_ecs

# task-definition simples que desenvolvedores entendem
Resources:
  PedidoService:
    Type: AWS::ECS::TaskDefinition
    Properties:
      Family: pedido-service
      NetworkMode: awsvpc
      RequiresCompatibilities: [FARGATE]
      Cpu: 256        # 0.25 vCPU — suficiente para início
      Memory: 512     # 512MB — Spring Boot cabe com tuning
      ContainerDefinitions:
        - Name: pedido-api
          Image: !Sub "${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com/pedido-api:latest"
          PortMappings:
            - ContainerPort: 8080
          Environment:
            - Name: SPRING_PROFILES_ACTIVE
              Value: aws
          Secrets:
            - Name: DB_PASSWORD
              ValueFrom: !Sub "arn:aws:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:pedido/db-password"
          LogConfiguration:
            LogDriver: awslogs
            Options:
              awslogs-group: /ecs/pedido-service
              awslogs-region: !Ref AWS::Region
              awslogs-stream-prefix: ecs
```

---

## ECS Fargate — Especialista Enterprise

> Para sistemas com 50K+ RPS sustentados, ECS Fargate é o sweet spot entre **Lambda (cold start, 15min limit, custo > 100M req)** e **EC2 (gestão de patching, AMI, scaling complexo)**. Domine cada knob.

### Capacity Provider Strategy — Mix FARGATE + FARGATE_SPOT

**Erro comum:** usar só `FARGATE` (caro 100% on-demand) ou só `FARGATE_SPOT` (interrupção em 2 min destrói SLO).

**Estratégia canônica enterprise:**

```json
{
  "capacityProviderStrategy": [
    { "capacityProvider": "FARGATE",      "base": 4, "weight": 1 },
    { "capacityProvider": "FARGATE_SPOT", "base": 0, "weight": 4 }
  ]
}
```

**Leitura:** sempre 4 tasks on-demand (base — cobre baseline mesmo se Spot for revogado em massa). Acima disso, 4:1 — para cada task on-demand adicional, 4 tasks Spot. Resultado: ~80% Spot economy, 20% on-demand resilience.

**Regra de proteção:** `minimumHealthyPercent: 100`, `maximumPercent: 200` durante deploys. Spot interruption handler envia `SIGTERM` 2min antes — graceful shutdown precisa fechar em tempo (ver `engenheiro-devops` Graceful Shutdown phases).

### Predictive Scaling (não reativo)

**Reativo (CPU > 70%)** falha em pico de Black Friday: até o auto-scaling reagir, p99 já degradou.

**Predictive Scaling** usa ML (Forecast) para prever carga 48h à frente:

```java
// CDK Java 25
ScalableTaskCount scalableTarget = service.autoScaleTaskCount(
    EnableScalingProps.builder()
        .minCapacity(8)            // nunca menos que 8 (multi-AZ + headroom)
        .maxCapacity(500)
        .build()
);

// Predictive — usa historical data
scalableTarget.scaleOnMetric("PredictiveScaling",
    BasicStepScalingPolicyProps.builder()
        .metric(service.metricCpuUtilization())
        .scalingSteps(List.of(
            ScalingInterval.builder().lower(50).change(+5).build(),
            ScalingInterval.builder().lower(70).change(+10).build(),
            ScalingInterval.builder().lower(85).change(+25).build(),
            ScalingInterval.builder().upper(30).change(-2).build()
        ))
        .adjustmentType(AdjustmentType.CHANGE_IN_CAPACITY)
        .cooldown(Duration.seconds(30))     // crítico: cooldown curto evita lag
        .build()
);

// Target tracking secundário (defesa em profundidade)
scalableTarget.scaleOnCpuUtilization("CpuTarget",
    CpuUtilizationScalingProps.builder()
        .targetUtilizationPercent(60)      // headroom 40% para spike
        .scaleInCooldown(Duration.seconds(300))
        .scaleOutCooldown(Duration.seconds(30))
        .build()
);

// Request count per target (mais previsível para HTTP)
scalableTarget.scaleOnRequestCount("RpsTarget",
    RequestCountScalingProps.builder()
        .requestsPerTarget(1000)            // 1000 RPS por task
        .targetGroup(targetGroup)
        .scaleOutCooldown(Duration.seconds(30))
        .build()
);
```

**Por que 3 políticas simultâneas:** ECS aplica o **maior** desired count entre todas as políticas. Predictive antecipa carga conhecida (Black Friday), CPU target trata picos não previstos, Request count escala linearmente com tráfego HTTP.

### ECS Service Connect (substitui App Mesh para 90% dos casos)

Service Connect é o **service mesh nativo do ECS** desde 2023. Sem sidecar Envoy gerenciado por você. Aprenda isto antes de instalar App Mesh ou Istio.

```java
// CDK Java
FargateService service = FargateService.Builder.create(this, "OrderService")
    .cluster(cluster)
    .taskDefinition(taskDef)
    .desiredCount(8)
    .capacityProviderStrategies(List.of(
        CapacityProviderStrategy.builder().capacityProvider("FARGATE").base(4).weight(1).build(),
        CapacityProviderStrategy.builder().capacityProvider("FARGATE_SPOT").weight(4).build()
    ))
    .serviceConnectConfiguration(ServiceConnectProps.builder()
        .namespace("production.local")
        .services(List.of(
            ServiceConnectService.builder()
                .portMappingName("http")
                .dnsName("orders")
                .port(8080)
                .build()
        ))
        .logDriver(LogDrivers.awsLogs(AwsLogDriverProps.builder()
            .streamPrefix("svc-connect")
            .build()))
        .build())
    .enableExecuteCommand(true)             // ECS Exec habilitado
    .circuitBreaker(DeploymentCircuitBreaker.builder()
        .rollback(true)                     // rollback automático em deploy falho
        .build())
    .build();
```

**Benefícios:**
- DNS interno automático (`orders.production.local:8080`)
- mTLS automático entre serviços
- Métricas L7 nativas (request count, errors, latency p50/p95/p99) sem instrumentação
- Circuit breaker server-side
- Outlier detection (ejeção de task com erro)

**Quando ainda usar App Mesh:** sistemas com lógica de roteamento complexa (canary por header, traffic mirroring entre versões). Para tudo mais, Service Connect é suficiente.

### Graviton (ARM) — 40% mais barato + 20% mais rápido

**Não há razão técnica para não usar Graviton em Java 25.** OpenJDK 25 tem otimizações ARM excelentes; Spring Boot 4 roda nativamente.

```java
TaskDefinition taskDef = FargateTaskDefinition.Builder.create(this, "TaskDef")
    .cpu(2048)                              // 2 vCPU
    .memoryLimitMiB(4096)
    .runtimePlatform(RuntimePlatform.builder()
        .cpuArchitecture(CpuArchitecture.ARM64)        // Graviton
        .operatingSystemFamily(OperatingSystemFamily.LINUX)
        .build())
    .build();
```

**Build multi-arch obrigatório no CI:**

```dockerfile
# Build multi-arch com BuildKit
FROM --platform=$BUILDPLATFORM eclipse-temurin:25-jdk AS build
ARG TARGETARCH
WORKDIR /app
COPY . .
RUN ./mvnw -T 1C package -DskipTests

FROM --platform=$TARGETPLATFORM eclipse-temurin:25-jre-alpine
COPY --from=build /app/target/app.jar /app.jar
ENTRYPOINT ["java", "-jar", "/app.jar"]
```

```bash
docker buildx build --platform linux/amd64,linux/arm64 \
  -t 123.dkr.ecr.us-east-1.amazonaws.com/orders:1.2.3 \
  --push .
```

### Task Definition Tuning para Java 25 + Virtual Threads

```json
{
  "family": "orders",
  "cpu": "2048",
  "memory": "4096",
  "networkMode": "awsvpc",
  "runtimePlatform": {
    "cpuArchitecture": "ARM64",
    "operatingSystemFamily": "LINUX"
  },
  "executionRoleArn": "arn:aws:iam::123:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::123:role/ordersTaskRole",
  "containerDefinitions": [{
    "name": "app",
    "image": "123.dkr.ecr.us-east-1.amazonaws.com/orders:1.2.3",
    "essential": true,
    "readonlyRootFilesystem": true,
    "user": "1000",
    "ulimits": [
      { "name": "nofile", "softLimit": 65536, "hardLimit": 65536 }
    ],
    "environment": [
      { "name": "JAVA_TOOL_OPTIONS",
        "value": "-XX:+UseZGC -XX:+ZGenerational -XX:MaxRAMPercentage=75 -XX:InitialRAMPercentage=75 -XX:+ExitOnOutOfMemoryError -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/tmp -Djdk.tracePinnedThreads=short -XX:SharedArchiveFile=/app/app-cds.jsa" },
      { "name": "SPRING_PROFILES_ACTIVE", "value": "production" }
    ],
    "healthCheck": {
      "command": ["CMD-SHELL", "curl -fsS http://localhost:8080/actuator/health/liveness || exit 1"],
      "interval": 10,
      "timeout": 3,
      "retries": 3,
      "startPeriod": 60
    },
    "stopTimeout": 40,
    "logConfiguration": {
      "logDriver": "awsfirelens",
      "options": {
        "Name": "cloudwatch_logs",
        "region": "us-east-1",
        "log_group_name": "/ecs/orders",
        "log_stream_prefix": "from-fluentbit",
        "auto_create_group": "true"
      }
    },
    "mountPoints": [
      { "sourceVolume": "tmp", "containerPath": "/tmp" }
    ]
  }, {
    "name": "log_router",
    "image": "public.ecr.aws/aws-observability/aws-for-fluent-bit:stable",
    "essential": true,
    "firelensConfiguration": {
      "type": "fluentbit",
      "options": { "enable-ecs-log-metadata": "true" }
    },
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/orders/firelens",
        "awslogs-region": "us-east-1",
        "awslogs-create-group": "true",
        "awslogs-stream-prefix": "firelens"
      }
    }
  }],
  "volumes": [
    { "name": "tmp", "host": {} }
  ]
}
```

**Pontos críticos:**
- `MaxRAMPercentage=75` deixa 25% para off-heap (Netty buffers, metaspace, threads, code cache)
- `ZGC Generational` para latência sub-ms (Java 25 ZGC é production-ready)
- `stopTimeout: 40` casado com `terminationGracePeriodSeconds` do Spring Boot
- `nofile 65536` para suportar milhares de Virtual Threads
- **FireLens + Fluent Bit** sidecar substitui o `awslogs` driver direto: 5x mais barato em CloudWatch Logs ingestion (compressão, batching) e suporta multi-destino (S3, OpenSearch, Datadog)
- `readonlyRootFilesystem: true` + tmpfs em `/tmp` para hardening

### ECS Exec — Debug em Produção sem SSH

```bash
aws ecs execute-command \
  --cluster production \
  --task arn:aws:ecs:us-east-1:123:task/production/abc \
  --container app \
  --interactive --command "/bin/sh"
```

Habilitado via `enableExecuteCommand: true`. Combinado com `ssm:StartSession` na task role + audit em CloudTrail. Substitui completamente bastion EC2.

### Blue/Green Deploy com CodeDeploy + ALB

```java
EcsDeploymentGroup.Builder.create(this, "BlueGreen")
    .application(codeDeployApp)
    .service(service)
    .blueGreenDeploymentConfig(EcsBlueGreenDeploymentConfig.builder()
        .blueTargetGroup(blueTg)
        .greenTargetGroup(greenTg)
        .listener(prodListener)
        .testListener(testListener)              // listener separado para smoke tests
        .deploymentApprovalWaitTime(Duration.minutes(5))   // janela de validação manual
        .terminationWaitTime(Duration.minutes(10))         // tempo para rollback rápido
        .build())
    .deploymentConfig(EcsDeploymentConfig.CANARY_10_PERCENT_5_MINUTES)
    .autoRollback(AutoRollbackConfig.builder()
        .failedDeployment(true)
        .stoppedDeployment(true)
        .deploymentInAlarm(true)
        .build())
    .alarms(List.of(p99LatencyAlarm, error5xxAlarm, cveCriticalAlarm))
    .build();
```

**Estratégias disponíveis:**

| Estratégia | Uso |
|------------|-----|
| `CANARY_10_PERCENT_5_MINUTES` | 10% por 5 min, depois 100% — produção padrão |
| `CANARY_10_PERCENT_15_MINUTES` | 10% por 15 min — mudanças com risco médio |
| `LINEAR_10_PERCENT_EVERY_3_MINUTES` | 10% a cada 3 min — mudanças com risco alto |
| `ALL_AT_ONCE` | nunca em produção, ok para staging |

---

