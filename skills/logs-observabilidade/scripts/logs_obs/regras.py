"""Catálogo das regras LOG-xx — fonte única lida pelo linter, pelo checklist de review e pelos evals.

Severidades seguem o protocolo do tech-lead-review:
  🔴 BLOQUEANTE  (NOT READY)   🟡 NECESSÁRIO   🔵 SUGESTÃO   ⚪ OBSERVAÇÃO

Perfis do gate:
  segredos  → só as regras marcadas `gate=True` (vazamento de segredo/PII, exfiltração de ambiente,
              artefato de log com dado sensível). Falso positivo quase zero: é o que roda em todo push.
  completo  → todas as regras (review de PR, Fase 6 do squad-pipeline).
"""
from __future__ import annotations

from dataclasses import dataclass

BLOQ, NEC, SUG, OBS = "🔴", "🟡", "🔵", "⚪"


@dataclass(frozen=True)
class Regra:
    id: str
    severidade: str
    titulo: str
    linguagens: tuple[str, ...]     # java | kotlin | python | ts | config | artefato
    deteccao: str                   # como o linter (ou o revisor) encontra
    correcao: str                   # o que o autor deve fazer
    referencia: str                 # onde a doutrina explica (reference da skill)
    gate: bool = False              # entra no perfil `segredos` (push) ou só em `completo` (review)


