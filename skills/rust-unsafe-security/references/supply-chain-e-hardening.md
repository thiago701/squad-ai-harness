# Supply chain, entrada hostil, segredos e hardening em Rust

> Autoral (Squad AI). Testado em rustc 1.99.0, cargo-deny 0.20.2, cargo-fuzz 0.13.2 (libfuzzer-sys 0.4.13), secrecy 0.10.3, subtle 2.6.1, zeroize 1.9.0, serde_json 1.x.
> As saídas são **reais** (resumidas onde indicado). Ferramentas não executadas (cargo-audit, cargo-vet, cargo-geiger, cargo-auditable, SBOM) estão marcadas **não verificado**.
> Fontes conceituais: RustSec Advisory Database, documentação do cargo-deny/cargo-fuzz, *Rust Fuzz Book*, *Rustonomicon* (reescritas, sem cópia).

## 1. Modelo de ameaça da cadeia de suprimentos

| Vetor | Como ataca | Controle principal |
|---|---|---|
| **Dependência com vulnerabilidade conhecida** | advisory RustSec publicado para a versão que você usa | `cargo deny check advisories` no PR **e** em agenda (o banco muda sem o seu código mudar) |
| **Dependência maliciosa / *typosquatting*** | nome parecido (`serde_jsoon`), conta comprometida, versão nova com *payload* | revisão ao adicionar/atualizar; `Cargo.lock` versionado; fontes restritas |
| **Código executado no build** | `build.rs` e **proc-macros** rodam com as permissões de quem compila (dev e CI, com acesso a rede/segredos) | revisar; CI de build sem segredos no ambiente; `cargo tree -e build` |
| **Versão *yanked*/abandonada** | crate retirada por defeito grave ou sem manutenção | `yanked = "deny"`; lista de crates críticas com dono |
| **Licença incompatível** | copyleft inesperado em dependência transitiva | `[licenses]` com *allow-list* |
| **Fonte não oficial** | `git = "…"` sem *rev*, registry alternativo | `[sources] unknown-registry/unknown-git = "deny"` |

Princípio: **toda dependência é código seu**, com a diferença de que você não o escreveu. P1-Simplicidade: menos dependências, menos superfície.

## 2. `cargo-deny` — o portão mecânico

Esqueleto completo de `deny.toml` (bans/licenses/sources/advisories, validado): `rust-pro/references/cargo-e-qualidade.md` §6. Foco aqui: **advisories** e política de exceção.

Exemplo real (crate `time 0.1.45`, afetada pelo RUSTSEC-2020-0071 — "potential segfault in the time crate"). Sem exceção:

```text
$ cargo deny --config deny.toml check advisories
error[vulnerability]: Potential segfault in the time crate
  ┌─ Cargo.lock:3:1
  │
3 │ time 0.1.45 registry+https://github.com/rust-lang/crates.io-index
  │ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ security vulnerability detected
  │
  ├ ID: RUSTSEC-2020-0071
  ├ Advisory: https://rustsec.org/advisories/RUSTSEC-2020-0071
  ├ ### Impact
    The affected functions set environment variables without synchronization. On Unix-like operating systems, this can crash in multithreaded programs.
    … (patches, workarounds: "Users of time 0.1 do not have a patch and should upgrade to time 0.2.23 or greater or the 0.3 series.")
```

O código de saída é diferente de zero → o CI falha. Decisão possível, **documentada**, quando o upgrade não é imediato:

```toml
[advisories]
yanked = "deny"
ignore = [
  { id = "RUSTSEC-2020-0071", reason = "não alcançável: só usamos time::Duration (sem time::now/at); migrar para time 0.3 até 2026-12-31" },
]
```

```text
$ cargo deny --config deny.toml check advisories
advisories ok
```

