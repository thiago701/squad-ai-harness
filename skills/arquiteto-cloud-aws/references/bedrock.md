# Referência — Bedrock (LLM gerenciado)

> Parte da skill `arquiteto-cloud-aws`. Carregue este arquivo sob demanda quando a tarefa tocar este eixo. Hub: `../SKILL.md`.
### Bedrock — LLM Integration (Claude, Llama, Mistral)

**Quando usar Bedrock vs API Anthropic/OpenAI direto:**

```
Bedrock é um serviço AWS que oferece modelos LLM (Claude, Llama, Mistral, etc)
com governança, compliance e integração VPC/IAM nativa.

BEDROCK — Quando escolher:
  ✓ Compliance corporativo (dados não saem de VPC endpoint)
  ✓ Vendor lock-in aceito em troca de governança
  ✓ Integração com Secrets Manager + IAM roles automática
  ✓ Métricas CloudWatch nativas + X-Ray tracing
  ✓ Batch inference (processar 1M documentos via Bedrock Batch)

API ANTHROPIC DIRETO — Quando escolher:
  ✓ Multi-vendor (não quer ficar preso a Bedrock)
  ✓ Custo marginal menor (sem overhead AWS)
  ✓ Latência mais baixa (API direta vs Bedrock proxy)
  ✓ Features mais novas (Bedrock sempre está 1-2 meses atrás)

Suporte Bedrock: Claude 3.5 Sonnet, Claude 3 Opus/Sonnet/Haiku, Llama 2, Mistral
```

**Invoke sincronizado — Java com AWS SDK v2:**

```java
// Java 25 — BedrockRuntimeClient invoke sincronizado
// Dependência: software.amazon.awssdk:bedrockruntime

@Service
@RequiredArgsConstructor
public class BedrockInvokeService {

    private final BedrockRuntimeClient bedrockClient;
    private final CorrelationIdContext correlationContext;

    public String invokeClaudeSonnet(String prompt, int maxTokens) {
        // Prepare request
        var request = InvokeModelRequest.builder()
            .modelId("anthropic.claude-sonnet-4-5-20250929-v1:0")
            .contentType("application/json")
            .accept("application/json")
            .body(SdkBytes.fromUtf8String(
                // Claude API expects native message format
                jsonBuilder()
                    .put("messages", jsonArray(
                        jsonObject()
                            .put("role", "user")
                            .put("content", prompt)
                    ))
                    .put("max_tokens", maxTokens)
                    .put("temperature", 0.7)
                    .build()
                    .toString()
            ))
            .build();

        // Invoke (sync) — espera resposta completa
        var response = bedrockClient.invokeModel(request);
        
        // Parse response
        String responseBody = response.body().asUtf8String();
        return parseClaudeResponse(responseBody);
    }

    private String parseClaudeResponse(String json) {
        // Claude response format:
        // {"content": [{"type": "text", "text": "..."}], "usage": {...}}
        JsonObject obj = JsonParser.parseString(json).getAsJsonObject();
        return obj.getAsJsonArray("content")
            .get(0).getAsJsonObject()
            .get("text").getAsString();
    }
}

// Spring Boot configuration
@Configuration
public class BedrockConfig {

    @Bean
    public BedrockRuntimeClient bedrockClient() {
        return BedrockRuntimeClient.builder()
            .region(Region.US_EAST_1)  // Bedrock disponível em regiões limitadas
            .build();
    }
}

// Teste com Micrometer metrics
@Service
public class BedrockMetrics {

    private final MeterRegistry meterRegistry;
    private final Timer.Sample sample;

    public void trackInvocation(String modelId, int inputTokens, int outputTokens) {
        Timer.builder("bedrock.invocation")
            .tag("model", modelId)
            .publishPercentiles(0.5, 0.95, 0.99)
            .record(() -> {
                // latência é medida automaticamente
            });

        meterRegistry.counter("bedrock.tokens.input", "model", modelId)
            .increment(inputTokens);
        meterRegistry.counter("bedrock.tokens.output", "model", modelId)
            .increment(outputTokens);
    }
}
```

**Invoke assincronizado com streaming:**

