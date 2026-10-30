# Idiomas e padrões Rust (edição 2024)

> Autoral (Squad AI). Todos os trechos desta página foram **compilados e testados** com `rustc 1.99.0` (edição 2024), com `clippy::pedantic` + `-D warnings`
> (ver `cargo-e-qualidade.md` §3) e `rustfmt`. `thiserror` 2 e `anyhow` 1. Use como ponto de partida; adapte nomes ao domínio.

## 1. Propriedade e empréstimo — a regra de decisão

| Situação | Assinatura | Por quê |
|---|---|---|
| Só lê texto | `fn f(s: &str)` (não `&String`) | aceita `&String`, `&str`, literais, fatias |
| Só lê coleção | `fn f(xs: &[T])` (não `&Vec<T>`) | aceita `Vec`, array, fatia |
| Precisa guardar o valor | `fn f(s: impl Into<String>)` ou `s: String` | o chamador decide entre mover e alocar |
| Caminho de arquivo | `fn f(p: impl AsRef<Path>)` | aceita `&str`, `String`, `PathBuf`, `&Path` |
| Consome uma sequência | `fn f<I: IntoIterator<Item = T>>(it: I)` | aceita `Vec`, array, iterador, `HashSet`… |
| Modifica no lugar | `fn f(x: &mut T)` | sem retorno de cópia; sem `RefCell` |
| Pode ou não alterar a entrada | `fn f(s: &str) -> Cow<'_, str>` | só aloca quando necessário |
| Devolve sequência lazy | `-> impl Iterator<Item = &T>` (na edição 2024 captura os lifetimes em escopo; limite com `+ use<..>`) | sem alocar `Vec` intermediário |

```rust
use std::borrow::Cow;

/// Aceita qualquer coisa que se comporte como texto e devolve só o total — sem alocar.
pub fn tamanho_total<I, S>(itens: I) -> usize
where
    I: IntoIterator<Item = S>,
    S: AsRef<str>,
{
    itens.into_iter().map(|s| s.as_ref().len()).sum()
}

/// `Cow`: empresta quando nada muda; aloca só quando precisa modificar.
#[must_use]
pub fn sem_espacos_duplos(s: &str) -> Cow<'_, str> {
    if s.contains("  ") {
        Cow::Owned(s.split_whitespace().collect::<Vec<_>>().join(" "))
    } else {
        Cow::Borrowed(s)
    }
}
```

**Quando o borrow checker reclama** (diagnóstico → `rust-error-investigator`): primeiro tente (1) encurtar o empréstimo (extraia valor para variável local antes de mutar),
(2) devolver dado *owned* em vez de referência, (3) separar a struct em campos que podem ser emprestados independentemente, (4) usar índices em vez de referências para grafos.
**Só depois** pense em `Rc/Arc` + `RefCell/Mutex`; clonar para silenciar o compilador é sintoma de modelagem errada.

## 2. Erros

**Biblioteca** → enum tipado (o chamador pode reagir por variante). **Aplicação** → `anyhow` com contexto (o operador precisa de narrativa).

```rust
use std::{num::ParseIntError, path::{Path, PathBuf}};
use anyhow::Context as _;
use thiserror::Error;

#[derive(Debug, Error)]
#[non_exhaustive] // acrescentar variante não quebra semver
pub enum ConfigError {
    #[error("não foi possível ler {path}")]
    Leitura { path: PathBuf, #[source] fonte: std::io::Error },
    #[error("porta inválida: {0:?}")]
    Porta(String, #[source] ParseIntError),
    #[error("campo obrigatório ausente: {0}")]
    Ausente(&'static str),
}

pub fn ler_porta(path: &Path) -> Result<u16, ConfigError> {
    let txt = std::fs::read_to_string(path)
        .map_err(|fonte| ConfigError::Leitura { path: path.to_owned(), fonte })?;
    let bruto = txt
        .lines()
        .find_map(|l| l.strip_prefix("porta="))
        .ok_or(ConfigError::Ausente("porta"))?;
    bruto.trim().parse().map_err(|e| ConfigError::Porta(bruto.to_owned(), e))
}

// fronteira da aplicação: contexto narra a falha; `ensure!` valida regra de negócio
pub fn carregar(path: &Path) -> anyhow::Result<u16> {
    let porta = ler_porta(path).context("carregando configuração do serviço")?;
    anyhow::ensure!(porta >= 1024, "porta privilegiada: {porta}");
    Ok(porta)
}
```

