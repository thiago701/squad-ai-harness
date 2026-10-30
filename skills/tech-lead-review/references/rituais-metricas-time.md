# tech-lead-review · reference — Rituais Ágeis, DoD, Feedback e Métricas do Time

> Conteúdo movido VERBATIM do hub `../SKILL.md` (ciclo 6c do Loop V3, 2026-07-09) — progressive
> disclosure. Duas seções do hub: "Metodologia Ágil — Rituais e Cadência" e "Alta Performance de
> Time — Práticas Inegociáveis".

## Metodologia Ágil — Rituais e Cadência

### Sprint Review de Qualidade Técnica

A cada sprint, o Tech Lead conduz uma revisão de 15 minutos de saúde técnica:

```
INDICADORES DA SPRINT:
  □ Mutation score da sprint: atingiu > 80% nas features novas?
  □ Testes flaky introduzidos: zero tolerância
  □ PRs > 800 linhas aprovados: justificativa registrada?
  □ Tech debt cards criados: foram priorizados no backlog?
  □ Decisões sem ADR: existe decisão arquitetural não documentada?
  □ Padrões institucionais violados: quantos? Por quê?

AÇÃO SE INDICADOR VERMELHO:
  → Não punitivo — investigativo. "O que impediu o padrão?"
  → Identifica obstáculo de processo, não culpa individual
  → Gera card de melhoria para próxima sprint
```

### Definition of Done (DoD) Técnico

Uma entrega só está feita quando:

```
CÓDIGO:
  ✓ PR aprovado pelo Tech Lead ou por 2 pares sênior
  ✓ Todos os checks de CI passando (testes + lint + cobertura)
  ✓ Mutation score ≥ 80% nas classes alteradas
  ✓ Sem comentários 🔴 ou 🟡 em aberto

TESTES:
  ✓ Comportamento principal coberto por teste unitário
  ✓ Regras de borda documentadas em testes (boundary values)
  ✓ Integração com banco/fila coberta por teste de integração (se aplicável)
  ✓ Contrato de API coberto por teste funcional (se novo endpoint)

DOCUMENTAÇÃO:
  ✓ ADR criado se a entrega estabelece padrão arquitetural
  ✓ README atualizado se alterou setup ou variáveis de ambiente
  ✓ Changelog atualizado se altera contrato público

OPERAÇÃO:
  ✓ Logs estruturados nas operações críticas (audit trail)
  ✓ Métricas/alertas configurados se nova feature tem SLA
  ✓ Rollback plan documentado para mudanças de alto risco
```

### Retrospectiva Técnica — Formato do Tech Lead

```
FORMATO (30 min, mensal):

VELOCIDADE (10 min):
  "O que nos tornou mais rápidos esta sprint?"
  "O que nos tornou mais lentos? (processo, não pessoa)"
  → Foco: remover obstáculos de processo, não de habilidade

QUALIDADE (10 min):
  "Qual bug ou incidente poderia ter sido evitado com um teste?"
  "Qual decisão técnica tomamos que gostaríamos de ter tomado diferente?"
  → Resultado: card de melhoria de processo ou padrão

SIMPLIFICAÇÃO (10 min):
  "Qual parte do código mais difícil de entender revisamos esta sprint?"
  "O que podemos simplificar agora que entendemos melhor o domínio?"
  → Resultado: card de refatoração de simplificação (não de feature)
```

---

## Alta Performance de Time — Práticas Inegociáveis

### Feedback Técnico de Alta Qualidade

```
REGRA DO FEEDBACK TÉCNICO:
  Todo comentário de review deve conter:
  1. O problema observado (o quê)
  2. O princípio violado (por quê é problema)
  3. Uma sugestão concreta (como corrigir)
  4. O nível de severidade (🔴🟡🔵⚪)

EXEMPLO DE FEEDBACK RUIM:
  "Esse código está confuso."

EXEMPLO DE FEEDBACK BOM:
  🟡 Este método faz extração de dados E persistência (viola SRP — P1).
     Sugiro extrair o `salvarPedido()` para um método separado ou serviço dedicado.
     Referência: engenheiro-clean-architect → Divergent Change.
```

### Boas Práticas de Colaboração

```
PARA O TECH LEAD:
  ✓ Explique o "por quê" antes do "o quê" — contexto gera adesão
  ✓ Nunca rejeite sem sugestão alternativa concreta
  ✓ Reconheça em público; corrija em privado (salvo risco de segurança)
  ✓ Reserve tempo de review: máximo 24h para PRs normais, 4h para hotfix
  ✓ Calibre o nível de exigência ao nível de risco da mudança

PARA O TIME:
  ✓ PR pequeno > PR grande (sempre — sem exceção)
  ✓ Contexto no PR description reduz tempo de review em 50%
  ✓ Self-review antes de solicitar review de par
  ✓ Não use comentário de review para debate de arquitetura — crie ADR
  ✓ "Ship it" com tech debt card é melhor que bloquear indefinidamente

PARA DISCUSSÕES TÉCNICAS:
  ✓ Posições baseadas nas 3 prioridades, não em preferência pessoal
  ✓ Traga dados (métricas, benchmark, logs) antes de trazer opiniões
  ✓ "Eu prefiro X" sem fundamentação não tem peso no consenso
  ✓ Discordar do consenso é permitido; sabotar o consenso, não
```

### Métricas de Alta Performance do Time

```
DORA METRICS (meta da equipe):
  Deployment Frequency:   > 1 deploy por semana por feature team
  Lead Time for Changes:  < 3 dias (PR aberto até produção)
  Change Failure Rate:    < 5% de deploys geram incidente
  Time to Restore:        < 1 hora para incidentes críticos

MÉTRICAS DE QUALIDADE (acompanhamento semanal):
  Mutation score médio:   > 80%
  Cobertura de branches:  > 80%
  Testes flaky:           0 tolerados
  PR cycle time:          < 24h para review, < 4h para hotfix
  Tech debt ratio:        máximo 20% da capacidade da sprint
```
