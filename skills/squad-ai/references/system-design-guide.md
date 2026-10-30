# System Design — Framework de 5 Passos

> Absorvido de `engineering:system-design`. Complementa [[Minimalist Toolkit]] e `clean-architecture-java25.md` fornecendo um **framework estruturado de 5 passos** para discovery/design de sistemas e APIs. Usado em `step-02-discovery-design.md` antes de começar a construir.

## Quando usar

- Design novo: feature que cria novo Bounded Context ou Aggregate Root.
- Redesign: quando complexidade acidental acumulou e o módulo precisa ser repensado.
- Integração com sistema externo (API pública, banco, fila, provedor).
- Avaliação de proposta de terceiros ("o time X propôs Y, faz sentido?").

## Os 5 Passos

```
1. REQUIREMENTS  → 2. HIGH-LEVEL  → 3. DEEP DIVE  → 4. SCALE & RELIABILITY  → 5. TRADE-OFFS
```

Resistir à tentação de pular para "Deep Dive" antes de fechar os Requirements. 80% dos erros arquiteturais vêm de requisito mal entendido, não de escolha ruim de tecnologia.

---

## Passo 1 — Requirements

### Funcionais (o que o sistema faz)

- Quais **casos de uso** primários? Escreva 3-5 em linguagem ubíqua (sem jargão técnico).
- Quais são os **atores** (usuários humanos, sistemas consumidores, sistemas produtores)?
- Quais **invariantes de domínio** (regras que nunca podem ser violadas, ver [[Invariante de Dominio]])?
- Quais **entradas e saídas** canônicas (formatos, volumes esperados)?

### Não-funcionais (como o sistema se comporta)

| Dimensão | Pergunta | Exemplo |
|---|---|---|
| Escala | Quantos usuários / requests / eventos por unidade de tempo? | 2k RPS pico, 500 RPS médio |
| Latência | p50, p95, p99 alvo por endpoint? | /checkout p95 ≤ 300ms |
| Disponibilidade | Qual SLA? | 99.9% mensal = 43 min/mês de downtime tolerável |
| Durabilidade | Tolera perda de 1 segundo? 1 evento? 0? | Pedido confirmado = zero perda |
| Consistência | Forte, eventual, causal? | Saldo = forte; feed = eventual (≤ 30s) |
| Segurança | Quem pode ler/escrever? PII? Audit trail? | Ver `code-review-guide.md` Lente 1 |
| Custo | Budget mensal + custo por transação? | ≤ US$ 0,01/pedido em infra |

**Critério de saída do Passo 1:** cada dimensão tem **um número**, não um adjetivo. "Rápido" e "barato" não passam.

---

## Passo 2 — High-Level Design

Foco: caixas e setas. **Uma tela.** Se não cabe, está cedo demais para o Passo 3.

**Componentes canônicos a nomear:**
- **Clients** (browser, mobile, outro serviço, webhook).
- **Entrypoints** (ALB/NLB, API Gateway, SQS consumer, Scheduler).
- **Compute** (ECS Fargate / Lambda / EKS — default **ECS**, ver heurísticas em `minimalist-toolkit.md`).
- **Data stores** (Aurora PostgreSQL default, S3, DynamoDB — motivado pelo requisito, não pelo modismo).
- **Queue / Bus** (SQS default, Kafka só se streaming stateful — [[Advogado do Diabo]] pergunta 1).
- **Cache** (Caffeine in-process default, Redis só com TTL fino / pub-sub).
- **External providers** (Bedrock, Stripe, sendgrid, etc.).

**Desenhar em Structurizr DSL** — ver `documentation-guide.md` §Architecture. Versionado no repo, gera C4 níveis 1-3.

**Critério de saída do Passo 2:** novo engenheiro entende o sistema olhando o diagrama por ≤ 5 min.

---

## Passo 3 — Deep Dive

Agora sim, detalhes. Escolher **2-3 partes críticas** (geralmente a dobradiça do domínio + o hot path).

### Para cada parte, descrever:

**a) Modelo de dados**
- Tabelas / coleções / streams.
- Chave primária, índices, constraints.
- Expansão prevista (quantos registros em 1 ano? 3 anos?).
- Política de retenção (ver `cloud-native-aws.md`).

**b) Contrato de API**
- Método + rota + request/response schema.
- Auth (token, scopes, PDP/PEP).
- Error model ([[ProblemDetail]] RFC 9457).
- Rate limit + idempotência ([[Idempotencia de Consumer]]).
- Versionamento (URL vs header — default URL).

**c) Fluxo (sequence)**
- Quem chama quem.
- Transação do banco vs transação de negócio (Saga).
- Onde o [[Transactional Outbox]] publica.
- Onde a idempotência é aplicada.

