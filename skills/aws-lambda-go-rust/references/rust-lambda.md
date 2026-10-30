# Rust no AWS Lambda — referência

> Código **compilado e testado** nesta skill (rustc 1.99.0, edição 2024; `lambda_runtime` 1.4.0, `lambda_http` 1.3.1,
> `aws_lambda_events` 1.2.0, `aws-sdk-dynamodb` 1.130.0, `aws-config` 1.12.0): `cargo fmt`, `clippy --all-targets -D warnings` e
> `cargo test` verdes, e o `bootstrap` executado contra um Runtime API simulado (`references/iac-e-teste-local.md`). Os trechos são os
> arquivos reais — copie e adapte.

## 1. Estrutura e `Cargo.toml`

```text
src/lib.rs            # lógica PURA de lote (testável sem Lambda): processa_lote (padrão) e processa_fifo
src/bin/sqs.rs        # ponto de entrada SQS            → bootstrap da função de fila
src/bin/http.rs       # ponto de entrada HTTP API v2    → bootstrap da função de API
```

Um binário por função: cada Lambda recebe o **seu** executável, copiado para `bootstrap` no pacote. O SDK da AWS entra só no binário
que o usa (veja a variante com DynamoDB, §4).

`Cargo.toml`:

```toml
[package]
name = "rlam"
version = "0.1.0"
edition = "2024"
rust-version = "1.99"

[dependencies]
aws_lambda_events = { version = "1.2", default-features = false, features = ["sqs"] }
lambda_http = "1.3"
lambda_runtime = "1.4"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
thiserror = "2"
tokio = { version = "1", features = ["macros", "rt-multi-thread", "sync", "time"] }
tracing = "0.1"

[dev-dependencies]
tokio = { version = "1", features = ["test-util"] }

[lints.rust]
unsafe_code = "forbid"

[profile.release]
lto = "thin"
codegen-units = 1
strip = "symbols"
```

- `lambda_http` traz o tipo `Request`/`Response` para API Gateway/ALB; `lambda_runtime` + `aws_lambda_events` cobrem os demais eventos.
  Em `aws_lambda_events`, ative **só** as features dos eventos usados (`sqs`) — o crate tem dezenas e o tempo de compilação sobe.
- `strip = "symbols"` + `lto = "thin"` + `codegen-units = 1` reduzem o binário (→ **rust-performance-engineer** para o trade-off).
- `unsafe_code = "forbid"` no handler: não há razão para `unsafe` em código de evento.

## 2. Lote SQS (`src/lib.rs`)

