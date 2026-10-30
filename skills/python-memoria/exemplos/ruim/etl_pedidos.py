"""FIXTURE SINTÉTICA — tudo aqui está ERRADO de propósito (selftest da lente MEM-xx).

Versão correta: ../bom/etl_pedidos.py. Não use como referência de código.
"""
import asyncio
import copy
import hashlib
import queue
from dataclasses import dataclass
from functools import cache, lru_cache
from multiprocessing import Pool

import pandas as pd
import requests

CACHE_CLIENTES = {}                                   # MEM-12: cresce em função, ninguém esvazia
HISTORICO_EVENTOS = []                                # MEM-12


@dataclass
class Pedido:                                         # MEM-13: 5 campos sem slots=True
    id: str
    cliente_id: str
    valor_centavos: int
    status: str
    criado_em: str


class Catalogo:
    @lru_cache(maxsize=None)                          # MEM-01: ilimitado
    def preco(self, sku: str) -> int:
        return len(sku)

    @lru_cache(maxsize=256)                           # MEM-01: self preso no cache da classe
    def descricao(self, sku: str) -> str:
        return sku.upper()


@cache                                                # MEM-01: @cache nunca descarta
def converter_moeda(valor: float, taxa: float) -> float:
    return valor * taxa


def carregar(caminho: str) -> list[str]:
    with open(caminho, encoding="utf-8") as f:
        linhas = f.readlines()                        # MEM-02
    with open(caminho, encoding="utf-8") as f:
        outras = f.read().splitlines()                # MEM-02
    for linha in open(caminho).readlines():           # MEM-02
        CACHE_CLIENTES[linha] = linha
    return linhas + outras


def parsear(linhas: list[str]) -> list[Pedido]:
    return [Pedido(*l.split(";")) for l in linhas]     # instanciada em massa → MEM-13 na classe


def resumir(pedidos: list[Pedido]) -> dict:
    total = sum([p.valor_centavos for p in pedidos])             # MEM-04
    algum_grande = any([p.valor_centavos > 1_000_000 for p in pedidos])   # MEM-04
    ids = set([p.id for p in pedidos])                            # MEM-04
    maior = sorted([p.valor_centavos for p in pedidos])[-1]       # MEM-04 + MEM-18
    menor = sorted(p.valor_centavos for p in pedidos)[0]          # MEM-18
    return {"total": total, "grande": algum_grande, "ids": ids, "maior": maior, "menor": menor}


def relatorio(pedidos: list[Pedido]) -> str:
    texto = ""
    linhas = []
    for p in pedidos:
        texto += f"{p.id};{p.valor_centavos}\n"      # MEM-05
        linhas = linhas + [p.id]                     # MEM-05
        copia = copy.deepcopy(p)                     # MEM-07
        HISTORICO_EVENTOS.append(copia)
    for k in list(CACHE_CLIENTES.keys()):            # MEM-06: só itera, não muta
        texto += k                                   # (MEM-05 não dispara: tipo de k desconhecido — limite declarado)
    for p in [x for x in pedidos if x.status == "PAGO"]:   # MEM-19
        linhas.append(p.id)
    return texto


def carregar_dataframe(caminho: str) -> pd.DataFrame:
    df = pd.read_csv(caminho)                        # MEM-08: sem dtype/usecols/chunksize
    partes = pd.DataFrame()
    for _, linha in df.iterrows():                   # MEM-09
        partes = pd.concat([partes, linha.to_frame().T])   # MEM-10
        df2 = df.copy()                              # MEM-10
    return partes


def baixar(url: str, destino: str) -> str:
    r = requests.get(url)
    with open(destino, "wb") as f:
        f.write(r.content)                           # MEM-11
    with open(destino, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()  # MEM-14


def hash_incremental(caminho: str) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        h.update(f.read())                           # MEM-14
    return h.hexdigest()


def processar_lote(itens: list[dict]) -> list:
    erros = []
    for item in itens:
        try:
            int(item["valor"])
        except ValueError as e:
            erros.append(e)                          # MEM-15: exceção segura traceback+frames
    return erros


async def buscar_todos(urls: list[str]) -> list:
    async def um(u):
        return u
    return await asyncio.gather(*[um(u) for u in urls])   # MEM-16: sem backpressure


async def disparar(urls: list[str]) -> None:
    for u in urls:
        asyncio.create_task(buscar_todos([u]))       # MEM-16: create_task em loop


def paralelo(itens: list[int]) -> list[int]:
    fila = queue.Queue()                             # MEM-17: sem maxsize
    with Pool() as pool:                             # MEM-17: sem maxtasksperchild
        return pool.map(abs, itens)
