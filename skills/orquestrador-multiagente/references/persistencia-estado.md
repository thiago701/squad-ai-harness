# Persistência de Estado & Escalabilidade

> Detalhe de esquema é específico do motor de checkpointing (estilo LangGraph). Ver `PROCEDENCIA.md`.

## Porquê checkpointing
Fluxos multiagentes de longa duração exigem gravar o estado a cada transição/**superstep**. É um
*auto-save* que dá: resiliência a falha de infra, **interrupção para aprovação humana** e **time-travel**
(rebobinar e reexecutar a partir de qualquer ponto do histórico).

## PostgreSQL — 4 tabelas (persistência durável/transacional)

- **`checkpoints`** — estado completo do grafo em **JSONB**: `channel_values` (valores dos canais),
  `channel_versions` (versão por canal), metadados. **`parent_checkpoint_id`** encadeia o histórico em
  árvore → suporta desvios não-lineares e **time-travel**.
- **`checkpoint_blobs`** — isola dados grandes/voláteis (históricos de mensagens, ficheiros, saídas de
  ferramenta). Grava apenas **deltas** das variáveis que mudaram no passo → otimiza armazenamento.
- **`checkpoint_writes`** — escritas **pendentes** de cada passo. Se a infra cai a meio, os nós já
  validados estão salvos aqui → retoma sem repetir chamadas caras a APIs/ferramentas.
- **`checkpoint_migrations`** — versão do esquema do orquestrador; compatibilidade de retroversão em CI/CD.

```
checkpoints (checkpoint_id PK, thread_id, parent_checkpoint_id → self, channel_values JSONB, channel_versions)
   │ 1:N
   ▼
checkpoint_blobs (blob_id PK, checkpoint_id FK, channel, value_delta BLOB)
```

## Redis — baixa latência (<1 ms)
- **`RedisSaver`** — histórico completo de checkpoints via **RedisJSON** indexado → auditoria minuciosa.
- **`ShallowRedisSaver`** — só o **último** checkpoint ativo por thread, valores inline; limpeza
  automática de checkpoints antigos → menor pegada de RAM.

## Escalonamento (a persistência satura a base)
Persistir cada transição de cada subagente gera volume insustentável — **≈93 registos** para uma
conversa simples (2 mensagens + 3 chamadas de ferramenta). Mitigações:

1. **Compilar checkpoint só no supervisor.** Motor persistente **apenas** no grafo do orquestrador;
   especialistas rodam como **subgrafos sem estado** em memória (chamadas de ferramenta locais). Só o
   resultado estruturado final volta ao supervisor para gravação. *(diretriz central — no hub)*
2. **Particionamento físico + limpeza ativa.** `pg_partman` particiona por **`thread_id`**; cron jobs
   assíncronos eliminam partições históricas fora de uso.
3. **Extração para armazenamento frio.** ETL semanal converte históricos em **JSON comprimido** e envia
   para **S3** (cold storage) → alivia a base operacional, preserva dados para análise/auditoria.