Regras:

- **`?` em tudo**; `unwrap()/expect()` só em teste e em invariante *provada* (com `expect("motivo")`) — o lint `clippy::unwrap_used` obriga a justificar.
- **`#[source]`/`#[from]`** preservam a cadeia (`err.source()`); com `anyhow`, `e.chain()` e o formato `{:#}` mostram todas as causas. Teste verificado:
  `carregar("/nao/existe.cfg")` produz a cadeia `["carregando configuração do serviço", "não foi possível ler /nao/existe.cfg", "No such file or directory (os error 2)"]`.
- **Não exponha detalhe interno ao cliente** (mensagem de `io::Error`, SQL, caminhos): converta no limite HTTP/CLI e registre a causa no log → `rust-async-services`.
- `Box<dyn Error + Send + Sync>` serve a scripts/protótipos; em API pública de biblioteca use tipo próprio.
- `panic!` é para *bug* (invariante violada), nunca para entrada inválida. Em binários de serviço, defina `panic = "abort"` só se tiver supervisor (→ `rust-performance-engineer`).

## 3. Newtype e "parse, don't validate"

Valide **uma vez, na borda**, e carregue a prova no tipo:

```rust
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct Email(String);

#[derive(Debug, thiserror::Error, PartialEq, Eq)]
#[error("e-mail inválido: {0:?}")]
pub struct EmailInvalido(String);

impl TryFrom<&str> for Email {
    type Error = EmailInvalido;
    fn try_from(s: &str) -> Result<Self, Self::Error> {
        match s.split_once('@') {
            Some((u, d)) if !u.is_empty() && d.contains('.') => Ok(Self(s.to_ascii_lowercase())),
            _ => Err(EmailInvalido(s.to_owned())),
        }
    }
}

impl AsRef<str> for Email {
    fn as_ref(&self) -> &str { &self.0 }
}
```

O campo é privado ⇒ **só dá para obter um `Email` válido**; funções internas recebem `&Email` e dispensam revalidação. O mesmo vale para `Porta(u16)`, `Dinheiro(i64 centavos)`, `Id<Pedido>`.
Conversões numéricas: `u16::try_from(v)?` em vez de `v as u16` (que trunca em silêncio).

## 4. Typestate — o compilador impede o uso errado

```rust
use std::time::Duration;

#[derive(Debug)] pub struct SemUrl;
#[derive(Debug)] pub struct ComUrl(String);

#[derive(Debug)]
pub struct ClienteBuilder<U> { url: U, timeout: Duration }

#[derive(Debug)]
pub struct Cliente { pub url: String, pub timeout: Duration }

impl Default for ClienteBuilder<SemUrl> {
    fn default() -> Self { Self { url: SemUrl, timeout: Duration::from_secs(5) } }
}

impl ClienteBuilder<SemUrl> {
    #[must_use]
    pub fn url(self, url: impl Into<String>) -> ClienteBuilder<ComUrl> {
        ClienteBuilder { url: ComUrl(url.into()), timeout: self.timeout }
    }
}

impl<U> ClienteBuilder<U> {
    #[must_use]
    pub fn timeout(mut self, t: Duration) -> Self { self.timeout = t; self }
}

impl ClienteBuilder<ComUrl> {
    #[must_use]
    pub fn build(self) -> Cliente { Cliente { url: self.url.0, timeout: self.timeout } }
}

// ClienteBuilder::default().timeout(..).url("http://x").build()   ✔
// ClienteBuilder::default().build()                                ✘ não compila: build só existe com URL
```

Use typestate quando há **obrigatoriedade** (campo, ordem, estado de conexão). Para opções todas opcionais, um builder simples (`mut self → Self`) ou `struct` com `..Default::default()` basta (P1).

## 5. Enums como máquina de estados

```rust
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Pedido {
    Rascunho { itens: Vec<String> },
    Pago { id: u64, total_centavos: u64 },
    Cancelado { motivo: String },
}

#[derive(Debug, PartialEq, Eq)]
pub struct TransicaoInvalida { pub de: &'static str, pub evento: &'static str }

impl Pedido {
    fn nome(&self) -> &'static str {
        match self {
            Self::Rascunho { .. } => "rascunho",
            Self::Pago { .. } => "pago",
            Self::Cancelado { .. } => "cancelado",
        }
    }

    /// Consome `self`: o estado antigo deixa de existir.
    pub fn pagar(self, id: u64, total_centavos: u64) -> Result<Self, TransicaoInvalida> {
        match self {
            Self::Rascunho { itens } if !itens.is_empty() => Ok(Self::Pago { id, total_centavos }),
            outro => Err(TransicaoInvalida { de: outro.nome(), evento: "pagar" }),
        }
    }
}
```

