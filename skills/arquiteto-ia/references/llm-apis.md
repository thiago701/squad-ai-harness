# Referência — APIs de Modelos (Claude/Anthropic e Gemini/Google — adapters, tool use, multimodal)

> Parte da skill `arquiteto-ia`. Carregue sob demanda. Hub: `../SKILL.md`.
## APIs de Modelos — Claude e Gemini

### Anthropic Claude — Boas Práticas

```python
# Porta de abstração — nunca acoplar diretamente ao SDK
from typing import Protocol
from dataclasses import dataclass

@dataclass(frozen=True)
class LLMResponse:
    content: str
    tokens_used: int
    model: str
    stop_reason: str

class LLMPort(Protocol):
    def completar(self, prompt: str, system: str = "", temperatura: float = 0.0) -> LLMResponse: ...
    def completar_stream(self, prompt: str, system: str = "") -> "AsyncIterator[str]": ...


# Adapter Claude — implementa a porta
import anthropic
from typing import AsyncIterator

class ClaudeAdapter:
    """Adapter para Anthropic Claude — implementa LLMPort."""

    MODELO_PADRAO = "claude-sonnet-4-6"  # sempre use o mais recente disponível

    def __init__(self, api_key: str, modelo: str = MODELO_PADRAO):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._modelo = modelo

    def completar(
        self,
        prompt: str,
        system: str = "",
        temperatura: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        message = self._client.messages.create(
            model=self._modelo,
            max_tokens=max_tokens,
            temperature=temperatura,
            system=system or "Você é um assistente preciso e objetivo.",
            messages=[{"role": "user", "content": prompt}],
        )
        return LLMResponse(
            content=message.content[0].text,
            tokens_used=message.usage.input_tokens + message.usage.output_tokens,
            model=message.model,
            stop_reason=message.stop_reason,
        )

    async def completar_stream(
        self, prompt: str, system: str = ""
    ) -> AsyncIterator[str]:
        async with anthropic.AsyncAnthropic() as client:
            async with client.messages.stream(
                model=self._modelo,
                max_tokens=4096,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                async for text in stream.text_stream:
                    yield text


# Tool Use com Claude — function calling estruturado
def criar_agente_com_ferramentas(llm: ClaudeAdapter):
    tools = [
        {
            "name": "buscar_pedido",
            "description": "Busca dados de um pedido pelo ID. Use quando o usuário perguntar sobre status de pedido.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "pedido_id": {"type": "integer", "description": "ID numérico do pedido"}
                },
                "required": ["pedido_id"]
            }
        },
        {
            "name": "calcular_frete",
            "description": "Calcula o frete para um CEP de destino. Sempre use para perguntas sobre entrega.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "cep_destino": {"type": "string", "description": "CEP no formato 00000-000"},
                    "peso_kg": {"type": "number", "description": "Peso total em quilogramas"}
                },
                "required": ["cep_destino", "peso_kg"]
            }
        }
    ]

    response = llm._client.messages.create(
        model=ClaudeAdapter.MODELO_PADRAO,
        max_tokens=4096,
        tools=tools,
        messages=[{"role": "user", "content": "Qual o status do pedido 1234 e quanto custa o frete para 01310-100?"}]
    )

    # Processar tool calls de forma explícita e rastreável
    for block in response.content:
        if block.type == "tool_use":
            resultado = executar_ferramenta(block.name, block.input)
            # continuar conversa com resultado da ferramenta...

# Boas práticas de prompt para Claude
SYSTEM_PROMPT_TEMPLATE = """
Você é {papel}.

RESPONSABILIDADES:
{responsabilidades}

RESTRIÇÕES (NUNCA viole):
- Nunca invente dados que não foram fornecidos explicitamente
- Nunca execute ações sem confirmação quando o impacto for irreversível
- Sempre responda em português brasileiro
- Se não souber, diga "não tenho informação suficiente" — nunca adivinhe

FORMATO DE SAÍDA:
{formato_saida}
"""
```

### Google Gemini — Boas Práticas

```python
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

class GeminiAdapter:
    """Adapter para Google Gemini — implementa LLMPort."""

    MODELO_PADRAO = "gemini-2.5-pro"  # linha atual: Gemini 2.5/3.x — IDs de modelo sao pereciveis; use o mais recente disponivel

    def __init__(self, api_key: str, modelo: str = MODELO_PADRAO):
        genai.configure(api_key=api_key)
        self._modelo_nome = modelo
        self._safety_settings = {
            HarmCategory.HARM_CATEGORY_HATE_SPEECH:       HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_HARASSMENT:        HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
        }

    def completar(
        self,
        prompt: str,
        system: str = "",
        temperatura: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        model = genai.GenerativeModel(
            model_name=self._modelo_nome,
            system_instruction=system or "Você é um assistente preciso e objetivo.",
            safety_settings=self._safety_settings,
        )
        config = genai.types.GenerationConfig(
            temperature=temperatura,
            max_output_tokens=max_tokens,
        )
        response = model.generate_content(prompt, generation_config=config)
        return LLMResponse(
            content=response.text,
            tokens_used=response.usage_metadata.total_token_count,
            model=self._modelo_nome,
            stop_reason=response.candidates[0].finish_reason.name,
        )

    # Gemini Multimodal — texto + imagem + PDF
    def completar_multimodal(self, texto: str, imagem_bytes: bytes, mime_type: str = "image/jpeg") -> LLMResponse:
        model = genai.GenerativeModel(self._modelo_nome)
        parte_imagem = {"mime_type": mime_type, "data": imagem_bytes}
        response = model.generate_content([texto, parte_imagem])
        return LLMResponse(
            content=response.text,
            tokens_used=response.usage_metadata.total_token_count,
            model=self._modelo_nome,
            stop_reason="STOP",
        )

    # Function Calling com Gemini
    def criar_agente_com_ferramentas(self, ferramentas_python: list):
        """Gemini aceita funções Python diretamente — declaração automática de schema."""
        model = genai.GenerativeModel(
            model_name=self._modelo_nome,
            tools=ferramentas_python,  # funções Python com docstring → schema automático
        )
        chat = model.start_chat(enable_automatic_function_calling=True)
        return chat


# Exemplo de ferramenta Python para Gemini (schema inferido automaticamente)
def buscar_pedido(pedido_id: int) -> dict:
    """
    Busca os dados de um pedido pelo ID.

    Args:
        pedido_id: ID numérico único do pedido no sistema

    Returns:
        Dicionário com status, valor e data do pedido
    """
    # implementação real aqui
    return {"id": pedido_id, "status": "CONFIRMADO", "valor": 150.00}


# Factory para selecionar modelo por configuração — troca sem alterar código
class LLMFactory:
    @staticmethod
    def criar(provider: str, **kwargs) -> LLMPort:
        match provider.lower():
            case "claude":  return ClaudeAdapter(**kwargs)
            case "gemini":  return GeminiAdapter(**kwargs)
            case "bedrock": return BedrockAdapter(**kwargs)
            case _: raise ValueError(f"Provider desconhecido: {provider}")
```

---

