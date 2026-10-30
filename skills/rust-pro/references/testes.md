# Testes em Rust

> Autoral (Squad AI). Exemplos executados com `cargo 1.99.0` (`proptest` 1.11, `insta` 1.49). As saídas de falha abaixo são **reais** (capturadas no toolchain 1.99.0);
> `nextest`, cobertura e mocks são ferramentas de terceiros — o status de verificação está indicado em cada uma.

## 1. Onde cada teste mora

| Tipo | Local | Enxerga | Rodar |
|---|---|---|---|
| Unitário | `#[cfg(test)] mod tests` no mesmo arquivo | itens privados | `cargo test --lib` |
| Integração | `tests/*.rs` (cada arquivo é um crate separado) | só a API pública | `cargo test --test integracao` |
| Doctest | exemplos em `///` | só a API pública | `cargo test --doc` |
| Propriedade | `proptest!` dentro dos unitários | idem unitário | `cargo test` |
| Snapshot | `insta::assert_*_snapshot!` | idem | `cargo test` (+ `cargo insta review`) |
| Benchmark | `benches/` (**não** é teste) | API pública | `cargo bench` → rust-performance-engineer |

Regras: teste **comportamento** observável (entrada → saída/efeito), não a estrutura interna; um motivo para falhar por teste; nomes que dizem a regra
(`reparte_conserva_total`, não `test1`); sem dependência de ordem, relógio real, rede pública ou porta fixa.

## 2. Unitário em tabela, `should_panic`, `assert_matches!`

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use std::assert_matches; // 1.96

    #[test]
    fn normaliza_tabela() {
        let casos: &[(&[&str], &[&str])] = &[
            (&[], &[]),
            (&["A", "a"], &["a"]),
            (&["  x ", "", "y"], &["x", "y"]),
        ];
        for (entrada, esperado) in casos {
            assert_eq!(normaliza(entrada), *esperado, "entrada: {entrada:?}");
        }
    }

    #[test]
    #[should_panic(expected = "n deve ser > 0")]   // sempre com `expected`: evita passar por outro panic
    fn reparte_zero_panica() {
        let _ = reparte(10, 0);
    }

    #[test]
    fn padrao_do_resultado() {
        assert_matches!(reparte(5, 2).as_slice(), [3, 2]);
    }
}
```

- Mensagem do `assert_eq!` quando falha: `assertion 'left == right' failed` + `left:`/`right:`; **sempre** passe contexto (`"entrada: {entrada:?}"`) em testes de tabela.
- Teste que devolve `Result` evita `unwrap`: `#[test] fn ok() -> Result<(), Box<dyn std::error::Error>> { …; Ok(()) }` (o erro é impresso por `Debug` — use `anyhow::Result` para cadeia de causas).
- `#[ignore = "motivo"]` para testes lentos/de integração (rodam com `cargo test -- --ignored`); nunca ignore sem motivo registrado.
- Teste de erro: `assert!(matches!(err, Erro::Negativo(-1)))` ou `assert_matches!`; compare **variante**, não a mensagem de texto.

## 3. Testes de propriedade (`proptest`)

Em vez de escolher exemplos, descreva **invariantes** e deixe o framework gerar centenas de entradas e **encolher** a falha para o menor caso:

```rust
use proptest::prelude::*;

proptest! {
    // a soma das partes é o total, e nenhuma parte difere de outra por mais de 1
    #[test]
    fn reparte_conserva_total(total in 0u32..1_000_000, n in 1u32..1000) {
        let partes = reparte(total, n);
        prop_assert_eq!(partes.iter().sum::<u32>(), total);
        let (min, max) = (partes.iter().min().unwrap(), partes.iter().max().unwrap());
        prop_assert!(max - min <= 1);
    }

    // idempotência: normalizar duas vezes = normalizar uma vez
    #[test]
    fn normaliza_idempotente(tags in proptest::collection::vec("[ a-cA-C]{0,4}", 0..8)) {
        let refs: Vec<&str> = tags.iter().map(String::as_str).collect();
        let uma = normaliza(&refs);
        let refs2: Vec<&str> = uma.iter().map(String::as_str).collect();
        prop_assert_eq!(normaliza(&refs2), uma);
    }
}
```

Saída real quando a implementação tem um bug (troquei `<` por `<=` em `reparte`):

```text
proptest: Saving this and future failures in .../proptest-regressions/lib.txt
cc 5a37e349753c89462b65c01b181d478e5459637be4b38a8de06d796a955a41a8
Test failed: assertion failed: `(left == right)`
  left: `1`,
 right: `0` at src/lib.rs:65.
minimal failing input: total = 0, n = 1
```

- O arquivo `proptest-regressions/*.txt` guarda a semente do caso encolhido: **commite-o** — vira teste de regressão permanente.
- Boas propriedades: *round-trip* (`decode(encode(x)) == x`), idempotência, invariantes de conservação (soma/tamanho), comparação com implementação simples (modelo), "nunca entra em pânico" para parsers.
- Limite de tempo: `PROPTEST_CASES=2000` no CI noturno, padrão (256) no PR.

## 4. Snapshots (`insta`)

Para saídas grandes/estruturadas (JSON, relatórios, mensagens de erro), compare com um *snapshot* revisado por humanos:

