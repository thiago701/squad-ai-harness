# Referência — Health Probes e Graceful Shutdown (liveness/readiness/startup, K8s/ECS, 3 fases do shutdown)

> Parte da skill `engenheiro-devops`. Carregue sob demanda. Hub: `../SKILL.md`.
> Movido verbatim de `observabilidade.md` § "Health Probes e Graceful Shutdown" (ciclo 6a do Loop V3, 2026-07-09).

### Health Probes e Graceful Shutdown — Obrigatórios para Cloud Native

Todo serviço em ECS, Kubernetes ou qualquer orquestrador de containers DEVE implementar health probes e graceful shutdown. Sem isso, deploys causam downtime e containers são reciclados desnecessariamente.

#### Spring Boot 4 — Configuração Mínima Obrigatória

```properties
# application.properties — health probes para orquestradores
management.endpoint.health.probes.enabled=true
management.health.livenessState.enabled=true
management.health.readinessState.enabled=true

# Graceful shutdown — essencial para zero-downtime deploys
server.shutdown=graceful
spring.lifecycle.timeout-per-shutdown-phase=30s

# Endpoints expostos para o orquestrador
management.endpoints.web.exposure.include=health,info,prometheus
```

#### Liveness vs Readiness — Quando Cada Um Falha

```
LIVENESS (/actuator/health/liveness):
  "A aplicação está viva?"
  Se falhar → orquestrador REINICIA o container
  Deve verificar: JVM rodando, não está em deadlock
  NÃO deve verificar: banco, cache, serviços externos
  Por que: se o banco cai, reiniciar o app não resolve nada

READINESS (/actuator/health/readiness):
  "A aplicação está pronta para receber tráfego?"
  Se falhar → orquestrador PARA DE ENVIAR tráfego (mas não reinicia)
  Deve verificar: banco conectado, cache acessível, migrations rodaram
  Útil durante: startup (enquanto carrega caches) e degradação parcial
```

#### ECS Task Definition com Health Check

```json
{
  "healthCheck": {
    "command": ["CMD-SHELL", "curl -f http://localhost:8080/actuator/health/liveness || exit 1"],
    "interval": 30,
    "timeout": 5,
    "retries": 3,
    "startPeriod": 60
  }
}
```

#### Kubernetes Probes — Semântica Canônica (GLOSSARIO §4)

Referência: **GLOSSARIO.md §4 — Health Probes**. A seguir, expansão completa alinhada a Kubernetes.

| Probe | Endpoint | Semântica | Ação em falha |
|-------|----------|-----------|---|
| **Liveness** | `/actuator/health/liveness` | A JVM está viva e sem deadlock? | Pod é **reiniciado** (SIGTERM + SIGKILL) |
| **Readiness** | `/actuator/health/readiness` | App pronta para tráfego (banco ok, cache quente, circuit breakers fechados)? | Pod **removido do load balancer** (tráfego deixa de ser enviado) |
| **Startup** | `/actuator/health/liveness` (customizado) | App ainda está inicializando? Desabilita liveness/readiness enquanto startup não passa. | Pod continua em startup, **não é reiniciado** |

**Regra Crítica (GLOSSARIO §4):** Liveness **nunca** deve checar dependências externas (banco, cache, APIs). Senão uma indisponibilidade do banco reinicia todos os pods, piorando a situação.