`match` **exaustivo** (sem `_ =>` em enum seu) transforma "esqueci um estado novo" em erro de compilação. Em enum **público** da biblioteca, marque `#[non_exhaustive]` e documente.

## 6. Iteradores e coleções

```rust
use std::collections::HashMap;
use std::num::ParseIntError;

// colete Result: para no primeiro erro, sem unwrap nem laço manual
pub fn parse_todos(entrada: &str) -> Result<Vec<i64>, ParseIntError> {
    entrada.split(',').map(|p| p.trim().parse()).collect()
}

pub fn frequencias(palavras: &[&str]) -> HashMap<String, usize> {
    palavras.iter().fold(HashMap::new(), |mut m, p| {
        *m.entry((*p).to_lowercase()).or_default() += 1;
        m
    })
}

// agrupa elementos consecutivos iguais, sem alocar (1.77+)
pub fn grupos_iguais(v: &[i32]) -> Vec<&[i32]> {
    v.chunk_by(|a, b| a == b).collect()
}
```

- Devolva `impl Iterator` quando o chamador só vai percorrer: `fn evens<'a>(v: &'a [i32]) -> impl Iterator<Item = &'a i32> + use<'a>` (a edição 2024 captura todos os lifetimes em escopo; `use<..>` limita ao necessário).
- `entry().or_default()`/`or_insert_with` em vez de `contains_key + insert`; `BTreeMap` quando a ordem importa; `IndexMap` (crate) só se precisar de ordem de inserção.
- `Vec::with_capacity(n)` quando n é conhecido; `extend` em vez de `push` em laço; `retain`/`extract_if` para remover in-place.
- Evite `collect::<Vec<_>>()` intermediário só para iterar de novo.
- **Strings:** `String` é UTF-8 — `s.len()` é **bytes**; use `chars()`, `char_indices()` ou `unicode-segmentation` para texto de usuário. Fatiar fora de limite de caractere **entra em pânico**.

## 7. RAII — `Drop` como guarda de escopo

```rust
pub struct Guarda<F: FnMut()>(Option<F>);

impl<F: FnMut()> Guarda<F> {
    pub fn nova(f: F) -> Self { Self(Some(f)) }
}

impl<F: FnMut()> Drop for Guarda<F> {
    fn drop(&mut self) {
        if let Some(mut f) = self.0.take() { f(); }
    }
}
```

Use para liberar lock lógico, remover arquivo temporário, restaurar variável de ambiente em teste. `Drop` **não** pode falhar nem ser `async`: para limpeza assíncrona, ofereça `async fn close(self)` e documente (→ `rust-async-services`).

## 8. Traits: despacho estático × dinâmico

```rust
use std::{collections::BTreeMap, sync::Arc};

pub trait Formatador { fn formatar(&self, valor: f64) -> String; }
#[derive(Debug, Clone, Copy)] pub struct Moeda;
#[derive(Debug, Clone, Copy)] pub struct Percentual;
impl Formatador for Moeda { fn formatar(&self, v: f64) -> String { format!("R$ {v:.2}") } }
impl Formatador for Percentual { fn formatar(&self, v: f64) -> String { format!("{:.1}%", v * 100.0) } }

/// Estático: monomorfiza; tipo conhecido em compilação; sem chamada indireta.
pub fn relatorio_estatico(f: &impl Formatador, xs: &[f64]) -> Vec<String> {
    xs.iter().map(|&x| f.formatar(x)).collect()
}

/// Dinâmico: escolhido em runtime (config/plugin). `Send + Sync` permite compartilhar entre threads.
pub fn registro() -> BTreeMap<&'static str, Arc<dyn Formatador + Send + Sync>> {
    BTreeMap::from([
        ("moeda", Arc::new(Moeda) as Arc<dyn Formatador + Send + Sync>),
        ("pct", Arc::new(Percentual)),
    ])
}

// exigência verificada em COMPILAÇÃO (falha o build se o tipo deixar de ser Send + Sync)
pub const fn exige_send_sync<T: Send + Sync>() {}
const _: () = exige_send_sync::<Arc<dyn Formatador + Send + Sync>>();
```

