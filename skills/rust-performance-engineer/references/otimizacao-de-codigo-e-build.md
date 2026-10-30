# Otimização de código e de build em Rust

> Autoral (Squad AI). Medições em rustc 1.99.0 (Linux x86_64, **2 vCPUs**, VM compartilhada, alocador glibc), divan 0.1.21. Números **indicativos desta máquina** e sujeitos a ±20% de ruído — a **ordem de grandeza** e o método é que valem.
> Itens sem medição aqui estão marcados **não verificado**. Fontes conceituais: *The Rust Performance Book*, *The Cargo Book* (perfis), documentação do rustc (reescritas, sem cópia).

Regra de ouro (P1 > P2 > P3): cada técnica abaixo só entra com **perfil que a justifique** e **medição antes × depois**. A ordem é: (A) menos trabalho → (B) menos alocação → (C) layout → (D) despacho → (E) paralelismo → (F) build.

## 1. Menos alocação e menos cópia (padrões verificados)

Código que compila, passa `clippy -D warnings`, `rustfmt --check` e tem teste:

```rust
use std::borrow::Cow;
use std::fmt::Write as _;
use std::io::{self, BufWriter, Write};

/// `Cow`: só aloca quando precisa mudar o texto.
#[must_use]
pub fn normaliza_espacos(s: &str) -> Cow<'_, str> {
    if s.contains("  ") {
        Cow::Owned(s.split_whitespace().collect::<Vec<_>>().join(" "))
    } else {
        Cow::Borrowed(s)
    }
}

/// Reutiliza o mesmo `String` entre iterações: `clear()` mantém a capacidade.
#[must_use]
pub fn linhas_formatadas(ids: &[u32]) -> usize {
    let mut buf = String::with_capacity(32);
    let mut total = 0;
    for id in ids {
        buf.clear();
        let _ = write!(buf, "pedido-{id:08}"); // `write!` em String nunca falha
        total += buf.len();
    }
    total
}

/// Sem `Vec` intermediário: o iterador é consumido de uma vez.
#[must_use]
pub fn soma_dos_pares_ao_quadrado(v: &[u64]) -> u64 {
    v.iter()
        .filter(|&&x| x % 2 == 0)
        .map(|&x| x.wrapping_mul(x))
        .fold(0, u64::wrapping_add)
}

/// Saída em volume: um `BufWriter` sobre o `stdout` travado (uma vez), `flush` explícito no fim.
pub fn imprime_muitas(n: u32, destino: impl Write) -> io::Result<()> {
    let mut out = BufWriter::new(destino);
    for i in 0..n {
        writeln!(out, "linha {i}")?;
    }
    out.flush()
}

/// Texto imutável e compartilhado: `Arc<str>`/`Box<str>` evitam a capacidade extra de `String`.
#[must_use]
pub fn rotulo(s: &str) -> Box<str> {
    s.into()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cow_so_aloca_quando_muda() {
        assert!(matches!(normaliza_espacos("a b c"), Cow::Borrowed(_)));
        let r = normaliza_espacos("a   b  c");
        assert!(matches!(r, Cow::Owned(_)));
        assert_eq!(r, "a b c");
    }

    #[test]
    fn demais() {
        assert_eq!(linhas_formatadas(&[1, 22]), 2 * "pedido-00000001".len());
        assert_eq!(soma_dos_pares_ao_quadrado(&[1, 2, 3, 4]), 4 + 16);
        let mut saida = Vec::new();
        imprime_muitas(3, &mut saida).unwrap();
        assert_eq!(
            String::from_utf8(saida).unwrap(),
            "linha 0\nlinha 1\nlinha 2\n"
        );
        assert_eq!(&*rotulo("x"), "x");
        // `stdout().lock()` também é `Write`: imprime_muitas(n, std::io::stdout().lock())
    }
}
```

Quando usar cada um:

| Padrão | Use quando | Evidência |
|---|---|---|
| Emprestar (`&str`/`&[T]`) em vez de clonar; `HashMap<&str, _>` | os dados de origem vivem mais que o mapa | `summarize_slow → fast`: 10.163 → 3 alocações (dhat) |
| `write!(&mut String, …)` em vez de `format!` + `+` | montar texto em laço | idem; o topo do callgrind era `malloc`/`fmt` |
| `buf.clear()` e reutilizar o `String`/`Vec` | laço que produz um buffer por iteração | mantém a capacidade — zero alocação após a 1ª volta |
| `Cow<str>` | o texto **quase sempre** passa inalterado | só aloca no ramo que muda |
| Iterador encadeado até o consumo (`filter/map/fold`) | evitar `Vec` intermediário | o compilador funde o laço |
| `Box<str>`/`Arc<str>` | texto imutável guardado por muito tempo | sem a capacidade extra de `String` |
| `BufWriter`/`BufReader` | qualquer I/O linha a linha | **16×** (3,90 ms → 0,236 ms por 10 mil linhas, escrita em `/dev/null`) |
| `with_capacity` | tamanho conhecido de objeto grande/repetido | **sem ganho mensurável** para 100 mil `push` de `u64` (58,0 × 59,3 µs) — não aplique por reflexo |

