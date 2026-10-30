# tokio e concorrência assíncrona — receitas verificadas

> Autoral (Squad AI). Código **compilado e testado** com `rustc 1.99.0`, tokio 1.53.2, tokio-util 0.7.19, futures 0.3.34 (edição 2024; clippy `-D warnings`).
> A tabela de *cancel safety* foi extraída das seções `# Cancel safety` da documentação do tokio 1.53.2 — confira a doc da sua versão ao depender de um caso limite.

## 1. Modelo mental

- O **runtime** multiplexa muitas *tarefas* (`async` blocks) em poucas **threads de trabalho**. Padrão: uma thread por CPU disponível
  (`std::thread::available_parallelism`, que considera afinidade e **quotas de cgroup** no Linux; sobrescreva com `TOKIO_WORKER_THREADS` ou `Builder::worker_threads`).
- Uma tarefa só troca de lugar nos pontos de **`.await`**. Código sem `.await` por muito tempo **monopoliza a thread** (bloqueio): todas as outras tarefas daquela thread esperam.
- `#[tokio::main]` = runtime multi-thread; `#[tokio::main(flavor = "current_thread")]` = uma thread (CLI, testes, `!Send`). Em testes, `#[tokio::test]` usa `current_thread` por padrão.
- **`spawn` exige `Send + 'static`**: o future pode migrar de thread e viver mais que o escopo atual. Daí os erros típicos (§7) — clone/mova o que a tarefa precisa (`Arc`, `Sender`, `CancellationToken`) para dentro dela.

## 2. Tarefas: criar, aguardar, cancelar

| Preciso de… | Use | Observações |
|---|---|---|
| uma tarefa em segundo plano | `tokio::spawn` | guarde o `JoinHandle`; pânico na tarefa vira `JoinError` no `.await` do handle |
| N tarefas dinâmicas com término coletivo | `JoinSet` | `spawn`, `join_next().await`; ao dropar o `JoinSet`, **aborta** as tarefas restantes |
| rodar N futures concorrentes **sem** `spawn` | `futures::stream::iter(..).map(..).buffer_unordered(n)` | sem `'static`; roda dentro da tarefa atual (não paraleliza entre threads) |
| 2–3 futures fixos | `tokio::join!` / `try_join!` | `try_join!` cancela os demais no primeiro erro |
| CPU pesada ou API bloqueante | `tokio::task::spawn_blocking` | pool separado (padrão 512 threads); **não cancelável** depois de iniciada |
| esperar um evento com prazo | `tokio::time::timeout(d, fut)` | ao expirar, **descarta** `fut` (vale a seção 4) |
| tarefa `!Send` | `LocalSet` + `spawn_local` (ou runtime `current_thread`) | |

```rust
/// Trabalho CPU-bound fora do executor async. Propaga o `JoinError` (pânico/cancelamento) em vez de derrubar o chamador.
pub async fn hash_pesado(data: Vec<u8>) -> Result<u64, tokio::task::JoinError> {
    tokio::task::spawn_blocking(move || {
        data.iter().fold(0xcbf2_9ce4_8422_2325_u64, |h, b| {
            (h ^ u64::from(*b)).wrapping_mul(0x0100_0000_01b3)
        })
    })
    .await
}

/// Toda chamada externa precisa de prazo.
pub async fn com_prazo<T>(f: impl Future<Output = T>, d: Duration) -> Result<T, &'static str> {
    tokio::time::timeout(d, f).await.map_err(|_| "prazo excedido")
}
```

- **Quando é "bloqueio"?** `std::fs::*`, `std::thread::sleep`, `reqwest::blocking`, hash de senha (argon2/bcrypt), compressão, parsing de arquivo grande, laço longo sem `.await`.
  Em dúvida, meça; para laços CPU-bound longos mas assíncronos, `tokio::task::yield_now().await` de tempos em tempos devolve a vez às outras tarefas.
- `block_in_place` só em runtime multi-thread e quando `spawn_blocking` não serve (precisa emprestar dados); **nunca** em `current_thread` (entra em pânico).
- Nunca chame `Runtime::block_on`/`Handle::block_on` de dentro de código `async` (deadlock/pânico "Cannot start a runtime from within a runtime").

## 3. Canais — escolha pelo padrão de comunicação

| Canal | Quando | Cuidado |
|---|---|---|
| `mpsc::channel(N)` | fila de trabalho / ator; 1+ produtores → 1 consumidor | **sempre limitado**: quando enche, `send().await` espera (*backpressure*) |
| `mpsc::unbounded_channel` | só se o produtor é naturalmente limitado e curto (ex.: sinal de controle) | em caminho de carga vira OOM |
| `oneshot` | **uma** resposta a um pedido | `Sender::send` falha se o receptor desistiu — ignorar é correto |
| `broadcast` | N consumidores recebem **todas** as mensagens (eventos) | consumidor lento recebe `Lagged` e perde mensagens |
| `watch` | N consumidores só querem o **último valor** (config, estado de saúde) | não há fila: valores intermediários se perdem por desenho |
| `Notify` | acordar sem dados | |
| `CancellationToken` (tokio-util) | cancelar uma árvore de tarefas | `child_token()` para escopos aninhados; `token.cancelled().await` em `select!` |