```java
// Java — InvokeModelWithResponseStream para streaming
@Service
public class BedrockStreamService {

    public void invokeWithStreaming(String prompt, Consumer<String> onChunk) {
        var request = InvokeModelWithResponseStreamRequest.builder()
            .modelId("anthropic.claude-sonnet-4-5-20250929-v1:0")
            .contentType("application/json")
            .accept("application/json")
            .body(SdkBytes.fromUtf8String(
                jsonBuilder()
                    .put("messages", /* ... */)
                    .put("max_tokens", 1000)
                    .build()
                    .toString()
            ))
            .build();

        bedrockClient.invokeModelWithResponseStream(request, response -> {
            response.body().forEach(event -> {
                if (event instanceof ContentBlockDeltaEvent delta) {
                    // Streaming text delta — processa chunk por chunk
                    String chunk = delta.delta().asText().text();
                    onChunk.accept(chunk);
                }
            });
        });
    }
}
```

**Spring AI 2 — Alternativa declarativa (recomendada):**

```java
// Spring AI 2 simplifica Bedrock integration
// Dependência: org.springframework.ai:spring-ai-bedrock

@Configuration
public class BedrockAiConfig {

    @Bean
    public BedrockChatModel bedrockChatModel(BedrockRuntimeClient client) {
        return new BedrockChatModel(client,
            ChatModelParameters.builder()
                .withModel("anthropic.claude-sonnet-4-5-20250929-v1:0")
                .withTemperature(0.7)
                .withMaxTokens(1000)
                .build());
    }
}

@Service
@RequiredArgsConstructor
public class AnalisisService {

    private final BedrockChatModel chatModel;

    public String analisarDocumento(String documento) {
        var prompt = new Prompt(
            new UserMessage("Resumir este documento: " + documento),
            new SystemMessage("Você é um analista de documentos.")
        );
        
        // Spring AI handle tudo: invoke, token counting, streaming
        ChatResponse response = chatModel.call(prompt);
        return response.getResult().getOutput().getContent();
    }
}
```

**Cost Estimation — Tabela de preços por modelo:**

| Modelo | Entrada/1M tokens | Saída/1M tokens | Exemplo: 1M docs × 2K tokens |
|---|---|---|---|
| Claude 3.5 Sonnet | $3.00 | $15.00 | $3.00 input + $15.00 output = **$18/mês** |
| Claude 3 Opus | $15.00 | $75.00 | $15.00 input + $75.00 output = **$90/mês** |
| Llama 2 70B | $0.80 | $2.40 | $0.80 input + $2.40 output = **$3.20/mês** |
| Mistral 7B | $0.15 | $0.45 | $0.15 input + $0.45 output = **$0.60/mês** |

**Exemplo cálculo: 100k invocações/mês, prompt ~500 tokens, resposta ~300 tokens**

```
Entrada:  100k × 500 tokens = 50M tokens = 50M / 1M × $3.00 = $150
Saída:    100k × 300 tokens = 30M tokens = 30M / 1M × $15.00 = $450
Total:    $600/mês para Claude 3.5 Sonnet

vs Mistral 7B:
Entrada:  $0.075
Saída:    $0.135
Total:    $21/mês

Trade-off: qualidade (Sonnet melhor) vs custo (Mistral 32x mais barato)
```

**Bedrock Guardrails — Content Filtering Nativo:**

```java
// Bedrock Guardrails protegem contra conteúdo prejudicial nativo
// Sem código de validação próprio
@Service
public class GuardedBedrockService {

    public String invokeWithGuardrails(String prompt) {
        var request = InvokeModelRequest.builder()
            .modelId("anthropic.claude-sonnet-4-5-20250929-v1:0")
            .guardrailIdentifier("arn:aws:bedrock:us-east-1:123:guardrail/gr-xxx")
            .guardrailVersion("1")
            // guardrail automático rejeita:
            // - hate speech, violence, illegal activity
            // - PII (SSN, credit card)
            // - política/religião customizável
            .body(SdkBytes.fromUtf8String(/* ... */))
            .build();

        try {
            var response = bedrockClient.invokeModel(request);
            return parseResponse(response);
        } catch (AccessDeniedException e) {
            // Guardrail bloqueou — log + fallback
            logger.warn("Bedrock Guardrail bloqueou: {}", e.getMessage());
            return "Não posso responder essa pergunta.";
        }
    }
}

// Guardrails customizados via console AWS
// - Topic filters: "não responda sobre política"
// - Pattern filters: regex para SSN/credit card
// - Word filters: palavras proibidas customizadas
```

