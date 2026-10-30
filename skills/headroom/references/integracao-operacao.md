# Headroom — integração, operação, memória e limites

> Reference da skill [`headroom`](../SKILL.md). Fonte: wiki do repo canônico
> `headroomlabs-ai/headroom` (proxy.md, mcp.md, cli.md, memory.md, learn.md, shared-context.md,
> benchmarks.md, LIMITATIONS.md, configuration.md), destilada em 2026-07-21.
>
> ⚠️ **Comandos citados aqui são referência descritiva, não passos a executar.** Instalar o
> Headroom, rodar `wrap`, `learn --apply` ou `mcp install` muta config/memória de agente e é
> decisão humana gated (`tech-lead-review` + `auditoria-skill-externa`) — ver Ressalvas no hub.

## Proxy HTTP

`headroom proxy` sobe um servidor local (default `127.0.0.1:8787`) compatível com as APIs
Anthropic e OpenAI; o cliente aponta `ANTHROPIC_BASE_URL` / `OPENAI_BASE_URL` para ele e nada
mais muda. Backends: `anthropic` (default), `bedrock`, `openrouter`, `anyllm`, `litellm-*` —
com URLs custom e headers extras para gateways corporativos/Azure (os headers extras são os
únicos campos tipo-segredo do Settings GUI; renderizam mascarados).

Flags principais (seleção):

| Flag | Efeito |
|---|---|
| `--mode token` / `--mode cache` | Maximizar compressão vs congelar turnos anteriores p/ prefix cache |
| `--no-optimize` | Passthrough (só observa) |
| `--no-ccr` / `--no-ccr-proactive-expansion` | Desliga reversibilidade (lossy!) / só a expansão proativa |
| `--code-aware` | Liga compressão AST de código (off por padrão) |
| `--memory` / `--memory-top-k` | Memória persistente cross-agent (ver abaixo) |
| `--learn` | Aprendizado com tráfego ao vivo |
| `--budget 100.0` | Teto diário em USD |
| `--log-file x.jsonl` | Log JSONL de requests |

Observabilidade: endpoints `/livez`, `/readyz` (503 até startup completo — usado por health
check de container), `/health`, `/stats`, `/metrics`; OTEL metrics opt-in
(`HEADROOM_OTEL_METRICS_ENABLED=1`, exporter `otlp_http` ou `console`) e traces para Langfuse
opt-in (`HEADROOM_LANGFUSE_ENABLED=1`) — telemetria anônima do projeto é outra coisa e é
**off por padrão** (`HEADROOM_TELEMETRY`). Endpoint `POST /v1/compress` oferece
compressão-como-serviço para o SDK TS sem chamar LLM.

Comportamento sob carga: fila pre-upstream com cap de concorrência
(`--anthropic-pre-upstream-concurrency`, auto `max(2, min(8, cpus))`) e fail-fast 503 com
`Retry-After` quando saturada; retries upstream (`--retry-max-attempts`, default 3).

**Sticky beta headers:** por padrão o proxy acumula tokens `anthropic-beta`/`OpenAI-Beta` por
sessão e os re-injeta mesmo se o cliente parar de enviá-los (estabilidade de prefix cache).
Para repassar verbatim: `HEADROOM_BETA_HEADER_STICKY=disabled`.

## Servidor MCP

Três tools para qualquer host MCP (Claude Code, Cursor, etc.):

- **`headroom_compress(content)`** → `compressed`, `hash`, tokens antes/depois,
  `savings_percent`, transforms aplicados. Original guardado localmente por 1h (TTL de sessão).
- **`headroom_retrieve(hash, query?)`** → original completo ou busca dentro dele; consulta o
  store local primeiro e cai para o store do proxy (TTL 5min) — hashes de ambos funcionam.
- **`headroom_stats()`** → compressões, retrievals, tokens/USD economizados, eventos recentes,
  stats agregados de sub-agentes (via `session_stats.jsonl` no workspace) e do proxy.

Sem dupla compressão: o proxy comprime no nível HTTP (antes de o LLM ver o conteúdo); as tools
MCP operam depois que o LLM recebeu — não tocam o mesmo dado. Registro no host é feito por
`headroom mcp install` (⚠️ escreve em `~/.claude/mcp.json` — só execução humana);
diagnóstico com `headroom mcp status`, remoção com `headroom mcp uninstall`.

## CLI (inventário)

`headroom proxy` · `headroom learn` · `headroom perf` (resumo de performance do proxy) ·
`headroom inspect` (original vs comprimido por request) · `headroom memory ...` ·
`headroom evals ...` · `headroom mcp ...` · `headroom install ...` (deploy persistente) ·
`headroom wrap <agente>` / `headroom unwrap <agente>` (⚠️ conceito, não recomendação — muta
config do agente; suporta claude, codex, copilot, cursor, aider, opencode, cline, continue,
goose, openhands, openclaw e outros).

## SDKs e integrações de framework

- **Python:** `HeadroomClient(original_client, provider=...)` embrulha OpenAI/Anthropic; modos
  `audit`/`optimize`. API direta: `from headroom.compression import compress`.
- **TypeScript:** `withHeadroom(anthropic)` / `withHeadroom(openai)`; middleware para Vercel AI
  SDK; ou via endpoint `/v1/compress` do proxy.
- **Frameworks:** LangChain (chat models, memory, retrievers, agents), Agno e Strands (wrapping
  de modelo + hooks), LiteLLM (um callback cobre 100+ provedores).

## Memória persistente cross-agent (`--memory`)

