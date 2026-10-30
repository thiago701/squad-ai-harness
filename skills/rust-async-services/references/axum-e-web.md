# axum 0.8, tower-http, reqwest e sqlx — serviço web de produção

> Autoral (Squad AI). Código **compilado, testado e executado** com `rustc 1.99.0`, axum 0.8.9, tower 0.5.3, tower-http 0.7.1, reqwest 0.13.5 (feature `rustls`), sqlx 0.9.0 (SQLite),
> secrecy 0.10.3, subtle 2.6.1 (edição 2024, clippy `-D warnings`). O serviço foi iniciado de verdade: `GET /livez` → 204, `GET /items/0` → 404 JSON, `POST` inválido → 422,
> `SIGTERM` → saída 0 com a mensagem "encerrado com graça". Versões mudam rápido: use `cargo add` e confira o *changelog* ao atualizar.

## 1. Estrutura

```text
src/
  main.rs      # fino: config → telemetria → pool → router → serve com shutdown
  lib.rs       # reexporta módulos (permite testar sem subir processo)
  web.rs       # Router, handlers, ApiError, serve/shutdown
  db.rs        # pool + consultas
  seguranca.rs # auth, extractors, config
```

`main` fino e `router(state) -> Router` em `lib.rs` permitem testar o serviço inteiro com `tower::ServiceExt::oneshot` (sem porta, sem rede, em milissegundos).

## 2. Núcleo do serviço (código completo)

```rust
use std::{sync::Arc, time::Duration};
use axum::{
    Json, Router,
    extract::{Path, State},
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::{get, post},
};
use serde::{Deserialize, Serialize};
use tokio_util::sync::CancellationToken;
use tower_http::{limit::RequestBodyLimitLayer, timeout::TimeoutLayer, trace::TraceLayer}; // tower-http com as features `limit`, `timeout` e `trace`

/// Erro de API: variantes de domínio → status HTTP, sem vazar detalhes internos.
#[derive(Debug, thiserror::Error)]
pub enum ApiError {
    #[error("item {0} não encontrado")]
    NotFound(u64),
    #[error("entrada inválida: {0}")]
    Invalid(&'static str),
    #[error("erro interno")]
    Internal(#[source] anyhow::Error),
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let status = match &self {
            Self::NotFound(_) => StatusCode::NOT_FOUND,
            Self::Invalid(_) => StatusCode::UNPROCESSABLE_ENTITY,
            Self::Internal(e) => {
                tracing::error!(error = ?e, "falha interna");   // causa completa no LOG…
                StatusCode::INTERNAL_SERVER_ERROR
            }
        };
        let msg = match &self {
            Self::Internal(_) => "erro interno".to_owned(),     // …mas só texto genérico ao CLIENTE
            other => other.to_string(),
        };
        (status, Json(serde_json::json!({ "error": msg }))).into_response()
    }
}

#[derive(Clone, Debug)]
pub struct AppState {
    pub ready: Arc<std::sync::atomic::AtomicBool>,
}

#[derive(Serialize, Deserialize, PartialEq, Debug)]
pub struct Item { pub id: u64, pub name: String }

async fn get_item(State(_): State<AppState>, Path(id): Path<u64>) -> Result<Json<Item>, ApiError> {
    if id == 0 { return Err(ApiError::NotFound(id)); }
    Ok(Json(Item { id, name: "demo".into() }))
}

async fn create_item(Json(item): Json<Item>) -> Result<(StatusCode, Json<Item>), ApiError> {
    if item.name.trim().is_empty() { return Err(ApiError::Invalid("name vazio")); }
    Ok((StatusCode::CREATED, Json(item)))
}

async fn readyz(State(s): State<AppState>) -> StatusCode {
    if s.ready.load(std::sync::atomic::Ordering::Acquire) { StatusCode::NO_CONTENT } else { StatusCode::SERVICE_UNAVAILABLE }
}

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/items/{id}", get(get_item))            // axum 0.8: parâmetros usam {id} (não :id)
        .route("/items", post(create_item))
        .route("/livez", get(|| async { StatusCode::NO_CONTENT }))
        .route("/readyz", get(readyz))
        .layer(RequestBodyLimitLayer::new(1 << 20))      // 1 MiB
        .layer(TimeoutLayer::with_status_code(StatusCode::REQUEST_TIMEOUT, Duration::from_secs(10)))
        .layer(TraceLayer::new_for_http())
        .with_state(state)
}

/// Serve com desligamento gracioso: o token cancela → para de aceitar → drena as conexões em voo.
pub async fn serve(listener: tokio::net::TcpListener, app: Router, shutdown: CancellationToken) -> std::io::Result<()> {
    axum::serve(listener, app)
        .with_graceful_shutdown(async move { shutdown.cancelled().await })
        .await
}

/// SIGTERM (Linux) ou Ctrl-C (qualquer SO) → cancela o token.
pub async fn wait_for_signal(token: CancellationToken) -> std::io::Result<()> {
    #[cfg(unix)]
    {
        use tokio::signal::unix::{SignalKind, signal};
        let mut term = signal(SignalKind::terminate())?;
        tokio::select! {
            _ = term.recv() => {}
            r = tokio::signal::ctrl_c() => r?,
        }
    }
    #[cfg(not(unix))]
    tokio::signal::ctrl_c().await?;
    token.cancel();
    Ok(())
}
```