```rust
//! Processamento de lote SQS com falha parcial, concorrência limitada e prazo (deadline) do Lambda.
use std::collections::HashMap;
use std::future::Future;
use std::sync::Arc;
use std::time::Duration;

use aws_lambda_events::event::sqs::{BatchItemFailure, SqsBatchResponse, SqsEvent, SqsMessage};
use serde::Deserialize;
use thiserror::Error;
use tokio::sync::Semaphore;
use tokio::task::JoinSet;

/// Corpo esperado de cada mensagem. `deny_unknown_fields`: entrada externa é hostil.
#[derive(Debug, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Pedido {
    pub id: String,
    pub valor: i64, // centavos
}

#[derive(Debug, Error)]
pub enum ErroMensagem {
    #[error("mensagem inválida: {0}")]
    Invalida(String),
    #[error("falha no processamento: {0}")]
    Processamento(String),
}

pub fn decodifica(body: Option<&str>) -> Result<Pedido, ErroMensagem> {
    let body = body.ok_or_else(|| ErroMensagem::Invalida("sem corpo".into()))?;
    let p: Pedido =
        serde_json::from_str(body).map_err(|e| ErroMensagem::Invalida(e.to_string()))?;
    if p.id.is_empty() || p.valor <= 0 {
        return Err(ErroMensagem::Invalida("id/valor".into()));
    }
    Ok(p)
}

/// Processa o lote e devolve SÓ os `messageId` que falharam (partial batch response).
/// Requer `ReportBatchItemFailures` na event source mapping.
///
/// - concorrência máxima = `limite`;
/// - após `prazo`, o que não terminou é abortado e devolvido à fila;
/// - pânico numa mensagem não derruba o lote (vira falha só daquela).
///
/// Obs.: com `panic = "abort"` no perfil, um pânico derruba o processo inteiro — aqui a captura
/// via `JoinSet` só funciona com `panic = "unwind"` (veja a skill: decisão consciente).
pub async fn processa_lote<F, Fut>(
    registros: Vec<SqsMessage>,
    limite: usize,
    prazo: Duration,
    proc: F,
) -> Vec<String>
where
    F: Fn(Pedido) -> Fut + Send + Sync + Clone + 'static,
    Fut: Future<Output = Result<(), ErroMensagem>> + Send + 'static,
{
    let sem = Arc::new(Semaphore::new(limite.max(1)));
    let mut set: JoinSet<(String, bool)> = JoinSet::new();
    let mut por_tarefa: HashMap<tokio::task::Id, String> = HashMap::new();
    let mut falhas: Vec<String> = Vec::new();

    for r in registros {
        let id = r.message_id.clone().unwrap_or_default();
        let pedido = match decodifica(r.body.as_deref()) {
            Ok(p) => p,
            Err(_) => {
                falhas.push(id); // nunca vai passar: vai para a DLQ após maxReceiveCount
                continue;
            }
        };
        let (sem, proc, id2) = (Arc::clone(&sem), proc.clone(), id.clone());
        let handle = set.spawn(async move {
            let Ok(_permit) = sem.acquire_owned().await else {
                return (id2, false);
            };
            let ok = proc(pedido).await.is_ok();
            (id2, ok)
        });
        por_tarefa.insert(handle.id(), id);
    }

    let fim = tokio::time::Instant::now() + prazo;
    while !set.is_empty() {
        match tokio::time::timeout_at(fim, set.join_next_with_id()).await {
            Ok(Some(Ok((tid, (id, ok))))) => {
                por_tarefa.remove(&tid);
                if !ok {
                    falhas.push(id);
                }
            }
            Ok(Some(Err(e))) => {
                // pânico/cancelamento: o id vem do mapa por tarefa
                if let Some(id) = por_tarefa.remove(&e.id()) {
                    falhas.push(id);
                }
            }
            Ok(None) => break,
            Err(_) => {
                // estourou o prazo: aborta e devolve tudo que não terminou
                set.abort_all();
                falhas.extend(por_tarefa.drain().map(|(_, id)| id));
                break;
            }
        }
    }
    falhas
}

/// Fila FIFO: processa EM ORDEM e PARA na 1ª falha, devolvendo a que falhou e todas as seguintes
/// (preserva a ordem do grupo — exigência da AWS para FIFO com resposta parcial).
/// Pânico, erro, mensagem inválida e estouro de prazo contam como falha.
pub async fn processa_fifo<F, Fut>(
    registros: Vec<SqsMessage>,
    prazo: Duration,
    proc: F,
) -> Vec<String>
where
    F: Fn(Pedido) -> Fut + Send + Sync + Clone + 'static,
    Fut: Future<Output = Result<(), ErroMensagem>> + Send + 'static,
{
    let fim = tokio::time::Instant::now() + prazo;
    let ids: Vec<String> = registros
        .iter()
        .map(|r| r.message_id.clone().unwrap_or_default())
        .collect();
    for (i, r) in registros.into_iter().enumerate() {
        let ok = match decodifica(r.body.as_deref()) {
            Ok(pedido) => {
                let mut tarefa = tokio::spawn(proc.clone()(pedido));
                match tokio::time::timeout_at(fim, &mut tarefa).await {
                    Ok(Ok(Ok(()))) => true,
                    Ok(_) => false, // erro de negócio ou pânico (JoinError)
                    Err(_) => {
                        tarefa.abort(); // sem tempo: não deixa a tarefa rodando solta
                        false
                    }
                }
            }
            Err(_) => false,
        };
        if !ok {
            return ids[i..].to_vec();
        }
    }
    Vec::new()
}

pub fn resposta(falhas: Vec<String>) -> SqsBatchResponse {
    let mut r = SqsBatchResponse::default();
    r.batch_item_failures = falhas
        .into_iter()
        .map(|id| {
            let mut f = BatchItemFailure::default();
            f.item_identifier = id;
            f
        })
        .collect();
    r
}

/// Reserva uma margem do prazo restante para devolver a resposta antes do Lambda matar o ambiente.
pub fn prazo_util(restante: Duration) -> Duration {
    restante.saturating_sub(Duration::from_millis(500))
}

pub async fn handler_sqs<F, Fut>(
    ev: SqsEvent,
    restante: Duration,
    limite: usize,
    proc: F,
) -> SqsBatchResponse
where
    F: Fn(Pedido) -> Fut + Send + Sync + Clone + 'static,
    Fut: Future<Output = Result<(), ErroMensagem>> + Send + 'static,
{
    resposta(processa_lote(ev.records, limite, prazo_util(restante), proc).await)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn msg(id: &str, body: &str) -> SqsMessage {
        let mut m = SqsMessage::default();
        m.message_id = Some(id.into());
        m.body = Some(body.into());
        m
    }

    fn ordenado(mut v: Vec<String>) -> Vec<String> {
        v.sort();
        v
    }

    #[tokio::test]
    async fn falhas_parciais() {
        let regs = vec![
            msg("ok1", r#"{"id":"a","valor":100}"#),
            msg("json-ruim", "{nao é json"),
            msg("sem-valor", r#"{"id":"b","valor":0}"#),
            msg("campo-extra", r#"{"id":"b","valor":1,"x":1}"#),
            msg("erro-negocio", r#"{"id":"falha","valor":5}"#),
            msg("ok2", r#"{"id":"c","valor":7}"#),
        ];
        let proc = |p: Pedido| async move {
            if p.id == "falha" {
                Err(ErroMensagem::Processamento("dependência fora do ar".into()))
            } else {
                Ok(())
            }
        };
        let got = ordenado(processa_lote(regs, 3, Duration::from_secs(5), proc).await);
        assert_eq!(
            got,
            ["campo-extra", "erro-negocio", "json-ruim", "sem-valor"]
        );
    }

    #[tokio::test(start_paused = true)]
    async fn estouro_de_prazo_devolve_o_que_nao_terminou() {
        let regs = vec![
            msg("rapida", r#"{"id":"r","valor":1}"#),
            msg("lenta", r#"{"id":"l","valor":1}"#),
        ];
        let proc = |p: Pedido| async move {
            if p.id == "l" {
                tokio::time::sleep(Duration::from_secs(60)).await;
            }
            Ok(())
        };
        let got = processa_lote(regs, 2, Duration::from_secs(10), proc).await;
        assert_eq!(got, ["lenta"]);
    }

    #[tokio::test]
    async fn panico_vira_falha_so_da_mensagem() {
        let regs = vec![
            msg("boom", r#"{"id":"b","valor":1}"#),
            msg("ok", r#"{"id":"o","valor":1}"#),
        ];
        let proc = |p: Pedido| async move {
            assert_ne!(p.id, "b", "panico de teste");
            Ok(())
        };
        let got = processa_lote(regs, 2, Duration::from_secs(5), proc).await;
        assert_eq!(got, ["boom"]);
    }

    #[test]
    fn lote_vazio_serializa_lista_vazia() {
        let j = serde_json::to_string(&resposta(vec![])).unwrap();
        assert_eq!(j, r#"{"batchItemFailures":[]}"#);
    }

    #[tokio::test]
    async fn fifo_para_na_primeira_falha_e_devolve_o_resto() {
        let regs = vec![
            msg("1", r#"{"id":"a","valor":1}"#),
            msg("2", r#"{"id":"falha","valor":1}"#),
            msg("3", r#"{"id":"c","valor":1}"#),
            msg("4", r#"{"id":"d","valor":1}"#),
        ];
        let vistos = Arc::new(std::sync::Mutex::new(Vec::<String>::new()));
        let v = Arc::clone(&vistos);
        let proc = move |p: Pedido| {
            let v = Arc::clone(&v);
            async move {
                v.lock().unwrap().push(p.id.clone());
                if p.id == "falha" {
                    Err(ErroMensagem::Processamento("fora do ar".into()))
                } else {
                    Ok(())
                }
            }
        };
        let got = processa_fifo(regs, Duration::from_secs(5), proc).await;
        assert_eq!(got, ["2", "3", "4"]);
        assert_eq!(
            *vistos.lock().unwrap(),
            ["a", "falha"],
            "nada depois da falha pode rodar"
        );
    }

    #[tokio::test(start_paused = true)]
    async fn fifo_estouro_de_prazo_e_panico_contam_como_falha() {
        let lenta = |_p: Pedido| async move {
            tokio::time::sleep(Duration::from_secs(60)).await;
            Ok(())
        };
        let regs = vec![
            msg("1", r#"{"id":"a","valor":1}"#),
            msg("2", r#"{"id":"b","valor":1}"#),
        ];
        assert_eq!(
            processa_fifo(regs, Duration::from_secs(10), lenta).await,
            ["1", "2"]
        );

        let boom = |_p: Pedido| async move { panic!("boom") };
        let regs = vec![msg("1", r#"{"id":"a","valor":1}"#)];
        assert_eq!(
            processa_fifo(regs, Duration::from_secs(10), boom).await,
            ["1"]
        );
    }
}
```

