# -*- coding: utf-8 -*-
"""Testes reversos dirigidos pelo consumidor (CDC) para APIs REST atrás do API Gateway.

"Reverso" = a análise parte da EXPECTATIVA DO CONSUMIDOR e caminha até o backend:

    expectativa do consumidor → contrato publicado (OpenAPI) → configuração do Gateway → backend

Camadas de evidência (uma NÃO substitui a outra — o relatório diz qual foi obtida):

    A  consumidor ↔ OpenAPI ............ estática, milissegundos   ("conformidade da especificação")
    B  consumidor/OpenAPI ↔ Gateway .... estática, milissegundos   ("configuração do Gateway")
    C1 provedor in-process ............. JUnit lê o MESMO contrato, Gateway SIMULADO a partir do SAM
                                         e persistência em dublê   ("compatibilidade da implementação")
    C2 replay HTTP ..................... pelo endpoint do Gateway num ambiente autorizado
                                         ("funcionamento pelo Gateway implantado")

Veredito: aprovado | reprovado | inconclusivo. Falta de ambiente, credencial, JDK ou
dependência é INCONCLUSIVO — nunca aprovado.

Dependências: stdlib + PyYAML (já usada em scripts/quality e scripts/template_registry).
Sem PyYAML o veredito é inconclusivo. Nada aqui acessa a internet: a replay HTTP só
roda com `--alvo` explícito e host permitido pelo contrato.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

QUEBRA = "quebra"        # o consumidor quebra (ou o contrato deixa de prometer o que ele usa) → reprova
RISCO = "risco"          # divergência real que hoje não quebra este consumidor → relatada, não reprova
PENDENTE = "pendente"    # só comprovável numa camada que não rodou (ex.: Gateway implantado)
INFO = "info"

VEREDITOS = ("aprovado", "reprovado", "inconclusivo")
CODIGO_SAIDA = {"aprovado": 0, "reprovado": 1, "inconclusivo": 2}


@dataclass(frozen=True)
class Achado:
    camada: str              # A | B | C1 | C2 | infra
    severidade: str          # quebra | risco | pendente | info
    codigo: str              # identificador estável (usado por divergências aceitas e pelo bench)
    interacao: str | None    # id da interação do consumidor (None = achado global)
    mensagem: str
    evidencia: str = ""      # de onde saiu a conclusão (arquivo/regra)

    @property
    def chave(self) -> str:
        return f"{self.camada}:{self.codigo}:{self.interacao or '*'}"

    def para_dict(self) -> dict:
        dados = asdict(self)
        dados["chave"] = self.chave
        return dados


@dataclass
class ResultadoCamada:
    camada: str
    executada: bool
    motivo_nao_execucao: str = ""
    duracao_s: float = 0.0
    achados: list[Achado] = field(default_factory=list)
    alcance: str = ""        # o que esta camada comprova (e o que não)
    cache: bool = False
    extras: dict = field(default_factory=dict)
