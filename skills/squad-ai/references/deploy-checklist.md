# Deploy Checklist — Verificação Pré/Durante/Pós-Deploy

> Absorvido de `engineering:deploy-checklist`. Complementa `step-06-deliver.md` com **checklist executável** + **rollback triggers quantitativos** + **smoke tests estruturados**. Usado antes de cada release (Trunk-Based + release-please) para evitar deploys "no feeling".

## Quando usar

- Antes de promover `main` → `staging` ou `staging` → `production`.
- Deploy com migração de schema, feature flag nova ou mudança de contrato externo.
- Deploy Friday à tarde — o checklist **bloqueia** e força replanejamento.

## Estrutura

```
PRÉ-DEPLOY → DEPLOY (staging → canary → prod) → PÓS-DEPLOY
```

Cada fase tem gates. Se qualquer gate falhar, **não avance** — rollback (staging) ou reverta PR (prod).

---

## PRÉ-DEPLOY (checklist de 12 itens)

### Código

- [ ] **CI verde** em `main` — unit + integration + mutation (specimen ≥ 85%) + ArchUnit.
- [ ] **Cobertura ≥ meta** (tipicamente 80% linhas, 70% mutação no módulo `domain/`).
- [ ] **Aprovação de 1+ revisor** sênior — Protocolo de 5 Passos do `step-05-review.md` (ou 4 Lentes se hotfix).
- [ ] **Conventional Commits** válidos — release-please vai gerar `CHANGELOG.md` automático.
- [ ] **ADR criado** se decisão cruzou gatilho (ver `adr-guide.md`).

### Dados e contrato

- [ ] **Migração de schema é expand/contract** (Liquibase/Flyway) — nunca rename destrutivo no mesmo deploy do código novo.
- [ ] **Contrato público preserva backward compatibility** — OpenAPI diff verificado; campos adicionados, não removidos; `@HttpExchange` client compila com contrato antigo.
- [ ] **Feature flag criada e default OFF** — se o comportamento novo pode quebrar, ativa gradual.

### Operação

- [ ] **Runbook atualizado** no mesmo PR — ver `documentation-guide.md` §Runbook.
- [ ] **Rollback plan definido** — 1 comando, <5 minutos, testado em staging.
- [ ] **Alertas ajustados** — novas métricas têm alarme, métricas removidas têm dashboards atualizados.
- [ ] **Comunicação** — stakeholders (produto, suporte, on-call do consumer upstream) notificados da janela e do blast radius.

---

## DURANTE DEPLOY — Staging → Canary → Production

### Staging (gate 1)

- [ ] Deploy bem-sucedido (ECS task stable, health probe 200).
- [ ] **Smoke tests** passaram (ver seção abaixo).
- [ ] Logs sem `ERROR` novo nos primeiros 5 min.
- [ ] Métricas core sem degradação (p95, error_rate, throughput).

### Canary (gate 2) — 5-10% do tráfego

- [ ] Canary estável por ≥ 15 minutos.
- [ ] Comparação canary vs baseline:
  - Error rate canary ≤ 1.2 × baseline.
  - p95 canary ≤ 1.5 × baseline.
  - Nenhum alerta disparou.
- [ ] Logs do canary sem exceções novas.

### Production (gate 3) — rollout completo

- [ ] Rollout gradual (0→25→50→100%) com janela de observação entre passos.
- [ ] **Rollback triggers ativos durante todo o rollout** (ver próxima seção).
- [ ] Após 100%, manter observação por ≥ 30 minutos antes de declarar "deploy completo".

---

## Rollback Triggers (quantitativos, pré-definidos)

**Regra:** gatilho é automático quando possível, manual com checklist quando não. Nunca "vamos ver".

| Trigger | Threshold | Ação | Decisor |
|---|---|---|---|
| Error rate | > 2 × baseline por 5 min | Rollback automático | Alarme CloudWatch |
| p95 latency | > 3 × baseline por 10 min | Rollback automático | Alarme CloudWatch |
| 5xx sustained | > 1% por 3 min | Rollback automático | Alarme CloudWatch |
| User flow quebrado | Synthetic canary falha 3× consecutivo | Rollback manual em ≤ 10 min | On-call |
| Dados corrompidos | Qualquer linha com invariante violada | Rollback + pause + investigação | On-call + DBA |
| Alerta externo (cliente) | Ticket SEV1 do consumer upstream | Rollback manual + abrir incidente | On-call |

**Rollback ≠ fix.** Rollback estabiliza; o fix vem depois pelo fluxo completo (debug → PR → review → deploy).

---

## Smoke Tests (obrigatórios)

**Sem smoke test passando, não há "deploy bem-sucedido".**

Execute em staging e canary, idealmente via Synthetic (CloudWatch Synthetics / Playwright headless) agendado:

1. **Login / auth:** obter token e validar claim.
2. **Read path:** listar recurso paginado e abrir 1 detalhe.
3. **Write path:** criar recurso que aciona o Aggregate Root canônico + `Transactional Outbox` → confirmar que evento foi publicado (consultar SQS / Kafka).
4. **Idempotência:** enviar mesma requisição 2×, confirmar dedupe (ver `cqrs-outbox.md`).
5. **Health probe:** `GET /actuator/health/readiness` retorna 200.
6. **Observabilidade:** trace-id aparece no X-Ray com spans do banco e da mensageria.

Tempo alvo: ≤ 2 minutos. Falha em qualquer = gate bloqueado.

---

## PÓS-DEPLOY

- [ ] Tag criada (release-please PR mergeado gerou `v1.N.0`).
- [ ] `CHANGELOG.md` publicado e linkado na PR de release.
- [ ] Dashboards revisados — p95, error_rate, throughput, saturação estáveis por ≥ 30 min.
- [ ] Feature flag ativada gradualmente (5% → 25% → 100%) se aplicável, com janela de observação.
- [ ] Notificação final no canal — "Deploy v1.N.0 concluído, sem alertas."
- [ ] Se algo ficou fora do escopo, criar card no board (não "vou lembrar").

---

## Sinais de saúde

- ✅ Checklist é checado ao vivo na PR de release, não "sim de boca".
- ✅ Rollback foi usado ao menos 1× sem culpa — sinal de cultura madura.
- ✅ Tempo médio deploy→healthy ≤ 15 min em staging, ≤ 30 min em prod.
- ❌ Deploy sem smoke test ("tem CI passando").
- ❌ Rollback "não é prático" — indica dívida em automação.

## Anti-padrões

- **Deploy na sexta à tarde** sem plano de rollback e on-call ciente.
- **Migração destrutiva no mesmo deploy** do código novo — quebra qualquer rollback.
- **"Feature flag vou criar depois"** — ativar + desativar deve ser possível sem redeploy.
- **Checklist decorativo** — preenchido depois, não antes.
- **Rollout 0→100% direto** em serviço com blast radius > 5% dos usuários.

## Relacionadas

- [[Release Please]] — Conventional Commits gera CHANGELOG e tag.
- [[Incident Response]] — se deploy causou incidente, fluxo muda para triagem.
- [[Runbook]] — deploy runbook é parte da taxonomia de documentação.
- `squad-ai/steps/step-06-deliver.md` §3 — runbook operacional.
- `engenheiro-devops/references/release-please.md`

#conceito #deploy #checklist #squad-ai #v8-3
