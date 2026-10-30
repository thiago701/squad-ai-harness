"""Contratos tipados e máquina de estados do pipeline — módulo ⑫ (doc evolucao-dsa 01)."""

from .validator import (  # noqa: F401
    ESTADOS,
    FERRAMENTAS_DESTRUTIVAS,
    LIMITE_TAMANHO_CHARS,
    REQUIRED_FIELDS,
    SCHEMA_VERSAO_ATUAL,
    TRANSICOES,
    TRANSICOES_TRIVIAL,
    TIPOS_ARTEFATO,
    VereditoArtefato,
    VereditoEscalonamento,
    VereditoPlano,
    VereditoTransicao,
    validar_artefato,
    validar_escalonamento,
    validar_plano,
    validar_transicao,
)

__all__ = [
    "ESTADOS", "FERRAMENTAS_DESTRUTIVAS", "LIMITE_TAMANHO_CHARS", "REQUIRED_FIELDS",
    "SCHEMA_VERSAO_ATUAL", "TRANSICOES", "TRANSICOES_TRIVIAL", "TIPOS_ARTEFATO",
    "VereditoArtefato", "VereditoEscalonamento", "VereditoPlano", "VereditoTransicao",
    "validar_artefato", "validar_escalonamento", "validar_plano", "validar_transicao",
]