| Preciso de… | Escolha |
|---|---|
| desempenho máximo, tipo conhecido | genérico (`impl Trait` / `<T: Trait>`) |
| coleção heterogênea, plugin, redução de código gerado | `Box<dyn Trait>` / `Arc<dyn Trait + Send + Sync>` |
| compartilhar entre threads | `Arc<T>` (+ `Mutex`/`RwLock`/atômico); **`Rc` não é `Send`** |
| mutação interior em uma thread | `Cell`/`RefCell` (panica se violar empréstimo em runtime) |
| fechar o conjunto de implementações | `enum` (despacho por `match`) ou *sealed trait* |
| herdar supertrait e usar como `&dyn Super` | trait upcasting (1.86): `fn as_named(a: &dyn Animal) -> &dyn Named { a }` |

Traits: poucos métodos, nomes por capacidade (`Formatador`, `Armazenamento`); implemente `Debug` em todo tipo público (o lint `missing_debug_implementations` cobra); derive o que for barato (`Clone, PartialEq, Eq, Hash, Default`).
`async fn` em trait **pública**: declare `fn get(&self, id: u64) -> impl Future<Output = Option<String>> + Send;` (lint `async_fn_in_trait`).

## 9. Convenções de API (Rust API Guidelines, resumidas)

- Nomes: `snake_case` funções/módulos, `CamelCase` tipos/traits, `SCREAMING_SNAKE` constantes. Conversões: `as_*` (barata, empresta), `to_*` (cara, aloca), `into_*` (consome). Getters sem prefixo `get_` (`len()`, não `get_len()`).
- `new` só quando há invariante; senão `Default` + literal de struct. Construtores falíveis: `TryFrom`/`FromStr`/`fn parse(...) -> Result`.
- Implemente `Display` para mensagens humanas, `Debug` (derive) para depuração; `From`/`TryFrom` em vez de `from_x()` soltos; `FromIterator`/`Extend` em coleções próprias.
- `#[must_use]` em construtores/builders/`Result`-like; `#[non_exhaustive]` em tipos públicos extensíveis; `pub(crate)` por padrão.
- Docs: `///` com seção `# Errors` e `# Panics`; exemplos executáveis (`cargo test --doc`); `#![warn(missing_docs)]` em biblioteca publicada.
- Módulos: um arquivo por conceito; `lib.rs` só reexporta (`pub use`) a API pública; evite `mod.rs` aninhado (prefira `foo.rs` + `foo/`).

## 10. Mutabilidade, closures e estado compartilhado

- Prefira **passar dado por valor/empréstimo** a estado global. Global necessário → `static X: LazyLock<…>` (1.80) para init preguiçosa e thread-safe; `static mut` é **erro** na edição 2024 (referências).
- Closure que move: `move || …` ao enviar para outra thread/tarefa; capture **clones nomeados** (`let tx = tx.clone();`) em vez de capturar o ambiente inteiro.
- `Mutex<T>`: segure o *guard* o mínimo; **não** atravesse `.await` com `std::sync::Mutex` (→ `rust-async-services`); envenenamento (`PoisonError`) acontece se uma thread entrou em pânico segurando o lock — trate ou use `parking_lot`.
- Atômicos (`AtomicBool`, `AtomicU64`) para contadores/flags; `Ordering::Relaxed` só para contadores independentes; na dúvida, `SeqCst`.
- Tempo: `Instant` (monotônico) para medir duração, `SystemTime` só para relógio de parede; `Duration::from_mins` (1.91).
- Inteiros: em código de segurança/financeiro, use `checked_*`/`strict_*` (1.91) — overflow aritmético não pode ser silencioso em release.

## 11. Checklist de revisão rápida

- [ ] Assinaturas aceitam o tipo mais geral e devolvem o mais útil; nenhum `&String`/`&Vec<T>`.
- [ ] Nenhum `unwrap/expect/panic!` em caminho de produção; erros com contexto na fronteira.
- [ ] Invariantes no tipo (newtype/enum/typestate); sem `bool` de modo, sem string mágica.
- [ ] `clone()` justificado; sem `Rc<RefCell>` onde índices ou `&mut` resolvem.
- [ ] API pública mínima, documentada, com `#[must_use]`/`#[non_exhaustive]` onde cabe.
- [ ] `cargo fmt`, `clippy -D warnings`, testes e doctests verdes.