Regras da exceção (inegociáveis): (1) **id + motivo técnico + prazo** no arquivo; (2) quem aprovou fica no *commit*/PR; (3) o prazo vira tarefa com dono — exceção sem prazo é vulnerabilidade aceita em silêncio; (4) `ignore` nunca por "está atrapalhando o CI".
Detalhe de sintaxe (0.20.2): opções globais vêm **antes** de `check` (`cargo deny --config x.toml check advisories`; `cargo deny check --config …` dá `unexpected argument`).

Outras ferramentas (de terceiros — **não verificadas aqui**, avalie antes de adotar):

| Ferramenta | Para quê |
|---|---|
| `cargo audit` | consulta o RustSec sobre o `Cargo.lock` (sobreposta ao `deny advisories`; útil para relatório/`audit.toml`) |
| `cargo vet` | registra **quem auditou** cada versão de dependência (modelo de confiança por organização); pesado — só vale em projetos críticos |
| `cargo geiger` | conta `unsafe` por crate na árvore de dependências (sinal, não veredito) |
| `cargo auditable` / SBOM (CycloneDX/SPDX) | embute a lista de dependências no binário / gera inventário para resposta a incidente |

## 3. Higiene de `Cargo.lock`, CI e `build.rs`

- **Binários/serviços:** `Cargo.lock` **versionado**; CI e imagem usam `cargo build --locked` (falha se o lock precisaria mudar); `cargo install <ferramenta> --locked` sempre. Bibliotecas: lock opcional, mas rode o CI contra o mais recente também (`cargo update` em job separado).
- **Atualizar:** `cargo update -p <crate>` cirúrgico, um PR por vez; leia o *changelog* e o diff de `build.rs`/`Cargo.toml`; bot (Dependabot/Renovate) **abre** PR, humano revisa.
- **Quem executa código no build:** liste com `cargo tree -e build` (dependências de `build.rs`; proc-macros aparecem marcadas `(proc-macro)` na árvore normal). Nova dependência com `build.rs` ou proc-macro = revisão extra (o que executa? baixa algo? lê o ambiente?).
- **CI sem segredos na etapa de build:** segredos (tokens de deploy/registry) só em jobs de publicação isolados; `cargo publish` com token de escopo mínimo; revisão obrigatória em PR que altera `Cargo.toml`, `build.rs`, `.cargo/config.toml` ou o workflow.
- **Reduza a árvore:** `cargo tree -d` (versões duplicadas), `cargo tree -i <crate>` (por que ela está aqui?), `default-features = false` e só os *features* necessários.
- **Fontes:** `[sources] unknown-registry = "deny"`, `unknown-git = "deny"`; dependência `git` só com `rev = "<sha>"` e *allow-list* explícita. `*` como versão é proibido (`wildcards = "deny"`).
- **Publicação (se você publica crates):** 2FA, token com escopo/expiração, `cargo publish --dry-run`, `cargo package --list` para não vazar arquivo sensível, `yank` em caso de vazamento **e** rotação do segredo (yank não apaga o conteúdo já baixado).

## 4. Entrada não confiável — padrões verificados

Crate de teste com `unsafe_code = "forbid"` e lints `clippy::{arithmetic_side_effects, indexing_slicing, cast_possible_truncation, unwrap_used, expect_used} = "warn"` (com `allow-unwrap-in-tests`/`allow-expect-in-tests` no `clippy.toml`).

### 4.1 `Path::join` com caminho absoluto descarta a base

```rust
use std::path::{Component, Path, PathBuf};

/// ARMADILHA: `join` com caminho ABSOLUTO descarta a base.
pub fn join_ingenuo(base: &Path, entrada: &str) -> PathBuf { base.join(entrada) }

#[derive(Debug, PartialEq, Eq)]
pub enum CaminhoInvalido { Absoluto, SobeDiretorio }

/// Aceita só caminhos RELATIVOS sem `..` (validação léxica) e junta à base.
pub fn join_seguro(base: &Path, entrada: &str) -> Result<PathBuf, CaminhoInvalido> {
    let rel = Path::new(entrada);
    for c in rel.components() {
        match c {
            Component::Normal(_) | Component::CurDir => {}
            Component::ParentDir => return Err(CaminhoInvalido::SobeDiretorio),
            Component::RootDir | Component::Prefix(_) => return Err(CaminhoInvalido::Absoluto),
        }
    }
    Ok(base.join(rel))
}
```

