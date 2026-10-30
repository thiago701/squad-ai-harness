# Guia de ADR — Architecture Decision Records

> Toda decisão arquitetural relevante da Squad AI vira um **ADR versionado**. O objetivo não é cerimônia — é evitar que a mesma discussão se repita em 3 meses sem memória do **porquê**.

## Quando criar um ADR

Crie um ADR quando a decisão satisfaz pelo menos UM dos gatilhos:

- Escolha entre tecnologias com trade-off real (ex: SQS vs Kafka, Aurora vs DynamoDB, JWT vs sessão).
- Mudança que afeta **mais de um bounded context** ou camada.
- Desvio do stack padrão da squad (Java 25 + Spring Boot 4 + Aurora + Maven 4).
- Decisão irreversível em < 1 semana (schema, contrato público, formato de evento).
- Introdução de padrão que a squad adotará como default (ex: "todo endpoint público responde ProblemDetail RFC 9457").

**Não precisa ADR** quando: é uma preferência de nomenclatura, escolha local dentro de um use case, ou decisão reversível de baixo custo em < 1 dia.

## Onde ficam

```
.agent/skills/squad-ai/.antigravity/equipe/decisoes/
├── ADR-0001-cqrs-in-process-default.md
├── ADR-0002-aurora-pg-como-banco-default.md
├── ADR-0003-outbox-schema-canonico.md
└── README.md   ← índice numerado
```

Numeração: sequencial (0001, 0002...). **Status nunca é editado retroativamente** — uma decisão superada vira novo ADR com `Status: Accepted` e o anterior é marcado `Superseded by ADR-NNNN`.

## Template canônico

```markdown
# ADR-[NNNN]: [Título curto e decisivo, ex: "Aurora Serverless v2 para ambientes não-prod"]

**Status:**     Proposed | Accepted | Deprecated | Superseded by ADR-NNNN
**Data:**       YYYY-MM-DD
**Deciders:**   Tech Lead + agentes envolvidos (Arquiteto Minimalista, DevOps, ...)
**Contexto:**   Fase 2 (Design) | Fase 3 (Build) | Incidente | Refactor

## Contexto

Qual é a situação? Quais forças estão em jogo? Cite números sempre que possível:
volumetria, SLA alvo, budget, expertise do time. Evite filosofar — seja concreto.

Exemplos do que entra aqui:
- "Carga esperada: 500 RPS p95 < 200ms em horário comercial, < 10 RPS noite."
- "Equipe de 4 pessoas, 2 com experiência AWS, nenhuma com Kafka em prod."
- "Budget cloud: USD 3k/mês no primeiro ano."

## Decisão

Uma sentença direta. Sem hedging. O leitor deve saber **o que** foi decidido em 10s.

> "Adotamos Aurora Serverless v2 em dev/staging; Aurora provisioned em prod."

## Opções Consideradas

### Opção A — [Nome]

| Dimensão | Avaliação |
|---|---|
| Complexidade | Baixa / Média / Alta |
| Custo estimado | USD X/mês |
| Latência esperada | p95 Xms |
| Familiaridade do time | 0-5 |
| Reversibilidade | Horas / Dias / Semanas |

**Prós:** ...
**Contras:** ...

### Opção B — [Nome]
(mesmo formato)

### Opção C — Status quo / Não fazer nada
Sempre liste esta opção. Às vezes a resposta é "espera para quando tivermos dados".

## Análise de Trade-offs

Explicite o que está sendo trocado por quê. **Use a bússola P1 > P2 > P3:**

- P1 (Simplicidade): qual opção é mais fácil de entender e operar?
- P2 (Performance): qual atende o SLA com folga?
- P3 (Custo): qual tem o TCO (não só infra — inclui tempo de operação e debugging)?

Se a escolha viola P1 em favor de P2 ou P3, **justifique com dado observado, não com especulação**.

## Consequências

- **O que fica mais fácil** — ex: "Dev local fica 1:1 com produção via LocalStack."
- **O que fica mais difícil** — ex: "Rollback envolve downtime de 5min em caso de schema change."
- **O que precisamos revisitar** — ex: "Se carga dobrar até Q3, reavaliar mover para Aurora Global."

## Action Items

- [ ] @engenheiro-devops: configurar Aurora Serverless v2 em dev/staging via CDK.
- [ ] @especialista-banco: documentar migrations Flyway compatíveis com Serverless (sem DDL pesado em janela de produção).
- [ ] @tech-lead: revisitar ADR em 6 meses com métricas reais de custo e latência.

## Referências

- [[Aurora DSQL]] (alternativa descartada — ver Opção C)
- [[Transactional Outbox]] (depende desta decisão)
- Doc AWS: <link>
- PR/Issue: <link>
```

