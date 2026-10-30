# Guia de Documentação Técnica — 5 Tipos + 5 Princípios

> Documentação é **código que o leitor humano precisa ler em 5 minutos para fazer algo**. Este guia define os 5 tipos que a Squad AI produz e os princípios de escrita que separam docs úteis de ruído.

## Quando usar este guia

- Fase 6 (Deliver): runbook operacional, README de deploy, onboarding do time de suporte.
- Fase 5 (Review): documentação de ADRs, atualização de docs de API, registro de tech debt.
- Onboarding de novo engenheiro na squad (humano ou agente).
- Toda vez que a squad adicionar contexto que **outra pessoa** precisará consumir em < 90 dias.

A taxonomia aqui é **complementar** ao relatório final consolidado do step-06. Pense assim:
- Relatório final = visão executiva do projeto (1 arquivo, 1 leitura).
- Docs aqui = artefatos operacionais contínuos (múltiplos arquivos, múltiplas leituras).

## Os 5 Tipos

### 1. README (entrada do repositório)

**Leitor:** engenheiro que abre o repo pela primeira vez — humano ou futuro agente.
**Sucesso:** primeira execução local em < 5 minutos.

Seções canônicas:

```markdown
# Nome do Projeto

Uma frase: o que é, para quem, por que existe.

## Quick Start

```bash
git clone ...
./mvnw verify
docker compose up
curl http://localhost:8080/actuator/health
```

## Configuração

Lista de variáveis de ambiente obrigatórias (aponte para `.env.example`).

## Stack

Java 25 + Spring Boot 4 + Aurora PG + Maven 4. Aponte para `ARCHITECTURE.md`.

## Como contribuir

TDD obrigatório, ArchUnit verde, PR com 🔴 bloqueia merge. Aponte para `CONTRIBUTING.md`.

## Links

- Arquitetura: `ARCHITECTURE.md`
- Runbook: `docs/runbook.md`
- ADRs: `.agent/skills/squad-ai/.antigravity/equipe/decisoes/`
```

**Anti-padrão:** README como livro de 800 linhas com história da empresa, filosofia e screenshots de reuniões. Mantenha enxuto; linke o resto.

### 2. API Documentation (contrato público)

**Leitor:** consumidor da API — outro time, cliente externo, frontend.
**Sucesso:** entende um endpoint e testa com `curl` em < 2 minutos.

Estrutura mínima por endpoint:

```markdown
## POST /pedidos

Cria um novo pedido.

### Authentication

`Authorization: Bearer <JWT>` com claim `scope=pedidos:write`.

### Request

Content-Type: `application/json`

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| clienteId | UUID | sim | ID do cliente |
| itens | array | sim | Mínimo 1, máximo 50 |
| itens[].produtoId | UUID | sim | SKU do produto |
| itens[].quantidade | int | sim | 1..999 |

Exemplo:

```json
{
  "clienteId": "4c3a...",
  "itens": [{"produtoId": "a1b2...", "quantidade": 2}]
}
```

### Response

**201 Created**

```json
{
  "id": "8f7e...",
  "status": "CRIADO",
  "total": "199.80",
  "criadoEm": "2026-04-20T14:30:00Z"
}
```

**400 Bad Request** — ProblemDetail RFC 9457

```json
{
  "type": "https://api.example.com/errors/validation",
  "title": "Validation failed",
  "status": 400,
  "detail": "itens.0.quantidade deve ser >= 1"
}
```

### Rate Limit

60 req/min por token. Header `X-RateLimit-Remaining` presente em toda resposta.

### Exemplo curl

```bash
curl -X POST https://api.example.com/pedidos \
  -H 'Authorization: Bearer ...' \
  -H 'Content-Type: application/json' \
  -d '{"clienteId":"...","itens":[{"produtoId":"...","quantidade":1}]}'
```
```

**Preferência da squad:** gerar OpenAPI via `springdoc-openapi-starter-webmvc-ui` e publicar `/v3/api-docs` em staging. A doc humana em Markdown complementa com exemplos, rate limits, e raciocínio — o que OpenAPI não captura.

