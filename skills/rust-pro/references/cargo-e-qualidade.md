# Cargo, lints e qualidade contínua em Rust

> Autoral (Squad AI). O workspace desta página foi criado e validado com `cargo 1.99.0`: `cargo fmt --check`, `cargo clippy --workspace --all-targets -- -D warnings`,
> `cargo test --workspace` (inclui doctest), `cargo doc --workspace --no-deps`. Ferramentas de terceiros (cargo-deny, nextest…) estão marcadas com o status de verificação.

## 1. Workspace de referência

```toml
# Cargo.toml (raiz) — workspace virtual
[workspace]
members = ["crates/*"]
# em workspace VIRTUAL o resolver não é inferido da edição: declare (ver aviso abaixo)
resolver = "3"

[workspace.package]
edition = "2024"
rust-version = "1.99"          # MSRV: documenta, alimenta o resolver 3 e faz o cargo recusar rustc mais velho
license = "MIT OR Apache-2.0"
publish = false                # troque ao publicar numa biblioteca

[workspace.dependencies]       # versões em UM lugar; membros usam `dep.workspace = true`
anyhow = "1"
thiserror = "2"
nucleo = { path = "crates/nucleo" }

[workspace.lints.rust]
unsafe_code = "forbid"
missing_debug_implementations = "warn"
unused_must_use = "deny"

[workspace.lints.clippy]
all = { level = "warn", priority = -1 }        # grupos com prioridade menor: lints individuais abaixo vencem
pedantic = { level = "warn", priority = -1 }
unwrap_used = "warn"
expect_used = "warn"
dbg_macro = "warn"
todo = "warn"
print_stdout = "warn"                          # bibliotecas e serviços usam tracing, não println!
module_name_repetitions = "allow"              # lint do grupo restriction (não dispara com pedantic); allow inofensivo
missing_errors_doc = "allow"
must_use_candidate = "allow"                   # opcional: habilite em bibliotecas públicas

[profile.release]
lto = "thin"
codegen-units = 1
strip = "symbols"
```

```toml
# crates/nucleo/Cargo.toml — membro que herda tudo do workspace
[package]
name = "nucleo"
version = "0.1.0"
edition.workspace = true
rust-version.workspace = true
license.workspace = true
publish.workspace = true

[dependencies]
thiserror.workspace = true

[lints]
workspace = true
```

Sem `resolver` no workspace virtual o cargo 1.99 avisa (mensagem real):

```text
warning: virtual workspace defaulting to `resolver = "1"` despite one or more workspace members being on edition 2024 which implies `resolver = "3"`
```

Regras do workspace:

- **Um `Cargo.lock` na raiz, commitado** — aplicações *e* bibliotecas (reprodutibilidade de CI e auditoria). CI usa `--locked`: falha se o lock estiver desatualizado.
- `crates/` pequenas e coesas: `*-core` (domínio, sem I/O), `*-adapters`/`*-infra` (I/O), `app`/`cli` (binário fino). Dependência flui **para dentro**.
- Features **aditivas** (ligar uma feature nunca remove API); sem features mutuamente exclusivas; `default-features = false` em dependências para controlar a superfície e o tempo de build.
- `cargo tree -d` lista crates duplicadas em versões diferentes; `cargo tree -i <crate>` mostra quem puxa uma dependência (útil para auditoria e para reduzir o build).

## 2. Arquivos de configuração do repositório

```toml
# rust-toolchain.toml — mesmo compilador para todos e para o CI
[toolchain]
channel = "1.99.0"
components = ["rustfmt", "clippy"]
profile = "minimal"
```

```toml
# rustfmt.toml — estável; `style_edition` acompanha a edição
style_edition = "2024"
```

```toml
# clippy.toml
allow-unwrap-in-tests = true
allow-expect-in-tests = true
# msrv = "1.99"      # (opcional) o clippy lê rust-version do Cargo.toml automaticamente
```

Mantenha `rustfmt` com **o mínimo de opções** (opções instáveis exigem nightly e dividem o time). `.gitignore`: `/target`. `.cargo/config.toml` só para o que for do projeto (aliases, `build.build-dir`), nunca segredos.

## 3. Lints — contrato do projeto

