# Catálogo de erros Rust — mensagem → causa → checagem → correção

> Autoral (Squad AI). As mensagens abaixo foram **capturadas do toolchain rustc 1.99.0 / cargo 1.99.0 (e cargo 1.95.0 onde indicado)**, edição 2024 salvo menção; caminhos abreviados e rótulos `-->` encurtados. O *wording* muda um pouco entre versões — compare com a sua saída.
> Cada exemplo é um programa mínimo que reproduz o erro. Use junto com o protocolo do `error-investigator`: classifique, **colete evidência**, diagnostique, só então corrija. `rustc --explain E0xxx` dá a explicação oficial.

## 1. Borrow checker: movimento, empréstimo e tempo de vida

### E0382 — uso de valor movido

```rust
let s = String::from("a");
let t = s;
println!("{s} {t}");
```

```text
error[E0382]: borrow of moved value: `s`
2 |     let s = String::from("a");
  |         - move occurs because `s` has type `String`, which does not implement the `Copy` trait
3 |     let t = s;
  |             - value moved here
4 |     println!("{s} {t}");
  |                ^ value borrowed here after move
help: consider cloning the value if the performance cost is acceptable
```

Causa: `String` é *owned* e não `Copy`; `let t = s` **move**. Correções, em ordem: (1) emprestar (`let t = &s;`); (2) usar só `t` depois; (3) `clone()` **somente** se duas cópias independentes são a intenção. Em laço: `for x in v` consome `v` — use `for x in &v`/`.iter()`. Em closure: `move` leva ownership.

### E0499 / E0502 — empréstimos conflitantes

```text
error[E0499]: cannot borrow `v` as mutable more than once at a time
3 |     let a = &mut v;   ------ first mutable borrow occurs here
4 |     let b = &mut v;   ^^^^^^ second mutable borrow occurs here
5 |     a.push(1);        - first borrow later used here

error[E0502]: cannot borrow `v` as mutable because it is also borrowed as immutable
3 |     let first = &v[0];       - immutable borrow occurs here
4 |     v.push(4);               ^^^^^^^^^ mutable borrow occurs here
5 |     println!("{first}");     ----- immutable borrow later used here
```

Leia os três rótulos: **onde nasce**, **onde conflita**, **onde ainda é usado** — a correção é fazer o último uso do 1º empréstimo acontecer **antes** do conflito (copie o valor `let first = v[0];`, use e solte, reordene as linhas) ou separar os dados (campos distintos de uma `struct` são emprestáveis independentemente; `split_at_mut`, `iter_mut`, `get_disjoint_mut` — 1.86). Para mutar uma coleção percorrendo-a: colete índices/ids e aplique depois, ou `retain`/`extract_if`. **Não** resolva com `Rc<RefCell<_>>` por reflexo.

### E0505 — mover enquanto emprestado

```text
error[E0505]: cannot move out of `s` because it is borrowed
  let r = &s;   --  borrow of `s` occurs here
  let t = s;    ^   move out of `s` occurs here        ... println!("{r} {t}") ← borrow later used here
```

### E0507 — mover de trás de referência

```rust
struct S { name: String }
let r = &s; let n = r.name;
```

```text
error[E0507]: cannot move out of `r.name` which is behind a shared reference
help: consider borrowing here          →  let n = &r.name;
help: consider cloning the value ...   →  let n = r.name.clone();
```

Se precisa **tirar** o valor de dentro de um `&mut`: `Option::take()`, `std::mem::take`/`replace`. Se quer ficar com o dado, a função deveria receber ownership (`self`/`S`), não `&S`.

### E0597 / E0515 / E0716 — a referência sobrevive ao dono

```text
error[E0597]: `x` does not live long enough
  { let x = 5; r = &x; }   ← `x` dropped here while still borrowed
  println!("{r}");          ← borrow later used here

error[E0515]: cannot return reference to local variable `s`
    &s   ^^ returns a reference to data owned by the current function

error[E0716]: temporary value dropped while borrowed
  let r: &str = String::from("abc").as_str();   ← temporary value is freed at the end of this statement
help: consider using a `let` binding to create a longer lived value
```

