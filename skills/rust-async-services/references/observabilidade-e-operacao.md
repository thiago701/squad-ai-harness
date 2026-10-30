# Observabilidade e operação de serviços Rust

> Autoral (Squad AI). Verificado com `rustc 1.99.0`: **logs JSON** (tracing-subscriber 0.3.23), **traces OTLP** exportados de verdade para um coletor local (opentelemetry/-sdk/-otlp 0.33.0 + tracing-opentelemetry 0.34.0),
> **métricas Prometheus** (metrics 0.24.6 + metrics-exporter-prometheus 0.18.3), sequência de **shutdown** e build **estático musl**. O daemon do Docker não estava disponível no ambiente de verificação:
> o `Dockerfile` e o YAML de Kubernetes abaixo **não** foram construídos/aplicados aqui — valide em CI/cluster de teste. Pares de versões do ecossistema OpenTelemetry mudam a cada release: atualize `opentelemetry*` e `tracing-opentelemetry` **juntos**.

## 1. Logs estruturados (`tracing`)

```rust
use tracing::instrument;
use tracing_subscriber::{EnvFilter, fmt, prelude::*};

/// `RUST_LOG` controla níveis (padrão: info). JSON em produção, texto legível em desenvolvimento.
pub fn iniciar(json: bool) -> Result<(), tracing_subscriber::util::TryInitError> {
    let filtro = EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info"));
    let camada = if json { fmt::layer().json().boxed() } else { fmt::layer().boxed() };
    tracing_subscriber::registry().with(filtro).with(camada).try_init()
}

/// `#[instrument]` cria um span por chamada; `skip` evita registrar argumento sensível/grande; `err` registra o erro retornado.
#[instrument(skip(senha), fields(usuario = %usuario), err)]
pub fn autenticar(usuario: &str, senha: &str) -> Result<(), &'static str> {
    if senha.len() < 8 { return Err("senha curta"); }
    tracing::info!("autenticado");
    Ok(())
}
```

Saída **real** (duas chamadas; a senha não aparece em lugar nenhum):

```json
{"timestamp":"2026-10-03T18:29:35.164Z","level":"INFO","fields":{"message":"autenticado"},"target":"rsnip::obs","span":{"usuario":"ana","name":"autenticar"},"spans":[{"usuario":"ana","name":"autenticar"}]}
{"timestamp":"2026-10-03T18:29:35.164Z","level":"ERROR","fields":{"error":"senha curta"},"target":"rsnip::obs","span":{"usuario":"ana","name":"autenticar"},"spans":[{"usuario":"ana","name":"autenticar"}]}
```

Regras:

- **Campos estruturados, não texto interpolado:** `tracing::info!(pedido_id = %id, itens = n, "pedido criado")` — o agregador (Loki, CloudWatch, Datadog) filtra por campo. `%` usa `Display`, `?` usa `Debug`.
- **Nível certo:** `error` = falha que exige ação; `warn` = degradação; `info` = eventos de negócio/ciclo de vida; `debug`/`trace` = diagnóstico (desligados em produção por padrão). Nada de `info!` por item em laço quente.
- **Sem segredos/PII:** nunca logue `Authorization`, cookies, tokens, senhas, corpo bruto de requisição, URL com credencial. Use `#[instrument(skip(...))]` e tipos como `SecretString` (cujo `Debug` é `[REDACTED]`).
- **Spans e `.await`:** em código async **não** use `let _g = span.enter();` atravessando `.await` (o span "vaza" para outras tarefas). Use `#[instrument]` ou `fut.instrument(span).await` (`tracing::Instrument`).
- **Uma linha de log por requisição** (método, rota *com padrão*, status, duração, `request_id`) vem do `TraceLayer`/middleware; correlacione com `request_id`/`trace_id`.
- `err` no `#[instrument]` registra o erro no nível ERROR — não duplique com outro `error!` no chamador (log em dobro).
- `tracing_subscriber::fmt().json().with_writer(...)` permite **testar** o log (capturar num buffer e afirmar que o segredo não está lá — teste verificado).

## 2. Traces distribuídos (OpenTelemetry via OTLP)

Código verificado (compila e **exporta**): o serviço mandou `POST /v1/traces` com `application/x-protobuf` (557 bytes, contendo o nome do serviço e o span `trabalho`) a um coletor local, no encerramento.

