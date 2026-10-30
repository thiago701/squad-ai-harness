# Artefatos SDD e mapeamento ao pipeline gated

> Reference carregada sob demanda. Convenção de **artefatos Spec-Driven Development (SDD)** —
> inspirada em GitHub Spec Kit + AWS Kiro — sobre o **backbone gated que já existe** neste motor.
> O `squad-pipeline` **não muda**: esta reference só nomeia os artefatos por feature, mapeia as
> fases SDD às fases/gates existentes, e descreve como wirar os 2 skills novos. Âncoras:
> `docs/skills/sdd-skill-architecture.md` (§A–C) e `docs/workflows/sdd-development-loop.md` (loop completo).

## 1. Convenção de artefatos — `specs/<feature>/`

Cada feature versiona seus artefatos SDD em `specs/<feature-id>/` (separado do handoff operacional do
motor em `.claude/pipeline/<slug>/`: o primeiro é a **spec viva** por feature; o segundo é o handoff
por fase). Os artefatos:

| Artefato | O que é | Quem produz | Fase SDD |
|---|---|---|---|
| `constitution.md` | Princípios/constraints do projeto (P1>P2>P3 + DoD) que **ancoram toda fase** (Spec Kit constitution / Kiro steering) | rascunho no Intake; refinado pelos arquitetos | 0–1 |
| `SPEC_FREEZE_v1.md` | A spec **congelada**: visão, personas, jornadas, casos de uso, regras, requisitos (com ID), critérios de aceite, contratos esperados, DoD/DoQ | `engenheiro-especificacao` | 2 (GATE A) |
| `plan.md` | PRD curto → plano técnico → vertical slices; arquivos a tocar + deps | `arquiteto-minimalista` + `plan` | 4 |
| `tasks.md` | Tasks pequenas rastreáveis: caminho de arquivo exato + dependências + marca `[P]` paralelizável (estilo Spec Kit) | `plan` + motor (decomposição) | 4 |
| `traceability.md` | Matriz bidirecional requisito↔regra↔história↔API↔teste↔código↔evidência (cada ReqID → arquivo:linha + teste + critério + evidência) | 🆕 `traceability-matrix-builder` | 4 (atualizada em 5/6/7) |
| `drift-report.md` | Divergência spec×código+testes+docs: requisitos sem código/teste, operações de contrato sem teste, critérios sem assertion, **código não rastreado** (scope creep), tasks de correção | 🆕 `spec-code-drift-detector` | 7 (GATE B) |
| `delivery-evidence.md` | Specs atendidas, testes, cobertura, gates, retrabalho evitado, tempo antes×real, fator de aceleração | agregador sobre `verificacao-loop`+`tech-lead-review` | 8 |

## 2. Spec Freeze gate (GATE A) — nada de código antes da spec aprovada

**Regra inegociável:** **nenhuma implementação começa antes da aprovação do `SPEC_FREEZE_v1.md`**
(humana ou validação automática mínima da spec). Isto **não cria um gate novo** no motor: GATE A é o
**GATE 1 existente** (pós-plano) lido em modo SDD — a aprovação humana que já trava o avanço passa a
exigir, além do plano, que a **spec esteja congelada e os critérios de aceite sejam testáveis**.

- **Critério de saída de GATE A:** spec coerente · critérios de aceite testáveis · DoD definido · zero
  ambiguidade bloqueante aberta (clarify-gate da Fase 1).
- **Spec viva (estilo Kiro):** a spec **não** é imutável após o freeze — é a fonte de verdade. **Editar a
  spec regenera `tasks.md`** (e marca a matriz de rastreabilidade como suja). Mudança de escopo passa pela
  spec primeiro, nunca direto no código.

## 3. Mapeamento fases SDD → pipeline gated existente

O loop SDD (`docs/workflows/sdd-development-loop.md`) **não substitui** as fases do motor — mapeia sobre
elas. A lógica de fases/gates do `squad-pipeline` permanece intacta; o SDD adiciona só artefatos e o
wiring dos 2 skills novos:

| Fase SDD (workflow) | Fase/gate do `squad-pipeline` | Artefato SDD |
|---|---|---|
| 0 Intake | Fase 1 (Intake) + Step 0 (classificador) | `constitution.md` (rascunho) |
| 1 Discovery & Clarify | Fase 1 (`engenheiro-especificacao`) + clarify-gate | seção "Clarifications" |
| 2 **Spec Freeze** ═GATE A═ | **GATE 1** (pós-plano), lido como Spec Freeze | `SPEC_FREEZE_v1.md` |
| 3 Arquitetura & Contratos | Fase 3 (Plan) + arquitetos | ADRs + contratos (OpenAPI/AsyncAPI) |
| 4 Planning (vertical slices) | Fase 3/4 (Plan/Scaffold) | `plan.md` · `tasks.md` · **`traceability.md`** |
| 5 Testes-antes | Fase 5 (TDD, `especialista-qualidade`) | suíte rastreável ao ReqID |
| 6 Implementação agentic | Fase 4/5 (Build) + especialistas | código por slice |
| 7 Quality gates + drift ═GATE B═ | **GATE 2** (pré-commit) + gatilho de segurança | **`drift-report.md`** |
| 8 Evidência de entrega | Fase 6/7 (Review/Commit) | `delivery-evidence.md` |
| 9 Aprendizado | pós-pipeline (`memoria-sessao`, `cultivator`) | memória viva |

> GATE A = GATE 1 em modo Spec Freeze · GATE B = GATE 2 em modo drift+qualidade. **Dois gates humanos,
> não quatro** — os gates SDD são os gates existentes do motor com um critério de saída adicional.

## 4. Wiring dos 2 skills novos

### `traceability-matrix-builder` — Fase 4 (Planning)
- **Quando:** o motor o delega na **Fase 4 (Planning)**, após o plano e antes do Build; reroda para
  atualizar a matriz nas Fases 5/6/7.
- **Entrada/saída:** lê `SPEC_FREEZE` + `plan.md` + contratos + árvore de código/testes → escreve
  `specs/<feature>/traceability.md` (ReqID → arquivo:linha + teste + critério + evidência; lacunas explícitas).
- **Contrato de despacho** (protocolo "objetivo/aceite/formato" do motor): objetivo = rastrear cada
  requisito; aceite = 100% dos ReqIDs com linha na matriz; formato = `traceability.md`.
- **Pré-condição de GATE B:** matriz completa. Modelo sugerido `haiku` (busca/classificação).

### `spec-code-drift-detector` — Fase 7 / GATE B
- **Quando:** o motor o delega na **Fase 7 (Quality gates)**, **antes do GATE B (=GATE 2)**; também roda
  como hook pós-implementação de cada slice.
- **Entrada/saída:** lê `SPEC_FREEZE` + `traceability.md` + contratos + código/testes → escreve
  `specs/<feature>/drift-report.md` (itens órfãos nos dois sentidos + scope creep + tasks de correção).
  **Não conserta — gera tasks.**
- **Efeito no gate:** **bloqueia GATE B** se houver requisito sem código+teste rastreado, violação de
  contrato, ou drift não justificado. Mitigação gated (aprovador ≠ autor). Modelo sugerido `opus`.

> Ambos são **delegados pelo motor como qualquer especialista** (Fase → artefato → próxima fase lê o
> artefato). Não alteram a lógica de fases/gates — só ocupam um slot de delegação dentro das fases
> existentes e contribuem com a pré-condição/critério de saída do GATE correspondente.