### Ator: estado privado + `mpsc` + `oneshot` (sem Mutex)

Em vez de `Arc<Mutex<HashMap>>` disputado por todos, **uma tarefa é dona do estado** e todos falam com ela por mensagens:

```rust
use std::collections::HashMap;
use tokio::sync::{mpsc, oneshot};

#[derive(Debug)]
pub enum Cmd {
    Incrementa { chave: String, resp: oneshot::Sender<u64> },
    Le { chave: String, resp: oneshot::Sender<Option<u64>> },
}

#[derive(Clone, Debug)]
pub struct Contadores { tx: mpsc::Sender<Cmd> }

#[derive(Debug, thiserror::Error)]
#[error("ator encerrado")]
pub struct AtorEncerrado;

impl Contadores {
    #[must_use]
    pub fn iniciar() -> (Self, tokio::task::JoinHandle<()>) {
        let (tx, mut rx) = mpsc::channel::<Cmd>(64);      // fila LIMITADA
        let tarefa = tokio::spawn(async move {
            let mut estado: HashMap<String, u64> = HashMap::new(); // estado PRIVADO
            while let Some(cmd) = rx.recv().await {
                match cmd {
                    Cmd::Incrementa { chave, resp } => {
                        let v = estado.entry(chave).or_default();
                        *v += 1;
                        let _ = resp.send(*v);             // o chamador pode ter desistido
                    }
                    Cmd::Le { chave, resp } => { let _ = resp.send(estado.get(&chave).copied()); }
                }
            }
            // todos os Sender descartados → laço termina → a tarefa encerra sozinha
        });
        (Self { tx }, tarefa)
    }

    pub async fn incrementa(&self, chave: &str) -> Result<u64, AtorEncerrado> {
        let (resp, rx) = oneshot::channel();
        self.tx.send(Cmd::Incrementa { chave: chave.to_owned(), resp }).await.map_err(|_| AtorEncerrado)?;
        rx.await.map_err(|_| AtorEncerrado)
    }
}
```

Teste (verificado): 100 `incrementa("a")` concorrentes → `le("a") == Some(100)`; ao descartar o último handle o ator termina e o `JoinHandle` resolve.
Use ator quando o estado tem **invariantes entre campos** ou operações compostas; para um contador simples, `AtomicU64` basta (P1).

## 4. `select!` e *cancel safety*

`select!` aguarda vários futures e, quando um completa, **descarta os outros no ponto do `.await` em que estavam**. Um future é *cancel-safe* se descartá-lo não perde dado nem deixa efeito parcial.

### A armadilha (comportamento verificado com tempo virtual)

```rust
/// ARMADILHA: se o `select!` escolher outro ramo, só o `push(1)` aconteceu — estado pela metade.
pub async fn escreve_em_duas_etapas(buf: &mut Vec<u8>) {
    buf.push(1);
    sleep(Duration::from_millis(10)).await; // ← ponto de cancelamento
    buf.push(2);                            // nunca roda se o future for descartado antes
}

/// CORREÇÃO: todo o `.await` ANTES; a mutação depois, de uma vez e de forma síncrona.
pub async fn escreve_atomico(buf: &mut Vec<u8>) {
    sleep(Duration::from_millis(10)).await;
    buf.extend([1, 2]);
}

#[tokio::test(start_paused = true)]
async fn select_descarta_e_deixa_estado_parcial() {
    let mut buf = Vec::new();
    tokio::select! {
        () = escreve_em_duas_etapas(&mut buf) => {}
        () = sleep(Duration::from_millis(5)) => {}
    }
    assert_eq!(buf, [1]);   // metade da mutação — o bug
}
```

### Tabela (da documentação do tokio 1.53.2)

