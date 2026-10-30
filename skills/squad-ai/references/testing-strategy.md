# Testing Strategy — Pirâmide, Contract e Chaos

> Absorvido de `engineering:testing-strategy`. **Complementa** — não substitui — `testing-guide.md` (que cobre TDD RED→GREEN→REFACTOR, Mutation Testing e specimen `Pedido`). Foca no que falta: **pirâmide explícita**, **contract testing** para APIs consumidas por outros times, e **chaos engineering** para resiliência operacional.

> Para TDD, specimen e mutation, use `testing-guide.md`. Para escolher que testes adicionar a um design novo ou legado, use este guia.

## Pirâmide de Testes (referência canônica da squad)

```
          /\
         /E2E\        ~10%   (smoke + synthetic + user flows críticos)
        /------\
       /  INT   \     ~20%   (Testcontainers: Postgres, SQS, LocalStack)
      /----------\
     / COMPONENT  \   ~20%   (Spring slice: @WebMvcTest, @DataJpaTest)
    /--------------\
   /     UNIT       \ ~50%   (domain/ puro — sem Spring, sem IO)
  /------------------\
```

**Regra de ouro:** se um teste é lento (> 500 ms) ou flaky, ele pertence a uma camada superior **ou** precisa ser isolado. Unit test sempre é rápido e determinístico.

### Distribuição alvo

| Camada | Percentual | Tempo/teste | Escopo |
|---|---|---|---|
| Unit | 50% | ≤ 10 ms | Value Object, Aggregate Root, Invariantes, policy pure |
| Component (slice) | 20% | ≤ 100 ms | Controller + validação, Repository + mapeamento, Event handler |
| Integration | 20% | ≤ 3 s | Fluxo com Testcontainers (Postgres + SQS + LocalStack) |
| E2E / Synthetic | 10% | ≤ 30 s | User flow crítico em ambiente real (staging / canary) |

Desvios sinalizam dívida:
- Unit < 30% = domínio sem cobertura, sintoma de acoplamento.
- E2E > 20% = pirâmide invertida, CI lento e flaky.

## Estratégia por tipo de componente

### API REST consumida por outros times

**Obrigatório:** contract test (seção dedicada abaixo).
**Unit:** validators, mappers, policies.
**Component:** `@WebMvcTest` com `MockMvc` + `ProblemDetail` asserts.
**Integration:** endpoint completo com `@SpringBootTest` + Testcontainers Postgres.
**Synthetic:** CloudWatch Synthetics ou Playwright headless rodando smoke test a cada 5 min.

### Consumer de fila (SQS, Kafka)

**Unit:** handler puro com input deserializado.
**Component:** `@SqsListenerTest` ou equivalente com mensagem exemplo.
**Integration:** producer → SQS LocalStack → consumer real → assert no Postgres.
**Idempotência:** 2 testes explícitos — "mensagem duplicada é absorvida" + "mensagem dead-lettered vira alerta".

### Background job / scheduler

**Unit:** função pura que calcula o que fazer.
**Component:** `@SchedulerLock` test + time travel (`Clock` injetável).
**Integration:** roda o job real em Testcontainers, assert side effects.

### Integração com provedor externo (Bedrock, Stripe)

**Unit:** mappers, retry policy (com `Clock` mockado).
**Component:** `@HttpExchange` com WireMock respondendo cenários (200, 429, 5xx, timeout).
**Contract test:** schema do provedor (snapshot do OpenAPI deles; regressão se mudar).
**Chaos:** simular 429 por 5 min — assert que circuit breaker abre e serviço degrada graciosamente.

---

## Contract Testing

**Por que:** API sua tem consumers → mudança sua quebra eles. Unit test não protege.

### Ferramentas default

- **Spring Cloud Contract** (produtor define contrato, consumer consome stub gerado).
- **Pact** (consumer define expectativa, produtor valida).

**Recomendação da squad:** Spring Cloud Contract quando o produtor tem ≥ 2 consumers conhecidos e internos; Pact quando consumers são externos ou desconhecidos.

### Fluxo canônico (Spring Cloud Contract)

1. **Produtor** escreve contrato em `src/test/resources/contracts/<endpoint>.yml` ou `.groovy`.
2. CI do produtor gera **stub jar** + valida que API real cumpre o contrato.
3. Stub jar é publicado em repositório Maven interno.
4. **Consumer** adiciona `@AutoConfigureStubRunner` apontando para o stub — testa contra o mesmo contrato.
5. Qualquer alteração no contrato **quebra um dos lados** em CI — negociação forçada.

### Anti-padrões