`main.rs` (verificado em execução real):

```rust
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    obs::iniciar(true)?;                                      // logs JSON
    let token = CancellationToken::new();
    tokio::spawn(web::wait_for_signal(token.clone()));        // SIGTERM/Ctrl-C → cancela
    let listener = tokio::net::TcpListener::bind("0.0.0.0:8080").await?;
    let state = AppState { ready: Arc::new(true.into()) };
    tracing::info!(addr = %listener.local_addr()?, "servindo");
    web::serve(listener, web::router(state), token).await?;   // para de aceitar e drena
    tracing::info!("encerrado com graça");
    Ok(())
}
```

### Regras do `Router` e dos handlers

- **Sintaxe de caminho (0.8):** `"/items/{id}"` e `"/files/{*resto}"`. A sintaxe antiga `:id` **entra em pânico na montagem do router**:
  `Path segments must not start with ':'. For capture groups, use '{capture}'` — aparece no boot, não em runtime tardio.
- **Ordem dos extractors:** o que consome o corpo (`Json`, `Form`, `Bytes`) vai **por último**; `State`, `Path`, `Query`, `HeaderMap` antes. Erro de `Handler<_, _> is not satisfied` quase sempre é ordem errada, tipo sem `Deserialize`/`Serialize`,
  ou handler que segura valor não-`Send` através de `.await` — use `#[axum::debug_handler]` (feature `macros`) para a mensagem real.
- **Estado:** `State<AppState>` com `Clone` barato (`Arc` dentro). Não coloque `Mutex<HashMap>` global: modele com ator (→ `tokio-e-concorrencia.md` §3) ou banco.
- **Camadas (`.layer`)**: a última adicionada é a **mais externa** (executa primeiro na entrada). Com `ServiceBuilder`, a ordem é a de leitura (de cima para baixo = de fora para dentro).
  Boa ordem: `TraceLayer` (mais externa, vê tudo) → `Timeout` → limite de corpo → auth → handler. `route_layer` aplica só às rotas já declaradas (ex.: auth que não deve cobrir `/livez`).
- **Limites:** `RequestBodyLimitLayer` (corpo), `TimeoutLayer` (408; no tower-http 0.7 cobre só até a resposta ser produzida — para o corpo use as camadas de timeout de corpo, ocioso ou com prazo total —), limite de concorrência (`tower::limit::ConcurrencyLimitLayer`) e *load shedding* (`tower::load_shed`) para proteger dependências.
- **Probes:** `/livez` não toca em dependências; `/readyz` reflete se o serviço **pode** receber tráfego (pool ok, migrações aplicadas) e vira `503` durante o shutdown.

## 3. Segurança de entrada (código completo, testado)

