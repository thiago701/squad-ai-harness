# Step Functions Avançado: JSONata, API TestState e Padrões de Orquestração

> **Procedência:** absorvido e reescrito em PT-BR a partir de `aws/agent-toolkit-for-aws` (caminho upstream: skills/specialized-skills/serverless-skills/aws-step-functions e `processing-s3-uploads-with-step-functions`, commit `658b852f0612ca629d56d0a4de52738fb6a58714`, Apache-2.0).

---

## 1. JSONata em Amazon States Language (ASL)

Para novas state machines, declare `"QueryLanguage": "JSONata"` no topo da definição (ou estado a estado durante migração incremental). O JSONata substitui os 5 campos de I/O do JSONPath (`InputPath`, `Parameters`, `ResultSelector`, `ResultPath`, `OutputPath`) por três construções limpas: **`Arguments`**, **`Assign`** e **`Output`**.

### 1.1. Variável reservada `$states`

Em todo estado JSONata, o runtime expõe `$states`:

| Caminho | Disponibilidade | Papel |
|---|---|---|
| `$states.input` | Todos os estados | Entrada original recebida pelo estado |
| `$states.result` | `Task`, `Parallel`, `Map` (sucesso) | Resultado retornado pela integração ou sub-estados |
| `$states.errorOutput` | Somente dentro de `Catch` | Objeto de erro (`Error`, `Cause`) capturado |
| `$states.context.Execution.Id` / `Name` / `Input` / `StartTime` | Todos os estados | Metadados da execução e payload inicial do workflow |
| `$states.context.Execution.RedriveCount` / `RedriveTime` | Todos os estados | Contagem e instante do último redrive da execução |
| `$states.context.State.Name` / `EnteredTime` / `RetryCount` | Todos os estados | Nome do estado, timestamp de entrada (estável para idempotência) e tentativa atual |
| `$states.context.Task.Token` | Estados `.waitForTaskToken` | Token de callback (tratar como credencial secreta) |
| `$states.context.Map.Item.Index` / `Value` / `Key` / `Source` | Estados `Map` | Índice, valor, chave (ao iterar objeto JSON) e origem (`STATE_DATA` ou URI S3) |

### 1.2. Regra de Ouro: `Assign` e `Output` avaliam em PARALELO

Dentro de um mesmo estado, todas as expressões em `Assign` e `Output` são avaliadas **simultaneamente a partir do mesmo snapshot** (os dados de entrada do estado + `$states.result` + o valor das variáveis *antes* do estado).

- **Proibido:** atribuir `"Assign": { "total": "{% $states.result.Payload.total %}" }` e tentar ler `"{% $total %}"` no `Output` **do mesmo estado** (ele verá o valor antigo ou `undefined`, lançando `States.QueryEvaluationError`).
- **Correto:** referenciar `$states.result.Payload.total` diretamente no `Output` do estado atual e consumir `$total` apenas nos **estados seguintes**.
- **Proibido atribuir subcaminhos:** `"Assign": { "pedido.status": "PAGO" }` ou `"Assign": { "itens[0]": 1 }` são inválidos; atribua sempre a variável raiz.

### 1.3. Escopo e Limites de Variáveis

- **Escopo externo (`outer scope`):** estados declarados no `States` de topo.
- **Escopo interno (`inner scope`):** estados dentro de uma branch de `Parallel` ou iteração de `Map` (`INLINE`).
  1. Escopos internos **podem ler** variáveis do escopo externo.
  2. Escopos internos **não podem atribuir (`Assign`)** a variáveis do escopo externo nem criar variáveis com o mesmo nome (*no shadowing*).
  3. Branches de `Parallel` e iterações de `Map` são isoladas entre si; ao terminar a branch/iteração, suas variáveis saem de escopo (use `Output` no estado terminal da branch para devolver dados ao escopo externo).
  4. **Exceção crítica:** estados em **`Distributed Map` (`Mode: DISTRIBUTED`) NÃO têm acesso** às variáveis do escopo externo — passe tudo explicitamente via `ItemSelector`.
  5. Um bloco `Catch` no próprio estado `Parallel` ou `Map` atua no escopo externo e pode gravar variáveis externas.
- **Limites rígidos:**
  - Tamanho máximo por variável ou por bloco `Assign`: **256 KiB**.
  - Soma total de variáveis armazenadas por execução: **10 MiB**.
  - Tamanho máximo do nome da variável: **80 caracteres Unicode**.

---

## 2. Guia de Migração JSONPath → JSONata (8 Armadilhas Clássicas)