Por que é assim:

- **Resposta só com os `messageId` que falharam** (`ReportBatchItemFailures` na event source mapping). Os tipos de `aws_lambda_events`
  1.x são `#[non_exhaustive]`: construa com `Default` e atribua os campos (literal de struct não compila). Lote sem falhas serializa
  `{"batchItemFailures":[]}` (coberto por teste).
- **Concorrência limitada** com `Semaphore`; o `permit` é solto ao fim da tarefa.
- **Prazo (`timeout_at`)**: ao estourar, `abort_all()` e devolve à fila **tudo** o que não terminou. `prazo_util` reserva ≈ 500 ms para
  responder antes de o Lambda encerrar o ambiente.
- **Pânico por mensagem:** `JoinSet` devolve `JoinError`; o `HashMap<tokio::task::Id, String>` mapeia a tarefa de volta ao `messageId`.
  Isso só funciona com **`panic = "unwind"`** (o padrão). Com `panic = "abort"` um pânico derruba o processo e o lote inteiro volta —
  decisão consciente: ganho de tamanho de binário × isolamento de falha.
- **Entrada hostil:** `#[serde(deny_unknown_fields)]`, validação de `id`/`valor`, `Option<&str>` para corpo ausente. Mensagem inválida
  falha de propósito (vai à DLQ após `maxReceiveCount`).
