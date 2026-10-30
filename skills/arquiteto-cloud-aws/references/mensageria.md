# Referência — Mensageria (SQS, SNS, EventBridge)

> Parte da skill `arquiteto-cloud-aws`. Carregue este arquivo sob demanda quando a tarefa tocar este eixo. Hub: `../SKILL.md`.
### Mensageria — SQS, SNS, EventBridge

#### SQS — Fila Simples e Confiável

```
Free tier SQS: 1 MILHÃO de requisições/mês — permanente

Quando usar SQS:
  ✓ Desacoplar produtor de consumidor (processamento assíncrono)
  ✓ Buffer para picos de carga (Lambda ou ECS consome no ritmo certo)
  ✓ Dead Letter Queue para mensagens com falha (sem código de retry próprio)
  ✓ Filas FIFO quando ordem importa (ex: eventos de pagamento)

SQS Standard: alta throughput, entrega at-least-once, sem garantia de ordem
SQS FIFO:     até 300 msg/s, exatamente uma vez, ordem garantida (+10% custo)
```

```python
# Python — producer SQS (boto3 — sem biblioteca de fila própria)
import boto3
import json
from dataclasses import asdict

sqs = boto3.client("sqs", region_name="us-east-1")

class PedidoPublisher:
    def __init__(self, queue_url: str):
        self._queue_url = queue_url

    def publicar_pedido_confirmado(self, pedido: Pedido) -> None:
        sqs.send_message(
            QueueUrl=self._queue_url,
            MessageBody=json.dumps({
                "evento": "PEDIDO_CONFIRMADO",
                "pedido_id": pedido.id,
                "cliente_id": pedido.cliente_id,
                "valor": str(pedido.valor),
                "timestamp": pedido.confirmado_em.isoformat(),
            }),
            MessageAttributes={
                "EventType": {"DataType": "String", "StringValue": "PEDIDO_CONFIRMADO"}
            },
        )


# Consumer Lambda — SQS trigger direto, sem polling manual
def processar_pedidos(event, context):
    """Lambda consome SQS automaticamente — AWS gerencia polling, retry e DLQ."""
    for record in event["Records"]:
        corpo = json.loads(record["body"])
        try:
            notificacao_service.enviar(
                cliente_id=corpo["cliente_id"],
                mensagem=f"Pedido {corpo['pedido_id']} confirmado!",
            )
        except Exception as e:
            # Ao lançar exceção, AWS re-entrega a mensagem automaticamente
            # Após N tentativas, vai para a Dead Letter Queue
            raise e
```

```java
// Java — Spring Boot 4 + SQS com Spring Cloud AWS 3.x (sem polling manual)
// Dependência: io.awspring.cloud:spring-cloud-aws-starter-sqs
// Virtual Threads compatible: Spring Cloud AWS 3.x works seamlessly with Project Loom

@Service
public class PedidoSQSConsumer {

    // @SqsListener gerencia polling, visibilidade e ACK automaticamente
    @SqsListener(value = "${aws.sqs.pedidos-queue-url}", acknowledgementMode = ON_SUCCESS)
    public void processarPedidoConfirmado(
        @Payload PedidoConfirmadoEvent evento,
        @Headers MessageHeaders headers
    ) {
        log.info("Processando pedido: {}", evento.pedidoId());
        notificacaoService.enviarConfirmacao(evento);
        // ACK automático em sucesso, NACK automático em exceção (re-entrega)
    }
}

// Producer — envio assíncrono
@Service
@RequiredArgsConstructor
public class PedidoPublisher {

    private final SqsTemplate sqsTemplate;

    @Value("${aws.sqs.pedidos-queue-url}")
    private String queueUrl;

    public void publicarPedidoConfirmado(Pedido pedido) {
        sqsTemplate.send(queueUrl, PedidoConfirmadoEvent.from(pedido));
    }
}
```

#### SNS + SQS — Fan-out para Múltiplos Consumidores

```
Padrão SNS → SQS (fan-out):
  SNS Topic
    ├── SQS Queue A (serviço de notificação)
    ├── SQS Queue B (serviço de analytics)
    └── SQS Queue C (serviço de auditoria)

Vantagem: adicionar novo consumidor = criar nova SQS e subscrever ao SNS
          sem tocar em nenhum código existente — verdadeiro desacoplamento
```

#### SQS — Padrões Avançados (DLQ, FIFO, Batch, Poison Message)

