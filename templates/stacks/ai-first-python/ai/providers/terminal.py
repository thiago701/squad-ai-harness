"""O provedor TERMINAL — esqueleto para adaptar ao seu domínio.

Um produto de IA sem terminal determinístico tem a disponibilidade do seu
fornecedor mais frágil. Este provedor roda local, é instantâneo, custa zero e
**não pode falhar**: se a operação principal der erro, ele ainda devolve algo
utilizável. O pior resultado aceitável nunca é uma tela de erro.

Substitua `_fallback_local` pela resposta trivial do SEU caso — o resumo
extractivo em vez do gerado, o thumbnail em vez do render, o filtro em vez da
difusão. A propriedade que importa é: sempre existe uma saída.
"""
from __future__ import annotations

import time
from pathlib import Path

from ..ports import Requisicao, Resultado


class TerminalProvider:
    name = "terminal-local"
    custo_referencia_usd = 0.0
    terminal = True

    def __init__(self, dir_saida: Path) -> None:
        self._dir = Path(dir_saida)
        self._dir.mkdir(parents=True, exist_ok=True)

    async def health(self) -> bool:
        return True                       # terminal é terminal

    async def executar(self, req: Requisicao, *, timeout_s: float) -> Resultado:
        t0 = time.perf_counter()
        destino = self._dir / f"{Path(req.entrada_ref).stem}_{req.perfil}_local"
        try:
            saida = self._fallback_local(req, destino)
        except Exception:
            # Nem aqui pode falhar: no pior caso, devolve a entrada intacta.
            destino.write_bytes(Path(req.entrada_ref).read_bytes())
            saida = str(destino)
        return Resultado(
            saida_ref=saida, provider=self.name, model="deterministico",
            latency_ms=(time.perf_counter() - t0) * 1000, cost_usd=0.0, seed=req.seed,
        )

    def _fallback_local(self, req: Requisicao, destino: Path) -> str:
        """SUBSTITUA. Transformação determinística, local e instantânea."""
        destino.write_bytes(Path(req.entrada_ref).read_bytes())
        return str(destino)