Detalhes que costumam morder:

- `BufWriter` **precisa de `flush()`** (o `Drop` tenta, mas **ignora erros** — chame `flush()?` e trate). Para `stdout`, trave **uma vez**: `BufWriter::new(std::io::stdout().lock())`; o `stdout` do Rust é *line-buffered* (descarrega a cada `\n`, **inclusive quando redirecionado**) e `println!` trava/destrava a cada chamada — por isso 10 mil linhas custam 16× mais sem `BufWriter` (verificado com arquivo; a diferença vem de uma syscall por linha).
- `HashMap` padrão usa SipHash (resistente a HashDoS). *Hashers* mais rápidos (FxHash, ahash — terceiros, **não verificados**) são ótimos para chaves internas confiáveis e **perigosos** para chave controlada por atacante.
- `clone()` de `Vec<String>`/`HashMap` em laço quente costuma ser o gargalo "invisível"; procure `clone`/`to_string`/`to_owned`/`collect::<Vec<_>>()` no perfil.
- `String` → `&str` em argumentos (`fn f(s: &str)`) e `impl AsRef<Path>`/`impl Into<String>` com parcimônia: genéricos demais aumentam o tempo de compilação e o tamanho do binário (monomorfização).
- `Vec<Vec<T>>` → um `Vec<T>` plano + índice melhora localidade de cache; meça com dados reais.

## 2. Algoritmo e estrutura de dados (o ganho que o compilador não dá)

- `sort_unstable` em vez de `sort` quando empates não precisam manter a ordem: **2,24 ms → 1,33 ms** (100 mil `u64` aleatórios, ≈ 1,7×). Para "k menores" use `select_nth_unstable`; para busca repetida, ordene uma vez + `binary_search`.
- `contains` em `Vec` dentro de laço = O(n²): use `HashSet`/`BTreeSet`. Cuidado com o inverso: para n pequeno (dezenas), `Vec` + busca linear costuma **vencer** o mapa (localidade) — meça.
- `BTreeMap` quando precisa de ordem/range; `HashMap` quando só consulta. `VecDeque` para fila (não `Vec::remove(0)`).
- Evite recalcular: mova invariantes para fora do laço; memoize resultado caro com chave estável; não serialize/desserialize duas vezes.
- Strings: `str::contains`/`find` são otimizados; `regex` compilada **uma vez** (`LazyLock<Regex>` — `LazyLock` estável desde 1.80), nunca `Regex::new` dentro do laço.

## 3. Despacho e inline

```rust
trait Op { fn aplica(&self, x: u64) -> u64; }
struct Soma(u64);
impl Op for Soma { fn aplica(&self, x: u64) -> u64 { x.wrapping_add(self.0) } }

// 1000 chamadas: Vec<Box<dyn Op>> ≈ 1,25 µs   ×   Vec<Soma> (estático) ≈ 0,35 µs  (≈ 3,6×)
```

- `dyn Trait` custa uma chamada indireta **e impede o inline** (é isso que explica a diferença, não a tabela virtual em si). Em fronteiras de plugin/coleção heterogênea é a ferramenta certa; em laço quente com um tipo só, use genéricos (`impl Trait`/`T: Trait`).
- Genéricos monomorfizam: mais código/binário/compilação. Se o tipo concreto não importa para o desempenho, `&dyn Trait` na API pública reduz o tamanho.
- Função **não genérica** só é inlinada entre crates se for pequena (o rustc inlina automaticamente funções muito pequenas entre crates desde ~1.75 — **não verificado aqui**), se tiver `#[inline]` ou se houver LTO; genéricos são sempre instanciados no crate que os usa. `#[inline(always)]` raramente ajuda — meça. `#[cold]`/`#[inline(never)]` em caminhos de erro mantêm o caminho quente compacto.
- *Bounds checks*: o LLVM elimina a maioria quando o laço é simples — **verificado**: `for i in 0..v.len() { s += v[i] }` e `v.iter().fold(...)` empataram em 10,34 µs. Prefira iteradores por clareza; use `get_unchecked` só com prova e Miri → **rust-unsafe-security**.

## 4. Perfil de release (`[profile.release]`) — números reais

Binário de teste: `serde` + `serde_json` + `HashMap` (parse e serialização de um struct). Linux x86_64, rustc 1.99.0, 2 vCPUs. Cada linha acrescenta a opção à anterior; override por variável `CARGO_PROFILE_RELEASE_*`:

