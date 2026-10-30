"""Taxonomia de erro — a base de toda política de retry.

Repetir um erro permanente não conserta nada: só torna a falha N vezes mais lenta
e mais cara. Todo adapter traduz o erro do fornecedor para uma destas.
"""
from __future__ import annotations


class AppError(Exception):
    """Raiz de todo erro de domínio."""


class ErroTransitorio(AppError):
    """Vale a pena tentar de novo: 429, 503, timeout de rede, recurso ocupado."""


class ErroPermanente(AppError):
    """Não adianta repetir: 401, 400, entrada inválida, bug de configuração."""


class ErroValidacao(AppError):
    """A entrada não serve. Peça outra — não é falha de sistema."""


def deve_repetir(exc: BaseException) -> bool:
    """Política única de retry. NUNCA use `retry_on=Exception`: isso transforma
    um bug determinístico em três tentativas caras e uma falha 3x mais lenta."""
    return isinstance(exc, ErroTransitorio)