```rust
use axum::{Json, Router, extract::{FromRequest, Request, State}, http::{StatusCode, header::AUTHORIZATION},
           middleware::{self, Next}, response::{IntoResponse, Response}, routing::post};
use secrecy::{ExposeSecret as _, SecretString};
use serde::Deserialize;
use subtle::ConstantTimeEq as _;

/// `Debug` de SecretString imprime `[REDACTED]`; o valor só sai com `expose_secret()`.
#[derive(Clone, Debug)]
pub struct Config { pub token: SecretString }

impl Config {
    /// Lê a configuração UMA vez no início (fail-fast). `lookup` abstrai o ambiente: testável sem `set_var` (unsafe na edição 2024).
    pub fn de_ambiente(lookup: impl Fn(&str) -> Option<String>) -> Result<Self, String> {
        let token = lookup("API_TOKEN").ok_or("API_TOKEN ausente")?;
        if token.len() < 16 { return Err("API_TOKEN curto demais (mín. 16)".into()); }
        Ok(Self { token: SecretString::from(token) })
    }
}

/// Middleware: exige `Authorization: Bearer <token>` e compara em TEMPO CONSTANTE.
pub async fn exigir_token(State(cfg): State<Config>, req: Request, next: Next) -> Response {
    let enviado = req.headers().get(AUTHORIZATION).and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer ")).unwrap_or("");
    let esperado = cfg.token.expose_secret();
    let ok = enviado.len() == esperado.len() && bool::from(enviado.as_bytes().ct_eq(esperado.as_bytes()));
    if ok { next.run(req).await }
    else { (StatusCode::UNAUTHORIZED, Json(serde_json::json!({ "error": "não autorizado" }))).into_response() }
}

/// `Json` com rejeição PADRONIZADA: corpo malformado/tipo errado vira `ApiError` (mesmo formato de erro da API).
#[derive(Debug, FromRequest)]
#[from_request(via(axum::Json), rejection(ApiError))]
pub struct ApiJson<T>(pub T);

impl From<axum::extract::rejection::JsonRejection> for ApiError {
    fn from(_: axum::extract::rejection::JsonRejection) -> Self { ApiError::Invalid("corpo JSON inválido") }
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]                     // campo inesperado = 422, não silêncio
pub struct NovoPedido { pub item: String, pub qtd: u32 }

async fn criar(ApiJson(p): ApiJson<NovoPedido>) -> Result<StatusCode, ApiError> {
    if p.qtd == 0 { return Err(ApiError::Invalid("qtd deve ser > 0")); }
    Ok(StatusCode::CREATED)
}

pub fn router(cfg: Config) -> Router {
    Router::new()
        .route("/pedidos", post(criar))
        .route_layer(middleware::from_fn_with_state(cfg, exigir_token))   // só nas rotas acima
}
```

Testes verificados: sem token → 401; token errado → 401; token certo + corpo válido → 201; `qtd = 0` → 422; campo extra → 422; corpo que não é JSON → 422;
`format!("{cfg:?}")` imprime `Config { token: SecretBox<str>([REDACTED]) }` (sem o segredo).

- `derive(FromRequest)` e `#[axum::debug_handler]` exigem a **feature `macros`** do axum (`cargo add axum --features macros`); sem ela o erro é `cannot find derive macro FromRequest in this scope`.
- **Token estático é só para serviço-a-serviço interno.** Para usuários finais: OIDC/JWT validado (`jsonwebtoken` com `aud`/`iss`/`exp` obrigatórios) ou sessão — peça revisão do **engenheiro-seguranca**. Nunca logue `Authorization`, cookies ou corpo com credenciais
  (o `TraceLayer` padrão não loga headers; se customizar, **redija**).
- **CORS:** `tower_http::cors::CorsLayer` com origens **explícitas** (`AllowOrigin::list`); `Any` + credenciais é proibido.
- **Rate limit/abuso:** `tower_governor` (terceiros) ou o gateway/ALB; em mutações, exija idempotência (`Idempotency-Key`).

## 4. Testes do serviço sem rede

```rust
use tower::ServiceExt as _;                    // oneshot
#[tokio::test]
async fn get_ok_e_404() {
    let app = router(AppState { ready: Arc::new(true.into()) });
    let r = app.clone().oneshot(Request::get("/items/7").body(Body::empty()).unwrap()).await.unwrap();
    assert_eq!(r.status(), StatusCode::OK);
    let corpo = r.into_body().collect().await.unwrap().to_bytes();   // http_body_util::BodyExt
    let item: Item = serde_json::from_slice(&corpo).unwrap();
    assert_eq!(item.id, 7);
}
```

