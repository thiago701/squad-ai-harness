# squad-pipeline · reference — Contrato Conductor (ADR-005) e MODO SHADOW (V3 Fase 3)

> Conteúdo movido VERBATIM do hub `../SKILL.md` (ciclo 4 do Loop V3, 2026-07-09) — progressive
> disclosure. O hub mantém o resumo operacional do shadow; este arquivo guarda o regime integral.
> **Nota de resolução de paths:** os caminhos relativos abaixo permanecem como no hub e se
> resolvem a partir de `skills/squad-pipeline/` (raiz da skill), não deste subdiretório.

## Contrato Conductor — camada de planejamento declarativo (ADR-005 **Aceito** 2026-07-02)

Para tiers **standard/large** (triagem `DIFÍCIL/AGÊNTICA`), antes de executar o motor **emite o workflow
declarativo** do contrato Conductor (`orchestration/conductor/workflow-contract.md`): listas alinhadas
`subtasks` (instrução prompt-engineered por passo) + `worker_ids` (pool em
`orchestration/conductor/worker_pool.json`) + `access_lists` (topologia de comunicação: default binário
`[]`/`"all"`) + `roles` (`Thinker|Worker|Verifier`), com `budget` (`max_steps ≤ 5`,
`max_recursion_depth ≤ 2`) e validação DAG (`scripts/conductor/`; suíte em
`tests/test_conductor*.py` + `tests/test_residencia.py`).

- Os subagentes/gates existentes assumem os papéis: fases 1–5 = Worker, gatilho de segurança e
  Fase 6 = Verifier, motor = Thinker. Nada de treino (Fase 1 = Conductor-as-a-prompt).
- `cerebro_hits` do contrato = saída do RETRIEVE (Fase 0.5) + `squad_decision_log(query)` — declarar
  `[]` quando nada relevante.
- O workflow emitido é artefato: salvar em `.claude/pipeline/<slug>/00-workflow.json` antes do GATE 1.
- Tiers trivial/small dispensam o contrato (1 passo — cerimônia proporcional, P1).

### Contrato de workflow (MODO SHADOW — flag `SQUAD_CONDUCTOR_SHADOW`, default on) · V3 Fase 3

Fiação decidida no GATE arquitetural (GATE 2026-07-09, decisão 1; ADR-008 §Decisão item 3): o contrato acima roda **em modo shadow**,
atrás da feature-flag `SQUAD_CONDUCTOR_SHADOW` (default `on`; regime completo em
`orchestration/conductor/shadow-mode.md`). Na **Fase 3 (Plan)**, para tarefas **standard/large**:

1. **Emitir:** o orquestrador emite o objeto `Workflow` (schema do contrato) e o salva em
   `.claude/pipeline/<slug>/00-workflow.json`.
2. **Validar (dupla leitura):** roda `validate_workflow` (`scripts/conductor/validate.py`;
   `roster_size` = 24 workers do `worker_pool.json` v1.2) com `residencia=False` para o
   reward/SLI-1, **e** `observar_residencia(wf, camadas)` para o log observacional de residência
   (o que a invariante *teria* reprovado — nunca afeta o reward;
   `orchestration/cascata-3-camadas.md` §4).
3. **Registrar, NÃO bloquear:** o resultado (reward 0/0.5/1 + violações) é **REGISTRADO** —
   telemetria (`workflow_validity_rate`, SLI 1 do ADR-009, evento em `memory/sli.jsonl`) + anexo no
   artefato do plano (`03-plano.md` cita o veredito) — mas **não trava** o GATE 1 nem força
   re-emissão: em shadow, plano com violação segue para o GATE humano com o aviso visível.
4. **Promoção a bloqueio:** só após `workflow_validity_rate ≥ 95%` medido em **sessão live**
   (ADR-008/ADR-009) e overhead de cerimônia dentro do guard-rail calibrado nos logs do shadow.
   **Rollback = desligar a flag** (`off` → comportamento pré-fiação, sem emissão nem validação).

> O pass_rate 0,978 do contrato é `[PROXY/MOCK — harness sintético]`; nunca citar como validação real.
