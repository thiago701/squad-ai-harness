#!/usr/bin/env python3
"""Entrada da skill contrato-reverso — roda contra QUALQUER projeto.

    python <skill>/scripts/cr.py iniciar    --raiz <projeto>   # rascunho do contrato + verificador do provedor
    python <skill>/scripts/cr.py verificar  --raiz <projeto> --nivel rapido|direcionado|ampliado|auto
    python <skill>/scripts/cr.py impacto    --raiz <projeto>
    python <skill>/scripts/cr.py observar   --raiz <projeto>
    python <skill>/scripts/cr.py bench      --raiz <projeto>

Saída de `verificar`: 0 aprovado · 1 reprovado · 2 inconclusivo. Stdlib + PyYAML.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from contrato_reverso.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