Teste verificado:

```rust
let base = Path::new("/srv/dados");
assert_eq!(join_ingenuo(base, "/etc/passwd"), Path::new("/etc/passwd")); // a base sumiu!
assert_eq!(join_seguro(base, "/etc/passwd"), Err(CaminhoInvalido::Absoluto));
assert_eq!(join_seguro(base, "../segredo"), Err(CaminhoInvalido::SobeDiretorio));
assert_eq!(join_seguro(base, "a/b.txt").unwrap(), Path::new("/srv/dados/a/b.txt"));
```

Limites da validação **léxica**: não enxerga **links simbólicos** nem corrida (TOCTOU: o caminho muda entre checar e abrir). Defesa em profundidade: depois de abrir, compare `canonicalize()` com a base (`starts_with`), prefira abrir **relativo a um diretório já aberto** (APIs `openat`-style, p.ex. a crate `cap-std`, de terceiros — não verificada), e rode o serviço com usuário/sistema de arquivos de privilégio mínimo. Em Windows considere nomes reservados (`CON`, `NUL`) e `Prefix`. **Nunca** use o nome de arquivo enviado pelo cliente: gere o seu (UUID) e guarde o original como metadado.

### 4.2 JSON: limite de tamanho **e** de profundidade

```rust
pub fn parse_json_limitado(entrada: &[u8]) -> Result<serde_json::Value, String> {
    if entrada.len() > 1 << 20 {
        return Err("corpo grande demais".into());
    }
    serde_json::from_slice(entrada).map_err(|e| e.to_string())
}
```

```text
// 200 colchetes aninhados → recusado, sem estourar a pilha:
recursion limit exceeded at line 1 column 128
```

O `serde_json` aplica por padrão um limite de recursão de 128 níveis (o teste acima o confirma); **não** o desligue (`disable_recursion_limit` exige `unbounded_depth` e abre DoS por estouro de pilha).
O limite de **tamanho** é seu: aplique **antes** de ler o corpo inteiro (`RequestBodyLimitLayer` do tower-http (feature `limit`) em serviço axum → **rust-async-services**), pois `from_slice` já recebeu os bytes. Em tipos próprios use `#[serde(deny_unknown_fields)]`, newtypes validados e limites de coleção (`Vec` com `with_capacity` baseado em campo do atacante é DoS de memória — limite o campo).
Atenção a *zip/gzip bombs*: descompressão com limite de saída (`take(limite)` sobre o `Read`).

### 4.3 Aritmética, índices e conversões

- Dado externo: `checked_add/mul` (devolve `Option`), `saturating_*` quando saturar é a regra de negócio, `u32::try_from(x)?` em vez de `x as u32` (o `as` trunca em silêncio — `clippy::cast_possible_truncation`).
- Índice vindo de fora: `slice.get(i)`/`get(a..b)` em vez de `slice[i]` (pânico = DoS). Prova real no fuzzing (§6): `&dados[1..=n]` com `n` do primeiro byte entrou em pânico em **1 byte** de entrada.
- **Overflow em release:** por padrão o perfil `release` **não** verifica overflow (vira *wrapping*). Verificado com valor só conhecido em tempo de execução (`std::env::args().count() as u8 + 254`, depois `n + 2`): imprime `1` em `rustc -O` e entra em pânico (`attempt to add with overflow`) com `-C overflow-checks=on`. Com constante (`let n: u8 = 255; n + 2`) o rustc 1.99 **nem compila** (`error: this arithmetic operation will overflow`, lint `arithmetic_overflow` em deny). Para serviços que processam dinheiro/tamanhos/limites, ligue:

```toml
[profile.release]
overflow-checks = true   # custo costuma ser pequeno (meça); transforma wraparound silencioso em pânico detectável
```