Também verificados: **shutdown** (`token.cancel()` → `serve` retorna dentro de 2 s) e **drenagem** — uma requisição lenta (300 ms) já em andamento **termina com 200** depois do `cancel()`,
o `serve` só retorna após drená-la, e uma **nova** conexão é recusada. Esse teste é obrigatório em todo serviço (previne 502 a cada deploy).

## 5. Cliente HTTP (`reqwest`) com prazos e retry

```rust
/// Cliente ÚNICO e reutilizável (pool de conexões; `Client` é barato de clonar), com prazos explícitos.
pub fn cliente() -> reqwest::Result<reqwest::Client> {
    reqwest::Client::builder()
        .connect_timeout(Duration::from_secs(3))
        .timeout(Duration::from_secs(10))                 // prazo TOTAL da requisição
        .pool_idle_timeout(Duration::from_secs(30))
        .redirect(reqwest::redirect::Policy::limited(3))
        .user_agent(concat!(env!("CARGO_PKG_NAME"), "/", env!("CARGO_PKG_VERSION")))
        .build()
}

/// Só repete falhas transitórias. 4xx e erros de decodificação NÃO se repetem.
pub fn transitorio(e: &reqwest::Error) -> bool { e.is_timeout() || e.is_connect() }

/// Retry com backoff exponencial e *full jitter* — só em operações idempotentes (ou com Idempotency-Key).
pub async fn com_retry<T, E, F, Fut>(max_tentativas: u32, base: Duration, mut op: F, retentavel: impl Fn(&E) -> bool) -> Result<T, E>
where F: FnMut(u32) -> Fut, Fut: Future<Output = Result<T, E>>,
{
    let mut tentativa = 0;
    loop {
        match op(tentativa).await {
            Ok(v) => return Ok(v),
            Err(e) if tentativa + 1 < max_tentativas && retentavel(&e) => {
                let teto = base.saturating_mul(2u32.saturating_pow(tentativa));
                let teto_ms = u64::try_from(teto.as_millis()).unwrap_or(u64::MAX);
                tokio::time::sleep(Duration::from_millis(fastrand::u64(0..=teto_ms))).await;   // jitter: evita rajada sincronizada
                tentativa += 1;
            }
            Err(e) => return Err(e),
        }
    }
}
```

Verificado (tempo virtual): falha transitória 2× e sucesso na 3ª (3 chamadas); erro permanente **não** repete (1 chamada). E o cliente falou com o serviço local numa porta efêmera.

- TLS: no reqwest 0.13 a feature `rustls` usa **rustls** (sem OpenSSL do sistema ⇒ binário estático/`scratch`/`distroless` sem dor de `libssl`). `default-features = false` + `features = ["json", "rustls"]`
  reduz a árvore de dependências. No 0.13 a `rustls` valida com `rustls-platform-verifier` (CAs **do SO**): em `scratch` copie o bundle de CAs para a imagem (a `distroless` já o traz). Se precisar de `native-tls`, a imagem final precisa da `libssl` e dos certificados CA.
- `response.error_for_status()?` converte 4xx/5xx em erro; decida **antes** se aquele status é transitório (429/503 com `Retry-After`) e respeite o cabeçalho.
- Limite o **tamanho da resposta** de terceiros (`content_length()` + leitura em *stream* com teto) — resposta gigante é vetor de DoS/OOM.
- Cliente para URL vinda do usuário ⇒ risco de **SSRF**: allowlist de hosts, bloqueie IPs privados/metadata (169.254.169.254) e redirecionamentos não confiáveis.
- Circuit breaker/bulkhead: `tower::limit::ConcurrencyLimit` por dependência; para disjuntor, crates de terceiros (audite).

## 6. Banco de dados (`sqlx` 0.9)