```rust
#[test]
fn snapshot_inline() {
    insta::assert_debug_snapshot!(reparte(7, 3), @r"
    [
        3,
        2,
        2,
    ]
    ");
}
```

Falha real (esperado `[3, 3, 1]`, obtido `[3, 2, 2]`):

```text
Snapshot: snapshot_inline
Expression: reparte(7, 3)
-old snapshot
+new results
    1     1 │ [
    2     2 │     3,
    3       │-    3,
    4       │-    1,
          3 │+    2,
          4 │+    2,
To update snapshots run `cargo insta review`
```

Em CI, `INSTA_UPDATE=no` (padrão quando `CI` está definida) impede gravação automática. **Nunca** aceite snapshot sem ler o diff; snapshot com dado sensível/instável (timestamps, ids, segredos) deve ser redigido com filtros (`insta::with_settings!({filters => …})`).

## 5. Testes assíncronos e tempo

- `#[tokio::test]` cria um runtime por teste. Para tempo determinístico: `#[tokio::test(start_paused = true)]` (**exige** `tokio` com feature `test-util` em `[dev-dependencies]`) — `sleep`/`timeout` avançam sozinhos quando todas as tarefas estão ociosas, sem dormir de verdade → **rust-async-services** (§ testes).
- Nunca `std::thread::sleep` para "esperar a tarefa terminar": use canal/`JoinHandle`/`Notify`/`CancellationToken`.
- Teste de handler HTTP: `tower::ServiceExt::oneshot` sobre o `Router` (sem abrir porta) — exemplo em `rust-async-services`.

## 6. Isolamento, ambiente e arquivos

- **Edição 2024:** `std::env::set_var`/`remove_var` são `unsafe` (E0133). Em teste isso é duplamente perigoso (testes rodam em paralelo). Passe a configuração como **parâmetro/struct** e teste a função pura de parsing (`Config::from_lookup(|k| map.get(k))`), em vez de mutar o ambiente.
- Arquivos temporários: crate `tempfile` (`tempfile::tempdir()` apaga ao sair do escopo — RAII). Nunca escreva em caminho fixo do repositório.
- Estado global entre testes: evite; se inevitável, `serial_test` (terceiros) ou `-- --test-threads=1` **só** para o subconjunto afetado.
- Fakes em vez de mocks mágicos: defina uma `trait` pequena na fronteira (relógio, armazenamento, HTTP) e implemente um `FakeX` simples no teste. Mocks por macro (`mockall`, terceiros) só quando o fake manual fica maior que o ganho.
- Serviços reais (Postgres, Redis, LocalStack): `testcontainers` (terceiros) ou `docker compose` no CI, marcados `#[ignore]` ou numa *feature* `integration`, para a suíte unitária continuar rápida.

## 7. Runner, cobertura e qualidade da suíte

| Ferramenta | Uso | Status de verificação |
|---|---|---|
| `cargo test` | padrão; um processo por binário de teste, threads por teste | verificado |
| `cargo nextest run` | um processo **por teste** (isolamento real), paralelismo melhor, `--retries`, saída limpa; **não roda doctests** (rode `cargo test --doc` à parte) | **verificado** (cargo-nextest 0.9.146: 7 testes em 2 binários, sem o doctest) |
| `cargo llvm-cov` | cobertura por LLVM (`rustup component add llvm-tools-preview`) | terceiros, não verificado aqui |
| `cargo mutants` | testes de mutação: mede se a suíte detecta defeitos (mais honesto que cobertura) | terceiros, não verificado aqui |
| Miri (`cargo +nightly miri test`) | detecta UB em `unsafe` | verificado → rust-unsafe-security |
| `cargo fuzz` | fuzzing guiado por cobertura (parsers, decoders) | → rust-unsafe-security |

- **Cobertura é meio, não meta:** 100% de linhas sem asserção forte não prova nada; combine com mutação nos módulos críticos e propriedades.
- **Flaky:** reproduza com `--test-threads=1` e depois em loop (`nextest --retries 0 -j 1` / `for i in {1..50}`); causas comuns: relógio real, ordem de tarefas, porta fixa, dado compartilhado, `HashMap` com ordem de iteração assumida. **Não** mascare com retry — conserte a causa.
- Teste que só passa em *release* (ou só em *debug*) indica overflow aritmético, `debug_assert!` ou UB: investigue com Miri e `overflow-checks`.

## 8. Doctests

```rust
/// Raiz quadrada inteira.
///
/// # Examples
/// ```
/// assert_eq!(nucleo::raiz(16).unwrap(), 4);
/// ```
///
/// # Errors
/// Devolve [`Erro::Negativo`] se `n < 0`.
pub fn raiz(n: i64) -> Result<i64, Erro> { /* … */ }
```

- Linhas começando com `# ` ficam ocultas na documentação mas são compiladas (boilerplate). Atributos de bloco: ` ```no_run ` (compila, não executa — I/O/rede), ` ```compile_fail ` (garante que o uso errado **não** compila — ótimo para typestate), ` ```ignore ` (evite).
- `cargo test --doc` roda os exemplos; `RUSTDOCFLAGS="-D warnings" cargo doc` pega links quebrados.

> Nota sobre `nextest`: instalação por `cargo install cargo-nextest --locked`. Verificado aqui: `cargo nextest run` executou os testes unitários e de integração (7) e **não** o doctest, que foi rodado à parte com `cargo test --doc` — mantenha os dois passos no CI.
