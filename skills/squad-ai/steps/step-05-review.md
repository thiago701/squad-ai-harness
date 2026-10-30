# Step 5 — Review (Tech Lead)

## Fase 5 — REVIEW

### Objetivo

Revisão técnica final: aderência a DDD forte, CQRS+Outbox, Clean Architecture, Cloud Native e uso correto dos recursos modernos de Java 25 / Spring Boot 4 / Spring 7.

---

### 1. Ativar Tech Lead

```
Instruções para tech-lead-review:
  - Leia TODOS os artefatos das Fases 1 a 4
  - Aplique o Protocolo de Review em 5 passos
  - Verifique as 3 prioridades (P1 > P2 > P3) sequencialmente
  - Classifique cada achado com 🔴 / 🟡 / 🔵 / ⚪
  - Valide aderência DDD, CQRS, Clean Architecture, TDD
  - Consulte especialistas quando a dúvida for específica
```

---

### 2. Protocolo de Review — 5 Passos

#### Passo 1 — Contexto
- Qual requisito de negócio esta entrega atende?
- Quais bounded contexts foram tocados?
- Quais ADRs se aplicam?

#### Passo 2 — Verificação das 3 Prioridades

**P1 — Simplicidade**
- [ ] Qualquer engenheiro entende em 10 min?
- [ ] Nomes refletem linguagem ubíqua?
- [ ] Métodos ≤ 20 linhas? Classes ≤ 300?
- [ ] Máximo 2 níveis de if aninhado?
- [ ] Zero abstrações prematuras?
- [ ] Pattern Matching + Records reduzindo cerimônia onde faz sentido?

**P2 — Performance**
- [ ] SLAs cumpridos sob carga real (se aplicável)?
- [ ] I/O fora de loops?
- [ ] N+1 eliminado (teste com `@Sql` + contadores)?
- [ ] Virtual Threads habilitados onde o caminho é I/O-bound?
- [ ] Structured Concurrency em fan-out externo?
- [ ] Caching justificado (não especulativo)?

**P3 — Custo Cloud**
- [ ] Rightsized para carga atual (Aurora Serverless v2 quando irregular)?
- [ ] Pay-per-use onde tráfego é esparso?
- [ ] Recursos temporários com expiração?

#### Passo 3 — DDD (validação específica)
- [ ] Todo conceito de negócio tem Value Object correspondente (zero String/BigDecimal solto)?
- [ ] VOs validam no construtor (falha rápida, mensagem clara)?
- [ ] Aggregate Roots protegem invariantes — zero setter público?
- [ ] Mutações passam por métodos com nome do domínio (`confirmar()`, `adicionarItem()`)?
- [ ] Domain Events emitidos para toda mudança de estado relevante?
- [ ] Bounded contexts com pacotes separados e linguagens próprias?
- [ ] Linguagem ubíqua consistente entre código e glossário?

#### Passo 4 — Arquitetura
- [ ] Dependências na direção correta (ArchUnit verde)?
- [ ] Domínio sem imports de framework?
- [ ] Commands e Queries separados (CQRS honesto)?
- [ ] Outbox na mesma transação do command?
- [ ] Idempotência garantida em handlers?
- [ ] Contratos REST como ProblemDetail (RFC 9457)?
- [ ] Uso idiomático de features modernas:
    - [ ] Records para VOs/DTOs
    - [ ] Sealed types para estados finitos
    - [ ] `@HttpExchange` para clientes HTTP internos
    - [ ] `StructuredTaskScope` onde há fan-out
    - [ ] `ScopedValue` em vez de `ThreadLocal`

#### Passo 5 — TDD e Testes
- [ ] Histórico git reflete ciclos RED-GREEN-REFACTOR (commits pequenos)?
- [ ] Existem testes comentados? (zero tolerância)
- [ ] Testes validam comportamento (não implementação)?
- [ ] Testcontainers cobrindo repositórios, outbox, controllers?
- [ ] ArchUnit no CI com regras relevantes?
- [ ] Mocks usados com parcimônia (evitar mockar tudo)?

---

### 3. Classificação de Achados

| Símbolo | Significado | Ação |
|---|---|---|
| 🔴 | Bloqueante | Corrigir antes de aprovar |
| 🟡 | Importante | Corrigir antes de deliver |
| 🔵 | Melhoria | Tech debt rastreável |
| ⚪ | Preferência/estilo | Opcional |

