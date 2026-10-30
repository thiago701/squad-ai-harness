# especialista-qualidade · QA Orientada a Risco (JEV) — o pipeline inteligente de qualidade

> Reference da skill `especialista-qualidade` (movida da SKILL.md em 11/10/2026 — hub + references, I3). Carregue só quando a tarefa pedir este tema.

## QA Orientada a Risco (JEV) — o pipeline inteligente de qualidade

> **Núcleo determinístico:** `scripts/qa/jev_qa.py` (0 tokens, < 1 ms por análise) +
> suíte gold `labs/jev-ecosystem/suites/qa/` (13 casos). O LLM é **orquestrador e
> decisor** — nunca calcula métrica que o JEV já calcula.

```
Mudança → Change Impact Analysis (TIA) → Risk Classifier JEV (P(regressão) + tier)
  → Test Gap Analyzer JEV → Mutation/Coverage Analyzer JEV → Test Generator/Refactor
  → Suite Optimizer (valor do teste) → Execução seletiva (Critical/Relevant/Optional/Unrelated)
  → QA Reviewer → Quality Gate (changed-code coverage + risco, NUNCA % global isolado)
```

1. **Risk Classifier** (`risco_alteracao`): P(regressão) por sinais objetivos — nº de
   arquivos/linhas, domínio crítico (auth/security/payment/db/concurrency), churn,
   histórico de falhas. Tier baixo/médio/alto/crítico governa a cerimônia.
2. **Test Value** (`valor_teste`): `Risco × Detecção × CoberturaComportamental × Mutação ÷ Custo`.
   Teste de baixo valor é candidato a remoção/consolidação/parametrização — **cobertura útil,
   não quantidade** (meta: máxima confiança com o mínimo de testes).
3. **TIA** (`tia_selecionar`): classifica Critical/Relevant/Optional/Unrelated pelo diff +
   grafo de dependências — evita rodar a suíte inteira quando não há necessidade.
4. **Asserts fracos** (`asserts_fracos`): tautologias (`assertEquals(x, x)`), sem assert,
   `assertNull(null)` — bloqueantes na revisão da suíte.
5. **Redundância** (`analisar_redundancia`): testes semanticamente equivalentes (mesmo alvo +
   mesmo padrão de assert) → consolidar/parametrizar mantendo o de menor custo.
6. **Flaky Intelligence** (`flaky_sinais`): sinais de causa-raiz (sleep, relógio, rede,
   randomização, estado compartilhado) — **corrigir a causa, nunca só reexecutar**.
7. **Mutation Survivors** (`mutation_survivors_analisar`): equivalente → excluir do score;
   sobrevivente real → regra de negócio sem teste (aprender com o survivor).
8. **Gap Analyzer** (`gap_analisar`): branches não testados + branches críticos de domínio
   sem validação (blocker).
9. **Edge Cases** (`edge_cases`): gerador determinístico por tipo (null/vazio/limites/NaN/unicode).
10. **Quality Gate** (`gate_pr`): bloqueia por **changed-code coverage < 80%**, mutation < 70%,
    flaky > 5%, tempo desproporcional sem cobertura ≥ 90% e testes novos sem ganho de confiança —
    **nunca por um % global isolado** (linha de corte: cobertura global 55% com changed 100%
    e mutação 75% PASSA; global 95% com changed 55% BLOQUEIA).
11. **Pirâmide adaptativa** (`piramide_adaptativa`): mix por arquitetura (domínio rico → mais
    unit; eventos/filas → mais contract/component; banco → mais integração; legado → mais E2E).

Detalhe completo (Java 21/25: PIT/JaCoCo/JUnit 5/AssertJ/Mockito/Testcontainers/WireMock/
jqwik/ArchUnit/Pact/Awaitility + testes preditivos e propriedades):
`references/qa-orientada-a-risco.md`. Evidência: `docs/relatorios/QA-INTELIGENTE-2026-09-26.md`.

**Sempre que for montar/atualizar o stack de testes Java, leia `references/stack-testes-java-moderno.md`.** Cobre (verificado 09/2026): JUnit 6.1.3, AssertJ, Mockito 5.22 (`@MockitoBean`), Testcontainers 2.0.4, WireMock 3, Pitest, jqwik; contract testing em transição (Spring Cloud Contract → Stubborn.sh ⚠️); estratégia risco×pipeline (máxima confiança + mínimo de testes redundantes + menor tempo de pipeline); testes Native/AOT e serverless (Lambda/SnapStart).

---