```
DEAD LETTER QUEUE (DLQ) — Obrigatória em toda fila SQS:
  Toda fila SQS DEVE ter uma DLQ configurada. Sem DLQ, mensagens que falham
  ficam em loop infinito de retry, desperdiçando compute e mascarando bugs.

  Configuração recomendada:
    maxReceiveCount: 3          → após 3 tentativas, vai para DLQ
    DLQ retention: 14 dias      → tempo para investigar e reprocessar
    Alarme CloudWatch na DLQ    → ApproximateNumberOfMessagesVisible > 0
```

```java
// Java 25 — Spring Cloud AWS 3.x com DLQ handler
@SqsListener("pedidos-dlq")
public void handleDlq(@Payload PedidoEvent evento,
                       @Header("ApproximateReceiveCount") int tentativas) {
    logger.error("Mensagem na DLQ após {} tentativas: pedido_id={}",
                 tentativas, evento.pedidoId());
    // Salvar em tabela de erros para reprocessamento manual
    dlqRepository.salvar(new DlqEntry(evento, tentativas, Instant.now()));
    metricsService.increment("sqs.dlq.received", "queue", "pedidos");
}
```

```
FIFO QUEUES — Quando a ordem importa:
  ✓ Processamento de pagamentos (ordem de transações)
  ✓ Atualizações de status (evitar status antigo sobrescrever novo)
  ✓ Idempotência nativa (MessageDeduplicationId evita duplicatas)

  Nome da fila DEVE terminar em .fifo: pedidos-processamento.fifo
  Throughput: 300 msg/s sem batching, 3.000 msg/s com batching

  MessageGroupId → garante ordem DENTRO do grupo
  Exemplo: MessageGroupId = pedidoId → mensagens do mesmo pedido em ordem
           mas pedidos diferentes processados em paralelo
```

```java
// Java 25 — Envio para FIFO Queue com deduplicação
@Component
public class PedidoSqsFifoPublisher {

    private final SqsTemplate sqsTemplate;

    public void publicar(PedidoEvent evento) {
        sqsTemplate.send(to -> to
            .queue("pedidos-processamento.fifo")
            .payload(evento)
            .header(SqsHeaders.SQS_GROUP_ID_HEADER, evento.pedidoId().toString())
            .header(SqsHeaders.SQS_DEDUPLICATION_ID_HEADER,
                    evento.pedidoId() + "-" + evento.timestamp())
        );
    }
}
```

```
BATCH PROCESSING — Reduzir custo e aumentar throughput:
  SQS cobra por request. Batching reduz requests em até 10x.

  Receber: maxNumberOfMessages=10, waitTimeSeconds=20 (long polling)
  Enviar:  SendMessageBatch com até 10 mensagens por request

  Spring Cloud AWS 3.x: configuração automática via @SqsListener
    maxMessagesPerPoll: 10
    maxConcurrentMessages: 25    → 25 Virtual Threads processando
    pollTimeoutSeconds: 20       → long polling (evita requests vazios)
```

```yaml
# application.yml — SQS otimizado com Virtual Threads
spring:
  cloud:
    aws:
      sqs:
        listener:
          max-messages-per-poll: 10
          max-concurrent-messages: 25
          poll-timeout-seconds: 20
```

```
POISON MESSAGE HANDLING — Proteger contra mensagens malformadas:
  1. Deserializar dentro de try/catch
  2. Se falhar, logar corpo raw + enviar para DLQ imediatamente (não retry)
  3. Se processar parcialmente, usar acknowledgement manual

  REGRA: Nunca lance exceção não-tratada em @SqsListener.
         Isso causa retry infinito até maxReceiveCount → DLQ.
         Capture, classifique (transiente vs permanente) e trate.
```

