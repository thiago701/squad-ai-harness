# Logs always-on (invariantes — código novo já nasce assim)

> **Pack:** comum (always-on) · **Origin:** `squad-ai` · **Dono:** `logs-observabilidade` (doutrina) +
> `engenheiro-seguranca` (veto). Destilação dos invariantes; o procedimento, os templates e a lente vivem em
> [`skills/logs-observabilidade/SKILL.md`](../../skills/logs-observabilidade/SKILL.md). Não duplicar a skill aqui.

Log é **escrito certo na primeira vez**, não corrigido no review. A Review (`rev-logs`) só **confirma**.

## Invariantes (sempre verdade, em qualquer stack)

- **Evento, não prosa.** Toda mensagem começa pelo evento `dominio.entidade.acao` (catálogo do serviço) e leva
  contexto como `chave=valor`/campos estruturados — nunca frase livre, nunca o objeto inteiro (`toString` vaza).
- **Placeholders, nunca concatenação.** Java `{}`, Python `%s` com args, TS objeto estruturado. Exceção vai como
  **último argumento** (`log.error("pagamento.falhou pedido_id={}", id, e)` / `logger.exception(...)`);
  nunca só `e.getMessage()`, nunca `printStackTrace`/`System.out`/`print` em código de produção.
- **Nível semântico.** `ERROR` = alguém precisa agir (vira alerta); `WARN` = degradado mas tratado; `INFO` = evento
  de negócio; `DEBUG` = diagnóstico, **desligado ou amostrado** em prod. Sem `ERROR` em 404/validação; sem `INFO`
  por item de loop (agregue ou vire métrica).
- **Correlação em todo log.** `trace_id` + `span_id` + `correlation_id` — gerado na borda, devolvido na resposta,
  propagado em HTTP/SQS/EventBridge **e** em código assíncrono (MDC é ThreadLocal: `ContextSnapshot`/
  `TaskDecorator`/`ScopedValue`; `MDC.clear` em `finally`; Lambda `clearState=true`).
- **Segredo nunca — nem mascarado.** Senha, token, JWT, cookie, chave, credencial, connection string, ambiente
  inteiro (`System.getenv()`/`os.environ`) **não entram** no log; o appender tem filtro que **barra** e emite
  `log.segredo.bloqueado`. Pode: `token_presente=true`, `token_sufixo=[TOKEN:****6789]`, nomes de variáveis.
- **PII só mascarada na origem**, formato canônico: CPF `***.982.247-**`, CNPJ `**.222.333/0001-**`, cartão
  `**** **** **** 1111`, e-mail `t***********@exemplo.com`, telefone `+55 (83) *****-1234`. Tipo/record/serializer
  sabe se mascarar (`Mascara.java` / `mascara.py`); encoder tem rede; plataforma tem policy — **as três**.
- **Request inteiro nunca.** Nada de headers/body/payload/`HttpServletRequest` no log — campos escolhidos
  (método, rota, status, `duracao_ms`, `correlation_id`) e **uma linha canônica por requisição** no `finally`.
- **JSON estruturado no destino**, com o nome que o destino entende (`timestamp`, `level`, `message`, `service`,
  `env`, `version`, `dd.trace_id`); texto só em profile `local` com `%replace` de CRLF (log forging).
- **Configuração de prod sem vazamento:** `org.apache.http.wire`/`reactor.netty`/`org.springframework.security` em
  `DEBUG|TRACE`, `log-request-details`, `show-sql`, `hibernate…bind=TRACE`, Feign `FULL|HEADERS`, Powertools
  `logEvent=true`, `include-stacktrace=always` → **só em `local`**. Perfil padrão é produção.
- **Destino declarado na IaC:** `service/env/version`, `RetentionInDays` + classe do log group, data protection
  policy (CloudWatch) ou Sensitive Data Scanner (Datadog), exclusion filters para health/debug.

## O que fazer AO ESCREVER (não depois)

1. **Scaffold:** copie `skills/logs-observabilidade/templates/<stack>/` (Java: `Mascara`, `FiltroSegredos`,
   `MascaraJsonDecorator`, `logback-spring.xml`; Python: `logging_json.py`) e crie o **catálogo de eventos** do
   serviço antes da primeira linha de domínio.
2. **TDD:** todo ponto que toca PII ganha teste **antes → depois** (appender em memória: não contém o dado bruto,
   contém o mascarado); todo serviço ganha teste "token sintético é barrado".
3. **Antes de entregar o arquivo:** `python -X utf8 skills/logs-observabilidade/scripts/lint_logs.py verificar
   --raiz . --arquivos <tocados> --perfil completo --falhar-em necessario` — zero 🔴/🟡, supressão só com
   `// log-ok: <motivo>`. O hook `PostToolUse` (`hooks/scan_secrets.py`) já roda o perfil `segredos` em todo
   arquivo alterado e **para o agente** em 🔴.
4. **Go / Rust / TS sem template:** mesma doutrina com o logger estruturado da stack (`log/slog` JSON + handler de
   máscara; `tracing` + `tracing_subscriber::fmt().json()`; Powertools Logger / pino com `redact`).

> Dúvida de formato, nível ou destino → a skill, não a intuição. Vazamento de segredo/PII em log é **veto G7**,
> fora de P1 > P2 > P3.
