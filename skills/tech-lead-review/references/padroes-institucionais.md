# tech-lead-review · reference — Padrões Institucionais (código, calistenia, arquitetura, PR)

> Conteúdo movido VERBATIM do hub `../SKILL.md` (ciclo 6c do Loop V3, 2026-07-09) — progressive
> disclosure. Estes padrões são estabelecidos por consenso e são **imutáveis até nova deliberação
> formal** (doutrina no hub). A fonte canônica da Calistenia × Java 25 é a skill `java-modernizer`
> (`references/calistenia-java25.md` daquela skill).

### Padrões de Código

```
NOMENCLATURA:
  ✓ Métodos: verbo + substantivo em camelCase (buscarPedido, confirmarTransacao)
  ✓ Classes: substantivo que revela responsabilidade (PedidoService, NÃO: Manager/Helper/Util)
  ✓ Variáveis: intenção explícita (valorTotalComDesconto, NÃO: v, val, tmp)
  ✓ Booleanos: is/has/can/should (isPendente, hasPermissao, canConfirmar)
  ✗ Abreviações não universais (ord, cust, proc, calc — use o nome completo)

TAMANHO:
  ✓ Método de regra de negócio: máximo 20 linhas
  ✓ Classe: máximo 300 linhas (sinal de alerta acima de 200)
  ✓ Arquivo de configuração/setup: sem limite rígido
  ✓ Parâmetros por método: máximo 3 (acima disso, crie um objeto/record)

ESTRUTURA:
  ✓ Máximo 2 níveis de if aninhado (refatore com early return ou polimorfismo)
  ✓ Dependências injetadas, nunca instanciadas internamente
  ✓ Lógica de negócio no domínio, nunca no controller/router/adapter
  ✓ I/O (banco, rede) nunca dentro de loop sem justificativa documentada
```

### Calistenia de Objetos × Java 25 — checklist de review (fase: code review)

Régua de revisão para PR Java. A skill **`java-modernizer`** é a fonte canônica (antes/depois + JEPs + Gate P1 por regra). Marque o que se aplica:

- [ ] **R1 — 1 nível de indentação:** sem `for`/`if` aninhados; extraído para método ou via Streams/Gatherers (JEP 485).
- [ ] **R2 — sem `else`:** guard clauses + `switch` exaustivo sobre `sealed` (JEP 441/409), sem `default` defensivo.
- [ ] **R3 — primitivos envolvidos:** VOs (`Cpf`/`Dinheiro`) com invariante no compact constructor. ⚠️ **Valhalla (JEP 401) NÃO está no JDK 25** — não aprove código que conte com value class/flattening.
- [ ] **R4 — coleções de 1ª classe:** encapsuladas/imodificáveis (`List.copyOf`), sem `List` mutável interna vazando.
- [ ] **R5 — Lei de Demeter:** Record Patterns (JEP 440) no lugar de `a.getB().getC()`.
- [ ] **R6/R7 — nomes íntegros e entidades pequenas:** sem abreviação não universal; `record` + Compact Source (JEP 512).
- [ ] **R8 — ≤ 2 variáveis de instância:** estado coeso em records aninhados (heurística de coesão, não dogma literal).
- [ ] **R9 — Tell, Don't Ask:** sem setter mutável; evoluir imutável via `withX()` explícito. ⚠️ **`with`/JEP 468 NÃO está no 25.**
- [ ] **Gate P1:** cada regra aplicada deixou o código *mais simples*? Se não, o original fica — calistenia serve à simplicidade, não o contrário.

### Padrões de Arquitetura