```java
// Java 25 — Pattern Matching para validação e roteamento de mensagens malformadas

// Sealed interface com subtypes para cada caso de validação
sealed interface MessageValidationResult {
    record Valid(PedidoEvent evento) implements MessageValidationResult {}
    record Malformed(String reason) implements MessageValidationResult {}
    record MissingField(String field, boolean isCritical) implements MessageValidationResult {}
    record CorruptedJson(String rawMessage, Exception cause) implements MessageValidationResult {}
    record OversizedPayload(int size, int limit) implements MessageValidationResult {}
}

// Classe que valida mensagens com Pattern Matching
@Component
public class MessageValidator {

    private static final int MAX_PAYLOAD = 1_000_000; // 1MB
    private final ObjectMapper mapper;

    public MessageValidationResult validar(String rawMessage) {
        // Tamanho
        if (rawMessage.length() > MAX_PAYLOAD) {
            return new MessageValidationResult.OversizedPayload(rawMessage.length(), MAX_PAYLOAD);
        }

        // Parsing JSON
        JsonNode node;
        try {
            node = mapper.readTree(rawMessage);
        } catch (JsonProcessingException e) {
            return new MessageValidationResult.CorruptedJson(rawMessage, e);
        }

        // Campos críticos vs opcionais
        if (!node.has("pedidoId")) {
            return new MessageValidationResult.MissingField("pedidoId", true);
        }
        if (!node.has("clienteId")) {
            return new MessageValidationResult.MissingField("clienteId", true);
        }
        if (!node.has("timestamp")) {
            return new MessageValidationResult.MissingField("timestamp", false);
        }

        // Sucesso
        try {
            var evento = mapper.convertValue(node, PedidoEvent.class);
            return new MessageValidationResult.Valid(evento);
        } catch (Exception e) {
            return new MessageValidationResult.Malformed(e.getMessage());
        }
    }
}

// Handler SQS com Pattern Matching que roteia automaticamente
@Service
@RequiredArgsConstructor
public class PedidoSqsConsumer {

    private final MessageValidator validator;
    private final PedidoService pedidoService;
    private final MicrometerMetrics metrics;
    private final DlqPublisher dlq;

    @SqsListener("pedidos-processamento")
    public void processar(@Payload String rawMessage, Acknowledgement ack,
                          @Header("ApproximateReceiveCount") int tentativas) {
        // Pattern matching sobre o resultado de validação
        switch (validator.validar(rawMessage)) {
            // Sucesso — processar normalmente
            case MessageValidationResult.Valid(var evento) -> {
                logger.info("Processando pedido: {}", evento.pedidoId());
                try {
                    pedidoService.processar(evento);
                    ack.acknowledge();  // Remove da fila
                    metrics.increment("sqs.processed", "status", "success");
                } catch (ServiceException e) {
                    // Erro transiente → deixa SQS retentar (não faz ack)
                    logger.warn("Erro transiente (retry #{}/3): {}", tentativas, e.getMessage());
                    metrics.increment("sqs.processed", "status", "retry");
                    if (tentativas >= 3) {
                        ack.acknowledge();
                        dlq.send(rawMessage, "Transient error after 3 retries");
                    }
                }
            }

            // Falhas permanentes — enviar para DLQ imediatamente, sem retry
            case MessageValidationResult.Malformed(var reason) -> {
                logger.error("Mensagem malformada: {}", reason);
                ack.acknowledge();  // Remove para não ficar em loop infinito
                dlq.send(rawMessage, "Malformed: " + reason);
                metrics.increment("sqs.poison_messages_total", "reason", "malformed");
            }

            case MessageValidationResult.CorruptedJson(var msg, var cause) -> {
                logger.error("JSON corrompido: {}", cause.getMessage(), cause);
                ack.acknowledge();  // Remove imediatamente
                dlq.send(msg, "Corrupted JSON: " + cause.getMessage());
                metrics.increment("sqs.poison_messages_total", "reason", "corrupted_json");
            }

            case MessageValidationResult.OversizedPayload(var size, var limit) -> {
                logger.error("Payload muito grande: {} > {}", size, limit);
                ack.acknowledge();
                dlq.send(rawMessage, "Oversized: " + size + " > " + limit);
                metrics.increment("sqs.poison_messages_total", "reason", "oversized");
            }

            // Campos faltantes — decisão baseada em criticidade
            case MessageValidationResult.MissingField(var field, boolean isCritical) -> {
                if (isCritical) {
                    logger.error("Campo crítico faltando: {}", field);
                    ack.acknowledge();
                    dlq.send(rawMessage, "Missing critical field: " + field);
                    metrics.increment("sqs.poison_messages_total", "reason", "missing_critical");
                } else {
                    logger.warn("Campo opcional faltando: {} — processando com defaults", field);
                    ack.acknowledge();
                    // Processar com valores padrão (implementação domain-específica)
                    metrics.increment("sqs.processed", "status", "partial");
                }
            }
        }
    }
}

// Publicador de DLQ
@Component
public class DlqPublisher {
    private final SqsTemplate sqsTemplate;

    public void send(String rawMessage, String reason) {
        sqsTemplate.send(to -> to
            .queue("pedidos-dlq")
            .payload(rawMessage)
            .header("X-Error-Reason", reason)
            .header("X-Timestamp", Instant.now().toString())
        );
    }
}

// Configuração Micrometer para métricas
@Configuration
public class MetricsConfig {

    @Bean
    public MeterBinder sqlsPoisonMetrics(MeterRegistry registry) {
        return (reg) -> Counter.builder("sqs_poison_messages_total")
            .description("Total de mensagens poison processadas por razão")
            .tag("queue", "pedidos")
            .register(reg);
    }
}

// AlertManager — CloudWatch alerta se poison > 1% em 5min
/*
Metric Alarm Configuration:
  - MetricName: sqs_poison_messages_total
  - Statistic: Sum
  - Period: 300s (5 min)
  - Threshold: 1% of total messages
  - Action: SNS topic (page on-call if > 10 poison/5min)
*/
```

