# Como contribuir com o SquadAI Harness

Obrigado pelo interesse. O protocolo tem regras simples e inegociáveis — elas existem para manter o ecossistema confiável enquanto ele evolui.

## Princípios para qualquer contribuição

1. **Toda capacidade nasce como skill auditável** — não esconda comportamento em código solto (Agent-First / Skills-First).
2. **Mudança de comportamento vem com teste** — sem teste verde, não passa no gate (Test-Driven).
3. **Segurança é veto, não etapa final** — diffs que tocam auth/input/queries/cripto/secrets disparam auditoria automática (Security-First).
4. **Nada cruza um gate sem revisão humana** — *gated, not autonomous*.
5. **Arbitragem P1 > P2 > P3** — Simplicidade vence Performance, que vence Custo. Segurança está acima de todas.

## Fluxo de uma contribuição

```text
1. Abra uma issue descrevendo o problema/capacidade
2. Crie uma branch a partir de master:  feat/<descricao>  ou  fix/<descricao>
3. Implemente seguindo o template de skill (templates/skill-template.md)
4. Garanta os gates verdes: build, teste, segurança
5. Abra um Pull Request — nunca commite direto em master
6. Aguarde a revisão humana (gate G4)
```

## Padrão de commits

Usamos **Conventional Commits**:

```text
feat(skills): add <skill> for <capacidade>
fix(loops): corrige <bug> no harvester
docs(arch): atualiza diagrama de módulos
chore(core): ajusta quality gate G3
refactor(squad): extrai conductor para módulo próprio
```

## Estrutura de uma skill

Cada skill precisa do contrato completo (Nome, Propósito, Inputs, Outputs, Exemplos, Restrições, Critérios de qualidade, Checklist de revisão, Notas de evolução). Comece copiando `templates/skill-template.md`. Antes de criar, **verifique se uma skill existente já resolve o problema** — duplicação fere o princípio de não-conflito.

## Ambiente de desenvolvimento

- Python 3.13+ · Git
- O repositório suporta múltiplos clientes de IA (Claude Code, Codex, Windsurf, Devin) via configs versionadas. Use o que preferir; o comportamento canônico vive nas skills, não na IDE.
- Rode os checks locais antes do PR: testes (`pytest`) e lint (`ruff`).

## O que não fazer

- Não reescreva história Git nem sobrescreva config crítica sem backup (Immutability).
- Não faça merge direto em `master`.
- Não introduza dependência de naming interno ou conhecimento tácito — skills devem ser ativáveis em qualquer projeto.
- Não trate input externo como confiável.
