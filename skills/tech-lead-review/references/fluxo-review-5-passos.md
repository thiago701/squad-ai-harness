# tech-lead-review · reference — Fluxo de Review em 5 Passos (checklists completos)

> Conteúdo movido VERBATIM do hub `../SKILL.md` (ciclo 6c do Loop V3, 2026-07-09) — progressive
> disclosure. Inclui os checklists detalhados P1 / P1.DB (dados) / P1.CC (concorrência Java 25) /
> P2 / P3. Os wiki-links `[[...]]` referem-se às skills irmãs do catálogo, como no hub.

### Fluxo de Review em 5 Passos

```
PASSO 1 — CONTEXTO (2 min)
  Entenda antes de julgar:
  - Qual é o requisito de negócio que esta mudança atende?
  - Quais restrições existiam (tempo, legacy, dependências externas)?
  - Qual especialista do ecossistema é mais relevante para esta entrega?

PASSO 1b — LENTE VERACODE (determinística — skill validacao-veracode)
  □ veracode_precheck.py no diff (+ results.json real, se houver) → veracode_gate.py --perfil maximo
  □ BLOQUEADO? → REQUER NOVO ROUND (veto de segurança, fora de P1>P2>P3)
  □ 🔴 herdado do baseline tem card de dívida com prazo?
  □ Supressões têm motivo defensável? Mitigações estão APROVADAS (aprovador ≠ autor)?
  □ Cleanser Veracode novo (@CRLFCleanser, @XSSCleanser…) neutraliza de verdade e tem teste?

PASSO 1c — LENTE DE LOGS (determinística — skill logs-observabilidade)
  □ lint_logs.py verificar --diff <base> --perfil completo --falhar-em necessario → 05c-logs/relatorio.json
  □ 🔴 ativo (LOG-01 segredo / LOG-02 PII / LOG-03 ambiente / LOG-04 artefato / LOG-06 wire DEBUG)? → REQUER NOVO ROUND (veto)
  □ INCONCLUSIVO (2)? → NAO_VERIFICADO — nunca aprova
  □ Supressões `// log-ok: <motivo>` conferidas uma a uma (motivo defensável diante do autor?)

PASSO 1d — LENTE DE MEMÓRIA (determinística, Python — skill python-memoria)
  □ lint_memoria.py no diff → 🟡 = AGUARDANDO; critérios em ../../python-memoria/references/checklist-review.md

