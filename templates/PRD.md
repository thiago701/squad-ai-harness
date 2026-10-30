# PRD — [Nome do Projeto]

<!--
  PRODUCT REQUIREMENTS DOCUMENT (PRD)
  Quando usar: no início de qualquer projeto ou feature relevante, ANTES da arquitetura.
  Quem preenche: engenheiro-especificacao + Product Owner (humano valida).
  Regra de ouro: descreva o PROBLEMA e o RESULTADO esperado, não a solução técnica.
-->

| Campo | Valor |
|---|---|
| **Projeto** | [Nome do Projeto] |
| **Versão do documento** | [0.1.0] |
| **Data** | [AAAA-MM-DD] |
| **Autor(es)** | [Nome / Agente] |
| **Status** | [Rascunho \| Em revisão \| Aprovado \| Obsoleto] |

---

## 1. Visão do Produto

<!-- 1 a 3 frases. Elevator pitch: para quem, o que resolve, qual o diferencial.
     Formato sugerido: "Para [persona], que [problema], o [produto] é um [categoria]
     que [benefício-chave], diferente de [alternativa]." -->

[Descreva a visão em até 3 frases.]

## 2. Problema

<!-- Qual dor existe hoje? Como é resolvida atualmente (workaround)? Qual o custo de não resolver?
     Inclua evidências: métricas, reclamações, tickets, perda de receita. -->

- **Dor atual:** [descreva]
- **Como é resolvido hoje:** [workaround atual ou "não é resolvido"]
- **Custo de não resolver:** [impacto quantificado quando possível]

## 3. Personas

<!-- Liste 1 a 4 personas. Menos é mais — foque em quem realmente usa. -->

| Persona | Descrição | Necessidade principal | Frequência de uso |
|---|---|---|---|
| [Ana, Analista] | [perfil resumido] | [o que ela precisa] | [diária/semanal] |
| [Carlos, Gestor] | [perfil resumido] | [o que ele precisa] | [mensal] |

## 4. Objetivos Mensuráveis

<!-- Objetivos SMART. Cada objetivo DEVE ter métrica, baseline e meta com prazo.
     Se não dá para medir, não é objetivo — é desejo. -->

| # | Objetivo | Métrica | Baseline | Meta | Prazo |
|---|---|---|---|---|---|
| O1 | [Reduzir tempo de processamento] | [tempo médio em min] | [45 min] | [< 5 min] | [Q3/2026] |
| O2 | [Aumentar adoção] | [usuários ativos/mês] | [0] | [500] | [Q4/2026] |

## 5. Requisitos Funcionais (MoSCoW)

<!-- Priorize com MoSCoW: Must (sem isso não há produto), Should (importante, negociável),
     Could (desejável), Won't (explicitamente fora desta versão).
     Cada RF deve ser testável. Use verbos: "O sistema DEVE...". -->

### Must Have (obrigatório)

| ID | Requisito | Critério de aceitação |
|---|---|---|
| RF-001 | [O sistema DEVE permitir login via SSO] | [Usuário autentica com credenciais corporativas em < 3 cliques] |
| RF-002 | [...] | [...] |

### Should Have (importante)

| ID | Requisito | Critério de aceitação |
|---|---|---|
| RF-010 | [...] | [...] |

### Could Have (desejável)

| ID | Requisito | Critério de aceitação |
|---|---|---|
| RF-020 | [...] | [...] |

### Won't Have (não nesta versão)

| ID | Requisito | Motivo da exclusão |
|---|---|---|
| RF-090 | [...] | [...] |

## 6. Requisitos Não-Funcionais

<!-- Quantifique SEMPRE. "Rápido" não é requisito; "p95 < 300ms" é.
     Lembre das prioridades da Squad: P1-Simplicidade > P2-Performance > P3-CustoBaixo. -->

| ID | Categoria | Requisito | Como medir |
|---|---|---|---|
| RNF-001 | Performance | [p95 < 300ms nos endpoints críticos] | [APM / k6] |
| RNF-002 | Disponibilidade | [99,5% mensal] | [uptime monitor] |
| RNF-003 | Segurança | [Conformidade OWASP Top 10 + LGPD] | [SECURITY_REVIEW.md] |
| RNF-004 | Escalabilidade | [suportar X req/s com auto-scaling] | [teste de carga] |
| RNF-005 | Custo | [infra ≤ USD X/mês em produção] | [AWS Cost Explorer] |

## 7. Fora de Escopo

<!-- Liste explicitamente o que NÃO será feito. Evita expectativa errada e scope creep. -->

- [Item fora de escopo 1 — motivo]
- [Item fora de escopo 2 — motivo]

## 8. Métricas de Sucesso

<!-- Como saberemos que o produto deu certo APÓS o lançamento? North Star + métricas de suporte. -->

| Métrica | Tipo | Meta | Quando avaliar |
|---|---|---|---|
| [Métrica North Star] | Primária | [meta] | [30/60/90 dias pós-launch] |
| [Métrica de suporte] | Secundária | [meta] | [contínuo] |

## 9. Riscos

<!-- Probabilidade e impacto: Baixo / Médio / Alto. Todo risco Alto precisa de mitigação definida. -->

| # | Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|---|
| R1 | [Dependência externa atrasar] | [Média] | [Alto] | [plano de contingência] |
| R2 | [...] | [...] | [...] | [...] |

## 10. Dependências

<!-- Sistemas, times, contratos ou decisões das quais este projeto depende. -->

| Dependência | Tipo | Responsável | Status | Data necessária |
|---|---|---|---|---|
| [API do sistema X] | Técnica | [time/contato] | [Pendente] | [AAAA-MM-DD] |
| [Aprovação jurídica LGPD] | Negócio | [contato] | [Em andamento] | [AAAA-MM-DD] |

## 11. Aprovações

<!-- O PRD só vale após aprovação formal. Agentes IA NÃO aprovam — somente humanos. -->

| Papel | Nome | Decisão | Data |
|---|---|---|---|
| Product Owner | [nome] | [Aprovado / Reprovado / Pendente] | [AAAA-MM-DD] |
| Tech Lead | [nome] | [Pendente] | [AAAA-MM-DD] |
| Sponsor | [nome] | [Pendente] | [AAAA-MM-DD] |

---

<!-- Histórico de alterações do documento (não do produto). -->

## Histórico de Revisões

| Versão | Data | Autor | Mudança |
|---|---|---|---|
| 0.1.0 | [AAAA-MM-DD] | [autor] | Criação inicial |
