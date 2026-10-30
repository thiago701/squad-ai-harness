# logs-observabilidade · reference — Logs organizados por eventos

> Hub: `../SKILL.md`. Regras: LOG-10, LOG-11, LOG-12, LOG-14, LOG-15, LOG-16 (`scripts/logs_obs/regras.py`).
> Fontes: Stripe canonical log lines · Honeycomb wide events · OTel Logs Data Model/Semantic Conventions ·
> ECS · OWASP Logging Cheat Sheet · AWS Prescriptive Guidance (links no fim).

## 1. Princípio: logue eventos, não prosa

Um log é um **registro de que algo aconteceu**, com nome estável e contexto estruturado — não uma frase para
um humano ler no terminal. A frase "Criando pedido para o cliente informado agora" não é pesquisável, não agrega
e muda a cada refatoração; `pedido.criado pedido_id=p-55010 cliente_id=u-8812` é pesquisável em CloudWatch
Logs Insights (`filter message like /pedido.criado/`), agrupável no Datadog (`@evt.name:pedido.criado`) e
estável entre versões.

```
ERRADO  log.info("Criando pedido para o cliente " + cliente);
CERTO   log.info("pedido.criado pedido_id={} cliente_id={} valor_centavos={}", pedidoId, clienteId, valor);
CERTO   log.atInfo().addKeyValue("event", "pedido.criado").addKeyValue("pedido_id", pedidoId).log();   // SLF4J 2 fluent
```

## 2. Catálogo de eventos (contrato do serviço)

Todo serviço mantém um **catálogo de eventos** (`docs/eventos-log.md` ou enum `LogEvento`) — a mesma disciplina
dos contratos de API. Sem catálogo, cada dev inventa um nome e a busca morre.

| Campo | Regra | Exemplo |
|---|---|---|
| nome | `dominio.entidade.acao`, minúsculas, `snake_case` dentro de cada segmento, **sem valor dinâmico** no nome (OTel: "An event MUST have an event name that uniquely identifies the event structure") | `pagamento.boleto.emitido`, `auth.login.falhou` |
| nível | semântico (§4) | `INFO` |
| campos obrigatórios | ids de negócio em `snake_case`, tipados; nunca o objeto inteiro | `pedido_id`, `cliente_id`, `valor_centavos` |
| campos proibidos | PII bruta e segredo — ver `mascaramento.md` / `filtro-segredos.md` | `cpf`, `token` |
| dono | time/skill responsável por manter | `squad-pagamentos` |

Enum Java (gera nome estável e impede typo):

```java
public enum LogEvento {
    PEDIDO_CRIADO("pedido.criado"), PAGAMENTO_AUTORIZADO("pagamento.autorizado"),
    PAGAMENTO_FALHOU("pagamento.falhou"), AUTH_LOGIN_FALHOU("auth.login.falhou");
    public final String nome;
    LogEvento(String nome) { this.nome = nome; }
}
log.info("{} pedido_id={} cliente_id={}", LogEvento.PEDIDO_CRIADO.nome, pedidoId, clienteId);
```

Com Powertools (Lambda): `log.info("pedido.criado", entry("pedido_id", id), entry("cliente_id", cid))`
(`StructuredArguments.entry` — chaves reservadas são ignoradas com warning). OTel: campo `EventName` do
Log Record; ECS: `event.action`/`event.dataset`; Datadog: `evt.name`/`evt.outcome` (standard attributes).

## 3. Linha canônica (wide event) por requisição

Além dos eventos pontuais, **um evento largo por requisição/invocação**, emitido no `finally` do handler/filtro,
com tudo que um operador perguntaria às 3h da manhã (Stripe: "the authoritative line for a particular request";
Honeycomb: "arbitrarily wide structured event", dezenas de dimensões, alta cardinalidade bem-vinda):

```
http.request.concluido metodo=POST rota=/pedidos status=201 duracao_ms=183 correlation_id=c0ffee-0001
  trace_id=4bf92f35… cliente_id=u-8812 pedido_id=p-55010 db_queries=4 cache=hit versao=1.4.2 regiao=sa-east-1 outcome=success
```

- Campos mínimos: `duracao_ms`, `status`/`outcome` (`success|failure|partial`), `error.type`/`error.message`
  quando falhou, ids de negócio, versão/commit, região/ambiente, `correlation_id`/`trace_id`.
- Emitir **uma vez**, mesmo em exceção (`finally`); não substitui métricas (RED/USE) — complementa.
- Alta cardinalidade (`cliente_id`, `pedido_id`) vai em **logs/traces**; em **métricas** nunca (explosão de séries).

## 4. Níveis semânticos