Correção: devolva **owned** (`String`), eleve o dono ao escopo maior (`let binding = String::from("abc"); let r = binding.as_str();`), ou mude o design para o dono viver mais. Retornar `&'static str` de dado local nunca funciona.

### E0106 e "lifetime may not live long enough"

```text
error[E0106]: missing lifetime specifier
fn longest(a: &str, b: &str) -> &str
  = help: this function's return type contains a borrowed value, but the signature does not say whether it is borrowed from `a` or `b`
help: consider introducing a named lifetime parameter   →  fn longest<'a>(a: &'a str, b: &'a str) -> &'a str

error: lifetime may not live long enough
fn f<'a, 'b>(x: &'a str, _y: &'b str) -> &'b str { x }
  ... function was supposed to return data with lifetime `'b` but it is returning data with lifetime `'a`
  = help: consider adding the following bound: `'a: 'b`
```

Lifetime na assinatura **descreve uma relação** (o retorno vem de qual argumento). Antes de acrescentar `'a: 'b`, pergunte: a relação é verdadeira? Se não, devolva owned ou mude qual argumento é devolvido.

### E0373 / E0521 — `'static` exigido por `thread::spawn`/`tokio::spawn`

```text
error[E0373]: closure may outlive the current function, but it borrows `n`, which is owned by the current function
  let h = std::thread::spawn(|| println!("{n}"));
note: function requires argument type to outlive `'static`
help: to force the closure to take ownership of `n` (and any other referenced variables), use the `move` keyword

error[E0521]: borrowed data escapes outside of function
fn f(s: &str) { std::thread::spawn(|| println!("{s}")); }
  `s` escapes the function body here · argument requires that `'1` must outlive `'static`
```

`move` resolve o **E0373** quando a variável é `Copy`/owned. O **E0521** é diferente: `s` é uma **referência** de duração desconhecida — `move` leva a referência, não o dado. Passe dado **owned** (`s.to_owned()`/`Arc<str>`), ou use `std::thread::scope` (threads com escopo emprestam à vontade) — em async, `JoinSet`/`Arc`.

## 2. Tipos, traits e inferência

```text
error[E0308]: mismatched types
fn f() -> i32 { "texto" }          expected `i32`, found `&str`  (expected `i32` because of return type)

error[E0282]: type annotations needed for `Vec<_>`
let v = Vec::new(); println!("{}", v.len());
help: consider giving `v` an explicit type   →  let v: Vec<T> = Vec::new();

error[E0599]: no method named `nao_existe` found for struct `T` in the current scope

error[E0369]: cannot add `T` to `T`
fn soma<T>(a: T, b: T) -> T { a + b }
help: consider restricting type parameter `T` with trait `Add`   →  fn soma<T: std::ops::Add<Output = T>>(...)

error[E0046]: not all trait items implemented, missing: `b`

error[E0038]: the trait `Clonavel` is not dyn compatible
  ...because method `dup` references the `Self` type in its return type
  = help: consider moving `dup` to another trait

error[E0277]: `Rc<i32>` cannot be sent between threads safely
  = help: within `{closure@…}`, the trait `Send` is not implemented for `Rc<i32>`