### 3. Runbook (procedimento operacional)

**Leitor:** on-caller às 3h da manhã com alerta tocando.
**Sucesso:** encontra a ação certa em < 60 segundos; executa sem pedir ajuda.

Estrutura obrigatória:

```markdown
## Runbook — [Nome do alerta/cenário]

**Severidade:** P1 | P2 | P3 | P4
**Quando usar:** "Alerta Y disparou" | "Lag do Outbox > 5 min" | "5xx > 1%"

### Pré-requisitos

- Acesso AWS: role `ReadOnlyProd` mínimo; `OpsProd` para ações.
- Credenciais configuradas: `aws sts get-caller-identity`.
- VPN ativa (se acesso a subnet privada).

### Diagnóstico em 3 comandos

```bash
# 1. Estado atual
aws logs tail /aws/ecs/pedidos-api --since 10m --filter-pattern ERROR

# 2. Lag do Outbox
psql $AURORA_URL -c "SELECT count(*) FROM outbox_events WHERE sent_at IS NULL;"

# 3. Saturação de pool
curl https://api.example.com/actuator/metrics/hikaricp.connections.active
```

### Procedimento

1. **Identifique o sintoma** — cruze dashboard de latência com log de erros dos últimos 15 min.
2. **Aplique mitigação** — role novamente versão N-1 via `./scripts/rollback.sh` (testado em staging toda sprint).
3. **Confirme** — espere 2 min, rode diagnóstico novamente.
4. **Comunique** — `#incidentes` com resumo (1 parágrafo).

### Rollback

```bash
./scripts/rollback.sh <tag-anterior>
# Esperar 5 min e validar /actuator/health/readiness verde em 3 tasks seguidas.
```

### Escalação

- Primeiros 30 min: on-caller da squad.
- 30-60 min: Tech Lead (@thiago).
- > 60 min: VP Eng + comunicação aos stakeholders.

### Histórico de uso

| Data | Incidente | Duração | Lições |
|---|---|---|---|
| 2026-03-12 | Outbox lag 20min após deploy | 18min | Migration lenta; adicionada em passo separado |
```

**Regra:** runbook **sem histórico de uso** é teórico. Sem ensaio trimestral, é ficção.

### 4. Architecture Documentation (visão do sistema)

**Leitor:** engenheiro que entrará no projeto; arquiteto avaliando integração; segurança em auditoria.
**Sucesso:** entende em 15 min o que o sistema faz, como se comunica, e as decisões-chave.

Conteúdo mínimo:

```markdown
# Arquitetura — pedidos-api

## Contexto (C4 nível 1)

[Diagrama C4 — Sistema no ecossistema]

Pedidos-api atende frontend web e mobile via REST; consome Catalogo-api e publica
eventos em SQS para Financeiro-api e Notificacoes-api.

## Containers (C4 nível 2)

[Diagrama C4 — Containers]

- **pedidos-api** (Spring Boot 4 / ECS Fargate) — porta 8080, escrita+leitura no mesmo processo.
- **Aurora PG 16** — write/read. Outbox como tabela.
- **Outbox Relay** (Debezium) — CDC → SQS.

## Componentes (C4 nível 3 — domínio Pedidos)

```
domain/Pedido (Aggregate Root)
  ├── VOs: ClienteId, Money, ItemPedido
  ├── Events: PedidoCriado, PedidoConfirmado, PedidoCancelado
  └── Invariantes: I1..I4

application/
  ├── CriarPedidoCommand + Handler
  ├── ConfirmarPedidoCommand + Handler
  └── ListarPedidosQuery + Handler

infrastructure/
  ├── PedidoJpaRepository (JPA adapter)
  └── CatalogoHttpClient (@HttpExchange)
```

## Fluxo de dados — "Criar Pedido"

1. Cliente → POST /pedidos (JWT validado por Spring Security)
2. Controller → CriarPedidoCommand
3. Handler (transação @Transactional):
   a. Valida itens contra Catalogo-api (HTTP fan-out com StructuredTaskScope)
   b. Constrói Pedido aggregate (valida invariantes)
   c. Repository.save() → INSERT em `pedidos`
   d. OutboxGateway.append(PedidoCriado) → INSERT em `outbox_events` (mesma tx)
