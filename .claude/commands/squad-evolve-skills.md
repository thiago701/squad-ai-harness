---
description: Aprendizado contínuo — destila lições em instintos YAML e evolui as skills a partir de evidências de uso (mensal).
argument-hint: [escopo: aprender <lição> | evoluir | consolidar memória]
origin: squad-ai
---

Você está executando o comando **/squad-evolve-skills** — fachada fina do módulo **Memory & Learning** (`aprendizado-continuo`).

Escopo: **$ARGUMENTS**

Invoque a skill **`aprendizado-continuo`** e conduza a evolução por evidências:

1. **`/aprender` (manual, pontual):** ao captar uma lição (uma correção do usuário, uma resolução de erro, um padrão que funcionou), destile-a em um **instinto** YAML atômico em `memory/instintos/`: `trigger`, `confidence` (0.3–0.9), `domain`, `scope` (projeto/global) e `evidence`. Um instinto = um arquivo.
2. **`/evoluir` (mensal):** consolide os instintos acumulados, promova os de alta confiança a padrões institucionais, rebaixe/aposente os que não se confirmaram, e proponha edições nas SKILL.md correspondentes — **sempre com evidência**, nunca por achismo.
3. **Consolidar memória:** mescle ADRs e resumos de sessão duplicados, atualize o índice da memória, pode o que ficou obsoleto.
4. **Sem observer daemon.** A evolução é deliberada e gated — não há processo rodando em background coletando tudo (complexidade alta evitada por P1).

**Regra:** toda mudança em skill proposta aqui passa por **/squad-review** antes de ser aplicada. Evals devem acompanhar a evolução (with/without skill) para detectar regressão de prompt.

**Entrega:** instintos criados/atualizados + proposta de evolução de skills com evidência + memória consolidada.
