# Referência — AWS — Serviços de IA e ML (Bedrock, Agents/AgentCore, MCP, Advisors, RAG avançado, Comprehend/Textract/Rekognition/SageMaker)

> Parte da skill `arquiteto-ia`. Carregue sob demanda. Hub: `../SKILL.md`.
## AWS — Serviços de IA e ML

### Amazon Bedrock — LLMs Gerenciados

```python
import boto3
import json

class BedrockAdapter:
    """Adapter AWS Bedrock — implementa LLMPort. Suporta Claude, Llama, Titan e outros."""

    MODELOS = {
        "claude-sonnet":  "anthropic.claude-sonnet-4-5-20250929-v1:0",
        "claude-haiku":   "anthropic.claude-haiku-4-5-20251001-v1:0",
        "llama-70b":      "meta.llama3-70b-instruct-v1:0",
        "titan-premier":  "amazon.titan-text-premier-v1:0",
    }

    def __init__(self, regiao: str = "us-east-1", modelo: str = "claude-sonnet"):
        self._client = boto3.client("bedrock-runtime", region_name=regiao)
        self._modelo_id = self.MODELOS[modelo]

    def completar(self, prompt: str, system: str = "", temperatura: float = 0.0, max_tokens: int = 4096) -> LLMResponse:
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperatura,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        })
        response = self._client.invoke_model(modelId=self._modelo_id, body=body)
        result = json.loads(response["body"].read())
        return LLMResponse(
            content=result["content"][0]["text"],
            tokens_used=result["usage"]["input_tokens"] + result["usage"]["output_tokens"],
            model=self._modelo_id,
            stop_reason=result["stop_reason"],
        )

    # Bedrock Agents — agentes gerenciados com knowledge bases
    def criar_sessao_agente(self, agent_id: str, alias_id: str) -> str:
        client = boto3.client("bedrock-agent-runtime")
        response = client.create_agent_action_group(
            agentId=agent_id,
            agentAliasId=alias_id,
        )
        return response["sessionId"]


# Amazon Bedrock Knowledge Base — RAG gerenciado
class BedrockKnowledgeBase:
    def __init__(self, knowledge_base_id: str, regiao: str = "us-east-1"):
        self._client = boto3.client("bedrock-agent-runtime", region_name=regiao)
        self._kb_id = knowledge_base_id

    def recuperar_e_gerar(self, consulta: str, modelo_id: str) -> str:
        response = self._client.retrieve_and_generate(
            input={"text": consulta},
            retrieveAndGenerateConfiguration={
                "type": "KNOWLEDGE_BASE",
                "knowledgeBaseConfiguration": {
                    "knowledgeBaseId": self._kb_id,
                    "modelArn": f"arn:aws:bedrock:us-east-1::foundation-model/{modelo_id}",
                    "retrievalConfiguration": {
                        "vectorSearchConfiguration": {"numberOfResults": 5}
                    },
                },
            },
        )
        return response["output"]["text"]
```

### Bedrock Agents & AgentCore — Orquestração Gerenciada

**Bedrock Agents** (GA desde 2024) e **Bedrock AgentCore** (2025) permitem orquestrar agentes
sem escrever loop ReAct nem gerenciar memória — a AWS cuida de:

- **Action Groups** com OpenAPI 3 + Lambda como tool executor
- **Knowledge Bases** nativas (RAG gerenciado com reranking)
- **Memory** de curto e longo prazo persistente em sessão
- **Guardrails** declarativos (tópicos negados, filtros de conteúdo, PII redaction)
- **Tracing** automático em CloudWatch Application Signals

```yaml
# CDK Java — Bedrock Agent com action group e knowledge base
BedrockAgent.Builder.create(this, "PedidoAgent")
    .agentName("pedido-concierge")
    .foundationModel("anthropic.claude-sonnet-4-5-20250929-v1:0")
    .instruction("""
        Você ajuda clientes a consultar, cancelar e rastrear pedidos.
        NUNCA exponha dados de outros clientes. SEMPRE confirme antes de cancelar.
        """)
    .actionGroups(List.of(
        ActionGroup.builder()
            .name("pedidos")
            .lambdaFunction(pedidoLambda)
            .apiSchema(ApiSchema.fromAsset("openapi/pedidos.yaml"))
            .build()))
    .knowledgeBases(List.of(fazerKnowledgeBase))
    .guardrails(guardrails)     // PII + topics deny + content filter
    .build();
```

