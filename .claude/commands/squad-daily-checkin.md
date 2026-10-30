---
description: Check-in diário (Proactive Scheduler) — retoma sessão, resume pendências e prioriza o trabalho do dia.
argument-hint: [foco do dia, opcional]
origin: squad-ai
---

Você está executando o comando **/squad-daily-checkin** — fachada fina do **Proactive Scheduler** para a abertura do dia de trabalho.

Foco informado: **$ARGUMENTS** (opcional)

Acione o módulo **`scheduler`** em conjunto com a camada de memória (Memory & Learning) e monte o briefing diário:

1. **Retome a sessão:** carregue o último resumo de sessão (funcionou/falhou/pendente) e o `memory/WORKING-CONTEXT.md`. Reconstrua o contexto sem re-onboarding manual.
2. **Resumo do nightly:** leia o relatório mais recente de **/squad-nightly** (drift, stack, diff de nota) e destaque o que precisa de atenção hoje.
3. **Pendências e gates:** liste itens aguardando aprovação (GATE 1 / GATE 2), PRs em revisão e tarefas em aberto.
4. **Plano do dia:** proponha uma fila priorizada por `P1-Simplicidade > P2-Performance > P3-CustoBaixo`, respeitando o foco informado pelo usuário. Sugira o próximo comando concreto (ex.: /squad-build, /squad-review).

**Modo seguro:** apenas reporta e prioriza — **não inicia trabalho automaticamente**. Aguarda a escolha do usuário.

**Entrega:** briefing diário enxuto (tabela Markdown) com contexto retomado, atenções do nightly, pendências e fila priorizada do dia.
