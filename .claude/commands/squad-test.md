---
description: Projeta e executa testes robustos (unit, integração, E2E, performance) com o especialista-qualidade, método TDD.
argument-hint: [alvo: <módulo/feature> | tipo: unit|integração|e2e|performance]
origin: squad-ai
---

Você está executando o comando **/squad-test** — fachada fina do papel QA / Test.

Alvo do teste: **$ARGUMENTS** (se vazio, cubra o código alterado no working tree).

Invoque a skill **`especialista-qualidade`** (modelo recomendado: **sonnet**) e conduza:

1. **Gere cenários preditivos** — caminho feliz, bordas, erros e regressão — para tornar o refatoramento seguro.
2. **TDD como método:** red → green → refactor. Priorize testes unitários robustos + integração com infraestrutura real (Testcontainers) + E2E ponta a ponta (Playwright) quando houver frontend.
3. **Stack de referência:** JUnit 5 / PIT (mutation) para Java 25; `pytest` + cobertura para Python 3.13; `ng test` para Angular 21+. Valide também a infraestrutura Docker (healthchecks, conectividade entre containers) em fluxos E2E.
4. **Meta de cobertura ≥ 80%.** Não declare pronto sem testes verdes.

**Distinção:** pass@k (basta funcionar uma vez) vs. pass^k (consistência em execuções repetidas) — explicite qual nível o alvo exige.

**Entrega:** suíte de testes + relatório de cobertura. Para o veredito agregado de qualidade do build, encadeie com **/squad-quality-gate**. Segurança e performance entram via **/squad-security** e o `arquiteto-performance`.