## Exemplo real — ADR-0001

```markdown
# ADR-0001: CQRS in-process como default (não CQRS distribuído)

**Status:**   Accepted
**Data:**     2026-04-20
**Deciders:** Tech Lead, Arquiteto Minimalista, Engenheiro Clean Architect
**Contexto:** Fase 2 (Design) do pedidos-api

## Contexto

A equipe precisa separar responsabilidades de escrita (Pedido aceita, valida, emite
evento) de leitura (relatórios e listagens que não podem impactar o caminho transacional).
Volumetria prevista: 200 RPS de write, 800 RPS de read, mesma base de dados Aurora
Postgres. Time de 5 pessoas. Nenhuma com experiência em Axon/Kafka em produção.

## Decisão

Adotamos **CQRS in-process**: Commands e Queries separados como classes distintas, no
mesmo processo Spring Boot, lendo/escrevendo a mesma base Aurora. Outbox Pattern para
propagar Domain Events a consumidores externos. Sem event store separado, sem read
model físico distinto nesta fase.

## Opções Consideradas

### Opção A — CQRS in-process (escolhida)

| Dimensão | Avaliação |
|---|---|
| Complexidade | Baixa — uma transação, uma base |
| Custo | Zero adicional |
| Latência | p95 < 100ms em leitura direta |
| Familiaridade | 5/5 — padrão JPA conhecido |
| Reversibilidade | Horas para evoluir para read model físico |

**Prós:** simples; testável com Testcontainers; sem acoplamento com infra extra.
**Contras:** leituras pesadas podem competir com writes sob pico.

### Opção B — CQRS com event store (Axon + projeção Kafka)

| Dimensão | Avaliação |
|---|---|
| Complexidade | Alta — nova infra, novo mental model |
| Custo | +USD 400/mês Kafka MSK |
| Familiaridade | 0/5 — ninguém usou Axon em prod |
| Reversibilidade | Semanas |

**Prós:** escalabilidade horizontal de reads; histórico imutável.
**Contras:** overengineering para volumetria atual; curva de aprendizado.

### Opção C — Status quo (sem separação)

**Prós:** zero esforço.
**Contras:** acoplamento impede evoluir read model quando precisar.

## Análise de Trade-offs

P1 (Simplicidade) favorece Opção A — mesmo padrão JPA, sem nova infra. P2 (Performance)
atende SLA com Aurora read replicas se necessário. P3 (Custo) favorece A com folga.
Opção B viola P1 sem justificativa em P2/P3 atuais.

## Consequências

- Mais fácil: onboarding, debugging local, testes com Testcontainers.
- Mais difícil: se picos > 2k RPS aparecerem, precisaremos projeção física (via Outbox → read model).
- Revisitar: quando tivermos dado observado de > 1k RPS sustentado em reads ou pressão real sobre writes.

## Action Items

- [ ] @especialista-banco: criar tabela `outbox_events` + migration V1__init.
- [ ] @engenheiro-clean-architect: organizar pacotes `commands/` e `queries/` separados.
- [ ] @tech-lead: revisitar em 2026-10 com métricas reais.

## Referências

- [[CQRS In-Process]]
- [[Transactional Outbox]]
- `references/cqrs-outbox.md`
```

