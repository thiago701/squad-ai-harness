# Referência — Guardrails (camadas input/output/runtime, prompt injection, PII, limites de iteração)

> Parte da skill `arquiteto-ia`. Carregue sob demanda. Hub: `../SKILL.md`.
## Guardrails — Segurança e Controle

### Camadas de Guardrail
```
INPUT GUARDRAILS (antes do LLM):
  → Sanitização de prompt injection
  → Validação de schema de entrada
  → Detecção de PII sensível
  → Rate limiting por usuário/sessão
  → Classificação de intenção (bloqueia intenções proibidas)

OUTPUT GUARDRAILS (depois do LLM):
  → Validação de schema da resposta
  → Detecção de alucinação (grounding check)
  → Filtro de conteúdo impróprio
  → Verificação de dados sensíveis na saída (PII leak)
  → Validação de ação antes de executar (se tool use)

RUNTIME GUARDRAILS:
  → Timeout por chamada ao LLM
  → Limite de iterações de agente (loop infinito)
  → Orçamento de tokens por sessão
  → Circuit breaker para API do modelo
```

```python
# Guardrail como decorador — limpo e reutilizável
from functools import wraps
import re
import logging

logger = logging.getLogger(__name__)

class GuardrailViolation(Exception):
    def __init__(self, regra: str, detalhes: str):
        self.regra = regra
        self.detalhes = detalhes
        super().__init__(f"Guardrail '{regra}': {detalhes}")


class InputGuardrail:
    """Valida e sanitiza entrada antes de enviar ao LLM."""

    MAX_TOKENS_INPUT = 8000
    PADROES_INJECAO = [
        r"ignore (all |previous |above )?instructions",
        r"system prompt",
        r"jailbreak",
        r"você é agora",
        r"esqueça tudo",
    ]

    def validar(self, texto: str, contexto: str = "") -> str:
        self._verificar_tamanho(texto)
        self._verificar_injecao(texto)
        texto = self._sanitizar_pii(texto)
        logger.info("input_guardrail_passed", extra={"contexto": contexto, "tamanho": len(texto)})
        return texto

    def _verificar_tamanho(self, texto: str):
        tokens_estimados = len(texto) // 4  # estimativa grosseira: 4 chars ≈ 1 token
        if tokens_estimados > self.MAX_TOKENS_INPUT:
            raise GuardrailViolation("tamanho_input", f"Estimativa de {tokens_estimados} tokens excede limite {self.MAX_TOKENS_INPUT}")

    def _verificar_injecao(self, texto: str):
        texto_lower = texto.lower()
        for padrao in self.PADROES_INJECAO:
            if re.search(padrao, texto_lower):
                raise GuardrailViolation("prompt_injection", f"Padrão suspeito detectado: '{padrao}'")

    def _sanitizar_pii(self, texto: str) -> str:
        # Mascara CPF, cartão de crédito, etc. antes de enviar ao LLM
        texto = re.sub(r'\d{3}\.\d{3}\.\d{3}-\d{2}', '[CPF_REMOVIDO]', texto)
        texto = re.sub(r'\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}', '[CARTAO_REMOVIDO]', texto)
        return texto


class OutputGuardrail:
    """Valida saída do LLM antes de retornar ao usuário ou executar ação."""

    def validar_json(self, resposta: str, schema: dict) -> dict:
        """Valida que saída do LLM é JSON válido e conforme schema."""
        import json
        try:
            dados = json.loads(resposta)
        except json.JSONDecodeError as e:
            raise GuardrailViolation("json_invalido", f"LLM não retornou JSON válido: {e}")

        self._validar_schema(dados, schema)
        return dados

    def verificar_grounding(self, resposta: str, fontes: list[str]) -> bool:
        """
        Verifica se a resposta está ancorada nas fontes (anti-alucinação).
        Implementação simplificada — use NLI model em produção crítica.
        """
        palavras_resposta = set(resposta.lower().split())
        palavras_fontes   = set(" ".join(fontes).lower().split())
        overlap = palavras_resposta & palavras_fontes
        score = len(overlap) / max(len(palavras_resposta), 1)
        return score > 0.3  # threshold ajustável por domínio

    def validar_acao_reversivel(self, acao: str, parametros: dict) -> bool:
        """Ações irreversíveis exigem confirmação explícita — nunca execute automaticamente."""
        ACOES_IRREVERSIVEIS = {"deletar", "cancelar", "transferir", "publicar", "enviar_email"}
        return acao.lower() not in ACOES_IRREVERSIVEIS


# Limite de iterações — previne loop infinito em agentes ReAct
class AgenteLimitado:
    MAX_ITERACOES = 10
    ORCAMENTO_TOKENS = 50_000

    def __init__(self, llm: LLMPort, ferramentas: dict):
        self._llm = llm
        self._ferramentas = ferramentas
        self._tokens_usados = 0

    def executar(self, tarefa: str) -> str:
        historico = []
        for iteracao in range(self.MAX_ITERACOES):
            resposta = self._llm.completar(self._montar_prompt(tarefa, historico))
            self._tokens_usados += resposta.tokens_used

            if self._tokens_usados > self.ORCAMENTO_TOKENS:
                raise GuardrailViolation("orcamento_tokens",
                    f"Orçamento de {self.ORCAMENTO_TOKENS} tokens excedido na iteração {iteracao}")

            if resposta.stop_reason == "end_turn":
                return resposta.content  # tarefa concluída

            # processa tool calls...
            historico.append(resposta)

        raise GuardrailViolation("max_iteracoes",
            f"Agente não concluiu em {self.MAX_ITERACOES} iterações — possível loop")
```

---

