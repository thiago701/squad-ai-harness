# Stack de testes Java moderno — versões e estratégia de risco

> Complemento do hub `especialista-qualidade`. Versões verificadas 09/2026.
> **Objetivo declarado da Squad:** máxima confiança + maior cobertura de risco + menos testes
> redundantes + menor impacto no tempo da pipeline — **quantidade nunca é a meta**.

## 1. Stack e versões atuais (09/2026)

| Ferramenta | Versão | Nota |
|---|---|---|
| **JUnit** | **6.1.3** (repo renomeado p/ `junit-framework`) | JUnit 6 é a geração atual; JUnit 5 segue suportado |
| AssertJ | 4.x (última) | fluent assertions, padrão da Squad |
| **Mockito** | **5.22.0** (v6 em preparação p/ JUnit 6) | Boot 4: `@MockitoBean`/`@MockitoSpyBean` (substituem @MockBean) |
| **Testcontainers** | **2.0.4** | linha 2.x; DB reais em CI (`@ServiceConnection`) |
| WireMock | 3.x | mock de APIs HTTP em testes de contrato/integração |
| Pitest (mutation) | 1.x | mutation score ≥ 80% em domínio crítico |
| jqwik (property-based) | 1.x | propriedades p/ invariantes e geradores |
| Contract testing | Spring Cloud Contract **em transição p/ Stubborn.sh** ⚠️ | monitorar; SCC 5 em andamento — não apostar build novo no repo antigo |
| RestAssured / MockMvcTester / RestTestClient | — | RestTestClient é o padrão novo do Boot 4 |
| k6 | — | testes de performance/load na pipeline |

## 2. Pirâmide × risco (não pirâmide × contagem)

| Camada | Quando vale | Tempo de pipeline típico |
|---|---|---|
| Unit (JUnit+AssertJ+Mockito) | regras de domínio, casos de borda, contratos de método | ms |
| Integração (Testcontainers) | contrato com DB/broker real, migrações Flyway/Liquibase | s |
| API (RestTestClient/WireMock) | contrato HTTP, autenticação, erros | s |
| Mutation (Pitest) | somente **domínio crítico** (valida que testes verificam comportamento) | min |
| Property-based (jqwik) | parsers, serialização, invariantes de agregados | s |
| Native/AOT | quando o alvo é native/AOT: rodar a suíte contra o binário (`@QuarkusIntegrationTest`, native test Boot) | min (CI) |
| Serverless (SAM local/LocalStack) | handlers Lambda: cold start simulado, SnapStart hooks | min |

**Regra de corte:** teste redundante (mesmo comportamento, duas camadas) é custo, não segurança —
mantenha o de camada mais barata que detecta a falha. Cobertura de linhas é efeito colateral.

## 3. TDD na Squad (método)

1. Teste primeiro (ou junto) para **mudança de comportamento**; refatoração pura não exige teste novo.
2. AssertJ fluent + nomes que descrevem o contrato ("deve_rejeitar_pedido_sem_estoque").
3. `@MockitoBean` no slice certo (`@WebMvcTest`/`@DataJpaTest`) em vez de `@SpringBootTest` pesado.
4. Testcontainers com `@ServiceConnection`; Dev Services no Quarkus.
5. Gate: `/squad-quality-gate` — cobertura ≥ 90% e mutation ≥ 80% **em domínio crítico** (não em todo o repo).

## 4. Testes Native/AOT e serverless

- **Native:** sempre testar o binário, nunca só o jar (reachability metadata falha só em runtime).
  Spring Boot: `mvn -Pnative test`; Quarkus: `@QuarkusIntegrationTest`.
- **AOT Cache/CDS:** smoke de startup no CI (`measure-startup.ps1` do lab) comparando cache vs sem cache.
- **Lambda:** SAM local + LocalStack p/ integração; validar hooks SnapStart (`afterRestore` recria pool
  JDBC) com teste dedicado; benchmark de cold start com versões publicadas (não `$LATEST`).

## 5. Performance em testes (não deixar a pipeline morrer)

- Parallelismo (JUnit parallel execution em classes independentes), cache de contexto
  (`spring.test.context.cache.pause`), Testcontainers reutilizados (`withReuse`), k6 em job separado
  do feedback de PR. Meta declarada: **feedback < 10 min para o fluxo feliz**.
