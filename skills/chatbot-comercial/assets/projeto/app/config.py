"""Configuração do chatbot — um objeto, lido do ambiente, sem framework.

Teto de custo é configuração de primeira classe (restrição 3): existe teto por
conversa e teto mensal por tenant. Estourar o teto degrada para modo extrativo,
não derruba o atendimento.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _f(nome: str, padrao: float) -> float:
    bruto = os.getenv(nome)
    if bruto is None or not bruto.strip():
        return padrao
    return float(bruto)


def _i(nome: str, padrao: int) -> int:
    bruto = os.getenv(nome)
    if bruto is None or not bruto.strip():
        return padrao
    return int(bruto)


def _b(nome: str, padrao: bool) -> bool:
    bruto = os.getenv(nome)
    if bruto is None or not bruto.strip():
        return padrao
    return bruto.strip().lower() in {"1", "true", "sim", "yes", "on"}


@dataclass(frozen=True)
class Config:
    tenant: str = "demo"
    vertical: str = "pousada"
    estabelecimento: str = "Pousada Serra Viva"

    raiz: Path = RAIZ
    banco: Path = RAIZ / "var" / "chatbot.db"
    dados: Path = RAIZ / "dados"
    verticais: Path = RAIZ / "verticais"
    golden: Path = RAIZ / "golden"
    versoes: Path = RAIZ / "var" / "versoes"

    host: str = "0.0.0.0"
    porta: int = 8080

    canais: tuple[str, ...] = ("whatsapp", "web")
    whatsapp_app_secret: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_verificar_assinatura: bool = True

    # M2 — retrieval
    top_k: int = 3
    score_minimo: float = 0.30

    # Restrição 3 — custo observável e com teto
    teto_custo_conversa_brl: float = 0.50
    teto_custo_mes_brl: float = 150.0

    # Restrição 5 / M5 — LGPD
    retencao_dias: int = 180
    exigir_consentimento: bool = False

    # llm-gateway
    gateway_modelo_padrao: str = "rapido"
    gateway_timeout_s: float = 8.0
    gateway_tentativas: int = 2

    painel_token: str = field(default="", repr=False)

    @staticmethod
    def do_ambiente() -> Config:
        raiz = Path(os.getenv("CHATBOT_RAIZ", str(RAIZ))).resolve()
        canais = tuple(
            c.strip()
            for c in os.getenv("CHATBOT_CANAIS", "whatsapp,web").split(",")
            if c.strip()
        )
        return Config(
            tenant=os.getenv("CHATBOT_TENANT", "demo"),
            vertical=os.getenv("CHATBOT_VERTICAL", "pousada"),
            estabelecimento=os.getenv("CHATBOT_ESTABELECIMENTO", "Pousada Serra Viva"),
            raiz=raiz,
            banco=Path(os.getenv("CHATBOT_BANCO", str(raiz / "var" / "chatbot.db"))),
            dados=raiz / "dados",
            verticais=raiz / "verticais",
            golden=raiz / "golden",
            versoes=raiz / "var" / "versoes",
            host=os.getenv("CHATBOT_HOST", "0.0.0.0"),
            porta=_i("CHATBOT_PORTA", 8080),
            canais=canais,
            whatsapp_app_secret=os.getenv("WHATSAPP_APP_SECRET", ""),
            whatsapp_verify_token=os.getenv("WHATSAPP_VERIFY_TOKEN", ""),
            whatsapp_verificar_assinatura=_b("WHATSAPP_VERIFICAR_ASSINATURA", True),
            top_k=_i("CHATBOT_TOP_K", 3),
            score_minimo=_f("CHATBOT_SCORE_MINIMO", 0.30),
            teto_custo_conversa_brl=_f("CHATBOT_TETO_CONVERSA_BRL", 0.50),
            teto_custo_mes_brl=_f("CHATBOT_TETO_MES_BRL", 150.0),
            retencao_dias=_i("CHATBOT_RETENCAO_DIAS", 180),
            exigir_consentimento=_b("CHATBOT_EXIGIR_CONSENTIMENTO", False),
            gateway_modelo_padrao=os.getenv("LLM_GATEWAY_MODELO", "rapido"),
            gateway_timeout_s=_f("LLM_GATEWAY_TIMEOUT_S", 8.0),
            gateway_tentativas=_i("LLM_GATEWAY_TENTATIVAS", 2),
            painel_token=os.getenv("PAINEL_TOKEN", ""),
        )

    def preparar_diretorios(self) -> None:
        self.banco.parent.mkdir(parents=True, exist_ok=True)
        self.versoes.mkdir(parents=True, exist_ok=True)

    @property
    def pack_do_vertical(self) -> Path:
        return self.verticais / f"{self.vertical}.json"

    @property
    def dados_do_vertical(self) -> Path:
        return self.dados / self.vertical

    @property
    def golden_do_vertical(self) -> Path:
        return self.golden / f"{self.vertical}.json"
