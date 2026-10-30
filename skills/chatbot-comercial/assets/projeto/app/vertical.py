"""Vertical-pack: persona, intenções, ferramentas, recusas e KPIs por vertical.

Adicionar um vertical = adicionar `verticais/<nome>.json` + a seção
correspondente em `references/verticais.md`. Nenhum arquivo do núcleo muda.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rag_kit import fold


@dataclass(frozen=True, slots=True)
class Ferramenta:
    """Declaração de ferramenta — inclusive QUANDO chamá-la.

    O binding intenção→ferramenta mora aqui, no pack, e não no núcleo. Sem
    isso, `agente.py` precisaria de um `if intencao == ...` por vertical, e a
    promessa de "vertical novo sem tocar no núcleo" seria falsa.
    """

    nome: str
    descricao: str
    parametros: tuple[str, ...]
    efeito: str
    intencao: str = ""
    slots_obrigatorios: tuple[str, ...] = ()
    slots_padrao: dict[str, Any] = field(default_factory=dict)
    # {"tipo_acomodacao": {"suite master": "Suíte Master", "chale": "Chalé"}}
    slots_por_palavra: dict[str, dict[str, str]] = field(default_factory=dict)
    # Adapter genérico quando não há `_f_<nome>` no núcleo (ex.: "tabela").
    adapter: str = ""
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PadraoRecusa:
    regex: re.Pattern[str]
    motivo: str


@dataclass(frozen=True)
class VerticalPack:
    vertical: str
    rotulo: str
    persona_instrucao: str
    persona_tom: str
    intencoes: dict[str, tuple[str, ...]]
    ferramentas: dict[str, Ferramenta]
    escalonar_intencoes: frozenset[str]
    escalonar_sem_fonte: bool
    recusas: tuple[str, ...]
    padroes_recusa: tuple[PadraoRecusa, ...]
    captura_lead: dict[str, Any]
    kpis: tuple[str, ...]
    mensagens: dict[str, str] = field(default_factory=dict)
    # Vocabulário do cliente → vocabulário da base. "cachorro" → "animais de
    # estimação". Sem isto o RAG erra por léxico, não por falta de conteúdo.
    sinonimos: dict[str, set[str]] = field(default_factory=dict)
    # Palavras frequentes e inúteis deste domínio (nome do estabelecimento,
    # "pousada", "serviço"). Elas não ancoram resposta — ver conhecimento.py.
    termos_ignorados: frozenset[str] = frozenset()

    @staticmethod
    def carregar(caminho: Path, *, estabelecimento: str = "") -> VerticalPack:
        if not caminho.exists():
            raise FileNotFoundError(
                f"vertical-pack não encontrado: {caminho}. "
                "Crie o arquivo e documente-o em references/verticais.md."
            )
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
        faltando = {"vertical", "persona", "intencoes"} - set(bruto)
        if faltando:
            raise ValueError(f"{caminho.name}: campos obrigatórios ausentes: {faltando}")

        persona = bruto["persona"]
        instrucao = persona.get("instrucao", "").replace(
            "{{ESTABELECIMENTO}}", estabelecimento or bruto.get("rotulo", "")
        )
        return VerticalPack(
            vertical=bruto["vertical"],
            rotulo=bruto.get("rotulo", bruto["vertical"]),
            persona_instrucao=instrucao,
            persona_tom=persona.get("tom", ""),
            intencoes={
                i["nome"]: tuple(i.get("palavras", ())) for i in bruto["intencoes"]
            },
            ferramentas={
                f["nome"]: Ferramenta(
                    nome=f["nome"],
                    descricao=f.get("descricao", ""),
                    parametros=tuple(f.get("parametros", ())),
                    efeito=f.get("efeito", "leitura"),
                    intencao=f.get("intencao", ""),
                    slots_obrigatorios=tuple(f.get("slots_obrigatorios", ())),
                    slots_padrao=dict(f.get("slots_padrao", {})),
                    slots_por_palavra=dict(f.get("slots_por_palavra", {})),
                    adapter=f.get("adapter", ""),
                    config=dict(f.get("config", {})),
                )
                for f in bruto.get("ferramentas", [])
            },
            escalonar_intencoes=frozenset(bruto.get("escalonar_intencoes", ())),
            escalonar_sem_fonte=bool(bruto.get("escalonar_sem_fonte", True)),
            recusas=tuple(bruto.get("recusas", ())),
            padroes_recusa=tuple(
                PadraoRecusa(re.compile(p["regex"], re.I), p.get("motivo", "recusa"))
                for p in bruto.get("padroes_recusa", [])
            ),
            captura_lead=dict(bruto.get("captura_lead", {})),
            kpis=tuple(bruto.get("kpis", ())),
            mensagens=dict(bruto.get("mensagens", {})),
            sinonimos={
                chave: set(valores)
                for chave, valores in (bruto.get("sinonimos") or {}).items()
            },
            termos_ignorados=frozenset(
                fold(t) for t in bruto.get("termos_ignorados", ())
            ),
        )

    def mensagem(self, chave: str, padrao: str) -> str:
        return self.mensagens.get(chave, padrao)

    def sistema(self) -> str:
        """Prompt de sistema: persona + tom + política de recusa explícita."""
        blocos = [self.persona_instrucao]
        if self.persona_tom:
            blocos.append(f"Tom: {self.persona_tom}.")
        if self.recusas:
            blocos.append("Regras que você não pode quebrar:")
            blocos.extend(f"- {r}" for r in self.recusas)
        if self.ferramentas:
            nomes = ", ".join(self.ferramentas)
            blocos.append(f"Ferramentas disponíveis: {nomes}.")
        return "\n".join(blocos)


class Triagem:
    """Classificação por palavras do pack. Barata, auditável, sem chamada de LLM.

    Stage 1 do funil: 100% das mensagens passam aqui. Só quem sobrevive à
    triagem custa token.

    Duas regras que valem para qualquer vertical:

    1. **Fronteira de palavra, casando prefixo.** `cao` casa "cão" mas não
       "recep*ção*"; `quarto` casa "quartos". Casamento por substring solto
       produz erro silencioso — foi assim que "qual o horário de atendimento
       da recepção" foi classificada como `pet`.
    2. **A ordem das intenções no pack é a precedência.** Empate de acertos
       vai para quem aparece primeiro. Ordene da mais específica para a mais
       genérica.
    """

    def __init__(self, pack: VerticalPack, *, padrao: str = "outros"):
        self._regras: list[tuple[str, tuple[re.Pattern[str], ...]]] = []
        for nome, palavras in pack.intencoes.items():
            vistas: set[str] = set()
            padroes: list[re.Pattern[str]] = []
            for palavra in palavras:
                normalizada = fold(palavra).strip()
                if not normalizada or normalizada in vistas:
                    continue
                vistas.add(normalizada)
                padroes.append(re.compile(r"\b" + re.escape(normalizada)))
            if padroes:
                self._regras.append((nome, tuple(padroes)))
        self._padrao = padrao

    def classificar(self, texto: str) -> tuple[str, float]:
        normalizado = fold(texto or "")
        melhor_nome, melhor_peso = self._padrao, 0.0
        for nome, padroes in self._regras:
            acertos = sum(1 for p in padroes if p.search(normalizado))
            if not acertos:
                continue
            peso = min(0.95, 0.55 + 0.15 * acertos)
            if peso > melhor_peso:
                melhor_nome, melhor_peso = nome, peso
        return melhor_nome, melhor_peso or 0.3
