# Rust 1.99 e a edição 2024 — fatos de versão para decidir o que usar

> Autoral (Squad AI), reescrito em português. Fontes: notas de release oficiais do Rust (1.85–1.99), Edition Guide e o código-fonte da `std` do toolchain 1.99.0
> (atributos `#[stable(since = …)]` conferidos). Mensagens do compilador abaixo foram capturadas com `rustc 1.99.0 (b940084d7 2026-09-28)` e `cargo 1.99.0`.
> Quando o projeto usa outro MSRV, **o `Cargo.toml` manda** — esta página só diz o que cada versão permite.

## 1. Estado do ecossistema (out/2026)

- **Stable atual: 1.99.0 (01/10/2026).** Ciclo de 6 semanas; releases recentes: 1.95 (16/04), 1.96, 1.97 (09/07), 1.98 (20/08), 1.99 (01/10).
  Não existe LTS: só a stable mais nova recebe correções. Aplicações devem acompanhar; bibliotecas fixam um MSRV e o testam no CI.
- **Edição vigente: 2024** (estável desde 1.85, fev/2025). Edição é propriedade do *crate*, não do projeto: crates de edições diferentes se combinam.
- `resolver = "3"` (padrão na edição 2024): resolução de dependências **ciente de `rust-version`** — não escolhe versão de crate que exige rustc mais novo que o seu MSRV.
- Ferramentas oficiais embutidas: `rustfmt`, `clippy`, `rustdoc`, `cargo` (com `cargo doc`, `cargo tree`, `cargo fix`, `cargo clean --workspace`).
  Linker padrão em `x86_64-unknown-linux-gnu`: **lld** (desde 1.90) — links mais rápidos sem configurar nada.

## 2. Recursos por versão (o que o `rust-version` permite)

Cada linha foi **compilada** ou conferida no código da `std` do 1.99.0.

| Versão | Recurso | Para que serve / cuidado |
|---|---|---|
| 1.75 | `async fn` e `-> impl Trait` em traits | em trait **pública** declare `-> impl Future<Output = T> + Send` (senão o lint `async_fn_in_trait` avisa que o chamador não pode exigir `Send`) |
| 1.80 | `LazyLock`, `LazyCell` | estático preguiçoso e thread-safe sem `lazy_static`/`once_cell` |
| 1.81 | `#[expect(lint, reason = "…")]` | como `#[allow]`, mas **avisa** se o lint deixar de disparar |
| 1.82 | `Option::is_none_or`, sintaxe `use<..>` | captura precisa de lifetimes em `impl Trait` de retorno |
| 1.85 | **edição 2024**, async closures (`AsyncFn`, `AsyncFnMut`, `AsyncFnOnce`) | `async \|x\| …` empresta do ambiente; bound `F: AsyncFn(i32) -> i32` |
| 1.86 | trait upcasting; `get_disjoint_mut`; `Vec::pop_if` | `&dyn Sub` → `&dyn Super`; dois `&mut` em índices distintos sem `unsafe` |
| 1.87–1.88 | `Vec::extract_if`, `HashMap::extract_if`, `Cell::update` | remoção condicional in-place |
| 1.88 | **let chains** | `if let Some(x) = a && x > 0 && let Ok(y) = f(x)`; **só edição 2024** |
| 1.89 | argumentos const inferidos (`_`), lint `mismatched_lifetime_syntaxes`, `File::lock*` | lock de arquivo na std; `dangerous_implicit_autorefs` vira *deny* |
| 1.90 | **lld padrão** no Linux x86_64; publicação multi-pacote (`cargo publish --workspace`) | |
| 1.91 | aritmética **estrita** (`strict_add`, `strict_mul`…), `Duration::from_mins/from_hours`, `PathBuf::add_extension`, `BTreeMap::extract_if`, `build.build-dir` | `strict_*` entra em pânico em overflow **mesmo em release** (sem depender de `overflow-checks`) |
| 1.92 | `RwLockWriteGuard::downgrade`, `Box/Rc/Arc::new_zeroed` | |
| 1.93 | `VecDeque::pop_front_if/pop_back_if`, `std::fmt::from_fn`, `<[T]>::as_array` | |
| 1.94 | `LazyLock::get/get_mut`, `<[T]>::array_windows`, `Peekable::next_if_map`, TOML 1.1 no Cargo | |
| 1.95 | **`if let` guards** em `match`; `cfg_select!`; `Vec::push_mut/insert_mut`; atômicos `update` | `cfg_select!` substitui a crate `cfg-if` |
| 1.96 | `assert_matches!`/`debug_assert_matches!` (`std::assert_matches`) | |
| 1.97 | lint `dead_code_pub_in_binary` (itens `pub` nunca usados em *binário*; `allow` por padrão — habilite com `-W dead-code-pub-in-binary`), `build.warnings` e `resolver.lockfile-path` no config do Cargo, `self` final em `use` | |
| 1.98 | `bool::ok_or(_else)`, `str::substr_range`, `strip_circumfix`, métodos `algebraic_*` em floats | |
| 1.99 | `Vec::into_parts/from_parts`, `IntoIterator` para `Box<[T; N]>`, `VecDeque::retain_back`, `String::from_utf8_lossy_owned`, definição de funções C-variádicas, **perfil `debug`** embutido | veja §4 |

