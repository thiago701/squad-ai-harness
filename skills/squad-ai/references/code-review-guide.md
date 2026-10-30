# Guia de Code Review — 4 Lentes + Template de PR

> Complementa o Protocolo de Review em 5 Passos do `step-05-review.md` (focado em DDD/CQRS/Clean Architecture) com **4 lentes universais** aplicáveis a qualquer PR — especialmente hotfixes, bibliotecas compartilhadas, e código fora do caminho canônico da squad.

## Quando usar este guia

- PR pequeno fora do ciclo completo da squad (correção, ajuste, refactor incremental).
- Avaliação rápida antes de merge quando a Fase 5 completa não se aplica.
- Auditoria de código legado trazido para o padrão da squad.
- Complemento ao step-05-review em projetos onde o fluxo das 6 fases foi pulado.

Para PR que conclui uma User Story dentro do ciclo Discovery→Deliver, use **primeiro** o protocolo completo do `step-05-review.md`. As 4 lentes aqui são filtro universal, não substituto.

## As 4 Lentes

```
┌────────────────────────────────────────────────────────────┐
│  SEGURANÇA       PERFORMANCE       CORRETUDE       MANUT.  │
│  (OWASP + PII)   (N+1, latência)   (edge cases)    (legib) │
└────────────────────────────────────────────────────────────┘
```

Passe o PR por cada lente em ordem. A primeira que sinalizar 🔴 bloqueia — não adianta elogiar legibilidade se tem SQL injection.

### Lente 1 — Segurança (bloqueia merge)

Checklist inspirado no OWASP Top 10 2021/2025 adaptado para Java 25 + Spring Boot 4:

- [ ] **Injeção** — SQL via parâmetros nomeados (JdbcClient, `@Query` com `:param`, JPA Criteria). Zero string concat com input.
- [ ] **XSS / HTML** — saída escapada (Thymeleaf auto-escapa; para JSON usar Jackson default).
- [ ] **CSRF** — habilitado para endpoints `application/x-www-form-urlencoded` e multipart; desabilitado apenas para APIs REST puras com token.
- [ ] **Autenticação** — JWT validado (assinatura + `exp` + `iss` + `aud`); senha via Argon2id (nunca MD5/SHA1/bcrypt em novo código).
- [ ] **Autorização** — verificação por recurso (não só por rota). `@PreAuthorize` com SpEL sobre o recurso, ou PDP/PEP explícito.
- [ ] **Secrets** — `git grep -iE '(password|api[_-]?key|secret|token)\s*[:=]\s*["'\'']'` vazio. Config via env/SSM/Secrets Manager.
- [ ] **PII em logs** — nenhum CPF, email, cartão, token ou senha em `log.info()`. Masking obrigatório (`***@dominio.com`).
- [ ] **Deserialização** — Jackson com `@JsonTypeInfo` restrito; nunca `enableDefaultTyping()` aberto.
- [ ] **SSRF** — chamadas HTTP para URL recebida de usuário passam por allowlist ou `@HttpExchange` com base URL fixa.
- [ ] **Path traversal** — `Files.resolve()` validado contra `normalize()` + `startsWith(basePath)`.
- [ ] **Upload** — tipo/tamanho validados; arquivo salvo com nome gerado (nunca `original`).
- [ ] **Dependências** — OWASP Dependency-Check ou Renovate verde; zero CVE crítica aberta.

**Dica:** automatize. Semgrep rules + spotbugs-security + OWASP DC no CI pegam 70% disso sem leitura manual.

### Lente 2 — Performance

- [ ] **N+1 query** — `@BatchSize`, `JOIN FETCH`, ou `@EntityGraph` quando lista carrega relação. Teste com `@Sql` + contador de queries Hibernate em `application-test.yml`.
- [ ] **Queries sem limite** — toda listagem pública tem `Pageable` obrigatório. `findAll()` sem paginação é 🔴 em repositório de entidade com crescimento.
- [ ] **Índices** — para toda cláusula `WHERE`/`JOIN`/`ORDER BY` em query que aparece em caminho quente, existe índice correspondente (verificar migration).
- [ ] **Complexidade** — nenhum O(n²) em lista que pode crescer além de ~1k. Se for lista curta e estável, OK, mas comente.
- [ ] **Alocação desnecessária** — `new Object[]` em loop quente, `String.format` em log de hot path (use SLF4J com placeholder `{}`), streams aninhados com `toList()` intermediário.
- [ ] **Leaks de recurso** — `try-with-resources` para `Connection`, `InputStream`, `Scanner`. HttpClient reutilizado (não novo por chamada).
- [ ] **Virtual Threads** — I/O-bound: `Executors.newVirtualThreadPerTaskExecutor()` ou `@Async` com `SimpleAsyncTaskExecutor` + `virtualThreads=true`. CPU-bound: pool tradicional com tamanho = núcleos.
- [ ] **Fan-out externo** — `StructuredTaskScope.ShutdownOnFailure` em vez de `CompletableFuture.allOf` manual.
- [ ] **Caching** — justificado com número observado, não especulativo. TTL explícito. Invalidação clara.

### Lente 3 — Corretude

