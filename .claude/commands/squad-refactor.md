---
description: Refatoração segura — micro (naming/smells) com clean-code-craftsman + macro (SOLID/camadas) com engenheiro-clean-architect.
argument-hint: <arquivo/módulo a refatorar> [foco: naming | smells | SOLID | camadas]
origin: squad-ai
---

Você está executando o comando **/squad-refactor** — fachada fina do papel Refactoring.

Alvo: **$ARGUMENTS**

Invoque as skills **`clean-code-craftsman`** (qualidade micro) e **`engenheiro-clean-architect`** (qualidade macro), modelo recomendado **sonnet**:

1. **Pré-condição inegociável:** garanta uma **rede de testes verde ANTES** de refatorar. Se não houver cobertura suficiente, acione `especialista-qualidade` (/squad-test) primeiro. Refatoração sem testes é proibida.
2. **Micro (`clean-code-craftsman`):** naming expressivo, funções pequenas e coesas, eliminação de code smells, Tell-Don't-Ask, Lei de Demeter.
3. **Macro (`engenheiro-clean-architect`):** aplicar SOLID, isolar o domínio da infraestrutura, corrigir violações de camada (ports & adapters / hexagonal), inverter dependências. Use recursos modernos: Java 25 (Records, Sealed Classes, Pattern Matching) e Python 3.13 (match/case, Protocols, dataclasses).
4. **Comportamento preservado:** refatoração NÃO muda comportamento. Rode os testes novamente após cada passo — devem permanecer verdes.

**Arbitragem:** `P1-Simplicidade > P2-Performance > P3-CustoBaixo`. Não introduza complexidade acidental em nome de "elegância".

**Entrega:** diff de refatoração incremental + confirmação de testes verdes antes e depois. Encaminhe para **/squad-review** antes de comitar.
