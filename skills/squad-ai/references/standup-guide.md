# Standup — Formato Yesterday / Today / Blockers

> Absorvido de `engineering:standup`. Formato leve para **atualização diária assíncrona** a partir de atividade agregada (commits, PRs, tickets, incidentes). Complementa o ciclo SDLC da squad-ai sem introduzir cerimônia nova — funciona tanto em standup presencial quanto em thread assíncrona.

## Por que existe

- Sincroniza time em 2 min sem reunião de 30 min.
- Força explicitar **bloqueio** cedo — problema 24h parado é problema 48h caro.
- Liga commits dispersos a trabalho em andamento (card no board, PR em review).
- Extraível de histórico (git log + PR tracker + ticket system) sem escrever do zero todo dia.

## Formato canônico

```markdown
**Ontem:**
- [concluído] <verb no passado> <entrega objetiva> [link PR/ticket]
- [em progresso] <verb no passado> <o que avançou> [link]

**Hoje:**
- <verb no infinitivo> <entrega objetiva planejada> [link]

**Bloqueios:**
- <descrição objetiva + quem pode destravar + desde quando> — ou "Nenhum."
```

**Regras de redação:**

- **Verbo no início** ("Fechei", "Revisei", "Merguei", "Investiguei").
- **Outcome > atividade** — "fechei #123 (bug X resolvido)" > "trabalhei no #123".
- **1 linha por item**. Ficou em 3 linhas? é PR description, não standup.
- **Linkar card/PR** — destravadores conseguem contexto sem perguntar.
- **Bloqueio obrigatório** — "Nenhum" é resposta válida; ausência da seção não é.

## Bons exemplos

```
**Ontem:**
- Merguei #142 (Outbox poller agora idempotente com Postgres advisory lock)
- Revisei PR #145 do @fulano (CQRS read-model para /pedidos/:id)

**Hoje:**
- Fechar #150 (migração Flyway V7 — tabela outbox.processed_events)
- Pair com @fulana na spike de StructuredTaskScope para fan-out Bedrock

**Bloqueios:**
- Aguardando aprovação do ADR-0007 (Aurora DSQL adoption) desde 3d — @tech-lead
```

## Maus exemplos

```
**Ontem:** trabalhei no projeto ❌  (nada específico)
**Hoje:** várias coisas ❌  (nada específico)
**Bloqueios:** N/A ❌  (omitir bloqueio real é o pior crime do standup)
```

## Auto-geração (modo supercharged)

Quando a squad roda com tooling conectado, o standup pode ser **pré-preenchido** a partir de:

- **Git:** `git log --author=$ME --since=yesterday --oneline` → candidatos de "Ontem".
- **PRs:** tracker (GitHub/GitLab/Bitbucket) — PRs abertos, fechados, revisados nas últimas 24h.
- **Tickets:** board (Jira/Linear/Asana) — cards movidos In Progress → Done, comentários próprios.
- **Incidentes:** canal `#inc-*` — participação em incidente conta como "Ontem".
- **CI:** builds em que a pessoa foi autor ou revisor nas últimas 24h.

**Processo:**
1. Ferramenta agrega atividade das últimas 24h.
2. Agente gera draft no formato canônico.
3. Pessoa revisa, ajusta "Hoje" e "Bloqueios" (que não vêm do histórico).
4. Publica na thread do canal antes do horário combinado.

Tempo alvo: ≤ 2 minutos de leitura/ajuste por pessoa.

## Integração com os artefatos da squad

| Item do standup | Origem canônica | Link esperado |
|---|---|---|
| Commit/PR citado | repo | `<org>/<repo>/pull/NNN` |
| Card movido | board | `BOARD-NNN` |
| Incidente participado | `#inc-*` channel | `INC-YYYY-MM-DD-slug` |
| ADR proposto/aprovado | `.agent/skills/squad-ai/.antigravity/equipe/decisoes/` | `ADR-NNNN` |
| Bug corrigido com Debug Report | `docs/debug/INC-NNN.md` | `INC-NNN` |

## Sinais de saúde

- ✅ Standup em ≤ 5 min (assíncrono) ou ≤ 10 min (síncrono) para time de 6-8.
- ✅ Bloqueios destravados em ≤ 24h em média.
- ✅ "Ontem" sempre tem link — rastreável.
- ❌ Mesma linha de "Hoje" aparecendo 3 dias seguidos sem progresso — sinal de bloqueio não declarado.
- ❌ Standup vira status report para gerência em vez de sincronização entre pares.

## Anti-padrões

- **Relatório de horas** — standup não é folha-ponto.
- **Discussão técnica no standup** — agenda thread separada para debate.
- **Pular quando "não tem nada" ** — dia sem progresso é sinal; reporte o bloqueio.
- **Copiar de ontem** — indica time parado ou ausência de planejamento.
- **Cerimônia de 30 min para 8 pessoas** — 3 min/pessoa é teto. Excedeu = abre follow-up.

## Relacionadas

- [[Documentation 5 Tipos]] — standup é comunicação, não documentação — não vira doc permanente.
- [[Incident Response]] — participação em incidente conta como item do standup.
- [[Debug 4 Fases]] — debug em progresso aparece em "Hoje" com link.
- `squad-ai/steps/step-05-review.md` — PRs em review/merge são conteúdo natural do standup.

#conceito #standup #processo #squad-ai #v8-3
