"""logs_obs — biblioteca da skill `logs-observabilidade` (stdlib pura, Python 3.11+).

Módulos:
  mascara   — detecção validada (CPF, CNPJ, PAN com Luhn, e-mail, telefone, JWT, chaves) e
              mascaramento no formato canônico da Squad (antes → depois reproduzível).
  regras    — catálogo das regras LOG-xx (id, severidade, linguagem, como detectar, correção).
  lint      — varredura determinística de código, configuração e artefatos de log.

Sem rede, sem LLM, sem dependência fora da stdlib — roda no gate em menos de 1 s.
"""
from __future__ import annotations

__all__ = ["mascara", "regras", "lint"]
__version__ = "1.0.0"
