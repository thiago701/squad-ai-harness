# Template — SAGA_LOG

<!--
  SAGA LOG — registro durável e auditável de uma execução do squad-pipeline como Saga.
  Quem escreve: o SEC (Saga Execution Coordinator), a cada transição de fase. NUNCA o LLM à mão.
  Onde vive: .claude/saga/<saga_id>/log.jsonl  (append-only)  +  manifest.yaml (cabeçalho)
  Por que: recuperação determinística (replay), idempotência (sem efeito duplicado) e auditoria.
  Regra de ouro: o log é a única fonte de verdade para compensação (RAC). Sem step no log, não há rollback.
-->

## 1. Cabeçalho — `SagaRecord` (manifest.yaml)

```yaml
saga_id: "2026-06-30T14-03Z__<slug>"   # = correlation_id raiz, propagado em tudo
slug: "<slug>"
tier: standard                         # trivial | small | standard | large
status: running                        # running | settled | compensating | compensated | aborted | done
pivot_step: "gate2"                    # id do step pivô (commit/push/PR)
created_at: "2026-06-30T14:03:00Z"
updated_at: "2026-06-30T14:21:00Z"
budget_tokens: 150000
artifacts_dir: ".claude/pipeline/<slug>/"
gates: { gate1: pending, gate2: pending }   # pending | approved | rejected
```

## 2. Linha de evento — `SagaStep` (uma por linha em log.jsonl)

```json
{
  "saga_id": "2026-06-30T14-03Z__<slug>",
  "step_id": "tdd",
  "seq": 6,
  "tx_type": "compensavel",
  "effect_class": "bufferable",
  "status": "succeeded",
  "idempotency_key": "2026-06-30T14-03Z__<slug>_tdd_1",
  "agent": "especialista-qualidade",
  "model": "sonnet",
  "inputs_ref": ".claude/pipeline/<slug>/03-plano.md",
  "outputs_ref": ".claude/pipeline/<slug>/tests/",
  "compensation": "git_restore",
  "started_at": "2026-06-30T14:18:00Z",
  "ended_at": "2026-06-30T14:21:00Z",
  "hash": "sha256:...",
  "correlation_id": "2026-06-30T14-03Z__<slug>"
}
```

### Campos obrigatórios

| Campo | Domínio | Significado |
|---|---|---|
| `seq` | inteiro contíguo | ordem; buraco em `seq` = log corrompido (🔴 no verificacao-loop) |
| `tx_type` | `compensavel` \| `pivo` \| `retentavel` | mecânica de recuperação da fase |
| `effect_class` | `bufferable` \| `externalized` \| `irreversible` | quando o efeito pode sair (Atomix) |
| `status` | `started` \| `succeeded` \| `failed` \| `compensated` | estado do step |
| `idempotency_key` | `<saga_id>_<step>_<attempt>` | repetição = no-op |
| `compensation` | comando \| `n/a` \| `human_required` | como desfazer (ver COMPENSATION_CONTRACT) |
| `correlation_id` | = `saga_id` | rastro ponta-a-ponta |

## 3. Mapa fase → transação (tier standard)

| Fase | tx_type | effect_class | compensação |
|---|---|---|---|
| Intake / Research / Plan | compensavel | bufferable | apagar/descartar artefato |
| GATE 1 | checkpoint | — | rejeição → volta ao Plan |
| Scaffold / TDD | compensavel | bufferable | `git restore` / `git clean` |
| Gatilho Segurança | gate | — | 🔴 trava avanço |
| Review | compensavel | bufferable | NOT READY → volta ao TDD |
| **GATE 2** | **pivo / settlement** | — | última janela de abort barato |
| Commit + push + PR | retentavel | externalized | fechar PR + apagar branch remota |
| MERGE master / Release | pivo | irreversible | **humano** (fora do escopo do agente) |

## 4. Invariantes do log (checadas no verificacao-loop)

- `seq` contíguo a partir de 1; sem duplicatas.
- Todo step `externalized`/`irreversible` que mudou de `started`→`succeeded` tem `idempotency_key`.
- Nenhum step `irreversible` com `status: succeeded` **antes** de `gates.gate2 == approved`.
- `status` raiz consistente (ex.: `compensated` ⇒ existe ≥1 step com `status: compensated`).