```yaml
# ── Kubernetes Pod Spec com 3 probes alinhadas ao GLOSSARIO ──
apiVersion: v1
kind: Pod
metadata:
  name: pedidos-api
spec:
  containers:
  - name: app
    image: pedidos-api:latest
    ports:
    - containerPort: 8080
    
    # ── LIVENESS PROBE ──
    # Pergunta: "JVM está viva?"
    # Resposta positiva: heap ok, não está em deadlock
    # Em falha: pod é reiniciado
    # NUNCA checar: database, external APIs, cache
    livenessProbe:
      httpGet:
        path: /actuator/health/liveness
        port: 8080
        httpHeaders:
        - name: Accept
          value: application/json
      
      # Timing: CDS + Spring Boot + JPA initialization
      # Java 25 + CDS: ~500-800ms
      # Spring context: ~2-3s
      # Inicializar = ~3-5s
      # Adicionar 2x margem = 10s de delay
      initialDelaySeconds: 10
      
      # Periodicidade: check rápido e contínuo (overhead mínimo)
      periodSeconds: 10
      
      # Timeout: HTTP simples deve responder em <1s
      timeoutSeconds: 2
      
      # Quantas falhas consecutivas antes de restart
      failureThreshold: 3         # 3 × 10s = 30s de tolerância antes de restart
    
    # ── READINESS PROBE ──
    # Pergunta: "Pronta para receber tráfego?"
    # Resposta positiva: database conectado, cache aquecido, migrations completadas
    # Em falha: pod é removido do load balancer (sem restart)
    # CAN check: database, dependências externas (se críticas)
    readinessProbe:
      httpGet:
        path: /actuator/health/readiness
        port: 8080
        httpHeaders:
        - name: Accept
          value: application/json
      
      # Delay: dar tempo para estabelecer conexões de banco
      # CDS + Spring + JPA + DB connection pool init
      # Estimado: ~5-10s (dependendo do RDS latency)
      initialDelaySeconds: 15
      
      # Periodicidade: check frequente para detectar degradação rápido
      periodSeconds: 5
      
      # Timeout: pode incluir query ao banco (até 3s)
      timeoutSeconds: 3
      
      # FailureThreshold: 2-3 falhas antes de drena LB
      failureThreshold: 2         # 2 × 5s = 10s antes de drenaço
    
    # ── STARTUP PROBE (novo em K8s 1.16+) ──
    # Pergunta: "App ainda está inicializando?"
    # Resposta: se ainda em startup, desabilita liveness/readiness
    # Útil: para JVMs lentas, migrations longas, cache pre-warming
    # Em falha: pod é reiniciado
    startupProbe:
      httpGet:
        path: /actuator/health/liveness
        port: 8080
      
      # Delay inicial mínimo
      initialDelaySeconds: 5
      
      # Checagem mais frequente durante startup
      periodSeconds: 5
      
      # failureThreshold × periodSeconds = tempo total tolerado
      # 30 × 5s = 150s (2.5 min) para Java + Flyway + cache warmup
      failureThreshold: 30
    
    resources:
      requests:
        memory: "512Mi"
        cpu: "250m"
      limits:
        memory: "1Gi"
        cpu: "500m"
  
  # Graceful shutdown (GLOSSARIO §5)
  terminationGracePeriodSeconds: 45
```

#### Cálculo de `initialDelaySeconds` — Fórmula Prática

Baseado em medições reais de Java 25 + Spring Boot 4 + JPA:

```
initialDelaySeconds(liveness) = 2 × (CDS + Spring_startup + JPA_init)

Exemplo:
  CDS activation:     200ms
  Spring context:    2000ms  (pode chegar a 3-4s com múltiplos beans)
  JPA EntityManager:  1000ms
  ─────────────────────────
  Total estimated:   3200ms ≈ 3.2s
  
  Safety factor: 3x
  initialDelaySeconds = 3.2s × 3 = ~10s (use 10-15s em produção)

Para readiness:
  + Database connection pool: 1-2s (connection to RDS)
  + Health indicator query:   100-500ms
  
  initialDelaySeconds = 10s + 5s (extra para RDS) = 15s
```

#### Troubleshooting: Pod em CrashLoopBackOff com 137

Código 137 = SIGKILL (processo morto sem shutdown limpo). Causas típicas:

```
CrashLoopBackOff 137 diagnóstico:

1. OOM Kill (Out of Memory)
   → kubectl describe pod → "OOMKilled" in LastState
   → Aumentar memory.limits
   → Revisar heap: -Xmx deve ser < limits.memory

2. Liveness falha porque checa banco (antipadrão!)
   → Liveness faz query ao DB → DB lento → timeout
   → Restart de novo → CrashLoop
   → Solução: remover database check de liveness
   
3. Startup lento demais (Java 25 sem CDS)
   → initialDelaySeconds insuficiente
   → startup probe falha antes de liveness estar pronto
   → Aumentar initialDelaySeconds ou failureThreshold de startup probe

4. Virtual Threads bloqueadas (pinned threads)
   → App inicia mas liveness falha ao verificar thread status
   → Verificar: -Djdk.tracePinnedThreads=full em logs
   → Corrigir code que faz thread pinning (synchronized, native calls)

Debug script:
  $ kubectl logs -f <pod-name>                    # Ver logs da app
  $ kubectl describe pod <pod-name>               # Ver eventos (OOMKilled, etc)
  $ kubectl get pod <pod-name> -o yaml            # Ver config, recursos
  $ kubectl exec -it <pod-name> -- jps -l        # Ver processos Java
  $ kubectl exec -it <pod-name> -- top           # Ver memória/CPU atual
```

