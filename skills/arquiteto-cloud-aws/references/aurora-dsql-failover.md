# Aurora DSQL — Runbook Multi-Região Ativo-Ativo + Failover Drill

> Absorvido em v8.4 para fechar gap OBJ-4 (AWS Specialist). A squad já mencionava Aurora DSQL como default 2026 para consistência forte global; faltava o **runbook operacional** para DR regional + o **drill trimestral** que valida a prática.
>
> **Escopo:** apenas Aurora DSQL (PostgreSQL serverless multi-região ativo-ativo). Para Aurora tradicional (primary+replicas) seguir runbook genérico multi-AZ; este arquivo não cobre esse caso.

## Quando abrir este runbook

- **Drill trimestral** — obrigatório, parte da cadência de Game Days.
- **Incidente real** — AZ ou região inteira degradada, suspeita de split-brain lógico, latência p99 cross-região > SLO.
- **Onboarding** — todo SRE/plantonista precisa ter operado o failover em drill antes do primeiro plantão.
- **Mudança estrutural** — nova região adicionada, nova aplicação consumindo o cluster DSQL.

---

## Modelo mental mínimo

Aurora DSQL resolve **consistência forte multi-região sem primary designado**. Sem primary = failover não é "promover replica"; é **parar de rotear tráfego para a região problemática** e deixar as demais absorverem. Linhas não são reescritas; o protocolo interno (sync-on-commit via coordenação distribuída) garante que qualquer região retorna o último valor confirmado.

**Consequências práticas:**

- "Failover" aqui = **rotar tráfego** (DNS/ALB/ApiGateway), não promover database.
- **Latência de commit** sobe durante falha parcial — não há como evitar: consistência forte global cobra. Monitorar p95 commit antes de confundir lentidão com falha real.
- **Write-write conflict é resolvido pelo DSQL** (optimistic concurrency), não pela aplicação. App vê `40001 serialization_failure` e deve retry com backoff.

---

## Topologia canônica (default da squad)

```
  us-east-1 ─┐
             ├── Aurora DSQL Cluster (multi-região ativo-ativo)
  us-west-2 ─┤       (endpoint único por região)
             │
  eu-west-1 ─┘

  Route 53 (latency-based) → ALB regional → ECS/Lambda regional → DSQL endpoint regional
```

**Regiões default para a Squad AI:**
- **us-east-1** — primária histórica (CAPS, tráfego, preço).
- **us-west-2** — ativo secundário para disaster recovery continental.
- **eu-west-1** — ativo terceiro por conformidade GDPR / latência EMEA.

Trocar essas regiões justifica **ADR**.

---

## Pré-requisitos do cluster (gate anti-"drill-que-não-funciona")

Antes de o drill fazer sentido, o cluster precisa:

- [ ] **3 regiões ativas** (não 2 — 2 ativos + 1 standby força latência de quórum assimétrica).
- [ ] **Quorum endpoint configurado** — cada região tem endpoint local + pode ler de outra região em caso de falha local.
- [ ] **CloudWatch cross-region dashboards** com p50/p95/p99 de commit por região.
- [ ] **Alarme**: `CommitLatencyP95 > 100ms for 3 datapoints` → SEV2 automático.
- [ ] **Alarme**: `SerializationFailureRate > 0.5% for 5 min` → SEV3 (pode ser sintoma de hotspot, não de falha regional).
- [ ] **Route 53 health checks** em `/actuator/health/readiness` de cada região (checagem L7, não só TCP).
- [ ] **Connection pool HikariCP** com `connectionTimeout=3s`, `validationTimeout=2s` (não herdar default 30s — vira cascata lenta).
- [ ] **SDK v2 com retry policy** configurado: `RetryMode.STANDARD` + `maxAttempts=4` + backoff exponencial jitter.
- [ ] **Aplicação idempotente** (Pilar 4 da Squad: CQRS + Outbox + Idempotência já cobre).
- [ ] **Feature flag de kill switch regional** — `region.<name>.enabled=false` (Unleash/LaunchDarkly) para tirar região sem mexer em DNS.

Gate falhou = drill adiado + card BAIXA em `tech-debt-guide.md` para corrigir.

---

## Drill trimestral — protocolo

### Preparação (dia -7)

- [ ] Notificar stakeholders (squad + produto + suporte) — data + janela + região alvo.
- [ ] Escolher **região alvo** por rotação: drill N em us-east-1, N+1 em us-west-2, N+2 em eu-west-1. Nunca drillar sempre a mesma.
- [ ] Alinhar com on-call: **drill não é surpresa**. Surpresa é para security tabletop (T3), não para DR físico.
- [ ] Revisar este runbook em equipe (10 min).

### D-0 — execução (duração 45-60 min)

**1. Baseline (5 min)**
- Printar CloudWatch dashboard: p95 commit por região + error rate + throughput.
- Confirmar que todas 3 regiões estão saudáveis.
- Definir **critério de rollback** antecipado: "abortar se error_rate total > 3% ou p95 global > 800ms por 2 min".

**2. Injeção (varia pelo cenário)**

| Cenário | Comando |
|---------|---------|
| **A — Kill switch regional** (preferido, reversível) | Feature flag `region.us-east-1.enabled=false` via UI |
| **B — AZ isolation simulada** | AWS FIS experiment template `DSQL-AZ-Isolation-us-east-1a` |
| **C — Região inteira degradada** | Route 53 health check forçado para `unhealthy` na região alvo |
| **D — Latência injetada** (soft) | AWS FIS `inject-api-latency` 500ms no endpoint DSQL us-east-1 |

Cenários **A** e **D** no primeiro drill do ano; **B** e **C** no segundo semestre.

