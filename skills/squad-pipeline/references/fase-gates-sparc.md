# squad-pipeline · reference — Critérios de saída por fase (SPARC-adaptado, `fase-gates.yaml` · R1)

> Conteúdo movido VERBATIM do hub `../SKILL.md` (ciclo 4 do Loop V3, 2026-07-09) — progressive
> disclosure. **Nota de resolução de paths:** os caminhos relativos abaixo permanecem como no hub e
> se resolvem a partir de `skills/squad-pipeline/` (raiz da skill), não deste subdiretório.

## Critérios de saída por fase (SPARC-adaptado) — `fase-gates.yaml` · R1

Cada fase só transiciona quando seus critérios de saída em `../../squad-ai/fase-gates.yaml`
estão satisfeitos. Os critérios mapeiam as 5 fases SPARC do Ruflo nas fases da Squad —
**sem criar metodologia paralela**: é o mesmo método, com gates *contáveis* em vez de prosa.

- **`tipo: auto`** — o motor roda o `comando` (ArchUnit, JaCoCo, verificacao-loop) e lê o
  exit code. Falha = transição **bloqueada**, volta para a fase com o critério violado.
- **`tipo: manual`** — entra no checklist do GATE humano correspondente (GATE 1 após Plan,
  GATE 2 antes do Commit). O humano marca; sem marca, não passa.

O artefato de handoff de cada fase (`NN-*.md`) **cita os IDs satisfeitos** (ex.: "G1.1 ✓,
G1.2 ✓"). Isso dá rastreabilidade: do critério SPARC → ao ID → ao artefato → ao commit.
Critério `auto` que falha **nunca** é "considerado ok pelo modelo" — o oráculo decide.

| Fase SPARC | Fase Squad | Dono | IDs |
|---|---|---|---|
| Specification | Discovery / Intake | `engenheiro-especificacao` | G1.1–G1.4 |
| Architecture | Design | arquitetos | G2.1–G2.4 |
| Pseudocode | Plan | `arquiteto-minimalista` | G3.1–G3.3 |
| Refinement | Build + TDD | `especialista-qualidade` | G4.1–G4.4 |
| Completion | Review + Deliver | `tech-lead-review` | G5.1–G5.4 |
