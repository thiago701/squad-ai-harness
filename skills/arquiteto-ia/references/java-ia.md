# Referência — Java 25 — IA Moderna (Spring AI 2, pipeline RAG com Bedrock+PGVector, LangChain4j)

> Parte da skill `arquiteto-ia`. Carregue sob demanda. Hub: `../SKILL.md`.
## Java 25 — IA Moderna

### Spring AI — Integração LLM em Java

```java
// pom.xml — dependências Spring AI
// spring-ai-anthropic-spring-boot-starter
// spring-ai-openai-spring-boot-starter (para embeddings)
// spring-ai-pgvector-store-spring-boot-starter (vector store)

// Porta de abstração Java — independente de provider
public interface LLMPort {
    LLMResponse completar(String prompt, String system, float temperatura);
    Flux<String> completarStream(String prompt, String system);  // reativo com Virtual Threads
}

public record LLMResponse(String content, int tokensUsados, String modelo, String stopReason) {}


// Spring AI — adapter automático com abstração nativa
@Service
public class SpringAIClaudeAdapter implements LLMPort {

    private final ChatClient chatClient;

    public SpringAIClaudeAdapter(ChatClient.Builder builder) {
        this.chatClient = builder
            .defaultOptions(AnthropicChatOptions.builder()
                .withModel(AnthropicApi.ChatModel.CLAUDE_3_5_SONNET)
                .withTemperature(0.0f)
                .withMaxTokens(4096)
                .build())
            .build();
    }

    @Override
    public LLMResponse completar(String prompt, String system, float temperatura) {
        var response = chatClient.prompt()
            .system(system.isBlank() ? "Você é um assistente preciso e objetivo." : system)
            .user(prompt)
            .options(AnthropicChatOptions.builder().withTemperature(temperatura).build())
            .call()
            .chatResponse();

        return new LLMResponse(
            response.getResult().getOutput().getContent(),
            response.getMetadata().getUsage().getTotalTokens().intValue(),
            response.getMetadata().getModel(),
            response.getResult().getMetadata().getFinishReason()
        );
    }

    @Override
    public Flux<String> completarStream(String prompt, String system) {
        return chatClient.prompt()
            .system(system)
            .user(prompt)
            .stream()
            .content();  // Flux<String> — cada token conforme chega
    }
}


// RAG com Spring AI + PGVector
@Service
public class RAGService {

    private final VectorStore vectorStore;
    private final ChatClient chatClient;

    private static final String PROMPT_RAG = """
        Com base exclusivamente nos documentos abaixo, responda à pergunta.
        Se a informação não estiver nos documentos, responda que não encontrou.
        Nunca invente informações.

        DOCUMENTOS:
        {contexto}

        PERGUNTA:
        {pergunta}
        """;

    public String responder(String pergunta) {
        // Busca chunks relevantes por similaridade semântica
        var chunks = vectorStore.similaritySearch(
            SearchRequest.query(pergunta).withTopK(5).withSimilarityThreshold(0.7)
        );

        if (chunks.isEmpty()) {
            return "Não encontrei documentos relevantes para esta pergunta.";
        }

        var contexto = chunks.stream()
            .map(Document::getContent)
            .collect(Collectors.joining("\n\n---\n\n"));

        return chatClient.prompt()
            .user(u -> u.text(PROMPT_RAG).param("contexto", contexto).param("pergunta", pergunta))
            .call()
            .content();
    }

    public void indexar(List<Document> documentos) {
        vectorStore.add(documentos);  // embedding automático via Spring AI
    }
}


// Function Calling em Java com Spring AI — Records Java 25
@Service
public class AgenteComFerramentasService {

    record BuscarPedidoInput(@JsonProperty("pedido_id") int pedidoId) {}
    record BuscarPedidoOutput(int id, String status, BigDecimal valor) {}

    @Bean
    public Function<BuscarPedidoInput, BuscarPedidoOutput> buscarPedido(PedidoRepository repo) {
        return input -> {
            var pedido = repo.findById((long) input.pedidoId())
                .orElseThrow(() -> new PedidoNaoEncontradoException(input.pedidoId()));
            return new BuscarPedidoOutput(pedido.getId().intValue(), pedido.getStatus().name(), pedido.getValor());
        };
    }

    public String executarComFerramentas(String pergunta) {
        return chatClient.prompt()
            .user(pergunta)
            .functions("buscarPedido", "calcularFrete")  // beans registrados
            .call()
            .content();
    }
}
```

