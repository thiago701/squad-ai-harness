# Medição e profiling em Rust

> Autoral (Squad AI). Tudo marcado **verificado** foi executado em rustc/cargo 1.99.0 (Linux x86_64, VM compartilhada) com divan 0.1.21, criterion 0.8.2, dhat 0.3 e valgrind/callgrind 3.22.
> Os números são **indicativos desta máquina** (variam ±20% entre rodadas — ver §3); reproduza no seu ambiente. Ferramentas não executadas aqui (perf, flamegraph, samply, cargo-bloat, iai-callgrind) estão marcadas **não verificado**.
> Fontes conceituais: *The Rust Performance Book*, documentação do cargo/divan/criterion/dhat/valgrind (reescritas, sem cópia).

## 1. Caso de estudo (usado nas seções seguintes)

Agregar `n` linhas por chave e serializar `k=valor;`. Duas versões com **o mesmo resultado** (teste de equivalência incluso):

```rust
use std::collections::HashMap;
use std::fmt::Write as _;

pub struct Row {
    pub key: String,
    pub n: u64,
}

/// Versão lenta: clona chaves, `format!` por linha, mapa sem capacidade, concatena com `+`.
#[must_use]
pub fn summarize_slow(rows: &[Row]) -> String {
    let mut agg: HashMap<String, u64> = HashMap::new();
    for r in rows {
        *agg.entry(format!("{}", r.key.clone())).or_insert(0) += r.n;
    }
    let mut keys: Vec<String> = agg.keys().cloned().collect();
    keys.sort();
    let mut out = String::new();
    for k in keys {
        out = out + &format!("{}={};", k, agg[&k]);
    }
    out
}

/// Versão rápida: empresta `&str`, pré-dimensiona, escreve direto no `String` de saída.
#[must_use]
pub fn summarize_fast(rows: &[Row]) -> String {
    let mut agg: HashMap<&str, u64> = HashMap::with_capacity(64);
    for r in rows {
        *agg.entry(r.key.as_str()).or_insert(0) += r.n;
    }
    let mut keys: Vec<&str> = agg.keys().copied().collect();
    keys.sort_unstable();
    let mut out = String::with_capacity(keys.len() * 12);
    for k in keys {
        let _ = write!(out, "{k}={};", agg[k]); // `write!` em String nunca falha
    }
    out
}

#[must_use]
pub fn sample(n: usize) -> Vec<Row> {
    (0..n).map(|i| Row { key: format!("k{}", i % 50), n: i as u64 }).collect()
}
```

```rust
// tests/eq.rs — a otimização não pode mudar o resultado
use rbench::{sample, summarize_fast, summarize_slow};

#[test]
fn resultados_iguais() {
    let r = sample(500);
    assert_eq!(summarize_slow(&r), summarize_fast(&r));
}
```

## 2. Preparar o projeto para medir

```toml
[dev-dependencies]
divan = "0.1.21"
criterion = { version = "0.8.2", default-features = false, features = ["cargo_bench_support"] }

[[bench]]
name = "divan_bench"
harness = false          # divan/criterion trazem o próprio `main`

[profile.release]
debug = "line-tables-only"   # símbolos úteis para perf/callgrind sem info completa de depuração

# Alternativa que NÃO polui o release de produção: um perfil só para profiling
[profile.profiling]
inherits = "release"
debug = true
```

- `cargo bench` usa o perfil `bench` (herda `release`) — a mensagem do cargo confirma: ``Finished `bench` profile [optimized + debuginfo]``. Sempre otimizado; **nunca** meça em `dev`
  (verificado: ordenar 2 milhões de `u64` ≈ 0,9 s em `dev` × 0,04–0,06 s em release).
- **Custo do debuginfo (verificado):** o binário de exemplo foi de 593 KB (padrão) para 5,2 MB (`line-tables-only`) e 6,8 MB (`debug = true`). Por isso o perfil **`profiling` separado** (`cargo build --profile profiling`, binário em `target/profiling/`):
  perfila-se com símbolos e entrega-se o `release` enxuto.
- Sobrescrever perfil por variável de ambiente, sem editar o `Cargo.toml`, funciona (verificado): `CARGO_PROFILE_BENCH_LTO=fat CARGO_PROFILE_BENCH_CODEGEN_UNITS=1 cargo bench`.
- Use um diretório de build dedicado (`CARGO_TARGET_DIR`) ao comparar flags, para não misturar caches.

