# Templates Spec-Driven — contrato `spec → plan → tasks` (aplicado · Ciclo 3)

> **Origin:** `squad-ai | adaptado-de-spec-kit` (GitHub spec-kit, Spec-Driven Development).
> **Status:** **aplicado** no Ciclo 3 (2026-06-16) — versão canônica dos 3 templates. A proposta-fonte
> (revisável) permanece em [`../../docs/propostas/onda-1-spec-driven/`](../../docs/propostas/onda-1-spec-driven/).
> **Não aplicado:** a *Emenda da Constituição* (versionamento de `AGENTS.md`/`RULES.md`) — é mudança de
> governança de maior risco e segue como proposta gated separada.

## O contrato

Um trio por feature, em `specs/NNN-<slug>/` (modelo Flow-Forward — artefatos imutáveis por ciclo):

| Arquivo | Papel | Vértice |
|---|---|---|
| `spec-template.md` | O quê/porquê: user stories `US`, requisitos `RF-`/`RNF-`, regras `RN-`, critérios `CS-`, `Dado/Quando/Então`, `[PRECISA-CLARIFICAR]` | 1 |
| `plan-template.md` | O como: Contexto Técnico + Verificação da Constituição (GATE) + Rastreio de Complexidade | 2 |
| `tasks-template.md` | Decomposição por US, marcador `[P]` (paralelizável), IDs `T001`, checkpoints, MVP | 3 |

## IDs e marcadores (padrão do contrato)

`RF-001` requisito funcional · `RNF-001` não-funcional · `CS-001` critério de sucesso mensurável ·
`RN-001` regra de negócio · `US1` user story · `T001` tarefa · `[P]` paralelizável ·
`[PRECISA-CLARIFICAR: …]` ambiguidade (máx. 3 no spec).

## Como liga aos gates (R1 + Ciclo 3 #6)

Estes IDs **alimentam diretamente** os critérios de saída da fase Discovery em
[`../../squad-ai/fase-gates.yaml`](../../squad-ai/fase-gates.yaml):

| Critério | Alimentado por |
|---|---|
| **G1.1** (≥3 cenários BDD por story) | `US` + `Dado/Quando/Então` do `spec.md` |
| **G1.2** (invariantes/regras) | `RN-` do `spec.md` |
| **G1.3** (NFRs com números) | `RNF-` do `spec.md` |
| **G1.4** (zero ambiguidade bloqueante) | `[PRECISA-CLARIFICAR]` do `spec.md` (máx. 3) |
| **G1.5** (rastreabilidade) | cada `T###` do `tasks.md` rastreia a um `RF-`/`US` |

Assim o `spec.md` vira insumo do **GATE 1** e o `tasks.md` rastreia até o **GATE 2** (`verificacao-loop`).
