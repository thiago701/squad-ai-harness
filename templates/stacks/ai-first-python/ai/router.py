"""Roteamento por REGRAS — não machine learning.

Com poucos provedores e nenhum histórico, um roteador aprendido precisaria de
milhares de observações rotuladas para superar seis `if`. Regras explícitas são
auditáveis, testáveis e depuráveis às 23h de um incidente; um modelo não é.

Três invariantes:
  1. Toda cadeia termina em algo que não pode falhar.
  2. Teto de orçamento é sinal de primeira classe.
  3. Aderência ao último caminho bom evita oscilação.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum

from .errors import ErroPermanente
from .ports import Provider


class EstadoDisjuntor(StrEnum):
    FECHADO = "FECHADO"
    ABERTO = "ABERTO"
    MEIO_ABERTO = "MEIO_ABERTO"
    LOCKOUT = "LOCKOUT"      # falha permanente: não volta sozinha, exige humano


@dataclass(slots=True)
class Disjuntor:
    falhas: int = 0
    estado: EstadoDisjuntor = EstadoDisjuntor.FECHADO
    aberto_ate: float = 0.0
    cooldown_s: float = 30.0
    limite: int = 3

    def disponivel(self, agora: float) -> bool:
        if self.estado is EstadoDisjuntor.LOCKOUT:
            return False
        if self.estado is EstadoDisjuntor.ABERTO:
            if agora >= self.aberto_ate:
                self.estado = EstadoDisjuntor.MEIO_ABERTO
                return True
            return False
        return True

    def sucesso(self) -> None:
        if self.estado is EstadoDisjuntor.LOCKOUT:
            return
        self.falhas = 0
        self.cooldown_s = 30.0
        self.estado = EstadoDisjuntor.FECHADO

    def falha(self, exc: BaseException, agora: float) -> None:
        # Falha permanente NÃO entra em cooldown curto: tentar para sempre um
        # caminho que não volta sozinho é o erro clássico desta camada.
        if isinstance(exc, ErroPermanente):
            self.estado = EstadoDisjuntor.LOCKOUT
            return
        self.falhas += 1
        meio = self.estado is EstadoDisjuntor.MEIO_ABERTO
        if meio or self.falhas >= self.limite:
            if meio:
                self.cooldown_s = min(self.cooldown_s * 2, 300.0)
            self.estado = EstadoDisjuntor.ABERTO
            self.aberto_ate = agora + self.cooldown_s
            self.falhas = 0


@dataclass(slots=True)
class Contexto:
    """Só sinais OBSERVÁVEIS em tempo real. Nenhum inferido."""

    online: bool = True
    fila_len: int = 0
    limite_fila: int = 6
    custo_acumulado_usd: float = 0.0
    teto_usd: float = 100.0
    ultimo_bom: str | None = None


class Router:
    def __init__(self, provedores: list[Provider], terminal: Provider,
                 ctx: Contexto | None = None) -> None:
        if not terminal.terminal:
            raise ValueError("o provedor terminal precisa declarar terminal=True")
        self.provedores = {p.name: p for p in provedores}
        self.terminal = terminal
        self.ctx = ctx or Contexto()
        self.disjuntores = {n: Disjuntor() for n in self.provedores}

    @property
    def fracao_orcamento(self) -> float:
        return self.ctx.custo_acumulado_usd / self.ctx.teto_usd if self.ctx.teto_usd else 0.0

    def resolver(self, nome: str) -> Provider | None:
        """Ponto ÚNICO de nome → objeto.

        Se o estado guarda nomes (serializáveis) e os objetos vivem fora dele,
        dois lugares fazendo essa resolução é bug garantido: um deles não vai
        conhecer o provedor recém-adicionado, e o pedido cai no fallback em
        silêncio. Aconteceu num projeto real.
        """
        if nome == self.terminal.name:
            return self.terminal
        return self.provedores.get(nome)

    def rotear(self, *, premium: bool = False, agora: float | None = None) -> list[Provider]:
        agora = time.monotonic() if agora is None else agora

        if self.fracao_orcamento >= 1.0:          # trava dura: degrada, não para
            return [self.terminal]
        if not self.ctx.online:
            return [self.terminal]

        candidatos = [n for n, d in self.disjuntores.items() if d.disponivel(agora)]
        pressao = self.ctx.fila_len > self.ctx.limite_fila or self.fracao_orcamento >= 0.8
        if pressao:
            candidatos.sort(key=lambda n: self.provedores[n].custo_referencia_usd)
        elif premium:
            candidatos.sort(key=lambda n: -self.provedores[n].custo_referencia_usd)

        ub = self.ctx.ultimo_bom                  # aderência: não oscile a cada request
        if not pressao and ub in candidatos:
            candidatos.remove(ub)
            candidatos.insert(0, ub)

        return [self.provedores[n] for n in candidatos] + [self.terminal]

    def marcar_sucesso(self, nome: str, custo_usd: float) -> None:
        if nome in self.disjuntores:
            self.disjuntores[nome].sucesso()
            self.ctx.ultimo_bom = nome
        self.ctx.custo_acumulado_usd += custo_usd

    def marcar_falha(self, nome: str, exc: BaseException, agora: float | None = None) -> None:
        if nome in self.disjuntores:
            self.disjuntores[nome].falha(exc, time.monotonic() if agora is None else agora)

    def snapshot(self) -> dict:
        return {
            "custo_acumulado_usd": round(self.ctx.custo_acumulado_usd, 4),
            "fracao_orcamento": round(self.fracao_orcamento, 3),
            "ultimo_bom": self.ctx.ultimo_bom,
            "online": self.ctx.online,
            "disjuntores": {n: d.estado.value for n, d in self.disjuntores.items()},
        }
