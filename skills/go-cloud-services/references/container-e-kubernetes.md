# Contêiner e Kubernetes para serviços Go

> Autoral (Squad AI). Os YAML abaixo foram validados sintaticamente (parser YAML); o `Dockerfile` não foi construído (sem daemon Docker no ambiente de verificação) — comentários ficam em linhas próprias porque o Docker só trata `#` no **início** da linha como comentário. Aplique tudo em cluster/CI de teste antes de produção.
> Valores de exemplo (memória, réplicas) são **ponto de partida**: calibre por medição (`go-performance-engineer`).

## 1. Dockerfile mínimo, reprodutível e seguro

```dockerfile
# syntax=docker/dockerfile:1
FROM golang:1.27 AS build
# GOTOOLCHAIN=local: não baixa outro toolchain; CGO_ENABLED=0: binário estático
ENV GOTOOLCHAIN=local CGO_ENABLED=0
WORKDIR /src
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod go mod download && go mod verify
COPY . .
ARG VERSION=dev
RUN --mount=type=cache,target=/root/.cache/go-build \
    go build -trimpath -ldflags="-s -w -X main.version=${VERSION}" -o /out/app ./cmd/app

# sem shell nem gerenciador de pacotes; fixe por digest em produção
FROM gcr.io/distroless/static:nonroot
COPY --from=build /out/app /app
USER 65532:65532   # UID numérico: com nome, o kubelet não verifica runAsNonRoot (CreateContainerConfigError)
EXPOSE 8080
ENTRYPOINT ["/app"]
```

- **`CGO_ENABLED=0`** gera binário estático ⇒ `distroless/static` ou `scratch`. Se precisa de cgo (SQLite, libs C), use `distroless/base`/`cc` e a mesma libc do build.
- **Certificados CA e fuso:** `distroless/static` já traz CA e `tzdata`; em `scratch` copie `/etc/ssl/certs/ca-certificates.crt` (ou `import _ "time/tzdata"`).
- **Pin por digest** (`FROM gcr.io/distroless/static@sha256:…`) e atualize via bot (Renovate/Dependabot) com revisão — tags móveis quebram a reprodutibilidade.
- Nunca coloque segredo em `ARG`/`ENV` da imagem (ficam no histórico das camadas); injete em runtime.
- `.dockerignore` com `.git`, `*.md`, testes e `bin/`; contexto pequeno = build rápido e menos vazamento.
- Escaneie a imagem (Trivy/Grype) e rode `govulncheck -mode=binary /out/app` no CI; gere SBOM (`go version -m`, syft).
- Arm64: `docker buildx build --platform linux/amd64,linux/arm64` — Graviton/Fargate arm64 costumam custar menos por vCPU (P3); valide desempenho.

## 2. Deployment de referência

```yaml
apiVersion: apps/v1
kind: Deployment
metadata: {name: pedidos, labels: {app: pedidos}}
spec:
  replicas: 3
  strategy: {type: RollingUpdate, rollingUpdate: {maxUnavailable: 0, maxSurge: 1}}
  selector: {matchLabels: {app: pedidos}}
  template:
    metadata: {labels: {app: pedidos}}
    spec:
      terminationGracePeriodSeconds: 30        # > preStop + ShutdownTimeout da app
      securityContext: {runAsNonRoot: true, runAsUser: 65532, seccompProfile: {type: RuntimeDefault}}
      topologySpreadConstraints:
        - {maxSkew: 1, topologyKey: topology.kubernetes.io/zone, whenUnsatisfiable: ScheduleAnyway, labelSelector: {matchLabels: {app: pedidos}}}
      containers:
        - name: app
          image: registry.exemplo.com/pedidos@sha256:REPLACE_DIGEST
          ports: [{containerPort: 8080, name: http}]
          env:
            - {name: GOMEMLIMIT, value: "900MiB"}     # ≈ 90% do limit de memória (1Gi). GOMAXPROCS só acompanha o limit de CPU (não o request) e exige `go ≥ 1.25` no go.mod
            - {name: SHUTDOWN_TIMEOUT, value: "20s"}
            - name: DATABASE_URL
              valueFrom: {secretKeyRef: {name: pedidos-db, key: url}}
          resources:
            requests: {cpu: 250m, memory: 1Gi}
            limits: {memory: 1Gi}                       # limit de CPU: ver nota abaixo
          securityContext: {allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, capabilities: {drop: [ALL]}}
          startupProbe:   {httpGet: {path: /livez, port: http}, periodSeconds: 2, failureThreshold: 30}
          livenessProbe:  {httpGet: {path: /livez, port: http}, periodSeconds: 10, timeoutSeconds: 2, failureThreshold: 3}
          readinessProbe: {httpGet: {path: /readyz, port: http}, periodSeconds: 5, timeoutSeconds: 2, failureThreshold: 2}
          lifecycle:
            preStop: {sleep: {seconds: 5}}              # dá tempo ao Service/Ingress de tirar o pod do balanceamento
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata: {name: pedidos}
spec:
  minAvailable: 2
  selector: {matchLabels: {app: pedidos}}
```