## Exemplo expandido — ADR-0002 com Advogado do Diabo aplicado

> **Quando usar este exemplo como tutorial:** sempre que a proposta envolver **arquitetura complexa** (Kafka, microsserviços, event sourcing, CQRS distribuído, Kubernetes, multi-região ativo-ativo). O Advogado do Diabo (4 perguntas obrigatórias do `minimalist-toolkit.md` §57) **deve estar respondido por escrito dentro do ADR**, não em conversa de Slack.

```markdown
# ADR-0002: Manter SQS+SNS para messaging (não migrar para Kafka MSK)

**Status:**   Accepted
**Data:**     2026-04-29
**Deciders:** Tech Lead, Arquiteto Minimalista, Arquiteto Cloud AWS
**Contexto:** Fase 2 (Design) do pedidos-api — proposta originada por engenheiro pleno após bootcamp Confluent

## Contexto

Volumetria observada (últimos 90 dias em produção):
- **Throughput médio:** 180 msg/s (pico 420 msg/s em horário comercial)
- **Throughput projetado 12 meses (modelagem conservadora):** 600 msg/s pico
- **Tópicos lógicos:** 7 (pedido.criado, pedido.confirmado, pedido.cancelado, estoque.reservado, pagamento.aprovado, pagamento.rejeitado, notificacao.enviada)
- **Consumidores por tópico:** entre 1 e 3, todos in-house
- **Retenção exigida:** 7 dias (auditoria), reprocessamento manual raro
- **SLA p99 de propagação:** 500 ms (acordado com produto)

Time atual: 6 engenheiros backend, 1 SRE compartilhado com outro produto. Nenhum tem experiência operacional com Kafka/MSK. Stack atual: SQS FIFO + SNS Fan-out + DLQ por tópico, custando USD 87/mês.

Proposta apresentada: migrar para Kafka via Amazon MSK Provisioned (3 brokers kafka.m5.large, 3 AZs), motivada por "necessidade de event sourcing futuro" e "padrão de mercado para event-driven".

## Aplicação do Advogado do Diabo (4 perguntas obrigatórias)

### 1. Qual problema específico e atual isso resolve que SQS+SNS não resolve?

**Resposta exigida (numérica).** Auditados os tickets dos últimos 6 meses:
- Zero incidentes ligados a throughput de fila (utilização média 8% do limit nominal de SQS Standard).
- Zero incidentes ligados a ordering — onde houve necessidade, FIFO já entregou.
- Zero requisições de replay de eventos > 24h (DLQ + script ad-hoc atendeu 3 casos em 6 meses, total 47 minutos de trabalho).
- Tempo médio até consumo: p95 = 38 ms, p99 = 124 ms — **bem abaixo do SLA de 500 ms**.

**Conclusão:** nenhum problema atual. "Event sourcing futuro" é hipótese sem requisito formal. **Falha pergunta 1.**

### 2. O time está preparado para o custo operacional?

**Resposta exigida (lista verificável).**
- Observabilidade distribuída (traces cruzando broker → consumer): **não temos** — OTel está em piloto, sem métricas Kafka customizadas.
- Debugging de falhas assíncronas e parciais (rebalances, lag por consumer group): **time não tem playbook** — entrevistados 6/6 engenheiros não souberam diagnosticar `OffsetOutOfRangeException`.
- Deploy coordenado de contratos (schema registry, evolução compatível): **não temos** — payloads atuais são JSON livre.
- Operação 24/7 dos brokers (patching, expansão de partições, monitoria de under-replicated partitions): **SRE compartilhado, capacidade ~ 4h/semana**, insuficiente para MSK provisioned.

**Conclusão:** custo operacional **excede capacidade do time em 3 dimensões críticas**. **Falha pergunta 2.**

### 3. Você já tem esse problema hoje, ou está antecipando um cenário que pode nunca ocorrer?

**Resposta exigida (evidência ou previsão honesta).**
- Hoje: throughput = 5% do que SQS Standard suporta sem ajuste.
- Projeção 12 meses: 600 msg/s — ainda ~ 3% do limite SQS.
- Projeção otimista 36 meses: 3.000 msg/s — ainda dentro de SQS sem mudança arquitetural.
- O cenário onde Kafka seria justificado (>10k msg/s sustentado **ou** múltiplos consumers replay-heavy **ou** integração com pipeline analítico real-time): nenhum no roadmap atual nem nos OKRs do próximo ano.

**Conclusão:** YAGNI — antecipação de cenário **não suportado por dado nem por roadmap**. **Falha pergunta 3.**

### 4. Qual é o caminho de volta se essa escolha estiver errada?

**Resposta exigida (tempo concreto).**
- Migração SQS → Kafka: estimativa otimista 6-8 semanas (refactor de produtores/consumidores + observability + runbooks + treinamento). Custo MSK provisioned: USD ~430/mês (5× o atual) + custo de transferência inter-AZ.
- Migração Kafka → SQS (caminho de volta): mais difícil que a ida — código já estará acoplado a semântica de Kafka (offsets, partitions, consumer groups). Estimativa: **8-12 semanas** + perda de histórico em retenção.

**Conclusão:** caminho de volta **demoraria mais que a ida** e teria custo de oportunidade alto. **Falha pergunta 4.**

### Veredito do Advogado do Diabo

**4 de 4 perguntas falharam.** Pelo protocolo do `minimalist-toolkit.md` §77, a proposta **volta para o autor** como lição de casa. ADR é registrado com decisão **"manter SQS+SNS"** e proposta arquivada (não rejeitada — pode voltar com evidências novas).

## Decisão

Mantemos **SQS+SNS** como messaging default. Reavaliação obrigatória se **qualquer um** dos gatilhos abaixo for observado:
- Throughput sustentado > 5.000 msg/s por > 7 dias
- > 2 incidentes/trimestre relacionados a limites de SQS (visibility timeout, throughput, ordering)
- Demanda formal de pipeline analítico real-time com latência sub-segundo (não dashboard)
- Necessidade de replay > 7 dias com governança formal de schema

Até lá, qualquer proposta de Kafka volta a passar pelo Advogado do Diabo.

## Opções Consideradas

### Opção A — Manter SQS+SNS (escolhida)

| Dimensão | Avaliação |
|---|---|
| Complexidade | Baixa — managed AWS, zero brokers para operar |
| Custo | USD 87/mês (atual), projeção USD 290/mês em 12m |
| Latência | p99 124 ms (vs SLA 500 ms) — folga 4× |
| Familiaridade | 6/6 engenheiros |
| Reversibilidade | n/a (status quo) |

### Opção B — Amazon MSK Provisioned (rejeitada)

| Dimensão | Avaliação |
|---|---|
| Complexidade | Alta — 3 brokers, partitions, consumer groups, schema registry |
| Custo | USD ~430/mês + transferência inter-AZ + custo time SRE |
| Familiaridade | 0/6 engenheiros, 0 horas operação real |
| Reversibilidade | 8-12 semanas de refactor para voltar |

### Opção C — MSK Serverless (rejeitada com ressalvas)

Mesma falha nas perguntas 1, 2, 3. Reversibilidade um pouco melhor (sem brokers para operar) mas ainda exige schema/replay/ordering como em B. **Reabrir o ADR se Confluent Cloud lançar tier compatível e o gatilho de throughput for atingido.**

## Análise de Trade-offs

P1 (Simplicidade) favorece A com folga — managed, sem brokers, time já opera. P2 (Performance) atende SLA com margem 4×. P3 (Custo) favorece A — diferença anual de USD 4.116. Opção B viola P1 e P3 sem justificativa em P2 atual.

## Consequências

- **Mais fácil:** continuar entregando features, debug local com LocalStack, onboarding de novo dev (semana zero produtivo).
- **Mais difícil:** se o cenário > 10k msg/s materializar, a migração levará tempo. Compensa: **observabilidade real chega antes**, decisão será baseada em dado.
- **Revisitar:** sprint planning trimestral verifica se algum gatilho da seção Decisão foi atingido. Sem gatilho = sem ADR novo.

## Action Items

- [ ] @sre: configurar dashboards CloudWatch com utilização SQS/SNS por tópico (alerta em 60% da capacidade nominal).
- [ ] @arquiteto-minimalista: divulgar este ADR como exemplo canônico de Advogado do Diabo aplicado em onboarding.
- [ ] @tech-lead: revisitar em 2026-10 com métricas reais e checklist dos 4 gatilhos.

## Referências

- [[Advogado do Diabo]]
- [[Tres Prioridades Imutaveis]]
- `references/minimalist-toolkit.md` §57 (4 perguntas)
- `arquiteto-cloud-aws/SKILL.md` §SQS+SNS canônico
- ADR-0001 (CQRS in-process) — relacionado
```

