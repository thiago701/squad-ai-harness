"""Detecção validada e mascaramento canônico de dados sensíveis em texto de log.

Doutrina (ver ../../references/mascaramento.md):
  * mascarar NA ORIGEM (serializer/record) — este módulo é a *rede de segurança* e o oráculo
    de teste que prova o formato "antes → depois";
  * nunca inventar: só mascara o que passa no validador (dígitos verificadores do CPF/CNPJ,
    Luhn do cartão), para não corromper números de pedido, timestamps e ids;
  * formato estável e reconhecível — o operador precisa saber que ALGO foi mascarado e de que
    tipo, sem recuperar o valor;
  * segredo (senha, token, chave) some por inteiro; dado pessoal (CPF, e-mail) preserva só o
    suficiente para suporte (regra de minimização — LGPD art. 6º III).

API:
    mascarar_texto(texto) -> str
    detectar(texto) -> list[Achado]
    mascarar_cpf / mascarar_cnpj / mascarar_pan / mascarar_email / mascarar_telefone / ...
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

# --------------------------------------------------------------------------- #
# Validadores (evitam falso positivo em sequências numéricas quaisquer)
# --------------------------------------------------------------------------- #

def _digitos(s: str) -> str:
    return re.sub(r"\D", "", s)


def cpf_valido(cpf: str) -> bool:
    d = _digitos(cpf)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        soma = sum(int(d[i]) * ((n + 1) - i) for i in range(n))
        dv = (soma * 10) % 11
        dv = 0 if dv == 10 else dv
        if dv != int(d[n]):
            return False
    return True


def cnpj_valido(cnpj: str) -> bool:
    d = _digitos(cnpj)
    if len(d) != 14 or d == d[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    for pesos, pos in ((pesos1, 12), (pesos2, 13)):
        soma = sum(int(d[i]) * p for i, p in enumerate(pesos))
        resto = soma % 11
        dv = 0 if resto < 2 else 11 - resto
        if dv != int(d[pos]):
            return False
    return True


def luhn_valido(numero: str) -> bool:
    d = _digitos(numero)
    if not (13 <= len(d) <= 19):
        return False
    total, alt = 0, False
    for ch in reversed(d):
        n = int(ch)
        if alt:
            n *= 2
            if n > 9:
                n -= 9
        total += n
        alt = not alt
    return total % 10 == 0


# --------------------------------------------------------------------------- #
# Mascaradores unitários — o FORMATO é contrato (testes o travam)
# --------------------------------------------------------------------------- #

def mascarar_cpf(cpf: str) -> str:
    """123.456.789-09 → ***.456.789-** (mantém os 6 dígitos centrais — padrão Receita)."""
    d = _digitos(cpf)
    return f"***.{d[3:6]}.{d[6:9]}-**"


def mascarar_cnpj(cnpj: str) -> str:
    """12.345.678/0001-95 → **.345.678/0001-**"""
    d = _digitos(cnpj)
    return f"**.{d[2:5]}.{d[5:8]}/{d[8:12]}-**"


def mascarar_pan(pan: str, *, manter_bin: bool = False) -> str:
    """4111 1111 1111 1111 → **** **** **** 1111  (PCI DSS 4.0 req. 3.4.1: no máximo BIN + 4 finais).

    `manter_bin=True` devolve 411111******1111 — só para quem tem necessidade de negócio
    documentada (ex.: roteamento por bandeira)."""
    d = _digitos(pan)
    if manter_bin:
        return d[:6] + "*" * (len(d) - 10) + d[-4:]
    return "**** **** **** " + d[-4:]


def mascarar_email(email: str) -> str:
    """thiago.silva@exemplo.com → t***********@exemplo.com (1º caractere + domínio)."""
    local, _, dominio = email.partition("@")
    if not dominio:
        return "****"
    return local[0] + "*" * max(3, len(local) - 1) + "@" + dominio


def mascarar_telefone(tel: str) -> str:
    """(83) 99999-1234 → (83) *****-1234"""
    d = _digitos(tel)
    pais = d.startswith("55") and len(d) in (12, 13)
    if pais:
        d = d[2:]
    ddd, final, meio = d[:2], d[-4:], "*" * (len(d) - 6)
    return f"{'+55 ' if pais else ''}({ddd}) {meio}-{final}"


def mascarar_token(valor: str, *, rotulo: str = "TOKEN") -> str:
    """eyJhbGciOi...xyz9 → [TOKEN:****xyz9] — segredo some; 4 finais permitem correlacionar."""
    cauda = valor[-4:] if len(valor) >= 12 else ""
    return f"[{rotulo}:****{cauda}]"


def mascarar_total(_: str) -> str:
    return "****"


# --------------------------------------------------------------------------- #
# Catálogo de detectores (ordem importa: do mais específico ao mais genérico)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Detector:
    nome: str                 # id curto usado nos achados
    categoria: str            # "segredo" | "pii"
    regex: re.Pattern
    mascarar: Callable[[re.Match], str]
    valido: Callable[[re.Match], bool] = lambda m: True


@dataclass(frozen=True)
class Achado:
    nome: str
    categoria: str
    inicio: int
    fim: int
    mascarado: str

    @property
    def tamanho(self) -> int:
        return self.fim - self.inicio


_VALORES_NAO_BRUTOS = {"null", "none", "true", "false", "redacted", "<redacted>", "[redacted]", "x", "xxx"}


def _valor_bruto(v: str) -> bool:
    """False quando o valor já está mascarado/placeholder — evita 'mascarar o mascarado' e falso positivo."""
    low = v.lower()
    if low in _VALORES_NAO_BRUTOS or set(v) <= {"*", "x", "X"}:
        return False
    return not v.startswith(("*", "[", "<", "${", "{{", "%(", "{"))


_CHAVES_SEGREDO = (
    r"(?:senha|password|passwd|pwd|secret|client_secret|api[_-]?key|apikey|access[_-]?key|"
    r"secret[_-]?key|private[_-]?key|auth[_-]?token|access[_-]?token|refresh[_-]?token|"
    r"id[_-]?token|token|authorization|credential[s]?|cvv|cvc)"
)
# NB: session_id/sessionId ficou FORA de propósito — em transcripts/telemetria de agentes é só
# um identificador de sessão de trabalho (não credencial). Em aplicações web continua sendo
# "nunca logar" (OWASP) — item de LEITURA do checklist (LOG-01), não detector mecânico.


def _cartao_plausivel(bruto: str) -> bool:
    """Luhn passa em ~10% de qualquer sequência — sozinho gera falso positivo em epoch-ms e ids.
    Sem separador: só 15–16 dígitos com prefixo de bandeira (3 Amex/Diners, 4 Visa, 5 MC, 6 Elo/Disc).
    Com separador (espaço/hífen em grupos): 13–19 dígitos, como impresso no plástico."""
    d = _digitos(bruto)
    if not luhn_valido(d):
        return False
    if re.search(r"[ -]", bruto):
        return 13 <= len(d) <= 19
    return len(d) in (15, 16) and d[0] in "3456"

DETECTORES: tuple[Detector, ...] = (
    # Blocos PEM inteiros
    Detector(
        "chave_privada", "segredo",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----|"
                   r"-----BEGIN [A-Z ]*PRIVATE KEY-----[^\n]*"),
        lambda m: "[CHAVE_PRIVADA_REDIGIDA]",
    ),
    # Authorization: Bearer xxx / Basic xxx
    Detector(
        "authorization_header", "segredo",
        re.compile(r"(?i)(authorization\s*[:=]\s*(?:bearer|basic|token)\s+)([A-Za-z0-9\-._~+/=]{8,})"),
        lambda m: m.group(1) + mascarar_token(m.group(2)),
    ),
    # chave=valor de segredo (senha=..., token: ..., "api_key":"...")
    Detector(
        "segredo_chave_valor", "segredo",
        re.compile(r"(?i)([\"']?\b" + _CHAVES_SEGREDO + r"\b[\"']?\s*[:=]\s*[\"']?)([^\s\"',;&)}\]]{3,})"),
        lambda m: m.group(1) + "****",
        lambda m: _valor_bruto(m.group(2)),
    ),
    # Credencial embutida em URL: scheme://user:senha@host
    Detector(
        "credencial_em_url", "segredo",
        re.compile(r"([a-z][a-z0-9+.-]*://[^/\s:@]+:)([^@\s/]+)(@)"),
        lambda m: m.group(1) + "****" + m.group(3),
        lambda m: _valor_bruto(m.group(2)),
    ),
    # JWT (3 segmentos base64url)
    Detector(
        "jwt", "segredo",
        re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
        lambda m: mascarar_token(m.group(0), rotulo="JWT"),
    ),
    # Chaves de provedores (formato público e estável — mesmas famílias do gitleaks)
    Detector(
        "aws_access_key", "segredo",
        re.compile(r"\b((?:AKIA|ASIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA)[0-9A-Z]{16})\b"),
        lambda m: m.group(1)[:4] + "*" * 12 + m.group(1)[-4:],
    ),
    Detector(
        "github_token", "segredo",
        re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})\b"),
        lambda m: mascarar_token(m.group(1), rotulo="GITHUB_TOKEN"),
    ),
    Detector(
        "slack_token", "segredo",
        re.compile(r"\b(xox[baprs]-[A-Za-z0-9-]{10,})\b"),
        lambda m: mascarar_token(m.group(1), rotulo="SLACK_TOKEN"),
    ),
    Detector(
        "openai_anthropic_key", "segredo",
        re.compile(r"\b(sk-(?:ant-)?[A-Za-z0-9_-]{20,})\b"),
        lambda m: mascarar_token(m.group(1), rotulo="API_KEY"),
    ),
    Detector(
        "google_api_key", "segredo",
        re.compile(r"\b(AIza[0-9A-Za-z_-]{35})\b"),
        lambda m: mascarar_token(m.group(1), rotulo="API_KEY"),
    ),
    Detector(
        "datadog_api_key", "segredo",
        re.compile(r"(?i)\b(dd_api_key|dd_app_key|datadog_api_key)\b\s*[:=]\s*[\"']?([a-f0-9]{32,40})\b"),
        lambda m: m.group(1) + "=****",
    ),
    # ---- dados pessoais (PII) ----
    Detector(
        "cnpj", "pii",
        re.compile(r"(?<!\d)(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})(?!\d)"),
        lambda m: mascarar_cnpj(m.group(1)),
        lambda m: cnpj_valido(m.group(1)) and ("/" in m.group(1) or "." in m.group(1) or "-" in m.group(1)),
    ),
    Detector(
        "cpf", "pii",
        re.compile(r"(?<![\d.\-/])(\d{3}\.?\d{3}\.?\d{3}-?\d{2})(?![\d\-/])"),
        lambda m: mascarar_cpf(m.group(1)),
        lambda m: cpf_valido(m.group(1)),
    ),
    Detector(
        "cartao", "pii",
        # bordas estritas: nada de letra/dígito/ponto/hífen colado (UUIDs, floats longos, hashes)
        re.compile(r"(?<![\w.-])((?:\d[ -]?){12,18}\d)(?![\w.-])"),
        lambda m: mascarar_pan(m.group(1)),
        lambda m: _cartao_plausivel(m.group(1)),
    ),
    Detector(
        "email", "pii",
        re.compile(r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b"),
        lambda m: mascarar_email(m.group(1)),
    ),
    Detector(
        "telefone_br", "pii",
        re.compile(r"(?<!\d)((?:\+55\s?)?\(\d{2}\)\s?9?\d{4}-?\d{4}|(?:\+55\s?)?\d{2}\s?9\d{4}-\d{4})(?!\d)"),
        lambda m: mascarar_telefone(m.group(1)),
    ),
)

POR_NOME = {d.nome: d for d in DETECTORES}


def detectar(texto: str, *, categorias: set[str] | None = None) -> list[Achado]:
    """Lista achados validados, sem sobreposição (o 1º detector que casar vence)."""
    ocupado: list[tuple[int, int]] = []
    achados: list[Achado] = []
    for det in DETECTORES:
        if categorias and det.categoria not in categorias:
            continue
        for m in det.regex.finditer(texto):
            ini, fim = m.start(), m.end()
            if any(not (fim <= a or ini >= b) for a, b in ocupado):
                continue
            if not det.valido(m):
                continue
            achados.append(Achado(det.nome, det.categoria, ini, fim, det.mascarar(m)))
            ocupado.append((ini, fim))
    achados.sort(key=lambda a: a.inicio)
    return achados


def mascarar_texto(texto: str, *, categorias: set[str] | None = None) -> str:
    """Devolve o texto com todos os achados substituídos pela forma mascarada."""
    saida, pos = [], 0
    for a in detectar(texto, categorias=categorias):
        saida.append(texto[pos:a.inicio])
        saida.append(a.mascarado)
        pos = a.fim
    saida.append(texto[pos:])
    return "".join(saida)


def neutralizar_crlf(texto: str) -> str:
    """Anti log-forging (CWE-117): quebra de linha vinda de entrada externa vira literal visível."""
    return texto.replace("\r", "\\r").replace("\n", "\\n")


def sanitizar_para_log(texto: str) -> str:
    """Uso típico na borda: mascara dados sensíveis E neutraliza CRLF em um passo."""
    return neutralizar_crlf(mascarar_texto(texto))