### Spring AI 2 + Bedrock + PGVector — Pipeline RAG Completo (Java 25)

```java
// Pipeline RAG (Retrieval-Augmented Generation) completo com Spring AI 2
// Stack: Spring Boot 4 + Spring AI 2 + Amazon Bedrock (Claude) + PGVector

// 1. Dependências (pom.xml — Apache Maven 4, model 4.1.0)
/*
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-bedrock-ai-spring-boot-starter</artifactId>
</dependency>
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-pgvector-store-spring-boot-starter</artifactId>
</dependency>
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-tika-document-reader</artifactId>
</dependency>
*/

// 2. Configuração
/*
spring:
  ai:
    bedrock:
      anthropic:
        chat:
          model: anthropic.claude-sonnet-4-5-20250929-v1:0
          max-tokens: 4096
          temperature: 0.3
    vectorstore:
      pgvector:
        dimensions: 1024
        distance-type: cosine_distance
        index-type: hnsw
*/

// 3. Ingestão de documentos (indexação)
@Service
public class DocumentIngestionService {

    private final VectorStore vectorStore;
    private final TokenTextSplitter textSplitter;

    public DocumentIngestionService(VectorStore vectorStore) {
        this.vectorStore = vectorStore;
        this.textSplitter = new TokenTextSplitter(800, 200, 5, 10000, true);
    }

    // Indexar documento PDF/DOCX/TXT
    public int indexar(Resource documento) {
        var reader = new TikaDocumentReader(documento);
        var documentos = reader.get();
        var chunks = textSplitter.apply(documentos);
        vectorStore.add(chunks);
        return chunks.size();
    }

    // Indexar múltiplos documentos com Virtual Threads (fan-out)
    public Map<String, Integer> indexarBatch(List<Resource> documentos) {
        try (var scope = StructuredTaskScope.open(Joiner.allSuccessfulOrThrow())) {
            var tasks = documentos.stream()
                .map(doc -> scope.fork(() -> Map.entry(doc.getFilename(), indexar(doc))))
                .toList();
            scope.join();
            return tasks.stream()
                .map(Subtask::get)
                .collect(Collectors.toMap(Map.Entry::getKey, Map.Entry::getValue));
        }
    }
}

// 4. RAG Query Service — busca + geração com contexto
@Service
public class RagQueryService {

    private final ChatClient chatClient;
    private final VectorStore vectorStore;

    public RagQueryService(ChatClient.Builder builder, VectorStore vectorStore) {
        this.chatClient = builder
            .defaultSystem("""
                Você é um assistente especializado. Responda APENAS com base
                no contexto fornecido. Se não souber, diga que não encontrou
                informação relevante nos documentos disponíveis.
                """)
            .build();
        this.vectorStore = vectorStore;
    }

    public record RagResponse(String resposta, List<String> fontes) {}

    public RagResponse consultar(String pergunta) {
        // Buscar documentos relevantes (top 5)
        var documentosRelevantes = vectorStore.similaritySearch(
            SearchRequest.builder()
                .query(pergunta)
                .topK(5)
                .similarityThreshold(0.7)
                .build()
        );

        var contexto = documentosRelevantes.stream()
            .map(Document::getText)
            .collect(Collectors.joining("\n\n---\n\n"));

        var fontes = documentosRelevantes.stream()
            .map(d -> d.getMetadata().getOrDefault("source", "desconhecido").toString())
            .distinct()
            .toList();

        var resposta = chatClient.prompt()
            .user(u -> u.text("""
                Contexto dos documentos:
                {contexto}

                Pergunta do usuário:
                {pergunta}
                """)
                .param("contexto", contexto)
                .param("pergunta", pergunta))
            .call()
            .content();

        return new RagResponse(resposta, fontes);
    }
}

// 5. REST Controller com observabilidade
@RestController
@RequestMapping("/api/rag")
public class RagController {

    private final RagQueryService ragService;

    @PostMapping("/query")
    @Observed(name = "rag.query", contextualName = "rag-query")
    public RagQueryService.RagResponse consultar(@RequestBody PerguntaRequest request) {
        return ragService.consultar(request.pergunta());
    }

    @PostMapping("/ingest")
    public Map<String, Integer> ingerir(@RequestParam("files") List<MultipartFile> files) {
        var resources = files.stream()
            .map(MultipartFile::getResource)
            .toList();
        return ingestionService.indexarBatch(resources);
    }
}
```

