# tasks.md — Tarefas: [NOME DA FEATURE]

> **Origin:** `squad-ai | adaptado-de-spec-kit` · Terceiro vértice do contrato **spec → plan → tasks**.
> **Arbitragem:** P1‑Simplicidade > P2‑Performance > P3‑CustoBaixo · Segurança é cláusula pétrea.

<!--
  TAREFAS (tasks.md).
  Quando usar: após o plan.md aprovado no GATE 1. Executado por /squad-build via squad-pipeline.
  Quem preenche: arquiteto-minimalista + Core Orchestrator.
  Regra de ouro: organizado POR USER STORY, para entrega e teste independentes.
  Cada tarefa de história rastreia a um requisito/US — é o que o /squad-analyze (Onda 2) audita.
-->

| Campo | Valor |
|---|---|
| **Feature** | [nome] |
| **Plano base** | `specs/[NNN-slug]/plan.md` |
| **Data** | [AAAA-MM-DD] |
| **Status** | [Rascunho \| Pronto p/ Execução \| Em execução \| Concluído] |
| **Testes** | [obrigatórios (TDD) \| opcionais — decisão do plan.md] |

**Formato de cada tarefa:** `- [ ] [ID] [P?] [US?] Descrição com caminho de arquivo`

- **[ID]** sequencial e estável: `T001`, `T002`…
- **[P]** = paralelizável (arquivos distintos, sem dependência) → candidata a *worktree* própria. Sem `[P]` = sequencial.
- **[US1]/[US2]** = a qual user story pertence. Obrigatório nas fases de história; ausente em Setup/Fundacional/Polimento.
- **Convenções de caminho:** Java `src/main/java/...` · Python `src/<pkg>/...` · Angular `src/app/...` (ajuste ao tipo de projeto do plan.md).

---

## Fase 1 — Setup

- [ ] T001 Criar a estrutura do projeto/módulo conforme o `plan.md`
- [ ] T002 [P] Configurar lint/format e pipeline base (CI)
- [ ] T003 [P] Declarar as dependências aprovadas no plano (justificadas — N4)

## Fase 2 — Fundacional

> ⚠️ **CRÍTICO:** nenhuma user story começa antes desta fase terminar. São pré-requisitos bloqueantes (schema base, autenticação, infra compartilhada).

- [ ] T004 [Migração/Schema base conforme `data-model.md`]
- [ ] T005 [Camada de configuração/segurança compartilhada]

**🚦 Checkpoint Fundacional:** base pronta — as histórias podem começar (inclusive em paralelo).

## Fase 3 — US1: [título] (Prioridade P1) 🎯 MVP

**Objetivo:** [o que estará funcionando ao final desta fase.]
**Teste independente:** [como demonstrar a US1 sozinha.]

<!-- Bloco de testes OPCIONAL (só se o plano pediu TDD). Se incluído: escreva PRIMEIRO e garanta que FALHAM (Red). -->

- [ ] T006 [P] [US1] (teste) [contrato/integração da US1] — escrever antes da implementação
- [ ] T007 [US1] [implementar modelo/serviço da US1 em `<caminho>`]
- [ ] T008 [US1] [implementar endpoint/UI da US1 em `<caminho>`]

**🚦 Checkpoint US1:** US1 funcional e testável de forma independente → MVP entregável.

## Fase 4 — US2: [título] (Prioridade P2)

**Objetivo:** [...] · **Teste independente:** [...]

- [ ] T009 [P] [US2] [...]
- [ ] T010 [US2] [...]

**🚦 Checkpoint US2:** US2 funcional e independente.

## Fase Final — Polimento e Transversais

- [ ] T011 [P] [Documentação: `API_SPEC.md`, README]
- [ ] T012 [P] [Observabilidade: logs/métricas nos novos fluxos]
- [ ] T013 [Hardening de segurança / `SECURITY_REVIEW.md`]

## Dependências e Ordem de Execução

- **Entre fases:** Setup → Fundacional → (US por prioridade) → Polimento.
- **Dentro de cada US:** testes → modelos → serviços → endpoints/UI.
- **Oportunidades de paralelismo:** tarefas `[P]` de US diferentes (após o Checkpoint Fundacional) rodam em *worktrees* isoladas; histórias com escopo sobreposto rodam **em série** (evita *overlapping writes*).

## Exemplo de Paralelismo (git worktrees)

<!-- A Squad não usa tmux: paralelismo real = worktrees isoladas com card owner/scope/merge-gate. -->

```text
worktree A → US1 (T006, T007, T008)   [owner: agente-1 | scope: módulo X]
worktree B → US2 (T009, T010)         [owner: agente-2 | scope: módulo Y]
merge-gate: cada worktree passa no verificacao-loop (PRONTO) antes do merge
```

## Estratégia de Implementação

1. **MVP primeiro:** entregue só a US1 (Fases 1+2+3) e valide com o humano antes de seguir.
2. **Entrega incremental:** cada US fecha num checkpoint demonstrável.
3. **GATE 2 por entrega:** `verificacao-loop` (build → typecheck → lint → testes+cobertura → scan de secrets → revisão de diff) → relatório `PRONTO` antes de qualquer commit.

## Notas

- Marcar tarefa concluída com `[X]`. Tarefa não-paralela que falha **interrompe** a fase.
- Rastreabilidade: toda tarefa de história carrega `[US?]`; o `/squad-analyze` (Onda 2) verifica que **todo RF tem tarefa** e **toda tarefa rastreia a um requisito**.

## Histórico de Revisões

| Versão | Data | Autor | Mudança |
|---|---|---|---|
| 0.1.0 | [AAAA-MM-DD] | arquiteto-minimalista | Criação inicial |