#### Exemplo Completo: Deployment com 3 Probes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pedidos-api
  namespace: default
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 1
  selector:
    matchLabels:
      app: pedidos-api
  template:
    metadata:
      labels:
        app: pedidos-api
    spec:
      # Rolling update com graceful shutdown
      terminationGracePeriodSeconds: 45
      
      containers:
      - name: app
        image: 111111111111.dkr.ecr.us-east-1.amazonaws.com/pedidos-api:v1.2.3
        imagePullPolicy: IfNotPresent
        
        ports:
        - name: http
          containerPort: 8080
          protocol: TCP
        
        env:
        - name: SPRING_PROFILES_ACTIVE
          value: "k8s,prod"
        - name: SPRING_DATASOURCE_URL
          value: "jdbc:postgresql://postgres-svc:5432/pedidos"
        - name: JAVA_TOOL_OPTIONS
          value: "-XX:+UseG1GC -Xms256m -Xmx512m"
        
        # ── STARTUP PROBE (priority: desabilita outras enquanto rodando) ──
        startupProbe:
          httpGet:
            path: /actuator/health/liveness
            port: http
            scheme: HTTP
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 1
          failureThreshold: 30          # 150s total
        
        # ── LIVENESS PROBE (restart se falhar) ──
        livenessProbe:
          httpGet:
            path: /actuator/health/liveness
            port: http
            scheme: HTTP
          initialDelaySeconds: 15
          periodSeconds: 10
          timeoutSeconds: 2
          failureThreshold: 3
          successThreshold: 1
        
        # ── READINESS PROBE (drain LB se falhar) ──
        readinessProbe:
          httpGet:
            path: /actuator/health/readiness
            port: http
            scheme: HTTP
          initialDelaySeconds: 20
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 2
          successThreshold: 1
        
        # Resources
        resources:
          requests:
            cpu: 250m
            memory: 512Mi
          limits:
            cpu: 500m
            memory: 1Gi
        
        # Security
        securityContext:
          runAsNonRoot: true
          runAsUser: 1000
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop:
              - ALL
        
        volumeMounts:
        - name: tmp
          mountPath: /tmp
      
      volumes:
      - name: tmp
        emptyDir:
          medium: Memory
          sizeLimit: 512Mi
      
      # Affinity rules (distribuir pods entre nodes)
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - pedidos-api
              topologyKey: kubernetes.io/hostname

---
# Service para expor deployment
apiVersion: v1
kind: Service
metadata:
  name: pedidos-api-svc
spec:
  type: ClusterIP
  selector:
    app: pedidos-api
  ports:
  - name: http
    port: 8080
    targetPort: http
    protocol: TCP
