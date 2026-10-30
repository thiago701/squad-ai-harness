"""Varredura determinística de logs — código, configuração e artefatos de log.

Entrada: raiz do projeto + (opcional) lista de arquivos ou `--diff <ref>`.
Saída:   achados LOG-xx com trecho JÁ MASCARADO (o linter nunca reimprime o segredo que achou),
         relatório JSON em --saida, código de saída 0 aprovado · 1 reprovado · 2 inconclusivo.

Heurísticas são declaradas e testadas (tests/test_logs_observabilidade.py); supressão só com
motivo: `// log-ok: <motivo>` ou `# log-ok: <motivo>` na linha ou na anterior.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import mascara
from .regras import BLOQ, NEC, POR_ID, REGRAS, SUG

# --------------------------------------------------------------------------- #
# Classificação de arquivos
# --------------------------------------------------------------------------- #
EXT_LINGUAGEM = {
    ".java": "java", ".kt": "kotlin", ".kts": "kotlin", ".py": "python",
    ".ts": "ts", ".tsx": "ts", ".js": "ts", ".mjs": "ts", ".cjs": "ts",
}
EXT_ARTEFATO = {".log", ".jsonl", ".ndjson"}
NOMES_CONFIG_APP = re.compile(r"^(application|bootstrap)[\w.-]*\.(ya?ml|properties)$", re.I)
NOMES_CONFIG_LOG = re.compile(r"^(logback|log4j2?)[\w.-]*\.xml$", re.I)
DIRS_IGNORADOS = {
    ".git", "node_modules", ".venv", "venv", "target", "build", "dist", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "_local-artifacts", ".cache", "graphify-out",
    ".aws-sam", ".idea", ".gradle", "out", "coverage", "site-packages",
}
PROFILES_LOCAIS = re.compile(r"(local|dev|test|h2)", re.I)
TAMANHO_MAX_ARTEFATO = 5 * 1024 * 1024


def classificar(caminho: Path) -> str | None:
    nome = caminho.name
    ext = caminho.suffix.lower()
    if ext in EXT_LINGUAGEM:
        return EXT_LINGUAGEM[ext]
    if NOMES_CONFIG_APP.match(nome) or NOMES_CONFIG_LOG.match(nome):
        return "config"
    if ext in EXT_ARTEFATO or (ext == ".txt" and "log" in nome.lower()):
        return "artefato"
    return None


def _eh_teste(rel: str) -> bool:
    r = rel.replace("\\", "/").lower()
    return "/test/" in r or r.startswith("test") or "/tests/" in r or r.startswith("tests/") \
        or "_test." in r or ".test." in r or ".spec." in r or "/test_" in r


# --------------------------------------------------------------------------- #
# Modelo de achado
# --------------------------------------------------------------------------- #
@dataclass
class Achado:
    regra: str
    severidade: str
    arquivo: str
    linha: int
    trecho: str              # sempre mascarado
    detalhe: str
    suprimido: bool = False
    motivo: str = ""

    def chave(self) -> tuple:
        return (self.regra, self.arquivo, self.linha)


@dataclass
class Relatorio:
    perfil: str
    raiz: str
    arquivos_analisados: int = 0
    arquivos_pulados: list[str] = field(default_factory=list)
    achados: list[Achado] = field(default_factory=list)
    notas: list[str] = field(default_factory=list)
    duracao_s: float = 0.0

    def ativos(self, severidade: str | None = None) -> list[Achado]:
        return [a for a in self.achados if not a.suprimido and (severidade is None or a.severidade == severidade)]

    def veredito(self, falhar_em_necessario: bool = False) -> tuple[int, str]:
        if self.arquivos_analisados == 0:
            return 2, "INCONCLUSIVO"
        if self.ativos(BLOQ):
            return 1, "REPROVADO"
        if falhar_em_necessario and self.ativos(NEC):
            return 1, "REPROVADO"
        return 0, "APROVADO"


# --------------------------------------------------------------------------- #
# Utilitários de texto
# --------------------------------------------------------------------------- #
_RE_SUPRESSAO = re.compile(r"(?://|#|<!--|/\*|\*)\s*log-ok:\s*(.+?)\s*(?:-->|\*/)?\s*$")


def _supressao(linhas: list[str], idx: int) -> str | None:
    for j in (idx, idx - 1):
        if 0 <= j < len(linhas):
            m = _RE_SUPRESSAO.search(linhas[j])
            if m and len(m.group(1).strip()) >= 5:
                return m.group(1).strip()
    return None


def _trecho(linha: str, limite: int = 160) -> str:
    t = mascara.mascarar_texto(linha.strip())
    return t if len(t) <= limite else t[:limite - 1] + "…"


def _palavras(ident: str) -> list[str]:
    """accessToken → [access, token]; cpf_cliente → [cpf, cliente]; DD_API_KEY → [dd, api, key]."""
    partes = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", ident).replace("-", "_").replace(".", "_").lower().split("_")
    return [p for p in partes if p]


# chaves de segredo: a ÚLTIMA palavra do identificador decide (userPassword sim; passwordHash não)
_SEGREDO_ULTIMA = {
    "senha", "password", "passwd", "pwd", "secret", "token", "jwt", "bearer", "cookie",
    "authorization", "credential", "credentials", "cvv", "cvc", "apikey",
}
_SEGREDO_PARES = {("api", "key"), ("access", "key"), ("secret", "key"), ("private", "key"),
                  ("signing", "key"), ("encryption", "key"), ("client", "secret")}
# palavra que, em QUALQUER posição, indica que o valor já não é o dado bruto
_NEUTRAS_QUALQUER = {
    "mascarado", "mascarar", "mascara", "masked", "mask", "hash", "hashed", "parcial", "partial",
    "redacted", "redact", "redigido", "redigir", "ofuscado", "ofuscar", "anonimizado", "anonymized",
    "presente", "present", "exists", "expira", "expiry", "expires", "ttl", "valido", "valid",
    "invalido", "invalid", "enviado", "sent", "count", "total", "size", "length", "tamanho",
    "qtd", "quantidade", "sufixo", "suffix", "ultimos", "last4",
}
# palavra que, só como ÚLTIMA, indica objeto auxiliar e não o segredo (tokenService, cookieName)
_NEUTRAS_ULTIMA = {
    "service", "sender", "client", "template", "provider", "manager", "repository", "config",
    "configuration", "header", "headers", "url", "path", "prefix", "suffix", "name", "nome",
    "type", "tipo", "id", "ids", "kid", "alg", "usage", "limit", "budget", "cost", "custo",
    "window", "rate", "factory", "resolver", "validator", "filter", "store", "cache", "error",
    "erro", "exception", "status", "enabled", "required", "format", "formato", "mode", "modo",
}
_PII_QUALQUER = {
    "cpf", "cnpj", "cartao", "pan", "email", "telefone", "phone", "celular",
    "endereco", "address", "nascimento", "birthdate", "rg", "passaporte", "passport",
    "cep", "zipcode", "salario", "salary", "renda",
}
# "card" sozinho é ambíguo (model card, card de kanban): só conta em par com número/portador/crédito
_PII_PARES = {("card", "number"), ("credit", "card"), ("debit", "card"), ("card", "holder"),
              ("cardholder", "name"), ("numero", "cartao"), ("card", "pan"), ("payment", "card")}
_PII_PARES_EXCECAO = {("ip", "address"), ("host", "address"), ("server", "address"),
                      ("bind", "address"), ("mac", "address"), ("contract", "address"),
                      ("email", "service"), ("email", "sender"), ("email", "template"),
                      ("email", "client"), ("cartao", "token"), ("cartao", "tipo"), ("cartao", "bandeira")}

_RE_CHAVE_PLACEHOLDER = re.compile(
    r"(?i)(?<![\w.])(senha|password|passwd|pwd|secret|client[_-]?secret|api[_-]?key|apikey|"
    r"access[_-]?key|secret[_-]?key|private[_-]?key|auth[_-]?token|access[_-]?token|"
    r"refresh[_-]?token|id[_-]?token|token|jwt|bearer|cookie|authorization|"
    r"credentials?|cvv|cvc)(?![\w.])\s*[=:]\s*(\{|%s|%r|%d|\$\{|\$\w|\"\s*\+|'\s*\+|\+)")
_RE_PII_PLACEHOLDER = re.compile(
    r"(?i)(?<![\w.])(cpf|cnpj|cart[aã]o|card[_-]?number|numero[_-]?cartao|pan|e-?mail|telefone|"
    r"phone|celular|endere[cç]o|address|data[_-]?nascimento|birth[_-]?date|rg|passaporte|passport)"
    r"(?![\w.])\s*[=:]\s*(\{|%s|%r|\$\{|\$\w|\"\s*\+|'\s*\+|\+)")
# chave de dicionário/objeto estruturado: extra={"cpf": x}, {"password": y} — a chave entre aspas decide
_RE_CHAVE_DICT_SEGREDO = re.compile(
    r"(?i)[\"'](senha|password|passwd|pwd|secret|client[_-]?secret|api[_-]?key|apikey|access[_-]?key|"
    r"secret[_-]?key|private[_-]?key|auth[_-]?token|access[_-]?token|refresh[_-]?token|id[_-]?token|"
    r"token|jwt|bearer|cookie|authorization|credentials?|cvv|cvc)[\"']\s*:\s*(?![\"']\*{2,})")
_RE_CHAVE_DICT_PII = re.compile(
    r"(?i)[\"'](cpf|cnpj|cart[aã]o|card[_-]?number|numero[_-]?cartao|pan|e-?mail|telefone|phone|celular|"
    r"endere[cç]o|address|data[_-]?nascimento|birth[_-]?date|rg|passaporte|passport)[\"']\s*:\s*(?![\"']\*{2,})")
_RE_GETTER_SEGREDO = re.compile(
    r"\.get(?:Password|Senha|Secret|Token|AccessToken|RefreshToken|IdToken|ApiKey|Authorization|"
    r"Cvv|PrivateKey|Credentials?|ClientSecret|Cookie)\(\)")
_RE_GETTER_PII = re.compile(
    r"\.get(?:Cpf|Cnpj|Cartao|CardNumber|NumeroCartao|Pan|Email|Telefone|Phone|Celular|Endereco|"
    r"Address|DataNascimento|BirthDate|Rg|Passaporte|Passport)\(\)")
_RE_WRAPPER = re.compile(r"(?i)\b(?:mascar\w*|mask\w*|redact\w*|redig\w*|ofusc\w*|anonim\w*|hash\w*|"
                         r"sha\d*\w*|digest\w*|sanitiz\w*|scrub\w*|ultimos\w*|last4|lastFour|truncat\w*)"
                         r"(?:\.(\w+))?\s*\(")
_RE_AMBIENTE = re.compile(
    r"System\.getenv\(\s*\)|System\.getProperties\(\)|\bos\.environ\b(?!\s*(?:\[|\.get\b))|"
    r"dict\(os\.environ\)|environ\.items\(\)|process\.env\b(?!\s*[\[.])|JSON\.stringify\(\s*process\.env\s*\)|"
    r"(?<![\w.])getenv\(\s*\)")
_RE_REQUEST_INTEIRO = re.compile(
    r"getHeaderNames\(\)|getHeaders\(\)|getBody\(\)|(?<!len\()\brequest\.(?:data|json|body)\b(?!\s*(?:\.get\(|\[|\.keys|\.size|\.length))|"
    r"HttpServletRequest|getInputStream\(\)|"
    r"(?:[,(]|\{|\+)\s*(?:self\.|this\.|req\.|request\.|response\.|event\.)?"
    r"(?:headers|body|payload|requestBody|rawBody|request_body|raw_body)\s*(?:[,)]|\}|\+|$)")
_RE_EVENTO = re.compile(r"^[a-z][a-z0-9]*(?:[._][a-z0-9]+)+(?:\s|$|[=:])")

_CHAMADA_JAVA = re.compile(r"\b(?:log|logger|LOG|LOGGER|_log|_logger|slf4j)\.(trace|debug|info|warn|error|fatal)\s*\(")
_CHAMADA_PY = re.compile(r"\b(?:log|logger|logging|_log|_logger|LOG|LOGGER|self\.log|self\.logger|cls\.logger)"
                         r"\.(debug|info|warning|warn|error|critical|exception)\s*\(")
_PRINT_PY = re.compile(r"(?<![\w.])print\s*\(")
_CHAMADA_TS = re.compile(r"\b(?:console|log|logger|LOG|this\.logger|this\.log)\.(log|trace|debug|info|warn|error|fatal)\s*\(")
_PRINT_JAVA = re.compile(r"System\.(out|err)\.print(?:ln|f)?\s*\(|\.printStackTrace\s*\(")


def _coletar_chamada(linhas: list[str], i: int, inicio: int, max_linhas: int = 8) -> tuple[str, int]:
    """Texto da chamada a partir do '(' em linhas[i][inicio:] até fechar parênteses (ou max_linhas)."""
    buf, prof, aberto = [], 0, False
    for k in range(i, min(len(linhas), i + max_linhas)):
        seg = linhas[k][inicio:] if k == i else linhas[k]
        for ch in seg:
            if ch == "(":
                prof += 1
                aberto = True
            elif ch == ")":
                prof -= 1
        buf.append(seg.rstrip("\n"))
        if aberto and prof <= 0:
            return " ".join(s.strip() for s in buf), k
    return " ".join(s.strip() for s in buf), min(len(linhas) - 1, i + max_linhas - 1)


def _identificadores(texto: str) -> list[str]:
    """Identificadores fora de literais + os interpolados dentro deles ({cpf}, ${token}, $senha)."""
    interpolados = []
    for m in re.finditer(r"\$\{\s*([A-Za-z_][\w.]*)|\{\s*([A-Za-z_][\w.]*)|\$([A-Za-z_]\w*)", texto):
        ident = m.group(1) or m.group(2) or m.group(3)
        interpolados.append(ident.split(".")[-1])
    sem_str = re.sub(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`", '""', texto)
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*", sem_str) + interpolados


def _ident_segredo(ident: str) -> bool:
    p = _palavras(ident)
    if not p or _NEUTRAS_QUALQUER.intersection(p) or p[-1] in _NEUTRAS_ULTIMA:
        return False
    if len(p) >= 2 and (p[-2], p[-1]) in _SEGREDO_PARES:
        return True
    return p[-1] in _SEGREDO_ULTIMA


def _ident_pii(ident: str) -> bool:
    p = _palavras(ident)
    if not p or _NEUTRAS_QUALQUER.intersection(p) or p[-1] in _NEUTRAS_ULTIMA - {"nome", "name"}:
        return False
    pares = set(zip(p, p[1:]))
    if pares & _PII_PARES_EXCECAO:
        return False
    return bool(_PII_QUALQUER.intersection(p)) or bool(pares & _PII_PARES)


def _args_balanceados(texto: str, pos_abre: int) -> str:
    prof = 0
    for k in range(pos_abre, len(texto)):
        if texto[k] == "(":
            prof += 1
        elif texto[k] == ")":
            prof -= 1
            if prof == 0:
                return texto[pos_abre + 1:k]
    return texto[pos_abre + 1:]


def _mascarado_no_texto(chamada: str, ident: str | None = None) -> bool:
    """True se a chamada já passa o dado por um invólucro de máscara (mascarar_cpf(x), Mascara.pan(y))."""
    if "****" in chamada:
        return True
    for m in _RE_WRAPPER.finditer(chamada):
        if ident is None:
            return True
        if ident.lower() in _palavras(m.group(0).rstrip("( \t")):   # Mascara.cpf( / mascarar_cpf(
            return True
        args = _args_balanceados(chamada, m.end() - 1)
        if re.search(r"\b" + re.escape(ident) + r"\b", args):
            return True
    return False


def _primeiro_literal(chamada: str) -> str | None:
    m = re.search(r"[fFrRbB]?\"((?:\\.|[^\"\\])*)\"|[fFrRbB]?'((?:\\.|[^'\\])*)'", chamada)
    if not m:
        return None
    return m.group(1) if m.group(1) is not None else m.group(2)


# --------------------------------------------------------------------------- #
# Analisadores
# --------------------------------------------------------------------------- #
def analisar_codigo(rel: str, texto: str, lang: str, perfil: str) -> list[Achado]:
    linhas = texto.splitlines()
    achados: list[Achado] = []
    teste = _eh_teste(rel)

    def add(regra: str, i: int, detalhe: str, linha_txt: str | None = None):
        r = POR_ID[regra]
        severidade = r.severidade
        if teste and regra in ("LOG-01", "LOG-02", "LOG-03"):
            # fixture de teste com segredo/PII em log é material didático (ex.: caso Veracode CWE-532),
            # não caminho de produção: fora do gate de push; sugestão no review.
            if perfil != "completo":
                return
            severidade = SUG
            detalhe = "(arquivo de teste) " + detalhe
        a = Achado(regra, severidade, rel, i + 1, _trecho(linha_txt if linha_txt is not None else linhas[i]), detalhe)
        motivo = _supressao(linhas, i)
        if motivo:
            a.suprimido, a.motivo = True, motivo
        if a.chave() not in {x.chave() for x in achados}:
            achados.append(a)

    chamada_re = {"java": _CHAMADA_JAVA, "kotlin": _CHAMADA_JAVA, "python": _CHAMADA_PY, "ts": _CHAMADA_TS}[lang]
    i = 0
    while i < len(linhas):
        linha = linhas[i]
        # LOG-10 — print/printStackTrace (Java/Kotlin, fora de teste, perfil completo)
        if lang in ("java", "kotlin") and perfil == "completo" and not teste and _PRINT_JAVA.search(linha):
            add("LOG-10", i, "saída direta em stdout/stderr ou printStackTrace em vez de logger")
        candidatos = [(m.start(), m.group(1)) for m in chamada_re.finditer(linha)]
        if lang == "python":
            candidatos += [(m.start(), "print") for m in _PRINT_PY.finditer(linha)]
        if not candidatos:
            i += 1
            continue
        ultimo_fim = i
        for ini, nivel in candidatos:
            chamada, fim = _coletar_chamada(linhas, i, ini)
            ultimo_fim = max(ultimo_fim, fim)
            _avaliar_chamada(add, i, chamada, nivel, lang, perfil, teste)
        i = ultimo_fim + 1
    return achados


def _avaliar_chamada(add, i: int, chamada: str, nivel: str, lang: str, perfil: str, teste: bool) -> None:
    idents = _identificadores(chamada)
    # ---- LOG-01 segredo ----
    vaz_seg = []
    if _RE_CHAVE_PLACEHOLDER.search(chamada) and not _mascarado_no_texto(chamada):
        vaz_seg.append("chave de segredo seguida de placeholder/valor na mensagem")
    for ident in idents:
        if _ident_segredo(ident) and not _mascarado_no_texto(chamada, ident):
            vaz_seg.append(f"argumento `{ident}`")
    for m in _RE_CHAVE_DICT_SEGREDO.finditer(chamada):
        if not _mascarado_no_texto(chamada[m.start():], m.group(1)):
            vaz_seg.append(f"chave estruturada `{m.group(1)}`")
    if _RE_GETTER_SEGREDO.search(chamada) and not _mascarado_no_texto(chamada):
        vaz_seg.append("getter de segredo")
    if vaz_seg:
        add("LOG-01", i, "; ".join(dict.fromkeys(vaz_seg)), chamada)
    # ---- LOG-02 PII ----
    vaz_pii = []
    if _RE_PII_PLACEHOLDER.search(chamada) and not _mascarado_no_texto(chamada):
        vaz_pii.append("chave de dado pessoal seguida de placeholder/valor")
    for ident in idents:
        if _ident_pii(ident) and not _mascarado_no_texto(chamada, ident):
            vaz_pii.append(f"argumento `{ident}`")
    for m in _RE_CHAVE_DICT_PII.finditer(chamada):
        if not _mascarado_no_texto(chamada[m.start():], m.group(1)):
            vaz_pii.append(f"chave estruturada `{m.group(1)}`")
    if _RE_GETTER_PII.search(chamada) and not _mascarado_no_texto(chamada):
        vaz_pii.append("getter de dado pessoal")
    if vaz_pii:
        add("LOG-02", i, "; ".join(dict.fromkeys(vaz_pii)), chamada)
    # ---- LOG-03 ambiente inteiro ----
    if _RE_AMBIENTE.search(chamada):
        add("LOG-03", i, "ambiente/propriedades do processo inteiros na saída de log", chamada)
    if perfil != "completo":
        return
    # ---- LOG-13 request inteiro ----
    if _RE_REQUEST_INTEIRO.search(chamada):
        add("LOG-13", i, "request/headers/body/payload inteiro — logue campos escolhidos", chamada)
    # ---- LOG-12 concatenação / f-string ----
    if lang in ("java", "kotlin"):
        if re.search(r"\"\s*\+\s*[A-Za-z_(]|[A-Za-z_)\]]\s*\+\s*\"", chamada):
            add("LOG-12", i, "concatenação de string dentro da chamada — use placeholders `{}`", chamada)
    elif lang == "python" and nivel != "print":
        corpo = chamada[chamada.find("(") + 1:]
        if re.match(r"\s*[fF][\"']", corpo) or re.search(r"[\"']\s*%\s*[\w(]", corpo) or re.search(r"[\"']\s*\.format\(", corpo):
            add("LOG-12", i, "f-string/%/format dentro da chamada — use `%s` com argumentos (avaliação preguiçosa)", chamada)
    elif lang == "ts":
        if re.search(r"`[^`]*\$\{[^}]*(?:password|senha|token|secret|cpf|email)", chamada, re.I):
            pass  # já coberto por LOG-01/02 via placeholder
    # ---- LOG-11 exceção sem stack ----
    if nivel in ("error", "warn", "warning", "critical", "fatal"):
        if lang in ("java", "kotlin") and ".getMessage()" in chamada and not re.search(r",\s*[A-Za-z_]\w*\s*\)\s*;?\s*$", chamada):
            add("LOG-11", i, "`getMessage()` sem a exceção como último argumento — stack trace perdido", chamada)
        if lang == "python" and nivel != "exception" and "exc_info" not in chamada \
                and re.search(r"str\(\s*(?:e|ex|exc|err|error|exception)\s*\)|\{\s*(?:e|ex|exc|err|error|exception)\s*\}|%\s*(?:e|ex|exc|err)\b|,\s*(?:e|ex|exc|err|error)\s*\)", chamada):
            add("LOG-11", i, "exceção logada só pela mensagem — use `logger.exception(...)` ou `exc_info=True`", chamada)
    # ---- LOG-14 evento nomeado (sugestão) ----
    if nivel not in ("print", "trace", "debug") and not teste:
        lit = _primeiro_literal(chamada)
        if lit and len(lit.split()) >= 4 and not _RE_EVENTO.match(lit) and "=" not in lit:
            add("LOG-14", i, "mensagem em prosa — comece pelo evento `dominio.entidade.acao` + chave=valor", chamada)


_RE_CFG_PERIGOSA = (
    (re.compile(r"(?i)(org\.apache\.(?:http|hc\.client5\.http)\.wire|reactor\.netty\.http\.client|org\.springframework\.web\.reactive\.function\.client\.ExchangeFunctions|org\.springframework\.security|org\.hibernate\.orm\.jdbc\.bind|org\.hibernate\.type\.descriptor\.sql|okhttp3\.logging|org\.apache\.http\.headers|httpclient\.wire)\s*[:=]\s*[\"']?(debug|trace)"),
     "logger de wire/segurança/bind em DEBUG|TRACE expõe Authorization, cookies e parâmetros"),
    (re.compile(r"(?i)log-request-details\s*[:=]\s*[\"']?true"), "spring.mvc.log-request-details=true loga headers e corpo"),
    (re.compile(r"(?i)show-sql\s*[:=]\s*[\"']?true"), "show-sql=true em perfil não-local"),
    (re.compile(r"(?i)loggerLevel\s*[:=]\s*[\"']?(full|headers)"), "Feign loggerLevel FULL/HEADERS expõe headers de autenticação"),
    (re.compile(r"(?i)^\s*(?:logging\.level\.)?root\s*[:=]\s*[\"']?(debug|trace)", re.M), "root em DEBUG|TRACE fora de perfil local"),
)


def analisar_config(rel: str, texto: str, perfil: str) -> list[Achado]:
    achados: list[Achado] = []
    nome = Path(rel).name
    linhas = texto.splitlines()

    def add(regra: str, i: int, detalhe: str):
        r = POR_ID[regra]
        a = Achado(regra, r.severidade, rel, i + 1, _trecho(linhas[i] if 0 <= i < len(linhas) else ""), detalhe)
        motivo = _supressao(linhas, i)
        if motivo:
            a.suprimido, a.motivo = True, motivo
        achados.append(a)

    if NOMES_CONFIG_APP.match(nome):
        # arquivo inteiro de profile local/dev/test → fora do escopo
        if PROFILES_LOCAIS.search(nome.replace("application", "").replace("bootstrap", "")):
            return achados
        # segmentos YAML multi-documento: pula os que ativam profile local
        segmentos, atual, base = [], [], 0
        for idx, l in enumerate(linhas):
            if l.strip() == "---":
                segmentos.append((base, atual))
                atual, base = [], idx + 1
            else:
                atual.append(l)
        segmentos.append((base, atual))
        for base, seg in segmentos:
            bloco = "\n".join(seg)
            if re.search(r"on-profile\s*:\s*[\"']?\[?\s*(local|dev|test|h2)", bloco, re.I):
                continue
            for rx, detalhe in _RE_CFG_PERIGOSA:
                for m in rx.finditer(bloco):
                    li = base + bloco[:m.start()].count("\n")
                    add("LOG-06", li, detalhe)
        return achados

    if NOMES_CONFIG_LOG.match(nome) and perfil == "completo":
        efetivo = re.sub(r"<!--.*?-->", "", texto, flags=re.S)   # comentário não configura nada
        json_ok = re.search(r"JsonEncoder|LogstashEncoder|JsonTemplateLayout|JsonLayout|JSONLayout|EcsEncoder|StructuredLogEncoder", efetivo)
        if not json_ok:
            add("LOG-20", 0, "nenhum encoder/layout JSON — saída em texto livre")
            if re.search(r"%(?:msg|m\b|message)", efetivo) and "%replace" not in efetivo:
                add("LOG-21", 0, "PatternLayout com %msg sem %replace de CRLF (log forging)")
        if not re.search(r"includeMdcKeyName|traceId|trace_id|dd\.trace_id|%X\{|includeMdc|correlation", efetivo, re.I):
            add("LOG-22", 0, "sem campos de correlação (trace_id/span_id/correlation_id) no encoder")
    return achados


def analisar_artefato(rel: str, texto: str) -> list[Achado]:
    achados: list[Achado] = []
    linhas = texto.splitlines()
    for i, l in enumerate(linhas):
        for a in mascara.detectar(l):
            regra = "LOG-04" if a.categoria == "segredo" else "LOG-05"
            ach = Achado(regra, POR_ID[regra].severidade, rel, i + 1, _trecho(l),
                         f"{a.nome} em artefato de log (mascarado aqui como `{a.mascarado}`)")
            motivo = _supressao(linhas, i)
            if motivo:
                ach.suprimido, ach.motivo = True, motivo
            achados.append(ach)
            if len(achados) >= 200:
                return achados
    return achados


# --------------------------------------------------------------------------- #
# Orquestração
# --------------------------------------------------------------------------- #
def _arquivos_diff(raiz: Path, ref: str) -> list[Path]:
    saida = subprocess.run(["git", "diff", "--name-only", "--diff-filter=ACMR", ref],
                           cwd=raiz, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if saida.returncode != 0:
        raise RuntimeError(f"git diff falhou: {saida.stderr.strip()}")
    out = [raiz / p for p in saida.stdout.splitlines() if p.strip()]
    nao_rastreados = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"],
                                    cwd=raiz, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if nao_rastreados.returncode == 0:
        out += [raiz / p for p in nao_rastreados.stdout.splitlines() if p.strip()]
    return out


def _ignorado(rel: str, ignorar: list[str]) -> bool:
    rel = rel.replace("\\", "/")
    partes = rel.split("/")
    if any(p in DIRS_IGNORADOS for p in partes[:-1]):
        return True
    return any(fnmatch.fnmatch(rel, pad) or fnmatch.fnmatch(rel, pad.rstrip("/*") + "/*") for pad in ignorar)


def _dir_ignorado(rel_dir: str, ignorar: list[str]) -> bool:
    rel_dir = rel_dir.replace("\\", "/")
    return any(fnmatch.fnmatch(rel_dir, pad.rstrip("/*")) or fnmatch.fnmatch(rel_dir + "/x", pad) for pad in ignorar)


def _arquivos_git(raiz: Path) -> list[Path] | None:
    """Rastreados + não-rastreados-não-ignorados: mais rápido que os.walk em volumes montados e já
    exclui .venv/node_modules/target pelo .gitignore do próprio projeto."""
    if not (raiz / ".git").exists():
        return None
    try:
        saida = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                               cwd=raiz, capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if saida.returncode != 0:
        return None
    nomes = [n.decode("utf-8", "replace") for n in saida.stdout.split(b"\0") if n]
    return [raiz / n for n in nomes]


def _iterar(raiz: Path, ignorar: list[str]):
    via_git = _arquivos_git(raiz)
    if via_git is not None:
        for p in via_git:
            rel = os.path.relpath(p, raiz)
            if not _ignorado(rel, ignorar):
                yield p
        return
    for atual, dirs, files in os.walk(raiz):
        rel_atual = os.path.relpath(atual, raiz)
        dirs[:] = [d for d in dirs
                   if (d not in DIRS_IGNORADOS and not d.startswith(".") or d == ".github")
                   and not _dir_ignorado(("" if rel_atual == "." else rel_atual + "/") + d, ignorar)]
        for f in files:
            p = Path(atual) / f
            rel = os.path.relpath(p, raiz)
            if _ignorado(rel, ignorar):
                continue
            yield p


def executar(raiz: Path, *, arquivos: list[Path] | None = None, diff: str | None = None,
             perfil: str = "segredos", ignorar: list[str] | None = None) -> Relatorio:
    t0 = time.perf_counter()
    raiz = raiz.resolve()
    ignorar = list(ignorar or [])
    rel_ = Relatorio(perfil=perfil, raiz=str(raiz))
    if diff:
        try:
            arquivos = _arquivos_diff(raiz, diff)
        except RuntimeError as e:
            rel_.notas.append(str(e))
            return rel_
    candidatos = arquivos if arquivos is not None else list(_iterar(raiz, ignorar))
    for p in candidatos:
        p = Path(p)
        if not p.is_absolute():
            p = raiz / p
        if not p.is_file():
            continue
        rel = os.path.relpath(p, raiz).replace("\\", "/")
        if arquivos is not None and _ignorado(rel, ignorar):
            continue
        tipo = classificar(p)
        if tipo is None:
            continue
        try:
            if tipo == "artefato" and p.stat().st_size > TAMANHO_MAX_ARTEFATO:
                rel_.arquivos_pulados.append(f"{rel} (artefato > 5 MB — não varrido; NÃO conta como verificado)")
                continue
            texto = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            rel_.arquivos_pulados.append(f"{rel} ({e.__class__.__name__})")
            continue
        if "\x00" in texto[:4096]:
            continue
        rel_.arquivos_analisados += 1
        if tipo == "config":
            rel_.achados += analisar_config(rel, texto, perfil)
        elif tipo == "artefato":
            rel_.achados += analisar_artefato(rel, texto)
        else:
            rel_.achados += analisar_codigo(rel, texto, tipo, perfil)
    rel_.achados.sort(key=lambda a: ({BLOQ: 0, NEC: 1, SUG: 2}.get(a.severidade, 3), a.arquivo, a.linha))
    rel_.duracao_s = round(time.perf_counter() - t0, 3)
    return rel_


# --------------------------------------------------------------------------- #
# Apresentação
# --------------------------------------------------------------------------- #
def para_json(rel_: Relatorio, falhar_em_necessario: bool) -> dict:
    codigo, veredito = rel_.veredito(falhar_em_necessario)
    return {
        "skill": "logs-observabilidade", "versao": "1.0.0", "perfil": rel_.perfil, "raiz": rel_.raiz,
        "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"), "duracao_s": rel_.duracao_s,
        "arquivos_analisados": rel_.arquivos_analisados, "arquivos_pulados": rel_.arquivos_pulados,
        "veredito": veredito, "codigo_saida": codigo,
        "contagem": {
            "bloqueante": len(rel_.ativos(BLOQ)), "necessario": len(rel_.ativos(NEC)),
            "sugestao": len(rel_.ativos(SUG)), "suprimidos": len([a for a in rel_.achados if a.suprimido]),
        },
        "achados": [asdict(a) for a in rel_.achados], "notas": rel_.notas,
    }


def imprimir(rel_: Relatorio, falhar_em_necessario: bool, *, maximo: int = 80) -> None:
    codigo, veredito = rel_.veredito(falhar_em_necessario)
    print(f"logs-observabilidade · perfil={rel_.perfil} · arquivos={rel_.arquivos_analisados} · {rel_.duracao_s}s")
    por_regra: dict[str, int] = {}
    for a in rel_.ativos():
        por_regra[a.regra] = por_regra.get(a.regra, 0) + 1
    if por_regra:
        print("  por regra: " + ", ".join(f"{k}={v}" for k, v in sorted(por_regra.items())))
    for a in rel_.achados[:maximo]:
        marca = "(suprimido: " + a.motivo + ")" if a.suprimido else ""
        print(f"  {a.severidade} {a.regra} {a.arquivo}:{a.linha} — {a.detalhe} {marca}")
        print(f"      › {a.trecho}")
    if len(rel_.achados) > maximo:
        print(f"  … +{len(rel_.achados) - maximo} achados (ver relatório JSON)")
    for n in rel_.arquivos_pulados[:10]:
        print(f"  ⚠ pulado: {n}")
    for n in rel_.notas:
        print(f"  ⚠ {n}")
    if codigo == 2:
        print("::inconclusivo:: nenhum arquivo analisável — não conta como verificado")
    print(f"RESULTADO: {veredito}")
