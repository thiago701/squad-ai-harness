---
description: Roda o loop bug-debt-investigation definido em loops/bug-debt-investigation-loop.md — varre o repo, valida build/testes por stack, investiga bugs/débitos/riscos com evidência obrigatória e registra sem duplicata em docs/memoria/.
argument-hint: "[opcional: até=HH:MM foco=<módulo/stack>]"
---

Execute o loop especificado em `loops/bug-debt-investigation-loop.md` (raiz deste repositório).
Leia esse documento primeiro e siga os passos da volta exatamente.

Resumo do contrato: detecte a(s) stack(s) (Java/Maven em `app/`, Python na raiz + pacotes em
`loops/loop-cultivator` e `loops/loop-harvester`), rode as validações compatíveis (`mvnw.cmd -q
-B clean test`, `pytest -q`, `ruff check .`) — se o Bash tool estiver morto, use o workaround
documentado (canal `cmd` via `.claude/launch.json` + `preview_start`/`preview_logs`, comando
num `.cmd` no scratchpad terminando em `echo ---EXIT---%ERRORLEVEL%`). Investigue as fontes
obrigatórias (build/testes/cobertura/logs/TODO-FIXME reais/duplicação/tamanho excessivo/
acoplamento/segurança/dependências/config/drift doc↔código/performance/arquitetura/pipelines/
docs) via Grep/Glob/Read (paralelizável em subagentes read-only). ANTES de registrar qualquer
achado, releia `docs/memoria/{bugs,debitos-tecnicos,riscos-tecnicos,melhorias-recomendadas}.md`
— atualize item existente (nova evidência, severidade revista, ou `Reaberto`) em vez de
duplicar. Todo achado exige evidência mínima (trecho, comando, arquivo, teste); sem evidência,
descarte. Classifique em Bug | Débito técnico | Risco técnico | Melhoria recomendada, registre
com o template de `## [ID] Título` da spec, priorize, e anexe um `# Ciclo N` em
`docs/memoria/relatorio-investigacao-recursiva.md`. Nunca corrija de verdade, nunca commite —
só descoberta e registro. Se `até=HH:MM` foi passado e o horário local já foi atingido, gere o
Relatório Final (template no fim da spec) em vez de um ciclo incremental.

Inputs inline (se houver): $ARGUMENTS — `até` e `foco` são opcionais; sem eles, rode uma volta
balanceada sem corte de horário embutido (o corte só se aplica ao modo agendado).