note: required by a bound in `spawn`   (F: Send + 'static)
```

| Código | Pergunta-chave | Correção típica |
|---|---|---|
| E0308 | qual tipo era esperado e **por quê** (retorno, argumento, `if`/`match` com ramos diferentes)? | converta explicitamente (`.into()`, `try_from`, `as` só em numéricos seguros), corrija o ramo, `?` com `From` do erro |
| E0282/E0283 | o compilador não achou o tipo | anotação, *turbofish* (`collect::<Vec<_>>()`, `parse::<u32>()`) |
| E0599 | método existe? trait no escopo? bound satisfeito? | `use Trait;`, `derive`, `where T: Bound`; variante errada de `Option`/`Result` |
| E0369 / E0277 (operador/trait) | falta o *bound* | `T: Add<Output = T>`, `T: Display`, `T: Clone`… (a sugestão do compilador costuma servir) |
| E0046 | impl incompleto | implemente os itens listados (ou dê *default* no trait) |
| E0038 | trait não pode virar objeto (`dyn`) | tire `-> Self`/genéricos do trait objeto, `where Self: Sized` no método, ou use genéricos/`enum` em vez de `dyn` |
| E0277 `Send` | tipo `!Send` cruzando thread | `Rc`→`Arc`, `RefCell`→`Mutex`/`RwLock` (ver §4 p/ `.await`) |
| E0603 / E0616 | item/campo privado | `pub`/`pub(crate)` **conscientemente** ou use a API pública (construtor/getter) |
| E0433 / E0432 / E0425 | `use of undeclared type`, `unresolved import`, `cannot find value` | falta `use std::collections::HashMap;` (a mensagem sugere), módulo/crate errado (`could not find 'colecoes' in 'std'`), erro de digitação (`a local variable with a similar name exists`) |
| E0381 | `used binding isn't initialized` | inicialize ou garanta atribuição em **todos** os ramos |
| E0384 / E0596 | variável imutável (`cannot assign twice`, `cannot borrow as mutable`) | `let mut` — **só se** a mutação é mesmo o design |
| E0015 | função não-`const` em `const` | marque a função `const fn`, ou use `LazyLock`/`OnceLock` em vez de `const` |
| E0133 | chamada `unsafe` fora de bloco | **não** envolva em `unsafe` sem provar o contrato → **rust-unsafe-security** |

## 3. Edição 2024 e versão do compilador

```text
error: extern blocks must be unsafe
extern "C" { fn abs(x: i32) -> i32; }          →  unsafe extern "C" { fn abs(x: i32) -> i32; }  (itens podem ser `safe fn`)

error: unsafe attribute used without unsafe
#[no_mangle]                                   →  #[unsafe(no_mangle)]

error: creating a shared reference to mutable static
  = note: `#[deny(static_mut_refs)]` (part of `#[deny(rust_2024_compatibility)]`) on by default
help: use `&raw const` instead to create a raw pointer

error: let chains are only allowed in Rust 2024 or later
if let Some(x) = a && x > 0 { … }              →  edition = "2024" (e Rust ≥ 1.88), ou if-let aninhado/`matches!`

error[E0554]: `#![feature]` may not be used on the stable release channel
  = help: the feature `let_chains` has been stable since `1.88.0` and no longer requires an attribute to enable
```

O último é um exemplo útil: **o compilador diz desde qual versão o recurso é estável** — remova o `#![feature]`; não "mude para nightly". `cargo fix --edition` migra a maior parte; revise o diff e comite isolado → **rust-pro**.

## 4. Async: `Send`, runtime e tarefas

```text
error: future cannot be sent between threads safely
  tokio::spawn(async move { let g = m.lock().unwrap(); tokio::time::sleep(…).await; println!("{}", *g); })
  = help: within `{async block@…}`, the trait `Send` is not implemented for `std::sync::MutexGuard<'_, i32>`
note: future is not `Send` as this value is used across an await
  let g = m.lock().unwrap();    - has type `std::sync::MutexGuard<'_, i32>` which is not `Send`
  …sleep(…).await;               ^^^^^ await occurs here, with `g` maybe used later
note: required by a bound in `tokio::spawn`   (F: Future + Send + 'static)
```

O compilador aponta o **valor** (`g`) e o **`.await`** que o atravessa. Correções: (1) encurte o escopo — `{ let g = m.lock().unwrap(); … }` e só então `.await`; (2) copie o dado necessário e solte o guard; (3) `tokio::sync::Mutex` **somente** se o lock precisa cobrir o `.await`; (4) uma tarefa dona do estado + canal. Mesmo padrão com `Rc` (`future created by async block is not Send` + `has type Rc<i32> which is not Send`) e `RefCell`. **Verificado no 1.99.0:** `let v = *g; drop(g); …sleep(…).await` **continua** sendo rejeitado com o mesmo erro — o `drop` explícito não encerra o escopo para esta análise; use o **bloco** `{ … }` (ou copie o dado e solte o guard num escopo interno).

Panics em runtime (tokio 1.53):

```text
thread 'main' panicked at src/bin/noreactor.rs:3:14:
there is no reactor running, must be called from the context of a Tokio 1.x runtime
    → usou `tokio::time::sleep`/`TcpStream` fora de um runtime (sem #[tokio::main] / sem `rt.enter()`)

thread 'main' panicked at src/bin/nested.rs:5:8:
Cannot start a runtime from within a runtime. This happens because a function (like `block_on`) attempted to block the current thread while the thread is being used to drive asynchronous tasks.
    → `block_on` dentro de `async`: use `.await`; para código bloqueante use `spawn_blocking`

thread 'tokio-rt-worker' panicked at …: index out of bounds: the len is 0 but the index is 3
is_panic=true -> task 3 panicked with message "index out of bounds: the len is 0 but the index is 3"
    → pânico dentro de `tokio::spawn`: o runtime sobrevive e o `JoinHandle` devolve `Err(JoinError)` — se ninguém dá `.await` no handle, o erro é engolido
```

Mais: tarefa travada/lenta → chamada bloqueante no runtime ou `select!` mal desenhado (`else =>` pode nunca disparar quando um ramo de cancelamento fica pendente — verificado) → **rust-async-services**.

## 5. Cargo, dependências e linker

```text
$ cargo build   (cargo 1.95 com rust-version = "1.99")
error: rustc 1.95.0 is not supported by the following package:
  msrv@0.1.0 requires rustc 1.99
→ atualize o toolchain (rustup update / rust-toolchain.toml) OU reduza `rust-version` se for realmente compatível

error: failed to select a version for the requirement `serde = "^99"`
candidate versions found which didn't match: 1.0.229, 1.0.228, 1.0.227, ...
location searched: crates.io index
→ versão/feature que não existe: confira o requisito (`serde = "1"`), o nome do crate e as features

$ cargo build --locked   (sem Cargo.lock)
error: cannot create the lock file …/Cargo.lock because --locked was passed to prevent this
→ gere/atualize o lock localmente (`cargo generate-lockfile`/`cargo update -p x`), REVISE o diff e comite; não tire `--locked` do CI

error: linker `naoexiste-cc` not found
  = note: No such file or directory (os error 2)
→ linker ausente ou `-C linker`/`linker =` em `.cargo/config.toml` errado: instale `build-essential`/`gcc`, ou corrija a configuração

error: linking with `cc` failed: exit status: 1
  = note: rust-lld: error: unable to find library -lnaoexiste
→ biblioteca nativa ausente: instale o pacote `-dev` na imagem de build, corrija o nome em `#[link(name = "…")]`/`build.rs`, ou use alternativa em Rust puro

error: failed to run custom build command for `openssl-sys v0.9.117`
  OpenSSL include directory does not exist: /nao/existe/include     (com OPENSSL_DIR apontando para lugar inexistente)
→ sem OpenSSL de desenvolvimento: instale `libssl-dev`+`pkg-config`, corrija `OPENSSL_DIR`, ou troque a dependência por `rustls` (preferência do Squad AI)
```

Checklist de investigação de build:

1. `rustc -Vv && cargo -V` e `cat rust-toolchain.toml` — o toolchain é o esperado? (`rustup show`)
2. `cargo build -vv` — mostra o comando exato do rustc e a saída do `build.rs` (`cargo:warning=…`).
3. `cargo tree -d` (versões duplicadas), `cargo tree -i <crate>` (quem puxa), `cargo tree -e features` (quem ligou a *feature*).
4. `cat .cargo/config.toml ~/.cargo/config.toml` e `env | grep -E 'RUST|CARGO'` — `RUSTFLAGS`/`linker` herdados explicam "só falha na minha máquina".
5. `cargo clean -p <crate>` antes de `cargo clean`; troque de toolchain ⇒ recompile.
6. Cross/musl: `rustup target add x86_64-unknown-linux-musl`, linker/`CC` do alvo, nada de `openssl` nativo (use `rustls`).

## 6. Panics — leia a mensagem, depois a pilha

```text
thread 'main' (31517) panicked at p_overflow.rs:1:25:
attempt to add with overflow                                ← só em debug / com overflow-checks; em release vira wrapping

thread 'main' panicked at p_index.rs:1:90:
index out of bounds: the len is 3 but the index is 5        ← use `get(i)`

thread 'main' panicked at p_slice.rs:1:83:
end byte index 3 is not a char boundary; it is inside 'á' (bytes 2..4 of string)     ← fatiar &str no meio de um caractere UTF-8

called `Option::unwrap()` on a `None` value
called `Result::unwrap()` on an `Err` value: "falhou"
config PORT inválida: ParseIntError { kind: InvalidDigit }   ← `expect("contexto")` ajuda; `?` + erro tipado é melhor

attempt to divide by zero
RefCell already borrowed                                     ← dois `borrow_mut()` vivos (BorrowMutError)
called `Result::unwrap()` on an `Err` value: PoisonError { .. }   ← OUTRA thread entrou em pânico segurando o Mutex; ache o PRIMEIRO pânico

thread 'main' has overflowed its stack
fatal runtime error: stack overflow, aborting               ← recursão profunda; SIGABRT

panic in a function that cannot unwind
thread caused non-unwinding panic. aborting.                ← pânico em `extern "C"`: aborta (exit 134)
```

Método: (1) a **mensagem** diz o quê; (2) `RUST_BACKTRACE=1` e o **1º frame do seu código** diz onde; (3) pergunte **por que o valor era inválido** (entrada? invariante quebrada? ordem?) — corrigir o `unwrap` sem responder isso só move o pânico; (4) a correção costuma ser **tratar o caso no tipo** (`Option`/`Result`, newtype validado, `get`, `checked_*`) e cobrir com teste.
Pânico em produção deve virar log estruturado com a causa e a requisição, e o processo deve ser reiniciado pelo orquestrador (liveness) — `panic = "abort"` muda esse comportamento (→ **rust-performance-engineer**).

## 7. Testes

```text
---- t stdout ----
thread 't' panicked at ec_assert.rs:2:10:
assertion `left == right` failed: soma de um mais um
  left: 2
 right: 3
```

`left` é o valor obtido, `right` o esperado (na ordem escrita em `assert_eq!(obtido, esperado, "contexto")`); **sempre** passe contexto em testes de tabela. Saídas reais de `proptest` (`minimal failing input: total = 0, n = 1`, arquivo `proptest-regressions/`) e de `insta` (diff `-old snapshot`/`+new results`) → `rust-pro/references/testes.md`.
Teste que trava: veja a SKILL (§4) — `timeout`, `nextest`, `start_paused`, e `select!` com `else =>`.

## 8. Clippy

`cargo clippy --all-targets -- -D warnings` é parte do gate. Regras para investigar: leia o **nome do lint** (`clippy::redundant_clone`, `clippy::unwrap_used`…) e o `help:` — o lint costuma explicar o idioma correto; `#[expect(clippy::lint, reason = "…")]` (1.81) em vez de `#[allow]` quando a exceção é consciente (avisa quando deixa de ser necessária).
Lints de segurança de `unsafe` e as mensagens reais (`unsafe block missing a safety comment`, `this public function might dereference a raw pointer but is not marked unsafe`) → **rust-unsafe-security**.

## 9. Cartão de bolso: erro → primeira ação

| Você viu | Primeira ação |
|---|---|
| `E0382`/`E0505`/`E0507` | quem é o dono? emprestar em vez de mover; `clone` só se for a intenção |
| `E0499`/`E0502` | encurte o 1º empréstimo (use e solte antes); separe campos; colete índices |
| `E0597`/`E0515`/`E0716` | devolva owned / eleve o dono de escopo |
| `E0373`/`E0521` | `move` + dado owned/`Arc`; `thread::scope` |
| `E0277 … cannot be sent between threads` | `Rc`→`Arc`; guard atravessando `.await` → bloco curto |
| `E0282` | anote o tipo / turbofish |
| `E0599` | trait no escopo? bound? variante? |
| `extern blocks must be unsafe` etc. | migração para a edição 2024 (tabela §3) |
| `rustc X is not supported by … requires rustc Y` | toolchain/MSRV |
| `unable to find library -lX` / `linker … not found` | pacote `-dev`/toolchain C ausente na imagem |
| `there is no reactor running` | faltou runtime tokio |
| `Cannot start a runtime from within a runtime` | `block_on` dentro de async |
| `PoisonError` | procure o primeiro pânico, não o `unwrap` do lock |
| `SIGABRT`/exit 134 | pânico em `extern "C"` ou stack overflow |