**Quando usar Bedrock Agents** vs orquestração manual:
- ✓ Agent com ≤ 10 tools, domínio estável, requer guardrails + memória persistente
- ✗ Multi-agent com coordenação complexa → use **AgentCore** ou orquestração custom (LangGraph/Spring AI)

### Model Context Protocol (MCP) — Tools universais entre agentes e IDEs

**MCP** é o padrão aberto (Anthropic 2024) que permite qualquer agente (Claude Desktop, Cursor,
Cowork, Spring AI 2) consumir o mesmo conjunto de tools via servers padronizados.

**Arquitetura:**
- **MCP Server** expõe tools (filesystem, GitHub, Slack, banco de dados interno) via stdio/HTTP+SSE
- **MCP Client** (agente) descobre tools dinamicamente via `tools/list` e as invoca via `tools/call`
- **Schemas JSON** estritos garantem validação bilateral

```java
// Spring AI 2 — expor tool Java como MCP server
@Component
public class EstoqueMcpServer {
    @McpTool(name = "consultar_estoque", description = "Consulta estoque de um SKU")
    public EstoqueDto consultar(
        @McpParam(description = "Código SKU") String sku) {
        return estoqueService.buscar(sku);
    }
}

// Spring Boot ativa MCP server em /mcp via HTTP+SSE
// spring.ai.mcp.server.enabled=true
```

```java
// Spring AI 2 — consumir MCP server externo
@Bean
McpSyncClient githubMcp() {
    return McpClient.sync(new HttpClientTransport("http://mcp-gateway/github"))
        .clientInfo(new Implementation("my-agent", "1.0"))
        .build();
}

// ChatClient descobre e usa tools automaticamente
chatClient.prompt("crie uma issue no repo acme/backend com título 'bug de login'")
    .tools(githubMcp)
    .call();
```

**Vantagem estratégica:** tools são escritas uma vez e funcionam em Claude Desktop, Cursor,
Cowork Mode, agentes Spring AI e qualquer futuro consumidor — zero lock-in.

### Advisors — Pipeline declarativo de pré/pós-processamento (Spring AI 2)

Advisors são o padrão canônico do Spring AI 2 para injetar comportamento transversal (guardrails,
memória, RAG, observabilidade) em qualquer chamada de LLM **sem espalhar lógica** entre use cases.

```java
// Advisor customizado — rejeita entrada em domínio proibido
public class DomainBlocklistAdvisor implements CallAroundAdvisor {
    private final Set<String> blockedTopics;
    public AdvisedResponse aroundCall(AdvisedRequest req, CallAroundAdvisorChain chain) {
        var user = req.userText().toLowerCase();
        if (blockedTopics.stream().anyMatch(user::contains)) {
            return AdvisedResponse.builder()
                .response(ChatResponse.from("Não posso discutir esse tópico."))
                .build();
        }
        return chain.nextAroundCall(req);
    }
    public String getName() { return "domain-blocklist"; }
    public int getOrder() { return 1; } // antes do LLM
}

// Pipeline completo — composto como middleware
chatClient.prompt(pergunta)
    .advisors(
        new DomainBlocklistAdvisor(Set.of("concorrente", "senha", "cartão")),
        new QuestionAnswerAdvisor(vectorStore),                    // RAG
        new MessageChatMemoryAdvisor(memory),                      // histórico
        new SafeGuardAdvisor(List.of("CPF", "RG"), "***REDACTED***"), // PII out
        new LoggingAdvisor())                                      // observabilidade
    .call().content();
```

**Ordem sugerida** (getOrder): input guardrails (1) → RAG (10) → memória (20) → LLM call → output
guardrails (100) → logging (1000).

### RAG Avançado — Hybrid Search + Reranking + HyDE

