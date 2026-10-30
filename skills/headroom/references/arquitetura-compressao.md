# Headroom — arquitetura e pipeline de compressão

> Reference da skill [`headroom`](../SKILL.md). Fonte: wiki do repo
> `headroomlabs-ai/headroom` (ARCHITECTURE.md, compression.md, ccr.md, transforms.md),
> destilada em 2026-07-21. Nada aqui é código copiado — é síntese técnica.

## Visão geral do fluxo

```
Entry points                Pipeline de transforms              Saída
─────────────               ─────────────────────               ─────
Proxy (HTTP)          ┌──> CacheAligner                   ┌──> Otimização de cache
SDK (HeadroomClient)  │    (prefixo estável p/ cache)     │    por provedor:
Integrações           │        │                          │    · Anthropic: cache_control
(LangChain, Agno,     │        ▼                          │    · OpenAI: prefix alignment
 Strands, LiteLLM)    │    ContentRouter → compressor     │    · Google: CachedContent
                      │        │                          │
                      │        ▼                          └──> LLM API
                      └──> ContextManager (limites de token, score por recência/relevância)
                               │
                               └──(originais)──> CCR store ⇆ tool headroom_retrieve
```

O `HeadroomClient` embrulha o cliente OpenAI/Anthropic existente, intercepta as chamadas, roda o
pipeline e chama a API real — a resposta volta inalterada. Dois modos de operação do cliente:
`audit` (só observa e loga métricas) e `optimize` (aplica transforms). `Providers` encapsulam o
conhecimento por modelo (janela de contexto, tokenizer — tiktoken para OpenAI, estimativa
calibrada para Anthropic — e preços); o `Parser` quebra as mensagens em blocos tipados
(system/user/tool_call/tool_result) com contagem de tokens e detecta sinais de desperdício
(JSON > 500 tokens, HTML, base64, whitespace excessivo).

## Transforms

### CacheAligner

Provedores só acertam o cache de prompt se o prefixo for byte-idêntico. Uma data no system prompt
quebra o cache todo dia. O CacheAligner extrai padrões dinâmicos (datas, UUIDs, tokens de sessão)
do system prompt e move para o fim como bloco `[Dynamic Context]` — o prefixo vira estável.

| Cenário | Cache hits antes | Depois |
|---|---|---|
| Data diária no prompt | 0% | ~95% |
| Contexto dinâmico de usuário | ~10% | ~80% |

Limitações: só processa **system messages**; normalização de whitespace pode afetar conteúdo com
indentação significativa (blocos de código, ASCII art); o marcador adiciona alguns tokens.

### SmartCrusher (default para arrays JSON)

Substituiu o "Tool Crusher naive" (que cortava nos primeiros N itens e perdia o spike na posição
45). Faz **análise estatística** campo a campo do array: tipo (sequencial/constante), variância,
change-points, razão de valores únicos. Retenção por **K adaptativo** — não há K fixo:

1. **Algoritmo Kneedle** sobre curvas de cobertura de bigramas acha o ponto em que mais itens não
   trazem informação nova.
2. **SimHash** detecta quase-duplicatas.
3. Validação por **zlib** garante que o subconjunto captura a diversidade do conjunto.
4. O K resultante se divide: ~30% do início do array (schema/paginação), ~15% do fim (recência),
   ~55% por score de importância.

**Garantias aditivas (nunca descartadas, mesmo estourando o K):** itens de erro ("error",
"exception", "failed", "critical"...), anomalias numéricas (> 2 desvios-padrão da média),
anomalias de comprimento de string (idem) e change-points. Tipos de array suportados: dicts (análise completa),
strings (dedup + amostragem), números (sumário estatístico + outliers), mistos (agrupados por
tipo). Recursão em objetos aninhados até profundidade 5.

**Passa direto (sem comprimir):** arrays < 5 itens, conteúdo < 200 tokens, arrays só de bool,
JSON sem arrays, JSON malformado (passthrough silencioso), conteúdo não-JSON.

### CodeCompressor / code-aware (opt-in, protegido por padrão)

AST via tree-sitter — preserva imports, assinaturas, classes, type annotations e decorators;
comprime corpos de função. Tier 1 (AST completo): Python, JavaScript, TypeScript. Tier 2 (corpo
de função): Go, Rust, Java, C, C++. Fallback regex quando o parse falha.

**Na prática código quase sempre passa intacto**, por três portões intencionais:
1. Conteúdo < 50 palavras é pulado.
2. `protect_recent_code=4`: código nas últimas 4 mensagens nunca é comprimido (tool result é
   sempre "recente" no padrão de tool call).