```toml
# Cargo.toml (versões pareadas — atualize juntas)
opentelemetry = "0.33"
opentelemetry_sdk = "0.33"
opentelemetry-otlp = { version = "0.33", default-features = false, features = ["trace", "http-proto", "reqwest-blocking-client"] }
tracing-opentelemetry = "0.34"
```

```rust
use opentelemetry::trace::TracerProvider as _;
use opentelemetry_otlp::SpanExporter;
use opentelemetry_sdk::{Resource, trace::SdkTracerProvider};
use tracing_subscriber::{EnvFilter, fmt, prelude::*};

/// Guarda o provider: no encerramento, `shutdown()` faz o FLUSH dos spans pendentes.
struct Telemetria(SdkTracerProvider);

impl Telemetria {
    fn iniciar(servico: &'static str) -> Result<Self, Box<dyn std::error::Error + Send + Sync>> {
        // endpoint, cabeçalhos e timeout vêm das variáveis OTEL_EXPORTER_OTLP_* — o código só conhece o nome do serviço
        let exportador = SpanExporter::builder().with_http().build()?;
        let provider = SdkTracerProvider::builder()
            .with_batch_exporter(exportador)
            .with_resource(Resource::builder().with_service_name(servico).build())
            .build();
        let camada_otel = tracing_opentelemetry::layer().with_tracer(provider.tracer(servico));
        tracing_subscriber::registry()
            .with(EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")))
            .with(fmt::layer().json())
            .with(camada_otel)
            .try_init()?;
        Ok(Self(provider))
    }

    fn encerrar(self) {
        if let Err(e) = self.0.shutdown() { eprintln!("falha ao descarregar telemetria: {e}"); }
    }
}
```

Operação:

- **Configuração por ambiente (padrão OTel):** `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318`, `OTEL_SERVICE_NAME`, `OTEL_RESOURCE_ATTRIBUTES=deployment.environment=prod,service.version=…`,
  amostragem `OTEL_TRACES_SAMPLER=parentbased_traceidratio` + `OTEL_TRACES_SAMPLER_ARG=0.1`. Com HTTP/protobuf o caminho `/v1/traces` é acrescentado ao endpoint (confirmado no teste).
- **Sempre chame `shutdown()`** depois de parar de servir: o exportador em lote é assíncrono e **perde os últimos spans** se o processo sair antes do *flush*. Em Lambda/CLI curto, faça `force_flush()` antes de terminar.
- Exporte para um **OpenTelemetry Collector** (DaemonSet/sidecar) — ele faz *batching*, retry, redação de atributos e roteamento; a aplicação não fala direto com o backend.
- **Propagação entre serviços:** instale `TraceContextPropagator` (W3C `traceparent`) e injete/extraia nos clientes/servidores HTTP; sem isso cada serviço gera traces isolados. (Não verificado aqui — confira o pacote `opentelemetry-http`/`tower-http` da sua versão.)
- Atributos de span **sem PII**; **baixa cardinalidade** nos nomes (`GET /items/{id}`, não `GET /items/12345`).
- Telemetria nunca pode derrubar o serviço: falha do exportador só gera aviso; use timeouts curtos no exportador.

## 3. Métricas (RED + saturação) com Prometheus

```rust
use metrics::{counter, gauge, histogram};
use metrics_exporter_prometheus::{Matcher, PrometheusBuilder};

let handle = PrometheusBuilder::new()
    // SEM isto, histogram! vira *summary* (quantis por réplica, NÃO agregáveis entre pods). Com buckets: histograma de verdade.
    .set_buckets_for_metric(Matcher::Full("http_request_duration_seconds".into()), &[0.005, 0.025, 0.1, 0.5, 2.5])?
    .install_recorder()?;

// rótulos de BAIXA cardinalidade (rota-padrão, método, status) — nunca id de usuário ou URL crua
counter!("http_requests_total", "route" => "/items/{id}", "status" => "200").increment(1);
gauge!("pool_conexoes_ativas").set(3.0);
histogram!("http_request_duration_seconds", "route" => "/items/{id}").record(0.042);
// handle.render() → texto no formato de exposição do Prometheus (sirva em GET /metrics numa porta INTERNA)
```