| Configuração | Tamanho | Observação |
|---|---:|---|
| `release` padrão | 593.456 B | já sem `debuginfo` (padrão do release) |
| `+ strip = "symbols"` | 455.632 B | −23% só removendo a tabela de símbolos |
| `+ lto = "fat"`, `codegen-units = 1` | 373.488 B | −18% adicional; **build 37% mais lento** (6,4 s → 8,8 s do zero; `thin`: 8,0 s) |
| `+ panic = "abort"` | 369.640 B | −1% (remove a tabela de *unwinding* só em parte) |
| `+ opt-level = "s"` | 333.224 B | −10% |
| `+ opt-level = "z"` | 334.432 B | **maior** que `s` neste caso — "z" não é sempre o menor |
| `debug = "line-tables-only"` (sem strip) | 5.210.544 B | ≈ 9× — só para profiling |
| `debug = true` (sem strip) | 6.848.216 B | ≈ 12× |

Efeito de **velocidade** de `lto = "fat"` + `codegen-units = 1` no benchmark `summarize` (n = 5000, mediana, 2 rodadas por configuração):

| | `fast` | `slow` |
|---|---:|---:|
| padrão | 76,3 – 76,9 µs | 273,6 – 280,7 µs |
| fat LTO + cgu=1 | 49,0 e 61,3 µs | 199,7 e 245,2 µs |

Plausível ganho de ~10–35% (a tabela mostra −20% a −36% no `fast` e −11% a −29% no `slow`) (inline entre o crate de benchmark e a lib), **mas** as duas rodadas com LTO divergiram 25% entre si — confirme com mais rodadas antes de afirmar qualquer número no PR. O que é robusto: **ganho existe, custo de build também**.

Quando usar cada botão:

| Opção | Efeito | Custo / risco |
|---|---|---|
| `lto = "thin"` | meio-termo (inline entre crates) | build um pouco mais lento; bom padrão para serviço |
| `lto = "fat"` + `codegen-units = 1` | máximo de inline/otimização | build mais lento e mais memória no linker; CI/imagem final, não o laço de dev |
| `panic = "abort"` | binário menor, sem *unwinding* | **pânico em qualquer thread derruba o processo**; `catch_unwind` (e o isolamento de pânico de tarefas do tokio, que depende de *unwind*) deixa de funcionar — incompatível com a estratégia de `rust-unsafe-security` (FFI) e com serviços que querem sobreviver a pânico por requisição |
| `strip = "symbols"` | binário menor | perde símbolos para depurar incidentes — guarde um build com símbolos (`[profile.profiling]`) e o *build id* |
| `opt-level = "s"/"z"` | binário menor | pode ficar mais lento; compare `s`, `z` e 3 (padrão do release) — Lambda/CLI pequena |
| `-C target-cpu=x86-64-v3` (ou `native`) | usa AVX2 etc. | **o binário pode dar `SIGILL` em CPU mais antiga**; `native` só para a máquina que compila. Verificado que a flag compila e roda no CPU deste ambiente; use `v3` só se **toda** a frota suporta |
| `incremental = false` (padrão no release) | — | em CI o cargo já desativa incremental quando `CI=true` (verificado) |

Receitas (comece pela primeira e só avance se medir ganho):

```toml
# Serviço (latência/throughput)
[profile.release]
lto = "thin"
codegen-units = 1
# panic = "abort"   # só se aceitar derrubar o processo em pânico

# Binário pequeno (CLI, Lambda): meça s × z × 3
[profile.release-small]
inherits = "release"
opt-level = "s"
lto = "fat"
codegen-units = 1
panic = "abort"
strip = "symbols"

# Profiling (nunca vai para produção)
[profile.profiling]
inherits = "release"
debug = true
```

(`cargo build --profile release-small` grava em `target/release-small/`.)

## 5. PGO — o fluxo funciona; o ganho depende da carga (verificado)

PGO usa um perfil de execução para guiar inline e layout. Fluxo exercitado de ponta a ponta com `llvm-tools` (`rustup component add llvm-tools`):

```bash
TGT=x86_64-unknown-linux-gnu
# 1) build instrumentado (passe --target para não instrumentar build scripts)
RUSTFLAGS="-Cprofile-generate=/tmp/pgo" cargo build --release --target $TGT
# 2) rode com carga REPRESENTATIVA (gera .profraw em /tmp/pgo)
./target/$TGT/release/app <carga>
# 3) mescle
"$(rustc --print sysroot)/lib/rustlib/$TGT/bin/llvm-profdata" merge -o /tmp/pgo/merged.profdata /tmp/pgo
# 4) rebuild com o perfil
RUSTFLAGS="-Cprofile-use=/tmp/pgo/merged.profdata" cargo build --release --target $TGT
```

