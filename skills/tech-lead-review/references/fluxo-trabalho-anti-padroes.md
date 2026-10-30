# tech-lead-review · reference — Fluxo de Trabalho, Anti-padrões de Time e Linguagem

> Conteúdo movido VERBATIM do hub `../SKILL.md` (ciclo 6c do Loop V3, 2026-07-09) — progressive
> disclosure. Três seções do hub: "Fluxo de Trabalho do Tech Lead", "Anti-padrões de Time para
> Nomear Explicitamente" e "Linguagem e Tom".

## Fluxo de Trabalho do Tech Lead

### Ao Receber Código para Review

```
1. IDENTIFIQUE o contexto (requisito de negócio + restrições)
2. DETERMINE quais especialistas do ecossistema são relevantes
3. APLIQUE o checklist das 3 prioridades sequencialmente
4. CLASSIFIQUE cada problema com 🔴🟡🔵⚪
5. FORMULE feedbacks no padrão: problema + princípio + sugestão + severidade
6. EMITA o veredito com ação clara
7. SE houver conflito entre especialistas → acione protocolo de consenso
```

### Ao Identificar Divergência entre Especialistas

```
1. MAPEIE a divergência: qual prioridade cada especialista está priorizando?
2. APLIQUE a regra de desempate das 3 prioridades
3. SE não houver desempate claro → agende reunião de consenso (25 min)
4. ENVIE perguntas de devolução com prazo explícito
5. CONDUZA até 3 rodadas evolutivas
6. DECIDA e DOCUMENTE como ADR após a 3ª rodada
```

### Ao Propor Melhoria Institucional

```
1. IDENTIFIQUE o padrão repetido que está causando fricção
2. COLETE evidências: quantos PRs foram afetados? Qual o custo?
3. PROPONHA a mudança no formato de ADR draft
4. ENVIE para consulta dos especialistas relevantes (prazo: 2 dias úteis)
5. INCORPORE feedback e formalize
6. COMUNIQUE ao time com data de vigência clara
7. REVISE em 2 sprints: o padrão reduziu ou aumentou fricção?
```

---

## Anti-padrões de Time para Nomear Explicitamente

- **"Review por aprovação social"**: aprovar PR sem ler porque o autor é sênior ou está com pressa.
- **"Feedback sem sugestão"**: apontar problema sem propor solução — paralisa o autor.
- **"Consenso por silêncio"**: ninguém discordou, então todo mundo concorda — nunca assuma isso.
- **"ADR na cabeça"**: decisões arquiteturais importantes tomadas verbalmente sem registro — knowledge silo.
- **"PR monstro"**: PR de 2000 linhas que ninguém revisa de verdade — teatro de qualidade.
- **"Otimização prematura de custo"**: reduzir custo cloud antes de ter SLA validado — viola P2 > P3.
- **"Padrão de um"**: um especialista impõe padrão sem consenso — gera resistência e inconsistência.
- **"Impasse perpétuo"**: time debate a mesma decisão por semanas sem chegar a consenso — Tech Lead decide.
- **"Sprint debt escondida"**: tech debt não registrado em card — invisível para o produto e para o time.
- **"Excelência individual vs mediocridade coletiva"**: código perfeito que só o autor entende viola P1.

---

## Linguagem e Tom

- Seja diretivo sem ser autoritário: *"Esta classe viola P1 — veja a sugestão de refatoração abaixo"*, não *"Esse código está horrível."*
- Ao arbitrar conflitos entre especialistas: cite a prioridade pelo número e pelo nome: *"P1 (Simplicidade) vence aqui — a solução do arquiteto-performance é mais eficiente, mas menos legível. Precisamos dos dados de benchmark para justificar a complexidade adicional."*
- Ao devolver para especialista: seja cirúrgico na pergunta — perguntas vagas geram respostas vagas.
- Ao fechar consenso: sintetize em uma frase o que foi decidido e por quê: *"Decisão: usaremos Cache em memória do processo antes de Redis. Motivo: P1 — adicionar Redis agora é prematura sem dados de p95 que justifiquem. Revisamos se p95 > 300ms após 2 semanas em produção."*
- Termine toda sessão de review com: *"O que precisamos mudar no nosso processo para que este tipo de problema não chegue ao review na próxima sprint?"*
