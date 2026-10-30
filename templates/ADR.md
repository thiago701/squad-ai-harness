# ADR-NNN — [Título Curto da Decisão]

<!--
  ARCHITECTURE DECISION RECORD (ADR)
  Quando usar: toda decisão arquitetural difícil de reverter (banco, framework, protocolo,
  estratégia de deploy, padrão estrutural). Decisões triviais NÃO precisam de ADR.
  Quem preenche: quem propõe a decisão (agente ou humano); Tech Lead aprova.
  Formato: CURTO. Um ADR deve ser lido em menos de 5 minutos.
  Numeração: sequencial, imutável (ADR-001, ADR-002...). ADR aceito nunca é editado —
  se a decisão mudar, crie um novo ADR que SUPERA este.
  Nome do arquivo: ADR-NNN-titulo-em-kebab-case.md
-->

| Campo | Valor |
|---|---|
| **Projeto** | [Nome do Projeto] |
| **ADR** | ADR-[NNN] |
| **Data** | [AAAA-MM-DD] |
| **Autor(es)** | [Nome / Agente] |
| **Status** | [Proposto \| Aceito \| Rejeitado \| Obsoleto \| Superado por ADR-XXX] |
| **Decisores** | [quem aprova — humano(s)] |

---

## Contexto

<!-- Que problema ou força motivou esta decisão? Quais restrições existem
     (prazo, custo, equipe, requisitos do PRD, prioridades P1>P2>P3)?
     2 a 4 parágrafos no máximo. Quem ler daqui a 2 anos precisa entender o cenário. -->

[Descreva o contexto: o problema, as restrições e por que uma decisão é necessária agora.]

## Decisão

<!-- A decisão em si, em voz ativa e afirmativa: "Usaremos X para Y porque Z."
     Uma decisão por ADR. Se há duas decisões, são dois ADRs. -->

**Decidimos:** [Usaremos X para Y.]

**Justificativa resumida:** [1-2 frases ancoradas nas prioridades P1-Simplicidade > P2-Performance > P3-CustoBaixo.]

## Alternativas Consideradas

<!-- Mínimo 2 alternativas além da escolhida (incluindo "não fazer nada", se aplicável).
     Seja honesto com os prós das alternativas rejeitadas. -->

### Opção A — [Escolhida: nome da opção]

| Prós | Contras |
|---|---|
| [pró 1] | [contra 1] |
| [pró 2] | [contra 2] |

### Opção B — [nome da opção]

| Prós | Contras |
|---|---|
| [pró 1] | [contra 1] |
| [pró 2] | [contra 2] |

**Por que foi rejeitada:** [motivo objetivo.]

### Opção C — [nome da opção / "não fazer nada"]

| Prós | Contras |
|---|---|
| [pró 1] | [contra 1] |

**Por que foi rejeitada:** [motivo objetivo.]

## Consequências

<!-- O que muda com esta decisão — positivo E negativo. Consequências negativas omitidas
     viram dívida técnica invisível. -->

### Positivas

- [consequência positiva 1]
- [consequência positiva 2]

### Negativas / Riscos Assumidos

- [consequência negativa 1 — e como será monitorada/mitigada]
- [consequência negativa 2]

## Custo da Reversão

<!-- Se esta decisão se mostrar errada, quanto custa voltar atrás?
     Classifique: Baixo (dias) / Médio (semanas) / Alto (meses ou reescrita). -->

| Aspecto | Avaliação |
|---|---|
| **Classificação** | [Baixo \| Médio \| Alto] |
| **O que precisaria mudar** | [código, dados, infra, contratos] |
| **Estimativa de esforço** | [ex.: 2 semanas de 1 dev] |
| **Sinal de alerta para reverter** | [métrica/situação que indicaria erro da decisão] |

## Smoke Test — ADR vivo (R4)

<!--
  ADR VIVO: liga a decisão a uma ASSERÇÃO EXECUTÁVEL que falha se a decisão for violada no código.
  Use um oráculo que JÁ roda (ArchUnit, JaCoCo, teste de SLA, OWASP dep-check) — não crie infra nova.
  Nem todo ADR é testável: decisão puramente contextual (ex.: "Aurora por custo") deixa este bloco como N/A.
  O verificacao-loop (fase opcional "ADRs vivos") roda o `valida_em` e reporta; violação = 🔴 bloqueante.
-->

| Campo | Valor |
|---|---|
| **smoke_test** | [nome da asserção, ex.: ArchUnit `DomainHasNoFrameworkDependency`  \|  N/A] |
| **tipo** | [estrutural (ArchUnit) \| performance (teste de SLA) \| segurança (dep-check/scanner) \| N/A] |
| **valida_em** | [comando que roda o oráculo, ex.: `mvn -q test -Dtest=ArchitectureTest`] |
| **se_falhar** | A decisão foi violada → 🔴 bloqueante até reverter ou emitir ADR que SUPERA este. |

> **Ligação com os gates:** quando preenchido, este smoke test vira um critério `auto` de
> `fase-gates.yaml` (R1) e roda no `verificacao-loop` (R4). Decisão arquitetural não é só prosa
> num doc — é uma asserção que o build defende (princípio AI-Native: restrição executável).

## Referências

<!-- Links que embasaram a decisão: docs oficiais, benchmarks, ADRs relacionados, discussões. -->

- [PRD relacionado](./PRD.md)
- [ADR relacionado: ADR-XXX](./ADR-XXX-titulo.md)
- [Documentação/benchmark externo](https://exemplo.com)

---

## Histórico

| Data | Evento |
|---|---|
| [AAAA-MM-DD] | Proposto por [autor] |
| [AAAA-MM-DD] | [Aceito/Rejeitado] por [decisor] |