Saída real do `render()` com buckets (trecho): `http_request_duration_seconds_bucket{route="/items/{id}",le="0.1"} 1` … `le="+Inf"} 1`, `_sum` e `_count`.

- **O que medir (RED):** *Rate* (`http_requests_total`), *Errors* (status 5xx), *Duration* (histograma). **Saturação:** conexões do pool em uso/espera, tamanho de filas (`mpsc` — `Sender::capacity()`/`max_capacity()`), tarefas em voo, `spawn_blocking` ocupado.
- **Cardinalidade explode custo (P3):** cada combinação de rótulos é uma série. Proibido usar `user_id`, `email`, caminho cru ou mensagem de erro como rótulo.
- `/metrics` em **porta separada** (ou protegido): não exponha por Ingress público.
- Métricas do runtime tokio (tarefas vivas, fila global, workers ocupados): `Handle::current().metrics()` e a crate `tokio-metrics` (terceiros; **não verificada aqui**).
- SLOs → alertas por *burn rate* (erro e latência), não por limiar fixo de CPU.

## 4. Encerramento: probes + drenagem (verificado)

```rust
/// (1) readiness cai → o balanceador para de enviar tráfego; (2) espera `drain` para propagar; (3) só então cancela o servidor.
pub async fn encerrar_com_drain(ready: &AtomicBool, token: &CancellationToken, drain: Duration) {
    ready.store(false, Ordering::Release);
    tokio::time::sleep(drain).await;
    token.cancel();
}
```

Teste (tempo virtual): 1 s depois do sinal a readiness já é `false` e o token **ainda não** foi cancelado; só após o `drain` (5 s) o token cancela. Combine com `with_graceful_shutdown`
(que, verificado, **termina a requisição lenta em voo** e recusa conexões novas) e *flush* da telemetria (§2).

Linha do tempo (Kubernetes): `SIGTERM` → readiness falha → `drain` (≈ `preStop`/5 s) → drena requisições (≤ `SHUTDOWN_TIMEOUT`) → fecha pool → `shutdown()` da telemetria → `exit 0` — tudo **dentro** de `terminationGracePeriodSeconds`.
Se o binário for PID 1 de contêiner, ele recebe o `SIGTERM` direto (use a forma `exec` do `ENTRYPOINT`: `["/app"]`, não `sh -c`).

## 5. Contêiner

Resultados de build **medidos** (serviço axum + tokio + tracing JSON, `lto = "thin"`, `codegen-units = 1`, `strip = "symbols"`, `panic = "abort"`, rustc 1.99.0):

| Alvo | Tamanho | Ligação |
|---|---|---|
| `x86_64-unknown-linux-gnu` | 1,12 MB | dinâmica: `libgcc_s`, `libm`, `libc` (glibc) → imagem `distroless/cc` |
| `x86_64-unknown-linux-musl` | 1,25 MB | **estática** (`static-pie`, `ldd`: statically linked) → `scratch`/`distroless/static` |

O binário musl respondeu `{"ok":true}` e emitiu o log JSON. **Cuidado:** dependências com código C (`aws-lc-rs` do rustls, `libsqlite3-sys`, `openssl-sys`) exigem toolchain C para musl
(`musl-tools`/`musl-gcc`) e podem ficar **mais lentas** com o alocador do musl em carga multithread — meça (→ **rust-performance-engineer**) antes de adotar musl só pelo tamanho da imagem.

```dockerfile
# syntax=docker/dockerfile:1
# fixe as imagens por digest em produção
FROM rust:1.99-bookworm AS build
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY crates ./crates
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/src/target \
    cargo build --release --locked && cp target/release/app /out-app

# glibc + libgcc; sem shell nem gerenciador de pacotes
FROM gcr.io/distroless/cc-debian12:nonroot
COPY --from=build /out-app /app
USER nonroot:nonroot
EXPOSE 8080
# forma exec: o processo (PID 1) recebe o SIGTERM diretamente
ENTRYPOINT ["/app"]
```