Resultado medido (3.000 repetições de `summarize_fast` + `summarize_slow`, 3 rodadas): base 1,07 / 1,15 / 1,40 s × PGO 1,09 / 1,04 / 1,15 s — **dentro do ruído**. Esperado: a carga é dominada por alocação/`fmt` (nada que o PGO melhore).
PGO rende em código **com muitos ramos e chamadas indiretas** (parsers, interpretadores, compiladores), tipicamente alguns pontos percentuais a algumas dezenas — **não medido aqui**. Regras: perfil de carga **real**, reperfilar a cada mudança relevante de código (o perfil envelhece), manter o fluxo automatizado no CI de release.
`cargo-pgo` e BOLT (otimização pós-link) são ferramentas de terceiros — **não verificadas**.

## 6. Alocador

Todas as medições acima usam o alocador do sistema (glibc `malloc`). Trocar o alocador global é uma linha (`#[global_allocator] static A: …`; o mesmo mecanismo do `dhat::Alloc`, verificado), mas:

- **mimalloc/jemalloc** (terceiros): reduzem fragmentação/contenção em serviços multi-thread com muita alocação pequena; ganho típico documentado pela comunidade — **não medido aqui**; mede-se com a carga real (RSS e p99).
- **musl estático:** o `malloc` do musl é notoriamente mais lento sob contenção; em imagens `scratch`/musl com muita alocação, avalie mimalloc (comportamento **não medido aqui**). Tamanho verificado do serviço de exemplo: gnu 1,12 MB × musl estático 1,25 MB → **rust-async-services** (tabela de contêiner).
- Antes de trocar: reduza as alocações (Seção 1) — é mais barato e mais seguro.

## 7. Concorrência e CPU-bound

- Trabalho CPU-bound e separável: `rayon` (terceiros, **não verificado aqui**) com `par_iter()`; meça com `1`, `2`, `N` threads — Amdahl e *false sharing* limitam o ganho (esta VM tem 2 vCPUs: o teto é ~2×).
- Em serviço async: trabalho pesado vai para `tokio::task::spawn_blocking` (ou pool dedicado), **não** dentro do handler; limite a concorrência com `Semaphore` → **rust-async-services**.
- Contenção: `Mutex` global em caminho quente → shard (`N` mutexes), troque por atores/canais, ou estruturas lock-free (terceiros). Meça tempo de espera (tokio-metrics/perf), não suponha.
- Latência de cauda (p99): culpados frequentes são pausas de alocação grande, `clone` de coleção grande, lock contention, GC de cache externo, retries sem *jitter* e I/O síncrono no runtime. Teste de carga (oha/wrk/k6 — terceiros, **não verificados**) com taxa fixa, não só "o mais rápido possível".

## 8. Tamanho do binário e cold start

- Ordem das alavancas (ver tabela da Seção 4): `strip` → LTO/`codegen-units = 1` → `opt-level = "s"` (compare `z`) → `panic = "abort"` → menos dependências/`default-features = false`.
- `cargo bloat --release --crates` / `cargo llvm-lines` (terceiros, **não verificados**) dizem *o que* ocupa espaço/monomorfização.
- Empacotar com UPX (compressão de executável): afeta tempo de início, alarmes de antivírus e verificação de integridade — **não recomendado por padrão**; não verificado aqui.
- Lambda/cold start: o tamanho do pacote e a inicialização (conexões, config, TLS) pesam mais que o `opt-level` → **aws-lambda-go-rust**.

## 9. Tempo de compilação (feedback loop)

- `cargo check` no laço de edição; `cargo build --timings` para achar o que domina (verificado); `lld` é o *linker* padrão no Linux x86_64 desde 1.90; menos `features`/dependências pesadas e **proc-macros** (cada uma serializa o início do build).
- LTO fat + `codegen-units = 1` são **só** para o artefato final (custo medido: +37% de build neste exemplo).
- Cache de compilação em CI (`Swatinem/rust-cache`, `sccache` — terceiros, não verificados); `cargo nextest` para testes mais rápidos (verificado → `rust-pro/references/testes.md`).

## 10. Checklist de entrega de uma otimização

```text
[ ] meta e métrica definidas; baseline medido em --release (≥ 3 rodadas, medianas)
[ ] causa identificada por perfil (dhat/callgrind/perf), não por palpite
[ ] UMA mudança por vez; teste de equivalência verde; clippy -D warnings
[ ] depois: tabela real antes × depois (tempo + alocações e/ou instruções); ganho >> ruído
[ ] custo registrado: legibilidade, tempo de build, tamanho, portabilidade (target-cpu), panic=abort
[ ] sem unsafe novo (ou com Miri + // SAFETY: → rust-unsafe-security)
[ ] ganho < alvo ou < ruído → reverter (P1)
```
