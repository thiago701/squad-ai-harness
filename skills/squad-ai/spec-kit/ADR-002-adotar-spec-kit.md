# ADR-002 — Adotar o spec-kit (OpenDesign + loop Build->Audit->Fix por waves)

| Campo | Valor |
|---|---|
| **Projeto** | Squad AI Skill-Orchestrator |
| **ADR** | ADR-002 (spec-kit) |
| **Data** | 2026-06-20 |
| **Autor(es)** | Squad AI (agente) |
| **Status** | Aceito |
| **Decisores** | thiago701 (humano) |

---

## Contexto

O ecossistema ja tem gates executaveis (`fase-gates.yaml`, `validate_skills.py`, `pytest`,
CAP), juiz independente (`/squad-judge`) e ReasoningBank. Falta um **fluxo padrao de
construcao por fatias** que force design antes de codigo e auditoria multi-vetor antes do
merge — hoje isso fica implicito no `squad-pipeline`. O workflow OpenDesign (Build->Audit->Fix
com 5 vetores) oferece esse formato. A restricao e nao introduzir over-engineering nem
duplicar o que ja existe (P1-Simplicidade; o CAP existe justamente para barrar drift).

## Decisao

**Decidimos:** adotar um `squad-ai/spec-kit/` com (1) **OpenDesign** lido no GATE 1, (2)
**waves** canonicas (`WAVE-SPEC.yaml` + `wave-runner.ps1`) e (3) **5 vetores de auditoria**,
orquestrados pelo comando `/squad-wave` — **reusando** scan-secrets, pytest, `/squad-judge`
e o ReasoningBank em vez de criar infra nova.

**Justificativa resumida:** torna explicito e gated o loop spec->build->audit->fix (P1: menos
ambiguidade, mais restricao executavel), sem novo runtime — os vetores apontam para gates que
ja rodam.

## Alternativas Consideradas

### Opcao A — [Escolhida] spec-kit fino que reusa os gates existentes
| Pros | Contras |
|---|---|
| Zero infra nova; reusa pytest/scan-secrets/judge | Um diretorio e um comando a manter |
| Design pre-codigo vira GATE 1 countable | Curva de adocao do OPENDESIGN.md |

### Opcao B — Embutir o loop dentro do squad-pipeline existente
| Pros | Contras |
|---|---|
| Nenhum artefato novo | Incha o pipeline; mistura orquestracao com auditoria |

**Por que foi rejeitada:** acoplaria 5 vetores ao pipeline gigante, contra P1 (separar papeis).

### Opcao C — Nao fazer nada (manter implicito)
| Pros | Contras |
|---|---|
| Custo zero | Design pre-codigo e auditoria multi-vetor seguem informais, nao-gated |

**Por que foi rejeitada:** perde a forca do "design antes de codigo" e da auditoria como gate.

## Consequencias

### Positivas
- GATE 1 passa a exigir spec preenchida (design antes de codigo).
- Auditoria multi-vetor padronizada (5 angulos distintos de falha), com severidade e prova.
- Metricas reais por wave alimentam o ReasoningBank (laco R2).

### Negativas / Riscos Assumidos
- Mais um comando/diretorio para manter — mitigado por ser fino e reusar gates (sem runtime novo).
- OPENDESIGN.md mal preenchido degrada o GATE 1 — mitigado pelo checklist do GUIDE e pelo guard-eval.

## Custo da Reversao

| Aspecto | Avaliacao |
|---|---|
| **Classificacao** | Baixo (dias) |
| **O que precisaria mudar** | remover `squad-ai/spec-kit/`, o comando `/squad-wave` e o SS5 do ATTRIBUTIONS |
| **Estimativa de esforco** | < 1 dia |
| **Sinal de alerta para reverter** | `/squad-wave` sem uso real apos N ciclos; ou os vetores duplicando o que pytest/CAP/judge ja fazem |

## Smoke Test — ADR vivo (R4)

| Campo | Valor |
|---|---|
| **smoke_test** | `wave-runner.ps1` roda (plan/record/DEFERRED) + `/squad-wave` tem evals + `auditoria_skills.py` 24/24 (spec-kit excluido) |
| **tipo** | estrutural (scripts/gates do ecossistema) |
| **valida_em** | `python -m pytest -q && python scripts/auditoria_skills.py` + execucao do `wave-runner.ps1` |
| **se_falhar** | a integracao do spec-kit regrediu -> bloqueante ate corrigir |

## Referencias

- [Atribuicao SS5 — OpenDesign/Build-Audit-Fix](../../docs/ATTRIBUTIONS.md)
- [README dos 5 vetores](audit-vectors/README.md)
- [Guia do OpenDesign](opendesign/OPENDESIGN-GUIDE.md)

---

## Historico

| Data | Evento |
|---|---|
| 2026-06-20 | Proposto e Aceito (spec-kit implementado e integrado) |
| 2026-06-20 | Renumerado de ADR-001 para ADR-002 (ADR-001 ja era citado no COMMAND_INDEX para a decisao Skills-First/PR5) |