Notas operacionais:

- **Linha do tempo do encerramento:** o `preStop` (5 s) roda primeiro e a contagem do *grace period* já começou → `SIGTERM` → app derruba readiness → drena (≤ `SHUTDOWN_TIMEOUT` 20 s) → `SIGKILL` aos 30 s. Some: `preStop + drain + shutdown ≤ terminationGracePeriodSeconds`.
- **`preStop.sleep`** (ação nativa) exige Kubernetes ≥ 1.30; em clusters mais antigos, imagem `distroless` não tem `sleep` — implemente o *drain* na própria app (parâmetro `drain` do `Serve`).
- **Memória:** `limits.memory` = `requests.memory` evita *eviction* surpresa; `GOMEMLIMIT` ~90% do limit para o GC reagir antes do OOMKill. Se o limit mudar, **atualize `GOMEMLIMIT`** (K8s não calcula percentual). Alternativa: biblioteca `automemlimit` (terceiros — auditar antes).
- **CPU:** com `limits.cpu`, o Go ≥ 1.25 (módulo com `go 1.25+` no go.mod, ou `GODEBUG`) ajusta `GOMAXPROCS` ao **limit** (arredonda para cima, mín. 2) e reajusta se o limite mudar, o que evita *throttling* por excesso de threads — **não** precisa mais de `automaxprocs`. O runtime **não considera o `requests.cpu`**: quem define só `requests.cpu` (sem limit, para evitar *throttling*) fica com `GOMAXPROCS` = nº de CPUs do **nó** — fixe `GOMAXPROCS` explicitamente e use HPA; decida por medição.
- **Probes:** `startupProbe` protege inicialização lenta; `liveness` **sem dependências**; `readiness` com timeout curto. Probe gRPC nativo: `grpc: {port: 9090}` com o serviço `grpc.health.v1`.
- **HPA:** escale por CPU/RPS/latência (métrica custom) com `minReplicas ≥ 2` e janela de estabilização; *scale-down* lento evita oscilação. Combine com PDB e `topologySpreadConstraints`.
- **Config/segredos:** `ConfigMap` para não secretos; `Secret` (idealmente via External Secrets/CSI de um cofre) para o resto; rotação sem rebuild da imagem; `RBAC` mínimo; `NetworkPolicy` default-deny.
- **Identidade AWS no EKS:** IRSA ou EKS Pod Identity — **sem** chaves de acesso em `Secret`.

## 3. Observabilidade em cluster

- Logs em **stdout** (JSON); o agente do nó coleta. Sem arquivos de log no contêiner (FS é somente leitura).
- Traces/métricas: OTLP para um **OpenTelemetry Collector** (DaemonSet ou sidecar) — o app só conhece `OTEL_EXPORTER_OTLP_ENDPOINT`. Prometheus: `/metrics` em porta separada ou via Collector.
- Perfis: pprof só por `kubectl port-forward` a uma porta interna/loopback do pod; nunca por Ingress. Profiling contínuo (Pyroscope/Parca) apenas com auditoria do agente.
- Alertas por **SLO/burn rate**; painel RED + saturação (`/gc/*`, goroutines, pool de conexões, filas).

## 4. Outras plataformas (mesmo contrato de encerramento)

| Plataforma | Sinal/janela | Observações |
|---|---|---|
| ECS/Fargate | `SIGTERM`, `stopTimeout` (padrão 30 s) | arm64 mais barato; health check do ALB = `/readyz`; role da task (sem chaves) |
| Cloud Run / App Runner | `SIGTERM` com janela curta (Cloud Run: 10 s; confirme a do App Runner na doc) | porta via `PORT`; `Shutdown` com prazo ≤ janela; concorrência por instância configurável |
| VM/systemd | `SIGTERM` + `TimeoutStopSec` | `Restart=on-failure`, `NoNewPrivileges`, usuário dedicado |
| AWS Lambda | *sem* servidor HTTP próprio | outro modelo de execução → **aws-lambda-go** |

## 5. Checklist de deploy

- [ ] Imagem por digest, não-root, FS somente leitura, sem segredos; `govulncheck` e scan de imagem limpos.
- [ ] `GOMEMLIMIT` coerente com o limit; requests/limits dimensionados por carga real.
- [ ] Probes corretos; encerramento testado (`kubectl delete pod` sob carga ⇒ 0 erros 5xx).
- [ ] PDB, ≥2 réplicas, spread por zona; rollout `maxUnavailable: 0`.
- [ ] Logs/traces/métricas chegando; alertas de SLO configurados; runbook com comandos de perfil/diagnóstico.
