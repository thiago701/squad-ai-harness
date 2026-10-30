# Java em ECS × Lambda — critérios mensuráveis

> Parte da skill `arquiteto-cloud-aws`. Hub: `../SKILL.md`. Números com fonte em
> `fatos-verificados-aws.md` §6. Marcas de evidência: `governance/politica-evidencias-sigilo-qualidade.md`.
> Seletor determinístico (restrições duras + heurísticas marcadas): `scripts/aws/seletor_compute.py`.

## 1. Decisão em duas camadas

**Camada 1 — restrições duras `[OK]`** (violou, a opção sai da mesa):

| Restrição | Lambda | ECS Fargate | Ação quando estoura |
|---|---|---|---|
| Duração por unidade de trabalho | ≤ 900 s | sem limite de execução | job longo → ECS (ou quebrar em etapas no Step Functions) |
| Payload síncrono | ≤ 6 MB | limite do protocolo/LB | arquivo grande → S3 + URL pré-assinada |
| Payload assíncrono | ≤ 1 MB | — | referência a objeto em S3 |
| Memória | ≤ 10.240 MB | até 244 GiB (32 vCPU) | acima → ECS em EC2 |
| Concorrência | 1.000/região por padrão (aumentável) | tasks × capacidade | pedir quota **antes** do pico |
| Encerramento | instância gerenciada pela plataforma | SIGTERM → SIGKILL em `stopTimeout` (≤ 120 s) | drenagem obrigatória no ECS |

**Camada 2 — heurísticas `[AN]`** (pesam, mas exigem medição para decidir):

| Sinal | Tende a | Por quê | Medição que confirma |
|---|---|---|---|
| Tráfego intermitente, rajadas, ociosidade longa | Lambda | paga por uso, escala por requisição | custo mensal com volume real (Cost Explorer ou calculadora) |
| Carga alta e constante (≥ ~20 h/dia ativas) | ECS | capacidade reservável e reaproveitada | custo/1M req nos dois modelos com o mesmo perfil |
| Conexões longas, estado em memória, pool grande e quente | ECS | o ambiente Lambda pode ser reciclado a qualquer momento | taxa de reconexão, p99 sob reciclagem |
| Meta de p99 apertada com cold start sensível | ECS, ou Lambda com SnapStart/GraalVM **medido** | cold start entra no p99 | p99 separado em frio × quente |
| Evento → processamento curto e idempotente | Lambda | integração nativa com SQS/EventBridge/Streams | taxa de erro e duplicidade por lote |

> **Proibido:** prometer "resposta em poucos milissegundos" sem cenário. A meta é **por cenário**
> (ex.: "`POST /ordens` p99 ≤ X ms com N req/s, payload Y KB, 1% de cold start") e é medida.

## 2. Protocolo de medição (obrigatório antes de afirmar ganho)

1. **Cenário:** rota/evento, payload, taxa (req/s), concorrência, duração do teste, região.
2. **Métricas:** latência **ponta a ponta** (cliente → resposta) em p50/p95/p99, separando frio e
   quente; taxa de erro (4xx/5xx/timeout); throttling; custo estimado por 1M requisições com o
   volume real; para filas, idade da mensagem mais antiga e backlog.
3. **Amostra:** registre `n` por percentil; p99 com poucas centenas de amostras é `[AN]`.
4. **Mesma régua antes/depois:** mesma carga, mesmo ambiente, mesma ferramenta (k6, por exemplo).
5. **Relato:** tabela com cenário, `n`, percentis, erros, custo — e o nível de validação
   (V2–V5 da política). Benchmark local não prova comportamento em produção.

Evidência histórica da casa (um cenário específico, não regra geral):
`benchmark-aws-lambda-aot/` e `lambda-aot-benchmark/`.

## 3. Checklist Java em ECS

| Eixo | Verificar |
|---|---|
| EC2 × Fargate | Fargate por padrão (sem gestão de host); EC2 só com justificativa medida (custo reservado, hardware específico, densidade) |
| Imagem | base mínima e fixada por digest; usuário não-root; scan de vulnerabilidades no registro; sem segredo na imagem |
| Privilégios | sem `privileged`; root filesystem somente leitura quando possível; sem `ECS Exec` habilitado em produção sem processo break-glass |
| CPU/memória/heap | heap por porcentagem do container (`-XX:MaxRAMPercentage`), deixando margem para metaspace, threads e buffers nativos; memória do container ≥ heap + não-heap medido |
| Inicialização | `startPeriod` do health check cobre o warm-up real; readiness ≠ liveness |
| Encerramento gracioso | SIGTERM tratado (Spring: `server.shutdown=graceful`); tempo de drenagem < `stopTimeout` (≤ 120 s) e coerente com o *deregistration delay* do target group |
| Balanceamento/autoscaling | target tracking em métrica que representa saturação (CPU, requisições por alvo, backlog por task) |
| Pools, timeouts, retries | timeout de cliente < timeout de quem chama; retries com backoff + jitter e limite; backpressure (fila limitada, rejeição explícita) em vez de fila infinita |
| Identidades | **task role** = permissões da aplicação; **execution role** = pull de imagem, logs e leitura de segredos para injeção; nunca misturar |
| Segredos | `secrets` com Secrets Manager/SSM — injetados só no start: rotação exige nova task |
| Rollout/rollback | deployment circuit breaker com rollback; health checks que reprovam de verdade |
| Observabilidade | logs estruturados com correlação, métricas RED, tracing; alarmes em p99, erros e saturação |

## 4. Checklist Java em Lambda

| Eixo | Verificar |
|---|---|
| Limites | §1 camada 1; runtime gerenciado `java25` ou `java21` (AL2023) |
| Cold start | medir frio × quente separados; SnapStart (Java 11+; incompatível com provisioned concurrency, EFS e ephemeral > 512 MB) ou GraalVM Native **só quando a medição justificar** |
| Memória ↔ CPU | memória também determina CPU disponível — ajuste por medição (ex.: Lambda Power Tuning), não por padrão |
| Concorrência | reserved concurrency para proteger downstream; provisioned concurrency só com meta de p99 que a exija |
| Conexões | clientes do SDK e pools criados **fora** do handler e reutilizados; banco relacional via proxy de conexões; nada de estado de negócio em variável estática |
| Assíncrono | retries (0–2) e idade máxima configurados; destino on-failure ou DLQ; handler idempotente (duplicatas são possíveis) |
| Lotes (SQS/Kinesis/Streams) | `ReportBatchItemFailures` + idempotência por item; nunca falhar o lote inteiro por um item |
| Empacotamento | dependências mínimas; sem reflexão desnecessária (AOT); teste de inicialização no pipeline |
| Otimização | AOT/imagem nativa e outras otimizações **somente quando aplicáveis e medidas** (protocolo §2) |

## 5. Saída esperada do arquiteto

```
Escolha: <LAMBDA | ECS_FARGATE | ECS_EC2>
Restrições duras checadas: [OK] … (fonte: fatos-verificados-aws.md §6)
Heurísticas: [AN] … (o que confirmaria)
Metas por cenário: <rota/evento> p99 ≤ … com … req/s
Medições exigidas antes do GATE 2: …
Riscos e plano de reversão: …
```