3. `protect_analysis_context=True`: se a última mensagem do usuário contém "analyze", "review",
   "explain", "fix", "debug", "optimize", "error", "bug" — TODO código da conversa é protegido.

Racional: código é buscado porque o usuário quer trabalhar nele; comprimir corpos removeria
exatamente o que ele precisa. Override consciente: `protect_analysis_context=False` em
`ContentRouterConfig` + extra `headroom-ai[code]`.

### Kompress (compressão ML de texto, opt-in)

Modelo próprio (Kompress-v2-base, ModernBERT, HuggingFace) via extra `headroom-ai[ml]`.
Substituiu a integração LLMLingua-2 (aposentada — flags `--llmlingua` não existem mais).
Comprime texto livre 80–95%, mas **adiciona latência** (50–200ms + load do modelo na primeira
chamada; instância global única com lock — acesso sequencial sob concorrência). Usar para
economia de custo, não de velocidade.

### ContentRouter — roteamento por tipo

| Estratégia | Conteúdo | Compressor |
|---|---|---|
| SMART_CRUSHER | Arrays JSON | SmartCrusher |
| CODE_AWARE | Código-fonte | CodeCompressor |
| SEARCH | Saída de grep/find | SearchCompressor |
| LOG | Logs | LogCompressor |
| TEXT | Texto puro | TextCompressor/Kompress |
| PASSTHROUGH | Conteúdo pequeno | nenhum |

Detecção de tipo com Magika (ML, extra `[magika]`). **Structure masks** definem o que preservar
por tipo: JSON mantém chaves, sintaxe estrutural, booleans/nulls, strings de alta entropia
(UUIDs, hashes — `entropy_threshold=0.85`) e números curtos (IDs); comprime valores longos.

## Compressão universal (API `compress()`)

```python
from headroom.compression import compress
result = compress(content)
# result.compressed / .original / .tokens_saved / .savings_percentage
# result.content_type / .handler_used / .ccr_key
```

Config principal (`UniversalCompressorConfig`): `compression_ratio_target` (0.3 = manter 30%),
`min_content_length` (default 100 chars), `use_entropy_preservation`, `ccr_enabled`. Handlers
customizados registráveis por `ContentType`. Batch: `compress_batch(contents)`.

**Tratamento de erro em todos os compressores: fail graceful.** JSON inválido → passthrough;
falha de AST → original; compressão que aumenta o tamanho → original; dependência opcional
ausente → passthrough com warning. Erros nunca propagam ao caller.

## CCR — Compress-Cache-Retrieve (reversibilidade)

Elimina o trade-off "compressão agressiva arrisca perder dados vs conservadora economiza pouco":

1. **Compression Store** — ao comprimir, o original vai para um cache LRU local com chave hash;
   o output comprimido ganha um marcador: `[1000 items compressed to 20. Retrieve: hash=abc123]`.
2. **Tool injection** — a tool `headroom_retrieve(hash)` é injetada nas tools disponíveis do LLM.
3. **Response Handler** — quando o LLM chama a tool, o handler intercepta, recupera do cache
   (~1ms) e continua a chamada automaticamente; o cliente nunca vê os tool calls de CCR.
4. **Context Tracker (multi-turn)** — lembra o que foi comprimido em turnos anteriores, analisa
   a relevância de novas perguntas ("what about the auth middleware?") e **expande
   proativamente** o conteúdo comprimido relevante antes de o LLM pedir.

Invariantes importantes:
- **Nunca derruba mensagens inteiras** — CCR opera sobre blocos de conteúdo (tool outputs mais
  novos, a "live zone"). System prompt, definições de tool e turnos antigos (a hot zone do cache
  do provedor) **não são mutados** — prompt caching continua funcionando.
- TTLs: conteúdo comprimido via MCP `headroom_compress` fica 1h; via proxy, 5min.
- **TOIN** (Tool Output Intelligence Network): aprende com padrões de retrieval — o que os
  usuários recuperam vira sinal de valor para decisões futuras de compressão. Cold start: sem
  padrões aprendidos usa heurística estatística; hints ignorados abaixo de
  `toin_confidence_threshold` (0.3).

Flags do proxy: `--no-ccr` (desliga tudo — **lossy**, sem caminho de recuperação),
`--no-ccr-proactive-expansion` (desliga só a expansão proativa).

## Modos de execução do proxy

- `token` (default): maximiza compressão; histórico anterior pode ser reescrito.
- `cache`: congela turnos anteriores (só o turno mais novo é mutável) — prioriza estabilidade do
  prefix cache do provedor. Melhor para conversas longas.

`headroom proxy --mode cache` ou `HEADROOM_MODE=cache`. Aliases legados: `token_headroom`,
`cost_savings`.