```

#### Graceful Shutdown — 3 Fases Nomeadas (GLOSSARIO §5)

Referência canônica: **GLOSSARIO.md §5 — Graceful Shutdown**. Implementação em Java 25 + Spring Boot 4.

O encerramento gracioso divide-se em **3 fases distintas**, cada uma com ação e duração específica:

```
┌──────────────────────────────────────────────────────────────────┐
│ GRACEFUL SHUTDOWN — 3 FASES (Duração total: ~45 segundos)       │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  FASE 1: REJECT (5-10s)                                          │
│  ├─ Orquestrador envia SIGTERM ao container                      │
│  ├─ `/actuator/health/readiness` passa a retornar 503            │
│  ├─ Load Balancer detecta 503 → drena nova carga                 │
│  ├─ Requests em voo: CONTINUAM sendo processadas                 │
│  └─ Duração típica: 5-10s (LB rebalanceia)                       │
│                                                                   │
│  ↓                                                                 │
│                                                                   │
│  FASE 2: DRAIN (15-30s)                                          │
│  ├─ Sem nova carga (readiness=503)                               │
│  ├─ Requests em voo aguardam conclusão                           │
│  ├─ Timeout máximo: `spring.lifecycle.timeout-per-shutdown-phase` │
│  ├─ Virtual Threads em execução: aguardadas normalmente          │
│  ├─ HTTP clients: aguardam response do upstream                  │
│  ├─ SQS/SNS listeners: recusam novo message, aguardam processamento │
│  └─ Duração típica: 15-30s (requests concluem)                   │
│                                                                   │
│  ↓                                                                 │
│                                                                   │
│  FASE 3: CLOSE (2-5s)                                            │
│  ├─ HikariCP encerra conexões de banco (max 5s)                  │
│  ├─ Redis/Memcached: clients.close()                             │
│  ├─ HTTP clients: shutdown()                                     │
│  ├─ SQS/SNS clients: close() (flushes pending acks)              │
│  ├─ OpenTelemetry exporter: flushes spans/traces                 │
│  ├─ JVM encerra (exit code 0)                                    │
│  └─ Duração típica: 2-5s                                         │
│                                                                   │
│  ↓                                                                 │
│                                                                   │
│  SIGKILL (se processo ainda vivo após terminationGracePeriodSeconds) │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

**Fase 1: Reject** — Parar de aceitar novas requests

```properties
# application.properties — habilitar graceful shutdown em Spring Boot 4
server.shutdown=graceful

# Timeout total para drenaço (covers Fase 2 + Fase 3)
spring.lifecycle.timeout-per-shutdown-phase=30s

# Health probes
management.endpoint.health.probes.enabled=true
management.health.livenessState.enabled=true
management.health.readinessState.enabled=true
```

Quando `SIGTERM` é recebido:
1. Spring Boot ativa `gracefulShutdown`
2. `/actuator/health/readiness` passa a retornar `HTTP 503`
3. Load Balancer (ALB, NLB, K8s Service) detecta 503
4. Nova carga é redirecionada para outros pods/tasks
5. **Requests em voo continuam sendo processadas**

```java
// Exemplo: verificar estado de shutdown em logs
@Component
public class ShutdownListener implements ApplicationListener<ContextClosedEvent> {

    private static final Logger LOG = LoggerFactory.getLogger(ShutdownListener.class);

    @Override
    public void onApplicationEvent(ContextClosedEvent event) {
        LOG.info("=== FASE 1: REJECT — Readiness probe now returns 503 ===");
        LOG.info("Load balancer will drain new requests within 5-10 seconds");
    }
}
```

**Fase 2: Drain** — Aguardar requests em voo

```properties
# Duração máxima para FASE 2 (não para Fase 1)
spring.lifecycle.timeout-per-shutdown-phase=30s
```

Spring Boot internamente:
1. Para de aceitar novas conexões
2. Aguarda todas as threads ativas (virtual ou platform threads)
3. Se usar Virtual Threads (Java 25): podem ser centenas, todas aguardadas
4. Timeout: se alguma request levar > 30s, é forcibly encerrada (não gracioso)

```java
// ANTI-PADRÃO: request que nunca retorna
@GetMapping("/long-operation")
public ResponseEntity<?> longOperation() throws InterruptedException {
    Thread.sleep(60_000);  // 60 segundos — vai ser killed durante DRAIN
    return ResponseEntity.ok("Done");
}

// PADRÃO: usar timeout em chamadas externas
@GetMapping("/safe-long-operation")
public ResponseEntity<?> safeLongOperation() {
    try {
        // RestClient com timeout
        var response = restClient.get()
            .uri("https://slow-api.example.com/data")
            .retrieve()
            .toEntity(String.class);
        return ResponseEntity.ok(response);
    } catch (ResourceAccessException e) {
        LOG.warn("Request timeout during drain phase", e);
        return ResponseEntity.status(503).build();
    }
}
```

