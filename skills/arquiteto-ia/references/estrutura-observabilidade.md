# Referência — Estrutura de Projeto + Observabilidade (layout Python/Java, tracing, métricas OTel GenAI)

> Parte da skill `arquiteto-ia`. Carregue sob demanda. Hub: `../SKILL.md`.
## Estrutura de Projeto para Sistemas de IA

### Python — Estrutura Recomendada
```
projeto_ia/
├── src/
│   ├── domain/                    ← ZERO dependência de IA
│   │   ├── models/                ← entidades de negócio
│   │   └── services/              ← lógica de negócio pura
│   │
│   ├── ai/                        ← núcleo de IA isolado
│   │   ├── ports/
│   │   │   ├── llm_port.py        ← Protocol LLMPort
│   │   │   └── vector_store_port.py
│   │   ├── adapters/
│   │   │   ├── claude_adapter.py
│   │   │   ├── gemini_adapter.py
│   │   │   └── bedrock_adapter.py
│   │   ├── agents/
│   │   │   ├── base_agent.py      ← classe base com guardrails + observabilidade
│   │   │   ├── atendimento_agent.py
│   │   │   └── analise_agent.py
│   │   ├── rag/
│   │   │   ├── rag_service.py
│   │   │   └── chunker.py
│   │   ├── guardrails/
│   │   │   ├── input_guardrail.py
│   │   │   └── output_guardrail.py
│   │   └── prompts/               ← prompts como arquivos .txt ou .jinja2
│   │       ├── atendimento_system.txt
│   │       └── analise_system.txt
│   │
│   ├── application/               ← orquestra domain + ai
│   │   └── use_cases/
│   │       └── responder_cliente.py
│   │
│   └── infrastructure/
│       ├── aws/                   ← Bedrock, Comprehend, Textract
│       └── vector_stores/         ← pgvector, pinecone, opensearch
│
├── tests/
│   ├── unit/ai/                   ← testa lógica de agente com LLM mockado
│   ├── integration/ai/            ← testa com LLM real (marcados como @slow)
│   └── prompts/                   ← testes de prompt regression
│
└── prompts/                       ← prompts versionados como artefatos
    └── v1/
        └── atendimento_system.txt
```

### Java — Estrutura Recomendada
```
src/main/java/com/empresa/produto/
├── domain/                        ← ZERO dependência de IA ou frameworks
│   ├── model/
│   └── service/
│
├── ai/                            ← módulo de IA isolado
│   ├── port/
│   │   ├── LLMPort.java           ← interface
│   │   └── VectorStorePort.java
│   ├── adapter/
│   │   ├── SpringAIClaudeAdapter.java
│   │   └── BedrockAdapter.java
│   ├── agent/
│   │   ├── BaseAgent.java         ← guardrails + observabilidade + limite de iterações
│   │   └── AtendimentoAgent.java
│   ├── rag/
│   │   └── RAGService.java
│   └── guardrail/
│       ├── InputGuardrail.java
│       └── OutputGuardrail.java
│
├── application/
│   └── usecase/
│       └── ResponderClienteUseCase.java
│
└── config/
    └── AIConfig.java              ← wiring de agentes, adapters, guardrails
```

---

## Observabilidade de Sistemas de IA

### Rastreamento Estruturado de Agentes

```python
import structlog
from dataclasses import dataclass, field
from datetime import datetime
import uuid

logger = structlog.get_logger()

@dataclass
class AITrace:
    """Registro completo de uma execução de agente — auditável e depurável."""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agente: str = ""
    modelo: str = ""
    tarefa: str = ""
    iteracoes: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    ferramentas_usadas: list[str] = field(default_factory=list)
    guardrails_acionados: list[str] = field(default_factory=list)
    latencia_ms: float = 0.0
    sucesso: bool = False
    erro: str = ""
    iniciado_em: datetime = field(default_factory=datetime.utcnow)


def rastrear_agente(func):
    """Decorator que injeta observabilidade em qualquer agente."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        trace = AITrace(agente=self.__class__.__name__)
        inicio = datetime.utcnow()
        try:
            resultado = func(self, *args, **kwargs)
            trace.sucesso = True
            return resultado
        except Exception as e:
            trace.erro = str(e)
            trace.sucesso = False
            raise
        finally:
            trace.latencia_ms = (datetime.utcnow() - inicio).total_seconds() * 1000
            logger.info(
                "ai_agent_execution",
                trace_id=trace.trace_id,
                agente=trace.agente,
                modelo=trace.modelo,
                tokens_total=trace.tokens_input + trace.tokens_output,
                latencia_ms=trace.latencia_ms,
                ferramentas=trace.ferramentas_usadas,
                guardrails=trace.guardrails_acionados,
                sucesso=trace.sucesso,
                erro=trace.erro or None,
            )
    return wrapper
```

### Métricas GenAI Canônicas (OpenTelemetry Semantic Conventions v1.28+)

Emitir **todas** as chamadas de LLM com atributos semanticamente padronizados permite dashboards
reaproveitáveis (Grafana, Datadog, CloudWatch Application Signals) sem precisar instrumentar por
vendor. Seguir as [OTel GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/):

| Atributo OTel | Obrigatório | Exemplo |
|---|---|---|
| `gen_ai.system` | sim | `anthropic`, `bedrock`, `openai`, `google.vertex_ai` |
| `gen_ai.request.model` | sim | `claude-sonnet-4-6` |
| `gen_ai.response.model` | sim | (pode diferir em casos de fallback/roteamento) |
| `gen_ai.operation.name` | sim | `chat`, `text_completion`, `embeddings` |
| `gen_ai.usage.input_tokens` | sim | 1450 |
| `gen_ai.usage.output_tokens` | sim | 320 |
| `gen_ai.request.temperature` | não | 0.0 |
| `gen_ai.request.top_p` | não | 0.95 |
| `gen_ai.response.finish_reasons` | sim | `["stop"]`, `["length"]`, `["tool_calls"]` |
| `gen_ai.conversation.id` | não | UUID para agrupar turns |

**Métricas derivadas canônicas** (emitir sempre):
- `gen_ai.client.token.usage` (histogram, por `input`/`output`)
- `gen_ai.client.operation.duration` (histogram, em segundos)
- `gen_ai.server.request.duration` (para self-hosted)

Em Spring AI 2.0, o `ObservationRegistry` já instrumenta `ChatClient` com esses atributos
automaticamente — basta registrar `io.micrometer.tracing` + `micrometer-registry-otlp` e
exportar para o collector OTel. Para Bedrock, o `BedrockRuntimeClient` (SDK v2.32+) emite
estes campos quando o `TracingInterceptor` está ativo.

**Langfuse / LangSmith** são ótimos para experimentação, mas em produção a disciplina OTel
garante portabilidade: os mesmos traces rodam em Grafana Tempo, Jaeger, AWS X-Ray e
CloudWatch Application Signals sem reescrita.

---

