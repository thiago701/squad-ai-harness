# aws-lambda-java25-aot · Cold start: GraalVM Native é o PADRÃO para Java 25 (SnapStart é o override)

> Reference da skill `aws-lambda-java25-aot` (movida da SKILL.md em 11/10/2026 — hub + references, I3). Carregue só quando a tarefa pedir este tema.

## Cold start: GraalVM Native é o PADRÃO para Java 25 (SnapStart é o override)

**Decisão da Squad (2026-07-05, baseada em evidência medida — ver `lambda-aot-benchmark/`
e `report/relatorio-comparativo.html`): para novas Lambdas Java 25, o padrão é
GraalVM Native (AOT).** Racional duplo:

1. **Performance (prioridade P2 do usuário)** — Native reduz o cold start ~**4× vs `java21`**
   (p95 medido ~540 ms em função instrumentada; "30–150 ms" só p/ handler enxuto — **medir**;
   fontes em `references/graalvm-native-java25-sota.md`), vencendo o p99 em tráfego spiky.
2. **Eficiência de recursos** — footprint de memória menor (menos GB-segundo) + right-size;
   `-XX:+UseCompactObjectHeaders` (JEP 519, final/opt-in) corta +10–20% de heap.

> **Nota (atualizada pós-pesquisa 2025-2026):** `java25` + SnapStart **É GA** (14/nov/2025) e
> **grátis para Java** — não é mais "só `java21`". O default Native se sustenta por **performance**,
> não por indisponibilidade do SnapStart. As "3 AOTs" (Native ≠ Leyden AOT cache ≠ SnapStart) e
> os números com fonte estão em `references/graalvm-native-java25-sota.md`.
>
> **Atualização set/2026 (pesquisa verificada):** SnapStart suporta Java 11+ (inclui `java25`),
> hooks via CRaC (`beforeCheckpoint/afterRestore`; restore ≤ 10 s; **recriar pool JDBC/Hikari no
> afterRestore**). AWS SDK v2 **2.55.x**; **Powertools for Java 2.10.0** (v1 EOL). Alternativa
> nova: **Lambda Managed Instances** (GA 30/11/2025) — zero cold start em EC2 gerenciado.
> Fontes: `docs/research/notes/java-aws-notes.md`.

| Caminho | Cold start | Esforço / custo | Papel |
|---|---|---|---|
| **GraalVM Native (AOT)** — esta skill, Java 25 | ~**4× < java21** (medir) | alto: metadata, build +minutos, divergência JVM↔nativo | **PADRÃO para Java 25 novo** |
| SnapStart — runtime `java21`/`java25` | 200–500 ms (P99 −90%) | zero mudança de build; **grátis p/ Java**; só config SAM | **override** documentado (ver regra) |
| Runtime gerenciado `java25` + AOT cache (Leyden, default) | sub-2 s | zero | baseline; cargas tolerantes a cold start |

**Regra:** gere **Native por padrão** para Java 25. Faça **override para SnapStart (em
`java21`)** quando o contexto pesar mais que a latência: deploy contínuo várias vezes/dia,
time pequeno priorizando time-to-market, muitas libs com reflexão/proxy dinâmico difícil de
portar, ou SLA que tolera 200–500 ms. Nesses casos seja honesto — proponha SnapStart e gere
pelo caminho vanilla-JVM. O default é **opinativo, não cego**: a evidência e o trade-off de
TCO (SnapStart vence esforço/manutenção) estão documentados em `lambda-aot-benchmark/report/`.
