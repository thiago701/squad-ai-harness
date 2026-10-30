# Referência — Saga Pattern (transações distribuídas: orquestrada com Step Functions · coreografada com SQS/SNS)

> Parte da skill `engenheiro-devops`. Carregue sob demanda. Hub: `../SKILL.md`.
> Movido verbatim de `principios-e-deploy.md` §6.2.1 (ciclo 6a do Loop V3, 2026-07-09).

### 6.2.1 Saga Pattern — Distributed Transactions em Microserviços

Padrão de resiliência para **transações distribuídas** em arquiteturas de microserviços. Substitui o anti-padrão 2PC (Two-Phase Commit) que travaria todo o sistema se uma dependência cair.

**Por que Saga?** Em um sistema distribuído (pedidos → estoque → pagamento → notificação):
- 2PC: coordenador travaria se qualquer nó não responder → downtime
- Saga: cada step falha independentemente, compensação explícita

**2 estilos:**

| Estilo | Orquestração | Exemplo | Recomendado |
|--------|---|---|---|
| **Orquestrada** | State machine central (AWS Step Functions, Apache Temporal) | Pedido → StepFunction → atividade reservar → atividade cobrar → atividade notificar | Cloud native (P1 = Simplicidade) |
| **Coreografada** | Services se comunicam via eventos (SQS, SNS, EventBridge) | PedidoService publica `PedidoCriado` → EstoqueService consome → publica `EstoqueReservado` | Sistemas com muitos services |

**Exemplo: Saga Orquestrada com AWS Step Functions**

```
Saga de Pedido (Order Saga):
  1. Reservar Estoque (if falha → rollback para compensar estoque restante)
  2. Debitar Pagamento (if falha → devolver estoque + return erro)
  3. Enviar Notificação (if falha → não bloqueia — tentativa assíncrona)
  4. Confirmar Pedido (idempotent)

Cada step tem:
  - Happy path: sucesso → próximo step
  - Failure path: falha + compensação (desfazer ação anterior)
```

```json
{
  "Comment": "Order Saga — Reservar Estoque → Cobrar → Notificar → Confirmar",
  "StartAt": "ReserveInventory",
  "States": {
    "ReserveInventory": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:111111111111:function:ReserveInventory",
      "Parameters": {
        "orderId.$": "$.orderId",
        "items.$": "$.items"
      },
      "Catch": [
        {
          "ErrorEquals": ["InsufficientInventory"],
          "Next": "ReserveInventoryFailed"
        }
      ],
      "Next": "ChargePayment"
    },

    "ChargePayment": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:111111111111:function:ChargePayment",
      "Parameters": {
        "orderId.$": "$.orderId",
        "amount.$": "$.totalAmount",
        "cardToken.$": "$.cardToken"
      },
      "Catch": [
        {
          "ErrorEquals": ["PaymentFailed"],
          "ResultPath": "$.error",
          "Next": "ReleaseInventory"  # Compensação
        }
      ],
      "Next": "SendNotification"
    },

    "SendNotification": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:111111111111:function:SendNotification",
      "Parameters": {
        "orderId.$": "$.orderId",
        "email.$": "$.customerEmail",
        "status": "order_confirmed"
      },
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed"],
          "IntervalSeconds": 5,
          "MaxAttempts": 3,
          "BackoffRate": 1.5
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.notificationError",
          "Next": "ConfirmOrder"  # Não bloqueia confirmação
        }
      ],
      "Next": "ConfirmOrder"
    },

    "ConfirmOrder": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:111111111111:function:ConfirmOrder",
      "Parameters": {
        "orderId.$": "$.orderId"
      },
      "Next": "SagaSuccess"
    },

    # ─────── COMPENSAÇÕES ───────
    "ReleaseInventory": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:111111111111:function:ReleaseInventory",
      "Parameters": {
        "orderId.$": "$.orderId",
        "items.$": "$.items"
      },
      "Next": "SagaFailed"
    },

    "ReserveInventoryFailed": {
      "Type": "Pass",
      "Result": "Inventory reservation failed",
      "ResultPath": "$.error",
      "Next": "SagaFailed"
    },

    "SagaSuccess": {
      "Type": "Succeed"
    },

    "SagaFailed": {
      "Type": "Fail",
      "Cause": "Order saga failed",
      "Error": "SagaFailure"
    }
  }
}
```

```java
// Java: invocar saga do seu microserviço
@Service
public class OrderService {

    private final SfnClient stepFunctionsClient;
    private final CorrelationIdContext correlationIdContext;  // Propagar Correlation ID

    public void submitOrderSaga(OrderCommand cmd) {
        String sagaInput = """
            {
              "orderId": "%s",
              "items": %s,
              "totalAmount": %s,
              "cardToken": "%s",
              "customerEmail": "%s",
              "correlationId": "%s"
            }
            """.formatted(
                cmd.orderId(),
                JsonUtils.toJson(cmd.items()),
                cmd.totalAmount(),
                cmd.cardToken(),
                cmd.customerEmail(),
                CorrelationIdContext.currentOrNew()
            );

        StartExecutionRequest request = StartExecutionRequest.builder()
                .stateMachineArn("arn:aws:states:us-east-1:111111111111:stateMachine:OrderSaga")
                .name("order-" + cmd.orderId())  // Idempotency key
                .input(sagaInput)
                .build();

        ExecutionArn arn = stepFunctionsClient.startExecution(request);
        LOG.info("Order saga started", Map.of(
            "orderId", cmd.orderId(),
            "executionArn", arn.executionArn(),
            "correlationId", CorrelationIdContext.currentOrNew()
        ));
    }

    // Polling para saber resultado (ou usar EventBridge para callbacks)
    public OrderSagaStatus checkSagaStatus(String executionArn) {
        DescribeExecutionRequest req = DescribeExecutionRequest.builder()
                .executionArn(executionArn)
                .build();

        ExecutionDescription desc = stepFunctionsClient.describeExecution(req);

        return switch (desc.status()) {
            case RUNNING -> OrderSagaStatus.RUNNING;
            case SUCCEEDED -> OrderSagaStatus.SUCCESS;
            case FAILED -> OrderSagaStatus.FAILED;
            case ABORTED -> OrderSagaStatus.ABORTED;
            default -> OrderSagaStatus.UNKNOWN;
        };
    }
}
```

