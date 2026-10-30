---
description: Retrospectiva de ciclo/projeto com tech-lead-review — o que funcionou, o que falhou, ações e instintos a destilar.
argument-hint: [escopo: último ciclo | sprint | projeto <nome>]
origin: squad-ai
---

Você está executando o comando **/squad-retrospective** — fachada fina de melhoria contínua de processo.

Escopo: **$ARGUMENTS** (se vazio, retrospectiva do último ciclo do pipeline).

Invoque a skill **`tech-lead-review`** (modelo opus) e conduza a retrospectiva, consumindo a memória institucional:

1. **Coleta de evidências:** leia os resumos de sessão, ADRs, relatórios de verificação e achados de review do período. Baseie-se em fatos (artefatos), não em impressões.
2. **Análise estruturada:**
   - **Funcionou** — práticas e decisões a reforçar.
   - **Falhou** — gargalos, retrabalho, gates vermelhos recorrentes, drift.
   - **Pendente** — itens carregados de um ciclo para o próximo.
3. **Decisões de processo:** proponha ajustes (padrões institucionais, novos gates, mudança de model routing) e registre como **ADR** quando houver decisão durável.
4. **Aprendizado:** destile as lições em **instintos** (encaminhe para **/squad-evolve-skills**) para que a squad melhore de fato a cada ciclo.

**Arbitragem:** priorize ações por `P1-Simplicidade > P2-Performance > P3-CustoBaixo`.

**Entrega:** ata de retrospectiva (funcionou/falhou/pendente) + ações priorizadas com responsável + ADRs/instintos gerados, persistidos em `memory/`.
