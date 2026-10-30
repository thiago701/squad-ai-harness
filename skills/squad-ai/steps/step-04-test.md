# Step 4 — Test (Ampliação)

## Fase 4 — TEST

### Objetivo

Validar dimensões que o TDD unitário da Fase 3 não cobre: integração entre componentes reais, comportamento sob carga, segurança.

**Premissa:** o código chega com testes unitários sólidos e testes de integração base (Testcontainers). A Fase 4 **estende** — não substitui.

---

### 1. Ativar Especialistas

- `especialista-qualidade` — lidera, completa a pirâmide
- `engenheiro-seguranca` — auditoria OWASP
- `arquiteto-performance` — SLAs sob carga (se NFR exige)

---

### 2. Pirâmide de Testes (meta)

```
Cobertura por tipo de teste:

  60% — Unitários         (já base do TDD; completar edge cases)
  20% — Integração        (Testcontainers; write + read + outbox + migrations)
  15% — Funcionais/BDD    (cenários da Discovery end-to-end contra app real)
   5% — E2E               (só fluxos críticos de produção)
```

Detalhes e exemplos em `references/testing-guide.md`.

---

### 3. Testes Obrigatórios (mínimo de entrega)

#### 3.1 Integração — Testcontainers

```
□ Teste de repositório JPA com Postgres 16 real
   - save + findById round-trip de TODO aggregate (mapper sem perda)
   - queries complexas validadas (not only unit tests on mocks)

□ Teste de Outbox
   - commit do command → row em outbox_events
   - relay consome e marca processed_at
   - idempotência: reprocessar não duplica efeito

□ Teste de Flyway
   - migrations aplicam em banco vazio sem erro
   - schema final coerente com JPA entities (schema validation)

□ Teste de Controller REST
   - @SpringBootTest + MockMvc ou WebTestClient
   - validação de DTOs (Bean Validation)
   - GlobalExceptionHandler retorna ProblemDetail (RFC 9457)

□ Teste de Virtual Threads
   - verifica que endpoint roda em virtual thread quando habilitado
```

#### 3.2 Arquitetura — ArchUnit (CI fail-fast)

```java
@ArchTest
static final ArchRule dominioNaoDependeDeFramework =
    noClasses().that().resideInAPackage("..domain..")
        .should().dependOnClassesThat().resideInAnyPackage(
            "jakarta..", "org.springframework..", "org.hibernate..",
            "com.fasterxml.jackson.."
        );

@ArchTest
static final ArchRule applicationSoDependeDeDomainEPorts =
    classes().that().resideInAPackage("..application..")
        .should().onlyDependOnClassesThat()
        .resideInAnyPackage("..application..", "..domain..", "java..", "javax.annotation..");

@ArchTest
static final ArchRule naoUsarThreadLocal =
    noClasses().should().dependOnClassesThat().haveFullyQualifiedName("java.lang.ThreadLocal");
```

---

### 4. Testes Recomendados (documentar escolha via ADR)

Quando justificado pelo contexto:

- **Mutation testing (PIT)** — score ≥ 80% em classes de domínio. Detecta testes fracos.
- **Property-based (jqwik)** — regras de negócio com alto espaço de entradas (cálculos, validadores).
- **Contract testing (Pact / Spring Cloud Contract)** — se há integrações entre serviços.
- **Performance (k6 / Gatling / JMH)** — NFRs com SLAs p95/p99 rigorosos.
- **E2E (RestAssured / Karate)** — fluxos críticos de produção.

Não adicione todos automaticamente. Adicione **o que agrega valor** para o contexto; registre a decisão em ADR.

---

### 5. Segurança — OWASP Top 10

O `engenheiro-seguranca` executa checklist:

```
□ A01 Broken Access Control      — Spring Security @PreAuthorize, teste de autorização
□ A02 Cryptographic Failures      — senhas com Argon2/BCrypt, TLS obrigatório
□ A03 Injection                   — JPA parametrizado, validação Bean Validation
□ A04 Insecure Design             — threat modeling da Discovery
□ A05 Security Misconfiguration   — Spring Security headers, CORS restrito
□ A06 Vulnerable Components       — mvn dependency-check, Renovate
□ A07 Auth Failures               — lockout, MFA se aplicável, JWT com expiração curta
□ A08 Data Integrity Failures     — assinaturas de artefatos, SBOM
□ A09 Logging & Monitoring        — logs JSON estruturados com correlation-id
□ A10 SSRF                        — allowlist de URLs externos
```

Adicional:
```
□ Zero secrets em código (TruffleHog / gitleaks no CI)
□ Rate limiting onde aplicável (Bucket4j ou Spring Cloud Gateway)
□ Input validation em TODAS as entradas (Bean Validation + VO validando no domínio)
```

---

### 6. Performance (se NFRs exigem)

`arquiteto-performance` conduz:

```
□ Load test: carga normal por 10min → p95/p99 dentro do SLA
□ Stress test: 2x carga esperada → degradação graceful
□ Spike test: pico repentino → recuperação em < 30s
□ Soak test: carga normal por 1h → sem memory leak

Ferramentas: k6 (preferido), Gatling, JMH para benchmarks de código quente.
```

---

### 7. Entregas

`artefatos/fase-4-test/`:

```
├── relatorio-integracao.md      → Testcontainers: cobertura e resultados
├── relatorio-funcionais.md      → BDD end-to-end
├── relatorio-archunit.md        → Regras e violações (zero)
├── relatorio-seguranca.md       → OWASP + CVEs + secrets
├── relatorio-performance.md     → Load/stress/spike (se aplicável)
├── relatorio-mutation.md        → Score (se aplicável)
└── cobertura-final.md           → JaCoCo consolidado
```

### 8. Gatekeeping Test → Review

```
CHECKLIST
  □ Pirâmide respeitada (60/20/15/5)
  □ Zero vulnerabilidades críticas OWASP
  □ Zero CVEs de alta severidade em dependências
  □ SLAs p95/p99 validados (se NFR exige)
  □ Zero secrets no código (gitleaks)
  □ Cenários BDD da Discovery todos cobertos
  □ Testcontainers roda no CI sem flakiness
  □ ArchUnit sem violações
```

### 9. Próximo Step

`./step-05-review.md`