```rust
#[derive(Debug, sqlx::FromRow, PartialEq, Eq)]           // exige a feature `derive`
pub struct Usuario { pub id: i64, pub nome: String }

/// Pool com limites explícitos: tamanho máximo e prazo para obter conexão (evita fila infinita sob carga).
pub async fn abrir(url: &str, max: u32) -> Result<SqlitePool, sqlx::Error> {
    SqlitePoolOptions::new().max_connections(max).acquire_timeout(Duration::from_secs(3)).connect(url).await
}

/// Consulta PARAMETRIZADA (`?` no SQLite, `$1` no Postgres): nunca monte SQL com `format!`.
pub async fn buscar(pool: &SqlitePool, id: i64) -> Result<Option<Usuario>, sqlx::Error> {
    sqlx::query_as::<_, Usuario>("SELECT id, nome FROM usuarios WHERE id = ?").bind(id).fetch_optional(pool).await
}

/// Transação: tudo ou nada. Retornar antes do `commit` faz *rollback* no `Drop`.
pub async fn transferir_nome(pool: &SqlitePool, de: i64, para: i64) -> Result<(), sqlx::Error> {
    let mut tx = pool.begin().await?;
    let nome: String = sqlx::query_scalar("SELECT nome FROM usuarios WHERE id = ?").bind(de).fetch_one(&mut *tx).await?;
    sqlx::query("UPDATE usuarios SET nome = ? WHERE id = ?").bind(nome).bind(para).execute(&mut *tx).await?;
    tx.commit().await
}
```

Verificado em SQLite em memória (`sqlite::memory:` com `max_connections(1)`; o sqlx compartilha o banco em memória entre conexões do pool, mas ele **some quando a última conexão fecha** — por isso fixe 1 conexão viva): consulta, `None` para id inexistente,
transação confirmada e **rollback** quando a origem não existe (`RowNotFound`, dado intacto).

- **sqlx 0.9 e injeção de SQL:** `sqlx::query(sql)` aceita só `&'static str` (trait `SqlSafeStr`). Passar `String` (por exemplo de `format!`) **não compila**:
  `error[E0277]: dynamic SQL strings should be audited for possible injections … wrap with AssertSqlSafe()`.
  Para filtros dinâmicos use `QueryBuilder` com `push_bind`; `AssertSqlSafe(...)` só depois de auditar (nomes de coluna vindos de allowlist, nunca valores).
- **Mapeie erros no limite:** `sqlx::Error::RowNotFound` → `ApiError::NotFound`; violação de unicidade → 409; todo o resto → `Internal` (causa no log). Não devolva texto do driver ao cliente.
- **Pool:** `max_connections` × número de réplicas **≤** limite do banco (deixe folga para migrações/ferramentas); `acquire_timeout` curto; reduza o tempo que cada tarefa segura a conexão (não faça I/O externo com a conexão aberta).
  Na transação, **não** atravesse chamadas HTTP lentas.
- **Migrações:** `sqlx::migrate!("./migrations").run(&pool)` (embute os `.sql` em compilação; com `default-features = false` exige as features `migrate` **e** `macros` — sem `macros`: `cannot find migrate in sqlx`; verificado: aplicou `0001_usuarios.sql` e a consulta seguinte funcionou) + `sqlx-cli` (terceiros) — aplique em job separado ou no boot com **lock** consultivo; migração destrutiva exige GATE humano e plano de *rollback*.
- **Macros `query!`** (checagem em compilação contra um banco real) exigem `DATABASE_URL` no build ou `cargo sqlx prepare` (modo offline) — vale em projeto com CI preparado; sem isso, `query_as` em runtime (acima) é mais simples (P1).
- Este exemplo usa **SQLite** porque roda em memória nos testes; para **Postgres** troque `SqlitePool`/`?` por `PgPool`/`$1` e valide contra um Postgres real (`testcontainers` ou `docker compose` no CI). Essa troca **não** foi executada aqui.

## 7. Checklist do serviço

- [ ] `router()` testado com `oneshot` (rotas, status, corpo de erro) e `serve` testado com shutdown **e** drenagem.
- [ ] Limites: corpo, timeout total, concorrência por dependência; cliente HTTP com `timeout`/`connect_timeout`; pool com `acquire_timeout`.
- [ ] Erros: `ApiError` único → status corretos; 5xx genérico no cliente, causa no log; rejeições de extractor padronizadas.
- [ ] Entrada: `deny_unknown_fields`, validação por tipo, SQL parametrizado, sem `format!` em SQL; segredos só em `SecretString`.
- [ ] Probes `/livez` (sem dependências) e `/readyz` (com prazo curto; `503` no shutdown); SIGTERM tratado.
- [ ] `cargo clippy --all-targets -- -D warnings`, `cargo test`, `cargo deny check` verdes.
