# Referência — Containers (Dockerfile multi-stage, hardening, Docker Compose)

> Parte da skill `engenheiro-devops`. Carregue sob demanda. Hub: `../SKILL.md`.
## Dockerfile — Padrões Obrigatórios

### Java 25 (Spring Boot 4) — Multi-stage

```dockerfile
# Stage 1: Build (Maven 4 via wrapper)
FROM eclipse-temurin:25-jdk-alpine AS build
WORKDIR /app
# Copia o wrapper primeiro para cachear o download do Maven 4
COPY .mvn/ .mvn/
COPY mvnw pom.xml ./
# Pré-resolve dependências (cache de layer do Docker reutiliza quando pom.xml não muda)
RUN ./mvnw -B dependency:go-offline
COPY src/ src/
RUN ./mvnw -B -T 1C -DskipTests package spring-boot:repackage

# Stage 2: Runtime
FROM eclipse-temurin:25-jre-alpine
WORKDIR /app
RUN addgroup -S app && adduser -S app -G app
COPY --from=build /app/target/*.jar app.jar
USER app
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s \
  CMD wget -qO- http://localhost:8080/actuator/health || exit 1
ENTRYPOINT ["java", "-XX:+UseZGC", "-jar", "app.jar"]
```

### Python 3.12+ (FastAPI) — Multi-stage