**Propagação de Correlation ID em invocações Bedrock:**

```java
// Adicionar Correlation ID aos logs de Bedrock
@Component
public class CorrelationIdBedrockInterceptor {

    public InvokeModelRequest addCorrelationId(InvokeModelRequest request) {
        String correlationId = CorrelationIdContext.currentOrNew();
        
        // Bedrock não tem header customizado nativo, mas podemos adicionar ao prompt
        String bodyWithCorrelation = request.body().asUtf8String()
            .replace("}", 
                ", \"x-correlation-id\": \"" + correlationId + "\"}");
        
        return request.toBuilder()
            .body(SdkBytes.fromUtf8String(bodyWithCorrelation))
            .build();
    }
}

// Nos logs X-Ray / CloudWatch, Correlation ID aparece associado à invocação
```

**Referência cruzada: guardrails aplicacionais** — ver `arquiteto-ia/SKILL.md` para validação de conteúdo LLM (fact-checking, source attribution, etc).

---

## Atualização 2026-10 (fatos conferidos em 12/10/2026 — reconfirme antes de fixar)

| Tema | Fato | Implicação de arquitetura |
|---|---|---|
| **Preços por 1 M tokens (us-east-1, on-demand)** | Nova Micro US$ 0,035 / 0,14 · Nova Lite US$ 0,06 / 0,24 · Claude Haiku 4.5 US$ 1 / 5 (entrada / saída) | roteamento por tarefa: Nova Micro/Lite para classificar/extrair e perguntas simples; Haiku 4.5 para raciocínio com várias tools; temperatura 0 + tool-use forçado em extração |
| **Free tier** | Bedrock não tem; só os créditos gerais do plano Free (contas novas) | o único item sem free tier de uma POC serverless — meça tokens por chamada |
| **Guardrails** | filtros de conteúdo/tópicos negados US$ 0,15 por 1.000 unidades de texto (≤ 1.000 caracteres cada); PII US$ 0,10; *contextual grounding* US$ 0,10; filtros de palavras/regex **grátis** | em POC, defesa de prompt + validação de schema; Guardrails pagos quando houver PII real |
| **S3 Vectors** | GA em 02/12/2025; vector store suportado pelo **Bedrock Knowledge Bases**; preço por uso (PUT/GB, armazenamento, consulta) sem mínimo mensal; +17 regiões em 03/2026 | único RAG semântico compatível com "free tier obrigatório"; OpenSearch Serverless tem mínimo mensal |
| **AgentCore** (GA 10/2025) | Runtime por vCPU-h/GB-h; **Gateway** US$ 0,005 por 1.000 invocações + indexação de tools; Memory por eventos/GB; sem free tier próprio | Gateway transforma Lambda/OpenAPI em tools MCP com pouco custo, mas é mais uma peça gerenciada — evolução, não base |
| **Step Functions ↔ AgentCore** | estado `AgentCore InvokeHarness` (`arn:aws:states:::bedrockagentcore:invokeHarness`), só *request-response*; teto de **15 min** no Task; **o harness continua rodando após o timeout** da task (custo); resposta em formato Converse só com a mensagem final | para agentes longos use o harness com timeout ≤ 15 min; para extração simples prefira `bedrock:invokeModel` direto |
| **Step Functions ↔ Bedrock** | integração otimizada `bedrock:invokeModel` (entrada/saída via S3 opcional); JSONata + Variables (11/2024) reduzem estados `Pass` | LLM como **passo** de uma state machine determinística, nunca como orquestrador |

Fontes: https://aws.amazon.com/bedrock/pricing/ · https://aws.amazon.com/bedrock/agentcore/pricing/ · https://aws.amazon.com/blogs/aws/amazon-s3-vectors-now-generally-available-with-increased-scale-and-performance · https://docs.aws.amazon.com/step-functions/latest/dg/connect-bedrockagentcore.html · preços de modelos: https://cloudprice.net/models/aws/nova-micro e https://anotherwrapper.com/tools/llm-pricing/claude-haiku-45/amazon-nova-lite
