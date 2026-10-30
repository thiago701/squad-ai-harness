# Skills e código always-on (invariantes)

> **Pack:** comum (always-on) · **Origin:** `squad-ai`
> Destilação. O formato canônico vive em [`RULES.md §3`](../../RULES.md) e [`governance/padrao-skill.md`](../../governance/padrao-skill.md) (ADR-010). Não duplicar.

A capacidade nasce como **skill** (deep, on-demand); o comando é uma **fachada fina**. Estas regras são always-on.

## Invariantes

- **Skills-First.** Toda capacidade é uma skill auditável. O que um agente faz é o que está escrito numa skill,
  não em código oculto. Não reimplementar em prosa o que uma skill já faz.
- **Comando = fachada fina.** `/squad-*` é atalho que **invoca a skill** — corpo curto, sem reimplementar a lógica.
  A capacidade vive na skill; o comando só a aciona com o contexto certo.
- **`origin:` no frontmatter.** Toda skill/agente/comando declara `squad-ai | adaptado-de-ecc | community`.
  Origem ≠ `squad-ai` **exige** entrada em [`docs/ATTRIBUTIONS.md`](../../docs/ATTRIBUTIONS.md).
- **Hub + references para skills grandes.** O `SKILL.md` é hub enxuto (≤400 linhas); o conteúdo profundo vai
  para `references/`, carregado sob demanda. Hub barato; profundidade só quando precisa.
- **Least agency.** Cada skill/subagente recebe o **menor conjunto de ferramentas** que cumpre a missão
  (ver `seguranca.md`). Skills de leitura/análise não têm `Write`/`Edit`/`Bash`.
- **Execução incremental.** Entregar em fatias testáveis com checkpoints; nunca big-bang.
- **Cerimônia proporcional ao blast radius.** Tarefa **trivial** → **1 especialista direto**, sem orquestração.
  Não acionar todos os agentes para dúvida pontual: *agent soup* é desperdício de tokens (P3) e ruído.
- **Delegar com contexto, não só a pergunta.** Todo despacho carrega objetivo de negócio + critério de aceite +
  formato de retorno. O orquestrador **avalia o retorno** (não aceita cego), com no máximo 2 follow-ups.

> Regra de ouro: capacidade = skill; comando = atalho; ferramenta = a mínima que basta.