- Limites genéricos: `F: Fn(Pedido) -> Fut + Send + Sync + Clone + 'static` e `Fut: Send + 'static` — a tarefa é `spawn`ada, então não
  pode emprestar do chamador; clone/`Arc` o estado compartilhado.
- Teste de prazo com `#[tokio::test(start_paused = true)]` (relógio virtual, sem esperar de verdade; exige `tokio` com `test-util`).
- **FIFO:** `processa_fifo` processa **em ordem** e **para na 1ª falha**, devolvendo a que falhou e todas as seguintes (exigência da AWS
  para filas FIFO com resposta parcial); erro, pânico, mensagem inválida e estouro de prazo contam como falha; a tarefa lenta é
  abortada (`abort()`), não deixada solta.

## 3. Pontos de entrada

`src/bin/sqs.rs`:

```rust
use std::time::{Duration, SystemTime};

use aws_lambda_events::event::sqs::{SqsBatchResponse, SqsEvent};
use lambda_runtime::{Error, LambdaEvent, run, service_fn};
use rlam::{ErroMensagem, Pedido, handler_sqs};

async fn processa(p: Pedido) -> Result<(), ErroMensagem> {
    // aqui entram os clientes criados NA INICIALIZAÇÃO (SDK, pool): clonados (Arc) entre invocações
    tracing::info!(id = %p.id, valor = p.valor, "pedido processado");
    Ok(())
}

async fn handler(event: LambdaEvent<SqsEvent>) -> Result<SqsBatchResponse, Error> {
    let restante = event
        .context
        .deadline()
        .duration_since(SystemTime::now())
        .unwrap_or(Duration::ZERO);
    let recebidas = event.payload.records.len();
    let r = handler_sqs(event.payload, restante, 5, processa).await;
    tracing::info!(
        recebidas,
        falhas = r.batch_item_failures.len(),
        "lote concluído"
    );
    Ok(r)
}

#[tokio::main]
async fn main() -> Result<(), Error> {
    lambda_runtime::tracing::init_default_subscriber(); // stdout → CloudWatch; JSON se AWS_LAMBDA_LOG_FORMAT=JSON
    run(service_fn(handler)).await
}
```

