# ADR-006 — Saga Execution Coordinator (SEC) no Core Orchestrator

| Campo | Valor |
|---|---|
| **Projeto** | SquadAI Harness |
| **ADR** | ADR-006 |
| **Data** | 2026-06-30 |
| **Autor(es)** | Squad AI (arquiteto transacional) |
| **Status** | Proposto |
| **Decisores** | Tech Lead (humano) |

---

## Contexto

O `squad-pipeline` é um motor gated **linear**: conduz uma mudança por fases (`Intake → Research → Plan → GATE 1 → Scaffold → TDD → [Segurança] → Review → GATE 2 → Commit`) com handoff por artefato. Isso funciona bem para tarefas curtas, mas em workflows longos (ou no Skill Harvester, que roda a cada 3h) faltam três garantias transacionais: (1) **registro durável** de estado/decisões/dependências por etapa; (2) **recuperação determinística** de falha parcial sem re-executar do zero — hoje um re-início pode **duplicar efeitos** (ex.: re-push, comentário repetido no PR); (3) **compensação declarada**, em vez de reversão improvisada pelo LLM.

A pesquisa `docs/research/Padrão Saga em IA Multi-Agente.md` mapeia o estado da arte (SagaLLM, RAC, Atomix, PatchBoard, Temporal vs. LangGraph) e mostra dois perigos concretos: o re-planejamento especulativo por LLM (caso citado: ~5M tokens e ~34k ações de compensação inúteis) e o *Semantic Rollback Attack* (efeito irreversível emitido por re-execução). A `autonomy-policy` já define N0–N3 e os marcos M1–M10; falta a camada que **materializa** essas regras como estado transacional auditável.

É preciso decidir **como** absorver o Padrão Saga sem violar os princípios imutáveis (Segurança > P1 > P2 > P3; gated, não autônomo) e **sem reescrever** o motor que já funciona.

## Decisão

**Decidimos:** adicionar ao Core Orchestrator um subcomponente **SEC — Saga Execution Coordinator**, que **envolve** o `squad-pipeline` (não o reescreve). O SEC: classifica cada fase como `compensável | pivô | retentável` e cada efeito como `bufferable | externalized | irreversible`; grava um **Saga Log** durável (JSONL append-only) com **idempotency keys**; bloqueia efeitos `irreversible` numa **Outbox** até o *settlement* no **GATE 2**; e executa **compensação determinística (RAC)** por log reverso, a partir de pares declarados no schema das skills/tools. A transação **pivô** é o **commit/push/PR** (autorizado pelo GATE 2); **merge/release** é pivô irreversível reservado ao humano.

**Justificativa resumida:** captura a garantia transacional do Padrão Saga com **mudança mínima** (P1) e custo quase nulo (P3 — só arquivos/SQLite/JSONL), preservando integralmente o caráter *gated* e a segurança.

## Alternativas Consideradas

### Opção A — [Escolhida] SEC sobre o motor atual (arquivos/SQLite/JSONL)

| Prós | Contras |
|---|---|
| Mudança mínima; não reescreve o `squad-pipeline` | Ganho transacional limitado a um nó (sem durabilidade distribuída) |
| Custo ~zero; sem infra nova; reversível | Depende de disciplina nos `compensation_contract` |
| Compensação determinística (RAC) elimina rollback alucinado | — |

### Opção B — Adotar Temporal.io / AWS Step Functions já

| Prós | Contras |
|---|---|
| *Durable execution* real; `saga.addCompensation` nativo | Infra externa, operação e custo; viola P1/P3 sem dor medida |
| Estado da arte para workflows longos | Overkill para pipeline síncrono de uma mudança |

**Por que foi rejeitada:** sem workflow longo/externo/assíncrono comprovado, é *Premature Systematizer*. Fica como Fase 5 sob gatilho (ADR-010).

### Opção C — Não fazer nada (manter pipeline linear)

| Prós | Contras |
|---|---|
| Zero esforço | Persistem duplicação em retry, rollback improvisado e ausência de auditoria |

**Por que foi rejeitada:** o risco de efeito colateral irreversível e de *retry loop* caro é incompatível com Segurança-primeiro.

## Consequências

### Positivas

- Workflows longos ficam consistentes e **auditáveis** ponta-a-ponta por um `correlation_id`.
- Falha parcial recupera por **compensação determinística**, sem duplicar efeitos.
- Efeito irreversível **nunca** sai antes do settlement (reforça M3–M8).
- Estado compartilhado deixa de viver em chat livre (caminho para PatchBoard, ADR-009).

### Negativas / Riscos Assumidos

- Cada skill mutável precisa declarar `compensation_contract` (mitigação: gate de CI; começar pelo caso `git`-nativo).
- Mais um artefato por run (Saga Log) — overhead desprezível (append local).
- Risco de over-orquestração — mitigado pelo veto do `arquiteto-minimalista` e pela adoção faseada.

## Custo da Reversão

| Aspecto | Avaliação |
|---|---|
| **Classificação** | Baixo (dias) |
| **O que precisaria mudar** | Remover `scripts/saga/`, o bloco `compensation_contract` das skills e os critérios novos de `fase-gates.yaml`; o motor volta ao estado atual |
| **Estimativa de esforço** | < 2 dias |
| **Sinal de alerta para reverter** | Saga Log sem uso real, contratos virando burocracia sem evitar incidente, ou overhead percebido sem ganho em 3–4 tarefas-piloto |

## Smoke Test — ADR vivo (R4)

| Campo | Valor |
|---|---|
| **smoke_test** | `saga_external_tool_has_compensation_contract` |
| **tipo** | estrutural (lint de frontmatter no `/review` + CI) |
| **valida_em** | `python scripts/saga/check_contracts.py` (toda tool `externalized`/`irreversible` deve ter `compensation` ou `requires_human: true`) |
| **se_falhar** | Tool de efeito externo sem compensação → 🔴 bloqueante até corrigir ou emitir ADR que SUPERA este. |

> **Ligação com os gates:** o smoke test entra como critério `auto` de `fase-gates.yaml` (R1) e roda no `verificacao-loop` (R4) no GATE 2.

## Referências

- [Proposta: Evolução Saga-Orchestrator para Squad IA](../../docs/propostas/saga-orchestrator-squad-ia.md)
- [Pesquisa: Padrão Saga em IA Multi-Agente](../../docs/research/Padrão Saga em IA Multi-Agente.md)
- [ADR-005 — Orquestrador Conductor](./ADR-005-orquestrador-conductor.md)
- [Política de autonomia (N0–N3, M1–M10)](../../governance/autonomy-policy.md)
- Templates: [SAGA_LOG](../../templates/SAGA_LOG.md) · [COMPENSATION_CONTRACT](../../templates/COMPENSATION_CONTRACT.md) · [PATCHBOARD_STATE](../../templates/PATCHBOARD_STATE.md)

---

## Histórico

| Data | Evento |
|---|---|
| 2026-06-30 | Proposto por Squad AI (arquiteto transacional) |