## 3. Benchmarks: divan e criterion

### divan (sintaxe curta, saída em árvore) — verificado

```rust
use rbench::{sample, summarize_fast, summarize_slow};

fn main() {
    divan::main();
}

#[divan::bench(args = [1_000, 5_000])]
fn slow(bencher: divan::Bencher, n: usize) {
    let rows = sample(n);
    bencher.bench_local(|| summarize_slow(divan::black_box(&rows)));
}

#[divan::bench(args = [1_000, 5_000])]
fn fast(bencher: divan::Bencher, n: usize) {
    let rows = sample(n);
    bencher.bench_local(|| summarize_fast(divan::black_box(&rows)));
}
```

```text
$ cargo bench --bench divan_bench
Timer precision: 24 ns
divan_bench  fastest       │ slowest       │ median        │ mean          │ samples │ iters
├─ fast                    │               │               │               │         │
│  ├─ 1000   17.81 µs      │ 296.9 µs      │ 18.29 µs      │ 22.27 µs      │ 100     │ 100
│  ╰─ 5000   74.4 µs       │ 170.2 µs      │ 76.93 µs      │ 85.31 µs      │ 100     │ 100
╰─ slow                    │               │               │               │         │
   ├─ 1000   61.48 µs      │ 160.7 µs      │ 63.48 µs      │ 67.24 µs      │ 100     │ 100
   ╰─ 5000   263.5 µs      │ 518.3 µs      │ 273.6 µs      │ 287.6 µs      │ 100     │ 100
```

Leitura: compare a **mediana** (a coluna `fastest` é o melhor caso e engana; `slowest` mostra outliers). `args = [...]` roda o mesmo benchmark em vários tamanhos — revela complexidade (aqui ≈ linear nas duas versões, mas `slow` com constante ≈ 3,6× maior).
Filtro por nome: `cargo bench -- fast`. `bench_local` não exige `Sync` (use quando o dado não é `Sync`); `with_inputs(|| …).bench_local_values(|x| …)` prepara uma entrada nova **fora** do tempo medido (necessário para operações que consomem/mutam a entrada, como `sort`).

### criterion (estatística e comparação com baseline) — verificado

```rust
use criterion::{Criterion, criterion_group, criterion_main};
use rbench::{sample, summarize_fast, summarize_slow};
use std::hint::black_box;

fn bench(c: &mut Criterion) {
    let rows = sample(5_000);
    let mut g = c.benchmark_group("summarize");
    g.bench_function("slow", |b| b.iter(|| summarize_slow(black_box(&rows))));
    g.bench_function("fast", |b| b.iter(|| summarize_fast(black_box(&rows))));
    g.finish();
}

criterion_group!(benches, bench);
criterion_main!(benches);
```

```text
summarize/slow          time:   [270.54 µs 280.80 µs 291.64 µs]
                        change: [−16.702% −11.865% −6.7892%] (p = 0.00 < 0.05)
                        Performance has improved.
summarize/fast          time:   [76.491 µs 78.250 µs 80.119 µs]
                        change: [−8.8420% −4.1017% +0.3492%] (p = 0.10 > 0.05)
                        No change in performance detected.
```

Os três valores de `time` são o intervalo de confiança (limite inferior, estimativa, limite superior). **Lição importante, observada de verdade:** o bloco `change:` compara com a execução anterior salva em `target/criterion/`;
aqui o código **não mudou** entre as rodadas e mesmo assim o criterion declarou *"Performance has improved"* (−11,9%, p<0,05) — era ruído da VM compartilhada. Conclusões:

1. Só confie em comparação quando a máquina está quieta e a diferença é **muito maior** que a variação entre rodadas (aqui 3,6× — inequívoco; 5% — indistinguível).
2. Para comparar A×B de forma justa, rode **os dois no mesmo processo/rodada** (como acima, mesmo grupo) ou use baselines nomeados: `cargo bench -- --save-baseline antes` … `cargo bench -- --baseline antes` (opções documentadas do criterion; não exercitadas aqui).
3. `default-features = false` + `cargo_bench_support` (como no `Cargo.toml` acima, verificado) mantém a árvore de dependências enxuta; gráficos/relatórios HTML dependem de *features* opcionais que variam por versão — consulte a documentação da versão usada (não verificado).

