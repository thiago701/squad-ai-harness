# Referência — Resiliência (Resilience4j para serviços AWS)

> Parte da skill `arquiteto-cloud-aws`. Carregue este arquivo sob demanda quando a tarefa tocar este eixo. Hub: `../SKILL.md`.
### Resiliência — Resilience4j para Serviços AWS

#### Por que Resiliência é Obrigatória em Cloud Native

Serviços AWS são confiáveis mas NÃO são infalíveis. SQS pode ter latência aumentada, RDS pode reiniciar por manutenção, serviços downstream podem ficar indisponíveis. Sem resiliência explícita, uma falha em cascata derruba o sistema inteiro.

```
Padrões obrigatórios para integrações AWS:
  ✓ Circuit Breaker    → protege contra serviço downstream degradado
  ✓ Retry              → recupera de falhas transientes (throttling, timeout)
  ✓ Bulkhead           → isola recursos (um serviço lento não esgota o pool)
  ✓ Rate Limiter       → protege contra uso excessivo de APIs AWS (evita throttling)
  ✓ Time Limiter       → timeout explícito para toda chamada externa
```

```java
// Java 25 — Spring Boot 4 + Resilience4j (configuração declarativa)
// Dependência: io.github.resilience4j:resilience4j-spring-boot3 (compatível com SB4)

// application.yml — configuração centralizada, zero código de resiliência espalhado
/*
resilience4j:
  circuitbreaker:
    instances:
      pedido-service:
        sliding-window-size: 10
        failure-rate-threshold: 50
        wait-duration-in-open-state: 10s
        permitted-number-of-calls-in-half-open-state: 3
        slow-call-duration-threshold: 2s
        slow-call-rate-threshold: 80
  retry:
    instances:
      sqs-publisher:
        max-attempts: 3
        wait-duration: 500ms
        exponential-backoff-multiplier: 2
        retry-exceptions:
          - software.amazon.awssdk.core.exception.SdkServiceException
        ignore-exceptions:
          - software.amazon.awssdk.services.sqs.model.InvalidMessageContentsException
  bulkhead:
    instances:
      external-api:
        max-concurrent-calls: 25
        max-wait-duration: 500ms
  timelimiter:
    instances:
      default:
        timeout-duration: 3s
*/

// Uso no service — anotações declarativas, sem boilerplate
@Service
@RequiredArgsConstructor
public class PedidoService {

    private final PedidoRepository repository;
    private final PagamentoClient pagamentoClient;

    @CircuitBreaker(name = "pedido-service", fallbackMethod = "confirmarFallback")
    @Retry(name = "sqs-publisher")
    @TimeLimiter(name = "default")
    public CompletableFuture<PedidoConfirmado> confirmar(PedidoId id) {
        // Com Virtual Threads, o CompletableFuture aqui é só para o TimeLimiter
        return CompletableFuture.supplyAsync(() -> {
            var pedido = repository.buscarPorId(id)
                .orElseThrow(() -> new PedidoNaoEncontradoException(id));
            var pagamento = pagamentoClient.processar(pedido);
            pedido.confirmar(pagamento);
            repository.salvar(pedido);
            return PedidoConfirmado.from(pedido);
        });
    }

    private CompletableFuture<PedidoConfirmado> confirmarFallback(PedidoId id, Throwable ex) {
        log.warn("Fallback para pedido {}: {}", id, ex.getMessage());
        return CompletableFuture.completedFuture(
            PedidoConfirmado.pendente(id, "Processamento em fila — tentaremos novamente")
        );
    }
}
```

```
Quando usar cada padrão com AWS:

  Circuit Breaker:
    ✓ Chamadas a APIs externas (pagamento, parceiros)
    ✓ Chamadas a outros microserviços via HTTP
    ✗ SQS/SNS (já tem retry nativo — não precisa de CB)
    ✗ DynamoDB (SDK já tem retry built-in)

  Retry:
    ✓ Publicação em SQS/SNS (throttling temporário)
    ✓ Operações S3 (eventual consistency, throttling)
    ✓ Chamadas a Secrets Manager (rate limiting)
    ✗ Erros de validação (retry não resolve lógica errada)

  Bulkhead:
    ✓ Chamadas a serviços externos (isolar para não esgotar VT carrier threads)
    ✓ Queries pesadas ao RDS (separar do pool principal)

  Rate Limiter:
    ✓ APIs que chamam Bedrock/SageMaker (evitar throttling por cota)
    ✓ Webhooks que disparam em rajadas
```

---

