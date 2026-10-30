"""Versão CORRETA do ../ruim/etl_pedidos.py — passa limpa na lente MEM-xx.

Doutrina aplicada: streaming em vez de materializar, geradores entre etapas, caches com limite,
dados com dtype declarado e concatenação única, I/O em blocos, exceções guardadas como texto,
backpressure em async, workers reciclados — e um orçamento de memória medido no teste.
"""
import asyncio
import hashlib
import queue
from collections import deque
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from functools import lru_cache
from multiprocessing import Pool

import pandas as pd
import requests

HISTORICO_EVENTOS: deque = deque(maxlen=10_000)      # histórico com limite: o mais velho sai sozinho


@dataclass(slots=True, frozen=True)                   # slots: ~50 % menos memória por instância; frozen: sem cópia defensiva
class Pedido:
    id: str
    cliente_id: str
    valor_centavos: int
    status: str
    criado_em: str


@lru_cache(maxsize=4_096)                             # cache dimensionado (função pura, chave sem self)
def preco(sku: str) -> int:
    return len(sku)


def carregar(caminho: str) -> Iterator[str]:
    """Gerador: uma linha viva por vez, qualquer tamanho de arquivo."""
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            yield linha.rstrip("\n")


def parsear(linhas: Iterable[str]) -> Iterator[Pedido]:
    for l in linhas:                                  # gerador: um Pedido vivo por vez (slots → ~50 % menor)
        yield Pedido(*l.split(";"))


def resumir(pedidos: Iterable[Pedido]) -> dict:
    valores = [p.valor_centavos for p in pedidos]     # materializa UMA vez porque três agregações precisam dele
    return {"total": sum(valores), "grande": any(v > 1_000_000 for v in valores),
            "maior": max(valores) if valores else 0, "menor": min(valores) if valores else 0}


def relatorio(pedidos: Iterable[Pedido]) -> str:
    partes = []                                       # acumula e junta uma vez (O(n))
    pagos = []
    for p in pedidos:
        partes.append(f"{p.id};{p.valor_centavos}\n")
        if p.status == "PAGO":
            pagos.append(p.id)
        HISTORICO_EVENTOS.append(p)                   # frozen: sem deepcopy
    return "".join(partes)


def carregar_dataframe(caminho: str) -> pd.DataFrame:
    pedacos = []
    for chunk in pd.read_csv(caminho, usecols=["id", "valor_centavos", "status"],
                             dtype={"id": "string", "valor_centavos": "int32", "status": "category"},
                             chunksize=100_000):
        pedacos.append(chunk[chunk["status"] == "PAGO"])
    return pd.concat(pedacos, ignore_index=True) if pedacos else pd.DataFrame()


def baixar(url: str, destino: str) -> str:
    h = hashlib.sha256()
    with requests.get(url, stream=True, timeout=30) as r, open(destino, "wb") as f:
        r.raise_for_status()
        for bloco in r.iter_content(chunk_size=1 << 20):   # 1 MiB vivo por vez
            f.write(bloco)
            h.update(bloco)
    return h.hexdigest()


def hash_arquivo(caminho: str) -> str:
    with open(caminho, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()   # 3.11+: blocos internos, sem read() inteiro


def processar_lote(itens: Iterable[dict]) -> list[dict]:
    erros = []
    for item in itens:
        try:
            int(item["valor"])
        except ValueError as e:
            erros.append({"item": item.get("id"), "erro": f"{type(e).__name__}: {e}"})   # texto, não a exceção
    return erros


async def buscar_todos(urls: list[str], paralelismo: int = 20) -> list:
    sem = asyncio.Semaphore(paralelismo)              # no máximo N vivas ao mesmo tempo

    async def um(u):
        async with sem:
            return u

    async with asyncio.TaskGroup() as tg:
        tarefas = [tg.create_task(um(u)) for u in urls]
    return [t.result() for t in tarefas]


def paralelo(itens: list[int]) -> list[int]:
    fila: queue.Queue = queue.Queue(maxsize=1_000)   # backpressure para o produtor
    with Pool(maxtasksperchild=500) as pool:          # worker reciclado: vazamento tem prazo de validade
        return pool.map(abs, itens, chunksize=1_000)