**Benefícios:**
- ✓ **Pattern Matching** (Java 25): cada tipo de erro é uma classe, compilador garante cobertura
- ✓ **Sem retry inútil**: malformed/corrupted vão direto para DLQ
- ✓ **Métricas por tipo**: `sqs_poison_messages_total{reason="..."}`
- ✓ **Alertas automáticos**: CloudWatch detecta > 1% poison → page on-call
- ✓ **Graceful degradation**: campos opcionais faltando permitem processar com defaults

#### EventBridge — Orquestração de Eventos sem Código

```
Quando usar EventBridge em vez de SQS:
  ✓ Roteamento de eventos baseado em conteúdo (regras sem código)
  ✓ Integração com +200 serviços AWS e SaaS nativamente
  ✓ Agendamento de jobs (EventBridge Scheduler substitui cron)
  ✓ Replay de eventos para reprocessamento

Preço (fatos-verificados-aws.md §3): no bus Classic, AWS management events são ingeridos
de graça; custom events são cobrados por milhão (cada bloco de 64 KB = 1 evento).
Os 14 milhões grátis/mês são do EventBridge SCHEDULER (invocações), não do bus.

# Regra de roteamento sem código:
# "quando pedido.status == CANCELADO e pedido.valor > 1000,
#  chamar Lambda de alerta de alto valor"
# → configuração no console/CDK, zero código de routing
```

#### EventBridge Rules & Content Filtering — Fan-out com Roteamento Inteligente

**Diferença crítica:** EventBridge **Scheduler** = jobs agendados (cron). EventBridge **Rules** = roteamento de eventos baseado em conteúdo (event-driven).

```
EventBridge Rules:
  ✓ Content-based filtering (matchers: prefix, suffix, numeric, exists, cidr, anything-but)
  ✓ Fan-out para múltiplos targets (SQS, Lambda, SNS, Step Functions, API Destinations)
  ✓ Dead Letter Queue para targets que falham
  ✓ Retry automático com backoff exponencial
  ✓ Zero código de routing — configuração apenas

Matchers disponíveis:
  - { "prefix": "ORDER" }               → evento["orderId"] começa com "ORDER"
  - { "suffix": "-URGENT" }             → termina com "-URGENT"
  - { "anything-but": "CANCELLED" }     → qualquer coisa MENOS "CANCELLED"
  - { "numeric": [ ">", 1000 ] }        → valor > 1000
  - { "exists": true }                  → campo existe
  - { "cidr": "10.0.0.0/8" }            → IP dentro da rede
```

**Exemplo: Fan-out baseado em valor de pedido**

```json
{
  "Name": "RoteioPedidosPorValor",
  "EventBusName": "default",
  "EventPattern": {
    "source": ["ecommerce"],
    "detail-type": ["OrderCreated"],
    "detail": {
      "amount": [{ "numeric": [">", 1000] }]  // ← Apenas pedidos > R$1000
    }
  },
  "State": "ENABLED",
  "Targets": [
    {
      "Id": "HighValueOrdersQueue",
      "Arn": "arn:aws:sqs:us-east-1:123:pedidos-alto-valor",
      "RoleArn": "arn:aws:iam::123:role/EventBridgeRole",
      "DeadLetterConfig": {
        "Arn": "arn:aws:sqs:us-east-1:123:pedidos-dlq"
      },
      "RetryPolicy": {
        "MaximumEventAge": 3600,
        "MaximumRetryAttempts": 2
      }
    },
    {
      "Id": "AlertaGerencia",
      "Arn": "arn:aws:lambda:us-east-1:123:function:alertar-gerencia",
      "RoleArn": "arn:aws:iam::123:role/EventBridgeRole"
    }
  ]
}
```

**Paralelamente, rule para pedidos normais (amount ≤ 1000):**

```json
{
  "Name": "RoteioPedidosNormais",
  "EventPattern": {
    "source": ["ecommerce"],
    "detail-type": ["OrderCreated"],
    "detail": {
      "amount": [{ "numeric": ["<=", 1000] }]  // ← Pedidos <= R$1000
    }
  },
  "Targets": [
    {
      "Id": "StandardOrdersQueue",
      "Arn": "arn:aws:sqs:us-east-1:123:pedidos-processamento",
      "DeadLetterConfig": {
        "Arn": "arn:aws:sqs:us-east-1:123:pedidos-dlq"
      }
    }
  ]
}
```