- [ ] **Edge cases** — `null`, lista vazia, string vazia, `Integer.MAX_VALUE`, timezone UTC vs local, charset não-UTF-8.
- [ ] **Race conditions** — estado compartilhado mutável entre threads? Se sim: `ConcurrentHashMap`, `AtomicReference`, ou lock explícito. Transações com `@Transactional` com isolation correto.
- [ ] **Error handling** — exceções capturadas no nível certo; nunca `catch (Exception e) { log.error(...); }` sem rethrow ou ação. `@ControllerAdvice` converte para `ProblemDetail` RFC 9457.
- [ ] **Off-by-one** — `<=` vs `<` em loops, `.subList(from, to)` com `to` exclusivo, paginação `page` 0-based vs 1-based.
- [ ] **Type safety** — nenhum `Object` em API pública; nenhum `Map<String, Object>` como DTO; records com tipos específicos (VO, `UUID`, `BigDecimal` com escala).
- [ ] **Idempotência** — toda ação com efeito colateral externo (pagamento, notificação, comando de outro BC) tem `event_id`/`request_id` como chave natural. Handler rejeita duplicata silenciosamente.
- [ ] **Invariantes do aggregate** — método mutador valida estado resultante antes de commitar (vide Pilar 1 DDD).
- [ ] **Consistência transacional** — Outbox na mesma transação do write principal (nunca em transação separada).

### Lente 4 — Manutenibilidade

- [ ] **Nomes expressivos** — classes substantivas do domínio (`Pedido`, não `PedidoService` se é aggregate); métodos verbos do domínio (`confirmar()`, não `setStatus(CONFIRMED)`).
- [ ] **Responsabilidade única** — cada classe tem um motivo para mudar. Use cases = um por comando/query.
- [ ] **Tamanho** — métodos ≤ 20 linhas, classes ≤ 300 linhas. Aceitar exceções quando justificado por coesão.
- [ ] **Duplicação** — mesma lógica em 3+ lugares vira método/classe. 2 vezes: regra dos três, ainda não.
- [ ] **Testes acompanham** — mudança de comportamento = mudança de teste. Mudança sem teste = 🔴 (falha em TDD).
- [ ] **Comentários** — explicam **porquê**, não **o que**. `// incrementa i` é ruído; `// RFC 9457 exige 'type' como URI` tem valor.
- [ ] **Imports** — zero import `jakarta.*` / `org.springframework.*` / `org.hibernate.*` em `domain/` (ArchUnit vigia).
- [ ] **Features modernas usadas com juízo** — records para VO/DTO, sealed para estados, pattern matching com guards. Mas não force: `switch` exaustivo só quando o domínio é naturalmente fechado.

## Template de Output — PR Review

```markdown
## Code Review: [título do PR ou caminho do arquivo]

### Summary
[2-3 frases: o que o PR faz, qualidade geral, verdict antecipado]

### 🔴 Critical (bloqueia merge)

| # | Arquivo:Linha | Problema | Lente |
|---|---|---|---|
| 1 | `PedidoController.java:42` | SQL concatenado com `pedidoId` de path variable (injection) | Segurança |
| 2 | `PedidoRepository.java:18` | `findAll()` sem paginação em entidade com milhões de linhas (N+1 agregado) | Performance |

### 🟡 Suggestions (corrigir antes de deliver)

| # | Arquivo:Linha | Sugestão | Lente |
|---|---|---|---|
| 1 | `PedidoHandler.java:30` | Converter `if/else` por tipo em `switch` com sealed interface | Manutenibilidade |
| 2 | `PagamentoClient.java:15` | Usar `StructuredTaskScope.ShutdownOnFailure` em vez de `CompletableFuture.allOf` | Performance |

### 🔵 Tech Debt (rastreável)

| # | Arquivo:Linha | Observação |
|---|---|---|
| 1 | `CalculadoraPreco.java` | Lógica de desconto está em use case — candidata a Domain Service |

### ⚪ Estilo / Preferência

| # | Arquivo:Linha | Nota |
|---|---|---|
| 1 | `PedidoTest.java:22` | Assertiva poderia usar `assertThatThrownBy` em vez de `try/catch` |

### What Looks Good

- VOs validados no construtor (Email, Money) aplicam falha rápida correta.
- `@HttpExchange` em vez de RestTemplate manual — segue padrão da squad.
- Testcontainers com Postgres real para repositório — zero mock em I/O.

### Verdict

- [ ] Approve
- [x] Request Changes — 2 🔴 bloqueiam merge (SQL injection + paginação ausente)
- [ ] Needs Discussion — alinhar com Arquiteto Minimalista
```

## Fluxo integrado com step-05

```
PR chega → Tech Lead ativa step-05 (ciclo completo)? 
           ├── Sim (fecha User Story)  → Protocolo 5 Passos completo
           └── Não (hotfix, lib, refactor) → 4 Lentes + template deste guia
```

Mesmo no fluxo reduzido, **os 🔴 do step-05 (domínio sem infra, CQRS, Outbox idempotente) continuam valendo** — são invariantes da squad, não tópicos opcionais.

## Sinais de saúde

- ✅ Revisor lista 🔴 com arquivo:linha e motivo — rastreável.
- ✅ "What Looks Good" tem 3+ itens — feedback positivo reforça padrão.
- ✅ 🔵 viram cards de tech debt no board — não somem no vazio.
- ❌ Review apenas com ⚪ (estilo) — não agregou valor técnico, provavelmente faltou leitura.
- ❌ Review sem verdict explícito — merge incerto, fricção desnecessária.

## Anti-padrões de revisão

- **Rubber stamp** — "LGTM 🚀" sem leitura. Se não há tempo, recusa com honestidade.
- **Bikeshedding** — debate de 40 comentários em ⚪ enquanto 🔴 passa despercebido.
- **Revisor hostil** — tom que ataca pessoa em vez de código. Revisão é sobre melhorar o PR, não sobre ego.
- **Escopo inflado** — "já que mexeu aqui, refaz essa outra coisa". Aceite o escopo do PR; crie card para o resto.

## Relacionadas

- `./step-05-review.md` — protocolo completo das 6 fases
- [[Skill - Tech Lead Review]]
- [[Skill - Engenheiro Seguranca]]
- `references/minimalist-toolkit.md` — heurísticas rápidas
- `references/ddd-guide.md` — invariantes de domínio