```
CAMADAS (Clean Architecture):
  domain/       → zero dependência externa. Regras de negócio puras.
  application/  → orquestra domínio. Sem frameworks.
  adapter/      → implementa portas. Conhece infra, não conhece domínio interno.
  config/       → wiring de dependências. Só configuração.

DEPENDÊNCIAS:
  ✓ Domínio define interfaces (portas) — infra implementa (adapters)
  ✓ Use cases dependem de interfaces, nunca de implementações concretas
  ✗ Controller importando Entity do JPA/SQLAlchemy diretamente → 🔴

TESTES (Pirâmide obrigatória):
  60% unitários   → lógica pura, milissegundos, zero infraestrutura
  20% integração  → banco real (Testcontainers), zero H2/mock de repositório
  15% funcionais  → API HTTP, BDD, contract
   5% E2E         → apenas fluxos críticos de negócio

AGENTES DE IA (quando presentes):
  ✓ Porta LLMPort abstrai qualquer modelo — sem acoplamento a SDK específico
  ✓ Guardrails explícitos em InputGuardrail e OutputGuardrail separados
  ✓ Observabilidade obrigatória: trace_id, tokens, latência, guardrails acionados
  ✗ Lógica de negócio delegada ao LLM → 🔴 (alucinação é bug de arquitetura)
```

### Padrões de Pull Request

```
TÍTULO: Conventional Commits (angular) — binding obrigatório para release-please
  <tipo>(<escopo>): <descrição em imperativo, minúscula, sem ponto final>
  tipos: feat | fix | refactor | perf | test | docs | chore | build | ci | revert
  BREAKING CHANGE: prefixar título com "!" (ex: "feat(api)!: trocar contrato") + footer

  ex: "feat(pedido): adicionar confirmação com notificação assíncrona"
  ex: "fix(auth): impedir bypass de DPoP em endpoint de pagamento"
  ex: "perf(catalogo): cachear lista com Caffeine reduzindo p99 de 800ms para 50ms"

DESCRIÇÃO OBRIGATÓRIA (seções abaixo — PR é bloqueado se faltar):
  ## O que muda
  [descrição objetiva — 2 a 5 linhas]

  ## Por que muda
  [motivação de negócio ou técnica, link do card]

  ## Como testar
  [passo a passo local + link para ambiente de preview se houver]

  ## Impacto de Segurança
  [explícito: nenhum / baixo / alto. Se afeta auth, dados sensíveis, endpoints externos,
   mudança de IAM, secrets → marcar ALTO e acionar review de @engenheiro-seguranca]

  ## Impacto de Performance
  [SLA antes/depois, benchmark, curvas p50/p95/p99 se touch hot path.
   N+1 verificado? Pool ajustado? Cache invalidado corretamente?]

  ## Impacto de Observabilidade
  [métricas/traces/logs novos ou alterados? Dashboards/alertas ajustados?
   Correlation ID propaga end-to-end? SLO afetado?]

  ## Checklist
  - [ ] Testes unitários adicionados/atualizados (cobertura do novo código > 80%)
  - [ ] Testes de integração Testcontainers (se alterou persistência/SQS/Bedrock)
  - [ ] Mutation score ≥ 80% nas classes alteradas (pitest)
  - [ ] ArchUnit roda verde (dependências na direção correta)
  - [ ] DBML atualizado (se alterou schema) + Flyway migration idempotente
  - [ ] Documentação atualizada (se alterou contrato de API — OpenAPI/AsyncAPI)
  - [ ] ADR criado (se decisão arquitetural) — `docs/adr/NNNN-titulo.md`
  - [ ] Sem breaking changes (ou BREAKING CHANGE explícito no commit + migração documentada)
  - [ ] Feature flag criada (se toggle incremental) + plano de remoção
  - [ ] Logs não vazam PII (verificado com teste de redação)
  - [ ] Custo cloud estimado se adicionou serviço novo (Bedrock invoke, DAX, etc.)

TAMANHO MÁXIMO DE PR:
  ✓ Ideal: até 400 linhas alteradas
  ✓ Aceitável: até 800 linhas com justificativa
  ✗ Acima de 800: dividir em PRs menores é obrigatório
  Motivo: PR grande = review raso = bugs em produção
```