**CDK Java 25 — Definir rules e targets programaticamente:**

```java
@Component
public class OrderEventRoutingStack {

    public void setupRules(Stack stack, IEventBus eventBus,
                          Queue highValueQueue, Queue standardQueue,
                          IFunction alertFunction) {

        // Rule para pedidos de alto valor (> R$1000)
        Rule highValueRule = Rule.Builder.create(stack, "HighValueOrdersRule")
            .eventBus(eventBus)
            .eventPattern(EventPattern.builder()
                .source(List.of("ecommerce"))
                .detailType(List.of("OrderCreated"))
                .detail(Map.of(
                    "amount", Map.of("numeric", List.of(">", 1000))
                ))
                .build())
            .description("Roteia pedidos > R$1000 para fila prioritária")
            .build();

        // Targets: SQS + Lambda
        highValueRule.addTarget(new SqsQueue(highValueQueue,
            SqsQueueProps.builder()
                .deadLetterQueue(new Queue(stack, "HighValueDLQ"))
                .retryAttempts(2)
                .maxEventAge(Duration.hours(1))
                .build()));

        highValueRule.addTarget(new LambdaFunction(alertFunction,
            LambdaFunctionProps.builder()
                .retryAttempts(1)
                .build()));

        // Rule para pedidos normais (≤ R$1000)
        Rule standardRule = Rule.Builder.create(stack, "StandardOrdersRule")
            .eventBus(eventBus)
            .eventPattern(EventPattern.builder()
                .source(List.of("ecommerce"))
                .detailType(List.of("OrderCreated"))
                .detail(Map.of(
                    "amount", Map.of("numeric", List.of("<=", 1000))
                ))
                .build())
            .build();

        standardRule.addTarget(new SqsQueue(standardQueue,
            SqsQueueProps.builder()
                .deadLetterQueue(new Queue(stack, "StandardDLQ"))
                .build()));
    }
}
```

**Consumers (Lambda / SQS listeners) — nenhuma lógica de roteamento, só processamento:**

```java
// Lambda que consome da fila de alto valor — nenhuma validação de amount
@Component
public class HighValueOrderProcessor {

    @SqsListener("pedidos-alto-valor")
    public void processar(@Payload OrderEvent evento) {
        // EventBridge garantiu que amount > 1000
        // Implementar lógica de negócio, não validação
        logger.info("Processando pedido de alto valor: {}", evento.orderId());
        criarNotaFiscalPrioritaria(evento);
        enviarParaGerencia(evento);
    }
}
```

**Benefícios:**
- ✓ **Zero código de roteamento**: regras declarativas no EventBridge
- ✓ **DLQ automática**: targets que falham vão para DLQ configurada
- ✓ **Retry inteligente**: backoff exponencial, max attempts configurável
- ✓ **Fan-out nativo**: múltiplos targets por rule, sem SQS intermediário
- ✓ **Monitoramento**: CloudWatch Metrics por rule + target
- ✓ **Replayable**: historicamente todos os eventos podem ser reprocessados

---

#### Step Functions — Saga Pattern para Transações Distribuídas

```
Quando usar Step Functions (vs EventBridge):
  ✓ Workflow com estado (precisa saber "onde estou no processo")
  ✓ Compensação em caso de falha (saga pattern)
  ✓ Orquestração de múltiplos serviços com retry por etapa
  ✓ Processos de longa duração (até 1 ano)
  ✗ Roteamento simples de eventos → use EventBridge
  ✗ Fan-out para múltiplos consumidores → use SNS+SQS

Preço (fatos-verificados-aws.md §1): Standard cobra por transição (4.000/mês grátis, sem
expiração; cada retry conta); Express cobra requisição + duração (sem free tier citado).
```

```
SAGA PATTERN — Orquestrado (Step Functions):
  Quando um processo de negócio envolve múltiplos serviços e cada etapa
  pode falhar, use saga com compensação automática:

  ┌──────────┐    ┌──────────┐    ┌──────────┐
  │ Reservar  │───▶│  Cobrar   │───▶│  Enviar  │ → SUCESSO
  │ Estoque  │    │ Pagamento │    │  Pedido  │
  └────┬─────┘    └────┬──────┘    └────┬─────┘
       │ falha         │ falha          │ falha
       ▼               ▼               ▼
  ┌──────────┐    ┌──────────┐    ┌──────────┐
  │ (noop)   │◀───│ Liberar   │◀───│ Estornar │
  │          │    │ Estoque  │    │ + Liberar │
  └──────────┘    └──────────┘    └──────────┘
```