### Exemplos compilados (edição 2024, rustc 1.99.0)

```rust
// let chains (1.88, edição 2024)
pub fn first_even_gt(v: &[i32], min: i32) -> Option<i32> {
    if let Some(&x) = v.first()
        && x % 2 == 0
        && x > min
    {
        Some(x)
    } else {
        None
    }
}

// `if let` guard (1.95)
pub fn classify(r: Option<&str>) -> &'static str {
    match r {
        Some(s)
            if let Ok(n) = s.parse::<i32>()
                && n > 0 =>
        {
            "positivo"
        }
        Some(s) if s.parse::<i32>().is_ok() => "inteiro",
        Some(_) => "texto",
        None => "nada",
    }
}

// async closure (1.85) com bound AsyncFn
pub async fn apply<F>(f: F) -> i32
where
    F: AsyncFn(i32) -> i32,
{
    f(1).await + f(2).await
}

// seleção em tempo de compilação sem a crate cfg-if (1.95)
pub fn plataforma() -> &'static str {
    cfg_select! {
        target_os = "linux" => "linux",
        target_os = "windows" => "windows",
        _ => "outra",
    }
}

// dois &mut em índices distintos, sem unsafe (1.86)
pub fn troca_primeiro_e_ultimo(v: &mut [i32]) {
    if let Some(n) = v.len().checked_sub(1)
        && let Ok([a, b]) = v.get_disjoint_mut([0, n])
    {
        std::mem::swap(a, b); // slice vazio: não faz nada; com 1 elemento, índices iguais → Err
    }
}
```

## 3. Edição 2024 — o que muda e como migrar

Migração: `cargo fix --edition` (aplica o que é automático) → troque `edition = "2024"` no `Cargo.toml` → `cargo build && cargo test` → revise o diff. Faça em **commit isolado**.
Dica: antes de trocar, ligue o grupo `rust_2024_compatibility` (`#![warn(rust_2024_compatibility)]`) para ver os avisos na edição antiga.

| Mudança | Efeito prático | Mensagem real (rustc 1.99.0) |
|---|---|---|
| `extern` blocks são `unsafe extern` | declare `unsafe extern "C" { … }`; itens podem ser marcados `safe fn` quando provadamente seguros | `error: extern blocks must be unsafe` |
| Atributos `no_mangle`, `export_name`, `link_section` são `unsafe` | `#[unsafe(no_mangle)]` | `error: unsafe attribute used without unsafe` |
| `static mut`: referências viram **erro** (`static_mut_refs` = deny) | use `&raw const`/`&raw mut`, `AtomicXxx`, `Mutex` ou `LazyLock<Mutex<_>>` | `error: creating a shared reference to mutable static` … `help: use &raw const instead` |
| `std::env::set_var` / `remove_var` são `unsafe` | mutar o ambiente com outras threads lendo é UB: faça no início de `main` (ainda single-thread) dentro de `unsafe {}` com `// SAFETY:`, ou — melhor — passe a config por parâmetro e não mute o ambiente (em testes, isso quebra a execução paralela) | `error[E0133]: call to unsafe function set_var is unsafe and requires unsafe block` |
| `unsafe_op_in_unsafe_fn` = warn | `unsafe fn` não autoriza mais operações unsafe no corpo — use bloco `unsafe {}` explícito | |
| `gen` é palavra reservada | renomeie ou escreva `r#gen` | `error: expected identifier, found reserved keyword gen` |
| Escopo de temporários em expressões-cauda | o temporário de `c.borrow().len()` na última expressão morre **antes** das variáveis locais | com 2021: `error[E0597]: c does not live long enough`; com 2024 compila |
| `if let` reescopado | o temporário do scrutinee é descartado antes do `else` | evita deadlock de `Mutex` em `if let … else` |
| `impl Trait` em retorno captura **todos** os lifetimes em escopo | use `+ use<'a>` (ou `use<>`) para capturar só o necessário | |
| `.into_iter()` em `Box<[T]>` passa a chamar o `IntoIterator` por valor (o `impl` existe desde a 1.80 em todas as edições; `for x in boxed` já rende `T` na 2021) | só a chamada como **método** muda — lint `boxed_slice_into_iter` | |
| Fallback do tipo never (`!`) mudou | pode alterar inferência em código antigo de `panic!`/`todo!` em closures | |
| Cargo: `resolver = "3"` (ciente de `rust-version`) é o padrão da edição | ver §4 | |
| Macros: fragmento `expr` inclui `const {}`/`_`; `expr_2021` preserva o antigo | só importa para autores de `macro_rules!` | |