Para melhorar recall/precision além do básico cosine similarity:

- **Hybrid Search**: combina BM25 (lexical) + vetorial (semântico) com fusão RRF (Reciprocal Rank Fusion).
  Captura tanto palavras-chave exatas quanto paráfrases. Indispensável para documentos técnicos/legais.
- **Reranking**: passa top-N (ex: 50) por modelo cross-encoder (Cohere Rerank, Voyage) que pontua
  par-a-par — top-K final (ex: 5) tem precisão muito maior que cosine puro.
- **HyDE** (Hypothetical Document Embeddings): LLM gera um documento hipotético que responderia a
  pergunta, e o embedding desse documento é usado na busca. Útil para perguntas abstratas.

```java
// Pipeline: HyDE → Hybrid Search → Rerank → LLM
var hypothetical = chatClient.prompt("Gere um parágrafo que responderia: " + pergunta)
    .call().content();
var hybrid = hybridSearcher.search(hypothetical, /*topN*/ 50);
var ranked = reranker.rerank(pergunta, hybrid, /*topK*/ 5);
return chatClient.prompt()
    .user(pergunta)
    .advisors(new QuestionAnswerAdvisor(new StaticVectorStore(ranked)))
    .call().content();
```

### Guardrails — Matriz Canônica

| Camada | Tipo | Ferramenta | Quando bloqueia |
|--------|------|-----------|-----------------|
| **Input** | Prompt Injection | Regex + classificador (Lakera, LLM Guard) | Antes do modelo |
| **Input** | Topic Off-limits | Classificador + allowlist | Antes do modelo |
| **Input** | PII sensível | Comprehend PII + regex | Antes do modelo (redige ou bloqueia) |
| **Context** | RAG permission | ACL no retriever (filter by userId) | Durante retrieve |
| **Tool** | Ação destrutiva | Human-in-the-loop approval | Antes de executar |
| **Tool** | Schema drift | JSON schema validator | Na chamada da tool |
| **Output** | PII leak | Comprehend PII + regex + masker | Após o modelo |
| **Output** | Alucinação | Citation check (RAG exige fonte) | Após o modelo |
| **Output** | Jailbreak evasion | Refusal classifier | Após o modelo |

Ver [[Skill - Engenheiro Seguranca]] para OWASP LLM Top 10 completo e exemplos Java 25 de
guardrail com Structured Concurrency.

### Outros Serviços AWS de IA

