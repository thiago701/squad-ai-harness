"""M1 — o agente. Triagem → recusa → escalonamento → RAG → resposta citada.

Guard de entrada e resiliência vêm de `conversation_core`; retrieval vem de
`rag_kit`. Aqui mora só a política do produto.

Invariante (restrição 4): se `fontes` está vazio e a resposta não veio de
ferramenta, o agente diz que não sabe. Não existe caminho que produza texto
afirmativo sem procedência.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from conversation_core import InputGuard

from .conhecimento import citar, recuperar
from .llm import RespostaLlm
from .vertical import Triagem, VerticalPack

_DATAS = re.compile(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b")
_HOSPEDES = re.compile(r"\b(\d{1,2})\s*(?:pessoas?|h[oó]spedes?|adultos?)\b", re.I)


@dataclass(frozen=True, slots=True)
class Entrada:
    texto: str
    sessao: str
    usuario: str
    canal: str = "web"
    message_id: str = ""
    tenant: str = "demo"


@dataclass
class Resposta:
    texto: str
    intencao: str = ""
    fontes: tuple[str, ...] = ()
    escalonado: bool = False
    sem_fonte: bool = False
    recusado: str = ""
    motivo: str = ""
    modelo: str = ""
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_brl: float = 0.0
    latencia_ms: float = 0.0
    contexto: tuple[str, ...] = ()
    ferramenta: str = ""
    dados: dict[str, Any] = field(default_factory=dict)


def extrair_slots(texto: str, hoje: date | None = None) -> dict[str, Any]:
    """Slot filling determinístico: datas e nº de hóspedes. Sem LLM, sem custo."""
    referencia = hoje or date.today()
    slots: dict[str, Any] = {}
    achadas: list[str] = []
    for dia, mes, ano in _DATAS.findall(texto):
        try:
            completo = int(ano) if ano else referencia.year
            if completo < 100:
                completo += 2000
            achadas.append(datetime(completo, int(mes), int(dia)).date().isoformat())
        except ValueError:
            continue
    if achadas:
        slots["data_entrada"] = achadas[0]
    if len(achadas) > 1:
        slots["data_saida"] = achadas[1]
    hospedes = _HOSPEDES.search(texto)
    if hospedes:
        slots["hospedes"] = int(hospedes.group(1))
    return slots


class Agente:
    def __init__(
        self,
        *,
        pack: VerticalPack,
        base: Any,
        llm: Any,
        config: Any,
        ferramentas: Any = None,
        guard: InputGuard | None = None,
        historico: Any = None,
    ):
        self._pack = pack
        self._base = base
        self._llm = llm
        self._config = config
        self._ferramentas = ferramentas
        self._guard = guard or InputGuard(max_chars=2000)
        self._triagem = Triagem(pack)
        self._historico = historico

    # -- política de recusa -------------------------------------------------

    def _recusa(self, texto: str) -> str:
        for padrao in self._pack.padroes_recusa:
            if padrao.regex.search(texto):
                return padrao.motivo
        return ""

    # -- ferramentas --------------------------------------------------------

    def _tentar_ferramenta(self, intencao: str, texto: str) -> Any:
        """Dispatch dirigido pelo pack — nenhum `if` por vertical aqui.

        A ferramenta declara `intencao` e `slots_obrigatorios`; se os slots
        forem extraíveis da mensagem, ela roda.
        """
        if self._ferramentas is None:
            return None
        minusculo = texto.lower()
        for ferramenta in self._pack.ferramentas.values():
            if ferramenta.intencao != intencao or not ferramenta.intencao:
                continue
            slots: dict[str, Any] = {"consulta": texto}
            slots.update(extrair_slots(texto))
            for campo, mapa in ferramenta.slots_por_palavra.items():
                for gatilho, valor in mapa.items():
                    if gatilho.lower() in minusculo:
                        slots[campo] = valor
                        break
            for campo, valor in ferramenta.slots_padrao.items():
                slots.setdefault(campo, valor)
            if not set(ferramenta.slots_obrigatorios) <= set(slots):
                continue
            return self._ferramentas.executar(ferramenta.nome, slots)
        return None

    # -- fluxo principal ----------------------------------------------------

    def responder(self, entrada: Entrada, *, llm: Any = None) -> Resposta:
        """`llm` sobrescreve o modelo do turno — usado na degradação por teto."""
        modelo = llm if llm is not None else self._llm
        verificado = self._guard.check(entrada.texto)
        if not verificado.ok:
            return Resposta(
                texto="Não consegui ler essa mensagem. Pode reformular?",
                recusado=verificado.reason,
                motivo=verificado.reason,
            )
        texto = verificado.sanitized_text
        intencao, _ = self._triagem.classificar(texto)

        motivo_recusa = self._recusa(texto)
        if motivo_recusa:
            return Resposta(
                texto=self._pack.mensagem(
                    "recusa", "Isso eu não posso confirmar por aqui. Vou chamar um atendente."
                ),
                intencao=intencao,
                escalonado=True,
                recusado=motivo_recusa,
                motivo=motivo_recusa,
            )

        if intencao in self._pack.escalonar_intencoes:
            return Resposta(
                texto=self._pack.mensagem(
                    "escalonamento", "Vou transferir você para um atendente."
                ),
                intencao=intencao,
                escalonado=True,
                motivo=f"intencao:{intencao}",
            )

        resultado = self._tentar_ferramenta(intencao, texto)
        if resultado is not None and resultado.ok:
            return Resposta(
                texto=resultado.texto,
                intencao=intencao,
                fontes=(resultado.fonte,),
                ferramenta=resultado.ferramenta,
                dados=dict(resultado.dados),
                modelo="ferramenta",
            )

        trechos = recuperar(self._base, texto, self._config)
        if not trechos:
            return Resposta(
                texto=self._pack.mensagem(
                    "sem_fonte",
                    "Não encontrei isso na base. Vou chamar um atendente para te responder.",
                ),
                intencao=intencao,
                sem_fonte=True,
                escalonado=self._pack.escalonar_sem_fonte,
                motivo="sem_fonte",
            )

        saida: RespostaLlm = modelo.responder(
            sistema=self._pack.sistema(),
            pergunta=texto,
            trechos=trechos,
            tenant=entrada.tenant,
            tarefa=intencao,
        )
        fontes = citar(trechos)
        return Resposta(
            texto=saida.texto,
            intencao=intencao,
            fontes=fontes,
            modelo=saida.modelo,
            tokens_entrada=saida.tokens_entrada,
            tokens_saida=saida.tokens_saida,
            custo_brl=saida.custo_brl,
            latencia_ms=saida.latencia_ms,
            contexto=tuple(f"{p.source}#{p.chunk_id}" for p in trechos),
        )