| Construção JSONPath | Equivalente JSONata |
|---|---|
| `InputPath` | Removido — referencie `$states.input` diretamente |
| `Parameters` com `"chave.$": "$.campo"` | `Arguments` com `"chave": "{% $states.input.campo %}"` (sem sufixo `.$`) |
| `ResultSelector` + `OutputPath` | `Output` referenciando `$states.result` |
| `ResultPath` | `Assign` (preferido) ou `Output` |
| `TimeoutSecondsPath` / `HeartbeatSecondsPath` | `TimeoutSeconds` / `HeartbeatSeconds` com `"{% ... %}"` |
| `TimestampPath` (em `Wait`) | `Timestamp: "{% $states.input.dataIso %}"` |
| `ItemsPath` + `Parameters` + `Iterator` (em `Map`) | `Items` + `ItemSelector` + `ItemProcessor` (com `ProcessorConfig`) |
| `Choices` com `Variable` + `StringEquals`/`NumericGreaterThan` | `Choices` com `"Condition": "{% $states.input.status = 'APROVADO' and $states.input.valor > 100 %}"` |
| `Catch` com `ResultPath: "$.erro"` | `Catch` com `"Assign": { "erro": "{% $states.errorOutput %}" }` |

### Mapeamento de Funções Intrínsecas para JSONata

| Intrínseca JSONPath | Função JSONata |
|---|---|
| `States.Format('Pedido {}', $.id)` | `'Pedido ' & $states.input.id` |
| `States.StringToJson($.str)` / `States.JsonToString($.obj)` | `$parse($states.input.str)` / `$string($states.input.obj)` |
| `States.StringSplit($.str, ',')` | `$split($states.input.str, ',')` |
| `States.Array($.a, $.b)` / `States.ArrayPartition($.arr, 10)` | `[$states.input.a, $states.input.b]` / `$partition($states.input.arr, 10)` |
| `States.ArrayContains($.arr, $.v)` / `States.ArrayUnique($.arr)` | `$states.input.v in $states.input.arr` / `$distinct($states.input.arr)` |
| `States.ArrayLength($.arr)` / `States.ArrayGetItem($.arr, 0)` | `$count($states.input.arr)` / `$states.input.arr[0]` |
| `States.Base64Encode` / `States.Base64Decode` | `$base64encode(...)` / `$base64decode(...)` |
| `States.Hash($.d, 'SHA-256')` / `States.UUID()` | `$hash($states.input.d, 'SHA-256')` / `$uuid()` |
| `States.JsonMerge($.a, $.b)` | `$merge([$states.input.a, $states.input.b])` |

### As 8 Armadilhas que Quebram Workflows JSONata

1. **Misturar campos JSONPath e JSONata no mesmo estado:** um estado usa uma única linguagem. Nunca combine `Arguments` com `InputPath`/`ResultPath` ou `Condition` com `Variable`.
2. **Manter o sufixo `.$` nas chaves:** em JSONata, `"id.$": "{% ... %}"` cria uma chave literal chamada `"id.$"`. Remova sempre o `.$`.
3. **Usar `$` ou `$$` na raiz da expressão:** use `$states.input` e `$states.context` (`$` só vale dentro de predicados de filtro como `$states.input.itens[$.preco > 10]`).
4. **Aspas duplas dentro da expressão JSONata:** use aspas simples (`'ativo'`) dentro de `"{% ... %}"` para não quebrar o JSON.
5. **Ler variável recém-atribuída no `Output` do mesmo estado:** `Assign` e `Output` rodam em paralelo.
6. **Campos opcionais ausentes lançam `States.QueryEvaluationError`:** diferente do JSONPath, que retorna `null`, o JSONata falha se a expressão resultar em `undefined`. Proteja com `$exists($states.input.campo) ? $states.input.campo : ''`.
7. **Filtro JSONata com 1 elemento retorna objeto escalar, não array:** em JSONata, `ordens[status = 'PENDENTE']` devolve um **objeto** quando apenas 1 item casa, e `undefined` quando nenhum casa — quebrando o campo `Items` do estado `Map` ou `$count()`. Use sempre o idioma defensivo:
   ```
   "{% ( $f := $states.input.ordens[status = 'PENDENTE']; $type($f) = 'array' ? $f : $exists($f) ? [$f] : [] ) %}"
   ```
8. **Esquecer de converter `Iterator` para `ItemProcessor`:** exija `ItemProcessor` com `ProcessorConfig: { "Mode": "INLINE" | "DISTRIBUTED" }`.

---

## 3. Testes Unitários e Encadeados sem Deploy com a API `TestState`

A API `TestState` (`aws stepfunctions test-state`) permite testar estados isolados ou cadeias de estados **sem implantar a state machine** e sem invocar serviços reais (via `--mock`).

### 3.1. Regras Críticas do `--mock` e Níveis de Inspeção

- **Schema estrito da API do serviço:** o JSON passado em `--mock '{"result":"..."}'` deve respeitar **exatamente** o contrato de resposta do AWS SDK (case-sensitive):
  - `lambda:invoke` → `{"StatusCode": 200, "Payload": {"status": "ok"}}`
  - `dynamodb:putItem` / `getItem` → `{"Attributes": {...}}` / `{"Item": {"id": {"S": "123"}}}`
  - `sqs:sendMessage` → `{"MessageId": "xyz", "MD5OfMessageBody": "..."}`
  - `sns:publish` → `{"MessageId": "abc-123"}`
  - `events:putEvents` → `{"FailedEntryCount": 0, "Entries": [{"EventId": "123"}]}`