**3. Observação (15-25 min)**

Time divide em papéis — IC, Tech Lead, Scribe — mesmo em drill. Pratica o workflow do `incident-response.md`.

- [ ] Route 53 recalculou e removeu região degradada em ≤ 90s?
- [ ] Tráfego migrou para regiões remanescentes em ≤ 120s?
- [ ] Nenhum erro visível ao cliente em feature-crítica idempotente (leituras) durante a migração?
- [ ] Writes in-flight na região degradada **não sumiram** (confirmação via query cross-região após 30s)?
- [ ] p95 de commit global voltou a baseline em ≤ 5 min? (Subida temporária é esperada: ≤ 2× baseline durante transição.)
- [ ] Serialization failures subiram temporariamente (esperado) mas retry automático reabsorveu?

**4. Recuperação (10 min)**

- Reverter injeção (flag ON, FIS stop, Route 53 force healthy).
- Confirmar que tráfego voltou a distribuir nas 3 regiões em ≤ 2 min.
- Confirmar p95 voltou a baseline.

**5. Debrief (15 min)**

Usar seção "Debrief" do tabletop exercise em `incident-response.md`. Saídas concretas:

- Action items com dono + prazo (entra no `tech-debt-guide.md` se for estrutural).
- Runbook atualizado **na hora** com tudo que não estava escrito mas foi necessário.
- Log do drill em `.reviews/failover-log.md` (ver §Log abaixo).

---

## Incidente real — diferenças vs drill

1. **Skip preparação.** Workflow é `TRIAGE → COMMUNICATE → MITIGATE → POSTMORTEM` do `incident-response.md`.
2. **Prioridade de mitigação** é **a mesma do drill**: kill switch regional **antes** de Route 53 manual, Route 53 manual **antes** de alteração no cluster DSQL.
3. **Nunca** executar `ALTER CLUSTER` ou `DROP REGION` durante SEV. Apenas rotear tráfego.
4. Se após 10 min o failover regional não normalizar: SEV1 → envolver AWS Support (Enterprise tier). Não há hotfix em DSQL; o contrato é com a AWS.
5. Postmortem obrigatório em ≤ 3 dias úteis mesmo que resolução tenha sido "AWS corrigiu sozinho".

---

## Anti-padrões

- **"Ativo-ativo com primary de papel"** — time escreve só em us-east-1 "por hábito" mesmo com cluster ativo-ativo. Resultado: primeiro failover real é o primeiro write multi-região. Detectar via `SELECT region FROM pg_stat_activity` e forçar traffic split na origem.
- **Retry infinito em serialization_failure** — 3 retries com backoff jitter, depois 5xx para o cliente. Consumer idempotente lida.
- **Connection pool gigante esperando que "pool grande = resiliência"** — Aurora DSQL com connection pool > CPU do app = pin + contention. HikariCP `maximumPoolSize=10` por instância é ponto de partida; medir.
- **Drill só em produção** — sempre drillar antes em ambiente `stage` com carga sintética. Primeiro drill em prod = drill teatro.
- **Ignorar write amplification em failover parcial** — durante migração de tráfego, 2× volume de commits na região saudável por alguns segundos. Capacity headroom 40-60% (§System Design `scale-reliability`) absorve.

---

## Log de drills (obrigatório)

Todo drill alimenta `.reviews/failover-log.md` com:

```markdown
## DSQL Drill YYYY-MM-DD

- **Cenário:** A/B/C/D
- **Região alvo:** us-east-1
- **Duração total:** 42 min
- **Resultado:** PASS / PASS-com-ressalvas / FAIL
- **Tempo até Route 53 remover região:** 73s ✅
- **Tempo até tráfego estabilizar nas 2 regiões restantes:** 98s ✅
- **p95 pico durante transição:** 680ms (baseline 320ms) ✅
- **Serialization failures durante transição:** 0.8% (esperado ≤ 1%) ✅
- **Erros visíveis ao cliente:** 0 ✅
- **Action items abertos:** [lista com links]
- **Runbook atualizado:** [sim/não, resumo da mudança]
- **Scribe:** @nome · IC: @nome · Tech Lead: @nome
```

---

## Sinais de saúde

- ✅ ≥ 4 drills/ano (1 por trimestre), log completo em `.reviews/failover-log.md`.
- ✅ p95 de commit global nunca passa de 2× baseline durante drill.
- ✅ Route 53 remove região degradada em ≤ 90s (health check + TTL coerentes).
- ✅ Nenhuma alteração no cluster DSQL durante incidente real nos últimos 12 meses.
- ✅ Ao menos 3 pessoas diferentes no papel de IC ao longo do ano (evita bus factor 1).
- ❌ "Não precisamos drillar, nunca aconteceu nada" — a prática **é** a prevenção.
- ❌ Drill no mesmo dia/hora — acostuma o sistema e o time com uma única condição.

---

## Relacionadas

- `arquiteto-cloud-aws/SKILL.md` — Aurora DSQL como default 2026 de consistência forte.
- `squad-ai/references/cloud-native-aws.md` — 12-Factor + multi-região.
- `squad-ai/references/incident-response.md` — workflow de SEV real, tabletop T4 aciona este runbook.
- `squad-ai/references/deploy-checklist.md` — deploy multi-região com canary por região.
- `squad-ai/references/system-design-guide.md` — Passo 4 (Scale & Reliability) define topologia antes do código.
- [[Aurora DSQL]] / [[Aurora DSQL Failover]] (vault) — conceito e runbook.

#reference #aws #aurora-dsql #failover #multi-regiao #runbook #squad-ai #v8-4
