"""Telemetria — instrumentada ANTES de otimizar qualquer coisa.

Sem métricas não há benchmark, não há diagnóstico e não há decisão de custo.
Uma linha JSON por operação, append-only. JSONL + SQLite respondem tudo numa
POC; não construa plataforma para isso.

**Regra-zero:** todo número publicado leva selo — `medido`, `proxy`, `estimado`
ou `pendente`. Nenhuma estimativa aparece como medição.
"""
from __future__ import annotations

import json
import time
from pathlib import Path


def agora_ms() -> float:
    return time.time() * 1000


def derivar_intervalos(marcos: dict, rotulos: dict[str, str]) -> dict:
    """Marcos absolutos -> durações por etapa + o total PERCEBIDO.

    `rotulos` mapeia "T0-T1" -> "captura". O total ponta a ponta é a métrica
    soberana: um modelo 2 s mais rápido que exige 4 s de preparo é pior.
    """
    chaves = sorted(marcos, key=lambda k: int(k[1:]))
    out: dict[str, float] = {}
    for a, b in zip(chaves, chaves[1:]):
        rot = rotulos.get(f"{a}-{b}", f"{a}-{b}")
        out[rot] = round(marcos[b] - marcos[a], 2)
    if len(chaves) >= 2:
        out["e2e"] = round(marcos[chaves[-1]] - marcos[chaves[0]], 2)
    return out


def percentil(valores: list[float], p: float) -> float | None:
    """Percentis, nunca média: a média esconde exatamente o caso ruim."""
    if not valores:
        return None
    s = sorted(valores)
    k = max(0, min(len(s) - 1, round((p / 100) * (len(s) - 1))))
    return round(s[k], 1)


class Telemetry:
    def __init__(self, arquivo: Path) -> None:
        self.arquivo = Path(arquivo)
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)

    def registrar(self, linha: dict, *, selo: str = "medido") -> dict:
        registro = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **linha, "selo": selo}
        with self.arquivo.open("a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
        return registro

    def ler(self) -> list[dict]:
        if not self.arquivo.exists():
            return []
        return [json.loads(l) for l in
                self.arquivo.read_text(encoding="utf-8").splitlines() if l.strip()]

    def agregar(self, campo_latencia: str = "e2e_ms") -> dict:
        linhas = self.ler()
        if not linhas:
            return {"n": 0, "selo": "pendente"}

        # ATENÇÃO — a lição que mais custou caro num projeto real: NÃO some
        # contadores que significam coisas diferentes. "Entregue", "rejeitado na
        # entrada" (o sistema funcionando) e "erro" (o sistema quebrando) são
        # três números. Somá-los produziu, uma vez, "100% de sucesso" com todas
        # as entradas rejeitadas.
        entregues = [x for x in linhas if x.get("resultado") == "entregue"]
        rejeitadas = [x for x in linhas if x.get("resultado") == "rejeitado"]
        erros = [x for x in linhas if x.get("resultado") == "erro"]
        lat = [x[campo_latencia] for x in entregues if x.get(campo_latencia) is not None]
        custo = sum(x.get("custo_usd", 0.0) for x in linhas)

        return {
            "n": len(linhas),
            "taxa_entrega": round(len(entregues) / len(linhas), 4),
            "taxa_rejeicao_de_entrada": round(len(rejeitadas) / len(linhas), 4),
            "taxa_erro": round(len(erros) / len(linhas), 4),
            "p50_ms": percentil(lat, 50),
            "p95_ms": percentil(lat, 95),
            "p99_ms": percentil(lat, 99),
            "custo_total_usd": round(custo, 5),
            "custo_por_operacao_usd": round(custo / len(linhas), 6),
            "selo": "medido",
        }