(ou use `checked_*` nos pontos críticos e deixe o padrão — decisão de P2 que deve ser **medida** → **rust-performance-engineer**.)
- `unwrap`/`expect`/indexação em caminho de entrada externa = pânico remoto. Lints `unwrap_used`, `expect_used`, `indexing_slicing`, `arithmetic_side_effects` em `warn` (ou `deny` nos módulos de borda).
- Regex: a crate `regex` usa autômatos e não sofre *backtracking* catastrófico (garantia documentada); `fancy-regex` com retrovisores não tem essa garantia — limite o tamanho da entrada.
- SQL: sempre parametrizado (no sqlx 0.9, `query(String)` nem compila → **rust-async-services**). Comandos externos: `Command::new("prog").arg(x)` (sem shell); nunca `sh -c` com entrada interpolada.

## 5. Segredos em memória, logs e comparações

```rust
use secrecy::{ExposeSecret, SecretString};
use subtle::ConstantTimeEq;

/// Configuração com segredo: `Debug` NÃO imprime o valor.
#[derive(Debug)]
pub struct Config {
    pub usuario: String,
    pub token: SecretString,
}

impl Config {
    pub fn novo(usuario: &str, token: &str) -> Self {
        Self { usuario: usuario.to_owned(), token: SecretString::from(token) }
    }

    /// Comparação em tempo constante (evita *timing attack* em tokens/MACs).
    pub fn confere(&self, candidato: &str) -> bool {
        self.token.expose_secret().as_bytes().ct_eq(candidato.as_bytes()).into()
    }
}
```

Saída verificada do `println!("{c:?}")` num teste (e `clippy -D warnings` limpo):

```text
Config { usuario: "ana", token: SecretBox<str>([REDACTED]) }
```

Regras:

- **`SecretString`/`SecretBox<T>`** (secrecy 0.10): `Debug` redigido, apaga ao descartar (via `zeroize`), exige `.expose_secret()` explícito — cada uso aparece em *grep*/revisão. Desserialize direto para `SecretString` (`serde` feature) em vez de `String`.
- **`zeroize`:** `Zeroizing<Vec<u8>>` apaga ao sair de escopo (verificado: `buf.zeroize()` zera o conteúdo; `Zeroizing::new(vec![0xAB; 32])`). Limite honesto: **cópias anteriores** (um `Vec` que cresceu e realocou, um `String` clonado, valor movido por registradores/pilha) **não** são apagadas — crie o segredo já no tipo protegido, evite `clone`/`to_string`, e reserve capacidade antes (`Vec::with_capacity`).
- **`subtle::ConstantTimeEq`** para comparar token/MAC/hash (a comparação por `==` em `&[u8]` retorna ao primeiro byte diferente → vazamento por tempo). Nota: o `ct_eq` de slices com **tamanhos diferentes** retorna falso imediatamente (o comprimento não é segredo) — verificado no teste (`confere("curto")` → `false`).
- **Nunca** em log: `#[derive(Debug)]` em structs de config + `tracing::info!(?config)` é o vazamento clássico — use os tipos acima e `#[instrument(skip(senha, token))]`; revise erros (`Display`) para não ecoarem URL com credencial/`DATABASE_URL`.
- Senhas de usuário: hash lento com sal (Argon2id via crate mantida — p.ex. `argon2` do RustCrypto; **não verificado aqui**), em `spawn_blocking` se estiver num serviço async; nunca criptografia reversível. Escolha de algoritmo/parâmetros → **engenheiro-seguranca**.
- Aleatoriedade para chaves/tokens: gerador criptograficamente seguro semeado pelo sistema operacional (`getrandom`, ou o gerador criptográfico da crate `rand`); nunca PRNG de uso geral (`SmallRng`, `fastrand`), contador ou `SystemTime` como semente.
- Memória sensível em *core dumps*/swap: `mlock`, `RLIMIT_CORE=0`, `prctl(PR_SET_DUMPABLE, 0)` são medidas de SO **não verificadas aqui** — avalie conforme o modelo de ameaça (→ **engenheiro-seguranca**).