PASSO 1e — LENTE DE CLEAN CODE (determinística — referência lente-clean-code.md)
  □ Linter da stack rodou no código tocado (Go: golangci-lint; Python: ruff) com a régua da squad? → 05d-clean.md
  □ Alguma função nova/alterada acima de cognitiva 15 (S3776), ciclomática 15 (S1541) ou 7 parâmetros (S107)? → AGUARDANDO (refatorar ou decisão escrita do dono)
  □ Supressão inline nova (//nolint, lint:ignore, #nosec, # noqa, # ruff: noqa, # mypy: ignore-errors, # complexipy: ignore, NOSONAR, @SuppressWarnings)? Exceção nova na config sem motivo escrito? → AGUARDANDO
  □ Teto afrouxado na config sem ADR com medição? → REQUER NOVO ROUND (🔴; BLOCKER no verificacao-loop)
  □ Ferramenta/config ausente? → NAO_VERIFICADO (MAJOR nomeado), nunca verde

PASSO 2 — VERIFICAÇÃO DAS TRÊS PRIORIDADES (checklist obrigatório)
  P1 - Simplicidade:
    □ Qualquer membro do time entende o código em 10 minutos?
    □ Nomes de variáveis, métodos e classes revelam intenção?
    □ Ausência de lógica condicional densa (> 2 níveis de if)?
    □ Métodos com responsabilidade única (< 20 linhas de regra)?
    □ Ausência de abstrações prematuras (interfaces sem variação real)?

  P1.CLEAN - Clean code no que o linter não vê (consultar [[Skill - Clean Code Craftsman]] e lente-clean-code.md §3–4):
    □ Nomes na linguagem do domínio; escopo curto = nome curto, escopo longo = nome descritivo?
    □ Handler/controlador só adapta; regra de negócio em função pura testável sem mock?
    □ I/O, relógio e aleatoriedade entram por parâmetro/interface (nada de global escondido além das dependências da init)?
    □ Erro tratado uma vez (registra OU propaga com contexto — %w / raise … from), genérico só na fronteira?
    □ Sem flag booleana de comportamento; sem duplicação de regra de negócio; sem parâmetro "para o futuro"?
    □ Valor validado vira tipo (frozen dataclass / NewType / struct com construtor) em vez de dict/map solto?
    □ Comentário explica o porquê; nenhum código comentado?
    □ Testes: um comportamento por teste, nome do cenário, AAA/tabela, provam o efeito?
    □ Refatoração ampla separada da mudança de comportamento (commit/PR próprio, suíte verde antes e depois)?
    □ Código gerado por IA passou pelo roteiro de codigo-gerado-por-ia.md (autor ≠ aprovador)?

  P1.DB - Coerência com Modelo de Dados (consultar [[Skill - Especialista Banco]]):
    □ DBML é a fonte de verdade (mudanças começam por .dbml, nunca por .sql direto)?
    □ JPA Entities refletem fielmente o DBML (nomes, tipos, relacionamentos)?
    □ Domain Entity ≠ JPA Entity (mapper existe e é testado round-trip)?
    □ Flyway migrations coerentes com DBML — validadas por teste de schema coerence
    □ Fetch strategy explícito (LAZY padrão, EAGER somente com justificativa escrita)?
    □ Indexes do DBML presentes nas JPA Entities (@Index) e nas migrations?
    □ Enums do DBML mapeados como @Enumerated(EnumType.STRING) — nunca ORDINAL
    □ @Version para optimistic locking em agregados editáveis concorrentemente
    □ Refatorações destrutivas seguem Expand-Contract (nunca drop+recreate em prod)
    □ Soft delete via @SQLRestriction ou deleted_at, nunca DELETE físico em agregados
    □ ddl-auto=validate em staging/prod (NUNCA update ou create)
    □ Para NoSQL: access patterns documentados ANTES de escolher PK/SK (Single Table Design)
    □ CQRS read model tem política de rebuild (CDC idempotente) caso drift
    □ Outbox Pattern para eventos críticos (pedido pago, envio) — commit atômico
    □ Queries com N+1 detectadas em teste de integração via @SqlMergeMode + assertSelectCount

  P1.CC - Java 25 Concorrência Estruturada (consultar [[Skill - Java25 Spring Boot]]):
    □ Virtual Threads habilitado (spring.threads.virtual.enabled=true) em serviços I/O-bound?
    □ Sem uso de synchronized em regiões que bloqueiam VT (usar ReentrantLock)
    □ Pool HikariCP dimensionado conforme fórmula (RDS max × 0.8 ÷ instâncias)
    □ StructuredTaskScope.open(Joiner) em fan-out (não Executors.newVirtualThreadPerTaskExecutor manual)?
    □ scope.join() ANTES de subtask.get() (nunca get antes de join)
    □ ScopedValue para tenant/correlation em vez de ThreadLocal
    □ Timeout explícito em forks (via Joiner.allUntil ou Structured timeout wrapper)
    □ Ausência de pinning (verificado com -Djdk.tracePinnedThreads=short em staging)

  P1.LOG - Logs por evento, correlação e proteção (consultar [[Skill - Logs Observabilidade]]):
    □ Mensagem começa pelo evento `dominio.entidade.acao` (catálogo do serviço) + contexto chave=valor?
    □ Placeholders `{}`/`%s` (sem concatenação/f-string); exceção como ÚLTIMO argumento; sem printStackTrace/System.out?
    □ Nível semântico: ERROR só quando alguém precisa agir; sem ERROR em 404/validação; sem INFO por item de loop?
    □ Linha canônica por requisição (duracao_ms, outcome, status, ids de negócio) no finally?
    □ trace_id + span_id + correlation_id em TODO log da requisição; correlation_id gerado na borda e propagado (HTTP/SQS/EventBridge)?
    □ MDC propagado em @Async/CompletableFuture/executor/Virtual Threads/StructuredTaskScope (ContextSnapshot/TaskDecorator/ScopedValue); MDC.clear em finally; Lambda clearState=true?
    □ Segredo NUNCA logado (nem mascarado): FiltroSegredos/logging.Filter nega e emite log.segredo.bloqueado?
    □ PII mascarada NA ORIGEM com formato canônico (***.982.247-** / **** **** **** 1111 / t***@dominio) + rede no encoder + teste antes→depois?
    □ Nenhum request/headers/body/DTO/entidade inteiro no log; nenhum System.getenv()/os.environ inteiro?
    □ Config de prod sem wire DEBUG, log-request-details, show-sql, security TRACE, Feign FULL; include-stacktrace=never?
    □ JSON estruturado no destino (Powertools/ALC/structured/LogstashEncoder) — texto só em profile local com %replace CRLF?
    □ Destino: service/env/version (DD_* / POWERTOOLS_SERVICE_NAME); RetentionInDays + classe; data protection policy / Sensitive Data Scanner; exclusion filters?
    □ Eventos de segurança obrigatórios (login ok/falha, autz negada, mudança de credencial, acesso a dado sensível) com usuario_id/origem/outcome?

  P2 - Performance:
    □ SLAs devem ser cumpridos sob carga real?
    □ Ambiente de desenvolvimento é leve (startup rápido, build incremental, feedback instantâneo)?
    □ Operações de I/O (banco, rede) estão fora de loops?
    □ Queries têm índices? N+1 foi evitado?
    □ Caching aplicado onde carga justifica?
    □ Operações assíncronas onde I/O domina?
    □ SLA do endpoint foi medido ou estimado?

  P2.MEM - Memória RAM em Python (consultar [[Skill - Python Memoria]]; lente `lint_memoria.py --falhar-em necessario` no diff):
    □ Caminho quente itera (generators, `for linha in f`, `sum(x for …)`) em vez de materializar (readlines, sum([…]), sorted(x)[0])?
    □ Caches têm limite (lru_cache(maxsize=N)/TTL/deque(maxlen)); nenhum `@cache`/`maxsize=None`/lru_cache em método?
    □ Nada guarda exceção/frames/objeto gordo em coleção; globais que só crescem têm política de descarte?
    □ I/O em blocos (stream/iter_content/fileobj/file_digest); JSON/CSV grande em streaming?
    □ pandas com usecols+dtype(+chunksize), sem iterrows, concat uma vez; ETL grande em polars lazy/DuckDB/parquet?
    □ Instâncias em massa com slots (dataclass(slots=True)/__slots__/msgspec)?
    □ Concorrência com teto (Semaphore/TaskGroup, Queue(maxsize), Pool(maxtasksperchild)); fork com gc.freeze()?
    □ Produção com limite declarado (container memory limit + --max-requests; Lambda MemorySize por Power Tuning)?
    □ Teste de orçamento de memória no caminho que processa arquivo/lote/stream (`with orcamento(max_pico_mb=…)`)?

  P3 - Custo Cloud:
    □ Serviços cloud estão rightsized para a carga atual?
    □ Dados em trânsito entre regiões foram minimizados?
    □ Recursos temporários têm política de expiração?
    □ Pay-per-use preferido a pay-per-hour onde tráfego é irregular?

  P1.SL - Serverless Low-Code, Edge (CloudFront Functions + KVS) & SPA Estática (quando aplicável):
    □ CloudFront Function `.js` está em LF puro e abaixo de 10.176 bytes (margem de 64 B para o limite de 10.240 B) e foi testada localmente em `node vm`?
    □ Rotas virtuais de borda usam método `GET` (Default Cache Behavior bloqueia `POST` com 403) com guarda CSRF (`Sec-Fetch-Site` + `X-Requested-With`)?
    □ Cadastro/alteração de usuários mantém sincronia tripla (`DynamoDB META` ↔ `S3 colaboradores.json` ↔ `CloudFront KVS`)?
    □ Step Functions JSONata usa timezone explícito (`-0300`) em `$now()` / `$fromMillis()`, projeta `Output` enxuto em `Map` inline (< 256 KiB) e tem `TimeoutSeconds <= 28` atrás de HTTP API?
    □ Scripts `aws s3 sync --delete` incluem `--exclude` para todas as views dinâmicas e prefixos de cache no mesmo bucket?
    □ SPA está 100% livre de `innerHTML`/`outerHTML`/`style=` inline (usando `domEl` e classes CSS `--pct`), valida magic bytes em uploads e protege `AbortController` contra corrida em `catch`/`finally`?

PASSO 3 — REVISÃO DE REGRAS DE NEGÓCIO
  □ A lógica implementada corresponde ao requisito aceito?
  □ Casos de borda estão cobertos (null, vazio, limite, concorrência)?
  □ Tratamento de erro é explícito e informativo?
  □ Testes cobrem comportamento do negócio, não implementação?
  □ Existe log de auditoria onde o negócio exige rastreabilidade (evento nomeado + usuario_id + outcome — P1.LOG)?

PASSO 4 — REVISÃO DE ARQUITETURA
  □ Dependências apontam na direção correta (domínio sem infra)?
  □ Responsabilidades estão na camada certa?
  □ Contratos entre módulos/serviços estão explícitos?
  □ A solução é evolutível sem reescrever tudo?
  □ Breaking changes foram identificados e comunicados?

PASSO 5 — VEREDITO COM AÇÃO CLARA
  APROVADO          → merge liberado
  APROVADO COM DEBT → merge liberado + card de tech debt criado obrigatoriamente
  AGUARDANDO        → itens 🟡 a corrigir, sem novo round de review
  REQUER NOVO ROUND → itens 🔴, requer correção + re-review completo
```