- **Contract test só no produtor** — consumer usa mock inventado, quebra em prod.
- **Contrato como documentação pós-fato** — escrito depois do código, vira teatro.
- **Breaking change sem bump de versão** — a ação é quebrar deliberadamente, não sutilmente.

---

## Chaos Engineering

**Por que:** testes normais validam caminho feliz; prod tem caminhos infelizes que nunca foram exercitados.

### Escopo apropriado

A squad **não** adota Chaos Monkey full em ambiente pré-produção como default. Use chaos engineering quando:
- Sistema é SEV1-crítico (outage = perda direta > 6 dígitos).
- Dependência externa instável já causou incidente 2+ vezes.
- Recém-adotou padrão novo (circuit breaker, fallback, read-only mode) — precisa validar.

### Experimentos úteis (ordem crescente de disrupção)

1. **Latency injection** — adicionar 200ms artificialmente em chamada ao Bedrock. Observar p95 total + SLO. Executado em staging.
2. **Error injection** — forçar 429 / 5xx por janela de 2 min. Validar circuit breaker abrindo + fallback.
3. **Dependency outage** — derrubar stub local do provedor externo. Validar graceful degradation (read-only? cache servindo stale? mensagem amigável?).
4. **Instance kill** — matar 1 task ECS durante load test. Validar que ALB drena, graceful shutdown finaliza inflight, traffic absorvido por outras tasks.
5. **AZ isolation** — bloquear tráfego a 1 AZ (via security group). Validar que Aurora multi-AZ e ECS multi-AZ fazem o failover.

### Ferramentas default

- **AWS Fault Injection Simulator (FIS)** — integrado com ECS, Aurora, Lambda.
- **Toxiproxy** — latency/error injection por proxy em teste de integração.
- **Chaos Monkey for Spring Boot** — injeção dentro do próprio app (latência, exceção, saturação de memória).

### Regras operacionais

- Experimento chaos **tem janela anunciada** (canal do time avisado), blast radius limitado, critério de aborto explícito.
- **Nunca em prod** sem dry-run em staging passando há ≥ 2 semanas.
- Resultado do experimento vira **action item** (alerta novo? runbook? circuit breaker?) — caso contrário, exercício foi teatro.

---

## Checklist de Test Plan por feature nova

Ao fechar discovery (`step-02`), documente no ticket da feature:

- [ ] Unit tests — quais invariantes? quais VOs? quais policies?
- [ ] Component tests — quais slices? (Web? Data? Event?)
- [ ] Integration tests — Testcontainers habilitado (Postgres default, SQS se aplicável)?
- [ ] Contract test — produtor ou consumer? ferramenta?
- [ ] Idempotência — 2 casos (dedupe + dead-letter)?
- [ ] Chaos — algum cenário específico a exercitar?
- [ ] Synthetic — user flow crítico coberto?
- [ ] Mutation — specimen identificado? meta de score declarada?
- [ ] Coverage — meta declarada (domain ≥ 90%, geral ≥ 80%)?

## Sinais de saúde

- ✅ Pirâmide visualmente próxima à ideal (rodar `jacoco` + classificar testes por tempo).
- ✅ CI completo ≤ 10 min — sinal de unit-heavy.
- ✅ Contract test quebra em CI **antes** do deploy em cada lado.
- ✅ Chaos injection rodou ≥ 1× por trimestre em cada serviço SEV1.
- ❌ Pirâmide invertida — CI > 30 min + flaky.
- ❌ Unit test que sobe Spring — sinal de dependência no lugar errado.

## Anti-padrões

- **"Escrevo unit, test integration faz no final"** — test integration no final = test integration que nunca vem.
- **Coverage % como meta única** — 95% de linhas com 40% de mutação é autoengano.
- **Teste flaky ignorado** — "é flaky, roda de novo". Ou conserta ou remove.
- **Chaos porque é cool** — sem blast radius, sem aborto, sem action item — é só disrupção.
- **Contract test manual** — mock escrito à mão = documentação desatualizada em 1 sprint.

## Relacionadas

- `testing-guide.md` — TDD, specimen, mutation testing, ArchUnit (fonte canônica do como escrever).
- [[Deploy Checklist]] — smoke tests são E2E no topo da pirâmide.
- [[Incident Response]] — chaos bem rodado reduz duração de incidentes reais.
- [[Advogado do Diabo]] — "quanto de teste é suficiente?" deve passar pelas 4 perguntas.
- `squad-ai/steps/step-03-build.md` e `step-04-test.md`

#conceito #testing #pyramid #contract #chaos #squad-ai #v8-3