## 6. Fuzzing com `cargo-fuzz` (fluxo verificado de ponta a ponta)

Requisitos: nightly (`rustup toolchain install nightly`) com `rust-src` (`rustup component add rust-src --toolchain nightly` — o `--build-std` vem ligado por padrão), compilador C++11, `cargo install cargo-fuzz --locked` (0.13.2 aqui), Unix-like em x86-64 ou AArch64. Cada *fuzz target* é um binário libFuzzer com **ASAN ligado por padrão**; encontra pânicos, estouros, travamentos (timeout) e corrupção de memória em `unsafe`/FFI.

Alvo de exemplo — formato "1 byte de tamanho `n` + `n` bytes de payload":

```rust
// src/lib.rs
/// BUG PROPOSITAL (versão ruim): confia no byte de tamanho sem checar o que sobrou.
pub fn payload_ruim(dados: &[u8]) -> Option<&[u8]> {
    let n = usize::from(*dados.first()?);
    Some(&dados[1..=n]) // pânico se `dados.len() <= n`
}

/// Versão correta: `get` devolve `None` em vez de entrar em pânico.
pub fn payload(dados: &[u8]) -> Option<&[u8]> {
    let (&n, resto) = dados.split_first()?;
    resto.get(..usize::from(n))
}
```

```rust
// fuzz/fuzz_targets/fuzz_target_1.rs   (cargo +nightly fuzz init gera o esqueleto)
#![no_main]
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    // propriedade: o parser NUNCA entra em pânico, e o payload devolvido cabe nos dados
    if let Some(p) = rfuzz::payload_ruim(data) {
        assert!(p.len() <= data.len());
    }
});
```

Execução e achado (poucos segundos):

```text
$ cargo +nightly fuzz run fuzz_target_1
thread '<unnamed>' panicked at src/lib.rs:7:16:
range end index 10 out of range for slice of length 1
==NNNNN== ERROR: libFuzzer: deadly signal
...
artifact_prefix='.../fuzz/artifacts/fuzz_target_1/'; Test unit written to .../crash-adc83b19e793491b1c6ea0fd8b46cd9f32e592fc
```

Reproduzir o caso: `cargo +nightly fuzz run fuzz_target_1 fuzz/artifacts/fuzz_target_1/crash-adc83b19…` (mesma falha, determinística). Depois da correção (`payload` com `get`), a mesma execução:

```text
#11581832	DONE   cov: 14 ft: 15 corp: 1/1b lim: 4096 exec/s: 1052893 rss: 618Mb
Done 11581832 runs in 11 second(s)
```

Boas práticas:

- **Alvos que valem a pena:** parsers (protocolo, formato de arquivo, JSON/CSV/YAML próprio), decoders/descompressores, validadores de entrada, qualquer `unsafe` que interprete bytes. Propriedades úteis: "nunca entra em pânico", *round-trip* (`decode(encode(x)) == x`), comparação com implementação ingênua.
- **Corpus semente** (`fuzz/corpus/<alvo>/`): exemplos válidos reais aceleram a cobertura; **commite** o corpus mínimo e os `crash-*` corrigidos como **testes de regressão** (converta cada crash em `#[test]`).
- **Tempo:** PR = curto (`-- -max_total_time=60`); noturno = horas; mantenha `-- -rss_limit_mb=…` e `-timeout=…` para detectar DoS (travamento/memória), não só crash.
- **Estruturado:** `arbitrary` (`#[derive(Arbitrary)]`) gera tipos Rust em vez de bytes cegos (de terceiros, não verificado aqui). Alternativas: `honggfuzz-rs`, `afl.rs` (não verificadas).
- Fuzzing **complementa** testes de propriedade (`proptest`, → `rust-pro/references/testes.md`): proptest é rápido no CI e encolhe falhas; fuzz guiado por cobertura chega a estados que a geração aleatória não alcança.
- Combine: `cargo +nightly miri test` sobre o crash reproduzido ajuda a classificar (pânico lógico × UB).