```
RAG CHECKLIST:
  □ Embedding model dimensionado (1024 para Claude, 1536 para OpenAI)
  □ Chunk size otimizado (800 tokens com 200 overlap — balancear precisão vs contexto)
  □ Similarity threshold > 0.7 (evitar contexto irrelevante)
  □ Top-K = 5 (balancear contexto vs custo de tokens)
  □ System prompt com guardrail: "responda APENAS com base no contexto"
  □ Fontes retornadas junto com a resposta (rastreabilidade)
  □ Métricas: latência da query, tokens consumidos, similarity scores
  □ PGVector com índice HNSW para performance em scale
```

### LangChain4j — Java AI Framework

```java
// LangChain4j — alternativa ao Spring AI, mais explícita no design de agentes
// Dependência: dev.langchain4j:langchain4j-anthropic

// Interface de agente declarativa — LangChain4j gera o orquestrador automaticamente
interface AgenteAtendimento {
    @SystemMessage("""
        Você é um assistente de atendimento ao cliente da empresa.
        Responda sempre em português, seja objetivo e prestativo.
        Nunca invente informações — use apenas as ferramentas disponíveis.
        """)
    String responder(@UserMessage String pergunta);
}

// Ferramentas do agente — métodos anotados com @Tool
public class FerramentasPedido {

    @Tool("Busca o status atual de um pedido pelo ID. Use quando o cliente perguntar sobre seu pedido.")
    public String buscarStatusPedido(
        @P("ID numérico do pedido") int pedidoId
    ) {
        // implementação real — chamada ao domínio, não ao banco diretamente
        return pedidoService.buscarStatus(pedidoId).toString();
    }

    @Tool("Cancela um pedido. ATENÇÃO: operação irreversível — confirme com o usuário antes de usar.")
    public String cancelarPedido(
        @P("ID do pedido a cancelar") int pedidoId,
        @P("Motivo do cancelamento informado pelo cliente") String motivo
    ) {
        pedidoService.cancelar(pedidoId, motivo);
        return "Pedido " + pedidoId + " cancelado com sucesso.";
    }
}

// Montagem do agente — wiring explícito
@Configuration
public class AgenteConfig {

    @Bean
    public AgenteAtendimento agenteAtendimento(FerramentasPedido ferramentas) {
        return AiServices.builder(AgenteAtendimento.class)
            .chatLanguageModel(
                AnthropicChatModel.builder()
                    .apiKey(System.getenv("ANTHROPIC_API_KEY"))
                    .modelName(AnthropicModelName.CLAUDE_3_5_SONNET_20241022)
                    .temperature(0.0)
                    .maxTokens(4096)
                    .build()
            )
            .tools(ferramentas)
            .chatMemory(MessageWindowChatMemory.withMaxMessages(20))  // memória de conversa
            .build();
    }
}
```

---