**Exemplo: Saga Coreografada com SQS/SNS**

```java
// PedidoService publica evento
@Service
public class PedidoService {

    private final SqsPublisher sqsPublisher;
    private final CorrelationIdContext correlationIdContext;

    public void criarPedido(PedidoCommand cmd) {
        // 1. Criar pedido localmente
        Pedido pedido = new Pedido(cmd.clienteId(), cmd.itens());
        pedidoRepository.save(pedido);

        // 2. Publicar evento para iniciar saga
        sqsPublisher.publish("pedido-eventos", 
            new PedidoCriadoEvent(
                pedido.id(),
                pedido.itens(),
                pedido.total(),
                CorrelationIdContext.currentOrNew()
            )
        );

        LOG.info("Pedido criado e saga iniciada", Map.of(
            "pedidoId", pedido.id(),
            "correlationId", CorrelationIdContext.currentOrNew()
        ));
    }
}

// EstoqueService consome e responde
@Component
public class EstoqueConsumer {

    private final EstoqueRepository estoqueRepository;
    private final SqsPublisher sqsPublisher;

    @SqsListener("pedido-eventos")
    public void handlePedidoCriado(PedidoCriadoEvent event) {
        try {
            // 1. Tentar reservar estoque
            Reserva reserva = estoqueRepository.reservar(event.itens());

            // 2. Publicar sucesso
            sqsPublisher.publish("estoque-eventos",
                new EstoqueReservadoEvent(
                    event.pedidoId(),
                    reserva.id(),
                    event.correlationId()
                )
            );
            LOG.info("Estoque reservado", Map.of(
                "pedidoId", event.pedidoId(),
                "reservaId", reserva.id(),
                "correlationId", event.correlationId()
            ));
        } catch (InsufficientInventoryException e) {
            // 3. Publicar falha (trigger compensação)
            sqsPublisher.publish("estoque-eventos",
                new EstoqueReservadoFailedEvent(
                    event.pedidoId(),
                    e.getMessage(),
                    event.correlationId()
                )
            );
            LOG.warn("Estoque insuficiente", Map.of(
                "pedidoId", event.pedidoId(),
                "correlationId", event.correlationId()
            ));
        }
    }
}
```

#### Testes: Validar Compensação

```java
// Teste: simular falha em cada step e validar compensação
@SpringBootTest
public class OrderSagaCompensationTest {

    private final StepFunctionsTest sfnTest;
    private final OrderRepository orderRepository;

    @Test
    public void testSagaCompensationOnPaymentFailure() {
        // 1. Arrange: setup saga com payment failure
        String orderId = "order-12345";
        OrderCommand cmd = new OrderCommand(orderId, List.of(...), 100.0);

        // 2. Act: submeter saga (vai falhar em payment, triggerar compensação)
        orderService.submitOrderSaga(cmd);

        // 3. Assert: validar que estoque foi liberado (compensação)
        assertThat(inventoryService.getReservedCount(orderId))
                .as("Reserved inventory should be released after payment failure")
                .isZero();

        // 4. Assert: validar que order está em FAILED state
        Order savedOrder = orderRepository.findById(orderId);
        assertThat(savedOrder.getStatus())
                .isEqualTo(OrderStatus.FAILED);
    }

    @Test
    public void testSagaIdempotency() {
        // 1. Submit saga com mesmo order ID
        orderService.submitOrderSaga(cmd);

        // 2. Submit again (deve ser idempotent)
        orderService.submitOrderSaga(cmd);

        // 3. Verificar que só 1 saga rodou
        List<ExecutionHistory> executions = stepFunctionsClient.getExecutionHistory(...);
        assertThat(executions)
                .hasSize(1)
                .allMatch(ex -> ex.getName().equals("order-12345"));
    }
}
```

#### Checklist: Saga Pattern

- ✅ Usar Step Functions (orquestrada) para flows com < 5 steps — **P1 Simplicidade**
- ✅ Usar eventos SQS/SNS (coreografada) para sistemas com > 10 microserviços
- ✅ Cada step tem compensação explícita (rollback)
- ✅ Correlation ID propagado end-to-end (GLOSSARIO §3)
- ✅ Idempotency key em cada invocação (evita duplicatas)
- ✅ Retry com exponential backoff para falhas transitórias
- ✅ Testes: simular falha em cada step, validar compensação
- ✅ Monitoramento: métricas DORA, alertas para saga failures > 5%
- ✅ Runbook documentado: "Saga travada? Como recuperar manualmente?"