- **Para integrações `.sync`, faça mock da API de POLLING (não da chamada inicial):**
  - `states:startExecution.sync:2` → mock de `DescribeExecution` (`{"Status": "SUCCEEDED", "Output": "{...}"}`)
  - `batch:submitJob.sync` → mock de `DescribeJobs`
  - `glue:startJobRun.sync` → mock de `GetJobRun`
- **Para `.waitForTaskToken`:** passe `--context '{"Task":{"Token":"token-teste-123"}}'` junto com o `--mock`.
- **Modos de validação (`fieldValidationMode`):** use `NONE` no rascunho inicial, `PRESENT` em testes parciais e **`STRICT` (padrão) obrigatoriamente no gate/CI**.
- **Níveis de inspeção (`--inspection-level`):**
  - `INFO`: `output`, `status`, `nextState`.
  - `DEBUG`: adiciona `afterArguments`, `result`, `variables`, `afterItemSelector` (essencial para depurar expressões JSONata).
  - `TRACE`: adiciona HTTP `request`/`response` para `http:invoke` (nunca versione nem exponha saídas com `--reveal-secrets` em logs).
- **Simulação de Retries e Falhas em Map:**
  - Retry na N-ésima tentativa: `--state-configuration '{"retrierRetryCount": 1}' --mock '{"errorOutput":{"error":"Lambda.ServiceException","cause":"..."}}'` → valida `status: "RETRIABLE"` e `retryBackoffIntervalSeconds`.
  - Limiar de falha no Map: `--state-configuration '{"mapIterationFailureCount": 5}'`.

---

## 4. Sete Padrões Arquiteturais Canônicos em Step Functions

1. **Polling Loop (`Wait → Check → Choice`):** para operações assíncronas sem suporte a `.sync`. Inicie a tarefa, aguarde o tempo estimado inicial (`Wait`), consulte o status, avalie no `Choice` (sucesso, falha terminal ou novo `Wait` curto com contador máximo de iterações para evitar loop infinito).
2. **Saga com Compensação Reversa:** cada etapa de avanço (`ReserveInventory` → `ChargePayment` → `ShipOrder`) guarda os identificadores em variáveis (`Assign`: `$reservedQty`, `$chargeId`) e possui um `Catch` que registra `$failedStep` e `$errorInfo`, roteando para a cadeia reversa exata (`RefundPayment` → `ReleaseInventory` → `OrderFailed`).
3. **Scatter-Gather com Resultados Parciais:** em chamadas por item para APIs externas sujeitas a falha, configure `ToleratedFailurePercentage` no `Map` e pós-processe o array resultante separando sucessos e falhas via filtro `$exists(Error)` protegido pelo idioma de array JSONata.
4. **Semáforo / Lock Distribuído com DynamoDB:** quando apenas uma execução pode processar um recurso por vez, adquira o lock via `dynamodb:putItem` com `ConditionExpression: "attribute_not_exists(lockKey) OR expiresAt < :now"` + TTL `expiresAt`, faça spin-wait controlado com `Retry` em `DynamoDB.ConditionalCheckFailedException`, e garanta que o `Catch` do trabalho protegido sempre passe por `ReleaseLock` (que deleta condicionalmente apenas se `executionId = :myExecId`).
5. **Human-in-the-Loop com Escalonamento por Timeout:** encadeie múltiplos estados `.waitForTaskToken` com `HeartbeatSeconds`/`TimeoutSeconds` e `Catch` para `States.Timeout` (aprovador primário → gestor → rejeição automática). Nunca envie PII ou valores financeiros no corpo de SNS/SQS; envie apenas o ID de referência e trate o `Task.Token` como segredo.
6. **Handoff `Express → Standard`:** use um workflow **Express** para ingestão de altíssimo volume e baixa latência e dispare (`states:startExecution` assíncrono) um workflow **Standard** apenas para a cauda longa que exige auditoria de 90 dias, espera longa ou `.sync`/`.waitForTaskToken`.
7. **Roteamento de Uploads S3 por Tamanho (`S3 → EventBridge → Step Functions → Lambda ou Fargate`):**
   - Habilite notificações EventBridge no bucket S3 (com criptografia KMS) e filtre `detail-type: ["Object Created"]` com DLQ no target do EventBridge.
   - Na state machine (`Choice` sobre `detail.object.size`), encaminhe arquivos pequenos (**≤ 6 MB**) para **AWS Lambda** e arquivos grandes (**> 6 MB**) para **ECS Fargate** (`ecs:runTask.sync`).
   - Em tarefas Fargate acionadas pelo Step Functions: revogue a regra de saída padrão `0.0.0.0/0` do Security Group e restrinja egress a TCP 443 (HTTPS) e UDP 53 (DNS), preferindo VPC Endpoints para S3 e CloudWatch Logs, com role do Step Functions escopada com `iam:PassRole` restrito às roles de execução e de tarefa do ECS.