`src/bin/http.rs` (API Gateway HTTP API, payload v2):

```rust
use lambda_http::{Body, Error, Request, RequestExt, Response, run, service_fn};

fn json(status: u16, corpo: &serde_json::Value) -> Result<Response<Body>, Error> {
    Ok(Response::builder()
        .status(status)
        .header("content-type", "application/json")
        .header("x-content-type-options", "nosniff")
        .body(Body::Text(corpo.to_string()))?)
}

/// HTTP API (payload v2): GET /pedidos/{id}
async fn handler(req: Request) -> Result<Response<Body>, Error> {
    if req.method() != "GET" || !req.uri().path().starts_with("/pedidos/") {
        return json(404, &serde_json::json!({"erro": "não encontrado"}));
    }
    let id = req
        .path_parameters()
        .first("id")
        .unwrap_or_default()
        .to_owned();
    if id.is_empty() || id.len() > 64 {
        // entrada externa: valide sempre
        return json(400, &serde_json::json!({"erro": "id inválido"}));
    }
    json(200, &serde_json::json!({"id": id, "status": "pago"}))
}

#[tokio::main]
async fn main() -> Result<(), Error> {
    lambda_runtime::tracing::init_default_subscriber(); // stdout → CloudWatch; JSON se AWS_LAMBDA_LOG_FORMAT=JSON
    run(service_fn(handler)).await
}
```

- Prazo: `event.context.deadline()` (um `SystemTime`) → `duration_since(now)`; passe o restante ao lote.
- Valide toda entrada externa (aqui: `id` vazio ou > 64 → 400). Erro de negócio é **resposta** 4xx; `Err` do handler vira 5xx genérico.
- **Logs** (fonte: a documentação do crate no docs.rs, não a página da AWS): `init_default_subscriber()` escreve no stdout e só emite **JSON** quando
  `AWS_LAMBDA_LOG_FORMAT=JSON` (variável que o Lambda define quando a função usa `LoggingConfig.LogFormat: JSON` — veja o template SAM; confirme no
  CloudWatch). O nível vem de `AWS_LAMBDA_LOG_LEVEL`, depois `RUST_LOG`, senão INFO.
  Escrever no stdout pode bloquear brevemente o runtime Tokio sob muita concorrência; em função de alto *throughput* e longa vida,
  considere um *writer* não bloqueante (e então cuide do *flush*, pois não há janela de shutdown garantida).
- Não logue o evento inteiro, o corpo da mensagem nem segredos; use `%` (Display) e campos estruturados.

## 4. Inicialização reaproveitável + idempotência (SDK, DynamoDB)

SQS entrega *pelo menos uma vez*. A guarda abaixo reserva a chave com **lease** (`EM_ANDAMENTO` + prazo) por escrita condicional e marca
`CONCLUIDO` ao fim; erro de infraestrutura **propaga** (não vira "duplicata"). `src/idem.rs`:

