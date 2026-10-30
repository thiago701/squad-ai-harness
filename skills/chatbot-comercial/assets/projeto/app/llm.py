"""Fronteira com o LLM — restrição 1: consumir `llm-gateway`, não reimplementar.

Aqui NÃO existe roteamento por custo, cache, retry próprio nem contador de
teto por tenant. Roteamento e cache são responsabilidade do `llm-gateway`.
Timeout, retry e circuit breaker vêm de `conversation_core.ResilientCaller`,
que já está entregue e testado. Este módulo só traduz.

Dois modos, ambos reais — nenhum mock:

  `LlmGateway`        produção; delega ao pacote `llm_gateway`.
  `RespostaExtrativa` sem gateway configurado; responde com o trecho
                      recuperado e a fonte. Determinístico, custo zero,
                      nunca inventa. É modo degradado, não simulação.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Protocol

from conversation_core.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    LlmUnavailableError,
    ResilientCaller,
)

from .conhecimento import frases_relevantes

MODELO_EXTRATIVO = "extrativo"


@dataclass(frozen=True, slots=True)
class RespostaLlm:
    texto: str
    modelo: str
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_brl: float = 0.0
    latencia_ms: float = 0.0


class LlmPort(Protocol):
    def responder(
        self,
        *,
        sistema: str,
        pergunta: str,
        trechos: list[Any],
        tenant: str,
        tarefa: str,
    ) -> RespostaLlm:
        ...


class GatewayIndisponivel(RuntimeError):
    pass


def _bloco_de_contexto(trechos: list[Any]) -> str:
    linhas = []
    for i, p in enumerate(trechos, start=1):
        linhas.append(f"[{i}] (fonte: {p.source}) {p.text}")
    return "\n\n".join(linhas)


class RespostaExtrativa:
    """Responde com as frases do trecho que respondem à pergunta. Sempre citando.

    Não inventa nada: recorta. É o modo degradado — real, determinístico, custo
    zero — usado quando não há `llm-gateway` configurado ou quando o teto de
    custo estourou.
    """

    def __init__(self, *, expandir: Any = None, maximo_frases: int = 3):
        self._expandir = expandir
        self._maximo = maximo_frases

    def responder(
        self,
        *,
        sistema: str,
        pergunta: str,
        trechos: list[Any],
        tenant: str = "",
        tarefa: str = "",
    ) -> RespostaLlm:
        del sistema, tenant, tarefa
        inicio = time.perf_counter()
        if not trechos:
            texto = "Não encontrei essa informação na base."
        else:
            # A melhor frase pode estar no 2º ou 3º trecho — o ranking do
            # retrieval é por chunk, e a resposta mora numa frase.
            recorte, fonte, melhor_nota = "", trechos[0].source, -1.0
            for passagem in trechos:
                candidato, nota = frases_relevantes(
                    pergunta, passagem.text, maximo=self._maximo, expandir=self._expandir
                )
                if nota > melhor_nota:
                    recorte, fonte, melhor_nota = candidato, passagem.source, nota
            texto = f"{recorte}\n\n(fonte: {fonte})"
        return RespostaLlm(
            texto=texto,
            modelo=MODELO_EXTRATIVO,
            latencia_ms=(time.perf_counter() - inicio) * 1000,
        )


class LlmGateway:
    """Adapter para o pacote `llm-gateway` da Neural7.

    Contrato esperado (ver `references/arquitetura-referencia.md`):

        from llm_gateway import Gateway
        gw = Gateway.from_env()
        r = gw.complete(prompt=..., system=..., tenant=..., task=..., max_tokens=...)
        r.text / r.model / r.input_tokens / r.output_tokens / r.cost_brl

    `tests/test_llm.py::test_contrato_do_llm_gateway_real` (marker `gateway`)
    falha alto se o pacote instalado não satisfizer esse contrato. Nada aqui
    adivinha comportamento.
    """

    def __init__(self, gateway: Any | None = None, *, modelo_padrao: str = "rapido"):
        self._gateway = gateway if gateway is not None else self._carregar()
        self._modelo_padrao = modelo_padrao

    @staticmethod
    def _carregar() -> Any:
        try:
            from llm_gateway import Gateway  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - depende do ambiente
            raise GatewayIndisponivel(
                "pacote `llm-gateway` não instalado. "
                "Instale-o ou rode em modo extrativo (LLM_GATEWAY_ATIVO=0)."
            ) from exc
        return Gateway.from_env()

    def responder(
        self,
        *,
        sistema: str,
        pergunta: str,
        trechos: list[Any],
        tenant: str,
        tarefa: str,
    ) -> RespostaLlm:
        inicio = time.perf_counter()
        contexto = _bloco_de_contexto(trechos)
        prompt = (
            f"Trechos da base de conhecimento:\n{contexto}\n\n"
            f"Pergunta do cliente: {pergunta}\n\n"
            "Responda apenas com o que está nos trechos e cite a fonte."
        )
        try:
            bruta = self._gateway.complete(
                prompt=prompt,
                system=sistema,
                tenant=tenant,
                task=tarefa or self._modelo_padrao,
            )
        except Exception as exc:  # provider/gateway → retryável pelo caller
            raise LlmUnavailableError(str(exc)) from exc
        return RespostaLlm(
            texto=getattr(bruta, "text", str(bruta)),
            modelo=getattr(bruta, "model", "desconhecido"),
            tokens_entrada=int(getattr(bruta, "input_tokens", 0) or 0),
            tokens_saida=int(getattr(bruta, "output_tokens", 0) or 0),
            custo_brl=float(getattr(bruta, "cost_brl", 0.0) or 0.0),
            latencia_ms=(time.perf_counter() - inicio) * 1000,
        )


class LlmResiliente:
    """Timeout/retry/breaker de `conversation_core` + fallback extrativo.

    Não reimplementa resiliência: delega a `ResilientCaller`, já testado no
    n7-ai-core.
    """

    def __init__(
        self,
        primario: LlmPort,
        *,
        fallback: LlmPort | None = None,
        timeout_s: float = 8.0,
        tentativas: int = 2,
        breaker: CircuitBreaker | None = None,
    ):
        self._primario = primario
        self._fallback = fallback or RespostaExtrativa()
        self._breaker = breaker or CircuitBreaker(
            failure_threshold=5, recovery_timeout_s=20.0
        )
        self._caller = ResilientCaller(
            timeout_s=timeout_s, attempts=tentativas, breaker=self._breaker
        )

    @property
    def breaker(self) -> CircuitBreaker:
        return self._breaker

    def responder(
        self,
        *,
        sistema: str,
        pergunta: str,
        trechos: list[Any],
        tenant: str,
        tarefa: str,
    ) -> RespostaLlm:
        def chamar() -> RespostaLlm:
            return self._primario.responder(
                sistema=sistema,
                pergunta=pergunta,
                trechos=trechos,
                tenant=tenant,
                tarefa=tarefa,
            )

        try:
            return self._caller.call(chamar)
        except (TimeoutError, CircuitOpenError, LlmUnavailableError):
            return self._fallback.responder(
                sistema=sistema,
                pergunta=pergunta,
                trechos=trechos,
                tenant=tenant,
                tarefa=tarefa,
            )


def construir_llm(config: Any, *, expandir: Any = None) -> LlmPort:
    """Escolhe o modo pelo ambiente. Default seguro = extrativo real."""
    ativo = os.getenv("LLM_GATEWAY_ATIVO", "0").strip().lower() in {
        "1",
        "true",
        "sim",
        "on",
    }
    extrativo = RespostaExtrativa(expandir=expandir)
    if not ativo:
        return extrativo
    return LlmResiliente(
        LlmGateway(modelo_padrao=config.gateway_modelo_padrao),
        fallback=extrativo,
        timeout_s=config.gateway_timeout_s,
        tentativas=config.gateway_tentativas,
    )