## 7. Hardening do binário (o que já vem de graça e o que ligar)

Verificado com `readelf` num binário Linux x86_64 gerado por `rustc 1.99.0 -O` **sem flags especiais**:

```text
Type:      DYN (Position-Independent Executable file)      → PIE (ASLR efetivo)
GNU_RELRO  presente                                         → relocações somente-leitura
FLAGS      BIND_NOW        FLAGS_1  NOW PIE                 → "full RELRO" (resolução imediata de símbolos)
GNU_STACK  RW (sem E)                                       → pilha não executável (NX)
```

Ou seja, **PIE + full RELRO + NX são o padrão** no alvo `x86_64-unknown-linux-gnu`; você não precisa de `-C link-arg=-Wl,-z,relro,-z,now` (passar não muda nada — verificado). Confirme em **cada alvo** que entregar (musl estático, aarch64, Windows, macOS) — o padrão difere.

O que *você* decide:

| Controle | Como | Observação |
|---|---|---|
| Overflow verificado em release | `[profile.release] overflow-checks = true` | verificado (§4.3); medir custo |
| Abort em pânico | `panic = "abort"` | menor binário e sem *unwinding*; **mas** pânico em thread derruba o processo e `catch_unwind` deixa de funcionar — incompatível com a estratégia da `squad_strlen` (§7 de `unsafe-e-ffi.md`) |
| Sem símbolos de depuração no artefato | `strip = "symbols"` (ou `debuginfo` separado) | reduz informação para engenharia reversa e tamanho; guarde os símbolos para depurar incidentes |
| Binário reprodutível e sem caminhos locais | `--remap-path-prefix=$PWD=/src` (via `RUSTFLAGS`/`.cargo/config.toml`) e `--locked` | evita vazar caminho do dev; ajuda a verificar integridade |
| Usuário sem privilégio, FS somente-leitura, *seccomp*, capabilities mínimas | contêiner/K8s (`runAsNonRoot`, `readOnlyRootFilesystem`) | → **engenheiro-devops** / `rust-async-services` (container) |
| CFI, *stack protector*, `-Zsanitizer` em produção | nightly/experimental | **não verificado**; trate como pesquisa, não como requisito |

## 8. Resposta a incidente (advisory novo na sua árvore)

1. `cargo deny check advisories` (ou audit) falha → leia o advisory: função afetada, versões corrigidas, *workaround*.
2. `cargo tree -i <crate>` → quem a traz? Você chama a função afetada (busque no código)?
3. Corrija: `cargo update -p <crate>` (ou suba a dependência direta que a puxa); se não há patch, avalie troca de crate/`[patch]` temporário.
4. Não dá para corrigir hoje → `ignore` com **id + motivo + prazo + dono** (§2) e *issue* de acompanhamento.
5. Publicou uma versão afetada? `cargo yank` da versão + aviso no `RUSTSEC` (via PR no banco, se você é mantenedor) + rotação de segredos se houve vazamento.
6. Registre a lição (post-mortem curto) → `aprendizado-continuo`/`error_ledger` do Squad AI.

## 9. Checklist para adicionar uma dependência (5 minutos)

```text
[ ] Preciso mesmo? (std/um módulo de 30 linhas resolve? — P1)
[ ] Mantida? (última versão recente, mantenedores, issues respondidas) e popular (dependentes/downloads)
[ ] Licença na allow-list (`cargo deny check licenses`)
[ ] Sem advisory aberto (`cargo deny check advisories`)
[ ] Tem build.rs ou proc-macro? O que executa? (`cargo tree -e build`)
[ ] Quanto `unsafe` e por quê? (geiger — não verificado — ou leitura rápida)
[ ] Features mínimas (`default-features = false`) e árvore transitiva aceitável (`cargo tree`)
[ ] Versão fixada pelo lock; fonte = crates.io (sem git solto)
```