```dockerfile
# Stage 1: Build
FROM python:3.12-slim AS build
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir --prefix=/install .

# Stage 2: Runtime
FROM python:3.12-slim
WORKDIR /app
RUN addgroup --system app && adduser --system --group app
COPY --from=build /install /usr/local
COPY src/ src/
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Layered JARs — Docker Rebuild em Segundos

Spring Boot 4 gera JARs em camadas por padrão. Isso permite rebuilds Docker em segundos
porque só a camada do código da aplicação muda — dependências ficam em cache.

```dockerfile
# Dockerfile — multi-stage com layers otimizadas
FROM eclipse-temurin:25-jre-alpine AS builder
WORKDIR /app
COPY target/*.jar app.jar
RUN java -Djarmode=tools -jar app.jar extract --layers --destination extracted

FROM eclipse-temurin:25-jre-alpine
WORKDIR /app

# Camadas ordenadas por frequência de mudança (menos → mais)
COPY --from=builder /app/extracted/dependencies/ ./
COPY --from=builder /app/extracted/spring-boot-loader/ ./
COPY --from=builder /app/extracted/snapshot-dependencies/ ./
COPY --from=builder /app/extracted/application/ ./

# CDS para startup rápido em produção (~800ms)
# RUN java -XX:ArchiveClassesAtExit=app-cds.jsa -Dspring.context.exit=onRefresh -jar app.jar || true

EXPOSE 8080
ENTRYPOINT ["java", \
  "-XX:+UseG1GC", \
  "-XX:MaxGCPauseMillis=200", \
  "-XX:+UseStringDeduplication", \
  "org.springframework.boot.loader.launch.JarLauncher"]
```

Por que funciona:
```
  Camada "dependencies"       → ~80MB, muda raramente     → cached
  Camada "spring-boot-loader" → ~200KB, quase nunca muda  → cached
  Camada "snapshot-deps"      → variável                  → cached
  Camada "application"        → ~500KB-2MB, muda sempre   → rebuild

  Resultado: rebuild Docker após mudar código = 2-5 segundos (vs 30-60s sem layers)
```

### Container Security — Hardening Obrigatório

```dockerfile
# ── Dockerfile hardened para produção ──

# 1. Base distroless (sem shell, sem package manager = menor superfície de ataque)
FROM eclipse-temurin:25-jre-alpine AS runtime
# Alternativa mais segura: gcr.io/distroless/java21-debian12 (sem shell)

# 2. Usuário não-root (NUNCA rodar como root em produção)
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

# 3. Read-only filesystem onde possível
# Configurar no docker-compose ou ECS task definition:
#   readonlyRootFilesystem: true
#   tmpfs: ["/tmp"]

# 4. Health check no Dockerfile
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -qO- http://localhost:8080/actuator/health/liveness || exit 1
```

```
CHECKLIST DE CONTAINER SECURITY:
  □ Imagem base mínima (Alpine ou distroless, NUNCA ubuntu/debian full)
  □ Usuário não-root (USER appuser)
  □ Multi-stage build (sem ferramentas de build na imagem final)
  □ .dockerignore configurado (excluir .git, .env, node_modules, target)
  □ Scan de vulnerabilidades na CI (Trivy ou Grype)
  □ Pinning de versão de base image (tag específica, não :latest)
  □ Zero secrets na imagem (usar env vars ou Secrets Manager em runtime)
  □ Read-only filesystem em produção
```

```yaml
# GitHub Actions — Scan de vulnerabilidades com Trivy
- name: Scan container image
  uses: aquasecurity/trivy-action@0.28.0
  with:
    image-ref: ${{ env.ECR_REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
    format: 'sarif'
    output: 'trivy-results.sarif'
    severity: 'CRITICAL,HIGH'
    exit-code: '1'   # Falha o pipeline se encontrar CRITICAL/HIGH

- name: Generate SBOM (CycloneDX)
  run: ./mvnw -B org.cyclonedx:cyclonedx-maven-plugin:2.9.1:makeAggregateBom
  # Ou plugar no pom.xml como execution do phase 'verify'.
  # Gera: target/bom.json (CycloneDX JSON 1.5)

- name: Upload SBOM artifact
  uses: actions/upload-artifact@v4
  with:
    name: sbom
    path: target/bom.json

- name: SBOM vulnerability check (Dependency-Track)
  run: |
    curl -X POST "$DEPENDENCY_TRACK_URL/api/v1/bom" \
      -H "X-Api-Key: ${{ secrets.DTRACK_API_KEY }}" \
      -H "Content-Type: multipart/form-data" \
      -F "project=${{ env.PROJECT_UUID }}" \
      -F "bom=@target/bom.json"
```

```xml
<!-- pom.xml — CycloneDX Maven plugin (model 4.1.0) -->
<plugin>
  <groupId>org.cyclonedx</groupId>
  <artifactId>cyclonedx-maven-plugin</artifactId>
  <version>2.9.1</version>
  <executions>
    <execution>
      <phase>verify</phase>
      <goals>
        <goal>makeAggregateBom</goal>
      </goals>
    </execution>
  </executions>
  <configuration>
    <schemaVersion>1.5</schemaVersion>
    <outputFormat>json</outputFormat>
    <includeBomSerialNumber>true</includeBomSerialNumber>
    <includeCompileScope>true</includeCompileScope>
    <includeRuntimeScope>true</includeRuntimeScope>
    <includeTestScope>false</includeTestScope>
  </configuration>
</plugin>
```

**SBOM Checklist:**
- ✅ CycloneDX Maven plugin ligado ao phase `verify` do `pom.xml`
- ✅ SBOM gerado em cada build da CI (formato CycloneDX JSON 1.5)
- ✅ SBOM armazenado como artifact do pipeline
- ✅ Opcional: upload para Dependency-Track para monitoramento contínuo
- ✅ SBOM inclui dependências transitivas (runtime + compile scope)

```yaml
# .dockerignore — OBRIGATÓRIO em todo projeto
# .git
# .env
# .env.*
# *.md
# target/
# node_modules/
# .m2/
# **/*.log
```

### Container Read-only Filesystem

**Regra de segurança:** filesystems com permissão de escrita permitem que um invasor persista alterações, instale backdoors e modifique logs. Produção deve rodar com `readonlyRootFilesystem: true` — apenas `/tmp` e `/var/cache` (via tmpfs) são writable.

#### Dockerfile com Read-only Filesystem

```dockerfile
# Stage 1: Build
FROM eclipse-temurin:25-jdk-alpine AS build
WORKDIR /app
COPY .mvn/ .mvn/
COPY mvnw pom.xml ./
RUN ./mvnw -B dependency:go-offline
COPY src/ src/
RUN ./mvnw -B -T 1C -DskipTests package spring-boot:repackage

# Stage 2: Runtime (read-only filesystem)
FROM eclipse-temurin:25-jre-alpine
WORKDIR /app

# Preparar diretórios writable ANTES de marcar fs como read-only
RUN addgroup -S app && adduser -S app -G app && \
    mkdir -p /tmp/logs /tmp/cache && \
    chown -R app:app /tmp /app