### `black_box` e a armadilha do compilador (verificado)

```rust
#[divan::bench]
fn entrada_constante() -> u64 { (1..=100_000u64).sum() }                  // 0,143 ns   ← impossível: < 1 ciclo
#[divan::bench]
fn entrada_opaca() -> u64 { (1..=divan::black_box(100_000u64)).sum() }    // 1,01 ns    ← ainda ~nada
```

0,143 ns é menos de **um ciclo de CPU** por chamada: o LLVM calculou a resposta em **tempo de compilação**. Mesmo com `black_box` na entrada, 1 ns indica que o LLVM transformou a soma numa **fórmula fechada** (`n(n+1)/2`) — o laço sumiu.
Regras: (1) valores sub-nanossegundo para trabalho que deveria iterar milhares de vezes = o benchmark mede nada; (2) passe a entrada por `black_box` (`std::hint::black_box` ou `divan::black_box`) **e** devolva o resultado (divan/criterion o consomem);
(3) escolha cargas que **não** tenham forma fechada e dependam de dados reais (como o `summarize_*`, que lê um `Vec<Row>`).

### Rodar benchmark também como teste

**Verificado:** `cargo test --benches` (ou `cargo bench --bench <nome> -- --test`) executa cada benchmark **uma vez** em modo teste — o criterion imprime `Testing summarize/slow … Success` e o divan lista a árvore —, só para garantir que compilam e não entram em pânico; barato no PR. A medição de verdade fica no job noturno/manual.

## 4. Alocações com `dhat` — verificado

```toml
[dependencies]
dhat = { version = "0.3", optional = true }

[features]
dhat-heap = ["dep:dhat"]
```

```rust
#[cfg(feature = "dhat-heap")]
#[global_allocator]
static ALLOC: dhat::Alloc = dhat::Alloc;

fn main() {
    #[cfg(feature = "dhat-heap")]
    {
        let _p = dhat::Profiler::builder().testing().build();
        let rows = rbench::sample(5_000);
        let a0 = dhat::HeapStats::get();
        let a = rbench::summarize_slow(&rows);
        let a1 = dhat::HeapStats::get();
        let b = rbench::summarize_fast(&rows);
        let b1 = dhat::HeapStats::get();
        assert_eq!(a, b);
        println!("slow: {} blocos, {} bytes", a1.total_blocks - a0.total_blocks, a1.total_bytes - a0.total_bytes);
        println!("fast: {} blocos, {} bytes", b1.total_blocks - a1.total_blocks, b1.total_bytes - a1.total_bytes);
    }
}
```

```text
$ cargo run --release --example dh --features dhat-heap
slow: 10163 blocos, 61982 bytes
fast: 3 blocos, 4616 bytes
```

`10.163 → 3` alocações e `61.982 → 4.616` bytes para o **mesmo** resultado. `Profiler::builder().testing()` + `HeapStats::get()` permite **asserções de alocação em testes** (ex.: `assert_eq!(depois.total_blocks - antes.total_blocks, 3)` num teste de regressão — alocação é determinística, ao contrário de tempo).
Sem `testing()`, o perfil é gravado em `dhat-heap.json` para o visualizador DHAT (`dh_view.html`, distribuído com o Valgrind) — mostra *quem* alocou, com pilha. Custo: o alocador instrumentado desacelera o programa; use em execução curta. No modo `testing()` só um `Profiler` pode existir por processo — rode esses testes isolados (arquivo de teste próprio ou `--test-threads=1`).

## 5. Instruções determinísticas com `valgrind --tool=callgrind` — verificado

Tempo de relógio oscila; **contagem de instruções não** — é o melhor sinal para um **portão de regressão em CI ruidoso** (e para saber *onde* o programa gasta).

```bash
cargo build --release --example cmp          # perfil com debug = "line-tables-only" para ter nomes/linhas
valgrind --tool=callgrind --callgrind-out-file=cg.slow.out target/release/examples/cmp slow
valgrind --tool=callgrind --callgrind-out-file=cg.fast.out target/release/examples/cmp fast
callgrind_annotate --inclusive=yes cg.slow.out | head -40
```

Resultado real (mesmo programa: gera 5.000 linhas e chama uma das duas funções):