> O Docker só trata `#` no **início** da linha como comentário; comentário no fim de `FROM`/`ENV`/`ENTRYPOINT` vira argumento e **quebra** o build — por isso ficam em linhas próprias.
> O `Dockerfile` não foi construído aqui (sem daemon Docker no ambiente); valide em CI. Como PID 1 de contêiner, o processo **ignora** sinais sem *handler* registrado: o `signal(SignalKind::terminate())` do §4 é obrigatório.

- `--locked` (falha se `Cargo.lock` divergir), imagem **não-root**, FS somente leitura no pod, **sem segredos** em `ARG`/`ENV`/camadas (injete em runtime).
- Cache de dependências: `--mount=type=cache` (BuildKit) acima; ou `cargo-chef` (terceiros) para camadas de dependência.
- Rode `cargo deny check` no CI e escaneie a imagem (Trivy/Grype); gere SBOM (`cargo cyclonedx`/`syft`, terceiros).
- Fuso horário e CA: `distroless` (static/base/cc) já traz `ca-certificates` e `tzdata`; em `scratch` você precisa copiá-los (ou embutir o fuso: `chrono-tz` embute o banco de fusos; para CAs, no reqwest 0.13 a feature `rustls` usa `rustls-platform-verifier` — CAs do SO — então copie o bundle de CAs também).
- `arm64`: `docker buildx build --platform linux/amd64,linux/arm64` — Graviton costuma custar menos por vCPU (P3); valide o desempenho antes.

## 6. Kubernetes (diferenças para Rust)

O `Deployment`, os probes, o PDB, o `topologySpreadConstraints`, a política de rollout e a linha do tempo de encerramento são **os mesmos** de qualquer serviço HTTP:
use os modelos de `go-cloud-services/references/container-e-kubernetes.md` (trocando a imagem, `readOnlyRootFilesystem`, `/livez` e `/readyz`). O que muda em Rust:

- **Sem GC, sem `GOMEMLIMIT`:** a memória é a soma de pilhas, *buffers*, caches e **fragmentação do alocador**. Defina `limits.memory = requests.memory` com folga medida; o OOMKill vem de vazamento lógico (cache/fila ilimitados), pico de `spawn_blocking`/buffers, ou arenas do glibc.
  Em serviços multithread de longa vida, `MALLOC_ARENA_MAX=2` ou um alocador alternativo (`jemalloc`/`mimalloc`) frequentemente estabilizam o RSS — **meça** (→ rust-performance-engineer).
- **CPU:** o tokio cria **uma thread de trabalho por CPU disponível** (`std::thread::available_parallelism`, que na doc da std considera afinidade e quotas de cgroup, mas **pode superestimar** quando o cgroup não pode ser consultado, p. ex. sob sandbox).
  Verifique no pod (`TOKIO_WORKER_THREADS` explícito se necessário) e **não** dimensione `worker_threads` acima do limite de CPU: threads demais com quota baixa geram *throttling* e latência de cauda.
- **Inicialização rápida, sem *warm-up*:** `startupProbe` curto; HPA por CPU/RPS/latência. Binário pequeno ⇒ `imagePullPolicy` e escala mais rápidos.
- **Identidade AWS no EKS:** IRSA ou EKS Pod Identity (o SDK `aws-config` resolve pela cadeia padrão); **sem** chaves de acesso em `Secret`.
- **Perfis em produção:** `pprof`/flamegraph só por `kubectl port-forward` a porta interna; nada de endpoint de depuração público.

## 7. Checklist de produção (Rust)

- [ ] Logs JSON sem segredo; `request_id`/`trace_id` correlacionados; nível por `RUST_LOG`.
- [ ] Traces OTLP com `shutdown()`/`force_flush()` no encerramento; versões OTel pareadas; amostragem configurada.
- [ ] Métricas RED + saturação; histogramas **com buckets**; rótulos de baixa cardinalidade; `/metrics` interno.
- [ ] `/livez` sem dependências, `/readyz` com prazo; sequência readiness → drain → shutdown testada; `SIGTERM` como PID 1 (forma exec).
- [ ] Imagem não-root, por digest, `--locked`, sem segredos; `cargo deny check` e scan da imagem limpos.
- [ ] Memória/CPU dimensionadas por **medição** (alocador, `worker_threads`, pool de banco × réplicas).
- [ ] Runbook: como ligar `debug` por serviço (`RUST_LOG`), como coletar perfil, como ler as métricas de saturação.
