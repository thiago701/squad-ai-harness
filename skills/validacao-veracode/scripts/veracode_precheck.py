#!/usr/bin/env python3
"""Pré-scan Veracode determinístico — sem rede, sem credencial, só stdlib (Python >= 3.10).

Antecipa, no código-fonte, as classes de flaw que o Veracode Static Analysis costuma reportar
(CWE + severidade 0-5 ESTIMADA) e os problemas de empacotamento que degradam a cobertura do
scan. NÃO substitui o scan real: é o filtro barato que roda em todo diff antes do Pipeline Scan
e a evidência mínima da lente Veracode do code review quando não há credencial.

Uso:
  python veracode_precheck.py <alvo> [--perfil maximo|padrao|bancario] [--desde <ref-git>]
         [--json saida.json] [--md saida.md] [--falhar] [--incluir-testes]
  python veracode_precheck.py --listar-regras

Saída: JSON canônico (stdout quando --json é omitido).
Exit:  0 = sem bloqueante (ou sem --falhar) · 1 = há 🔴 e --falhar · 2 = uso inválido.

Supressão AUDITÁVEL (mesma linha ou linha anterior; sem motivo = ignorada):
  veracode-precheck: ignorar <REGRA> motivo=<por que é falso-positivo>
Toda supressão aparece no relatório — nada some em silêncio.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

VERSAO = "1.0.0"
FERRAMENTA = "veracode_precheck"
LIMITE_BYTES = 1_500_000
ROTULO_SEV = {5: "Very High", 4: "High", 3: "Medium", 2: "Low", 1: "Very Low", 0: "Informational"}
ORDEM_SQUAD = {"🔴": 0, "🟡": 1, "🔵": 2, "⚪": 3}

# CWEs que nunca passam no perfil máximo, qualquer que seja a severidade estimada.
CWE_CRITICOS = frozenset({22, 73, 78, 89, 94, 95, 259, 295, 321, 502, 611, 798, 917, 918})
# Corte do perfil padrão: espelha o --fail_on_cwe do CI da squad
# (skills/engenheiro-seguranca/references/veracode.md).
CWE_PADRAO = frozenset({22, 78, 80, 89})
# Perfil bancário: além dos críticos, estas classes bloqueiam em QUALQUER severidade — fraude,
# sigilo bancário (LC 105/2001), PCI DSS e integridade transacional (references/contexto-bancario.md).
CWE_BANCARIOS = frozenset({90, 113, 117, 200, 208, 209, 287, 312, 319, 326, 327, 329, 347, 352, 359,
                           362, 367, 532, 601, 613, 639, 643, 681, 682, 837, 915, 916, 943, 1321, 1339})
PERFIS = ("maximo", "padrao", "bancario")
BANCO = ("bancario",)  # regras de domínio que só rodam no perfil bancário


def classificar(sev: int | None, cwe: int | None, perfil: str) -> str:
    """Severidade Veracode (0-5) + CWE -> severidade da squad (🔴🟡🔵⚪)."""
    if sev is None:  # empacotamento: degrada a cobertura do scan, não é flaw
        return "🟡"
    if perfil == "bancario":
        if sev >= 2 or cwe in CWE_CRITICOS or cwe in CWE_BANCARIOS:
            return "🔴"
        return "🟡" if sev == 1 else "🔵"
    if perfil == "maximo":
        if sev >= 3 or cwe in CWE_CRITICOS:
            return "🔴"
        return {2: "🟡", 1: "🔵"}.get(sev, "⚪")
    if sev >= 4 or cwe in CWE_PADRAO:
        return "🔴"
    return {3: "🟡", 2: "🔵", 1: "🔵"}.get(sev, "⚪")


def veredito_de(severidades: list[str]) -> str:
    if "🔴" in severidades:
        return "BLOQUEADO"
    if "🟡" in severidades:
        return "APROVADO_COM_RESSALVAS"
    return "APROVADO"


@dataclass(frozen=True)
class Regra:
    id: str
    cwe: int | None
    sev: int | None  # severidade Veracode estimada (0-5); None = empacotamento
    exts: tuple[str, ...]
    padrao: str
    titulo: str
    correcao: str
    exceto: str | None = None  # casou na MESMA linha -> não reporta
    arquivo_exige: str | None = None  # só aplica se o arquivo contiver (ex.: camada de entrada)
    arquivo_isenta: str | None = None  # não aplica se o arquivo contiver (ex.: defesa XXE)
    segredo: bool = False  # redige o trecho e varre também comentários
    fonte: str = "veracode"  # veracode = classe que o SAST reporta · squad = régua interna
    ignora_literais: bool = False  # remove literais de string antes de casar
    perfis: tuple[str, ...] = ()  # vazio = todos os perfis; ("bancario",) = só no perfil bancário
    validador: str | None = None  # pós-filtro do valor casado (Luhn, DV de CPF/CNPJ, limiares)


@dataclass
class Achado:
    regra: str
    cwe: int | None
    severidade_veracode: int | None
    rotulo_veracode: str
    severidade_squad: str
    arquivo: str
    linha: int
    trecho: str
    titulo: str
    correcao: str
    fonte: str


# --------------------------------------------------------------------------- #
# Escopo de arquivos
# --------------------------------------------------------------------------- #
JAVA = (".java", ".kt", ".scala", ".groovy")
JSP = (".jsp", ".jspx")
PY = (".py",)
JS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue")
CS = (".cs",)
CSHTML = (".cshtml", ".razor")
CONFIG = (".properties", ".yml", ".yaml", ".env", ".ini", ".conf", ".cfg", ".toml")
CODIGO = JAVA + JSP + PY + JS + CS + CSHTML + (".go", ".rb", ".php", ".sh", ".ps1", ".tf")
TODOS = CODIGO + CONFIG + (".json", ".xml", ".pem", ".key")
BUILD = ("pom.xml", "build.gradle", "build.gradle.kts")

DIRS_IGNORADOS = frozenset({
    ".git", "node_modules", "target", "build", "dist", "out", ".venv", "venv", "env",
    "__pycache__", ".idea", ".gradle", ".mvn", "vendor", "coverage", ".next", ".nuxt",
    ".pytest_cache", ".tox", "site-packages", "bin", "obj", ".terraform", "veracode-artifacts",
})
DIRS_TESTE = frozenset({"test", "tests", "__tests__", "testes", "spec", "fixtures", "testdata"})
ARQ_TESTE = re.compile(
    r"(?:Test|Tests|IT|Spec)\.(?:java|kt|cs)$|^test_.*\.py$|_test\.(?:py|go)$|\.(?:spec|test)\.[jt]sx?$"
)

# Camada de entrada (onde dado externo nasce) — usada para reduzir ruído de regras de fluxo.
WEB_JAVA = (
    r"@(?:Rest)?Controller\b|HttpServletRequest|@(?:Request|Get|Post|Put|Delete|Patch)Mapping"
    r"|RequestHandler<|APIGateway(?:Proxy|V2HTTP)\w*Event|SQSEvent|SNSEvent|@Path\(|ServerRequest\b"
    r"|@KafkaListener|@SqsListener"
)
WEB_PY = (
    r"(?m)^\s*(?:from|import)\s+(?:flask|fastapi|django|starlette|aiohttp|tornado|falcon|bottle)\b"
    r"|def\s+lambda_handler\s*\(|\bevent\[\s*['\"](?:body|queryStringParameters|pathParameters|headers)"
)
WEB_JS = (
    r"\breq\.(?:body|query|params|headers|cookies)\b|\bexpress\(\)|fastify|@Controller\(|NextRequest"
    r"|APIGatewayProxyEvent|event\.(?:body|queryStringParameters|pathParameters)"
)
# Indício de dado externo no argumento logado (P-LOG-01): precisão > recall — o scan real cobre o resto.
INDICIO_ENTRADA = (
    r"(?:request|req|body|payload|params?|query|headers?|event|form|args|json|input|entrada|user|usuario"
    r"|username|nome|email|url|path|cpf|dados)"
)
CLEANSER = r"(?i)sanitiz|cleans|crlf|escapeJava|encodeFor|Encode\.for|LogSafe|StringEscapeUtils"
EXC_LOG = r",\s*(?:e|ex|exc|err|exception|t|th|throwable)\s*\)\s*;?\s*$"
PLACEHOLDER = (
    r"(?i)\$\{[^}]*\}|\{\{[^}]*\}\}|<[a-z_ -]+>|%\([^)]+\)s|\*{3,}|x{4,}|your[_-]|example|exemplo"
    r"|placeholder|dummy|fake|redacted|redigido|getenv|environ|process\.env|System\.getProperty"
    r"|@Value\(|SecretsManager|ParameterStore|ssm:|vault:"
)

# --------------------------------------------------------------------------- #
# Validadores: reduzem falso-positivo onde regex sozinha não decide (PAN, CPF, limiares)
# --------------------------------------------------------------------------- #
_IIN = (  # prefixo de bandeira -> comprimentos válidos do PAN
    (re.compile(r"4"), (13, 16, 19)),
    (re.compile(r"5[1-5]|2(?:22[1-9]|2[3-9]\d|[3-6]\d\d|7[01]\d|720)"), (16,)),
    (re.compile(r"3[47]"), (15,)),
    (re.compile(r"6011|65|64[4-9]|606282|3841|50(?:41|66|67|9\d)|6277|636[23]|650\d|6516|6550"), (16, 17, 18, 19)),
)


def _luhn_ok(digitos: str) -> bool:
    total, dobra = 0, False
    for ch in reversed(digitos):
        n = int(ch)
        if dobra:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
        dobra = not dobra
    return total % 10 == 0


def pan_ok(valor: str) -> bool:
    d = re.sub(r"[ -]", "", valor)
    if not d.isdigit() or not 13 <= len(d) <= 19 or len(set(d)) == 1:
        return False
    if not any(rx.match(d) and len(d) in tamanhos for rx, tamanhos in _IIN):
        return False
    return _luhn_ok(d)


def _cpf_ok(d: str) -> bool:
    if len(d) != 11 or len(set(d)) == 1:
        return False
    for n in (9, 10):
        soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (soma * 10) % 11 % 10 != int(d[n]):
            return False
    return True


def _cnpj_ok(d: str) -> bool:
    if len(d) != 14 or len(set(d)) == 1:
        return False
    pesos = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for pos, ps in ((12, pesos), (13, [6] + pesos)):
        resto = sum(int(d[i]) * ps[i] for i in range(pos)) % 11
        if (0 if resto < 2 else 11 - resto) != int(d[pos]):
            return False
    return True


def cpf_cnpj_ok(valor: str) -> bool:
    d = re.sub(r"\D", "", valor)
    return _cpf_ok(d) if len(d) == 11 else _cnpj_ok(d)


def segundos(valor: str) -> int | None:
    t = valor.strip().strip("\"'").lower()
    m = re.fullmatch(r"pt(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", t)
    if m and any(m.groups()):
        h, mi, se = (int(x or 0) for x in m.groups())
        return h * 3600 + mi * 60 + se
    m = re.fullmatch(r"(-?\d+)\s*([smhd]?)", t)
    if m:
        return int(m.group(1)) * {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}[m.group(2)]
    m = re.fullmatch(r"(days|hours|minutes|seconds)\s*=\s*(\d+)", t)
    if m:
        return int(m.group(2)) * {"days": 86400, "hours": 3600, "minutes": 60, "seconds": 1}[m.group(1)]
    return None


def sessao_longa(valor: str) -> bool:
    """PCI DSS 8.2.8: ociosidade acima de 15 min exige reautenticação. <= 0 = nunca expira."""
    s = segundos(valor)
    return s is not None and (s <= 0 or s > 900)


def iteracoes_baixas(valor: str) -> bool:
    """OWASP Password Storage: PBKDF2 >= 210 mil iterações (SHA-512) / 600 mil (SHA-256)."""
    try:
        return int(valor) < 210_000
    except ValueError:
        return False


def bcrypt_baixo(valor: str) -> bool:
    """Squad: bcrypt custo >= 12. Sem número explícito = padrão da lib (10) = baixo."""
    try:
        return int(valor) < 12
    except ValueError:
        return True


VALIDADORES = {"pan": pan_ok, "cpf_cnpj": cpf_cnpj_ok, "sessao_longa": sessao_longa,
               "iteracoes_baixas": iteracoes_baixas, "bcrypt_baixo": bcrypt_baixo}


def _valor(m: re.Match[str]) -> str:
    for nome, v in m.groupdict().items():
        if v is not None and nome.startswith("v"):
            return v
    return m.group(0)


# --------------------------------------------------------------------------- #
# Blocos de SQL reutilizados pelas regras de injeção — flags SÓ em grupo escopado (?i:...),
# porque o resto do padrão é sensível a caixa (ex.: constante MAIÚSCULA não é entrada).
# --------------------------------------------------------------------------- #
_DQ = r'(?:[^"\\\n]|\\.)'  # conteúdo de literal "..." (aceita \" escapado)
_TPL = r"[^`\n]"  # conteúdo de template literal JS/Go


def _sql(c: str) -> str:
    inicio = (r"select\b" + c + r"*?\bfrom\b|insert\s+into\b|update\s+[\w.\"`\[\]]+\s+set\b"
              r"|delete\s+from\b|merge\s+into\b")
    clausula = (r"\bwhere\b" + c + r"*?(?:=|<>|!=|<|>|\blike\b|\bin\b|\bis\b|\bbetween\b)"
                r"|\b(?:and|or)\s+[\w.\"`]+\s*(?:=|<>|!=|<|>|\blike\b|\bin\b)"
                r"|\border\s+by\b|\bgroup\s+by\b|\bhaving\b|\bvalues\s*\("
                r"|\b(?:where|limit|offset|set)\s*(?=[\"'`])")
    return r"(?i:" + inicio + "|" + clausula + ")"


SQL_DQ = _sql(_DQ)
SQL_TPL = _sql(_TPL)
_NAO_CONST = r"(?![A-Z][A-Z0-9_]*\b)"  # concatenação com CONSTANTE não é entrada externa
_CONCAT = r'\s*\+\s*' + _NAO_CONST + r"[\w(]"
LIT_SQL_DQ = r'"' + _DQ + r"*?" + SQL_DQ + _DQ + r'*"'
# Nome inequivocamente monetário — calibração 04/10: "base_valor: float" de benchmark não é dinheiro.
_DINHEIRO = (r"(?i:\w*(?:saldo|montante|preco|tarifa|juros|quantia|amount|balance|price|fee)\w*"
             r"|\w*valor_?(?:transac|transfer|pagament|parcel|bolet|pix|ted|compra|saque|deposit|fatur|credit|debit"
             r"|operac|liquid|brut|principal|juros|tarif|cobranc|emprest|financ)\w*"
             r"|\w*limite_?(?:credit|cheque|pix|saque|disponivel|diario|noturno|transac)\w*|valor)\b")
_SQ = r"(?:[^'\\\n]|\\.)"  # conteúdo de literal '...' (aspas duplas podem aparecer dentro)
SQL_SQ = _sql(_SQ)
# Python: cada tipo de aspa com seu conteúdo — "... nome = '{}'".format(x) precisa casar.
LIT_SQL_PY = r'(?:"' + _DQ + r"*?" + SQL_DQ + _DQ + r'*"|' + r"'" + _SQ + r"*?" + SQL_SQ + _SQ + r"*')"
FSTR_SQL_PY = (r'\b[rR]?[fF][rR]?(?:"' + _DQ + r"*?" + SQL_DQ + _DQ + r'*?\{|'
               + r"'" + _SQ + r"*?" + SQL_SQ + _SQ + r"*?\{)")

# --------------------------------------------------------------------------- #
# Catálogo de regras (CWE + severidade Veracode estimada). Manter em sincronia com
# references/catalogo-cwe-veracode.md — `--listar-regras` imprime a tabela viva.
# --------------------------------------------------------------------------- #
REGRAS: tuple[Regra, ...] = (
    # ---------------------------------------------------------------- Java / JVM
    Regra("J-SQL-01", 89, 4, JAVA,
          LIT_SQL_DQ + _CONCAT
          + r'|' + LIT_SQL_DQ + r'\s*\)\s*\.append\(\s*' + _NAO_CONST + r'[\w(]'
          + r'|(?:String|MessageFormat)\.format\(\s*"' + _DQ + r'*?' + SQL_DQ
          + r'|' + LIT_SQL_DQ + r'\s*\.formatted\(',
          "SQL montado por concatenação/StringBuilder/format (SQL Injection) — inclui PartiQL do DynamoDB",
          "PreparedStatement com `?`, JPA com parâmetro nomeado, jOOQ, PartiQL com `?` + parameters(); ORDER BY dinâmico só via allowlist de colunas."),
    Regra("J-CMD-01", 78, 5, JAVA,
          r'Runtime\.getRuntime\(\)\.exec\(\s*(?!"[^"]*"\s*\))'
          r'|new\s+ProcessBuilder\([^;]*(?:"\s*\+|\+\s*"|"(?:sh|bash|cmd(?:\.exe)?|powershell)"\s*,\s*"(?:-c|/c)")',
          "Execução de comando de SO com argumento dinâmico ou via shell (OS Command Injection)",
          "Evite o shell: ProcessBuilder com lista fixa de argumentos + allowlist dos valores variáveis; nunca concatene entrada."),
    Regra("J-PATH-01", 73, 3, JAVA,
          r'new\s+(?:File|FileInputStream|FileOutputStream|FileReader|FileWriter|RandomAccessFile)\([^;]*\+'
          r'|(?:Paths\.get|Path\.of)\([^;]*\+'
          r'|(?:Paths\.get|Path\.of|new\s+File)\([^;]*(?:getParameter|getHeader)\(',
          "Caminho de arquivo controlado externamente (External Control of File Name or Path)",
          "Resolva contra um diretório-base, normalize e valide `startsWith(base)`; o padrão de cleanser CWE-73 que o Veracode reconhece está em references/remediacao-e-mitigacao.md.",
          exceto=r"FilenameUtils\.getName|@FilePathCleanser|normalize\(\)[^;]*startsWith"),
    Regra("J-XXE-01", 611, 4, JAVA,
          r'(?:DocumentBuilderFactory|SAXParserFactory|XMLInputFactory|TransformerFactory|SchemaFactory)\.new(?:Default)?(?:Instance|Factory)\('
          r'|new\s+(?:SAXReader|SAXBuilder)\(|XMLReaderFactory\.createXMLReader\(',
          "Parser XML sem desabilitar DTD/entidades externas (XXE)",
          "setFeature(\"http://apache.org/xml/features/disallow-doctype-decl\", true) + FEATURE_SECURE_PROCESSING; ACCESS_EXTERNAL_DTD/SCHEMA = \"\".",
          arquivo_isenta=r"disallow-doctype-decl|FEATURE_SECURE_PROCESSING|ACCESS_EXTERNAL_DTD|SUPPORT_DTD|IS_SUPPORTING_EXTERNAL_ENTITIES|external-general-entities"),
    Regra("J-DESER-01", 502, 4, JAVA,
          r'new\s+ObjectInputStream\(|new\s+XMLDecoder\(|SerializationUtils\.deserialize\(',
          "Desserialização nativa de dado não confiável",
          "Troque por JSON com tipos fechados (records); se inevitável, ObjectInputFilter com allowlist (JEP 290/415).",
          arquivo_isenta=r"setObjectInputFilter|ObjectInputFilter\.Config|ValidatingObjectInputStream"),
    Regra("J-DESER-02", 502, 4, JAVA,
          r'\.enableDefaultTyping\(|LaissezFaireSubTypeValidator|JsonTypeInfo\.Id\.(?:MINIMAL_)?CLASS\b',
          "Jackson com polimorfismo por nome de classe (gadget chain)",
          "Use JsonTypeInfo.Id.NAME + @JsonSubTypes fechados ou BasicPolymorphicTypeValidator com allowlist."),
    Regra("J-CRYPTO-01", 327, 3, JAVA,
          r'MessageDigest\.getInstance\(\s*"(?:MD2|MD4|MD5|SHA-?1|SHA)"\s*\)'
          r'|Cipher\.getInstance\(\s*"(?:DES|DESede|RC2|RC4|ARCFOUR|Blowfish|AES|[^"]*/ECB/[^"]*)"'
          r'|KeyGenerator\.getInstance\(\s*"(?:DES|DESede|RC2|RC4)"'
          r'|SecretKeyFactory\.getInstance\(\s*"PBEWith(?:MD5|SHA1)AndDES'
          r'|DigestUtils\.(?:md5|sha1|md5Hex|sha1Hex|shaHex)\(',
          "Algoritmo criptográfico fraco ou modo ECB",
          "SHA-256+ (hash), AES/GCM/NoPadding com IV aleatório (cifra), Argon2id/bcrypt (senha)."),
    Regra("J-CRYPTO-02", 780, 3, JAVA,
          r'Cipher\.getInstance\(\s*"RSA(?:/ECB/PKCS1Padding|/NONE/NoPadding|/ECB/NoPadding)?"\s*\)',
          "RSA sem OAEP",
          "Cipher.getInstance(\"RSA/ECB/OAEPWithSHA-256AndMGF1Padding\")."),
    Regra("J-RAND-01", 331, 3, JAVA,
          r'new\s+(?:java\.util\.)?Random\(|Math\.random\(\)|RandomStringUtils\.random(?:Alphanumeric|Alphabetic|Numeric|Ascii)?\(',
          "PRNG previsível (Insufficient Entropy)",
          "java.security.SecureRandom (ou SecureRandom.getInstanceStrong para chaves); se não é uso de segurança, mitigue por design com justificativa."),
    Regra("J-LOG-01", 117, 3, JAVA,
          r'\b(?:log|logger|LOG|LOGGER|Log|Logger)\.(?:trace|debug|info|warn|warning|error|fatal)\(\s*(?:"[^"]*"\s*[+,]|[a-zA-Z_][\w.]*(?:\([^)]*\))?\s*[,)+])',
          "Dado da camada de entrada gravado em log sem neutralizar CR/LF (Log Injection)",
          "Passe o valor por um método anotado @CRLFCleanser (VeracodeAnnotations) que remova \\r\\n — ver references/remediacao-e-mitigacao.md.",
          exceto=CLEANSER + "|" + EXC_LOG, arquivo_exige=WEB_JAVA),
    Regra("J-LOG-02", 532, 3, CODIGO,
          r'(?i)\b(?:log|logger|logging|console)\.\w+\([^)\n]*\b(?:password|passwd|senha|secret|token|cpf|cvv|card_?number|numero_?cartao)\b',
          "Dado sensível enviado ao log (LGPD/PII)",
          "Nunca logue segredo/PII; use mascaramento (PII redactor) — ver engenheiro-seguranca/references/lgpd-privacidade.md.",
          fonte="squad", ignora_literais=True),
    Regra("J-XSS-01", 80, 3, JAVA,
          r'\.getWriter\(\)\.(?:print|println|write|printf|format|append)\(\s*(?!"[^"]*"\s*\))',
          "Saída HTTP sem encoding de contexto (XSS)",
          "org.owasp.encoder.Encode.forHtml(...) ou HtmlUtils.htmlEscape(...) — cleansers que o Veracode reconhece; prefira template com autoescape.",
          exceto=r"Encode\.for|HtmlUtils\.htmlEscape|encodeForHTML|escapeHtml4?|@XSSCleanser"),
    Regra("J-XSS-02", 80, 3, JSP,
          r'<%=\s*request\.|\$\{\s*param\.',
          "JSP ecoando parâmetro sem escape (XSS)",
          "<c:out value=\"${...}\"/> ou fn:escapeXml(...).",
          exceto=r"fn:escapeXml|c:out|Encode\.for"),
    Regra("J-REDIR-01", 601, 3, JAVA,
          r'\.sendRedirect\(\s*(?!")|"redirect:"\s*\+|new\s+RedirectView\(\s*(?!")|\.location\(\s*URI\.create\(\s*(?!")',
          "Redirecionamento para URL dinâmica (Open Redirect)",
          "Allowlist de destinos (ou só caminhos relativos); método validador pode ser anotado @RedirectURLCleanser.",
          exceto=r"(?i)allowlist|whitelist|safe\w*url|@RedirectURLCleanser|validar\w*redirect"),
    Regra("J-SSRF-01", 918, 3, JAVA,
          r'new\s+URL\(\s*(?:[a-z]\w*(?:\.get\w*\(\))?\s*\)|[^")]*\+)'
          r'|\b(?:restTemplate|webClient|restClient|httpClient)\.\w+\(\s*(?:[a-z]\w*\s*[,)]|[^;]*"\s*\+)',
          "Requisição de saída com URL dinâmica na camada de entrada (SSRF)",
          "Allowlist de host/esquema, bloqueio de IPs internos/metadata (169.254.169.254), sem seguir redirect.",
          arquivo_exige=WEB_JAVA),
    Regra("J-TLS-01", 295, 4, JAVA,
          r'NoopHostnameVerifier|ALLOW_ALL_HOSTNAME_VERIFIER|AllowAllHostnameVerifier|InsecureTrustManagerFactory'
          r'|TrustAllStrategy|TrustSelfSignedStrategy|setHostnameVerifier\(\s*\(?[^)]*\)?\s*->\s*true'
          r'|checkServerTrusted\([^)]*\)\s*(?:throws\s+[\w.]+(?:\s*,\s*[\w.]+)*)?\s*\{\s*\}',
          "Validação de certificado/hostname TLS desligada",
          "Remova o trust-all; use o truststore do JDK ou um truststore dedicado com o certificado esperado."),
    Regra("J-COOKIE-01", 614, 2, JAVA,
          r'new\s+Cookie\(',
          "Cookie sem atributo Secure",
          "cookie.setSecure(true) (ou ResponseCookie.from(...).secure(true)).",
          arquivo_isenta=r"setSecure\(\s*true\s*\)|\.secure\(\s*true\s*\)"),
    Regra("J-COOKIE-02", 1004, 2, JAVA,
          r'new\s+Cookie\(',
          "Cookie sem atributo HttpOnly",
          "cookie.setHttpOnly(true) (ou ResponseCookie...httpOnly(true)).",
          arquivo_isenta=r"setHttpOnly\(\s*true\s*\)|\.httpOnly\(\s*true\s*\)"),
    Regra("J-ERR-01", 209, 2, JAVA,
          r'\.printStackTrace\(\s*\)',
          "Stack trace exposto (Information Exposure Through an Error Message)",
          "Logue com o logger (sem PII) e devolva mensagem genérica + id de correlação."),
    Regra("J-EXIT-01", 382, 2, JAVA,
          r'\bSystem\.exit\(',
          "System.exit em código de aplicação (J2EE Bad Practices)",
          "Propague exceção/sinal de shutdown do container; System.exit só em main de CLI.",
          arquivo_isenta=r"public\s+static\s+void\s+main\s*\("),
    Regra("J-REFL-01", 470, 3, JAVA,
          r'Class\.forName\(\s*(?!")',
          "Reflexão com nome de classe dinâmico na camada de entrada (Unsafe Reflection)",
          "Mapa fechado nome->implementação (sealed interface + switch) em vez de Class.forName com entrada.",
          arquivo_exige=WEB_JAVA),
    Regra("J-CSRF-01", 352, 3, JAVA,
          r'csrf\(\s*\)\s*\.disable\(\)|csrf\(\s*AbstractHttpConfigurer::disable\s*\)|csrf\(\s*\w+\s*->\s*\w+\.disable\(\)\s*\)',
          "Proteção CSRF desligada",
          "Mantenha CSRF em app com sessão/cookie; em API stateless só-Bearer, registre mitigação por design com evidência."),
    Regra("J-CORS-01", 942, 3, JAVA,
          r'@CrossOrigin\s*(?:\(\s*\))?\s*$|@CrossOrigin\(\s*(?:origins\s*=\s*)?\{?\s*"\*"'
          r'|allowedOrigins\(\s*"\*"|addAllowedOrigin\(\s*"\*"|setAllowedOrigins\([^)]*"\*"|allowedOriginPatterns\(\s*"\*"',
          "CORS aberto para qualquer origem",
          "Allowlist explícita de origins por ambiente (engenheiro-seguranca/references/rate-limiting.md).",
          fonte="squad"),
    Regra("J-SPEL-01", 917, 4, JAVA,
          r'parseExpression\(\s*(?!")',
          "Expression Language com expressão dinâmica (EL/SpEL Injection)",
          "Nunca avalie expressão vinda de entrada; use SimpleEvaluationContext e expressões fixas."),
    Regra("J-EVAL-01", 95, 4, JAVA,
          r'\.eval\(\s*(?!"[^"]*"\s*\))',
          "ScriptEngine avaliando código dinâmico (Eval Injection)",
          "Remova o eval de entrada; se precisar de regra configurável, use uma DSL fechada.",
          arquivo_exige=r"javax\.script|ScriptEngine"),
    Regra("J-TRUST-01", 501, 3, JAVA,
          r'\.setAttribute\([^;]*(?:getParameter|getHeader)\(',
          "Dado não validado gravado na sessão (Trust Boundary Violation)",
          "Valide/normalize antes de guardar na sessão; guarde só o valor de domínio já validado."),
    Regra("J-SPLIT-01", 113, 3, JAVA,
          r'\.(?:addHeader|setHeader)\([^;]*(?:getParameter|getHeader)\(|new\s+Cookie\([^;]*getParameter\(',
          "Cabeçalho/cookie com entrada sem neutralizar CR/LF (HTTP Response Splitting)",
          "Remova \\r\\n (método anotado @CRLFCleanser) ou use API que valida o valor do header.",
          exceto=CLEANSER),
    Regra("J-LDAP-01", 90, 4, JAVA,
          r'\.search\([^;]*"\s*\+',
          "Filtro LDAP montado por concatenação (LDAP Injection)",
          "Encoder.encodeForLDAP / LdapQueryBuilder com parâmetros.",
          arquivo_exige=r"javax\.naming|LdapTemplate|DirContext"),
    Regra("J-XPATH-01", 643, 3, JAVA,
          r'\.(?:compile|evaluate)\(\s*"[^"]*"\s*\+',
          "XPath montado por concatenação (XPath Injection)",
          "XPathVariableResolver com variáveis ($nome) em vez de concatenação.",
          arquivo_exige=r"javax\.xml\.xpath|XPathFactory"),
    Regra("J-SQL-02", 89, 4, JAVA,
          r'"""\s*\.formatted\(|(?:String|MessageFormat)\.format\(\s*"""',
          "Text block SQL formatado com valores (SQL Injection)",
          "Text block só com placeholders `?`/`:nome` e bind no PreparedStatement/JPA — nunca .formatted() com entrada.",
          arquivo_exige=r"(?i)\b(?:select\s|insert\s+into|update\s+\S+\s+set|delete\s+from)"),
    Regra("J-SQL-03", 89, 4, ("Mapper.xml", "mapper.xml", "Dao.xml", "dao.xml"),
          r'\$\{\s*[\w.]+\s*\}',
          "MyBatis com ${} (substituição textual, não bind) — SQL Injection",
          "Use #{param} (PreparedStatement); ${} só para identificador vindo de allowlist fechada."),
    Regra("J-SQL-04", 89, 4, JAVA,
          r'@(?:Select|Update|Insert|Delete)\s*\([^\n]*\$\{',
          "Anotação MyBatis com ${} (SQL Injection)",
          "Troque ${x} por #{x}; ordenação dinâmica via allowlist."),
    Regra("K-SQL-01", 89, 4, (".kt",),
          r'"' + _DQ + r'*?' + SQL_DQ + _DQ + r'*?\$\{?[a-zA-Z_]',
          "String template Kotlin com SQL interpolado (SQL Injection)",
          "Parâmetros nomeados (Exposed/JDBC/Spring Data) — nunca $variavel dentro do SQL."),
    Regra("J-NOSQL-01", 943, 4, JAVA,
          r'\.(?:filterExpression|keyConditionExpression|conditionExpression|updateExpression|projectionExpression|expression)\(\s*"'
          + _DQ + r'*"' + _CONCAT
          + r'|"\$where"\s*,\s*"' + _DQ + r'*"\s*\+|Filters\.where\(\s*(?!"' + _DQ + r'*"\s*\))',
          "Expressão DynamoDB/Mongo montada por concatenação (NoSQL Injection)",
          "DynamoDB: placeholders `:valor`/`#nome` + expressionAttributeValues/Names; Mongo: filtros tipados, nunca $where."),
    Regra("J-JWT-01", 347, 4, JAVA,
          r'\bJWT\.decode\(|\bSignedJWT\.parse\(|\bJWTParser\.parse\(',
          "JWT decodificado sem verificação de assinatura no arquivo",
          "JWT.require(alg).build().verify(token) / JwtDecoder do Spring Security — decode só depois de verificar.",
          arquivo_isenta=r"JWT\.require\(|\.verify\(\s*\w|JWSVerifier|verifyWith|setSigningKey|NimbusJwtDecoder|JwtDecoder|parseSignedClaims|parseClaimsJws"),
    Regra("J-JWT-02", 347, 4, JAVA,
          r'\.parseClaimsJwt\(|\.parseUnsecuredClaims\(|\.unsecured\(\)',
          "JWT aceito sem assinatura (alg none)",
          "parseSignedClaims/parseClaimsJws com chave de verificação; rejeite tokens não assinados."),
    Regra("J-KEY-02", 321, 4, JAVA,
          r'new\s+SecretKeySpec\(\s*(?:"[^"]*"\s*\.getBytes|new\s+byte\s*\[\s*\]\s*\{|[A-Z][A-Z0-9_]{2,}\s*\.getBytes)',
          "Chave criptográfica hardcoded",
          "Chave do KMS/HSM (envelope encryption) ou do cofre; nunca literal no código."),
    Regra("J-IV-01", 329, 3, JAVA,
          r'new\s+(?:IvParameterSpec|GCMParameterSpec)\(\s*(?:\d+\s*,\s*)?(?:"[^"]*"\s*\.getBytes|new\s+byte\s*\[\s*\]\s*\{|new\s+byte\s*\[\s*\w+\s*\]\s*\)|[A-Z][A-Z0-9_]{2,}\b)',
          "IV/nonce fixo ou zerado",
          "IV aleatório de SecureRandom a cada cifragem (12 bytes no GCM), enviado junto do ciphertext."),
    # ---------------------------------------------------------------- Python
    Regra("P-SQL-01", 89, 4, PY,
          r'\.(?:execute|executemany|executescript|raw|extra)\(\s*(?:f["\']|["\'][^"\'\n]*["\']\s*(?:%|\+|\.format\())|\btext\(\s*f["\']',
          "SQL montado por f-string/format/concatenação (SQL Injection)",
          "Parâmetros do driver (cursor.execute(sql, params)) ou bindparams do SQLAlchemy."),
    Regra("P-CMD-01", 78, 5, PY,
          r'\bos\.(?:system|popen|spawn\w*|exec\w*)\(|subprocess\.\w+\([^)\n]*shell\s*=\s*True|commands\.getoutput\(',
          "Execução de comando via shell (OS Command Injection)",
          "subprocess.run([...], shell=False, check=True) com lista fixa + allowlist dos argumentos variáveis.",
          exceto=r'os\.system\(\s*["\'][^"\'+%{]*["\']\s*\)'),
    Regra("P-EVAL-01", 95, 5, PY,
          r'(?<![\w.])(?:eval|exec)\(\s*(?!["\'][^"\']*["\']\s*\))',
          "eval/exec de valor dinâmico (Eval Injection)",
          "ast.literal_eval para literais; para regras, uma DSL fechada."),
    Regra("P-DESER-01", 502, 4, PY,
          r'\b(?:pickle|cPickle|_pickle|dill|shelve|marshal|jsonpickle)\.(?:loads?|Unpickler|open|decode)\('
          r'|yaml\.(?:load|load_all)\((?![^)\n]*Loader\s*=\s*(?:yaml\.)?C?SafeLoader)|yaml\.unsafe_load'
          r'|torch\.load\((?![^)\n]*weights_only\s*=\s*True)',
          "Desserialização insegura (pickle/yaml/torch)",
          "json/pydantic; yaml.safe_load; torch.load(..., weights_only=True); nunca pickle de origem externa."),
    Regra("P-TLS-01", 295, 4, PY,
          r'verify\s*=\s*False|ssl\._create_unverified_context|ssl\.CERT_NONE|check_hostname\s*=\s*False|urllib3\.disable_warnings',
          "Verificação TLS desligada",
          "Mantenha verify=True; para CA privada, verify='/caminho/ca.pem'.",
          exceto=r"jwt\.decode"),
    Regra("P-CRYPTO-01", 327, 3, PY,
          r'hashlib\.(?:md5|sha1)\((?![^)\n]*usedforsecurity\s*=\s*False)|hashlib\.new\(\s*["\'](?:md4|md5|sha1)["\']'
          r'|\b(?:DES|DES3|ARC4|ARC2|Blowfish)\.new\(|MODE_ECB',
          "Algoritmo criptográfico fraco ou modo ECB",
          "hashlib.sha256 (ou usedforsecurity=False se não for segurança), AES-GCM (cryptography), argon2-cffi para senha."),
    Regra("P-RAND-01", 331, 3, PY,
          r'(?<![\w.])random\.(?:random|randint|randrange|choice|choices|shuffle|sample|getrandbits|uniform)\(',
          "PRNG previsível (Insufficient Entropy)",
          "módulo secrets (secrets.token_urlsafe, secrets.choice) para qualquer valor de segurança.",
          exceto=r"SystemRandom"),
    Regra("P-PATH-01", 73, 3, PY,
          r'\bopen\(\s*(?:f["\']|[^"\'\n),]*\+)|send_file\(\s*(?!["\'])|os\.path\.join\([^)\n]*request\.',
          "Caminho de arquivo controlado externamente",
          "Path(base).joinpath(nome).resolve() + is_relative_to(base); werkzeug.utils.secure_filename.",
          exceto=r"secure_filename|is_relative_to", arquivo_exige=WEB_PY),
    Regra("P-DEBUG-01", 489, 3, PY,
          r'\.run\([^)\n]*debug\s*=\s*True|^\s*DEBUG\s*=\s*True\b',
          "Modo debug ativo (Active Debug Code)",
          "Debug só por variável de ambiente fora de produção; nunca hardcoded."),
    Regra("P-SSRF-01", 918, 3, PY,
          r'\b(?:requests|httpx|urllib\.request)\.(?:get|post|put|patch|delete|head|request|urlopen)\(\s*(?:f["\'](?:https?://)?\{|[a-z_]\w*\s*[,)])',
          "Requisição de saída com URL dinâmica na camada de entrada (SSRF)",
          "Allowlist de host/esquema e bloqueio de IP interno/metadata antes de requisitar.",
          arquivo_exige=WEB_PY),
    Regra("P-LOG-01", 117, 3, PY,
          r'\b(?:logging|logger|log|LOGGER)\.(?:debug|info|warning|warn|error|exception|critical)\(\s*'
          r'(?:f["\'][^\n]*\{[^}\n]*\b' + INDICIO_ENTRADA + r'\b'
          r'|["\'][^"\'\n]*["\']\s*(?:%|\+|,|\.format\()[^\n]*\b' + INDICIO_ENTRADA + r'\b)',
          "Dado da camada de entrada gravado em log sem neutralizar CR/LF (Log Injection)",
          "Neutralize \\r\\n antes de logar (filtro/Formatter dedicado) e evite f-string com entrada.",
          exceto=CLEANSER, arquivo_exige=WEB_PY),
    Regra("P-XXE-01", 611, 4, PY,
          r'(?:lxml\.)?etree\.(?:XMLParser|parse|fromstring|XML)\(|xml\.sax\.(?:make_parser|parse|parseString)\(|xml\.dom\.(?:minidom|pulldom)\.(?:parse|parseString)\(',
          "Parser XML sem proteção contra entidades externas (XXE)",
          "defusedxml (defusedxml.ElementTree / defusedxml.lxml) ou XMLParser(resolve_entities=False, no_network=True).",
          arquivo_exige=r"\blxml\b|xml\.sax|xml\.dom", arquivo_isenta=r"defusedxml|resolve_entities\s*=\s*False"),
    Regra("P-SSTI-01", 1336, 4, PY,
          r'render_template_string\(\s*(?!["\'])|Template\(\s*(?:f["\']|request\.)',
          "Template renderizado a partir de string dinâmica (SSTI)",
          "Templates em arquivo + contexto; nunca compile template vindo de entrada."),
    Regra("P-XSS-01", 80, 3, PY,
          r'\bMarkup\(\s*(?!["\'])|autoescape\s*=\s*False|mark_safe\(\s*(?!["\'])',
          "Escape de HTML desligado (XSS)",
          "Deixe o autoescape do Jinja/Django agir; markupsafe.escape no valor."),
    Regra("P-TMP-01", 377, 2, PY,
          r'tempfile\.mktemp\(',
          "Arquivo temporário inseguro (race)",
          "tempfile.NamedTemporaryFile / mkstemp."),
    Regra("P-SQL-02", 89, 4, PY,
          FSTR_SQL_PY
          + r'|' + LIT_SQL_PY + r'\s*(?:%\s*[\w(]|\.format\(|\+\s*' + _NAO_CONST + r'[\w(])',
          "SQL montado em string formatada antes da execução (SQL Injection)",
          "Monte o SQL só com placeholders e passe os valores em execute(sql, params) / bindparams."),
    Regra("P-NOSQL-01", 943, 4, PY,
          r'(?:FilterExpression|KeyConditionExpression|ConditionExpression|UpdateExpression|ProjectionExpression)\s*=\s*'
          r'(?:[rR]?[fF]["\']|["\'][^"\'\n]*["\']\s*(?:\+|%|\.format\())|["\']\$where["\']\s*:\s*(?:[rR]?[fF]["\']|[a-zA-Z_])',
          "Expressão DynamoDB/Mongo montada com valores (NoSQL Injection)",
          "boto3.dynamodb.conditions Key/Attr ou ExpressionAttributeValues; no Mongo, filtros tipados e nunca $where."),
    Regra("P-JWT-01", 347, 4, PY,
          r'["\']verify_signature["\']\s*:\s*False|jwt\.decode\([^)\n]*verify\s*=\s*False|algorithms\s*=\s*\[[^\]\n]*["\']none["\']',
          "JWT aceito sem verificar assinatura",
          "jwt.decode(token, chave_publica, algorithms=[\"RS256\"|\"PS256\"], audience=..., issuer=...)."),
    # ---------------------------------------------------------------- JavaScript / TypeScript
    Regra("JS-EVAL-01", 95, 5, JS,
          r'(?<![\w.$])eval\(|new\s+Function\(|set(?:Timeout|Interval)\(\s*["\'`]',
          "eval/Function com código dinâmico (Eval Injection)",
          "JSON.parse para dados; funções reais em vez de string para timers."),
    Regra("JS-XSS-01", 80, 3, JS,
          r'\.(?:innerHTML|outerHTML)\s*\+?=(?!=)|document\.write(?:ln)?\(|insertAdjacentHTML\(|dangerouslySetInnerHTML'
          r'|\bv-html\s*=|\[innerHTML\]\s*=|bypassSecurityTrust(?:Html|Script|Url|ResourceUrl|Style)\(',
          "Inserção de HTML sem sanitização (XSS)",
          "textContent / binding do framework; se HTML for necessário, DOMPurify.sanitize antes.",
          exceto=r'DOMPurify\.sanitize|sanitizeHtml\(|\.innerHTML\s*=\s*(?:""|\'\'|``)\s*;?\s*$'),
    Regra("JS-CMD-01", 78, 5, JS,
          r'\b(?:exec|execSync)\(\s*(?:`[^`]*\$\{|[^)\n]*\+)|\bspawn(?:Sync)?\([^)\n]*shell\s*:\s*true',
          "Execução de comando com string dinâmica (OS Command Injection)",
          "execFile/spawn com array de argumentos e shell:false + allowlist.",
          arquivo_exige=r"child_process"),
    Regra("JS-SQL-01", 89, 4, JS,
          r'\.(?:query|execute|raw|\$queryRawUnsafe|\$executeRawUnsafe|unsafe)\(\s*(?:`[^`]*\$\{|["\'][^"\'\n]*["\']\s*\+)',
          "SQL montado por template/concatenação (SQL Injection)",
          "Placeholders do driver ($1/?) ou tagged template seguro (Prisma $queryRaw`...`)."),
    Regra("JS-NOSQL-01", 943, 4, JS,
          r'\.(?:find|findOne|updateOne|updateMany|deleteOne|deleteMany|aggregate)\(\s*req\.(?:body|query)|\$where\s*:',
          "Consulta NoSQL com objeto vindo direto da requisição (NoSQL Injection)",
          "Monte o filtro campo a campo com tipos validados (zod/joi); proíba operadores $ vindos do cliente."),
    Regra("JS-TLS-01", 295, 4, JS,
          r'rejectUnauthorized\s*:\s*false|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*["\']?0|strictSSL\s*:\s*false',
          "Verificação TLS desligada",
          "Remova o bypass; para CA privada use a opção `ca`."),
    Regra("JS-RAND-01", 331, 3, JS,
          r'Math\.random\(\)',
          "PRNG previsível (Insufficient Entropy)",
          "crypto.randomUUID() / crypto.getRandomValues() / crypto.randomInt()."),
    Regra("JS-CRYPTO-01", 327, 3, JS,
          r'createHash\(\s*["\'](?:md4|md5|sha1)["\']|createCipher(?:iv)?\(\s*["\'](?:des[\w-]*|rc4[\w-]*|bf[\w-]*|aes-\d+-ecb)["\']|\bcreateCipher\(',
          "Algoritmo criptográfico fraco ou modo ECB",
          "sha256+; aes-256-gcm com IV aleatório via createCipheriv."),
    Regra("JS-REDIR-01", 601, 3, JS,
          r'\.redirect\(\s*(?:\d+\s*,\s*)?req\.(?:query|body|params)'
          r'|location(?:\.href)?\s*=\s*[^;\n]*(?:searchParams\.get|location\.(?:search|hash))'
          r'|location\.(?:assign|replace)\([^)\n]*(?:searchParams\.get|location\.(?:search|hash))',
          "Redirecionamento para URL vinda da requisição (Open Redirect)",
          "Allowlist de destinos ou só caminhos relativos validados."),
    Regra("JS-PROTO-01", 1321, 3, JS,
          r'(?:Object\.assign|_\.merge|\bmerge|\bextend|defaultsDeep)\([^)\n]*req\.(?:body|query|params)'
          r'|\[\s*req\.(?:body|query|params)(?:\.\w+|\[[^\]]+\])\s*\]\s*=',
          "Merge de objeto da requisição (Prototype Pollution)",
          "Valide com schema e copie campos explícitos; Object.create(null) para mapas."),
    Regra("JS-PATH-01", 73, 3, JS,
          r'(?:readFile|readFileSync|createReadStream|sendFile|download|unlink|writeFile|writeFileSync)\([^)\n]*req\.(?:query|params|body)'
          r'|path\.(?:join|resolve)\([^)\n]*req\.(?:query|params|body)',
          "Caminho de arquivo vindo da requisição (Path Traversal)",
          "path.resolve(base, nome) + checagem startsWith(base); path.basename no nome.",
          exceto=r"path\.basename"),
    Regra("JS-JWT-01", 347, 4, JS,
          r'algorithms\s*:\s*\[[^\]]*["\']none["\']|ignoreExpiration\s*:\s*true',
          "JWT aceitando alg none ou ignorando expiração",
          "algorithms fixo (RS256/ES256) e expiração validada."),
    Regra("JS-CORS-01", 942, 3, JS,
          r'\bcors\(\s*\)|origin\s*:\s*["\']\*["\']|origin\s*:\s*true\b|Access-Control-Allow-Origin["\']\s*,\s*["\']\*',
          "CORS aberto para qualquer origem",
          "cors({ origin: [allowlist por ambiente] }).",
          fonte="squad"),
    Regra("JS-SQL-02", 89, 4, JS,
          r'(?<![\w$.\])])`' + _TPL + r'*?' + SQL_TPL + _TPL + r'*?\$\{'
          + r'|["\']' + r"[^\"'\n]" + r'*?' + _sql(r"[^\"'\n]") + r"[^\"'\n]" + r'*["\']' + _CONCAT,
          "SQL em template literal/concatenação fora de tag segura (SQL Injection)",
          "Placeholders do driver ($1/?) ou template com tag segura (sql``, Prisma.sql``, $queryRaw``)."),
    # ---------------------------------------------------------------- C# / .NET
    Regra("CS-SQL-01", 89, 4, CS,
          r'new\s+SqlCommand\(\s*(?:\$"|"[^"\n]*"\s*\+)|\.(?:FromSqlRaw|ExecuteSqlRaw|ExecuteSqlRawAsync|SqlQueryRaw)\(\s*(?:\$"|"[^"\n]*"\s*\+)'
          r'|CommandText\s*=\s*(?:\$"|"[^"\n]*"\s*\+)',
          "SQL montado por interpolação/concatenação (SQL Injection)",
          "SqlParameter / FromSqlInterpolated / ExecuteSqlInterpolated."),
    Regra("CS-CMD-01", 78, 5, CS,
          r'Process\.Start\(\s*(?!"[^"]*"\s*\))|\bArguments\s*=\s*(?:\$"|[^;\n]*\+)',
          "Execução de processo com argumento dinâmico (OS Command Injection)",
          "ProcessStartInfo com ArgumentList + allowlist; UseShellExecute=false."),
    Regra("CS-DESER-01", 502, 5, CS,
          r'\b(?:BinaryFormatter|NetDataContractSerializer|LosFormatter|SoapFormatter|ObjectStateFormatter)\b'
          r'|TypeNameHandling\s*=\s*TypeNameHandling\.(?:All|Auto|Objects|Arrays)',
          "Desserializador inseguro / TypeNameHandling",
          "System.Text.Json com tipos fechados; TypeNameHandling.None."),
    Regra("CS-CRYPTO-01", 327, 3, CS,
          r'\b(?:MD5|SHA1)\.Create\(|new\s+(?:MD5CryptoServiceProvider|SHA1Managed|SHA1CryptoServiceProvider|DESCryptoServiceProvider|TripleDESCryptoServiceProvider|RC2CryptoServiceProvider)\('
          r'|\b(?:DES|TripleDES|RC2)\.Create\(|CipherMode\.ECB',
          "Algoritmo criptográfico fraco ou modo ECB",
          "SHA256.Create / AesGcm; senha com PBKDF2 (Rfc2898DeriveBytes.Pbkdf2) ou Argon2."),
    Regra("CS-TLS-01", 295, 4, CS,
          r'ServerCertificate(?:Custom)?ValidationCallback\s*\+?=\s*(?:\([^)]*\)|\w+)\s*=>\s*true|DangerousAcceptAnyServerCertificateValidator',
          "Validação de certificado TLS desligada",
          "Remova o callback; valide a cadeia ou fixe o certificado esperado."),
    Regra("CS-XXE-01", 611, 4, CS,
          r'DtdProcessing\s*=\s*DtdProcessing\.Parse|XmlResolver\s*=\s*new\s+XmlUrlResolver|ProhibitDtd\s*=\s*false',
          "XML com DTD/resolver externo habilitado (XXE)",
          "DtdProcessing.Prohibit e XmlResolver = null."),
    Regra("CS-RAND-01", 331, 3, CS,
          r'new\s+Random\(',
          "PRNG previsível (Insufficient Entropy)",
          "RandomNumberGenerator.GetInt32 / GetBytes."),
    Regra("CS-REDIR-01", 601, 3, CS,
          r'\bRedirect\(\s*(?:Request\.|returnUrl\b|url\b)',
          "Redirecionamento para URL dinâmica (Open Redirect)",
          "LocalRedirect(...) ou Url.IsLocalUrl(...) antes de Redirect.",
          arquivo_isenta=r"IsLocalUrl"),
    Regra("CS-XSS-01", 80, 3, CSHTML + CS,
          r'Html\.Raw\(|Response\.Write\(\s*(?!"[^"]*"\s*\))',
          "Saída HTML sem encoding (XSS)",
          "Deixe o Razor codificar; HtmlEncoder.Default.Encode quando montar HTML."),
    Regra("CS-SQL-02", 89, 4, CS,
          r'(?:\$@?|@\$)"' + _DQ + r'*?' + SQL_DQ + _DQ + r'*?\{|' + LIT_SQL_DQ + _CONCAT,
          "SQL em string interpolada/concatenada (SQL Injection) — inclui Dapper",
          "SqlParameter, Dapper com parâmetros (@id), EF Core FromSql/ExecuteSql com FormattableString.",
          exceto=r"FromSqlInterpolated|ExecuteSqlInterpolated|\.FromSql\(\s*\$|\.ExecuteSql(?:Async)?\(\s*\$|\.SqlQuery\s*<[^>]*>\s*\(\s*\$"),
    # ---------------------------------------------------------------- Go
    Regra("GO-SQL-01", 89, 4, (".go",),
          r'fmt\.Sprintf\(\s*"' + _DQ + r'*?' + SQL_DQ
          + r'|' + LIT_SQL_DQ + _CONCAT
          + r'|`' + _TPL + r'*?' + SQL_TPL + _TPL + r'*`' + _CONCAT,
          "SQL montado com Sprintf/concatenação (SQL Injection)",
          "db.Query(\"... WHERE id = $1\", id) / sqlx com bind; nunca Sprintf no SQL."),
    # ---------------------------------------------------------------- Transversais
    Regra("X-TLS-01", 326, 3, CODIGO,
          r'"(?:SSLv2|SSLv3|TLSv1|TLSv1\.1)"|SSLContext\.getInstance\(\s*"(?:SSL|SSLv3)"\s*\)|ssl\.PROTOCOL_(?:SSLv2|SSLv3|SSLv23|TLSv1|TLSv1_1)\b'
          r'|TLSVersion\.(?:SSLv3|TLSv1|TLSv1_1)\b|minVersion\s*:\s*["\']TLSv1(?:\.1)?["\']|secureProtocol\s*:\s*["\'](?:SSLv3|TLSv1|TLSv1_1)_method'
          r'|SecurityProtocolType\.(?:Ssl3|Tls|Tls11)\b|SslProtocols\.(?:Ssl2|Ssl3|Tls|Tls11)\b',
          "Protocolo TLS/SSL obsoleto (TLS 1.0/1.1, SSLv3)",
          "TLS 1.2+ (preferir 1.3) com suítes AEAD — PCI DSS 4.2.1 e requisito de criptografia da Res. CMN 4.893."),
    Regra("X-TLS-02", 326, 3, CONFIG + (".tf",),
          r'(?i)(?:enabled-protocols|ssl[._-]?protocols?|tls[._-]?versions?|min[._-]?tls[._-]?version)\s*[=:]\s*[^#\n]*\b(?:SSLv2|SSLv3|TLSv1(?![.\d])|TLSv1\.1)\b'
          r'|minimum_protocol_version\s*=\s*"(?:SSLv3|TLSv1|TLSv1_2016|TLSv1\.1_2016)"|ELBSecurityPolicy-(?:2015-05|2016-08|TLS-1-0|TLS-1-1)',
          "Configuração aceita TLS 1.0/1.1 ou política de listener fraca",
          "TLS 1.2+ (ex.: ELBSecurityPolicy-TLS13-1-2-2021-06, CloudFront TLSv1.2_2021)."),
    Regra("KDF-01", 916, 3, JAVA + PY + CS,
          r'new\s+PBEKeySpec\([^;\n]*,\s*(?P<v>\d+)\s*,\s*\d+\s*\)|pbkdf2_hmac\(\s*[^,\n]+,[^,\n]+,[^,\n]+,\s*(?P<v2>\d+)'
          r'|new\s+Rfc2898DeriveBytes\([^;\n]*?,\s*(?P<v3>\d+)\s*[,)]',
          "PBKDF2 com poucas iterações (senha quebrável offline)",
          "Argon2id; se PBKDF2, >= 600 mil iterações com SHA-256 (OWASP Password Storage).",
          perfis=("maximo", "bancario"), validador="iteracoes_baixas"),
    Regra("KDF-02", 916, 3, JAVA + PY + JS,
          r'new\s+BCryptPasswordEncoder\(\s*(?P<v>\d+)?\s*[,)]|bcrypt\.gensalt\(\s*(?:rounds\s*=\s*)?(?P<v2>\d+)'
          r'|bcrypt\.genSalt(?:Sync)?\(\s*(?P<v3>\d+)|bcrypt\.hash(?:Sync)?\([^)\n]*,\s*(?P<v4>\d+)\s*\)',
          "bcrypt com custo abaixo de 12",
          "BCryptPasswordEncoder(12) ou mais — ou Argon2id (Argon2PasswordEncoder).",
          perfis=("maximo", "bancario"), validador="bcrypt_baixo"),
    # ---------------------------------------------------------------- Segredos (todas as linguagens)
    Regra("G-KEY-01", 321, 4, TODOS,
          r'-----BEGIN [A-Z ]{0,24}PRIVATE KEY-----',
          "Chave privada versionada",
          "Remova do repositório E do histórico, revogue/rotacione, e carregue do cofre (Secrets Manager/KMS).",
          segredo=True),
    Regra("G-AWS-01", 798, 4, TODOS,
          r'\b(?:AKIA|ASIA)[0-9A-Z]{16}\b',
          "Access key AWS no código",
          "Revogue a chave já; use role IAM/credenciais temporárias; nunca chave estática no código.",
          segredo=True),
    Regra("G-VERACODE-01", 798, 5, TODOS,
          r'(?i)veracode[_-]?api[_-]?(?:key[_-]?)?(?:id|key|secret)\s*[:=]\s*["\']?[0-9a-f]{32,}',
          "Credencial HMAC da Veracode no código",
          "Revogue a credencial da API service account e injete VERACODE_API_ID/KEY só em runtime pelo cofre.",
          segredo=True),
    Regra("G-CREDS-01", 798, 4, CODIGO,
          r'(?i)\b(?:password|passwd|pwd|senha|secret|client_?secret|api_?key|apikey|access_?key|auth_?token|private_?key)\b["\']?\s*[:=]\s*["\'][^"\'\s]{4,}["\']',
          "Credencial hardcoded",
          "Leia do cofre (Secrets Manager/SSM/Key Vault) ou de variável de ambiente injetada em runtime.",
          exceto=PLACEHOLDER, segredo=True),
    Regra("G-CREDS-02", 798, 4, CONFIG,
          r'(?i)^\s*[\w.-]*(?:password|passwd|pwd|senha|secret|api[_-]?key|token|access[_-]?key)[\w.-]*\s*[:=]\s*(?!\s*$)[^\s#]{4,}',
          "Credencial em arquivo de configuração",
          "Placeholder ${VAR} resolvido em runtime pelo cofre; o valor real nunca vai para o repositório.",
          # calibração 04/10: "GenerateSecret: false" (SAM/Cognito) é flag booleana, não segredo
          exceto=PLACEHOLDER + r"|[=:]\s*[\"']?(?:true|false|yes|no|on|off|null|none|enabled|disabled)[\"']?\s*(?:#.*)?$",
          segredo=True),
    # ---------------------------------------------------------------- Domínio bancário (só perfil bancario)
    # Classes de lógica de negócio que o SAST não vê bem: dinheiro, sigilo, fraude e integridade.
    # Detalhe, normas e correções: references/contexto-bancario.md
    Regra("BK-DINHEIRO-01", 1339, 3, JAVA + CS + PY + JS,
          r'\b(?:double|float|Double|Float)\s+' + _DINHEIRO + r'\s*[=;,)]'
          + r'|\b(?:float|parseFloat)\(\s*(?:[\w.]+\.|[\w.]+\[["\'])?(?!valor\b)' + _DINHEIRO
          + r'|\b' + _DINHEIRO + r'\??\s*:\s*(?:float|number)\b',
          "Valor monetário em ponto flutuante (arredondamento binário em dinheiro)",
          "BigDecimal (Java) / decimal (C#, Python) / inteiro em centavos; nunca double/float/number para saldo, valor ou tarifa.",
          exceto=r"(?i)cent(?:s|avos)|minor_?units?|decimal|bigdecimal", fonte="bancario", perfis=BANCO),
    Regra("BK-DINHEIRO-02", 682, 3, JAVA,
          r'new\s+BigDecimal\(\s*-?\d+\.\d+[dDfF]?\s*\)|\.setScale\(\s*\d+\s*\)|\.divide\(\s*[^,()\n]+(?:\([^()\n]*\))?\s*\)'
          r'|\b(?i:valor|saldo|montante|amount|balance)\w*\.doubleValue\(\)',
          "Cálculo monetário com BigDecimal impreciso ou sem RoundingMode",
          "new BigDecimal(\"0.10\")/valueOf, setScale(2, RoundingMode.HALF_EVEN), divide(x, 2, RoundingMode.HALF_EVEN) ou MathContext.DECIMAL128.",
          arquivo_exige=r"BigDecimal", fonte="bancario", perfis=BANCO),
    Regra("BK-PAN-01", 312, 4, CODIGO + CONFIG + (".json", ".sql", ".csv", ".xml"),
          r'(?<![\w.-])(?P<v>[2-6](?:\d[ -]?){11,17}\d)(?![\w-])',
          "Número de cartão (PAN válido por Luhn) no código/config — PCI DSS 3.3/3.5",
          "PAN nunca em claro: tokenização (cofre/PSP) ou cifra forte; em tela só BIN + 4 últimos (PCI DSS 3.4.1); massa de teste fora do artefato.",
          segredo=True, fonte="bancario", perfis=BANCO, validador="pan"),
    Regra("BK-CPF-01", 359, 2, CODIGO + CONFIG + (".json", ".sql", ".csv"),
          r'(?<![\w.-])(?P<v>\d{3}\.\d{3}\.\d{3}-\d{2}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})(?![\w])',
          "CPF/CNPJ válido hardcoded (dado pessoal — LGPD)",
          "Dado de cliente nunca no código; massa sintética gerada no teste (DV válido, fora do artefato de produção).",
          segredo=True, fonte="bancario", perfis=BANCO, validador="cpf_cnpj"),
    Regra("BK-LOG-01", 532, 3, CODIGO,
          r'(?i)\b(?:log(?:ger)?|logging|console)\.\w+\([^)\n]*\b(?:pan|card_?number|numero_?cartao|cvv2?|cvc2?|pin|trilha|track2?|chave_?pix|pix_?key'
          r'|saldo|balance|numero_?conta|account_?number|agencia|cnpj|rg|data_?nascimento|birth_?date)\b',
          "Dado protegido por sigilo bancário/PCI enviado ao log",
          "Mascarar/tokenizar antes de logar (LC 105/2001, PCI DSS 3.3–3.4, LGPD); log de transação só com ids técnicos.",
          fonte="bancario", perfis=BANCO, ignora_literais=True),
    Regra("BK-BOLA-01", 639, 4, JAVA + JS + PY,
          r'@(?:Get|Post|Put|Delete|Patch|Request)Mapping\([^)\n]*\{(?i:conta|account|cliente|customer|agencia|cartao|card|contrato|contract|carteira|wallet)\w*\}'
          r'|\.(?:get|post|put|patch|delete|all)\(\s*["\'`][^"\'`\n]*:(?i:conta|account|cliente|customer|cartao|card|contrato|contract|carteira|wallet)\w*'
          r'|@\w+\.(?:get|post|put|patch|delete|route|api_route)\(\s*["\'][^"\'\n]*(?:\{|<(?:\w+:)?)(?i:conta|account|cliente|customer|cartao|card|contrato|contract)\w*[}>]',
          "Recurso de conta/cartão/cliente por id sem checagem de titularidade no arquivo (BOLA/IDOR — OWASP API1)",
          "Autorize por objeto: o id do path precisa pertencer ao titular do token (@PreAuthorize + serviço de titularidade, ou filtro por subject na consulta).",
          arquivo_isenta=r"@PreAuthorize|@PostAuthorize|hasPermission|@Secured|@RolesAllowed|(?i:titular|ownership|owner_?id|is_?owner|assert_?owner)"
                         r"|@AuthenticationPrincipal|getAuthentication\(\)|req\.user|req\.auth\b|res\.locals\.user|@UseGuards|current_user|get_current_user|request\.user",
          fonte="bancario", perfis=BANCO),
    Regra("BK-MASS-01", 915, 3, JAVA + JS + PY,
          r'@RequestBody\s+(?:@\w+(?:\([^)]*\))?\s+)*(?:final\s+)?\w*(?:Entity|Conta|Account|Cliente|Customer|Usuario|User)\b'
          r'|(?:new\s+[A-Z]\w*|\.(?:create|update|updateOne|updateMany|findByIdAndUpdate|findOneAndUpdate|save|build|upsert|insert))\(\s*(?:[^,()\n]*,\s*)?req\.body\s*[,)]'
          r'|\w+\(\s*\*\*\s*(?:request\.(?:json|form|data|get_json\(\))|payload|body)\s*\)',
          "Entidade preenchida direto com o corpo da requisição (Mass Assignment)",
          "DTO/record de entrada com campos permitidos + mapeamento explícito; saldo, limite, status e titular nunca vêm do cliente.",
          fonte="bancario", perfis=BANCO),
    Regra("BK-IDEMP-01", 837, 3, JAVA + JS + PY,
          r'@PostMapping\(\s*(?:(?:value|path)\s*=\s*)?\{?\s*"[^"\n]*(?i:pagamento|pagar|transfer|pix|\bted\b|boleto|saque|withdraw|payment|debito|debit|resgate|aporte)'
          r'|\.post\(\s*["\'`][^"\'`\n]*(?i:pagamento|pagar|transfer|pix|\bted\b|boleto|saque|withdraw|payment|debito|debit)'
          r'|@\w+\.(?:post|route)\(\s*["\'][^"\'\n]*(?i:pagamento|pagar|transfer|pix|\bted\b|boleto|saque|withdraw|payment|debito|debit)',
          "Operação financeira sem idempotência visível (retry = débito em dobro)",
          "Exigir Idempotency-Key (ou endToEndId/txid do Pix) com registro condicional (DynamoDB attribute_not_exists / UNIQUE) antes de efetivar; cliente sempre envia a chave.",
          arquivo_isenta=r"(?i)idempot|endToEndId|end_to_end_id|e2e_?id|\btxid\b", fonte="bancario", perfis=BANCO),
    Regra("BK-RACE-01", 367, 3, JAVA + PY + JS + CS,
          r'(?i:(?:\b|get|\.)(?:saldo|balance|limite|disponivel)\w*)(?:\(\s*\))?\s*(?:<=?|>=?)\s*[\w(]'
          r'|(?i:(?:\b|get|\.)(?:saldo|balance|limite|disponivel)\w*)(?:\(\s*\))?\.compareTo\(',
          "Checagem de saldo/limite antes do débito sem trava (TOCTOU — gasto duplo)",
          "Débito atômico: UPDATE ... WHERE saldo >= :v, SELECT ... FOR UPDATE, @Version/@Lock, ou DynamoDB ConditionExpression \"saldo >= :v\" / TransactWriteItems.",
          arquivo_exige=r"(?i)\b(?:debit\w*|debitar|sacar|saque\w*|withdraw\w*|transferir|transfer\w*|pagar|reservar)\s*\(",
          arquivo_isenta=r"@Lock\s*\(|PESSIMISTIC_WRITE|(?i:for\s+update)|@Version\b|(?i:condition_?expression)|(?i:transact_?write_?items)"
                         r"|SERIALIZABLE|(?i:optimistic)|LockModeType|compareAndSet|select_for_update|with_for_update",
          fonte="bancario", perfis=BANCO),
    Regra("BK-TIMING-01", 208, 3, JAVA + PY + JS + CS,
          r'(?i:\b\w*(?:senha|password|passwd|pin|otp|token|hmac|signature|assinatura|digest|secret|segredo))\w*(?:\(\s*\))?\s*\.equals\('
          r'|(?i:\b(?:hmac|signature|assinatura|digest|otp|token|senha|password|pin)\w*)\s*===?\s*(?i:\w*(?:hmac|signature|assinatura|digest|otp|token|senha|password|pin|esperad|expected|calculad|computed))',
          "Comparação de segredo em tempo variável (timing attack)",
          "MessageDigest.isEqual / hmac.compare_digest / crypto.timingSafeEqual / CryptographicOperations.FixedTimeEquals.",
          exceto=r'MessageDigest\.isEqual|compare_digest|timingSafeEqual|constantTimeEquals|FixedTimeEquals|==\s*(?:null|None|undefined)|\.equals\(\s*(?:null|")|==\s*["\']',
          fonte="bancario", perfis=BANCO),
    Regra("BK-SESSAO-01", 613, 2, CONFIG + JAVA + PY,
          r'(?i)(?:server\.servlet\.session\.timeout|session[._-]?timeout|max[-_]?inactive[-_]?interval|SESSION_COOKIE_AGE|PERMANENT_SESSION_LIFETIME)["\']?\s*[=:]\s*["\']?(?P<v>PT\w+|-?\d+\s*[smhd]?\b)'
          r'|setMaxInactiveInterval\(\s*(?P<v2>-?\d+)\s*\)|PERMANENT_SESSION_LIFETIME\s*=\s*timedelta\(\s*(?P<v3>\w+\s*=\s*\d+)',
          "Sessão ociosa acima de 15 minutos (PCI DSS 8.2.8)",
          "Timeout de inatividade <= 15 min com reautenticação; token de acesso curto + refresh rotativo.",
          fonte="bancario", perfis=BANCO, validador="sessao_longa"),
    Regra("BK-HTTP-01", 319, 3, CODIGO + CONFIG,
          r'["\'=:\s(]http://(?!localhost\b|127\.\d+\.\d+\.\d+|0\.0\.0\.0|\[::1\]|host\.docker\.internal|localstack\b|[\w.-]+\.local\b|[\w.-]+\.internal\b'
          r'|[\w.-]*w3\.org|schemas\.|java\.sun\.com|xmlns\.|maven\.apache\.org|www\.springframework\.org|json-schema\.org|purl\.org|example\.(?:com|org|net)\b|www\.apache\.org)'
          r'[\w-]+(?:\.[\w-]+)+',
          "Integração em HTTP sem TLS (dado em claro em trânsito)",
          "HTTPS com TLS 1.2+ e validação de certificado (mTLS com ICP-Brasil em integrações reguladas).",
          exceto=r"xmlns|schemaLocation|<!DOCTYPE|@see|(?i:license)", fonte="bancario", perfis=BANCO),
    Regra("BK-FAPI-01", 287, 3, CODIGO + CONFIG,
          r'(?i)\b(?:client_secret_basic|client_secret_post|client_secret_jwt)\b|code_challenge_method["\']?\s*[=:]\s*["\']?plain\b'
          r'|response_type["\']?\s*[=:]\s*["\']?token\b|grant_type["\']?\s*[=:]\s*["\']?password\b|AuthorizationGrantType\.(?:PASSWORD|IMPLICIT)\b'
          r'|\balg["\']?\s*[=:]\s*["\']?(?:none|HS256)\b|(?:SignatureAlgorithm|MacAlgorithm|MacAlgorithms)\.HS256\b',
          "Fluxo OAuth/assinatura fora do perfil FAPI (Open Finance Brasil)",
          "private_key_jwt, PAR + PKCE S256, tokens vinculados ao certificado mTLS (ICP-Brasil), assinatura PS256; sem implicit/password grant.",
          fonte="bancario", perfis=BANCO),
    Regra("BK-CFG-01", 209, 2, CONFIG,
          r'(?i)server\.error\.include-(?:stacktrace|message|exception|binding-errors)\s*[=:]\s*["\']?(?:always|true|on[-_]param)'
          r'|include-stacktrace\s*:\s*["\']?always|DEBUG_PROPAGATE_EXCEPTIONS\s*=\s*True',
          "Erro detalhado/stack trace devolvido ao cliente",
          "server.error.include-stacktrace=never e include-message=never; detalhe só no log interno com id de correlação.",
          fonte="bancario", perfis=BANCO),
    Regra("BK-CFG-02", 200, 3, CONFIG,
          r'(?i)management\.endpoints\.web\.exposure\.include\s*[=:]\s*["\']?[^#\n]*(?:\*|heapdump|\benv\b|threaddump|configprops|logfile|shutdown)',
          "Actuator expondo endpoints sensíveis (env, heapdump, shutdown)",
          "Exponha só health/info em porta de gestão interna, com autenticação.",
          fonte="bancario", perfis=BANCO),
    # ---------------------------------------------------------------- Empacotamento (cobertura do scan)
    Regra("PKG-01", None, None, BUILD,
          r'<artifactId>\s*maven-shade-plugin\s*</artifactId>|com\.github\.johnrengelman\.shadow|com\.gradleup\.shadow|\bshadowJar\b',
          "Fat-jar shaded: o Veracode tem suporte limitado a dependências shaded",
          "PR gate: `veracode package --java-source`; Policy Scan: repackage do Spring Boot ou só as classes de 1ª parte."),
    Regra("PKG-02", None, None, BUILD,
          r'<debug>\s*false\s*</debug>|<debuglevel>\s*none\s*</debuglevel>|-g:none|\bdebug\s*=\s*false\b',
          "Build sem símbolos de debug: o scan perde arquivo/linha e cobertura",
          "maven-compiler-plugin com <debug>true</debug> e <debuglevel>lines,vars,source</debuglevel>; não strippar o artefato."),
)

COMENTARIO = re.compile(r"^\s*(?://|#|/\*|\*|<!--|--\s)")
LITERAL = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`')
SUPRESSAO = re.compile(r"veracode-precheck:\s*ignorar\s+([A-Z]+-[A-Z]*-?\d+)(?:\s+motivo=(\S[^*>]*?))?\s*(?:\*/|-->)?\s*$")


def saida_utf8() -> None:
    """Relatórios têm emoji (🔴🟡): em Windows com stdout/stderr redirecionado (CI) o encoding
    padrão é cp1252 e o print quebraria com UnicodeEncodeError — força UTF-8."""
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")


@lru_cache(maxsize=None)
def _rx(padrao: str) -> re.Pattern[str]:
    return re.compile(padrao)


def eh_teste(rel: Path) -> bool:
    if {p.lower() for p in rel.parts[:-1]} & DIRS_TESTE:
        return True
    return bool(ARQ_TESTE.search(rel.name))


def _supressao(linhas: list[str], idx: int, regra: str) -> tuple[bool, str | None]:
    """(achou_marcador, motivo) olhando a linha do achado e a anterior."""
    for j in (idx, idx - 1):
        if 0 <= j < len(linhas):
            m = SUPRESSAO.search(linhas[j])
            if m and m.group(1) == regra:
                motivo = (m.group(2) or "").strip()
                return True, motivo or None
    return False, None


def _trecho(linha: str, m: re.Match[str], segredo: bool) -> str:
    texto = linha[: m.start()] + "<segredo redigido>" + linha[m.end():] if segredo else linha
    return texto.strip()[:160]


def analisar_texto(texto: str, rel: str, perfil: str, regras: tuple[Regra, ...] = REGRAS
                   ) -> tuple[list[Achado], list[dict]]:
    nome = Path(rel).name
    aplicaveis = [r for r in regras if nome.endswith(r.exts)]
    achados: list[Achado] = []
    suprimidos: list[dict] = []
    if not aplicaveis:
        return achados, suprimidos
    linhas = texto.splitlines()
    for r in aplicaveis:
        if r.perfis and perfil not in r.perfis:
            continue
        if r.arquivo_exige and not _rx(r.arquivo_exige).search(texto):
            continue
        if r.arquivo_isenta and _rx(r.arquivo_isenta).search(texto):
            continue
        padrao = _rx(r.padrao)
        exceto = _rx(r.exceto) if r.exceto else None
        for idx, linha in enumerate(linhas):
            if not r.segredo and COMENTARIO.match(linha):
                continue
            m = _primeiro(padrao, LITERAL.sub('""', linha) if r.ignora_literais else linha, r.validador)
            if not m or (exceto and exceto.search(linha)):
                continue
            achado = Achado(
                regra=r.id, cwe=r.cwe, severidade_veracode=r.sev,
                rotulo_veracode=ROTULO_SEV.get(r.sev, "Empacotamento") if r.sev is not None else "Empacotamento",
                severidade_squad=classificar(r.sev, r.cwe, perfil), arquivo=rel, linha=idx + 1,
                trecho=_trecho(linha, m, r.segredo), titulo=r.titulo, correcao=r.correcao, fonte=r.fonte,
            )
            marcado, motivo = _supressao(linhas, idx, r.id)
            if marcado and motivo:
                suprimidos.append({**asdict(achado), "motivo": motivo})
                continue
            if marcado:
                achado.titulo += " [supressão SEM motivo ignorada]"
            achados.append(achado)
    # Uma linha, um CWE: variantes da mesma classe (ex.: P-SQL-01 e P-SQL-02) não viram ruído duplicado.
    vistos: set[tuple] = set()
    unicos = []
    for a in achados:
        chave = (a.cwe, a.linha) if a.cwe is not None else (a.regra, a.linha)
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(a)
    return unicos, suprimidos


def _primeiro(padrao: re.Pattern[str], texto: str, validador: str | None) -> re.Match[str] | None:
    if not validador:
        return padrao.search(texto)
    valida = VALIDADORES[validador]
    return next((m for m in padrao.finditer(texto) if valida(_valor(m))), None)


# Somente leitura: nunca tomar lock opcional do índice (um `git status`/`diff` interrompido deixaria
# .git/index.lock órfão no repositório do usuário).
GIT_ENV = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}


def _git(top: Path, *args: str) -> list[str]:
    r = subprocess.run(["git", "--no-optional-locks", "-C", str(top), *args], capture_output=True, text=True, env=GIT_ENV)
    if r.returncode != 0:
        raise SystemExit(f"erro: git {' '.join(args)} falhou: {r.stderr.strip()}")
    return [linha for linha in r.stdout.splitlines() if linha.strip()]


def arquivos_alterados(alvo: Path, ref: str) -> list[Path]:
    base = alvo if alvo.is_dir() else alvo.parent
    r = subprocess.run(["git", "--no-optional-locks", "-C", str(base), "rev-parse", "--show-toplevel"],
                       capture_output=True, text=True, env=GIT_ENV)
    if r.returncode != 0:
        raise SystemExit(f"erro: {alvo} não está num repositório git (--desde exige git)")
    top = Path(r.stdout.strip())
    nomes = set(_git(top, "diff", "--name-only", "--diff-filter=ACMR", ref))
    nomes.update(_git(top, "ls-files", "--others", "--exclude-standard"))
    alvo_abs = alvo.resolve()
    saida = []
    for nome in sorted(nomes):
        p = (top / nome).resolve()
        if p.is_file() and (p == alvo_abs or alvo_abs in p.parents):
            saida.append(p)
    return saida


def enumerar(alvo: Path, incluir_testes: bool, desde: str | None) -> list[Path]:
    if desde:
        candidatos = arquivos_alterados(alvo, desde)
    elif alvo.is_file():
        candidatos = [alvo]
    else:  # os.walk podando node_modules/target/... ANTES de descer (rglob varreria tudo)
        candidatos = []
        for pasta, subpastas, nomes in os.walk(alvo):
            subpastas[:] = sorted(d for d in subpastas if d not in DIRS_IGNORADOS)
            candidatos.extend(Path(pasta) / n for n in sorted(nomes))
    raiz = alvo if alvo.is_dir() else alvo.parent
    saida = []
    for p in candidatos:
        try:
            rel = p.resolve().relative_to(raiz.resolve())
        except ValueError:
            rel = Path(p.name)
        if set(rel.parts[:-1]) & DIRS_IGNORADOS or p.name.endswith(".min.js"):
            continue
        if not incluir_testes and eh_teste(rel):
            continue
        saida.append(p)
    return saida


def executar(alvo: Path, perfil: str = "maximo", desde: str | None = None, incluir_testes: bool = False) -> dict:
    raiz = alvo if alvo.is_dir() else alvo.parent
    achados: list[Achado] = []
    suprimidos: list[dict] = []
    arquivos = enumerar(alvo, incluir_testes, desde)
    analisados = 0
    for p in arquivos:
        try:
            if p.stat().st_size > LIMITE_BYTES:
                continue
            texto = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        try:
            rel = p.resolve().relative_to(raiz.resolve()).as_posix()
        except ValueError:
            rel = p.name
        a, s = analisar_texto(texto, rel, perfil)
        analisados += 1
        achados.extend(a)
        suprimidos.extend(s)
    achados.sort(key=lambda x: (ORDEM_SQUAD[x.severidade_squad], -(x.severidade_veracode or 0), x.arquivo, x.linha))
    sevs = [x.severidade_squad for x in achados]
    return {
        "ferramenta": FERRAMENTA,
        "versao": VERSAO,
        "perfil": perfil,
        "alvo": str(alvo),
        "desde": desde,
        "arquivos_analisados": analisados,
        "achados": [asdict(x) for x in achados],
        "suprimidos": suprimidos,
        "resumo": {
            "total": len(achados),
            "por_severidade": {s: sevs.count(s) for s in ("🔴", "🟡", "🔵", "⚪")},
            "suprimidos": len(suprimidos),
            "veredito_preliminar": veredito_de(sevs),
        },
        "aviso": "Pré-scan heurístico: NÃO substitui o Veracode Static Analysis. Ausência de achado não prova ausência de flaw.",
    }


def para_markdown(rel: dict) -> str:
    r = rel["resumo"]
    ps = r["por_severidade"]
    linhas = [
        f"### Pré-scan Veracode — {r['veredito_preliminar']} (perfil: {rel['perfil']})",
        "",
        f"{rel['arquivos_analisados']} arquivos · 🔴 {ps['🔴']} · 🟡 {ps['🟡']} · 🔵 {ps['🔵']} · ⚪ {ps['⚪']}"
        f" · suprimidos com motivo: {r['suprimidos']}",
        "",
    ]
    if rel["achados"]:
        linhas += ["| Sev | CWE | Local | Achado | Correção |", "|---|---|---|---|---|"]
        for a in rel["achados"]:
            cwe = f"CWE-{a['cwe']}" if a["cwe"] else "—"
            rot = f" ({a['rotulo_veracode']})"
            linhas.append(
                f"| {a['severidade_squad']} | {cwe}{rot} | `{a['arquivo']}:{a['linha']}` | {a['titulo']} [{a['regra']}] | {a['correcao']} |"
            )
    if rel["suprimidos"]:
        linhas += ["", "**Supressões (auditáveis):**"]
        linhas += [f"- `{s['arquivo']}:{s['linha']}` {s['regra']} — motivo: {s['motivo']}" for s in rel["suprimidos"]]
    linhas += ["", f"> {rel['aviso']}"]
    return "\n".join(linhas) + "\n"


def listar_regras() -> str:
    linhas = ["| Regra | CWE | Sev. Veracode (estimada) | Fonte | Perfis | Achado |", "|---|---|---|---|---|---|"]
    for r in REGRAS:
        cwe = f"CWE-{r.cwe}" if r.cwe else "—"
        sev = f"{r.sev} {ROTULO_SEV[r.sev]}" if r.sev is not None else "empacotamento"
        perfis = ", ".join(r.perfis) if r.perfis else "todos"
        linhas.append(f"| {r.id} | {cwe} | {sev} | {r.fonte} | {perfis} | {r.titulo} |")
    return "\n".join(linhas) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pré-scan Veracode determinístico (lente de segurança do code review).")
    ap.add_argument("alvo", nargs="?", help="diretório ou arquivo a analisar")
    ap.add_argument("--perfil", choices=PERFIS, default="maximo")
    ap.add_argument("--desde", metavar="REF", help="só arquivos alterados desde a ref git (diff + não rastreados)")
    ap.add_argument("--json", dest="saida_json", metavar="ARQ")
    ap.add_argument("--md", dest="saida_md", metavar="ARQ")
    ap.add_argument("--falhar", action="store_true", help="exit 1 se houver 🔴")
    ap.add_argument("--incluir-testes", action="store_true")
    ap.add_argument("--listar-regras", action="store_true")
    args = ap.parse_args(argv)
    saida_utf8()
    if args.listar_regras:
        sys.stdout.write(listar_regras())
        return 0
    if not args.alvo:
        ap.error("informe o alvo (diretório ou arquivo)")
    alvo = Path(args.alvo)
    if not alvo.exists():
        print(f"erro: alvo inexistente: {alvo}", file=sys.stderr)
        return 2
    rel = executar(alvo, args.perfil, args.desde, args.incluir_testes)
    texto = json.dumps(rel, ensure_ascii=False, indent=2)
    if args.saida_json:
        Path(args.saida_json).write_text(texto + "\n", encoding="utf-8")
    else:
        print(texto)
    if args.saida_md:
        Path(args.saida_md).write_text(para_markdown(rel), encoding="utf-8")
    r = rel["resumo"]
    print(f"[precheck] {r['veredito_preliminar']} · {r['total']} achado(s) · perfil {args.perfil}", file=sys.stderr)
    return 1 if args.falhar and r["por_severidade"]["🔴"] else 0


if __name__ == "__main__":
    sys.exit(main())
