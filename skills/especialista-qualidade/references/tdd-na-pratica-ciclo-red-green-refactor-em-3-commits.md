# especialista-qualidade · TDD na Prática — Ciclo RED → GREEN → REFACTOR em 3 Commits

> Reference da skill `especialista-qualidade` (movida da SKILL.md em 11/10/2026 — hub + references, I3). Carregue só quando a tarefa pedir este tema.

## TDD na Prática — Ciclo RED → GREEN → REFACTOR em 3 Commits

TDD não é "escrever teste primeiro". É disciplina de design iterativa onde o teste guia a arquitetura:

1. **RED**: teste falha porque o comportamento ainda não existe (compilação OU asserção)
2. **GREEN**: código mínimo (pode ser feio/duplicado) que passa no teste
3. **REFACTOR**: melhorar código mantendo testes verdes

**Regra de ouro:** NUNCA pule RED. Código sem teste falho antes é adição de feature **sem contrato**.

### Ciclo cognitivo ampliado (TDD + JEV)

O ciclo tradicional vira 11 estágios dirigidos por microespecialistas JEV
(`scripts/qa/jev_tdd.py` — 0 tokens, < 1 ms por decisão; o LLM fica com design,
ambiguidade e análise profunda):

```
REQUISITO → ANÁLISE DE RISCO → TEST DESIGN → RED → IMPLEMENTAÇÃO MÍNIMA → GREEN
  → MUTATION/EDGE → REFACTOR → TEST OPTIMIZATION → REGRESSION → VALIDAÇÃO FINAL
```

| JEV | Decide | Guarda |
|---|---|---|
| Test Designer (`designer_cenarios`) | extrai cenários Gherkin-lite de requisito/critérios + bordas numéricas | bloqueia sem comportamento testável |
| Edge Case Hunter (`edge_hunter`) | limites declarados (X±1), estados inválidos, transições | completa bordas por tipo |
| Regression Predictor (`regression_predictor`) | P(regressão) + fatores (ciclomática/deps/integração/segurança/concorrência/persistência/externas/financeiro) | risco governa profundidade |
| TDD Coach (`tdd_coach`) | máquina de estados RED→GREEN→REFACTOR | bloqueia GREEN sem RED, REFACTOR sem GREEN, e sobreimplementação (YAGNI: impl > 5× teste) |
| Refactoring Guardian (`refactor_guardian`) | preservação de comportamento no refactor | bloqueia lógica alterada sem teste atualizado |
| Test Reviewer (`reviewer_teste`) | asserts fracos + fragilidade + valor | veredito manter/melhorar/consolidar |
| Coverage/Mutation Analyst | caminhos não exercitados + mutation survivors | reusa os JEVs de QA (`jev_qa.py`) |
| Test Optimizer (`optimizer_teste`) | redundância + lentos de baixo valor | nunca remove só por velocidade |
| Anti-bloat (`bloat_check`) | as 8 perguntas antes de adicionar teste (já coberto? detecta defeito? PBT/parametrizável? custo? mutation?) | combate test suite bloat |
| Testabilidade (`smells_testabilidade`) | acoplamento/estático/efeitos colaterais | dificuldade de testar = architecture smell |

**Princípio central:** o menor conjunto de testes com o maior nível de confiança —
nunca "mais testes". Evidência: `docs/relatorios/TDD-JEV-2026-09-26.md`.

**Ciclo executável (estado por artefato):** `scripts/qa/tdd_cycle.py`
(`init <slug> --requisito ...` · `advance <slug> --sinal chave=valor ...` · `status <slug>`) —
o estado persiste em `scheduler/tdd/<slug>.json` (handoff sem memória implícita) e o
Coach JEV valida cada transição: GREEN sem RED bloqueia, REFACTOR sem GREEN bloqueia,
YAGNI (impl > 5× teste) bloqueia. O LLM produz o conteúdo criativo; as guardas são do JEV.

**Padrão de 3 commits:**
- `test(pedido): RED - confirmar falha com estoque insuficiente`
- `feat(pedido): GREEN - validação de estoque ao confirmar`
- `refactor(pedido): extrair EstoqueValidator + sealed result`

Exemplo completo (Java 25 + Spring 7 com sealed result e Gatherers): ver `references/unit-tests.md` §TDD.

---