| Lint | Nível | Por quê |
|---|---|---|
| `unsafe_code` | `forbid` (ou `deny` com exceções documentadas) | prova mecânica de que não há `unsafe` fora das exceções → **rust-unsafe-security** |
| `clippy::unwrap_used` / `expect_used` | `warn` (CI: erro) | erro como valor; teste fica liberado por `clippy.toml` |
| `clippy::dbg_macro`, `todo`, `unimplemented` | `warn` | não vaza depuração/esqueleto |
| `clippy::print_stdout` / `print_stderr` | `warn` em bib/serviço | logs estruturados com `tracing` |
| `clippy::pedantic` | `warn` com *allows* pontuais | pega erros reais (`cast_possible_truncation`, `needless_pass_by_value`, `must_use_candidate`); desligue só o que for ruído |
| `clippy::undocumented_unsafe_blocks`, `missing_safety_doc` | `deny` quando houver `unsafe` | `// SAFETY:` obrigatório |
| `missing_debug_implementations` | `warn` | todo tipo público é depurável |
| `unused_must_use` | `deny` | `Result` ignorado é bug |
| `rust_2024_compatibility` | `warn` (só durante a migração) | mostra o que quebra ao trocar a edição |

- Prefira **`#[expect(lint, reason = "…")]`** a `#[allow]`: se o lint deixar de disparar, o compilador avisa e você remove a supressão (1.81).
- Ordem de prioridade: grupos com `priority = -1` e lints individuais sem prioridade — assim `pedantic = "warn"` não sobrescreve `module_name_repetitions = "allow"`.
- Aprendizado verificado: com `-D warnings` e `pedantic`, o clippy 0.1.99 acusa erros reais em código "normal" — `must_use_candidate`, `missing_errors_doc`, `cast_*`, `doc_markdown` (`missing_const_for_fn` é do grupo `nursery`: não dispara com `pedantic`). Corrija ou suprima com `reason`; não desligue o grupo inteiro.

## 4. Perfis de compilação (resumo; detalhes e medições em rust-performance-engineer)

| Objetivo | Config |
|---|---|
| build de dev rápido | padrão `dev`; `[profile.dev] debug = "line-tables-only"` reduz tempo/tamanho se não precisa de depurador completo |
| dependências otimizadas em dev (testes menos lentos) | `[profile.dev.package."*"] opt-level = 2` |
| release de serviço | `lto = "thin"`, `codegen-units = 1`, `strip = "symbols"` (+ `panic = "abort"` só com supervisor e sem `catch_unwind`) |
| release com símbolos para profiling | `[profile.release] debug = "line-tables-only"` e **sem** `strip` |
| menor binário (CLI/Lambda) | `opt-level = "s"` ou `"z"`, `lto = "fat"`, `panic = "abort"`, `strip = true` |

`panic = "abort"` mata o processo no panic (sem *unwinding*): ótimo para contêiner com restart; **incompatível** com `catch_unwind` e com testes de panic (`#[should_panic]` usa o perfil de teste, que sempre faz unwind).

## 5. Pipeline de CI (GitHub Actions) — ordem do mais barato ao mais caro

```yaml
name: ci
on: {push: {branches: [main]}, pull_request: {}}
permissions: {contents: read}
env:
  CARGO_TERM_COLOR: always
  CARGO_INCREMENTAL: "0"          # explícito (no cargo 1.99 já é desligado quando CI=true)
jobs:
  verificar:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<SHA-DA-VERSAO-AUDITADA>   # fixe por SHA; nunca por tag móvel
      - name: Toolchain (lê rust-toolchain.toml; idempotente no rustup 1.29)
        run: rustup toolchain install
      - run: cargo fmt --all --check
      - run: cargo clippy --workspace --all-targets --locked -- -D warnings
      - run: cargo test --workspace --locked
      - run: cargo test --workspace --doc --locked
      - name: Docs sem avisos
        run: cargo doc --workspace --no-deps --locked
        env: {RUSTDOCFLAGS: "-D warnings"}
  msrv:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<SHA-DA-VERSAO-AUDITADA>
      - run: rustup toolchain install 1.99.0 --profile minimal   # = rust-version do Cargo.toml
      - run: cargo +1.99.0 check --workspace --all-targets --locked
  supply-chain:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<SHA-DA-VERSAO-AUDITADA>
      - run: cargo install cargo-deny --locked      # ou binário verificado por checksum
      - run: cargo deny check
```

Notas:

