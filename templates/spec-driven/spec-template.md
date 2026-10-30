# spec.md — Especificação de Feature: [NOME DA FEATURE]

> **Origin:** `squad-ai | adaptado-de-spec-kit` · Primeiro vértice do contrato **spec → plan → tasks**.
> **Arbitragem:** P1‑Simplicidade > P2‑Performance > P3‑CustoBaixo · Segurança é cláusula pétrea.

<!--
  ESPECIFICAÇÃO DE FEATURE (spec.md).
  Quando usar: no início de qualquer feature standard/large, ANTES do plano técnico (regra N6).
  Quem preenche: engenheiro-especificacao (humano valida). Refinado por /squad-clarify (Onda 2).
  Regra de ouro: descreva o QUÊ e o PORQUÊ. NUNCA o COMO (stack, libs, schema) — isso é o plan.md.
  Máximo de 3 marcadores [PRECISA-CLARIFICAR] abertos. Priorize: escopo > segurança/privacidade > UX > técnico.
  O que não dá para perguntar com baixo risco, vire Premissa (§4) — não pergunte o óbvio.
-->

| Campo | Valor |
|---|---|
| **Feature** | [nome curto, 2–4 palavras] |
| **Diretório** | `specs/[NNN-slug-da-feature]/` |
| **Data** | [AAAA-MM-DD] |
| **Autor(es)** | engenheiro-especificacao + [humano] |
| **Status** | [Rascunho \| Clarificado \| Pronto p/ Plano \| Obsoleto] |
| **PRD base** | [link para `templates/PRD.md` preenchido, se houver] |
| **Constituição** | AGENTS.md v[X.Y.Z] |

---

## 1. Cenários de Usuário e Testes *(obrigatório)*

<!-- User stories PRIORIZADAS (P1/P2/P3). Cada uma é uma fatia de MVP INDEPENDENTEMENTE TESTÁVEL:
     desenvolvível, testável, entregável e demonstrável sozinha. A P1 é a fatia mínima que já entrega valor. -->

### US1 — [título da história] (Prioridade: P1) 🎯 MVP

Como [ator], quero [ação], para [benefício].

- **Por que esta prioridade:** [o valor que justifica ser P1.]
- **Teste independente:** [como validar esta história sozinha, sem as demais.]

**Cenários de Aceitação:**

1. **Dado** [contexto inicial], **Quando** [ação], **Então** [resultado observável].
2. **Dado** [...], **Quando** [...], **Então** [...].

### US2 — [título] (Prioridade: P2)

Como [ator], quero [ação], para [benefício].

- **Por que esta prioridade:** [...]
- **Teste independente:** [...]

**Cenários de Aceitação:**

1. **Dado** [...], **Quando** [...], **Então** [...].

### Casos de Borda (Edge Cases)

- O que acontece quando [condição de limite]?
- Como o sistema reage a [entrada inválida / falha de dependência externa]?

## 2. Requisitos *(obrigatório)*

### 2.1 Requisitos Funcionais

<!-- Testáveis e não-ambíguos. Use "O sistema DEVE...". Marque incertezas com [PRECISA-CLARIFICAR: ...]. -->

| ID | Requisito | Rastreia |
|---|---|---|
| RF-001 | O sistema DEVE [comportamento observável e testável]. | US1 |
| RF-002 | O sistema DEVE [...]. [PRECISA-CLARIFICAR: qual a política de retenção?] | US1 |
| RF-003 | O sistema DEVE [...]. | US2 |

### 2.2 Regras de Negócio *(opcional — herdadas do engenheiro-especificacao)*

| ID | Regra | Tipo | Fonte |
|---|---|---|---|
| RN-001 | [enunciado da regra] | [Restrição \| Derivação \| Ação \| Permissão] | [origem] |

### 2.3 Entidades-Chave *(incluir se a feature envolve dados)*

| Entidade | Descrição | Atributos principais | Relações |
|---|---|---|---|
| [Entidade] | [o que representa] | [campos] | [com quem se relaciona] |

### 2.4 Requisitos Não-Funcionais

<!-- Quantifique sempre. Lembre da arbitragem: simplicidade vence performance, salvo SLA explícito. -->

| ID | Categoria | Requisito | Como medir |
|---|---|---|---|
| RNF-001 | Performance | [meta quantificada — ou "N/A; P1 prevalece"] | [APM / k6] |
| RNF-002 | Segurança | [conformidade OWASP / LGPD] | `SECURITY_REVIEW.md` |

## 3. Critérios de Sucesso *(obrigatório)*

<!-- MENSURÁVEIS e AGNÓSTICOS de tecnologia.
     ❌ "resposta da API < 200ms" (isso é RNF/implementação).
     ✅ "o usuário conclui o cadastro em menos de 1 minuto".
     KPIs de longo prazo pós-lançamento ficam no PRD, não aqui. -->

| ID | Critério mensurável | Como medir |
|---|---|---|
| CS-001 | [resultado observável pelo usuário, com número] | [método] |
| CS-002 | [...] | [...] |

## 4. Premissas

<!-- Decisões assumidas como verdade (substituem perguntas de baixo risco). Documente em vez de perguntar. -->

- [Premissa 1 — ex.: a autenticação reusa o SSO corporativo já existente.]
- [Premissa 2]

## 5. Clarifications

<!-- Seção mantida por /squad-clarify (Onda 2). Cada sessão registra perguntas resolvidas;
     a resposta é aplicada na seção afetada acima e referenciada aqui. -->

### Sessão [AAAA-MM-DD]

- Q: [pergunta] → A: [resposta]

## 6. Checklist de Qualidade do Spec

<!-- "Unit tests for English": validam a QUALIDADE DOS REQUISITOS, não a implementação.
     Marque [x] só quando o spec satisfaz. /squad-analyze e /squad-checklist (Onda 2/3) reavaliam. -->

**Qualidade de conteúdo**

- [ ] Nenhum detalhe de implementação (stack, lib, schema) vazou para o spec
- [ ] Foco no quê/porquê; o como ficou para o `plan.md`
- [ ] Escrito de forma compreensível para leitores de negócio

**Completude dos requisitos**

- [ ] Nenhum `[PRECISA-CLARIFICAR]` aberto (ou ≤3, cada um justificado)
- [ ] Todo RF é testável e não-ambíguo
- [ ] Todo critério de sucesso (CS) é mensurável e agnóstico de tecnologia
- [ ] Toda US tem teste independente e cenários Dado/Quando/Então

**Prontidão da feature**

- [ ] Toda US tem prioridade (P1/P2/P3) e a P1 é uma fatia de MVP
- [ ] Casos de borda mapeados
- [ ] ≥80% dos requisitos rastreiam a uma US

## Histórico de Revisões

| Versão | Data | Autor | Mudança |
|---|---|---|---|
| 0.1.0 | [AAAA-MM-DD] | engenheiro-especificacao | Criação inicial |