| Operação | Cancel-safe? | Se descartada… |
|---|---|---|
| `mpsc::Receiver::recv`, `recv_many`, `mpsc::Sender::closed`; `unbounded` idem | **sim** | nenhuma mensagem é perdida |
| `oneshot::Receiver` (`&mut rx`), `broadcast::Receiver::recv`, `watch::Receiver::changed` | **sim** | |
| `JoinHandle` (`&mut handle`), `JoinSet::join_next` | **sim** | a saída da tarefa não se perde |
| `TcpListener::accept`, `time::interval().tick()` | **sim** | |
| `AsyncReadExt::read`, `read_buf`, `read_u8`, `fill_buf`; `lines().next_line()`; `AsyncWriteExt::write`, `write_buf`, `flush` | **sim** | |
| `AsyncReadExt::read_exact`, `read_u16/u32/u64…` (e `_le`), `read_to_end` | **não** | bytes já lidos **se perdem** |
| `AsyncBufReadExt::read_line`, `read_until` | **não** | dados parciais perdidos |
| `AsyncWriteExt::write_all` | **não** | parte do buffer já foi escrita |
| `mpsc::Sender::send` | parcial | a mensagem **não** é enviada e **é descartada** — use `reserve()` para não perder |
| `Mutex::lock`, `RwLock::{read,write}`, `Semaphore::acquire`, `Notify::notified` | sim, mas… | **perde a vez na fila** (fila justa) |

Regras práticas:

1. **Não recrie futures longos a cada volta do laço.** Fixe uma vez e reaproveite:

   ```rust
   let sinal = token.cancelled();
   tokio::pin!(sinal);
   loop {
       tokio::select! {
           biased;                                   // cancelamento tem prioridade sobre trabalho
           () = &mut sinal => break,                 // não é recriado a cada iteração
           msg = rx.recv() => match msg {
               Some(m) => tratar(m).await,
               None => break,                        // canal fechado
           },
       }
   }
   ```

   Cuidado com o ramo `else`: ele só executa quando **todos** os ramos estão desabilitados. Com `Some(msg) = rx.recv() => …, else => break`, ao fechar o canal o ramo de `recv` se desabilita,
   mas o ramo do `sinal` continua pendente — o `select!` **espera para sempre** (bug real encontrado ao testar esta receita). Trate `None` explicitamente, como acima.

2. **Dentro do corpo de um ramo, o `.await` é seguro** (o ramo já foi escolhido). O risco é no **future do ramo** (a expressão antes de `=>`).
3. Para I/O de mensagens, leia com um *framed codec* (`tokio_util::codec`) em vez de `read_exact` dentro de `select!`.
4. `timeout(d, fut)` é um `select!` disfarçado: se `fut` não for cancel-safe, o timeout deixa estado parcial. Coloque o `timeout` **em volta de uma operação atômica** ou desenhe para retomar.
5. `biased;` no `select!` define prioridade explícita (ex.: cancelamento antes de trabalho); sem ele a ordem é aleatória por justiça.

## 5. Concorrência limitada (fan-out com backpressure)

```rust
/// No máximo `limite` tarefas em voo; resultados na ordem de entrada.
pub async fn mapear_limitado<F, Fut, T>(ids: Vec<u64>, limite: usize, f: F) -> Vec<T>
where
    F: Fn(u64) -> Fut + Clone + Send + 'static,
    Fut: Future<Output = T> + Send + 'static,
    T: Send + 'static,
{
    let sem = Arc::new(Semaphore::new(limite));
    let mut set = JoinSet::new();
    for (i, id) in ids.into_iter().enumerate() {
        // adquire ANTES de criar a tarefa: o produtor é freado em vez de enfileirar milhares de tarefas
        let Ok(permit) = sem.clone().acquire_owned().await else { break };
        let f = f.clone();
        set.spawn(async move {
            let r = f(id).await;
            drop(permit);                   // libera a vaga ao terminar
            (i, r)
        });
    }
    let mut out = Vec::new();
    while let Some(r) = set.join_next().await {
        if let Ok(par) = r { out.push(par); } // JoinError (pânico na tarefa): registre/propague conforme o caso
    }
    out.sort_unstable_by_key(|(i, _)| *i);
    out.into_iter().map(|(_, t)| t).collect()
}
```

Teste verificado com tempo virtual: 20 itens, limite 3 ⇒ **pico de 3** tarefas simultâneas (contador atômico), resultado na ordem de entrada.
Alternativa sem `spawn`: `stream::iter(ids).map(|id| async move { … }).buffer_unordered(n).fold(…)` (verificado: soma 1..=10 dobrada = 110).
Para trabalho que pode falhar, acumule `Result` e decida: **fail-fast** (`try_join_all`/`JoinSet` + `abort_all()`) ou **coletar tudo** (relatório de falhas parciais).

### Pool de workers com cancelamento

O padrão `mpsc` limitado + N workers + `CancellationToken` + `JoinSet` está implementado e testado (50 itens processados; token cancelado ⇒ para cedo). Pontos essenciais:

- o **produtor** fecha o canal ao terminar (drop do `Sender`) ⇒ os workers saem ao esvaziar a fila;
- cada worker usa `select!` com `cancel.cancelled()` **e** `recv()` (ambos cancel-safe);
- o agregador lê até o canal de saída fechar e só então `join`a as tarefas.