**Lições deste ADR-0002 (use ao mentorar):**

- O Advogado do Diabo **não é cerimônia** — é gate. As 4 perguntas com numéricos travam decisão por currículo.
- "Status quo" (Opção C, ou neste caso **a própria escolhida**) sempre presente — sem isso o viés de ação fabrica complexidade.
- Decisão termina com **gatilhos quantitativos** para reabertura. Sem gatilho explícito, "vamos rever depois" vira procrastinação eterna (anti-padrão do `adr-guide.md` §187).
- **Falhar nas 4 perguntas é resultado válido**: ADR é registrado com decisão "não fazer", proposta volta como lição de casa, autor não é punido — o registro evita a próxima reabertura sem evidência nova.

---

## Sinais de saúde do backlog de ADRs

- ✅ ADRs lidos em retrospectivas — viram referência quando alguém questiona uma decisão.
- ✅ Superseded registrado — ninguém edita ADR antigo, decisão nova cria ADR novo apontando para o anterior.
- ✅ Números concretos no Contexto (volumetria, prazo, budget).
- ❌ ADR com "vamos ver" ou "talvez" no campo Decisão — indecisão virou documento.
- ❌ Mais de 3 ADRs abertos em Proposed por > 1 sprint — decisão virou procrastinação.
- ❌ ADR sem opção "status quo" — viés de ação, falta contraste honesto.

