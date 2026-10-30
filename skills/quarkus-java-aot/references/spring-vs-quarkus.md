# Spring Boot × Quarkus — comparação baseada em evidências (sem vencedor pré-declarado)

> **Regra:** conclusões só a partir de medições; itens qualitativos declarados como qualitativos.
> Evidências: (a) benchmark oficial Quarkus mar/2026 (aberto, vendor-run); (b) estudo acadêmico
> JCSI dez/2025 (DOI 10.35784/jcsi.8047); (c) laboratório próprio da Squad
> (`labs/java-spring-quarkus-benchmark/`, protocolo e números em
> `docs/research/java-spring-quarkus-benchmark.md`).

## 1. Dimensões mensuráveis (evidência)

| Dimensão | Spring Boot (JVM) | Quarkus (JVM) | Quarkus Native | Fonte |
|---|---|---|---|---|
| Startup | baseline | ~2,3× mais rápido | ms (native) | bench oficial Quarkus; lab próprio |
| Memória (RSS) | baseline | ~50% | ainda menor | bench oficial Quarkus |
| Throughput pico | baseline | **2,7× TPS** (bench oficial; workload específico) | ~50% do JVM | bench oficial |
| Build time | menor | maior (build-time processing) | muito maior (+min) | lab próprio |
| Tamanho do artefato | fat-jar ~18 MB (lab) | fast-jar ~16 MB (lab) | binário dezenas de MB | lab próprio |
| Cold start AWS | SnapStart 200–500 ms; Native 30–150 ms | SnapStart suportado; Native nativo por design | melhor da categoria | docs AWS/Quarkus |

> ⚠️ Benchmarks de terceiros medem o workload DELES. O lab da Squad mede o workload da Squad.
> Antes de decidir por performance, rodar o próprio protocolo.

## 2. Dimensões qualitativas (julgamento documentado, não número)

| Dimensão | Spring Boot | Quarkus |
|---|---|---|
| Ecossistema/maturidade | maior (mercado, empregos, libs, suporte comercial) | menor, porém focado e com LTS clara |
| Produtividade/DX | IDE madura, auto-config vasta | Dev Services + Dev UI + live reload + CLI; feedback instantâneo |
| Build-time vs runtime | runtime DI (familiar) | build-time DI (exige disciplina, habilita native) |
| Native/AOT | suportado (GraalVM 25, AOT Cache 4.1/Java 25+) | **nativo por design** (melhor DX native) |
| Compatibilidade de libs | máxima (ecossistema Java inteiro) | extensões curadas; libs de terceiros exigem verificação native |
| Observabilidade | Micrometer/OTel first-class (Boot 4) | SmallRye + Micrometer/OTel |
| AWS Lambda | SnapStart/AOT/Native via skills da Squad | SnapStart suportado; Native é o caminho natural |
| Padrão de mercado no Brasil | dominante | nicho crescente |

## 3. Matriz de decisão (P1-Simplicidade primeiro)

| Cenário | Recomendação com base em evidência |
|---|---|
| Time domina Spring, sem requisito de cold-start/memória | **Spring Boot** (P1: zero curva; performance raramente é o gargalo) |
| Serverless AWS / escala-a-zero / pods densos | **Quarkus** (startup/memória medidos; native first-class) |
| Native image como requisito duro | **Quarkus** (DX nativa; Spring exige mais cerimônia de hints) |
| Throughput de pico em JVM quente | **medir** — o bench vendor diz Quarkus 2,7×, mas workload específico; JIT maduro dos dois lados |
| Ecossistema/contratação/segurança de longo prazo | **Spring Boot** |
| Migração de legado Jakarta EE | **Quarkus** costuma ter rota mais suave p/ padrões EE |

## 4. O que NÃO afirmar sem medir

- "Quarkus é sempre mais rápido" — falso em throughput de pico nativo (~50%).
- "Spring é lento demais p/ serverless" — SnapStart/AOT Cache/Native cobrem parte do gap.
- "Native é sempre melhor" — trade-off build time × throughput × metadata.

**Conclusão-padrão da Squad:** escolher por **cenário** (requisito de startup/memória + time + ecossistema),
nunca por preferência de framework. Decisão registrada como ADR com a evidência usada.