```java
// Bean que limpa recursos durante FASE 2
@Component
public class ResourceCleanupListener {

    private final HikariDataSource dataSource;
    private final SqsAsyncClient sqsClient;
    private final RestClient restClient;

    public ResourceCleanupListener(HikariDataSource dataSource, 
                                   SqsAsyncClient sqsClient,
                                   RestClient restClient) {
        this.dataSource = dataSource;
        this.sqsClient = sqsClient;
        this.restClient = restClient;
    }

    // NUNCA usar @PreDestroy para recursos críticos
    // Spring Boot gerencia Fase 3 automaticamente para beans standard
    // Mas você pode registrar custom shutdown hooks:

    public void registerShutdownHook() {
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            LOG.info("=== FASE 3: CLOSE — Cleaning up resources ===");
            // HikariCP close (automático)
            // SQS client close
            if (sqsClient != null) {
                sqsClient.close();
            }
            LOG.info("All resources closed");
        }));
    }
}
```

**Fase 3: Close** — Encerrar recursos

```java
// Exemplo: custom bean que fecha recurso externo
@Component
public class ExternalServiceClient {

    private final RestClient restClient;
    private static final Logger LOG = LoggerFactory.getLogger(ExternalServiceClient.class);

    public ExternalServiceClient(RestClient restClient) {
        this.restClient = restClient;
    }

    // Spring Boot 4 chama automaticamente métodos anotados durante shutdown
    @PreDestroy
    public void shutdown() {
        LOG.info("=== FASE 3: CLOSE — Closing ExternalServiceClient ===");
        // Se restClient tiver recurso que precisa cleanup:
        // restClient.shutdown();  // (se método existir)
    }
}
```

#### Kubernetes e ECS Configuration

**Kubernetes: `terminationGracePeriodSeconds`**

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app
spec:
  containers:
  - name: app
    image: app:latest
    lifecycle:
      preStop:
        exec:
          command: ["/bin/sh", "-c", "sleep 5"]  # Fase 1: 5s para LB drains
  
  # REGRA: deve ser > timeout-per-shutdown-phase (30s) + 10s de margem
  terminationGracePeriodSeconds: 45
```

Fluxo em Kubernetes:
```
1. Pod receive SIGTERM
2. preStop hook executa (5s — aguarda LB drain)
3. readiness probe retorna 503 (detectado pelo Service)
4. Drainagem de novo tráfego começa (simultâneo ao preStop)
5. preStop termina → Spring Boot DRAIN phase (até 30s)
6. terminationGracePeriodSeconds - 5 - 30 = 10s remaining
7. Se ainda rodando: SIGKILL
```

**ECS Fargate: `stopTimeout`**

```json
{
  "containerDefinitions": [
    {
      "name": "app",
      "image": "...",
      "stopTimeout": 45
    }
  ]
}
```

Fluxo em ECS:
```
1. Task receive SIGTERM
2. readiness health check falha (503 from app)
3. ALB drains new traffic (5-10s)
4. Spring Boot DRAIN phase (até 30s)
5. Total: 35-40s < stopTimeout: 45s ✓
6. If still running: SIGKILL
```

#### Checklist: Graceful Shutdown Completo

```
Configuração Spring Boot:
  □ server.shutdown=graceful
  □ spring.lifecycle.timeout-per-shutdown-phase=30s
  □ management.endpoint.health.probes.enabled=true
  □ Readiness probe configurada (GLOSSARIO §4)

Orquestrador (Kubernetes):
  □ terminationGracePeriodSeconds ≥ 45s
  □ preStop hook para dar tempo a LB drenar (opcional, recomendado)
  □ readinessProbe habilitada (LB consulta para drain)

Orquestrador (ECS):
  □ stopTimeout ≥ 45s
  □ Health check habilitado (ALB detecta falha)
  □ targetGroupAttributes: deregistration_delay.timeout_seconds ≥ 40s

Testes em Dev:
  □ Local: docker-compose with SIGTERM → validar que app draina requests
  □ Validar: curl /actuator/health/readiness durante shutdown → deve ser 503
  □ Validar: requests em voo completam antes de JVM morrer
  □ Stress test: many concurrent requests → verifica se DRAIN aguarda todas
```

---

#### Checklist de Health Probes

```
□ Liveness probe configurada (NÃO verifica dependências externas)
□ Readiness probe configurada (verifica banco, cache, dependências)
□ Graceful shutdown habilitado (server.shutdown=graceful)
□ Timeout do orquestrador > timeout do Spring Boot
□ startPeriod/initialDelaySeconds suficiente para startup Java
□ Health check testado localmente com docker-compose
□ Zero downtime validado em deploy (rolling update)
```
