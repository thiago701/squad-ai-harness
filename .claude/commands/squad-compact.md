---
description: Compactação estratégica de contexto em fronteiras lógicas (pós-pesquisa/pós-milestone), nunca no meio da implementação.
argument-hint: [momento: pós-pesquisa | pós-milestone | pré-fase]
origin: squad-ai
---

Você está executando o comando **/squad-compact** — fachada fina do Token & Context Optimizer.

Contexto/momento: **$ARGUMENTS**

Invoque a skill **`compactacao-estrategica`** e siga a disciplina de contexto:

1. **Compacte apenas em fronteiras lógicas:** após a pesquisa (antes de planejar), após um milestone/fase concluída, ou antes de iniciar uma fase cara. **NUNCA compacte no meio de uma implementação** — perde-se estado de trabalho ativo.
2. **Preserve o que importa:** objetivo de negócio, decisões dos GATEs, artefatos de fase (`.prd.md`/`.plan.md`), itens pendentes e o resumo "funcionou/falhou/pendente". Descarte ruído de transcript já consolidado em arquivo.
3. **Handoff por artefato:** o estado essencial deve viver em arquivo (`.claude/plans/`, `memory/`), não na janela de contexto — assim a compactação é segura ("the pipeline carries no hidden state").
4. **Sincronize com a memória:** se for fim de sessão, encadeie com a gravação do resumo de sessão (Memory & Learning) para recarregar na próxima.

**Arbitragem:** simplicidade e continuidade do trabalho (P1) acima de economia agressiva de tokens (P3).

**Entrega:** contexto compactado com estado de trabalho íntegro e ponteiros para os artefatos persistidos.
