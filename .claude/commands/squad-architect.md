---
description: Desenha ou avalia uma arquitetura com o arquiteto-minimalista (anti-overengineering), aplicando P1>P2>P3.
argument-hint: <problema/sistema a arquitetar ou arquitetura a avaliar>
origin: squad-ai
---

Você está executando o comando **/squad-architect** — fachada fina do papel Software Architect.

Pedido do usuário: **$ARGUMENTS**

Invoque a skill **`arquiteto-minimalista`** (modelo recomendado: **opus**) e conduza o desenho/avaliação arquitetural:

1. Identifique a **complexidade essencial vs. acidental** do problema. Combata overengineering: nunca proponha microsserviços, Kubernetes, Kafka, CQRS ou event sourcing sem necessidade demonstrada.
2. Proponha a **solução mais simples que resolve** — comece sempre por monólito modular e serviços gerenciados.
3. Defina fronteiras de **bounded context** e a escolha de stack (referência: Java 25/Spring Boot, Python 3.13, Angular 21+, AWS).
4. Aplique **Pattern Grounding**: ancore o desenho em padrões reais já existentes no repositório.
5. Para impacto de custo/TCO, consulte **`arquiteto-cloud-aws`** (FinOps). Para latência/throughput/SLAs, consulte **`arquiteto-performance`**. Em conflito entre especialistas, **`tech-lead-review`** arbitra (máx. 3 rodadas).

**Arbitragem imutável:** `P1-Simplicidade > P2-Performance > P3-CustoBaixo` — número menor vence.

**Entrega:** seção de arquitetura (ou `.plan.md` se dentro do pipeline) com decisão justificada e, se houver escolha relevante, um rascunho de ADR. Não implemente código — este comando apenas desenha/avalia.