REGRAS: tuple[Regra, ...] = (
    # ---------------- vazamento (gate) ----------------
    Regra("LOG-01", BLOQ, "Segredo em chamada de log",
          ("java", "kotlin", "python", "ts"),
          "argumento/placeholder/chave de log casa com senha|password|secret|token|authorization|api_key|"
          "private_key|credential|cookie|session_id|cvv sem invólucro de máscara (mask/mascarar/redact/****)",
          "nunca logar o valor: logue só a existência (`token_presente=true`), o `kid`/4 finais via "
          "`mascarar_token`, ou remova. Segredo em log é CWE-532 e incidente de rotação.",
          "references/filtro-segredos.md", gate=True),
    Regra("LOG-02", BLOQ, "Dado pessoal (PII) em log sem máscara",
          ("java", "kotlin", "python", "ts"),
          "argumento/placeholder/chave casa com cpf|cnpj|cartao|card|pan|email|telefone|phone|endereco|"
          "nome_completo|data_nascimento|rg sem invólucro de máscara",
          "mascarar na origem (serializer/`@Sensitive`/record com toString seguro) e logar id interno "
          "(`cliente_id`) em vez do dado. Formatos canônicos: references/mascaramento.md.",
          "references/mascaramento.md", gate=True),
    Regra("LOG-03", BLOQ, "Ambiente/configuração inteira em log",
          ("java", "kotlin", "python", "ts"),
          "log/print contendo System.getenv( | os.environ | process.env | getProperties() | "
          "Environment.toString | config dump",
          "logue apenas NOMES de variáveis relevantes (`vars_presentes=[DB_URL, DD_SITE]`), nunca valores.",
          "references/filtro-segredos.md", gate=True),
    Regra("LOG-04", BLOQ, "Segredo literal em artefato de log versionado",
          ("artefato",),
          "arquivo .log/.jsonl/.txt de log contém JWT, AKIA…, ghp_…, chave privada, Authorization: Bearer …, "
          "senha=… (detectores de `mascara.py`, categoria segredo)",
          "apague o artefato do repositório, rotacione o segredo (incidente) e corrija a origem do log.",
          "references/filtro-segredos.md", gate=True),
    Regra("LOG-05", NEC, "PII validada em artefato de log versionado",
          ("artefato",),
          "arquivo de log contém CPF/CNPJ com dígito verificador válido, PAN com Luhn válido, e-mail ou telefone",
          "mascarar na origem; artefatos de exemplo usam dados sintéticos inválidos (CPF 000.000.000-00 não passa "
          "no validador, de propósito).",
          "references/mascaramento.md", gate=True),
    Regra("LOG-06", BLOQ, "Wire/HTTP debug ou request-details ligado em perfil não-local",
          ("config",),
          "application*.yml|properties com logging.level.org.apache.http.wire=DEBUG|TRACE, reactor.netty…=DEBUG, "
          "feign Logger.Level.FULL, spring.mvc.log-request-details=true, logging.level.org.springframework.security="
          "DEBUG|TRACE, org.hibernate.orm.jdbc.bind=TRACE, spring.jpa.show-sql=true (fora de profile local/test)",
          "mover para profile `local`; em produção headers Authorization/Cookie e bind params JAMAIS vão ao log.",
          "references/filtro-segredos.md", gate=True),

    # ---------------- higiene e estrutura (completo) ----------------
    Regra("LOG-10", BLOQ, "System.out/System.err/print em código de produção",
          ("java", "kotlin"),
          "System.out.print|System.err.print|printStackTrace( fora de src/test",
          "use o logger (SLF4J) com evento nomeado; `printStackTrace` → `log.error(\"evento\", e)`.",
          "references/doutrina-eventos.md"),
    Regra("LOG-11", NEC, "Exceção logada sem stack trace",
          ("java", "kotlin", "python"),
          "log.error/warn com `e.getMessage()`/`str(e)`/f\"{e}\" sem passar a exceção como último argumento "
          "(Java) ou sem `exc_info=True`/`logger.exception` (Python)",
          "Java: `log.error(\"pagamento.falhou pedido_id={}\", id, e)`; Python: `logger.exception(\"pagamento.falhou\", extra=...)`.",
          "references/doutrina-eventos.md"),
    Regra("LOG-12", NEC, "Concatenação/f-string dentro da chamada de log",
          ("java", "kotlin", "python"),
          "Java: literal + variável dentro de log.x( ; Python: logger.x(f\"…\") | \"…\" % | .format( dentro da chamada",
          "placeholders preguiçosos: Java `{}`; Python `%s` com args — evita custo quando o nível está desligado "
          "e deixa o argumento separado para mascaramento/escape do encoder.",
          "references/doutrina-eventos.md"),
    Regra("LOG-13", NEC, "Request/headers/body inteiro em log",
          ("java", "kotlin", "python", "ts"),
          "log contendo request.getHeader|getHeaders()|headers|requestBody|getBody()|req.body|request.data|"
          "HttpServletRequest|exchange.getRequest()",
          "logue campos escolhidos (método, rota, status, duração, correlation_id); corpo só em DEBUG "
          "com mascaramento e tamanho limitado.",
          "references/filtro-segredos.md"),
    Regra("LOG-14", SUG, "Mensagem sem evento nomeado",
          ("java", "kotlin", "python", "ts"),
          "literal de mensagem é frase livre (sem `dominio.entidade.acao`/snake_case no início e sem chave=valor)",
          "comece pelo evento (`pedido.criado`, `pagamento_recusado`) e passe contexto como pares chave=valor "
          "ou campos estruturados — pesquisável em CloudWatch Insights e Datadog.",
          "references/doutrina-eventos.md"),
    Regra("LOG-15", NEC, "Nível de log inadequado para o evento",
          ("java", "kotlin", "python", "ts"),
          "leitura: ERROR para fluxo esperado (validação de entrada, 404), INFO em loop por item, "
          "WARN sem ação possível, DEBUG com dado de negócio",
          "ERROR = exige ação humana/alerta; WARN = degradado mas tolerado; INFO = evento de negócio; "
          "DEBUG = diagnóstico, nunca com PII.",
          "references/doutrina-eventos.md"),
    Regra("LOG-16", NEC, "Log em loop/alto volume sem agregação ou amostragem",
          ("java", "kotlin", "python", "ts"),
          "leitura: log.info dentro de for/while/stream por item em caminho quente",
          "agregue (`itens_processados=1200 falhas=3`), use DEBUG com sampling (Powertools `samplingRate`) "
          "ou métrica (EMF/DogStatsD) em vez de log.",
          "references/cloudwatch.md"),

    # ---------------- correlação e configuração (completo) ----------------
    Regra("LOG-20", NEC, "Appender sem encoder JSON estruturado",
          ("config",),
          "logback*.xml/log4j2*.xml sem JsonEncoder|LogstashEncoder|JsonTemplateLayout e sem "
          "`logging.structured.format` no application; Lambda sem LogFormat JSON",
          "JSON na saída (Spring Boot 4: `logging.structured.format.console=ecs`; Lambda: `LoggingConfig.LogFormat: JSON`"
          " ou Powertools Logger). Texto livre não é pesquisável nem correlacionável.",
          "references/cloudwatch.md"),
    Regra("LOG-21", NEC, "Layout de texto sem neutralização de CRLF (log forging, CWE-117)",
          ("config",),
          "PatternLayout com %msg/%m sem %replace(…){'[\\r\\n]',''} e sem encoder JSON",
          "encoder JSON (escapa por construção) ou `%replace(%msg){'[\\r\\n]', '_'}`; na borda, "
          "`neutralizar_crlf`/`StringEscapeUtils` antes de logar entrada externa.",
          "references/filtro-segredos.md"),
    Regra("LOG-22", NEC, "Sem identificadores de correlação no log",
          ("config", "java", "kotlin", "python"),
          "encoder sem trace_id/span_id/correlation_id (MDC `includeMdcKeyName`, `dd.trace_id`, "
          "`%X{traceId}`); Lambda sem `correlationIdPath`; serviço sem filtro que propaga X-Request-ID/traceparent",
          "Micrometer Tracing + `logging.pattern.correlation`; Datadog `DD_LOGS_INJECTION=true`; "
          "Powertools `@Logging(correlationIdPath=API_GATEWAY_REST)`; Python `contextvars` + filtro.",
          "references/trace-correlacao.md"),
    Regra("LOG-23", NEC, "Unified Service Tagging ausente",
          ("config",),
          "sem service/env/version (DD_SERVICE/DD_ENV/DD_VERSION, `service.name` OTel, `POWERTOOLS_SERVICE_NAME`)",
          "defina as 3 tags em todo deploy — sem elas não há correlação métrica↔log↔trace no Datadog.",
          "references/datadog.md"),
    Regra("LOG-24", SUG, "Sem política de retenção/custo declarada",
          ("config",),
          "LogGroup sem RetentionInDays; Datadog sem exclusion filter para health/debug; sem log-based metric "
          "para contadores de alto volume",
          "retenção explícita por ambiente (prod 90–400 d, dev 7–14 d), classe IA para logs frios, "
          "exclusão de `/health` e DEBUG no índice.",
          "references/cloudwatch.md"),
    Regra("LOG-25", SUG, "Sem rede de segurança de redação no destino",
          ("config",),
          "CloudWatch sem data protection policy; Datadog sem Sensitive Data Scanner nas regras do serviço",
          "ative a policy (EmailAddress, CreditCardNumber, AwsSecretKey…) no log group e o scanner no "
          "índice — última linha, não a primeira: mascare na origem.",
          "references/mascaramento.md"),
    Regra("LOG-26", NEC, "MDC/ThreadLocal com Virtual Threads/async sem propagação",
          ("java", "kotlin"),
          "leitura: MDC.put em filtro + CompletableFuture/@Async/StructuredTaskScope sem copiar contexto; "
          "ScopedValue ausente em Java 25",
          "Java 25: `ScopedValue` para tenant/correlation + `MDC` só na borda; Micrometer `ContextSnapshot` "
          "para executors; nunca confie no MDC dentro de fork.",
          "references/trace-correlacao.md"),
)

POR_ID = {r.id: r for r in REGRAS}
IDS_GATE = tuple(r.id for r in REGRAS if r.gate)


def tabela_markdown() -> str:
    """Renderiza o catálogo como tabela — usado para gerar/validar references/checklist-review.md."""
    linhas = ["| ID | Sev. | Regra | Linguagens | Gate |", "|---|---|---|---|---|"]
    for r in REGRAS:
        linhas.append(f"| {r.id} | {r.severidade} | {r.titulo} | {', '.join(r.linguagens)} | "
                      f"{'push' if r.gate else 'review'} |")
    return "\n".join(linhas)