```python
# Amazon Comprehend — NLP gerenciado
class ComprehendService:
    """Análise de sentimento, entidades, idioma e PII sem LLM."""

    def __init__(self, regiao: str = "us-east-1"):
        self._client = boto3.client("comprehend", region_name=regiao)

    def analisar_sentimento(self, texto: str, idioma: str = "pt") -> dict:
        response = self._client.detect_sentiment(Text=texto, LanguageCode=idioma)
        return {
            "sentimento": response["Sentiment"],          # POSITIVE, NEGATIVE, NEUTRAL, MIXED
            "scores": response["SentimentScore"],
        }

    def detectar_pii(self, texto: str, idioma: str = "pt") -> list[dict]:
        """Detecta dados pessoais antes de enviar ao LLM — guardrail de privacidade."""
        response = self._client.detect_pii_entities(Text=texto, LanguageCode=idioma)
        return [{"tipo": e["Type"], "score": e["Score"]} for e in response["Entities"]]

    def extrair_entidades(self, texto: str, idioma: str = "pt") -> list[dict]:
        response = self._client.detect_entities(Text=texto, LanguageCode=idioma)
        return [{"texto": e["Text"], "tipo": e["Type"], "score": e["Score"]}
                for e in response["Entities"]]


# Amazon Textract — extração de documentos
class TextractService:
    def __init__(self, regiao: str = "us-east-1"):
        self._client = boto3.client("textract", region_name=regiao)

    def extrair_texto(self, imagem_bytes: bytes) -> str:
        response = self._client.detect_document_text(
            Document={"Bytes": imagem_bytes}
        )
        return " ".join(
            b["Text"] for b in response["Blocks"] if b["BlockType"] == "LINE"
        )

    def extrair_formulario(self, imagem_bytes: bytes) -> dict:
        """Extrai pares chave-valor de formulários — ideal para notas fiscais."""
        response = self._client.analyze_document(
            Document={"Bytes": imagem_bytes},
            FeatureTypes=["FORMS", "TABLES"],
        )
        return self._processar_form_blocks(response["Blocks"])


# Amazon Rekognition — visão computacional
class RekognitionService:
    def __init__(self, regiao: str = "us-east-1"):
        self._client = boto3.client("rekognition", region_name=regiao)

    def detectar_objetos(self, imagem_bytes: bytes, confianca_minima: float = 80.0) -> list[str]:
        response = self._client.detect_labels(
            Image={"Bytes": imagem_bytes},
            MinConfidence=confianca_minima,
        )
        return [label["Name"] for label in response["Labels"]]

    def moderar_conteudo(self, imagem_bytes: bytes) -> bool:
        """Retorna True se imagem é segura — guardrail de conteúdo."""
        response = self._client.detect_moderation_labels(Image={"Bytes": imagem_bytes})
        return len(response["ModerationLabels"]) == 0


# Amazon SageMaker — deploy de modelos customizados
class SageMakerEndpoint:
    def __init__(self, endpoint_name: str, regiao: str = "us-east-1"):
        self._runtime = boto3.client("sagemaker-runtime", region_name=regiao)
        self._endpoint = endpoint_name

    def inferir(self, payload: dict, content_type: str = "application/json") -> dict:
        response = self._runtime.invoke_endpoint(
            EndpointName=self._endpoint,
            ContentType=content_type,
            Body=json.dumps(payload),
        )
        return json.loads(response["Body"].read())
```

---


## Lambda como Compute de Inferência IA {#lambda-ia}

Lambda é a escolha ideal para inferência event-driven (S3/SQS/EventBridge → Bedrock → resultado)
e para expor LLMs com streaming sem manter container idle. Custo zero sem tráfego.

### Padrão 1 — Lambda Response Streaming (TTFB mínimo para chat)

Lambda Response Streaming envia chunks ao cliente antes da função terminar — essencial para
chat generativo onde o usuário espera a primeira palavra em < 500ms.

```python
# Python — Lambda com Bedrock streaming via awslambdaric
import json, boto3
from awslambdaric.bootstrap import LambdaContext

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

def handler(event, context: LambdaContext):
    """Handler com streaming — InvokeMode: RESPONSE_STREAM."""
    body = json.loads(event.get("body", "{}"))
    prompt = body.get("prompt", "")

    response = bedrock.invoke_model_with_response_stream(
        modelId="anthropic.claude-sonnet-4-5-20250929-v1:0",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}]
        }),
        contentType="application/json",
        accept="application/json"
    )

    # Yield chunks diretamente via streaming response
    for event_chunk in response["body"]:
        chunk = json.loads(event_chunk["chunk"]["bytes"])
        if chunk.get("type") == "content_block_delta":
            text = chunk["delta"].get("text", "")
            if text:
                yield text.encode("utf-8")
```

```yaml
# SAM — habilitar streaming
Resources:
  ChatFunction:
    Type: AWS::Serverless::Function
    Properties:
      Runtime: python3.13
      Handler: handler.handler
      MemorySize: 512
      Timeout: 60          # streaming pode durar 30–60s
      FunctionUrlConfig:
        AuthType: AWS_IAM
        InvokeMode: RESPONSE_STREAM   # ← habilita streaming
      Policies:
        - Statement:
            - Effect: Allow
              Action: bedrock:InvokeModelWithResponseStream
              Resource: "*"
```

### Padrão 2 — Pipeline Event-Driven (S3 → Lambda → Bedrock → DynamoDB)

Processamento assíncrono de documentos/imagens com Bedrock. Custo zero idle, escala
de 0 a milhares de invocações sem configuração.