**d) Estado e ciclo de vida**
- Máquina de estados do Aggregate Root.
- Invariantes por transição (I1, I2, ... — ver `ddd-guide.md`).

---

## Passo 4 — Scale & Reliability

**Perguntas operacionais:**

1. **Load estimation.** RPS × tamanho médio de request × tempo médio de resposta → throughput por instância → número mínimo de instâncias + headroom.
2. **Hot spots.** Qual endpoint/query vai dominar custo/latência? Endpoint p95 = sum(p95 das dependências) + overhead.
3. **Failure modes.** O que acontece se o Aurora cair 2 min? Se o Bedrock retornar 429 por 5 min? Se o SQS ficar sem consumers? Cada resposta deve ser **ação concreta**: retry com backoff, circuit breaker, dead-letter queue, read-only mode.
4. **Backpressure.** Quem protege quem? Rate limit na entrada, `maxConcurrency` nas saídas, queue bounded.
5. **Observabilidade.** Quais SLIs (latency, error_rate, saturation) viram SLOs (99.9%, p95 300ms) e quais viram alertas?
6. **Capacity headroom.** Operar em 40-60% da capacidade. Acima disso, picos derrubam.

**Padrões default:**
- Virtual Threads para I/O-bound (default SB4).
- StructuredTaskScope para fan-out externo.
- Circuit Breaker (Resilience4j) em cada integração externa.
- Health probes (`/actuator/health/readiness` e `liveness`) distintos.
- Graceful shutdown com `server.shutdown=graceful`.

---

## Passo 5 — Trade-offs (explícitos)

**Templado para registrar em [[ADR Template]]:**

| Opção | Complexidade | Custo | Latência | Familiaridade | Reversibilidade |
|---|---|---|---|---|---|
| A — proposta | M | $$ | p95 300ms | Alta | 1 semana |
| B — alternativa | H | $$$ | p95 150ms | Baixa | 2 meses |
| **C — status quo** | L | $ | p95 800ms | N/A | 0 |

**Regra:** Opção C (não fazer nada) **sempre** na tabela. Decisão é contra ela.

**Aplicar [[Advogado do Diabo]] 4 perguntas:**
1. Qual problema específico A resolve que C não resolve? (Número, não adjetivo.)
2. Time está preparado para o custo operacional de A?
3. Já tem esse problema hoje ou está antecipando?
4. Qual o caminho de volta se A falhar?

**Registrar trade-off explícito:** "A otimiza latência ao custo de familiaridade e custo. Aceitamos X porque Y (dado observado Z)."

---

## Template de Output (entrega do Passo final)

```markdown
# System Design — [Nome do sistema/feature]

## 1. Requirements
### Funcionais
- ...
### Não-funcionais
| Dimensão | Alvo | Fonte |
| ... | ... | ... |

## 2. High-Level
[Diagrama C4 Level 2 em Structurizr DSL — link]

## 3. Deep Dive
### Componente crítico A
- Modelo de dados: ...
- API: ...
- Fluxo: ...
- Estado: ...

## 4. Scale & Reliability
- Load estimation: ...
- Failure modes: tabela ação por falha
- SLIs → SLOs → Alertas: tabela
- Observabilidade: OTel / X-Ray / CloudWatch

## 5. Trade-offs
[Tabela dimensional com Opção C]
[4 perguntas do Advogado do Diabo respondidas]

## Decisão & ADR
Link para ADR-NNNN.

## Action Items
| # | Ação | Owner | Prazo |
```

## Sinais de saúde

- ✅ Requisitos têm números, não adjetivos.
- ✅ Diagrama high-level cabe em uma tela.
- ✅ Trade-offs incluem status quo.
- ✅ ADR formalizado após o design.
- ❌ Deep dive sem high-level — decisões descontextualizadas.
- ❌ Requisitos só funcionais — não-funcionais vão causar surpresa em produção.

## Anti-padrões

- **"Design por intuição"** — "eu acho que Kafka aqui". Acredite após os 5 passos, não antes.
- **Requirements aceitos de boca** — sem número, requisito é sonho.
- **Deep dive em tudo** — foque em 2-3 partes críticas, o resto é commodity.
- **Trade-off implícito** — "faremos A" sem mostrar B e C. Ninguém volta para questionar depois.
- **Resistir a revisitar** — design vira dívida se não é revisitado quando premissa muda.

## Relacionadas

- [[Minimalist Toolkit]] — defaults e heurísticas rápidas; aplicar antes de ampliar.
- [[ADR Template]] — registra a decisão final com Opção C obrigatória.
- [[Advogado do Diabo]] — 4 perguntas bloqueantes no Passo 5.
- [[Clean Architecture Java25]] — onde o design vira código.
- `squad-ai/steps/step-02-discovery-design.md`
- `squad-ai/references/cqrs-outbox.md`

#conceito #system-design #arquitetura #squad-ai #v8-3
