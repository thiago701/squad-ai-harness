# ADR-001 — [SUPERSEDED por ADR-002]

> **ATENCAO:** Este arquivo foi superseded pelo ADR-002. Ver:
> [`ADR-002-adotar-spec-kit.md`](ADR-002-adotar-spec-kit.md)
> Mantido apenas porque o filesystem NTFS nao permite delecao; NAO usar como referencia.

| Campo | Valor |
|---|---|
| **Projeto** | Squad AI Skill-Orchestrator |
| **ADR** | ADR-001 (spec-kit) — SUPERSEDED |
| **Data** | 2026-06-20 |
| **Autor(es)** | Squad AI (agente) |
| **Status** | Superseded por ADR-002 |
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

### Opção A — [Escolhida] spec-kit fino que reusa os gates existentes
| Prós | Contras |
|---|---|
| Zero infra nova; reusa pytest/scan-secrets/judge | Um diretorio e um comando a manter |
| Design pre-codigo vira GATE 1 countable | Curva de adocao do OPENDESIGN.md |

### Opção B — Embutir o loop dentro do squad-pipeline existente
| Prós | Contras |
|---|---|
| Nenhum artefato novo | Incha o pipeline; mistura orquestracao com auditoria |

**Por que foi rejeitada:** acoplaria 5 vetores ao pipeline gigante, contra P1 (separar papeis).

### Opção C — Não fazer nada (manter implicito)
| Prós | Contras |
|---|---|
| Custo zero | Design pre-codigo e auditoria multi-vetor seguem informais, nao-gated |

**Por que foi rejeitada:** perde a forca do "design antes de codigo" e da auditoria como gate.

## Consequências

### Positivas
- GATE 1 passa a exigir spec preenchida (design antes de codigo).
- Auditoria multi-vetor padronizada (5 angulos distintos de falha), com severidade e prova.
- Metricas reais por wave alimentam o ReasoningBank (laco R2).

### Negativas / Riscos Assumidos
- Mais um comando/diretorio para manter — mitigado por ser fino e reusar gates (sem runtime novo).
- OPENDESIGN.md mal preenchido degrada o GATE 1 — mitigado pelo checklist do GUIDE e pelo guard-eval.

## Custo da Reversão

| Aspecto | Avaliação |
|---|---|
| **Classificação** | Baixo (dias) |
| **O que precisaria mudar** | remover `squad-ai/spec-kit/`, o comando `/squad-wave` e o §5 do ATTRIBUTIONS |
| **Estimativa de esforço** | < 1 dia |
| **Sinal de alerta para reverter** | `/squad-wave` sem uso real apos N ciclos; ou os vetores duplicando o que pytest/CAP/judge ja fazem |

## Smoke Test — ADR vivo (R4)

| Campo | Valor |
|---|---|
| **smoke_test** | `wave-runner.ps1` roda (plan/record/DEFERRED) + `/squad-wave` tem evals + `auditoria_skills.py` 24/24 (spec-kit excluido) |
| **tipo** | estrutural (scripts/gates do ecossistema) |
| **valida_em** | `python -m pytest -q && python scripts/auditoria_skills.py` + execucao do `wave-runner.ps1` |
| **se_falhar** | a integracao do spec-kit regrediu → 🔴 bloqueante ate corrigir |

## Referências

- [Atribuição §5 — OpenDesign/Build-Audit-Fix](../../docs/ATTRIBUTIONS.md)
- [README dos 5 vetores](audit-vectors/README.md)
- [Guia do OpenDesign](opendesign/OPENDESIGN-GUIDE.md)

---

## Histórico

| Data | Evento |
|---|---|
| 2026-06-20 | Proposto e Aceito (spec-kit implementado e integrado) |