```json
// Step Functions — Amazon States Language (exemplo simplificado)
{
  "Comment": "Saga: Processar Pedido com Compensação",
  "StartAt": "ReservarEstoque",
  "States": {
    "ReservarEstoque": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:123:function:reservar-estoque",
      "Catch": [{ "ErrorEquals": ["States.ALL"], "Next": "FalhaSemCompensacao" }],
      "Next": "CobrarPagamento"
    },
    "CobrarPagamento": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:123:function:cobrar-pagamento",
      "Catch": [{ "ErrorEquals": ["States.ALL"], "Next": "CompensarEstoque" }],
      "Next": "EnviarPedido"
    },
    "EnviarPedido": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:123:function:enviar-pedido",
      "Catch": [{ "ErrorEquals": ["States.ALL"], "Next": "CompensarPagamento" }],
      "End": true
    },
    "CompensarPagamento": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:123:function:estornar-pagamento",
      "Next": "CompensarEstoque"
    },
    "CompensarEstoque": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:123:function:liberar-estoque",
      "Next": "FalhaSemCompensacao"
    },
    "FalhaSemCompensacao": {
      "Type": "Fail",
      "Error": "SagaFailed",
      "Cause": "Pedido falhou — compensações executadas"
    }
  }
}
```

```java
// Java 25 — CDK para definir Step Functions com Saga
var reservarEstoque = LambdaInvoke.Builder.create(this, "ReservarEstoque")
    .lambdaFunction(reservarEstoqueFn)
    .resultPath("$.estoque")
    .build();

var cobrarPagamento = LambdaInvoke.Builder.create(this, "CobrarPagamento")
    .lambdaFunction(cobrarPagamentoFn)
    .resultPath("$.pagamento")
    .build();

var compensarEstoque = LambdaInvoke.Builder.create(this, "CompensarEstoque")
    .lambdaFunction(liberarEstoqueFn)
    .build();

var compensarPagamento = LambdaInvoke.Builder.create(this, "CompensarPagamento")
    .lambdaFunction(estornarPagamentoFn)
    .next(compensarEstoque)
    .build();

// Encadear com compensação
cobrarPagamento.addCatch(compensarEstoque, CatchProps.builder().build());
var enviarPedido = LambdaInvoke.Builder.create(this, "EnviarPedido")
    .lambdaFunction(enviarPedidoFn).build();
enviarPedido.addCatch(compensarPagamento, CatchProps.builder().build());

var definition = reservarEstoque.next(cobrarPagamento).next(enviarPedido);

StateMachine.Builder.create(this, "SagaPedido")
    .definition(definition)
    .tracingEnabled(true)  // X-Ray automático
    .build();
```

```
SAGA COREOGRAFADO (alternativa sem Step Functions):
  Cada serviço publica evento de sucesso/falha via SNS/SQS.
  Serviços seguintes reagem ao evento.

  Vantagem: mais desacoplado, sem orquestrador central
  Desvantagem: difícil rastrear estado geral, compensação complexa

  Recomendação P1 (simplicidade): use Step Functions (orquestrado) quando
  tiver mais de 3 etapas. Saga coreografado só para 2-3 etapas simples.
```

> **Consistência transacional entre BD local e Saga** — quando uma etapa precisa gravar
> no banco E disparar o próximo passo Step Functions, **nunca** faça chamada direta ao
> Step Functions dentro do `@Transactional`. Use o **Outbox Pattern** (ver
> [[Skill - especialista-banco]] §9.1): escreva o evento numa tabela `outbox` na mesma
> transação do domínio; um poller lê a tabela e chama `StartExecution` (ou publica em
> EventBridge que aciona a State Machine). Isso garante publicação **at-least-once** mesmo
> com crash entre commit e chamada remota — o efeito único exige consumidor idempotente
> (ex.: `name` determinístico no `StartExecution` do Standard). Alternativa sem tabela extra:
> captura de mudanças (DynamoDB Streams → EventBridge Pipes) — ver `../../aws-serverless-eda/references/eventbridge.md`.

---

## SQS — Especialista Enterprise

> SQS é a fila gerenciada mais robusta do mundo. Mas é fácil errar e ter mensagens duplicadas, ordem quebrada, ou pool exhaustion. Domine cada parâmetro.

### Standard vs FIFO — Quando Cada Um

| Característica | **Standard** | **FIFO** |
|----------------|--------------|----------|
| Throughput | **Quase ilimitado** (3000+ msg/s default, request increase pra > 100K) | 300 msg/s sem batching, 3000 com batching, 70K com **High Throughput Mode** |
| Ordem | Best-effort | **Garantida por MessageGroupId** |
| Entrega | At-least-once (duplicatas possíveis) | Exactly-once (dedup por 5 min) |
| Latência | < 10 ms | < 10 ms |
| Custo (1M req) | $0.40 | $0.50 |
| Use case | Maioria dos casos: workers, fan-out, jobs idempotentes | Pagamentos, status updates, eventos com ordem dependente |

