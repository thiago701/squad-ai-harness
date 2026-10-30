# logs-observabilidade · reference — Filtros de segurança: segredo nunca chega ao log

> Hub: `../SKILL.md`. Regras: LOG-01, LOG-03, LOG-04, LOG-06, LOG-13, LOG-21. Dono da doutrina de segurança:
> `engenheiro-seguranca` (CWE-532/CWE-117, OWASP); lente Veracode: `validacao-veracode`. Esta reference é o
> **mecanismo**: o que bloquear, onde, e como provar.

## 1. Lista "nunca logar" (OWASP Logging Cheat Sheet)

Código-fonte da aplicação · **identificadores de sessão** · **access tokens / JWT / cookies** · senhas (mesmo
erradas) · **connection strings** · chaves criptográficas e outros segredos primários · dados de cartão/conta
bancária · dado pessoal sensível · tudo que exija consentimento. CWE-532 (*Insertion of Sensitive Information into
Log File*): exemplo canônico do que não fazer — `logger.info("Username: " + usernme + ", CCN: " + ccn);`.

Equivalentes que **podem** ir ao log: `token_presente=true`, `token_sufixo=[TOKEN:****6789]`, `kid`, `usuario_id`,
`chave_arn` (ARN de secret, nunca o valor), `vars_presentes=[DB_URL, DD_SITE]` (nomes, nunca valores — LOG-03).

## 2. Quatro barreiras (defesa em profundidade)

### 2.1 Código — revisão + lente determinística (LOG-01/02/03/13)

`python lint_logs.py verificar --raiz . --perfil segredos` roda em **todo push** (`ops/run.py gate`): segredo/PII em
chamada de log, ambiente inteiro, artefato `.log/.jsonl` com credencial. Supressão só com motivo
(`// log-ok: <por quê>`), contada no relatório. No review (`--perfil completo`) somam-se higiene e configuração.

### 2.2 Appender — filtro que **bloqueia** antes de formatar (Java)

```java
public final class FiltroSegredos extends TurboFilter {          // templates/java/FiltroSegredos.java
    private static final Pattern SEGREDO = Pattern.compile(
        "(?i)(authorization\\s*[:=]\\s*(bearer|basic)\\s+\\S+|\\beyJ[\\w-]{8,}\\.[\\w-]{8,}\\.[\\w-]{8,}\\b|"
      + "\\b(?:AKIA|ASIA)[0-9A-Z]{16}\\b|-----BEGIN [A-Z ]*PRIVATE KEY-----|\\b(senha|password|secret|api[_-]?key)\\s*[=:]\\s*\\S{3,})");
    @Override public FilterReply decide(Marker m, Logger l, Level lv, String fmt, Object[] args, Throwable t) {
        if (fmt != null && SEGREDO.matcher(fmt).find()) return bloquear(l, "formato");
        if (args != null) for (Object a : args) if (a != null && SEGREDO.matcher(a.toString()).find()) return bloquear(l, "argumento");
        return FilterReply.NEUTRAL;
    }
    private FilterReply bloquear(Logger l, String onde) {   // o próprio bloqueio é um evento de segurança auditável
        LoggerFactory.getLogger("seguranca").warn("log.segredo.bloqueado logger={} onde={}", l.getName(), onde);
        metrics.counter("log_segredo_bloqueado").increment();
        return FilterReply.DENY;
    }
}
```
`<turboFilter class="exemplo.observabilidade.FiltroSegredos"/>` no `logback-spring.xml`. Diferença para o
mascaramento: **segredo não é mascarado, é negado** — e o bloqueio vira métrica/alerta (`dd-monitors`), porque
indica bug no código. PII é mascarada (`mascaramento.md`); segredo é barrado.

Python: `logging.Filter` que devolve `False` + `logger.warning("log.segredo.bloqueado")` em um logger separado
(`templates/python/logging_json.py`).

### 2.3 Configuração — loggers perigosos (LOG-06)

| Configuração | Risco | Produção |
|---|---|---|
| `logging.level.org.apache.http.wire` / `org.apache.hc.client5.http.wire` / `reactor.netty.http.client` = DEBUG\|TRACE | corpo e headers (Authorization, Cookie) de toda chamada | `OFF`/`INFO` |
| `spring.mvc.log-request-details=true` / `spring.http.codecs.log-request-details=true` | headers e corpo das requisições | `false` (default) — só profile `local` |
| `logging.level.org.springframework.security=DEBUG\|TRACE` | detalhes de autenticação/tokens | `INFO` |
| `org.hibernate.orm.jdbc.bind=TRACE` / `spring.jpa.show-sql=true` | valores de bind (CPF, e-mail) no stdout | `OFF`/`false` |
| OpenFeign `loggerLevel: FULL\|HEADERS` | headers de autenticação de saída | `NONE`/`BASIC` |
| `@Logging(logEvent=true)` / `POWERTOOLS_LOGGER_LOG_EVENT=true` | evento inteiro (pode ter PII/token) | `false` |
| `logging.level.root=DEBUG` | tudo acima de uma vez | `INFO` |
| `spring.web.error.include-stacktrace=always` (SB4; `server.error.*` no SB3) / `include-message=always` | stack e mensagem interna para o **cliente** | `never` + ProblemDetail |

Isole em `---`/`on-profile: local` ou `application-local.yml`; o linter ignora esses e reprova no perfil padrão.

### 2.4 Repositório e artefatos — scanners (LOG-04)

