"""M1 — ferramentas do agente. Fronteira com o sistema do cliente.

Regra de efeito, inegociável:
  `leitura`             o agente executa sozinho.
  `escrita_reversivel`  o agente executa e registra (ex.: pré-reserva).
  `escrita_irreversivel` o agente NUNCA executa — escala para humano.

O adapter demo lê um calendário local real (`dados/<vertical>/ocupacao.json`).
Trocar pelo PMS/ERP do cliente é implementar `FonteDeDisponibilidade` — o
agente não muda.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any, Protocol

from rag_kit import fold as _fold
from rag_kit import tokenize as _tokens


def _ler_tabela(arquivo: Path) -> list[dict[str, Any]]:
    if arquivo.suffix.lower() == ".csv":
        with arquivo.open(encoding="utf-8", newline="") as origem:
            return [dict(linha) for linha in csv.DictReader(origem)]
    bruto = json.loads(arquivo.read_text(encoding="utf-8"))
    if isinstance(bruto, dict):
        for valor in bruto.values():
            if isinstance(valor, list):
                return [linha for linha in valor if isinstance(linha, dict)]
        return []
    return [linha for linha in bruto if isinstance(linha, dict)]


@dataclass(frozen=True, slots=True)
class ResultadoFerramenta:
    ok: bool
    ferramenta: str
    dados: dict[str, Any]
    texto: str
    fonte: str = "ferramenta"


class FonteDeDisponibilidade(Protocol):
    def livres(self, entrada: date, saida: date, hospedes: int) -> list[dict[str, Any]]:
        ...

    def tarifa(self, tipo: str, entrada: date, saida: date) -> dict[str, Any] | None:
        ...


def _data(bruto: str) -> date:
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y"):
        try:
            return datetime.strptime(bruto.strip(), formato).date()
        except ValueError:
            continue
    raise ValueError(f"data inválida: {bruto!r}")


class CalendarioLocal:
    """Fonte real baseada em arquivo. Substituível pelo PMS do cliente."""

    def __init__(self, caminho: Path):
        self._caminho = caminho
        self._cache: dict[str, Any] | None = None

    def _carregar(self) -> dict[str, Any]:
        if self._cache is None:
            if not self._caminho.exists():
                self._cache = {"acomodacoes": [], "bloqueios": []}
            else:
                self._cache = json.loads(self._caminho.read_text(encoding="utf-8"))
        return self._cache

    def _bloqueado(self, codigo: str, entrada: date, saida: date) -> bool:
        for bloqueio in self._carregar().get("bloqueios", []):
            if bloqueio.get("acomodacao") != codigo:
                continue
            b_ini, b_fim = _data(bloqueio["de"]), _data(bloqueio["ate"])
            if entrada < b_fim and b_ini < saida:
                return True
        return False

    def livres(self, entrada: date, saida: date, hospedes: int) -> list[dict[str, Any]]:
        return [
            acomodacao
            for acomodacao in self._carregar().get("acomodacoes", [])
            if acomodacao.get("capacidade", 0) >= hospedes
            and not self._bloqueado(acomodacao["codigo"], entrada, saida)
        ]

    def tarifa(self, tipo: str, entrada: date, saida: date) -> dict[str, Any] | None:
        noites = max(1, (saida - entrada).days)
        alvo = tipo.strip().lower()
        for acomodacao in self._carregar().get("acomodacoes", []):
            nome = acomodacao.get("tipo", "").lower()
            if alvo and (alvo in nome or nome in alvo):
                diaria = float(acomodacao.get("diaria_brl", 0.0))
                return {
                    "tipo": acomodacao["tipo"],
                    "diaria_brl": diaria,
                    "noites": noites,
                    "total_brl": round(diaria * noites, 2),
                }
        return None


class Ferramentas:
    """Executor com política de efeito. Registra o que rodou, para auditoria.

    Dispatch em duas camadas:
      1. `_f_<nome>` — adapter específico do domínio (integra com o PMS/ERP).
      2. `_f_<adapter>` — adapter genérico declarado no pack.

    O adapter genérico `tabela` cobre a maioria das ferramentas de consulta dos
    outros verticais (cardápio, planos, serviços, tabela de preços) **sem
    escrever código novo**: o pack aponta o arquivo e os campos.
    """

    def __init__(
        self,
        pack: Any,
        fonte: FonteDeDisponibilidade,
        *,
        raiz_dados: Path | None = None,
        registrar_lead: Any = None,
    ):
        self._pack = pack
        self._fonte = fonte
        self._raiz_dados = raiz_dados
        self._registrar_lead = registrar_lead

    def disponiveis(self) -> list[str]:
        return sorted(self._pack.ferramentas)

    def executar(self, nome: str, argumentos: dict[str, Any]) -> ResultadoFerramenta:
        definicao = self._pack.ferramentas.get(nome)
        if definicao is None:
            return ResultadoFerramenta(False, nome, {}, f"ferramenta desconhecida: {nome}")
        if definicao.efeito == "escrita_irreversivel":
            return ResultadoFerramenta(
                False, nome, {}, "ação irreversível: precisa de atendente humano."
            )
        metodo = getattr(self, f"_f_{nome}", None)
        if metodo is None and definicao.adapter:
            generico = getattr(self, f"_f_{definicao.adapter}", None)
            if generico is not None:
                metodo = partial(generico, definicao)
        if metodo is None:
            return ResultadoFerramenta(
                False,
                nome,
                {},
                f"ferramenta `{nome}` declarada sem adapter. "
                "Use `adapter: tabela` no pack ou escreva `_f_{nome}`.",
            )
        try:
            return metodo(argumentos)
        except ValueError as exc:
            return ResultadoFerramenta(False, nome, {}, str(exc))

    # -- adapter genérico ---------------------------------------------------

    def _f_tabela(self, definicao: Any, args: dict[str, Any]) -> ResultadoFerramenta:
        """Consulta uma tabela de `dados/<vertical>/` declarada no pack.

        config: {"arquivo": "cardapio.json", "campo_busca": "item",
                 "campos_saida": ["item", "preco"], "limite": 5}
        """
        cfg = definicao.config
        arquivo = (self._raiz_dados or Path(".")) / str(cfg.get("arquivo", ""))
        if not arquivo.exists():
            raise ValueError(f"tabela não encontrada: {arquivo.name}")
        linhas = _ler_tabela(arquivo)
        campo = str(cfg.get("campo_busca", ""))
        termos = [t for t in _tokens(str(args.get("consulta", ""))) if len(t) >= 4]
        achadas = [
            linha
            for linha in linhas
            if any(t in _fold(str(linha.get(campo, ""))) for t in termos)
        ][: int(cfg.get("limite", 5))]
        if not achadas:
            return ResultadoFerramenta(False, definicao.nome, {}, "não encontrei na tabela.")
        saida = cfg.get("campos_saida") or list(achadas[0])
        texto = "\n".join(
            " · ".join(f"{c}: {linha[c]}" for c in saida if c in linha) for linha in achadas
        )
        return ResultadoFerramenta(
            True, definicao.nome, {"linhas": achadas}, texto, fonte=arquivo.stem
        )

    def _f_consultar_disponibilidade(self, args: dict[str, Any]) -> ResultadoFerramenta:
        entrada = _data(args["data_entrada"])
        saida = _data(args.get("data_saida") or str(entrada + timedelta(days=1)))
        hospedes = int(args.get("hospedes", 2))
        if saida <= entrada:
            raise ValueError("a data de saída precisa ser depois da entrada.")
        livres = self._fonte.livres(entrada, saida, hospedes)
        if not livres:
            texto = (
                f"Não temos acomodação livre para {hospedes} pessoa(s) "
                f"de {entrada:%d/%m} a {saida:%d/%m}."
            )
        else:
            # O hóspede quer saber o tipo, não o número da unidade.
            contagem: dict[str, int] = {}
            for acomodacao in livres:
                contagem[acomodacao["tipo"]] = contagem.get(acomodacao["tipo"], 0) + 1
            nomes = ", ".join(
                tipo if quantas == 1 else f"{tipo} ({quantas} unidades)"
                for tipo, quantas in contagem.items()
            )
            texto = (
                f"Para {hospedes} pessoa(s) de {entrada:%d/%m} a {saida:%d/%m} "
                f"temos: {nomes}."
            )
        return ResultadoFerramenta(
            True,
            "consultar_disponibilidade",
            {"livres": livres, "noites": (saida - entrada).days},
            texto,
            fonte="calendario",
        )

    def _f_consultar_tarifa(self, args: dict[str, Any]) -> ResultadoFerramenta:
        entrada = _data(args["data_entrada"])
        saida = _data(args.get("data_saida") or str(entrada + timedelta(days=1)))
        tarifa = self._fonte.tarifa(args.get("tipo_acomodacao", ""), entrada, saida)
        if tarifa is None:
            return ResultadoFerramenta(
                False, "consultar_tarifa", {}, "não encontrei esse tipo de acomodação."
            )
        texto = (
            f"{tarifa['tipo']}: R$ {tarifa['diaria_brl']:.2f} a diária, "
            f"{tarifa['noites']} noite(s) = R$ {tarifa['total_brl']:.2f}."
        )
        return ResultadoFerramenta(True, "consultar_tarifa", tarifa, texto, fonte="calendario")

    def _f_criar_pre_reserva(self, args: dict[str, Any]) -> ResultadoFerramenta:
        obrigatorios = {"nome", "contato", "data_entrada"}
        faltando = obrigatorios - {k for k, v in args.items() if str(v).strip()}
        if faltando:
            raise ValueError(f"faltam dados para a pré-reserva: {', '.join(sorted(faltando))}.")
        if self._registrar_lead is not None:
            self._registrar_lead(args)
        texto = (
            "Registrei sua pré-reserva. Ela vale por 24 horas e a recepção "
            "confirma a disponibilidade antes do pagamento do sinal."
        )
        return ResultadoFerramenta(
            True, "criar_pre_reserva", dict(args), texto, fonte="pre_reserva"
        )

    def _f_status_reserva(self, args: dict[str, Any]) -> ResultadoFerramenta:
        codigo = str(args.get("codigo_reserva", "")).strip().upper()
        if not codigo:
            raise ValueError("informe o código da reserva.")
        return ResultadoFerramenta(
            False,
            "status_reserva",
            {"codigo": codigo},
            "Consulta de reserva é feita pela recepção. Vou te transferir.",
        )
