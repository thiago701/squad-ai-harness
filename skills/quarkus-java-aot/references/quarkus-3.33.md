# Quarkus + GraalVM/Mandrel — fatos de versão (verificado set/2026)

> **Atualização 2026-09-27/28** (substitui a versão "verificado jul/2026"). Fontes: quarkus.io
> (blog/guides/release planning wiki), Maven Central metadata, graalvm.org, github.com/quarkusio.
> ⚠️ Correção: **`quarkus-bom:3.33.0` nunca existiu** — a linha LTS 3.33 começou em **3.33.1**
> (a Squad usava "3.33.0" como pin, o que quebra o build). Pin correto: **3.33.3.3**.

## Linha do tempo / suporte

| Versão | Tipo | Situação (set/2026) |
|---|---|---|
| **3.39.5** | STS (estável) | Última release (23/09/2026) |
| **3.33 (3.33.3.3)** | **LTS** | Suporte até **25/03/2027** |
| 3.40 | LTS | Anúncio iminente (30/09/2026) |
| **4.0** | major | Beta1 30/09/2026; **GA ~25/11/2026**; baseline **Java 21** |
| 4.3 | LTS | Prevista **31/03/2027** |
| 3.27 | LTS | Suporte até 2026-09-24 (encerrando) |

- Política: LTS a cada ~6 meses, 12 meses de suporte (quarkus.io/blog/lts-releases/).
- **3.x baseline Java 17**; suporte completo a **Java 25 desde 3.31**. Quarkus 4 = Java 21 baseline
  com virtual threads first-class (C. Escoffier, quarkus.io/blog/java21/).
- **Leyden integrado (3.32):** AOT caches — startup 370 ms → 80 ms (app pequena); app com 9 mil
  classes: 3 s → 900 ms (quarkus.io/guides/aot).

## Native builder — GraalVM / Mandrel

- **Mandrel 25** (base Temurin 25) é o builder native **default do Quarkus ≥ 3.27**.
- **GraalVM Oracle/CE 25.4.4.1.1** (base JDK 25.0.4.1; **sem GA para JDK 26**).
- **Oracle-only (não existe no CE/Mandrel):** PGO e **G1 GC no native** — CE/Mandrel usam Serial GC.
- Quick Build (`-Ob`) p/ compilações rápidas de dev; JFR/NMT/jcmd suportados desde GraalVM 25.
- Licença: GFTC — Oracle GraalVM gratuito **inclusive produção**.

## ORM / REST / reatividade (estado atual)

- **Hibernate ORM 7.4.x** (7.4.9 na 3.40); Hibernate Reactive 3.2 → 3.x; **Panache Next experimental (3.31)**.
- **Quarkus REST** é o nome estável do RESTEasy Reactive; RESTEasy Classic mantido; `resteasy-mutiny` **deprecated**.
- Mutiny continua a API reativa central; Kafka via SmallRye Reactive Messaging; OpenTelemetry/K8s estáveis.

## AWS Lambda / SnapStart / CRaC

- **SnapStart suportado** (guia oficial quarkus.io/guides/aws-lambda-snapstart/): preload de classes,
  priming via API CRaC (`Resource.beforeCheckpoint/afterRestore`), TieredCompilation.
- **CRaC:** suporte básico no core desde 2.10 (PR #23950, `org.crac`; runtime Azul Zulu). ⚠️ O guia
  `/guides/crac` retorna 404 no site novo — tratar como em fluxo de revisão. Spring Boot usa o mesmo
  mecanismo/runtime (sem interop direta).

## Evidências de benchmark (para a comparação com Spring Boot)

- **Benchmark oficial Quarkus (mar/2026, aberto/reproduzível — Hyperfoil + qDup, cpuset):**
  Quarkus **2,7× TPS**, **2,3× startup**, **metade da memória** vs Spring Boot equivalente;
  **native corta ~50% do throughput em AMBOS** os frameworks.
  → quarkus.io/blog/new-benchmarks/ · repo: github.com/quarkusio/spring-quarkus-perf-comparison
  ⚠️ benchmark vendor-run (porém open-source e auditado pela comunidade).
- **Acadêmico JCSI (dez/2025, DOI 10.35784/jcsi.8047):** native Quarkus vence em startup/recursos;
  Spring Boot tem ecossistema maior.
- **Nosso laboratório:** `labs/java-spring-quarkus-benchmark/` (resultados em
  `docs/research/java-spring-quarkus-benchmark.md`).

## Incertezas (27/09/2026)

1. Data exata do GA do 3.40 LTS (anúncio vs site oficial "Upcoming").
2. Hibernate Reactive na 3.39 não confirmado (3.2 confirmado na 3.31).
3. Docs CRaC ausentes do site novo.
4. Benchmark 2,7× é vendor-run; números de referência, não verdade universal — medir no workload real.