```rust
//! Idempotência por chave com "lease" no DynamoDB.
//!
//! Fluxo por mensagem: `reservar` → processar → `concluir`.
//! - 1ª entrega: reserva (EM_ANDAMENTO + lease) e processa;
//! - duplicata enquanto outra invocação processa, ou já concluída: `reservar` devolve `false`;
//! - invocação que morreu: o lease expira e a próxima entrega reserva de novo.
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use aws_sdk_dynamodb::{Client, types::AttributeValue};

/// Erro de infraestrutura (rede, throttling, permissão). Boxed: o `Error` do SDK é grande.
pub type Erro = Box<dyn std::error::Error + Send + Sync>;

pub struct Guarda {
    pub db: Client,
    pub tabela: String, // chave de partição "pk" (S); habilite TTL no atributo "expira"
    pub lease: Duration, // > pior caso de processamento de 1 mensagem
    pub reter: Duration, // por quanto tempo lembrar de chaves concluídas
}

fn epoch(t: SystemTime) -> String {
    t.duration_since(UNIX_EPOCH)
        .map_or(0, |d| d.as_secs())
        .to_string()
}

impl Guarda {
    /// `true` se ESTA invocação deve processar a chave. Erro de infraestrutura propaga (`Err`).
    pub async fn reservar(&self, chave: &str, agora: SystemTime) -> Result<bool, Erro> {
        let r = self
            .db
            .put_item()
            .table_name(&self.tabela)
            .item("pk", AttributeValue::S(chave.into()))
            .item("estado", AttributeValue::S("EM_ANDAMENTO".into()))
            .item("lease", AttributeValue::N(epoch(agora + self.lease)))
            .item("expira", AttributeValue::N(epoch(agora + self.reter)))
            .condition_expression(
                "attribute_not_exists(pk) OR (estado = :andamento AND lease < :agora)",
            )
            .expression_attribute_values(":andamento", AttributeValue::S("EM_ANDAMENTO".into()))
            .expression_attribute_values(":agora", AttributeValue::N(epoch(agora)))
            .send()
            .await;
        match r {
            Ok(_) => Ok(true),
            Err(e)
                if e.as_service_error()
                    .is_some_and(|s| s.is_conditional_check_failed_exception()) =>
            {
                Ok(false)
            }
            Err(e) => Err(e.into()),
        }
    }

    /// Marca a chave como processada (mantida até `expira`).
    pub async fn concluir(&self, chave: &str) -> Result<(), Erro> {
        self.db
            .update_item()
            .table_name(&self.tabela)
            .key("pk", AttributeValue::S(chave.into()))
            .update_expression("SET estado = :ok")
            .expression_attribute_values(":ok", AttributeValue::S("CONCLUIDO".into()))
            .send()
            .await?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use aws_sdk_dynamodb::config::{BehaviorVersion, Credentials, Region};
    use aws_smithy_http_client::test_util::{ReplayEvent, StaticReplayClient};
    use aws_smithy_types::body::SdkBody;

    fn evento(status: u16, tipo: &str, corpo: &str) -> ReplayEvent {
        ReplayEvent::new(
            http::Request::builder().body(SdkBody::empty()).unwrap(),
            http::Response::builder()
                .status(status)
                .header("x-amzn-errortype", tipo)
                .body(SdkBody::from(corpo.to_owned()))
                .unwrap(),
        )
    }

    fn guarda(eventos: Vec<ReplayEvent>) -> Guarda {
        let conf = aws_sdk_dynamodb::Config::builder()
            .behavior_version(BehaviorVersion::latest())
            .region(Region::new("sa-east-1"))
            .credentials_provider(Credentials::new("teste", "teste", None, None, "teste"))
            .http_client(StaticReplayClient::new(eventos))
            .build();
        Guarda {
            db: Client::from_conf(conf),
            tabela: "idem".into(),
            lease: Duration::from_secs(60),
            reter: Duration::from_secs(86_400),
        }
    }

    #[tokio::test]
    async fn primeira_entrega_reserva_e_duplicata_nao() {
        let g = guarda(vec![
            evento(200, "", "{}"),
            evento(
                400,
                "ConditionalCheckFailedException",
                r#"{"__type":"com.amazonaws.dynamodb.v20120810#ConditionalCheckFailedException","message":"x"}"#,
            ),
        ]);
        let t = UNIX_EPOCH + Duration::from_secs(1_800_000_000);
        assert!(g.reservar("msg-1", t).await.unwrap());
        assert!(!g.reservar("msg-1", t).await.unwrap());
    }

    #[tokio::test]
    async fn erro_de_infra_nao_vira_duplicata() {
        let g = guarda(vec![evento(
            400,
            "ValidationException",
            r#"{"__type":"com.amazonaws.dynamodb.v20120810#ValidationException","message":"x"}"#,
        )]);
        assert!(g.reservar("k", UNIX_EPOCH).await.is_err());
    }
}
```

Ponto de entrada com os clientes criados **uma vez**, antes de `run` (`src/main.rs`):