## 6. Estado compartilhado

- **Prefira passar mensagens** (§3) a compartilhar. Quando compartilhar: `Arc<T>` imutável (config) · `AtomicXxx` (contadores/flags) · `Arc<RwLock<T>>`/`Arc<Mutex<T>>` (estado composto).
- **`std::sync::Mutex` × `tokio::sync::Mutex`:** use o **`std`** (ou `parking_lot`) quando a seção crítica é curta e **não contém `.await`** — é mais rápido. Use o **`tokio`** só quando o guard precisa atravessar um `.await`.
  Melhor ainda: reestruture para que o lock não cubra `.await` (copie o dado, solte o lock, faça a chamada).
- Substituição atômica de config lida com frequência: `watch` ou `arc-swap` (terceiros).
- Mapa concorrente com muita contenção: `dashmap` (terceiros) ou sharding; meça antes (→ rust-performance-engineer).

## 7. Erros de compilação típicos em async (reais, rustc 1.99.0)

**`MutexGuard` atravessando `.await` dentro de `spawn`:**

```text
error: future cannot be sent between threads safely
  = help: the trait `Send` is not implemented for `std::sync::MutexGuard<'_, i32>`
note: future is not `Send` as this value is used across an await
  7 |         let mut g = m.lock().unwrap();
    |             ----- has type `MutexGuard<'_, i32>` which is not `Send`
  8 |         tokio::time::sleep(Duration::from_millis(1)).await;
    |                                                            ^^^^^ await occurs here, with `mut g` maybe used later
note: required by a bound in `tokio::spawn`  (F: Future + Send + 'static)
```

Correção: soltar o guard antes do `.await` (`{ let mut g = m.lock()…; *g += 1; }` num bloco) ou usar `tokio::sync::Mutex` se o lock precisa cobrir a espera.
O mesmo erro aparece com `Rc<_>`, `RefCell` emprestado, ponteiros brutos ou *thread-local* guards atravessando `.await`. Catálogo completo e receitas → **rust-error-investigator**.

**`async fn` em trait pública:** o lint `async_fn_in_trait` avisa que o chamador não pode exigir `Send`. Declare `fn get(&self, id: u64) -> impl Future<Output = Option<String>> + Send;`
(os `impl` podem continuar escritos como `async fn`). Despacho dinâmico (`dyn Trait`) com async continua exigindo `Box<dyn Future>`/crate `async-trait` — prefira genéricos.

## 8. Tempo, intervalos e testes determinísticos

- `tokio::time::interval(d)`: o primeiro `tick()` completa **imediatamente**; ajuste `set_missed_tick_behavior(MissedTickBehavior::Delay | Skip)` conforme o trabalho possa atrasar (padrão `Burst` recupera todos os ticks perdidos de uma vez).
- Prazo global de uma operação com várias etapas: calcule `let limite = Instant::now() + d;` e use `timeout_at(limite, …)` em cada etapa — o prazo **não reinicia** a cada chamada.
- **Tempo virtual nos testes:** `#[tokio::test(start_paused = true)]` (exige `tokio` com a feature `test-util` em `[dev-dependencies]`). Quando todas as tarefas estão ociosas, o relógio avança sozinho até o próximo temporizador:

  ```rust
  #[tokio::test(start_paused = true)]
  async fn prazo_com_tempo_virtual() {
      let r = com_prazo(tokio::time::sleep(Duration::from_secs(3600)), Duration::from_secs(5)).await;
      assert_eq!(r, Err("prazo excedido")); // 1 hora simulada, 0 s reais
  }
  ```

  `tokio::time::advance(d)` avança manualmente. **Nunca** `std::thread::sleep` em teste async.
- Teste de concorrência real (sem tempo virtual): `#[tokio::test(flavor = "multi_thread", worker_threads = 4)]`; use `JoinSet` e verifique invariantes (sem sleeps para "dar tempo").

## 9. Diagnóstico de tarefas travadas

- Sintoma: requisições penduradas, CPU baixa ⇒ provável **deadlock lógico** (lock/canal cheio/esperando resposta que nunca vem) ou **tarefa bloqueando o executor** (CPU alta em 1 thread).
- `tokio-console` (terceiros) mostra tarefas, *polls* longos e tempos de espera — exige `RUSTFLAGS="--cfg tokio_unstable"` e a camada `console-subscriber` (**só em ambiente de teste**: expõe estado interno).
- `tracing` com `#[instrument]` + `RUST_LOG=trace` no escopo suspeito; `Handle::current().metrics()` (parte estável + extras com `tokio_unstable`) para fila de tarefas e workers ocupados.
- Aumentar `worker_threads` **não** corrige bloqueio de executor — isole o trabalho bloqueante em `spawn_blocking`.