## Anti-padrões

- **ADR retroativo de fachada** — escrito só para cobrir uma decisão já implementada sem análise real. Melhor não ter.
- **ADR-enxaqueca** — todas as decisões viram ADR, o cofre incha e ninguém lê. Reserve para decisões que passam nos gatilhos acima.
- **ADR sem deciders** — quem bate o martelo? Se não está claro, a decisão não foi tomada.
- **Contexto filosófico** — "microsserviços são a arquitetura do futuro" não é contexto. Número de RPS, budget, tamanho do time: isso é contexto.

## Integração com as fases

| Fase | Quem propõe ADR | Quem decide |
|---|---|---|
| Discovery | Especificador (escopo de bounded context, eventos canônicos) | Tech Lead + Arquiteto Minimalista |
| Design | Arquitetos (stack, persistência, CQRS, IaC) | Tech Lead |
| Build | Clean Architect / Java25 (padrões de código que viram default) | Tech Lead |
| Review | Tech Lead (promoção de prática para default da squad) | Squad (consenso) |
| Deliver | DevOps (estratégia de rollout, feature flags) | Tech Lead + DevOps |

Em impasse: Tech Lead arbitra após 3 rodadas de argumento.

## Relacionadas

- [[Skill - Arquiteto Minimalista]]
- [[Skill - Tech Lead Review]]
- [[Tres Prioridades Imutaveis]]
- `references/minimalist-toolkit.md`