```python
# Python — classificação de documentos S3 com Claude Vision
import boto3, json, base64

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime")
dynamodb = boto3.resource("dynamodb").Table("DocumentAnalysis")

def handler(event, context):
    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key    = record["s3"]["object"]["key"]

        # Ler documento do S3
        obj = s3.get_object(Bucket=bucket, Key=key)
        content = obj["Body"].read()
        b64_content = base64.b64encode(content).decode()

        # Invocar Claude Vision para análise
        response = bedrock.invoke_model(
            modelId="anthropic.claude-sonnet-4-5-20250929-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 500,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": b64_content
                        }},
                        {"type": "text", "text": "Classifique este documento. Retorne JSON: {tipo, confianca, resumo}"}
                    ]
                }]
            }),
            contentType="application/json",
            accept="application/json"
        )
        result = json.loads(response["body"].read())
        analysis = json.loads(result["content"][0]["text"])

        # Salvar resultado
        dynamodb.put_item(Item={
            "documentKey": key,
            "tipo": analysis["tipo"],
            "confianca": str(analysis["confianca"]),
            "resumo": analysis["resumo"]
        })
```

```yaml
# SAM — trigger S3 automático
DocumentAnalyzer:
  Type: AWS::Serverless::Function
  Properties:
    Runtime: python3.13
    MemorySize: 256
    Timeout: 30
    Events:
      S3Upload:
        Type: S3
        Properties:
          Bucket: !Ref DocumentsBucket
          Events: s3:ObjectCreated:*
          Filter:
            S3Key:
              Rules:
                - Name: suffix
                  Value: .jpg
    Policies:
      - S3ReadPolicy:      {BucketName: !Ref DocumentsBucket}
      - DynamoDBWritePolicy: {TableName: !Ref DocumentAnalysis}
      - Statement:
          - Effect: Allow
            Action: bedrock:InvokeModel
            Resource: "*"
```

### Padrão 3 — Lambda Container Image para ML (PyTorch/ONNX)

Para modelos com dependências pesadas (PyTorch, Transformers, ONNX), use Lambda Container Image
(até 10GB). Startup é mais lento, mas SnapStart resolve para Java. Para Python, use layers ou container.

```dockerfile
# Dockerfile para Lambda com modelo ONNX
FROM public.ecr.aws/lambda/python:3.13

# Instalar deps ML (PyTorch CPU ou ONNX runtime)
RUN pip install onnxruntime numpy pillow --no-cache-dir

# Copiar modelo ONNX (alternativa: carregar do S3 no cold start)
COPY model.onnx ${LAMBDA_TASK_ROOT}/
COPY handler.py ${LAMBDA_TASK_ROOT}/

CMD ["handler.handler"]
```

```python
# handler.py — inferência ONNX no Lambda
import onnxruntime as ort
import numpy as np
import json, os

# Carregar modelo fora do handler (re-uso entre invocações warm)
_model = ort.InferenceSession(
    os.path.join(os.environ["LAMBDA_TASK_ROOT"], "model.onnx"),
    providers=["CPUExecutionProvider"]
)

def handler(event, context):
    body = json.loads(event.get("body", "{}"))
    input_data = np.array(body["features"], dtype=np.float32).reshape(1, -1)
    
    result = _model.run(None, {"input": input_data})
    prediction = result[0][0].tolist()
    
    return {
        "statusCode": 200,
        "body": json.dumps({"prediction": prediction})
    }
```

### Quando usar Lambda vs SageMaker Endpoints para IA

| Critério | Lambda | SageMaker Endpoint |
|---|---|---|
| Tráfego | Irregular, picos, zero idle | Constante, > 100 RPS |
| Modelo | Leve (< 2GB), ONNX, Bedrock API | Pesado (PyTorch multi-GPU) |
| Latência | 100–500ms (SnapStart) | < 50ms (GPU dedicada) |
| Custo tráfego baixo | ~$0/mês idle | ~$100/mês mínimo por endpoint |
| Custo tráfego alto | Cresce linear — pode ser > SM | Fixo (over-provisioned) |
| Modelo de billing | Por invocação (ms + GB) | Por hora de instância |
| **Recomendação** | **Start aqui — scale até 10M req/mês** | **Quando Lambda fica mais caro** |

