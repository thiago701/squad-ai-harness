# Git always-on (invariantes)

> **Pack:** comum (always-on) · **Origin:** `squad-ai`
> Destilação. O detalhe vive em [`AGENTS.md §6`](../../AGENTS.md) e [`RULES.md §2`](../../RULES.md). Não duplicar.

A Squad AI usa **Conventional Commits com descrição em PT-BR** (como o repositório já pratica).

```
<tipo>(<escopo>): <descrição imperativa curta em português>

[corpo opcional: o porquê da mudança, não o como]
```

## Invariantes

- **Tipos:** `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `build`, `ci`, `style`.
- **Escopo:** nome da skill ou módulo afetado — ex.: `feat(markitdown): …`, `chore(aws-lambda-java25-aot): …`.
- **Descrição:** imperativa, minúscula, em **português brasileiro**, **sem ponto final**.
- **Branch antes de mexer na default.** Estando em `master`, **criar branch antes** de qualquer commit.
- **Commitar/pushar só quando o humano pedir.** Não antecipar commit/push sem pedido explícito.
- **Coautoria obrigatória.** Toda mensagem termina com a linha de coautoria do agente que executou.
- **Sem pular guardrails.** Nunca `--no-verify`, nunca pular hooks/assinatura sem pedido explícito do humano.
- **Immutability.** Não reescrever história compartilhada; **novo commit** é preferível a `--amend`.
  Nada de `push --force` em branch compartilhada (é comando destrutivo — exige confirmação).