```text
slow: I refs: 9,662,611        fast: I refs: 6,337,627          (diferença ≈ 3,3 M instruções)

callgrind_annotate (self, slow):
  923,332 ( 9.56%)  malloc.c:_int_free
  696,781 ( 7.21%)  malloc.c:_int_malloc
  635,045 ( 6.57%)  malloc.c:malloc
  539,258 ( 5.58%)  core/src/fmt/mod.rs:core::fmt::write
  448,950 ( 4.65%)  alloc::fmt::format::format_inner
callgrind_annotate --inclusive=yes (slow):
4,728,624 (48.94%)  rbench::summarize_slow
3,929,363 (40.67%)  rbench::sample            ← preparo dos dados, igual nas duas versões
```

Leitura: **o topo é alocador + `fmt`** ⇒ o problema é alocação/formatação, não lógica. `summarize_slow` sozinha custa 4,73 M instruções (inclusivo); a `fast` foi tão pequena que o LLVM a *inlinou* no `main` (não aparece como função). O `sample` (3,93 M) é custo de preparação **compartilhado** — sempre separe preparo de trabalho medido.
Notas: o callgrind roda ~20–50× mais devagar (use entradas pequenas); `--inclusive=yes` soma chamadas; `kcachegrind`/`qcachegrind` visualizam o arquivo `.out` (não verificado). Wrappers para benchmarks de instruções em CI (`iai-callgrind`, `gungraun`) são terceiros e **não foram verificados**.

## 6. Perfil de CPU em carga real (perf · flamegraph · samply) — **não verificado aqui**

O ambiente de teste não tinha `perf`; a receita abaixo é a documentada e **precisa ser validada no seu ambiente**:

```bash
# 1) símbolos + frame pointers (melhora muito a pilha do perf)
CARGO_PROFILE_RELEASE_DEBUG=line-tables-only RUSTFLAGS="-C force-frame-pointers=yes" cargo build --release
# 2a) flamegraph (terceiros): cargo install flamegraph --locked   → cargo flamegraph --bin app -- <args>
# 2b) perf direto:           perf record -F 99 --call-graph fp ./target/release/app <args> ; perf report
# 2c) samply (terceiros):    cargo install samply --locked → samply record ./target/release/app <args>
```

Em contêiner/VM, `perf` exige permissão (`kernel.perf_event_paranoid`, capability `CAP_PERFMON`/modo privilegiado) — peça ao time de plataforma; em produção prefira **amostragem de baixa frequência e curta duração**.
Como ler um flamegraph: largura = proporção de tempo; procure **platôs largos** no topo (funções que gastam *elas mesmas*), não torres altas. Pilha dominada por `malloc`/`memcpy`/`fmt` aponta para o Passo 3-B da SKILL.
**Segurança:** perfis e flamegraphs contêm nomes de função, caminhos e às vezes argumentos — trate como confidenciais.

## 7. Tempo de compilação e tamanho — `--timings` verificado

```bash
cargo build --release --timings        # gera target/cargo-timings/cargo-timing-<data>.html
```

O HTML mostra a linha do tempo por crate (quais dependências e proc-macros dominam; onde há gargalo de paralelismo). Ações usuais: reduzir `features`, remover dependência pesada, `cargo check` no laço de edição,
perfil `dev` com `opt-level = 2` só para dependências (`[profile.dev.package."*"] opt-level = 2`, documentado — não medido aqui), `lld` (padrão no Linux x86_64 desde 1.90). `cargo bloat` e `cargo llvm-lines` (terceiros, **não verificados**) mostram o que ocupa o binário/monomorfização.

## 8. Protocolo de benchmark confiável (checklist)

```text
[ ] cargo bench / --release; mesma máquina, mesma carga, mesma toolchain (rustc -Vv anotado)
[ ] entrada via black_box; resultado consumido; carga sem forma fechada; preparo fora do tempo medido
[ ] ≥ 3 rodadas; comparar medianas; só aceitar ganho >> variação entre rodadas (aqui ±20%)
[ ] A e B no mesmo grupo/processo; teste de equivalência passando
[ ] alocações (dhat) e/ou instruções (callgrind) como evidência determinística complementar
[ ] máquina quieta (sem build/CI paralelo); em CI use instruções, não tempo, como portão
[ ] registrar no PR: comando, versão, tabela real antes × depois, riscos
```
