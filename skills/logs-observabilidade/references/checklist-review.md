# logs-observabilidade · reference — Checklist de review de logs (lente `rev-logs`)

> Hub: `../SKILL.md`. Consumido pelo `tech-lead-review` (PASSO 1c / P1.LOG) e pelo `squad-pipeline` (gatilho
> **logs**). Fonte única das regras: `scripts/logs_obs/regras.py` (`python lint_logs.py catalogo` regenera a
> tabela). Severidades do protocolo do Tech Lead: 🔴 BLOQUEANTE (NOT READY) · 🟡 NECESSÁRIO · 🔵 SUGESTÃO.

## 1. Como a lente roda

```bash
# 1) determinístico — segundos, sem LLM, sem rede. "push" = roda em todo gate; "review" = perfil completo
python -X utf8 skills/logs-observabilidade/scripts/lint_logs.py verificar --raiz . --diff origin/master \
       --perfil completo --falhar-em necessario --saida .claude/pipeline/<slug>/05c-logs
# 2) leitura — itens marcados (leitura) abaixo, só para arquivos que o diff toca
```

Saída: `relatorio.json` com `veredito`, `contagem` e `achados` (trecho **já mascarado**). Mapeamento para o veredito
do Tech Lead: qualquer 🔴 ativo → **NOT READY / REQUER NOVO ROUND** (vazamento de segredo/PII é veto de segurança,
fora de P1>P2>P3, como a lente Veracode); só 🟡 → **AGUARDANDO**; só 🔵 → APROVADO (com observações);
`INCONCLUSIVO` (2) **nunca** vira aprovação — lente muda = `NAO_VERIFICADO`.

