# Referência — Streaming Stateful (Kinesis, MSK, Flink)

> Parte da skill `arquiteto-cloud-aws`. Carregue este arquivo sob demanda quando a tarefa tocar este eixo. Hub: `../SKILL.md`.
## Stateful Streaming — Kinesis, MSK, Flink (fora do núcleo da squad)

> **Escopo da squad**: workloads **stateless** (HTTP APIs, workers SQS, jobs agendados, pipelines EventBridge). Workloads **stateful de streaming** (Kafka Streams, Flink, Spark Structured Streaming) têm suas próprias disciplinas operacionais e **não são objetivo primário** do squad-ai-harness.

**Quando você está num workload stateful:**

- Agregações contínuas sobre janelas de tempo (tumbling, sliding, session)
- Estado grande por chave (> 100MB) distribuído e persistido (RocksDB state backend)
- CEP (Complex Event Processing) / pattern matching em streams
- Exactly-once processing end-to-end (não apenas idempotência)
- Ordenação estrita por chave com volumes > 50K msg/s

**Para esses casos, opções canônicas:**

| Workload | Opção AWS | Opção Open-Source |
|---|---|---|
| Stream ingestion alto volume | Kinesis Data Streams | MSK (Kafka managed) |
| Agregações contínuas | Kinesis Data Analytics (Flink) | MSK + Kafka Streams (self-hosted compute) |
| ETL batch + stream unificado | Glue Streaming | Apache Spark Structured Streaming |
| CEP / rules | Kinesis Data Analytics | Apache Flink CEP |

**Observações críticas para adoção:**
- **State backend** (RocksDB) deve estar em volume persistente (EBS gp3 com IOPS provisioned) — não use ephemeral storage.
- **Checkpoint interval** típico: 1-5min em S3 — ajusta trade-off entre recovery time e throughput.
- **Savepoints versionados** antes de qualquer deploy que mude operadores.
- **Schema evolution** via Avro/Protobuf + Schema Registry — nunca JSON puro em stream stateful.
- **Latência end-to-end** diferente do modelo request-response: p99 normalmente medido em segundos (event-time lag), não ms.

**Recomendação pragmática** (P1 Simplicidade):
- Antes de adotar Flink/Kafka Streams, verifique se Kinesis Data Streams + Lambda **já resolve** o caso (até 10K msg/s por shard).
- Agregações simples sobre janelas curtas: DynamoDB + TTL + Lambda trigger vez de state backend.
- Apenas adote stateful streaming quando os 5 critérios acima se aplicam **simultaneamente**.

Para um time que adote workloads stateful em escala, considerar:
1. Skill futura `arquiteto-dados-streaming` (roadmap — fora da release atual).
2. Referências externas: "Designing Data-Intensive Applications" (Kleppmann, cap 11-12), "Stream Processing with Apache Flink" (Hueske & Kalavri).

---