| Nível | Significa | Exemplos | Anti-exemplo |
|---|---|---|---|
| `ERROR` | invariante quebrada; **alguém precisa agir**; vira alerta | gateway de pagamento fora, dado corrompido, exceção não tratada | 404 de recurso, validação de entrada, token expirado |
| `WARN` | degradado mas **tratado** (retry venceu, fallback, limite perto) | circuit breaker meio-aberto, retry 2/3, quota a 80 % | log-and-rethrow em cada camada (duplica) |
| `INFO` | evento de negócio/ciclo de vida relevante | `pedido.criado`, `app.iniciado`, linha canônica | um INFO por item de loop |
| `DEBUG` | diagnóstico de desenvolvimento; **desligado em prod** (ou amostrado) | payload truncado e mascarado, decisão de cache | PII, segredo, corpo inteiro |
| `TRACE` | só local | — | em produção |

Regras: ERROR exige exceção como último argumento (SLF4J interpreta o último `Throwable` como stack —
`log.error("pagamento.falhou pedido_id={}", id, e)`); nunca `e.getMessage()` sozinho; nunca `printStackTrace`/
`System.out`. Em Python: `logger.exception("pagamento.falhou pedido_id=%s", pid)` dentro do `except`.
Nível mínimo de produção vem do ambiente (`AWS_LAMBDA_LOG_LEVEL`, `POWERTOOLS_LOG_LEVEL`, `logging.level.root`),
nunca `DEBUG` hardcoded no XML.

## 5. Volume: loops, amostragem e buffering

- Nada de `INFO` por item em caminho quente: agregue (`lote.processado itens=1200 falhas=3 duracao_ms=840`).
- `DEBUG` em produção só **amostrado**: Powertools `@Logging(samplingRate = 0.1)` / `POWERTOOLS_LOGGER_SAMPLE_RATE`.
- **Buffering** (Powertools v2): `BufferingAppender` guarda DEBUG e só descarrega quando há ERROR
  (`flushOnErrorLog=true`, `maxBytes=20480`) — custo baixo, diagnóstico completo no erro.
- Contadores de alto volume viram **métrica** (EMF via `@FlushMetrics`, DogStatsD, log-based metric no Datadog),
  não log indexado.
- AWS: "Be careful not to log an excessive amount of data"; considere logar só 4xx/5xx em serviços de borda.

## 6. O que SEMPRE logar (OWASP + PCI DSS 10.2)

Falhas de validação de entrada · autenticação (sucesso **e** falha) · autorização negada · falhas de sessão/JWT ·
erros de aplicação · start/stop · ações administrativas e mudança de credencial/privilégio · acesso a dado
sensível · uso de chaves criptográficas · import/export · upload · falha de desserialização. Cada um com
*quando / onde / quem (id, nunca PII) / o quê / resultado* (`evt.outcome=success|failure`).

## 7. Checklist de revisão (lido pelo `tech-lead-review`)

- [ ] Toda mensagem começa pelo evento `dominio.entidade.acao` e está no catálogo (LOG-14).
- [ ] Contexto como chave=valor / campos estruturados; objeto inteiro nunca (`toString()` vaza).
- [ ] Placeholders `{}`/`%s`, sem concatenação ou f-string (LOG-12).
- [ ] Exceção como último argumento / `logger.exception` (LOG-11); sem `printStackTrace`/`System.out` (LOG-10).
- [ ] Nível semântico correto (LOG-15); sem INFO em loop (LOG-16); DEBUG amostrado/bufferizado em prod.
- [ ] Linha canônica por requisição com `duracao_ms`, `outcome`, ids e correlação.
- [ ] Eventos de segurança da §6 presentes nos pontos de auth/autz.

## Fontes

- Stripe — Canonical log lines: https://stripe.com/blog/canonical-log-lines
- Honeycomb — Structured events are the basis of observability: https://honeycomb.io/blog/structured-events-basis-observability
- OTel Logs Data Model: https://opentelemetry.io/docs/specs/otel/logs/data-model/ · Eventos/naming: https://opentelemetry.io/docs/specs/semconv/general/events/ · https://opentelemetry.io/docs/specs/semconv/general/naming/ · Exceções em logs: https://opentelemetry.io/docs/specs/semconv/exceptions/exceptions-logs/
- Elastic Common Schema (logging): https://www.elastic.co/docs/reference/ecs/logging/intro
- OWASP Logging Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- AWS Prescriptive Guidance — logging best practices: https://docs.aws.amazon.com/prescriptive-guidance/latest/logging-monitoring-for-application-owners/logging-best-practices.html
- SLF4J FAQ (exceção como último parâmetro): https://www.slf4j.org/faq.html#paramException
- Skills da comunidade absorvidas (padrão "log events, not prose", níveis, wide events): addyosmani/agent-skills `observability-and-instrumentation` (MIT, 111k★) · boristane/agent-skills `logging-best-practices` (MIT) · evloghq/evlog `review-logging-patterns` (MIT)
