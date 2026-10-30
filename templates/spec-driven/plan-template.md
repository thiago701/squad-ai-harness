# plan.md — Plano Técnico: [NOME DA FEATURE]

> **Origin:** `squad-ai | adaptado-de-spec-kit` · Segundo vértice do contrato **spec → plan → tasks**.
> **Arbitragem:** P1‑Simplicidade > P2‑Performance > P3‑CustoBaixo · Segurança é cláusula pétrea.

<!--
  PLANO TÉCNICO (plan.md).
  Quando usar: após o spec.md clarificado, antes do tasks.md.
  Quem preenche: arquiteto-minimalista + Tech Lead (humano aprova no GATE 1).
  Regra de ouro: aqui entra o COMO — mas o gate da Constituição vem ANTES de qualquer pesquisa.
  Este plano gera artefatos de DESIGN (research/data-model/contracts/quickstart), não código.
-->

| Campo | Valor |
|---|---|
| **Feature** | [nome] |
| **Spec base** | `specs/[NNN-slug]/spec.md` |
| **Data** | [AAAA-MM-DD] |
| **Autor(es)** | arquiteto-minimalista + Tech Lead |
| **Status** | [Rascunho \| Constituição OK \| Design OK \| Aprovado no GATE 1] |
| **Backend** | [java \| python] · **Frontend:** Angular |

---

## 1. Resumo

[1–2 frases: o que será construído e a abordagem técnica central, vinculada às US do spec.]

## 2. Contexto Técnico

<!-- Preencha cada item. Desconhecidos viram [PRECISA-CLARIFICAR] e DEVEM ser resolvidos na Fase 0. -->

| Item | Decisão |
|---|---|
| Linguagem/Versão | [Java 25 LTS / Python 3.13] |
| Dependências principais | [Spring Boot 4 / FastAPI / Angular 21] |
| Armazenamento | [PostgreSQL / DynamoDB / N/A] |
| Testes | [JUnit + Testcontainers / pytest / Jasmine + Karma] |
| Plataforma-alvo | [AWS Lambda / ECS / ...] |
| Tipo de projeto | [serviço único / web (front+back) / biblioteca] |
| Metas de performance | [p95 < 300ms — ou "N/A; simplicidade prevalece"] |
| Restrições | [orçamento, prazo regulatório, Windows/PowerShell-first] |
| Escala/Escopo | [usuários, req/s, volume de dados] |

## 3. Verificação da Constituição ⛔ GATE

> **GATE: precisa passar ANTES da Fase 0 (pesquisa). Re-checar APÓS o design da Fase 1.**
> Conflito com a Constituição é **bloqueante** e NÃO pode ser diluído — ajuste o plano, não a regra.

| Princípio / Regra | Conforme? | Observação |
|---|---|---|
| P1 Simplicidade (A1) — menor complexidade que atende ao requisito | [ ] | [a opção escolhida é a mais simples viável?] |
| Test-Driven (princípio 2 / A3) — testes acompanham o código | [ ] | [estratégia de teste por US] |
| Security-First (princípio 3) — toca auth/input/queries/cripto/secrets? | [ ] | [se sim, `engenheiro-seguranca` entra no plano] |
| Immutability (princípio 4 / N2) — sem sobrescrever config sem backup | [ ] | |
| Mínimo suficiente (A9 / N4) — nenhuma dependência injustificada | [ ] | [toda dep nova justificada e com licença verificada?] |

**Resultado do gate:** [ ] PASSA · [ ] PASSA COM JUSTIFICATIVA (preencher §7) · [ ] NÃO PASSA (replanejar)

## 4. Artefatos de Design (gerados a partir deste plano)

| Artefato | Conteúdo | Gerado em |
|---|---|---|
| `research.md` | Decisões técnicas (Decisão / Justificativa / Alternativas) | Fase 0 |
| `data-model.md` | Entidades, campos, relações, transições de estado | Fase 1 |
| `contracts/` | Contratos de interface externa (API/schema/CLI) — só se houver | Fase 1 |
| `quickstart.md` | Cenários de validação executáveis (sem código de implementação) | Fase 1 |
| `tasks.md` | Decomposição em tarefas | `/squad-tasks` (próximo passo) |

## 5. Fase 0 — Pesquisa

<!-- Resolve TODOS os [PRECISA-CLARIFICAR] do contexto técnico. Cada decisão: o que, por quê, alternativas. -->

| Questão | Decisão | Justificativa (sob P1>P2>P3) | Alternativas rejeitadas |
|---|---|---|---|
| [tema] | [escolha] | [por quê] | [o que não escolhemos e por quê] |

## 6. Fase 1 — Design

<!-- Detalhe modelo de dados e contratos. SEM código de implementação — isso é a fase de tasks/implement. -->

- **Modelo de dados:** [resumo + ponteiro para `data-model.md`; alinhar com DBML / `especialista-banco`].
- **Contratos:** [endpoints/schemas; ponteiro para `contracts/` e `templates/API_SPEC.md`].
- **Validação:** [cenários do `quickstart.md` que provam cada US do spec].

## 7. Rastreio de Complexidade

<!-- Preencher SOMENTE se a Verificação da Constituição teve violação a justificar. Senão, escreva "Nenhuma". -->

| Violação | Por que é necessária | Alternativa mais simples rejeitada porque |
|---|---|---|
| [ex.: 2º serviço separado] | [requisito que força] | [por que o monólito modular não atende] |

## 8. Re-verificação da Constituição (pós-design)

- [ ] O design da Fase 1 manteve a conformidade da §3
- [ ] Nenhuma complexidade nova entrou sem registro na §7
- [ ] Pronto para `/squad-tasks` e GATE 1

## Histórico de Revisões

| Versão | Data | Autor | Mudança |
|---|---|---|---|
| 0.1.0 | [AAAA-MM-DD] | arquiteto-minimalista | Criação inicial |
