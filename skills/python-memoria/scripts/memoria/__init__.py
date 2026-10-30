"""memoria — biblioteca da skill `python-memoria` (stdlib pura, Python 3.10+).

Módulos:
  regras     — catálogo das regras MEM-xx (id, severidade, como detectar, correção, reference).
  lint       — lente determinística por AST sobre código Python (sem rede, sem LLM, < 1 s).
  orcamento  — medição de pico de memória (tracemalloc + RSS/HWM do processo) e orçamento em teste.

Convenção de saída igual às outras lentes da Squad: 0 aprovado · 1 reprovado · 2 inconclusivo.
"""
from __future__ import annotations

__all__ = ["regras", "lint", "orcamento"]
__version__ = "1.0.0"