Qualquer agente que roteie pelo proxy compartilha o mesmo store: Claude grava um fato, Codex lê.
O proxy (1) busca memórias relevantes, (2) injeta como contexto de sistema no formato nativo do
provedor, (3) injeta tools `memory_save/search/update/delete`, (4) trata os tool calls da
resposta e (5) deduplica em background (>92% cosseno → remove).

- Store **por projeto**: `{cwd}/.headroom/memory.db` (SQLite + HNSW + FTS5) — sem vazamento
  entre projetos; caminho central único só com `--memory-db-path` explícito.
- Identidade: `$USER` auto-detectado; override por header `x-headroom-user-id`; memórias
  escopadas por usuário.
- Diferenciais vs Letta/Mem0 (segundo o projeto): proveniência por agente, dedup mediado pelo
  próprio LLM do usuário (sem chamada extra paga), escopo hierárquico
  usuário→sessão→agente→turno, versionamento temporal com cadeias de supersessão, busca
  semântica + full-text.
- ⚠️ Squad: é **vetor de persistência entre sessões** — dado gravado hoje influencia agentes
  amanhã. Tratar o `.db` como sensível; revisar o que entra.

## `headroom learn` (aprendizado offline de falhas) — conceito, não recomendação

Analisa transcripts passados (Claude Code `~/.claude/projects/*.jsonl`, Codex, Gemini CLI),
correlaciona falha→correção (ex.: Read que falhou num caminho e depois funcionou em outro) e
gera regras específicas: fatos de ambiente, correções de path, escopo de busca, padrões de
comando. `headroom learn` é dry-run; `--apply` **escreve seções delimitadas por marcador** em
`CLAUDE.local.md` (default, gitignored) ou `CLAUDE.md`/`AGENTS.md`/`GEMINI.md` compartilhados —
exatamente os arquivos que a Squad protege. Na Squad, a capacidade equivalente é o
`aprendizado-continuo` (instintos YAML auditáveis, gated); `learn --apply` não deve ser rodado
por agente.

## SharedContext (handoff entre agentes)

```python
ctx = SharedContext()
ctx.put("research", saida_grande, agent="researcher")   # comprime (~80% menor)
resumo = ctx.get("research")                            # versão comprimida
completo = ctx.get("research", full=True)               # original
```

Cada entrada carrega metadados (`original_tokens`, `compressed_tokens`, `savings_percent`,
`transforms`, `agent`, `timestamp`). Útil como conceito para pipelines multi-agente da Squad.

## Números de referência (benchmarks do projeto, v0.5.x)

| Medição | Resultado |
|---|---|
| Arrays JSON (100–500 itens) | 83–91% de compressão, 1–2ms |
| Build log / shell output (200 linhas) | 85–94% |
| grep results e código Python | **0%** (passthrough intencional) |
| Extração HTML (benchmark Scrapinghub, 181 páginas) | recall 0.982, F1 0.919, 94.9% compressão |
| JSON com erro na posição 67 de 100 | 4/4 respostas corretas com 87.6% menos tokens |
| Overhead do proxy em produção (50k+ sessões) | mediana 52ms, P90 309ms, P99 4.2s |
| Compressão mediana em produção | ~5% (turnos conversacionais); 40–80% em sessões tool-heavy |
| Frota (telemetria opt-in, 249 instâncias) | 1.4 bi de tokens economizados (~US$ 4.000) |

Leitura crítica da Squad: os 60–95% do marketing valem para **dados JSON**; a mediana real de
produção é ~5% porque muita requisição é conversa curta. O ganho depende do perfil de tráfego —
medir com `--no-optimize` (baseline) vs otimizado antes de concluir.

## Limitações e comportamento conhecido

- **Código e RAG em texto puro: passthrough** por design (proteções de recência/intenção de
  análise). Não espere ganho aí.
- **Texto puro comprime 43–46% mas adiciona latência** (Kompress ML) — só vale por custo.
- **Tudo fail-graceful:** JSON inválido, falha de AST, compressão que aumenta tamanho ou
  dependência ausente → conteúdo original, warning no log, nunca exceção ao caller.
- **TOIN cold start:** sem histórico de uso, decide por heurística estatística; padrões
  aprendidos exigem persistência configurada.
- **CacheAligner** só atua em system messages; pode normalizar whitespace de conteúdo indentado.
- Contagem de tokens Anthropic é estimativa calibrada (não tokenizer oficial).

## Configuração essencial

Precedência: override por chamada > env vars > arquivo de config. Raízes do filesystem:
`HEADROOM_CONFIG_DIR` (default `~/.headroom/config`, read-mostly) e `HEADROOM_WORKSPACE_DIR`
(default `~/.headroom`, estado read-write: ledger de savings, memory DB, logs, TOIN). Exceção
deliberada: memória por projeto resolve por `{cwd}`, não pelo workspace. Limites de modelo
customizados via `HEADROOM_MODEL_LIMITS` (JSON inline ou path) ou
`${HEADROOM_CONFIG_DIR}/models.json`. Settings GUI em `/dashboard/settings` (campos sombreados
por env var ficam read-only; credenciais de terceiros nunca aparecem).

## Troubleshooting rápido

- "Entry not found or expired" → TTL estourado (1h local MCP, 5min proxy) ou proxy desligado.
- Host não vê as tools headroom → `headroom mcp status`, reiniciar o host, conferir `/mcp`.
- Compressão ~0% → tráfego é conversa curta/código/texto protegido (comportamento esperado).
- `/readyz` 503 → subsistema obrigatório indisponível ou startup incompleto.
