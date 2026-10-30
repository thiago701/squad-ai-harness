# QA orientada a risco — Java 21/25 e o pipeline JEV

> Núcleo executável: `scripts/qa/jev_qa.py` · suíte gold `labs/jev-ecosystem/suites/qa/`.
> Pesquisa de estado da arte (2026): ver `docs/relatorios/QA-INTELIGENTE-2026-09-26.md` §B.

## 1. Stack Java 21/25 por camada (versões verificadas 2026)

| Camada | Ferramenta | Versão | Papel no gate |
|---|---|---|---|
| Unit | JUnit 5 | 5.13.0 | `@ClassTemplate`/`@ParameterizedClass` eliminam matrizes duplicadas |
| Unit | AssertJ | 3.x | SoftAssertions em integração |
| Unit | Mockito | 5.20.x | strict stubs + inline mock maker (nunca "mockar tudo") |
| Unit (PBT) | jqwik | 1.10.1 | invariantes de domínio (serialize/deserialize, validações, parsers) |
| Mutation | PIT/Pitest | 1.20.5 | **só nas classes mudadas** (incremental) ou nightly; fallback `-Djava.release=21` (PIT rejeita bytecode 25) |
| Cobertura | JaCoCo | 0.8.13 | ratchet **no diff** (changed code coverage), não gate global |
| Integração | Testcontainers | 1.21.x | Postgres/Kafka/LocalStack reais efêmeros — menos drift de ambiente |
| Integração HTTP | WireMock | 3.11+ | stubs HTTP p/ clientes e consumer contracts |
| Contract | Pact JVM / SCC | 4.7.0 / 4.1.x | quebra de contrato no build via broker can-i-deploy |
| Arquitetura | ArchUnit | 1.4.x | regras hexagonais/clean como testes no gate |
| Assíncrono | Awaitility | 4.3.0 | polling assertions (compatível com Virtual Threads) |
| TIA no CI | gw-kit.test-impact / Develocity | — | seleção por impacto (padrão Ekstazi, ~32% menos tempo — validar recall na suíte) |

## 2. Testes preditivos (Probability of Regression)

Sinais que alimentam o Risk Classifier JEV: arquivos alterados · dependências (grafo) ·
histórico de bugs/falhas · complexidade ciclomática · cobertura atual · git diff ·
churn (frequência de alteração) · mutation survivors · áreas críticas do domínio.
Tier resultante governa a cerimônia: crítico → revisão de segurança + mutação
incremental + testes de regressão obrigatórios; baixo → fluxo enxuto.

## 3. Testes preditivos por propriedade (PBT)

Invariantes substituem famílias de testes tradicionais:

```text
Para qualquer entrada válida X: deserialize(serialize(X)) == X
Para qualquer lista L: ordenar(ordenar(L)) == ordenar(L)   (idempotência)
```

Aplicar em: regras matemáticas · validações · parsers · transformação de dados ·
serialização · algoritmos · regras com grande espaço de entrada. jqwik gera
exemplos e encolhe contra-exemplos automaticamente (shrinking).

## 4. Flaky intelligence (causa-raiz, nunca re-run cego)

Sinais que o JEV detecta e o padrão de correção:

| Sinal | Causa-raiz | Correção |
|---|---|---|
| `Thread.sleep`/`Instant.now`/`new Date()` | relógio real | injetar `Clock`/relógio fake |
| `Math.random`/UUID sem seed | randomização | seed determinística por teste |
| HTTP/socket/WebClient direto | rede real | WireMock/Testcontainers |
| `static` mutável compartilhado | estado entre testes | isolar/reset em `@AfterEach` |
| timeout curto fixo | lentidão de CI | Awaitility com deadline razoável |

## 5. Minimização de suíte (com evidência, nunca por velocidade)

Regra: remover/consolidar só quando a evidência mostra manutenção ou aumento de
confiança. Critérios do JEV `analisar_redundancia`: mesmo alvo + mesmo padrão de
assert → consolidar/parametrizar (ex.: 10 testes redundantes → 2-3 parametrizados,
mesma ou maior cobertura, menor tempo). Testes lentos de baixo valor → tier
noturno. Nunca remover teste que cobre branch crítica ou regra de negócio sem
substituto com mutation kill equivalente.

## 6. Quality Gate por PR (regras do JEV `gate_pr`)

- Changed code coverage < 80% → **block**
- Mutation score < 70% (quando medido) → **block**
- Flaky rate > 5% → **block**
- Tempo > 1,3× baseline sem cobertura ≥ 90% → necessary (custo desproporcional)
- Testes novos sem ganho de confiança declarado → necessary (quantidade não é métrica)
- **Nunca** bloquear por % global de line coverage isolado.
