"""Redação de dado pessoal — restrição 5: nenhum dado sensível em log.

Regra: nada entra em `logging`, em `stdout` ou na trilha de auditoria sem
passar por `redigir()`. Contato vira hash (para dedupe) + máscara (para o
atendente reconhecer o lead), nunca texto puro.
"""

from __future__ import annotations

import hashlib
import os
import re

_TELEFONE = re.compile(r"(?<!\d)(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}[-\s.]?\d{4}(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_CPF = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")
_CARTAO = re.compile(r"(?<!\d)(?:\d{4}[\s.-]?){3}\d{4}(?!\d)")
_PIX_CHAVE = re.compile(r"(?i)\bchave pix[:\s]+\S+")


def redigir(texto: str) -> str:
    """Substitui dado pessoal por marcador estável. Idempotente."""
    if not texto:
        return texto
    saida = _CARTAO.sub("[CARTAO]", texto)
    saida = _CPF.sub("[CPF]", saida)
    saida = _EMAIL.sub("[EMAIL]", saida)
    saida = _TELEFONE.sub("[TELEFONE]", saida)
    saida = _PIX_CHAVE.sub("chave pix: [PIX]", saida)
    return saida


def _sal() -> str:
    return os.getenv("CHATBOT_SAL_HASH", "n7-chatbot-comercial")


def hash_contato(contato: str) -> str:
    """Hash com sal para dedupe de lead sem guardar o contato em claro."""
    bruto = (contato or "").strip().lower()
    if not bruto:
        return ""
    return hashlib.sha256(f"{_sal()}::{bruto}".encode()).hexdigest()[:32]


def mascarar_contato(contato: str) -> str:
    """Máscara legível para o atendente: 5511****7788 / th***@gmail.com."""
    bruto = (contato or "").strip()
    if not bruto:
        return ""
    if "@" in bruto:
        usuario, _, dominio = bruto.partition("@")
        visivel = usuario[:2] if len(usuario) > 2 else usuario[:1]
        return f"{visivel}***@{dominio}"
    digitos = re.sub(r"\D", "", bruto)
    if len(digitos) <= 4:
        return "*" * len(digitos)
    return f"{digitos[:4]}{'*' * (len(digitos) - 8 if len(digitos) > 8 else 2)}{digitos[-4:]}"
