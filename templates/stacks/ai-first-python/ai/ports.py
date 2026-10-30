"""Contratos da camada de orquestração de IA.

Nenhum componente de negócio importa SDK de fornecedor. Um `Protocol` e adapters
finos: 40 linhas suas valem mais que a superfície de uma lib inteira, porque você
controla a semântica de erro, de custo e de timeout — que é o que a abstração de
terceiro esconde justamente quando você mais precisa dela.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class Requisicao:
    """Ajuste os campos ao seu domínio. `seed` fica: sem ela não há benchmark
    reproduzível — você compararia ruído em vez de provedores."""

    entrada_ref: str            # caminho/URI. NUNCA bytes atravessando camadas
    instrucao: str
    perfil: str                 # tema, modo, tarefa… o que o seu domínio chama
    seed: int | None = None
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Resultado:
    saida_ref: str
    provider: str
    model: str
    latency_ms: float
    cost_usd: float
    seed: int | None = None
    flags: tuple[str, ...] = field(default_factory=tuple)


@runtime_checkable
class Provider(Protocol):
    """Uma operação de IA, com custo, latência e erro tipados."""

    name: str
    #: custo de referência por chamada, em USD. 0.0 = local/determinístico.
    custo_referencia_usd: float
    #: um provedor terminal NUNCA falha — é o fim de toda cadeia de fallback.
    terminal: bool

    async def health(self) -> bool: ...

    async def executar(self, req: Requisicao, *, timeout_s: float) -> Resultado: ...