```rust
//! Lambda SQS com idempotência (DynamoDB) — clientes criados UMA vez, na inicialização.
use std::sync::Arc;
use std::time::{Duration, SystemTime};

use aws_config::BehaviorVersion;
use aws_lambda_events::event::sqs::{SqsBatchResponse, SqsEvent};
use lambda_runtime::{Error, LambdaEvent, run, service_fn};
use rdyn::idem::Guarda;
use rlam::{ErroMensagem, Pedido, handler_sqs};

async fn processa(guarda: Arc<Guarda>, p: Pedido) -> Result<(), ErroMensagem> {
    let chave = format!("pedido:{}", p.id);
    let falha = |e: rdyn::idem::Erro| ErroMensagem::Processamento(e.to_string());
    if !guarda
        .reservar(&chave, SystemTime::now())
        .await
        .map_err(falha)?
    {
        return Ok(()); // duplicata (ou em andamento): sucesso, descarta
    }
    // ... efeito colateral IDEMPOTENTE aqui (UPSERT, escrita condicional) ...
    guarda.concluir(&chave).await.map_err(falha)
}

async fn handler(
    event: LambdaEvent<SqsEvent>,
    guarda: Arc<Guarda>,
) -> Result<SqsBatchResponse, Error> {
    let restante = event
        .context
        .deadline()
        .duration_since(SystemTime::now())
        .unwrap_or(Duration::ZERO);
    let proc = move |p: Pedido| processa(Arc::clone(&guarda), p);
    Ok(handler_sqs(event.payload, restante, 5, proc).await)
}

#[tokio::main]
async fn main() -> Result<(), Error> {
    lambda_runtime::tracing::init_default_subscriber(); // stdout → CloudWatch; JSON se AWS_LAMBDA_LOG_FORMAT=JSON
    let conf = aws_config::defaults(BehaviorVersion::latest()).load().await; // credenciais, região, endpoint
    let guarda = Arc::new(Guarda {
        db: aws_sdk_dynamodb::Client::new(&conf),
        tabela: std::env::var("TABELA_IDEM")?,
        lease: Duration::from_secs(120),
        reter: Duration::from_secs(86_400),
    });
    run(service_fn(move |ev| handler(ev, Arc::clone(&guarda)))).await
}
```

- `Arc<Guarda>` é clonado por invocação e por tarefa; o `Client` do SDK já é barato de clonar.
- `aws_config::defaults(BehaviorVersion::latest())` resolve credenciais, região e endpoint (LocalStack: `AWS_ENDPOINT_URL`) do ambiente.
- Erro boxed (`Box<dyn Error + Send + Sync>`): o `Error` do SDK é grande e o `clippy::result_large_err` reclama.
- Chave de idempotência **reduz** duplicatas; só efeito idempotente (UPSERT, escrita condicional) garante o resultado. Habilite **TTL** no
  atributo `expira` (`ttl` é palavra reservada no DynamoDB).
- Verificado com cliente HTTP **simulado** (`StaticReplayClient`: compila e passa em teste); **não** foi executado contra o DynamoDB real
  nem LocalStack — faça o teste de integração no seu ambiente.

## 5. Panic: `unwind` × `abort`

| | `panic = "unwind"` (padrão) | `panic = "abort"` |
|---|---|---|
| Pânico numa mensagem | vira falha **só dela** (`JoinError`) | derruba o processo; o Lambda reinicia o ambiente e o **lote inteiro** volta |
| Binário | um pouco maior | menor |
| Quando | processamento de lote com isolamento (padrão desta skill) | função de uma única responsabilidade onde qualquer pânico deve reiniciar |

Em qualquer caso: nada de `unwrap()`/`expect()` em dado de evento; erros tipados (`thiserror`) → **rust-pro**.

## 6. Build para `arm64` e tamanho do pacote

### Sem SDK de serviço (handlers acima) — verificado

Compila para `aarch64-unknown-linux-musl` **sem toolchain C**, usando o `rust-lld` que acompanha o Rust (o grafo de dependências é Rust puro):

```bash
rustup target add aarch64-unknown-linux-musl
RUSTFLAGS="-C linker=rust-lld" cargo build --release --target aarch64-unknown-linux-musl --bins
cp target/aarch64-unknown-linux-musl/release/sqs bootstrap      # o executável chama-se "bootstrap" e fica na RAIZ do zip
file bootstrap                                                  # ELF 64-bit ... ARM aarch64 ... statically linked, stripped
```