4. Commit atômico.
5. Outbox Relay (assíncrono) → publica em SQS.

## Decisões-chave

- ADR-0001: CQRS in-process (não distribuído) — carga 200 RPS não justifica infra extra.
- ADR-0003: Outbox Pattern com Debezium — consistência eventual para integração externa.
- ADR-0007: Aurora Serverless v2 em dev/staging — custo; prod com provisioned.

## Observabilidade

OpenTelemetry OTLP → CloudWatch. Traces com correlation-id propagado via ScopedValue.

## Segurança

- TLS 1.3 obrigatório no ALB.
- JWT HS256 (secret em Secrets Manager rotacionado a cada 90 dias).
- Rate limit 60 req/min/token no API Gateway.
- CSP + HSTS em toda resposta.

## Limites conhecidos

- Picos > 2k RPS exigiriam read replicas — não contemplado nesta fase.
- Outbox relay é single-instance — downtime de até 5 min em troca de deploy.
```

**Fonte canônica:** gere os diagramas C4 via **Structurizr DSL** versionado no repo. Evite PNGs soltos em Confluence — desatualizam silenciosamente.

### 5. Onboarding Guide (ramp-up do novo engenheiro)

**Leitor:** engenheiro novo (humano) OU agente em primeira ativação no projeto.
**Sucesso:** produtivo em < 2 dias.

Estrutura:

```markdown
# Onboarding — squad pedidos

## Dia 1 — Ambiente e Primeira Build

1. Clone: `git clone git@github.com:org/pedidos-api.git`
2. JDK 25: `sdk install java 25-tem`
3. Maven 4: `sdk install maven 4.0.0-rc-3`
4. Docker + Colima (macOS) ou Docker Desktop (Win/Linux).
5. Build: `./mvnw verify` — esperado: todos os módulos verdes, Testcontainers sobe Postgres.
6. Dev local: `docker compose up -d && ./mvnw spring-boot:run -pl bootstrap`.
7. Primeira chamada: `curl localhost:8080/actuator/health` → `{"status":"UP"}`.

## Dia 1 — Leitura essencial (90 min)

- [ ] `README.md` — 5 min.
- [ ] `ARCHITECTURE.md` — 20 min.
- [ ] `GLOSSARIO.md` da squad (linguagem ubíqua) — 15 min.
- [ ] ADR-0001, ADR-0003, ADR-0007 (decisões estruturais) — 30 min.
- [ ] Dois use cases (`CriarPedidoHandler`, `ConfirmarPedidoHandler`) — 20 min.

## Dia 2 — Primeira contribuição

Peça ao Tech Lead um card 🔵 (tech debt pequeno, rastreável). Siga o fluxo:

1. Branch: `feat/<descrição>`.
2. TDD estrito — commit do RED, commit do GREEN, commit do REFACTOR.
3. PR com template `.github/PULL_REQUEST_TEMPLATE.md`.
4. Review via `references/code-review-guide.md` (4 lentes).
5. Merge após ArchUnit verde + 🔴 zerado.

## Quem procurar

| Assunto | Pessoa |
|---|---|
| Dúvida de domínio (regra de negócio) | @especificador / Product Owner |
| Dúvida de DDD / Clean Architecture | @clean-architect |
| Dúvida de performance | @perf |
| Incidente em produção | @devops |

## Primeiros erros comuns e como evitar

