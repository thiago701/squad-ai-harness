# OpenDesign — Guia de Preenchimento

Como preencher o `OPENDESIGN.md` e o que conta como **"pronto para build"**. O OpenDesign
e a fonte-de-verdade que o `/squad-wave` le no **GATE 1**: design antes de codigo, spec
antes de build. Sem ele preenchido, o build nao comeca (o agente para e pede preenchimento).

## Por que design pre-codigo

O custo de um erro cresce do design ao deploy. Uma invariante esquecida na spec vira
retrabalho na auditoria. O OpenDesign forca as decisoes dificeis (escopo, invariantes,
non-goals) para **antes** de gastar tokens em build — alinhado a P1-Simplicidade (menos
partes moveis) e ao AI-Native (cada decisao humana vira restricao executavel).

## Secao a secao

| Secao | O que e bom | Erro comum |
|---|---|---|
| **1. Objetivo** | 2 frases sobre o PROBLEMA | descrever a solucao em vez do problema |
| **2. Bounded Context** | fronteira explicita dentro/fora | "fora" vazio (tudo vira escopo) |
| **3. Regras de Negocio** | invariantes testaveis, numeradas (RN1..) | regra vaga que nao vira assercao |
| **4. Non-Goals** | o que NAO se faz + porque | omitir — vira escopo silencioso |
| **5. Criterios de Aceite** | AC verificavel por maquina + gate SPARC | AC subjetivo ("deve ser rapido") |
| **6. Stack & Constraints** | stack mandatoria + restricoes do ecossistema | esquecer P1>P2>P3 e ASCII-only |

### Regras de Negocio (RN) — testaveis
Cada RN deve poder virar uma assercao que a **auditoria de fidelidade** (`audit-vectors/fidelity.md`)
consegue procurar por grep/teste. Ruim: "o sistema deve ser seguro". Bom: "RN3 — toda
query parametrizada (zero concatenacao de string em SQL)".

### Criterios de Aceite (AC) — verificaveis e ligados ao gate
Cada AC referencia um gate de `squad-ai/fase-gates.yaml` (G1.x..G5.x). O AC e o **como
verificar** (comando/teste/grep), nao a impressao. Ruim: "AC-1 funciona bem". Bom:
"AC-1 — `pytest tests/test_x.py` verde; gate G4.2 (cobertura >= 80% no dominio)".

### Non-Goals — viram grep
Cada Non-Goal e checado pela fidelidade: se o conceito proibido aparece no codigo, e um
achado (o escopo vazou). Ex.: NG1 "sem cache distribuido" → a auditoria faz grep por
`redis`/`memcached` e flaga se aparecer sem ADR.

## Checklist de "Pronto-para-build" (GATE 1)

- [ ] Secoes 1-6 preenchidas — **zero placeholders `[...]`** restantes.
- [ ] Objetivo em <= 2 frases, focado no problema.
- [ ] Bounded Context com **dentro E fora** preenchidos.
- [ ] **>= 1 RN** numerada e testavel.
- [ ] **>= 1 AC** verificavel, com **gate SPARC** (G1.x..G5.x) mapeado.
- [ ] Non-Goals explicitos (>= 1).
- [ ] Constraints incluem P1>P2>P3 e ASCII-only (se houver `.ps1`/`.sh`).
- [ ] Status = **Pronto-para-build**.

> Se qualquer item falha, o `/squad-wave` **para no GATE 1** e devolve o checklist —
> nao executa build sobre spec incompleta (gated, nao autonomo).
