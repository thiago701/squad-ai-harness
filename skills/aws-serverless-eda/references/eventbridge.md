# EventBridge — Rules × Scheduler × Pipes, entrega, contratos e escrita dupla

> Parte da skill `aws-serverless-eda`. Hub: `../SKILL.md`. Fatos com fonte e data:
> `../../arquiteto-cloud-aws/references/fatos-verificados-aws.md` §3. Marcas de evidência:
> `governance/politica-evidencias-sigilo-qualidade.md`.

## 1. Qual peça usar

| Necessidade | Peça | Por quê |
|---|---|---|
| Muitos produtores → muitos consumidores, roteamento por conteúdo | **Event bus + Rules** | filtros declarativos, até vários targets por regra, arquivo/replay |
| Ponto a ponto de uma fonte (SQS, Kinesis, DynamoDB Streams, MQ, MSK, Kafka) para um alvo, com filtro/enriquecimento | **Pipes** | sem Lambda de cola; preserva a ordem da fonte; lote parcial |
| Agendamento (uma vez, `rate`, `cron` com fuso IANA) | **Scheduler** | regras agendadas são legado; Scheduler tem retry, DLQ e janela flexível |
| Ordem por grupo e deduplicação na publicação | **Custom event bus novo** (09/2026) | FIFO por event group, dedupe de 5 min, retenção 1–365 dias — `[AN]` avaliar maturidade/região antes de adotar |

## 2. Entrega: o que NÃO presumir

- **Sem ordem global** no barramento Classic; replay também sem ordem.
- **Duplicidade possível** ("the same rule can run more than once") → consumidor idempotente.
- Retry padrão do target: 24 h / 185 tentativas; esgotou → **descartado**, a menos que haja DLQ
  (SQS standard). Erros de permissão/recurso inexistente vão direto para a DLQ, sem retry.
- `PutEvents` com falha parcial devolve **200** e `FailedEntryCount > 0` → reenviar só as entradas
  com erro. Bus inexistente: 200 e evento descartado sem contar como falha.
- No Step Functions, `events:putEvents` falha com `EventBridge.FailedEntry` e o retry reenvia o lote
  inteiro — só com consumidores idempotentes.
- Evento até 1 MB (exceto 5 regiões), cobrado em blocos de 64 KB.

Modele explicitamente: **duplicidade, atraso, reentrega e fora de ordem** — e teste cada um.

## 3. Contratos versionados

- `source` e `detail-type` estáveis; `detail.versaoContrato` explícito.
- Mudança compatível: campo opcional novo, mesma versão. Incompatível: `v2` **em paralelo** + regra
  nova filtrando a versão; desligar `v1` só quando nenhum consumidor depender dela.
- Evento carrega **estado** (ou o suficiente para o consumidor decidir sem ler a origem) e uma
  **versão monotônica** por agregado → consumidor aplica "maior versão vence".
- Schema Registry aceita OpenAPI 3 e JSONSchema Draft4; gere bindings quando houver muitos consumidores.

## 4. Escrita dupla (gravar estado E publicar evento)

| Mecanismo | Como | Quando |
|---|---|---|
| **CDC** (DynamoDB Streams → Pipes → bus) | uma escrita; o evento é derivado do stream | estado em DynamoDB; menor código |
| **Outbox** | evento gravado na mesma transação do estado; publicador lê e publica | banco relacional/transacional; precisa de controle fino do payload |
| Publicar direto depois do commit | `PutEvents` após gravar | **evite**: crash entre os dois perde o evento; antes do commit publica o que pode não existir |

Ambos (CDC e outbox) dão **at-least-once** na publicação; efeito único = consumidor idempotente.
No Pipes, o input transformer **não escapa** valores e caminho ausente vira string vazia → só leve
campos de charset restrito (ids, enums, números como texto) e valide o contrato no consumidor.

## 5. Observabilidade e recuperação

- Correlação: id do agregado + versão em todo evento; `trace-header` quando houver X-Ray.
- Alarmes: DLQ > 0; `FailedInvocations`; `IteratorAge` do Pipe; idade da fila consumidora.
- Recuperação: **Archive & Replay** (o replay adiciona `replay-name`; espere ~10 min antes de
  reproduzir) para reconstruir projeções idempotentes.

## 6. Testes

| Cenário | Exemplo no repositório |
|---|---|
| Evento duplicado / fora de ordem na projeção | `labs/aws-referencia-ordens/java/src/test/java/exemplo/ordens/projecao/CqrsWebSocketTest.java` |
| Input template do Pipe × contrato do evento | `tests/test_aws_referencia_contratos.py::test_input_template_do_pipe_segue_o_contrato_do_evento` |
| Lote parcial no consumidor | `HandlersTest.lotePacial` |