Supressão `// log-ok: <motivo>` aparece no relatório: o revisor confere se o motivo é defensável ("token é o nome do
evento de mercado" sim; "é só debug" não).

## 2. Catálogo (mecânico)

| ID | Sev. | Regra | Linguagens | Gate |
|---|---|---|---|---|
| LOG-01 | 🔴 | Segredo em chamada de log | java, kotlin, python, ts | push |
| LOG-02 | 🔴 | Dado pessoal (PII) em log sem máscara | java, kotlin, python, ts | push |
| LOG-03 | 🔴 | Ambiente/configuração inteira em log | java, kotlin, python, ts | push |
| LOG-04 | 🔴 | Segredo literal em artefato de log versionado | artefato | push |
| LOG-05 | 🟡 | PII validada em artefato de log versionado | artefato | push |
| LOG-06 | 🔴 | Wire/HTTP debug ou request-details ligado em perfil não-local | config | push |
| LOG-10 | 🔴 | System.out/System.err/print em código de produção | java, kotlin | review |
| LOG-11 | 🟡 | Exceção logada sem stack trace | java, kotlin, python | review |
| LOG-12 | 🟡 | Concatenação/f-string dentro da chamada de log | java, kotlin, python | review |
| LOG-13 | 🟡 | Request/headers/body inteiro em log | java, kotlin, python, ts | review |
| LOG-14 | 🔵 | Mensagem sem evento nomeado | java, kotlin, python, ts | review |
| LOG-15 | 🟡 | Nível de log inadequado para o evento | (leitura) | review |
| LOG-16 | 🟡 | Log em loop/alto volume sem agregação ou amostragem | (leitura) | review |
| LOG-20 | 🟡 | Appender sem encoder JSON estruturado | config | review |
| LOG-21 | 🟡 | Layout de texto sem neutralização de CRLF (log forging, CWE-117) | config | review |
| LOG-22 | 🟡 | Sem identificadores de correlação no log | config (+ leitura) | review |
| LOG-23 | 🟡 | Unified Service Tagging ausente | (leitura de IaC/env) | review |
| LOG-24 | 🔵 | Sem política de retenção/custo declarada | (leitura de IaC) | review |
| LOG-25 | 🔵 | Sem rede de segurança de redação no destino | (leitura de IaC) | review |
| LOG-26 | 🟡 | MDC/ThreadLocal com Virtual Threads/async sem propagação | (leitura) | review |

Heurísticas declaradas do linter (para o revisor saber o que **não** está coberto): identificador é segredo quando a
**última** palavra é `senha|password|secret|token|jwt|bearer|cookie|authorization|credential|cvv` ou par
`api_key|access_key|secret_key|private_key|client_secret` (`tokenCount`, `passwordHash`, `tokenService` não);
é PII quando contém `cpf|cnpj|cartao|pan|email|telefone|phone|endereco|address|nascimento|rg|passaporte|cep|salario`
ou par `card_number|credit_card|numero_cartao` (`model_card`, `ip_address`, `email_service` não); invólucro
`mascar*/mask*/redact*/hash*/sha*/ultimos*/last4(...)` neutraliza; `session_id` **não** é detectado mecanicamente
(sessão de agente ≠ sessão web) — item de leitura em LOG-01; arquivos de teste saem do gate e viram 🔵 no review.

## 3. P1.LOG — checklist de leitura (PASSO 2 do fluxo de 5 passos)

Só para arquivos tocados pelo diff; cada item responde `achado | limpo | não verificado (motivo)` na Auditoria de
Cobertura.

**Vazamento (veto)**
- [ ] LOG-01 (leitura): `sessionId`/cookie de sessão web, connection string, `toString()` de objeto com credencial,
  `HttpHeaders` em exceção propagada ao log.
- [ ] LOG-02 (leitura): objeto de domínio inteiro no log cujo `toString`/record expõe PII; DTO de resposta logado.
- [ ] Resposta de erro ao cliente sem stack/mensagem interna (`spring.web.error.include-stacktrace=never`, ProblemDetail
  sem `e.getMessage()` técnico).

**Eventos e níveis** (`doutrina-eventos.md`)
- [ ] Evento `dominio.entidade.acao` presente no catálogo do serviço; contexto como chave=valor.
- [ ] LOG-15: ERROR só para falha que exige ação; sem ERROR em 404/validação; sem log-and-rethrow em cada camada.
- [ ] LOG-16: nada de INFO por item em loop/stream; DEBUG amostrado (`samplingRate`) ou bufferizado em prod.
- [ ] Linha canônica por requisição (`duracao_ms`, `outcome`, ids, correlação) no `finally`.
- [ ] Eventos de segurança obrigatórios (login ok/falha, autz negada, mudança de credencial, acesso a dado sensível)
  com `usuario_id`, origem, `outcome` — OWASP / PCI DSS 10.2.

**Correlação** (`trace-correlacao.md`)
- [ ] LOG-22: `trace_id`+`span_id`+`correlation_id` em todo log da requisição; `correlation_id` gerado na borda,
  devolvido na resposta e propagado (HTTP/SQS/EventBridge).
- [ ] LOG-26: `@Async`/`CompletableFuture`/executor/VT/`StructuredTaskScope` propagam MDC (`ContextSnapshot`,
  `TaskDecorator`, `getCopyOfContextMap`) ou usam `ScopedValue`; `MDC.remove/clear` em `finally`; Lambda
  `clearState=true`.
- [ ] Header de trace de entrada não confiável descartado na borda pública.

**Destino e custo** (`cloudwatch.md`, `datadog.md`)
- [ ] LOG-23: `POWERTOOLS_SERVICE_NAME` / `DD_SERVICE`+`DD_ENV`+`DD_VERSION` / `service.name` no deploy.
- [ ] LOG-24: log group com `RetentionInDays` e classe consciente; Datadog com exclusion filters/retenção; contadores
  em métrica (EMF/log-based), não em log indexado.
- [ ] LOG-25: data protection policy (`CpfCode-BR`, `Cnpj-BR`, `EmailAddress`, `CreditCardNumber`, `AwsSecretKey`…)
  ou Sensitive Data Scanner ativo — **além** do mascaramento na origem.
- [ ] Lambda: `LogFormat=JSON` + `ApplicationLogLevel`; `logEvent=false` em prod; timestamp RFC3339 UTC.

**Mascaramento** (`mascaramento.md`)
- [ ] Camada 1 (tipo/serializer) presente para toda classe com campo sensível; camada 2 (decorator/filtro) no appender.
- [ ] Teste automatizado "antes → depois" nos pontos que tocam PII; teste de que token sintético é **bloqueado**.
- [ ] Formatos iguais aos canônicos (`***.982.247-**`, `**** **** **** 1111`, `[TOKEN:****6789]`).

## 4. Saída esperada no laudo (`NN-review.md` / `05c-logs.md`)

```
### Lente rev-logs (logs-observabilidade 1.0.0)
veredito: APROVADO | AGUARDANDO | NOT READY | NAO_VERIFICADO     sha_revisado: <sha>
mecânico: 🔴 0 · 🟡 2 · 🔵 3 · suprimidos 1 (motivos conferidos: sim)
leitura (P1.LOG): vazamento=limpo · eventos=achado(LOG-15 x1) · correlação=limpo · destino=não verificado (sem IaC no diff) · mascaramento=limpo
achados:
  🟡 LOG-11 src/main/java/.../PagamentoService.java:88 — getMessage() sem exceção → stack perdido
  🟡 LOG-15 src/main/java/.../PedidoController.java:41 — ERROR em NotFound (fluxo esperado) → WARN/INFO
```