## 4. Cargo e ferramentas — o que importa em 1.9x

- **`rust-version`** no `[package]` (ou `[workspace.package]` + `rust-version.workspace = true`): documenta o MSRV, alimenta o resolver 3 e faz o cargo recusar compilar com rustc mais velho.
- **Perfil `debug` (1.99):** passou a existir como perfil nomeável; no cargo 1.95 `cargo build --profile debug` falhava com `error: profile name debug is reserved … use the name dev`.
  No 1.99, `[profile.debug]` é aceito e `--profile debug` imprime `Finished debug profile`. Continue usando `[profile.dev]` para configurar o padrão, salvo necessidade clara — **teste no seu CI** antes de depender disso.
- **`build.build-dir` (1.91):** separa artefatos intermediários do diretório final de saída (útil em CI com cache e em monorepo).
- **`build.warnings` (1.97):** política de avisos por config (`deny` em CI sem poluir `RUSTFLAGS`).
- **Workspace (1.99+ e edição 2024):** membros podem sobrescrever `default-features` herdado de `[workspace.dependencies]` (na edição 2021 só avisa; entre 1.85 e 1.98 com a 2024 ainda é erro).
- **Incremental em CI:** no 1.99, com `CI=true` no ambiente, o cargo **não** passa `-C incremental` ao rustc (verificado com `cargo build -v`; no 1.95 passava). Menos cache inútil nos runners; se medir ganho com cache persistente, reative com `CARGO_INCREMENTAL=1`.
- **TOML 1.1** aceito em `Cargo.toml` desde o cargo 1.94: usar os recursos novos **sobe o MSRV de desenvolvimento**, mas o manifesto publicado continua compatível com parsers antigos (changelog do Cargo 1.94) — consumidores não são afetados.
- **Segurança do próprio cargo:** o 1.96 corrigiu CVE-2026-5222 e CVE-2026-5223 — mantenha o toolchain atualizado em runners de CI.

## 5. Escolhas padrão (quando o usuário não define)

| Decisão | Padrão do Squad AI |
|---|---|
| Edição / MSRV de aplicação | `edition = "2024"`, `rust-version` = stable de 2 releases atrás no máximo; `rust-toolchain.toml` com canal fixo |
| Edição / MSRV de biblioteca | `edition = "2024"` + `rust-version` explícito e job de CI com esse rustc; subir MSRV = mudança *minor* documentada |
| Erros | biblioteca: `thiserror` 2; aplicação: `anyhow` 1 (+ `tracing`) |
| Async | `tokio` (runtime), `axum` 0.8 + `tower-http` 0.7 (HTTP), `reqwest` 0.13 (cliente) → **rust-async-services** |
| Serialização | `serde` + `serde_json`; `#[serde(deny_unknown_fields)]` em entrada externa |
| Testes | `cargo test` + `proptest` + `insta` (snapshots); runner `cargo nextest` no CI → `references/testes.md` |
| Bench | `divan` (rápido de escrever) ou `criterion` 0.8 (estatística/regressão) → **rust-performance-engineer** |

> Versões de crates acima vieram da resolução real do `cargo` em out/2026 (ex.: axum 0.8.9, tower-http 0.7.1, tokio 1.53, reqwest 0.13.5, proptest 1.11, divan 0.1.21, criterion 0.8.2).
> Crates mudam rápido: ao gerar um `Cargo.toml`, rode `cargo add <crate>` para fixar a versão atual em vez de copiar números desta página.