- ❌ Editar `domain/` importando `org.springframework.*` → ArchUnit quebra. Use ports em `application/`.
- ❌ `findAll()` sem `Pageable` → 🔴 no review. Pagine sempre.
- ❌ Migration que dropa coluna direto → use Expand-Contract (ADR-0005).
```

## Os 5 Princípios de escrita

### P1 — Escreva para o leitor, não para o autor

Antes de escrever, responda: **quem vai ler isto e em que situação?**

- README: engenheiro impaciente, 5 min de atenção.
- Runbook: on-caller, 30s de paciência.
- ADR: futuro engenheiro daqui a 18 meses tentando entender por quê.

Se a resposta é "ninguém em particular" — o doc provavelmente não precisa existir.

### P2 — Comece pelo mais útil

Não enterre o valor. README começa com quickstart, não com história. Runbook começa com diagnóstico em 3 comandos, não com teoria. A primeira tela do leitor deve resolver 80% das entradas mais comuns.

### P3 — Mostre, não conte

Um exemplo `curl` executável vale mais que três parágrafos descrevendo o endpoint. Um `docker compose up` funcionando vale mais que um manual de instalação. Código > prosa quando ambos podem existir.

### P4 — Mantenha atualizado ou delete

Doc desatualizado é **pior que doc ausente**: induz erro com confiança. Regras práticas:

- Runbook sem ensaio no último trimestre = deprecar.
- API doc com 3+ campos que não existem no código = bug de P1 (não detalhe).
- ADR "Accepted" de 2021 contrariado pela prática atual de 2026 = criar ADR novo superseding, não editar o antigo.

A squad trata doc com as mesmas regras do código: PR de feature toca doc correspondente ou bloqueia no review.

### P5 — Linke, não duplique

Cada informação tem uma **fonte canônica**:

| Tipo de info | Fonte canônica |
|---|---|
| Linguagem ubíqua | `GLOSSARIO.md` |
| Decisão arquitetural | ADR correspondente |
| Padrão de código da squad | `references/*.md` |
| Contrato de API | OpenAPI gerado + doc Markdown |
| Tópicos transversais (Virtual Threads, Outbox, CQRS) | Vault Obsidian + `references/` |

Outros docs linkam para a fonte. Duplicação vira inconsistência em < 6 meses.

## Sinais de saúde

- ✅ README atualizado no mesmo PR que adiciona variável de ambiente nova.
- ✅ Runbook executado por pessoa diferente do autor em ensaio trimestral.
- ✅ ADRs referenciados em code reviews ("ver ADR-0003").
- ✅ Onboarding concluído em ≤ 2 dias pelos últimos 3 novos engenheiros.
- ❌ Doc com data de última edição > 6 meses sem revisão — provavelmente mentira.
- ❌ Dois docs dizendo coisas diferentes sobre o mesmo tópico — escolha um, deprecado ou merge.
- ❌ "Docs" é uma pasta de 50 arquivos sem índice — ninguém encontra nada.

## Anti-padrões

- **Documentação como ritual** — gerada pro auditor e nunca lida. Se não serve a ninguém, não existe.
- **README enciclopédico** — 2000 linhas, 40 seções, ninguém passa da dobra.
- **Runbook teórico** — bonito no papel, nunca ensaiado. Primeiro uso real = descoberta de que não funciona.
- **Doc órfã** — commitada por alguém que saiu, sem dono atual. Crie dono ou delete.
- **Screenshots em tudo** — 6 meses depois a UI mudou. Prefira comandos e texto que sobrevivem a UI.

## Integração com a squad

| Papel | Docs sob sua responsabilidade |
|---|---|
| Especificador | Glossário de domínio, cenários BDD como documentação viva |
| Arquitetos | ARCHITECTURE.md, diagramas C4, ADRs |
| Clean Architect | Padrões de código em `CONTRIBUTING.md` |
| DevOps | Runbook, rollback plan, guia de ambiente |
| Tech Lead | README mantido, índice de ADRs, onboarding |
| Segurança | Threat model, guia de resposta a incidente |

Toda entrega (Fase 6) valida: cada doc acima tem responsável, tem leitor, e foi lido por pelo menos uma pessoa que não o autor antes do merge.

## Relacionadas

- `./step-06-deliver.md` — fase onde runbook e deploy são finalizados
- `references/adr-guide.md` — template de ADR
- `references/code-review-guide.md` — 4 lentes de PR
- [[Skill - Engenheiro DevOps]]
- [[Skill - Tech Lead Review]]