**Regra:** **Standard por default**. Use FIFO **só** quando ordem importa (pagamentos por usuário, status updates de pedido, webhooks ordenados).

### High Throughput FIFO Mode

FIFO com ordering por **MessageGroupId** mas sem ordem global → 70.000 msg/s sustentado:

```java
Queue fifoQueue = Queue.Builder.create(this, "PaymentsFifoQueue")
    .queueName("payments.fifo")
    .fifo(true)
    .contentBasedDeduplication(true)
    .deduplicationScope(DeduplicationScope.MESSAGE_GROUP)   // ⭐ por grupo, não global
    .fifoThroughputLimit(FifoThroughputLimit.PER_MESSAGE_GROUP_ID)  // ⭐ habilitar HT mode
    .visibilityTimeout(Duration.seconds(60))
    .receiveMessageWaitTime(Duration.seconds(20))           // long polling
    .deadLetterQueue(DeadLetterQueue.builder()
        .queue(dlq)
        .maxReceiveCount(3)
        .build())
    .build();
```

**Resultado:** ordem garantida **por usuário** (MessageGroupId = userId), throughput agregado de 70K msg/s.

### Long Polling — SEMPRE habilitado

```java
Queue queue = Queue.Builder.create(this, "OrdersQueue")
    .receiveMessageWaitTime(Duration.seconds(20))   // ⭐ 20s = max
    .build();
```

**Sem long polling:** consumer faz ReceiveMessage a cada 100ms → 600 req/min vazias → custo + latência ruim.
**Com long polling:** consumer espera até 20s → uma fila vazia faz 3 req/min → custo despreza.

### Batching — 10x Throughput, 1/10 Custo

**Send batch:**
```java
SqsClient sqs = SqsClient.create();

SendMessageBatchResponse response = sqs.sendMessageBatch(req -> req
    .queueUrl(queueUrl)
    .entries(messages.stream()
        .map(m -> SendMessageBatchRequestEntry.builder()
            .id(UUID.randomUUID().toString())
            .messageBody(m.body())
            .messageAttributes(Map.of(
                "correlationId", attr(m.correlationId())
            ))
            .build())
        .toList()));
```

**Receive batch:**
```java
ReceiveMessageResponse response = sqs.receiveMessage(req -> req
    .queueUrl(queueUrl)
    .maxNumberOfMessages(10)              // ⭐ máximo permitido
    .waitTimeSeconds(20)
    .messageAttributeNames("All"));
```

**Cobrança:** SQS cobra por **request**, não por mensagem. Batch de 10 = mesmo preço que 1 request. **Sempre batch.**

### Visibility Timeout — Tuning Crítico

**Erro comum:** deixar default (30s) e mensagem ficar visível antes do worker terminar → duplicação e cascata.

**Regra:** `visibility_timeout = p99 do tempo de processamento × 6`.

Exemplo: se p99 do worker é 5s, visibility = 30s. Se p99 é 30s, visibility = 180s.

**Para workers de longa duração**, use `ChangeMessageVisibility` para estender em runtime:
```java
sqs.changeMessageVisibility(req -> req
    .queueUrl(queueUrl)
    .receiptHandle(receiptHandle)
    .visibilityTimeout(300));        // estende para 5 min
```

### DLQ + Redrive Policy — Obrigatório

```java
Queue dlq = Queue.Builder.create(this, "OrdersDlq")
    .queueName("orders-dlq")
    .retentionPeriod(Duration.days(14))         // ⭐ 14 dias = max
    .build();

Queue mainQueue = Queue.Builder.create(this, "OrdersQueue")
    .queueName("orders")
    .deadLetterQueue(DeadLetterQueue.builder()
        .queue(dlq)
        .maxReceiveCount(3)                     // 3 falhas → DLQ
        .build())
    .build();

// Alarme em DLQ
new Alarm(this, "DlqHasMessages", AlarmProps.builder()
    .metric(dlq.metricApproximateNumberOfMessagesVisible())
    .threshold(0)
    .comparisonOperator(ComparisonOperator.GREATER_THAN_THRESHOLD)
    .evaluationPeriods(1)
    .build());

// Redrive task — mover msgs do DLQ de volta para main
// Habilitado via console ou CLI: aws sqs start-message-move-task --source-arn $DLQ
```

**Toda mensagem em DLQ é um bug.** Investigar SEMPRE. Não criar política de "limpar DLQ no fim do mês".

