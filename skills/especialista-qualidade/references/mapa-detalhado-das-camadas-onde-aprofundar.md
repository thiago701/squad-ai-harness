# especialista-qualidade · Mapa Detalhado das Camadas — Onde Aprofundar

> Reference da skill `especialista-qualidade` (movida da SKILL.md em 11/10/2026 — hub + references, I3). Carregue só quando a tarefa pedir este tema.

## Mapa Detalhado das Camadas — Onde Aprofundar

A SKILL.md é o **hub**: princípios + protocolo + ponteiros. O detalhamento operacional vive em `references/`. Carregue **apenas o que precisa** para a tarefa atual:

### Camada 1 — Testes Unitários
**Quando:** lógica pura, use cases com dependências mockadas, milissegundos.

**Conteúdo em `references/unit-tests.md`:**
- Estrutura de projeto canônica (Java/Kotlin/Python)
- Suíte unitária completa com os 8 eixos (Python pytest + parametrize)
- Property-based testing com Hypothesis (4 propriedades-tipo: invariante, comutatividade, idempotência, exceção esperada)
- Builders centralizados (Python e Kotlin) — Test Data Builder pattern
- Mutation testing com mutmut (Python) e PIT (Java)
- Classificação de mutantes — Aceitáveis vs Necessários
- Workflow de diagnóstico de mutantes sobreviventes

### Camada 2 — Testes de Integração
**Quando:** verificar contrato entre camadas com infraestrutura real (banco, fila, cache).

**Conteúdo em `references/integration-tests.md`:**
- Testcontainers com PostgreSQL e Kafka (Python async)
- Spring Boot 4 + `@ServiceConnection` (Kotlin)
- Testes de coerência DBML ↔ Persistência (mapper round-trip, Flyway, constraints, indexes, cascade)
- Testes de constraints DBML — DEFAULT, CHECK, UNIQUE, NOT NULL
- WireMock para gateways externos
- LocalStack para AWS (SQS, S3, DynamoDB)
- Concorrência real com OptimisticLockingFailureException

### Camada 3 — Testes Funcionais
**Quando:** comportamento pelo consumidor (cliente HTTP, API consumer, usuário final).

**Conteúdo em `references/functional-tests.md`:**
- Testes de API REST (Python httpx + pytest)
- BDD com Gherkin (Python pytest-bdd e Java Cucumber)
- Contract Testing com Pact (consumer/provider)
- E2E com Playwright (Java) — padrão canônico
- RestTestClient (Spring Boot 4)
- WireMock para integração com APIs externas

> **API REST black-box em Java (given/when/then): leia `references/rest-assured-api-testing.md`.** RestAssured em nível profissional — specs reutilizáveis (`RequestSpecBuilder`/`ResponseSpecBuilder`), validação por JSON Schema, serialização POJO, auth OAuth2/JWT, data-driven e `RestAssuredMockMvc` (slice Spring), com a **fronteira clara** vs `MockMvcTester`/`RestTestClient` (não duplicar caso). Exemplo executável (ciclo RED→GREEN) em `examples/rest-assured-professional/`.

> **Fronteira com `validador-navegador`.** Esta skill **escreve o teste durável** (código Playwright/E2E
> que roda no CI). A skill `validador-navegador` faz o oposto complementar: **dirige um browser ao vivo**
> como agente para validar um sistema em pé (smoke/jornada/console/rede/a11y ao vivo, veredito
> PRONTO/NÃO PRONTO) — sem escrever código. O ciclo saudável é **exploratório → confirmado → codificado**:
> o `validador-navegador` confirma o fluxo ao vivo e **entrega o roteiro** (passos, seletores, asserções
> observadas) para você codificá-lo como teste de regressão E2E. Todo bug que ele reproduz vira teste
> permanente aqui (8º eixo — REGRESSION).

### Camada 4 — Testes de Performance
**Quando:** SLAs como código, load/stress/spike/soak.

**Conteúdo em `references/performance-tests.md`:**
- 6 tipos de teste de performance (baseline, load, stress, spike, soak, concurrency)
- k6 com SLA como threshold (load + stress + spike scripts)
- Locust com lógica de negócio (Python)
- Gatling com DSL Kotlin
- Integração no pipeline CI/CD com gates automáticos

---