- `gitleaks` (`[extend] useDefault=true`, `.gitleaks.toml` do repo) no histórico e no diff (já em `ops/run.py security`);
  fixtures sintéticas entram na allowlist **por caminho exato**, nunca pasta inteira.
- `detect-secrets scan --baseline .secrets.baseline` + `audit` como segunda opinião (plugins AWSKey, JwtToken,
  PrivateKey, KeywordDetector, Base64/HexHighEntropy); `trufflehog --results=verified` quando se precisa saber se a
  credencial **ainda vale**.
- `lint_logs.py` varre `.log/.jsonl/.ndjson` versionados (snapshots de teste, telemetria local) com os mesmos
  detectores do `mascara.py` — segredo = 🔴 LOG-04, PII validada = 🟡 LOG-05.
- Achado real em artefato = **incidente**: apagar do repo + rotação (`security/credential-rotation.md`) + corrigir origem.

## 3. Log forging / CRLF (CWE-117, LOG-21)

Entrada externa logada em texto permite injetar `\n2026-10-27 INFO auth.login.ok usuario=admin` e forjar linhas.

- **JSON estruturado resolve por construção** (o encoder escapa `\n`); é o motivo principal de LOG-20.
- Texto (profile local): Logback `%replace(%msg){'[\r\n]', '_'}`; Log4j2 `%enc{%m}{CRLF}`; na borda
  `valor.replaceAll("[\r\n]", "_")` / `mascara.neutralizar_crlf`.
- Veracode CWE-117: "encode any input from users that is written to the log" — ESAPI logger ou `replaceAll`; a
  lente `validacao-veracode` aceita as duas formas. Semgrep oficial: `java.lang.security.audit.crlf-injection-logs`
  (`Logger` + `HttpServletRequest` no mesmo método) — útil no perfil `completo`.
- Também: limitar **tamanho** do campo logado (payload de 2 MB no log é DoS do pipeline) e nunca logar
  `HttpServletRequest`/headers/body inteiros (LOG-13).

## 4. Padrões de segredo que o `mascara.py` reconhece (famílias do gitleaks)

| Família | Padrão (resumo) | Exemplo gitleaks |
|---|---|---|
| AWS access key | `\b(AKIA\|ASIA\|AGPA\|AIDA\|AROA\|…)[0-9A-Z]{16}\b` | `aws-access-token` |
| JWT | `eyJ…\.eyJ…\.…` (3 segmentos base64url) | `jwt` |
| Chave privada | `-----BEGIN … PRIVATE KEY-----` | `private-key` |
| GitHub | `ghp_\|gho_\|ghu_\|ghs_\|ghr_[A-Za-z0-9]{36,}`, `github_pat_…` | `github-pat` |
| Slack | `xox[baprs]-…` | `slack-bot-token` |
| OpenAI/Anthropic | `sk-…`, `sk-ant-…` | `openai-api-key`, `anthropic-api-key` |
| Google | `AIza[0-9A-Za-z_-]{35}` | `gcp-api-key` |
| Datadog | `dd_api_key=<32-40 hex>` | — |
| Genérico | `(senha\|password\|secret\|api_key\|token\|authorization\|…)\s*[:=]\s*valor` | `generic-api-key` (entropia 3.5) |
| Credencial em URL | `scheme://user:senha@host` | — |

Chave nova no mundo (ex.: provedor novo de LLM) → adicionar `Detector` em `mascara.py` **com teste** e, se o gitleaks
ainda não cobrir, regra custom no `.gitleaks.toml`.

## 5. Checklist de filtros (review)

- [ ] Lente `lint_logs.py --perfil segredos` verde no diff; supressões com motivo defensável.
- [ ] `FiltroSegredos`/`logging.Filter` de bloqueio registrado no appender de produção; bloqueio gera métrica+alerta.
- [ ] Nenhuma configuração da §2.3 fora de profile local; `include-stacktrace=never`.
- [ ] gitleaks/detect-secrets verdes; fixtures sintéticas alistadas por caminho exato.
- [ ] Texto → `%replace` CRLF; JSON → ok por construção; tamanho de campo limitado; request inteiro nunca.
- [ ] Teste automatizado: logar um token sintético e asserir que o appender **não** o emitiu e que
  `log.segredo.bloqueado` foi emitido.

## Fontes

- OWASP Logging Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html · Log Injection: https://owasp.org/www-community/attacks/Log_Injection
- CWE-532: https://cwe.mitre.org/data/definitions/532.html · CWE-117: https://cwe.mitre.org/data/definitions/117.html · Veracode CWE-117 Java: https://downloads.veracode.com/securityscan/cwe/v4/java/117.html
- Semgrep `crlf-injection-logs`: https://github.com/semgrep/semgrep-rules/blob/develop/java/lang/security/audit/crlf-injection-logs.yaml
- gitleaks (regras/regex): https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml · detect-secrets: https://github.com/Yelp/detect-secrets · trufflehog: https://github.com/trufflesecurity/trufflehog
- Spring Boot properties (`log-request-details`, `spring.web.error.*`): https://docs.spring.io/spring-boot/appendix/application-properties/index.html · Spring MVC logging: https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-servlet/logging.html · OpenFeign `Logger.Level`: https://docs.spring.io/spring-cloud-openfeign/reference/spring-cloud-openfeign.html
- Logback TurboFilter: https://logback.qos.ch/manual/filters.html