### Lambda Event Source Mapping (ESM) — Tuning

```java
Function consumer = Function.Builder.create(this, "OrderConsumer")
    .runtime(Runtime.JAVA_25)
    .architecture(Architecture.ARM_64)
    .memorySize(2048)
    .timeout(Duration.minutes(15))
    .snapStart(SnapStartConf.ON_PUBLISHED_VERSIONS)
    .build();

consumer.addEventSource(SqsEventSource.Builder.create(queue)
    .batchSize(10)                              // 10 msgs por invocação
    .maxBatchingWindow(Duration.seconds(5))     // ou 5s, o que vier antes
    .reportBatchItemFailures(true)              // ⭐ partial batch failure
    .maxConcurrency(100)                        // limita Lambda concurrency
    .build());
```

**Partial Batch Failure** é o feature mais importante: handler retorna lista de IDs que falharam, só esses voltam para a fila (resto é deletado). Sem isso, 1 msg ruim no batch reprocessa as 10.

Handler:
```java
public class OrderHandler implements RequestHandler<SQSEvent, SQSBatchResponse> {

    @Override
    public SQSBatchResponse handleRequest(SQSEvent event, Context ctx) {
        List<SQSBatchResponse.BatchItemFailure> failures = new ArrayList<>();

        for (SQSEvent.SQSMessage msg : event.getRecords()) {
            try {
                processOrder(msg);
            } catch (TransientException e) {
                failures.add(SQSBatchResponse.BatchItemFailure.builder()
                    .withItemIdentifier(msg.getMessageId())
                    .build());
            } catch (PermanentException e) {
                // log + ack (não retorna em failures = considerado sucesso)
                log.error("Permanent failure, sending to DLQ-manual: {}", msg.getMessageId(), e);
                manualDlqClient.send(msg);
            }
        }

        return SQSBatchResponse.builder()
            .withBatchItemFailures(failures)
            .build();
    }
}
```

### Maximum Concurrency — Proteção contra Downstream Overload

ESM com Lambda pode escalar até 1000 invocações concorrentes (default). Se downstream (RDS, API externa) só aguenta 100, isso é receita para pool exhaustion + cascade failure.

```java
SqsEventSource.Builder.create(queue)
    .maxConcurrency(50)                  // ⭐ máx 50 invocações concorrentes
    .build();
```

### Extended Client — Mensagens > 256 KB

SQS limita payload a 256 KB. Para payloads maiores (XML grande, JSON com base64), use Extended Client que armazena no S3 e passa só o ponteiro:

```xml
<dependency>
    <groupId>com.amazonaws</groupId>
    <artifactId>amazon-sqs-java-extended-client-lib</artifactId>
    <version>2.1.0</version>
</dependency>
```

```java
ExtendedClientConfiguration config = new ExtendedClientConfiguration()
    .withPayloadSupportEnabled(s3Client, "sqs-large-payloads-bucket")
    .withAlwaysThroughS3(false)              // só payloads > 256 KB
    .withPayloadSizeThreshold(262144);       // 256 KB

SqsClient sqs = new AmazonSQSExtendedClient(SqsClient.create(), config);
```

**Custo extra:** S3 storage + GET/PUT por mensagem. Use só quando necessário.

### Métricas Críticas

| Métrica | Threshold | Significado |
|---------|-----------|-------------|
| `ApproximateAgeOfOldestMessage` | > 5 min | Backlog grande, scale consumers |
| `ApproximateNumberOfMessagesVisible` | > 1000 sustentado | Workers não acompanham produção |
| `NumberOfMessagesSent` vs `NumberOfMessagesDeleted` | divergência | Workers travados ou erro |
| `ApproximateNumberOfMessagesNotVisible` | constante alto | Visibility timeout muito longo ou worker travado |
| `NumberOfMessagesReceived` (DLQ) | > 0 | **PagerDuty crítico** |

### Padrão Idempotência (obrigatório com SQS Standard)

SQS Standard pode entregar mensagem 2+ vezes. Consumer **DEVE** ser idempotente.

```java
@Component
public class IdempotenteOrderProcessor {

    private final IdempotencyStore store;          // DynamoDB com TTL

    public void process(OrderEvent event) {
        String idempotencyKey = event.id();         // chave estável

        if (store.alreadyProcessed(idempotencyKey)) {
            log.info("Skipping duplicate: {}", idempotencyKey);
            return;
        }

        // executa lógica
        orderService.confirm(event);

        store.markProcessed(idempotencyKey, Duration.ofDays(7));
    }
}
```

**Power Tools for AWS Lambda (Java)** tem `@Idempotent` annotation que faz isso automaticamente com DynamoDB backend.

---