- **Cache**: `~/.cargo/registry`, `~/.cargo/git` e `target/` com chave `hash(Cargo.lock)+rustc`; a action `Swatinem/rust-cache` é popular, mas é código de **terceiros com acesso ao seu runner** — audite e fixe por SHA, ou use o cache nativo do CI.
- **`-D warnings`**: use em `clippy`/`cargo doc`; evite `RUSTFLAGS=-D warnings` global (invalida o cache e faz a atualização do rustc quebrar CI por lint novo). Alternativa (1.97+, verificada no 1.99): `cargo --config 'build.warnings="deny"' check` falha com a mensagem "warnings are denied by `build.warnings` configuration".
- Atualização de toolchain: PR automático (Renovate/Dependabot) que bumpa `rust-toolchain.toml`; novos lints do clippy aparecem como falha **no PR de bump**, não aleatoriamente.
- Matriz opcional: `os: [ubuntu, macos, windows]` se houver código específico de plataforma (`cfg_select!`); `--no-default-features` e `--all-features` em bibliotecas (ferramenta `cargo hack --each-feature` — *terceiros, não verificada aqui*).
- Segredos de publicação (`CARGO_REGISTRY_TOKEN`) só em job de release protegido por *environment* com aprovação; nunca em PR de fork.

## 6. Supply chain: `cargo-deny` + `cargo-audit` (+ `cargo-vet`)

Detalhe e racional → **rust-unsafe-security**. Esqueleto de `deny.toml` — **validado com cargo-deny 0.20.2** sobre o workspace desta página (`bans ok, licenses ok, sources ok`, `advisories ok`); revalide na sua versão:

```toml
[graph]
all-features = true

[advisories]
yanked = "deny"
# ignore = [{ id = "RUSTSEC-AAAA-NNNN", reason = "não alcançável: usamos só X; revisar até 2026-12-31" }]

[licenses]
allow = ["MIT", "Apache-2.0", "Apache-2.0 WITH LLVM-exception", "BSD-3-Clause", "ISC", "Unicode-3.0"]
confidence-threshold = 0.8

[bans]
multiple-versions = "warn"
wildcards = "deny"            # nada de "*" em dependências…
allow-wildcard-paths = true   # …exceto `path = "..."` do próprio workspace (sem isto o cargo-deny acusa `wildcard dependency`)
# deny = [{ crate = "openssl", reason = "padronizado em rustls" }]

[sources]
unknown-registry = "deny"
unknown-git = "deny"
allow-registry = ["https://github.com/rust-lang/crates.io-index"]
```

- `cargo deny check advisories` consulta o banco **RustSec** (precisa de rede para o repositório do banco); `licenses`/`bans`/`sources` funcionam offline.
- Toda exceção (`ignore`, licença extra) leva **motivo e prazo**; vira item de revisão no GATE.

## 7. Publicar uma biblioteca (checklist)

- [ ] `cargo package --list` (confira o que vai no tarball: sem `.env`, chaves, fixtures grandes) e `cargo publish --dry-run`.
- [ ] `description`, `license`, `repository`, `readme`, `keywords`, `categories`, `rust-version` preenchidos; `include`/`exclude` explícitos.
- [ ] `cargo semver-checks` (terceiros; compara a API pública com a versão anterior) — mudança quebrante ⇒ bump *major* (ou *minor* em `0.x`).
- [ ] Docs com exemplos executáveis; `#![warn(missing_docs)]`; `CHANGELOG`; MSRV declarado e testado no CI.
- [ ] 2FA na conta do registro; *trusted publishing* quando suportado; token com escopo mínimo.
- [ ] Publicação é **irreversível** (`yank` só esconde): GATE humano antes do `cargo publish` real.

## 8. Dia a dia — comandos úteis

| Quero… | Comando |
|---|---|
| checar sem gerar binário (rápido) | `cargo check --workspace --all-targets` |
| corrigir lints automaticamente | `cargo clippy --fix --allow-dirty` (revise o diff) |
| migrar de edição | `cargo fix --edition` |
| ver o que uma dependência puxa / por quê | `cargo tree -i <crate>`; `cargo tree -d` (duplicadas) |
| atualizar uma dependência com segurança | `cargo update -p <crate>`; revise `Cargo.lock` no diff |
| atualizar tudo dentro das restrições | `cargo update` e rode a suíte; `cargo update --dry-run` mostra antes |
| docs locais | `cargo doc --open --no-deps` |
| macros expandidas | `cargo expand` (terceiros; precisa nightly) |
| deps não usadas | `cargo machete` (terceiros; heurística — confira) |
| rodar um teste só | `cargo test <nome> -- --nocapture`; crate: `-p <pacote>` |
