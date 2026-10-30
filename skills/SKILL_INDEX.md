# SKILL_INDEX — catálogo aposentado (ponteiro para o registry gerado)

> **Este arquivo deixou de ser o catálogo de skills da Squad** (ADR-010, aposentadoria executada
> por PR humano dedicado — o mecanismo previsto no `governance/protected-ruler.json`).
> **Não registre skills aqui.** A fonte única do catálogo é o **registry gerado do disco**:
>
> - `governance/registry/registry.json` — consolidado (`"fonte_unica": true`)
> - `governance/registry/skills-canonicas.json` · `skills-instaladas.json` · `agentes.json` ·
>   `comandos.json` — parciais curados (campos `model` / `tools` / `descricao_1l` / `has_references`)

## Como regenerar e checar

- **Regenerar do disco:** `python scripts/generate_registry.py` — escreve apenas o
  `registry.json` (`--write-parciais` sobrescreve os parciais curados e destrói os campos
  curados; evitar).
- **Gate de drift:** `python scripts/generate_registry.py --check` (exit 1 em divergência
  disco↔JSONs salvos) e `pytest tests/test_registry.py` (paridade Glob↔registry, independente
  do script).
- **Onde o gate roda:** bateria do Loop de Evolução V3 (`loops/v3/loop-evolucao-v3.md`, veto
  "Drift: 0") e `.github/workflows/registry-drift.yml` (CI — publicação pendente de token com
  escopo `workflow`).

## Para onde foi o conteúdo normativo que vivia aqui

| Conteúdo | Novo lar |
|---|---|
| Frontmatter canônico de skill, heurística de roteamento de modelo por custo e rubrica estrutural (limites de hub, description, references, evals) | `governance/padrao-skill.md` |
| Linha de Defesa de Prompt (texto canônico anti-prompt-injection) | `security/security-policy.md` |
| Checklist "como adicionar uma skill nova" e estados de status (ativa / a-refatorar / deprecated) | `governance/padrao-skill.md` |
| Catálogo por skill (quando usar / não usar, riscos, entradas/saídas) | o `SKILL.md` de cada skill (fonte primária) + parciais curados do registry (agregado) |
| Candidatas ECC (C1–C24), roadmap de adoção e dívidas históricas de drift | `docs/ecc-analysis-report.md` §7 (fonte original) + histórico git deste arquivo |

## Notas de compatibilidade

- Este arquivo permanece listado no `governance/protected-ruler.json` (mudança só por PR humano
  dedicado com ADR) e permanece existindo neste path como **sentinela de raiz de repositório**
  para ferramentas legadas (`loops/loop-harvester`, `loops/loop-cultivator`,
  `skills/squad-benchmark/scripts/coletar.py`) até a migração delas para o registry.
- O histórico integral do índice manual (catálogo 2026-06, Parte 2 ECC, apêndices) permanece no
  git: `git log --follow -- skills/SKILL_INDEX.md`.
