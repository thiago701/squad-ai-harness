# OpenDesign — [Nome do Projeto]

<!--
  TEMPLATE de design PRE-CODIGO do Squad AI spec-kit. Preencha ANTES de qualquer build.
  E o artefato lido no GATE 1 do /squad-wave: sem este doc preenchido, o build NAO comeca.
  Como preencher e o que conta como "pronto": ver OPENDESIGN-GUIDE.md.
  Disciplina: P1-Simplicidade > P2-Performance > P3-CustoBaixo. Gated, nao autonomo.
-->

| Campo | Valor |
|---|---|
| **Projeto** | [nome] |
| **Data** | [AAAA-MM-DD] |
| **Autor(es)** | [agente / humano] |
| **Status** | [Rascunho \| Pronto-para-build \| Em-build \| Concluido] |

---

## 1. Objetivo

<!-- O que este projeto resolve, em no maximo 2 frases. Sem jargao de solucao; foco no problema. -->

[2 frases.]

## 2. Bounded Context

<!-- A fronteira explicita. O que esta DENTRO do escopo e o que esta FORA. -->

**Dentro:**
- [item dentro do escopo]

**Fora:**
- [item fora do escopo — delega a quem, ou fica para depois]

## 3. Regras de Negocio (invariantes)

<!-- Invariantes que o codigo DEVE preservar. Numeradas, testaveis, uma por linha.
     Cada RN deve poder virar uma assercao (a auditoria de fidelidade vai procurar por ela). -->

- **RN1** — [invariante]
- **RN2** — [invariante]

## 4. Non-Goals (o que NAO sera feito)

<!-- Explicito. Cada Non-Goal vira um grep da auditoria de fidelidade: se o conceito
     aparecer no codigo, e um achado (escopo vazou). -->

- **NG1** — [o que NAO sera feito] — [por que]
- **NG2** — [...]

## 5. Criterios de Aceite (verificaveis)

<!-- AC numerados, cada um VERIFICAVEL por maquina (teste, grep, comando), ligado ao gate
     SPARC correspondente em squad-ai/fase-gates.yaml (G1.x..G5.x). Sem AC subjetivo. -->

| AC | Criterio (verificavel) | Como verificar | Gate SPARC |
|---|---|---|---|
| **AC-1** | [criterio] | [comando/teste/grep] | [G1.x] |
| **AC-2** | [criterio] | [comando/teste/grep] | [G4.x] |

## 6. Stack & Constraints

<!-- Tecnologias mandatorias + restricoes do projeto. Inclua as restricoes do ecossistema. -->

**Stack mandatoria:**
- [ex.: Java 25 + Spring Boot 4 / Python 3.13 stdlib / ...]

**Restricoes (nao-negociaveis):**
- **P1 > P2 > P3** — Simplicidade > Performance > CustoBaixo.
- **ASCII-only** em `.ps1` e `.sh` (instinto-0004; PowerShell 5.1 le BOM-less como ANSI).
- **Gated, nao autonomo** — GATE 1 (pos-spec) e GATE 2 (pre-commit); seguranca nunca negociavel.
- [outras restricoes do projeto]

---

> **Pronto para build?** O `/squad-wave` so prossegue do GATE 1 quando: secoes 1-6 preenchidas
> (sem placeholders `[...]`), >=1 RN, >=1 AC com gate SPARC mapeado, Non-Goals explicitos.
> Checklist completo em `OPENDESIGN-GUIDE.md`.