# Copia artefatos
COPY --from=build --chown=app:app /app/target/*.jar app.jar

USER app
EXPOSE 8080

# Health check (read-only não afeta curl para localhost)
HEALTHCHECK --interval=30s --timeout=3s \
  CMD wget -qO- http://localhost:8080/actuator/health/liveness || exit 1

# Entrypoint com tmpdir e logging para stdout
ENTRYPOINT ["java", \
  "-Djava.io.tmpdir=/tmp", \
  "-XX:+UseG1GC", \
  "-jar", "app.jar"]
```

#### Spring Boot Configuration para Read-only Filesystem

```properties
# application.properties — redirecionar logs para stdout (ou tmpfs)
logging.level.root=INFO
# Para stdout + structured logging (recomendado):
logging.config=classpath:logback-spring.xml

# Diretórios de cache devem estar em /tmp (montado via tmpfs)
spring.cache.caffeine.cache-names=users,orders
# Se usar arquivo para cache, apontar para /tmp:
server.tomcat.basedir=/tmp
server.tomcat.accesslog.directory=/tmp

# Para H2 embedded (se usado em dev):
spring.h2.console.enabled=false
```

```xml
<!-- pom.xml — dependência para logging estruturado JSON -->
<dependency>
    <groupId>net.logstash.logback</groupId>
    <artifactId>logstash-logback-encoder</artifactId>
    <version>8.0</version>
</dependency>
```

```xml
<!-- logback-spring.xml — structured logging para stdout -->
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
    <encoder class="net.logstash.logback.encoder.LogstashEncoder">
      <includeContext>true</includeContext>
      <includeMdcData>true</includeMdcData>
      <customFields>{"service":"pedidos-api","environment":"prod"}</customFields>
    </encoder>
  </appender>

  <root level="INFO">
    <appender-ref ref="STDOUT" />
  </root>
</configuration>
```

#### ECS Task Definition com Read-only Filesystem

```json
{
  "containerDefinitions": [
    {
      "name": "app",
      "image": "111111111111.dkr.ecr.us-east-1.amazonaws.com/pedidos-api:latest",
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp"
        }
      ],
      "readonlyRootFilesystem": true,
      "mountPoints": [
        {
          "sourceVolume": "tmpfs-logs",
          "containerPath": "/tmp",
          "readOnly": false
        }
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8080/actuator/health/liveness || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ],
  "volumes": [
    {
      "name": "tmpfs-logs",
      "efsVolumeConfiguration": null,
      "fsxWindowsFileServerVolumeConfiguration": null,
      "dockerVolumeConfiguration": null,
      "host": null
    }
  ],
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "networkMode": "awsvpc"
}
```

**Nota:** Em ECS Fargate, não há suporte nativo a tmpfs. Alternativa:
- Redirecionar logs para CloudWatch Logs (via driver `awslogs`)
- Usar volume EBS se cache persistente for necessário
- Ou usar Amazon Linux 2 launch type com `tmpfs`

#### Kubernetes Pod Spec com Read-only Filesystem

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-pod
spec:
  containers:
  - name: app
    image: app:latest
    ports:
    - containerPort: 8080
    
    # Read-only root filesystem
    securityContext:
      readOnlyRootFilesystem: true
      runAsNonRoot: true
      runAsUser: 1000
      allowPrivilegeEscalation: false
      capabilities:
        drop:
          - ALL

    # Volumes writable para /tmp
    volumeMounts:
    - name: tmpfs-volume
      mountPath: /tmp
    - name: tmpfs-logs
      mountPath: /tmp/logs

    livenessProbe:
      httpGet:
        path: /actuator/health/liveness
        port: 8080
      initialDelaySeconds: 30
      periodSeconds: 10
      failureThreshold: 3

    readinessProbe:
      httpGet:
        path: /actuator/health/readiness
        port: 8080
      initialDelaySeconds: 20
      periodSeconds: 5
      failureThreshold: 2

  # Volumes: emptyDir = tmpfs em Kubernetes
  volumes:
  - name: tmpfs-volume
    emptyDir:
      medium: Memory
      sizeLimit: 512Mi
  - name: tmpfs-logs
    emptyDir:
      medium: Memory
      sizeLimit: 256Mi

  terminationGracePeriodSeconds: 45
```

#### Trivy Scan — Detectar Filesystem Writable

```bash
# Build imagem com read-only
docker build -t myapp:readonly .

# Scan com Trivy (deve PASSAR sem warnings de filesystem writable)
trivy image --severity HIGH,CRITICAL myapp:readonly

# Output esperado:
#  ✓ No HIGH or CRITICAL vulnerabilities found
#  ✓ Filesystem: read-only (verificado via docker inspect)
```

```yaml
# GitHub Actions — CI job para validar read-only filesystem
- name: Build container image
  run: docker build -t ${{ env.IMAGE_NAME }}:readonly .

- name: Verify read-only filesystem in Dockerfile
  run: |
    # Extrair o Dockerfile e validar presença de read-only markers
    grep -q "readonlyRootFilesystem" Dockerfile || \
      (echo "ERROR: readonlyRootFilesystem not configured" && exit 1)
    
    # Trivy scan
    docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
      aquasec/trivy:latest image --severity HIGH,CRITICAL \
      ${{ env.IMAGE_NAME }}:readonly
```

#### Checklist de Read-only Filesystem em CI

```bash
#!/bin/bash
# scripts/validate-readonly-fs.sh — rodado a cada PR

IMAGE="$1"
CONTAINER_NAME="test-readonly"

echo "=== Validando Read-only Filesystem ==="

# 1. Iniciar container em background com --read-only
docker run -d --name "$CONTAINER_NAME" --read-only \
  -v /tmp:/tmp \
  "$IMAGE" &
CONTAINER_PID=$!

sleep 5  # Dar tempo para startup

# 2. Validar que app está UP e respondendo
if curl -f http://localhost:8080/actuator/health/liveness; then
  echo "✓ App started with read-only filesystem"
else
  echo "✗ App failed to start with read-only filesystem"
  docker logs "$CONTAINER_NAME"
  exit 1
fi

# 3. Tentar escrever em raiz (deve falhar gracefully)
if docker exec "$CONTAINER_NAME" touch /test-file 2>&1 | grep -q "Read-only file system"; then
  echo "✓ Filesystem is truly read-only"
else
  echo "✗ Filesystem is writable (unexpected!)"
  exit 1
fi

# 4. Validar que /tmp é writable
if docker exec "$CONTAINER_NAME" touch /tmp/test-file; then
  echo "✓ /tmp is writable"
  docker exec "$CONTAINER_NAME" rm /tmp/test-file
else
  echo "✗ /tmp is not writable (misconfiguration)"
  exit 1
fi

# 5. Fazer smoke test de tráfego
for i in {1..10}; do
  curl -s http://localhost:8080/api/pedidos 2>&1 | grep -q "404\|200" || \
    (echo "✗ App not responding to requests"; exit 1)
done
echo "✓ Smoke test passed (10 requests)"

# Limpeza
docker kill "$CONTAINER_NAME"
docker rm "$CONTAINER_NAME"

echo "=== Validação concluída com sucesso ==="
```

```yaml
# .github/workflows/ci.yml — integrar validação de read-only
- name: Build container
  run: docker build -t ${{ env.IMAGE_NAME }}:${{ github.sha }} .

- name: Validate read-only filesystem
  run: bash scripts/validate-readonly-fs.sh ${{ env.IMAGE_NAME }}:${{ github.sha }}
```

---

## Docker Compose — Ambiente Local

### Docker Compose Profiles — Dev vs Full

Use profiles para separar o que o dev precisa (banco, cache) do que roda na IDE (a aplicação).

```yaml
# docker-compose.yml — profiles para desenvolvimento leve
services:
  # INFRA — sempre sobe com "docker compose --profile dev up"
  postgres:
    image: postgres:16-alpine
    profiles: ["dev", "full"]
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: app
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    profiles: ["dev", "full"]
    ports:
      - "6379:6379"

  localstack:
    image: localstack/localstack:3
    profiles: ["dev", "full"]
    ports:
      - "4566:4566"
    environment:
      SERVICES: sqs,sns,s3,dynamodb,secretsmanager

  # APP — só sobe com "docker compose --profile full up"
  # Em dev, rode a app direto na IDE com DevTools
  app:
    build: .
    profiles: ["full"]
    ports:
      - "8080:8080"
    environment:
      SPRING_PROFILES_ACTIVE: docker
      SPRING_DATASOURCE_URL: jdbc:postgresql://postgres:5432/app
    depends_on:
      postgres:
        condition: service_healthy

volumes:
  pgdata:
```

**Comandos:**

```bash
# Desenvolvimento: sobe só infra, app roda na IDE
docker compose --profile dev up -d
# Tempo: ~10-15s (imagens já baixadas)

# Teste integrado: sobe tudo
docker compose --profile full up -d

# Derrubar
docker compose --profile dev down
```

**REGRA: Em dev, o desenvolvedor NUNCA precisa rodar a app dentro do Docker.**
  IDE + DevTools + hot reload = feedback instantâneo.
  Docker é para infra local (banco, cache, fila) e para CI/deploy.

---