---

### 4. Devolução a Especialista

Se o Tech Lead precisa de expertise específica:

```
DEVOLUÇÃO
  Destinatário: <agente>
  Componente:   <classe/módulo>
  Prioridade:   P1 | P2 | P3
  Pergunta:     <específica>
  Critério:     <o que a resposta precisa conter>
  Prazo:        <quando>
```

---

### 5. Definition of Done (DoD)

```
CÓDIGO
  □ CI green em todos os checks
  □ Mutation score ≥ 80% no domínio (se PIT habilitado)
  □ Cobertura ≥ 80% domínio, ≥ 60% geral
  □ Zero 🔴 / 🟡 abertos
  □ Code review aprovado

DDD
  □ Todo VO validado no construtor
  □ Todo Aggregate protege invariantes
  □ Todo Domain Event documentado
  □ Linguagem ubíqua consistente

CLEAN ARCHITECTURE
  □ ArchUnit verde
  □ domain/ sem dependências de framework
  □ Dependências apontam para dentro

CQRS + OUTBOX
  □ Commands e Queries separados
  □ Outbox na mesma transação do command
  □ Relay funcional em ambiente real
  □ Idempotência testada

TESTES
  □ Unitários: domínio puro, use cases com ports mockados
  □ Integração: Testcontainers Postgres real
  □ ArchUnit: regras de camadas
  □ Cenários BDD da Discovery cobertos

OPERAÇÃO
  □ Logs JSON estruturados com correlation-id e trace-id
  □ Actuator health (liveness + readiness) expostos
  □ Métricas Micrometer + OpenTelemetry configurados
  □ Rollback plan documentado (se alto risco)

SEGURANÇA
  □ Zero vulnerabilidades críticas (OWASP + CVEs)
  □ Zero secrets em código
  □ Bean Validation em DTOs + VO validando domínio
```

---

### 6. Entregas

`artefatos/fase-5-review/`:

```
├── relatorio-review.md       → Review completo
├── issues.md                 → Lista 🔴🟡🔵⚪
├── aderencia-ddd.md          → Checklist DDD por aggregate
├── aderencia-arquitetura.md  → ArchUnit + auditoria manual
├── aderencia-tdd.md          → Histórico git + métricas
├── tech-debt.md              → Itens 🔵 rastreáveis
└── dod-checklist.md          → DoD assinado
```

### 7. Gatekeeping Review → Deliver

```
□ Zero 🔴 e zero 🟡 em aberto
□ DoD completo
□ Aderência DDD, CQRS, Clean Architecture, TDD validada
□ Tech debt documentado como cards
```

### 8. Guias complementares (progressive disclosure)

Para revisão fora do ciclo canônico (hotfix, lib compartilhada, refactor pontual) ou para reforçar a lente de segurança/performance/corretude/manutenibilidade em PRs específicos, consulte:

- `../references/code-review-guide.md` — **4 lentes universais** (Segurança OWASP + Performance + Corretude + Manutenibilidade) com template de output de PR conciso e checklist de automatização (Semgrep + Dependency-Check). Usa junto com o Protocolo 5 Passos acima.
- `../references/adr-guide.md` — quando uma decisão emergir no review (ex: "vamos promover esta prática a default da squad"), formalize via ADR usando o template canônico + gatilhos + sinais de saúde.
- `../references/minimalist-toolkit.md` — se o review identifica overengineering, aplique as 4 perguntas do **Advogado do Diabo** e nomeie o antipadrão (Distributed Monolith, Abstração Prematura, Integração por Banco, etc.).
- `../references/debug-guide.md` — quando o PR vem para resolver bug que reproduziu em staging/prod: protocolo **Reproduzir → Isolar → Diagnosticar → Corrigir** garante que o fix tem teste RED→GREEN e hipótese escrita, não é palpite.
- `../references/tech-debt-guide.md` — a coluna 🔵 (Tech Debt) do output de PR vira card usando as **6 categorias canônicas** (Code / Architecture / Test / Dependency / Documentation / Infrastructure) com scoring `(Impact + Risk) × (6 − Effort)` para priorização comparável.
- `../references/testing-strategy.md` — se o PR introduz ou consome API com outros times, valide se há **contract test** (Spring Cloud Contract ou Pact). Pirâmide invertida em módulo novo é 🔴 bloqueante.

### 9. Próximo Step

`./step-06-deliver.md`
