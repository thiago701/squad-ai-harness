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

## Ambiente de desenvolvimento e Trava Exclusiva Go (`Go-Exclusive Lock`)

- **Linguagem Exclusiva do Harness:** **Go 1.24.3+ (`CGO_ENABLED=0`, zero dependências externas no `go.mod`)**.
- **Proibido misturar outras linguagens no fonte do harness:** O gate `stage1.go_exclusive_lock` e os hooks `PreToolUse`/`PostToolUse` bloqueiam automaticamente qualquer arquivo `.py`, `.js`, `.ts`, `.java`, `.rs`, `.cs`, `.ps1`, `.sh`, `package.json`, `pyproject.toml` ou `requirements.txt` fora dos catálogos passivos (`skills/` e `templates/`).
- Rode os checks locais antes do PR: `go vet ./...`, `go test ./...` e `.\squad-harness.exe gate`.

## O que não fazer

- Não reescreva história Git nem sobrescreva config crítica sem backup (Immutability).
- Não faça merge direto em `master`.
- Não introduza dependência de naming interno ou conhecimento tácito — skills devem ser ativáveis em qualquer projeto.
- Não trate input externo como confiável.