### Com SDK da AWS (rustls) — verificado

O SDK da AWS usa `rustls`, cuja criptografia (`aws-lc-rs`) **compila código C** — para o alvo `arm64` é preciso um toolchain C. Verificado
com **Zig** via `cargo-zigbuild` (sem instalar um GCC cruzado):

```bash
pip install ziglang                                   # fornece o zig (verificado com 0.16.0)
cargo install cargo-zigbuild                          # verificado com 0.23.4
rustup target add aarch64-unknown-linux-musl
CARGO_PROFILE_RELEASE_LTO=fat CARGO_PROFILE_RELEASE_OPT_LEVEL=s \
  cargo zigbuild --release --target aarch64-unknown-linux-musl     # ELF aarch64, estático
```

`lto = "fat"` + `opt-level = "s"` custam tempo de compilação (≈ 4–5 min numa máquina de 2 CPUs) e podem custar velocidade de execução:
meça (→ **rust-performance-engineer**). Fixe as versões do Zig e do `cargo-zigbuild` na CI (supply chain).

### Tamanhos medidos (handler SQS/HTTP de exemplo; `lto = "thin"`, `strip = "symbols"`)

| Binário | Alvo | Tamanho |
|---|---|---|
| `sqs` | `aarch64-unknown-linux-musl` | **2,13 MB** (1,06 MB zipado) |
| `http` | `aarch64-unknown-linux-musl` | 2,82 MB |
| `sqs` | x86_64 glibc (host) | 2,30 MB |
| `http` | x86_64 glibc (host) | 3,11 MB |
| `rdyn` (SQS + `aws-sdk-dynamodb` + `aws-config`) | x86_64 glibc (host), LTO thin | 15,41 MB |
| `rdyn` | x86_64 glibc (host), `lto = "fat"` + `opt-level = "s"` | 8,75 MB |
| `rdyn` | `aarch64-unknown-linux-musl` (zigbuild), `lto = "fat"` + `opt-level = "s"` | **7,32 MB** (3,56 MB zipado) |

Para comparação, o equivalente em Go (`cmd/sqsdyn`, arm64, `norpc`, `-s -w`) ficou em 9,77 MB (3,70 MB zipado).

O SDK pesa muito mais que o handler. Antes de adicionar um cliente, confirme que precisa dele (P1/P3); cada serviço soma ao pacote, e o
tamanho do pacote pesa no cold start.

## 7. Managed Instances, cargo-lambda e variações

- **Lambda Managed Instances (documentado para Rust):** MSRV **1.84.0**; `lambda_runtime` ≥ 1.1.1 com a feature `concurrency-tokio` **e** `lambda_runtime::run_concurrent(...)` dentro do Tokio (com `run` não há
  concorrência); **8 requisições concorrentes por vCPU** (padrão, ajustável na configuração `PerExecutionEnvironmentMaxConcurrency`); várias invocações compartilham o processo → estado compartilhado via `Arc` (tipos
  `Send + Sync`), `/tmp` compartilhado (nomes de arquivo únicos), sem estado global mutável por requisição. A init pode usar o maior entre 130 s e o timeout configurado (máx. 900 s).
  Go em Managed Instances **não está documentado**.
- **`cargo-lambda`:** ferramenta de terceiros (compila e empacota; segundo o projeto, usa Zig para o *cross-link*). Cômoda, mas **não** é exigida: o `cargo build`
  acima basta (sem SDK). Não verificada nesta skill — o que foi verificado é `cargo-zigbuild`. Se adotar, fixe a versão, trate como dependência de supply chain (→ **rust-unsafe-security**) e confirme o artefato
  (`file bootstrap`).
- **Imagem de contêiner:** permitida (o nome do executável é livre); o pacote `.zip` com `bootstrap` na raiz continua o caminho mais simples.

## 8. Gates

```bash
cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
cargo deny check && cargo audit          # supply chain (→ rust-unsafe-security)
RUSTFLAGS="-C linker=rust-lld" cargo build --release --target aarch64-unknown-linux-musl --bins
```
