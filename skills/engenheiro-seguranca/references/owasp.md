# Referência — OWASP Top 10 + Spring Security 7 (Access Control, Injection, Auth Failures, Passkeys, DPoP, OWASP 2025, JWT Rotation)

> Parte da skill `engenheiro-seguranca`. Carregue sob demanda. Hub: `../SKILL.md`.
## OWASP Top 10 — Checklist de Auditoria

### A01 — Broken Access Control

```
CHECKLIST:
  □ Autenticação obrigatória em todos os endpoints (exceto /health, /docs)
  □ Autorização baseada em roles (RBAC) ou permissions
  □ Validação de ownership: usuário só acessa seus próprios recursos
  □ Rate limiting por IP e por usuário autenticado
  □ CORS configurado com allowedOrigins explícitos (nunca "*" em produção)
  □ Métodos HTTP restritos (DELETE/PUT protegidos)
  □ Autorização complexa (multi-tenant, ABAC, hierarquias) via PDP/PEP — NÃO hardcoded em @PreAuthorize
```

#### Quando RBAC em @PreAuthorize não é suficiente — PDP/PEP Pattern

A partir de ~50 regras ou qualquer lógica que envolva **atributos do recurso + atributos do usuário + contexto** (horário, IP, tier, hierarquia organizacional), `@PreAuthorize("hasRole(...)")` vira um emaranhado imanutenível. O padrão canônico é **PDP/PEP**:

```
PEP (Policy Enforcement Point)  →  PDP (Policy Decision Point)
  Spring Security filter             OPA / Cedar / Spring Authorization Server
  "Quem está pedindo o quê?"         "Pode ou não pode?"
  deixa passar / bloqueia            aplica política declarativa
```

**Quando usar:**
- Multi-tenant com hierarquia de organizações
- ABAC (atributos) além de RBAC (papéis)
- Políticas versionadas, auditáveis e revisadas por PRs
- Necessidade de testes unitários da política **sem** subir a aplicação

**Escolha: OPA (Open Policy Agent) vs Amazon Verified Permissions (Cedar)**

| Critério | **OPA (Rego)** | **Cedar (AVP)** |
|---|---|---|
| Linguagem | Rego (Datalog-inspired) | Cedar (spec-first, open-source Rust) |
| Deploy | Sidecar ou biblioteca | Managed AWS (AVP) ou self-hosted |
| Testabilidade | `opa test` nativo | `cedar validate` + testes JSON |
| Ecossistema | K8s, Istio, Envoy | AWS IAM Identity Center, AppSync, ALB |
| Recomendação squad | **OPA sidecar** para multi-cloud / on-prem | **AVP** quando já AWS-first + IAM Identity Center |

**Exemplo com OPA sidecar (Java 25):**

```java
@Component
public class OpaAuthorizationManager implements AuthorizationManager<RequestAuthorizationContext> {

    private final RestClient opa = RestClient.builder()
        .baseUrl("http://localhost:8181")  // sidecar
        .build();

    @Override
    public AuthorizationDecision check(Supplier<Authentication> auth,
                                       RequestAuthorizationContext ctx) {
        var jwt = (Jwt) auth.get().getPrincipal();
        var input = Map.of(
            "subject", Map.of(
                "id", jwt.getSubject(),
                "roles", jwt.getClaimAsStringList("roles"),
                "tenantId", jwt.getClaim("tenant_id")
            ),
            "resource", Map.of(
                "type", resolveType(ctx.getRequest()),
                "id", resolveId(ctx.getRequest()),
                "tenantId", resolveTenant(ctx.getRequest())
            ),
            "action", ctx.getRequest().getMethod().name().toLowerCase(),
            "context", Map.of(
                "ip", ctx.getRequest().getRemoteAddr(),
                "time", Instant.now().toString()
            )
        );
        var decision = opa.post()
            .uri("/v1/data/authz/allow")
            .body(Map.of("input", input))
            .retrieve()
            .body(OpaDecision.class);
        return new AuthorizationDecision(decision.result());
    }

    record OpaDecision(boolean result) {}
}
```

**Policy (Rego):**

```rego
package authz

default allow := false

# Owner do recurso sempre pode ler/atualizar
allow if {
    input.action in {"get", "put"}
    input.subject.id == input.resource.ownerId
}

# Admin pode tudo dentro do seu tenant
allow if {
    "admin" in input.subject.roles
    input.subject.tenantId == input.resource.tenantId
}

# Horário comercial (exemplo ABAC)
allow if {
    input.action == "post"
    "operator" in input.subject.roles
    hour := time.parse_rfc3339_ns(input.context.time) / 1e9 / 3600 % 24
    hour >= 8
    hour < 18
}
```

**Teste unitário (Rego):**

```rego
package authz_test
import data.authz

test_owner_can_read if {
    authz.allow with input as {
        "subject": {"id": "u1", "roles": [], "tenantId": "t1"},
        "resource": {"ownerId": "u1", "tenantId": "t1"},
        "action": "get",
        "context": {"time": "2026-04-13T10:00:00Z"}
    }
}

test_stranger_cannot_read if {
    not authz.allow with input as {
        "subject": {"id": "u2", "roles": [], "tenantId": "t1"},
        "resource": {"ownerId": "u1", "tenantId": "t1"},
        "action": "get",
        "context": {"time": "2026-04-13T10:00:00Z"}
    }
}
```

**Com Cedar (Amazon Verified Permissions):**

```cedar
// policy.cedar — versionada em Git
permit (
  principal,
  action == Action::"readOrder",
  resource
)
when {
  principal == resource.owner ||
  principal in resource.tenant::"admins"
};
```

Java cliente: `software.amazon.awssdk:verifiedpermissions` → `IsAuthorizedRequest`.

**Pitfalls**:
- **Latência**: chamada ao PDP vira hotpath — usar OPA sidecar em `localhost` (~1ms) ou cache local de 30s para decisões idempotentes.
- **Deny-by-default**: `default allow := false` é obrigatório — falha fechada.
- **Versionar políticas**: tratadas como código (PRs, code review, tests). Nunca edite no console.
- **Decision logs**: habilitar audit log do PDP com `decision_id` correlacionado ao `trace_id` da request.

Ver referência completa: `engenheiro-seguranca/references/pdp-pep-opa.md` (roadmap para próximo release).

```java
// Java — Spring Security
@EnableMethodSecurity
@Configuration
public class SecurityConfig {
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/actuator/health").permitAll()
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated()
            )
            .oauth2ResourceServer(oauth -> oauth.jwt(Customizer.withDefaults()))
            .build();
    }
}
```

---

### A03 — Injection

```
CHECKLIST:
  □ TODAS as queries SQL usam parametrização (PreparedStatement / SQLAlchemy bind)
  □ Zero concatenação de strings para montar queries
  □ Input validation em todas as entradas (tipo, formato, tamanho)
  □ ORM preferido sobre SQL raw quando possível
  □ NoSQL injection prevenido (MongoDB: validação de operadores)
```

```java
// CORRETO — Parametrização obrigatória
@Query("SELECT p FROM Pedido p WHERE p.status = :status AND p.clienteId = :clienteId")
List<Pedido> findByStatusAndCliente(@Param("status") String status, @Param("clienteId") Long clienteId);

// VIOLAÇÃO — SQL injection vulnerável
// String sql = "SELECT * FROM pedidos WHERE status = '" + status + "'"; // NUNCA!
```

```python
# CORRETO
result = await session.execute(
    select(Pedido).where(Pedido.status == status, Pedido.cliente_id == cliente_id)
)

# VIOLAÇÃO
# cursor.execute(f"SELECT * FROM pedidos WHERE status = '{status}'")  # NUNCA!
```

### A07 — Authentication Failures

```
CHECKLIST:
  □ Senhas com hashing forte (Argon2id ou bcrypt com cost ≥ 12) — Argon2id é o padrão 2025+
  □ Passkeys (WebAuthn) para login passwordless sempre que possível
  □ JWT assinado com EdDSA (Ed25519) ou ES256 — nunca HS256 com secret fraco
  □ Token expiration curto (access: 15min, refresh: 7d)
  □ Brute force protection (rate limit + account lockout após N tentativas)
  □ MFA para operações críticas — preferir Passkey, depois TOTP, nunca SMS
  □ Logout invalida token (blacklist ou token rotation)
  □ DPoP (RFC 9449) em endpoints de transferência de valor (pagamento, troca de e-mail)
  □ OAuth 2.1 obrigatório: PKCE em todos os clients, sem implicit/password grants
```

### Passkeys (WebAuthn) — Spring Security 7 nativo

Passkeys são chaves públicas assimétricas resistentes a phishing, vazadas e reutilização.
O Spring Security 7 traz `webAuthn()` como DSL de primeira classe.

```java
@Bean
SecurityFilterChain chain(HttpSecurity http) throws Exception {
    return http
        .webAuthn(w -> w                          // Passkeys nativo (WebAuthn)
            .rpName("Minha Aplicação")
            .rpId("app.empresa.com")              // domínio sem protocolo
            .allowedOrigins("https://app.empresa.com"))
        .formLogin(Customizer.withDefaults())     // fallback para senha durante migração
        .authorizeHttpRequests(a -> a
            .requestMatchers("/webauthn/**", "/login/**").permitAll()
            .anyRequest().authenticated())
        .build();
}
```

**Fluxo de registro (enrollment)**: usuário autenticado aciona `/webauthn/register`, navegador
chama `navigator.credentials.create()`, servidor valida attestation e grava `PublicKeyCredential`
(tabela `webauthn_credentials` com `credentialId`, `publicKey`, `signCount`, `userId`).

**Fluxo de autenticação**: `/webauthn/authenticate` desafia com challenge assinado pela chave
privada (armazenada em Secure Enclave / TPM / YubiKey), servidor valida assinatura contra a
chave pública registrada. **Nenhum segredo trafega pela rede.**

**Por que é superior a TOTP/SMS:**
- Resistente a phishing (domínio está atrelado à chave — site falso não recebe resposta válida)
- Não há shared secret para vazar
- UX sem fricção (Touch ID / Windows Hello / PIN do dispositivo)

### DPoP — Demonstrating Proof of Possession (RFC 9449)

DPoP vincula o access token ao par de chaves do cliente. Mesmo que o token seja roubado em
trânsito ou em log, o atacante não consegue usá-lo sem a chave privada correspondente.

```
FLUXO:
  1. Cliente gera par EC (ES256) em memória no boot
  2. Login → access_token (opaco) + DPoP-bound assinado
  3. Cada requisição inclui header DPoP: JWT assinado com método, URL, nonce, timestamp
  4. Servidor valida:
     - Assinatura do DPoP contra JWK embutida
     - jkt (JWK thumbprint) do token bate com a chave do DPoP
     - Nonce anti-replay (Redis com TTL 60s)
     - Timestamp dentro de janela aceitável (±30s)
```

```java
// Spring Security 7 — resolver de DPoP
public class DPoPBearerTokenResolver implements BearerTokenResolver {
    @Override
    public String resolve(HttpServletRequest request) {
        var dpop = request.getHeader("DPoP");
        if (dpop == null) throw new OAuth2AuthenticationException("missing_dpop");
        DPoPValidator.validate(dpop, request.getMethod(), request.getRequestURL().toString());
        return request.getHeader("Authorization").substring("DPoP ".length());
    }
}
```

**Obrigatório** em: pagamento, mudança de e-mail/senha, geração de chave API, transferência.
**Opcional** em: consultas idempotentes.

### OWASP Top 10 — 2025 Edition (novidades)

A versão 2025 do OWASP Top 10 inclui explicitamente riscos de **IA generativa** (LLM Top 10):

| Risco | Mitigação obrigatória na squad |
|-------|-------------------------------|
| LLM01 — Prompt Injection | Input guardrail (sanitização + intent classifier) antes do modelo |
| LLM02 — Insecure Output Handling | Output guardrail (PII redaction + regex injection + allowlist) |
| LLM03 — Training Data Poisoning | RAG com fontes versionadas e auditadas (nunca dados de usuário direto) |
| LLM04 — Model DoS | Rate limit por usuário + circuit breaker + budget cap no cliente Bedrock |
| LLM05 — Supply Chain | SBOM CycloneDX 1.6 dos modelos + checksum + Provenance SLSA L3 |
| LLM06 — Sensitive Info Disclosure | System prompt com regras LGPD + output filter (CPF/email/token) |
| LLM07 — Insecure Plugin Design | Tools com schema JSON estrito + permission check antes de executar |
| LLM08 — Excessive Agency | Human-in-the-loop para ações destrutivas (DELETE, transferência) |
| LLM09 — Overreliance | Mostrar citações (RAG) + confiança + flag de "não verificado" |
| LLM10 — Model Theft | IAM least privilege no Bedrock + VPC endpoints + logs CloudTrail |

Ver seção de Guardrails de IA abaixo para implementação concreta em Java 25.

### JWT Refresh Token Rotation — Sliding Window

O refresh token rotation garante que tokens roubados sejam invalidados automaticamente.
Cada vez que um refresh token é usado, um novo par (access + refresh) é emitido e o antigo é revogado.

```
FLUXO:
  1. Login → access_token (15min) + refresh_token_v1 (7d) emitidos
  2. Access expira → client envia refresh_token_v1 ao /auth/refresh
  3. Server valida refresh_token_v1, emite:
     → access_token_new (15min) + refresh_token_v2 (7d)
     → refresh_token_v1 é REVOGADO (marcado como usado)
  4. Se alguém tentar usar refresh_token_v1 novamente:
     → TODA a família de tokens é invalidada (reuse detection)
     → Usuário forçado a re-autenticar
```

```java
// Java 25 + Spring Security 7 — Refresh Token Rotation
public sealed interface RefreshResult
    permits RefreshResult.Success, RefreshResult.Revoked, RefreshResult.Expired {

    record Success(String accessToken, String refreshToken) implements RefreshResult {}
    record Revoked(String familyId) implements RefreshResult {}
    record Expired() implements RefreshResult {}
}

@Service
public class TokenRotationService {
    private final RefreshTokenRepository tokenRepo;
    private final JwtTokenProvider jwtProvider;

    public RefreshResult rotate(String currentRefreshToken) {
        var stored = tokenRepo.findByToken(currentRefreshToken)
            .orElseThrow(() -> new InvalidTokenException("Token not found"));

        // Reuse detection — token já foi usado → revogar família inteira
        if (stored.isUsed()) {
            tokenRepo.revokeFamily(stored.familyId());
            return new RefreshResult.Revoked(stored.familyId());
        }

        if (stored.isExpired()) {
            return new RefreshResult.Expired();
        }

        // Marcar token atual como usado
        tokenRepo.markAsUsed(stored.id());

        // Gerar novo par com mesma família
        var newAccess = jwtProvider.generateAccessToken(stored.userId());
        var newRefresh = jwtProvider.generateRefreshToken(stored.userId(), stored.familyId());
        tokenRepo.save(newRefresh);

        return new RefreshResult.Success(newAccess.value(), newRefresh.token());
    }
}
```

**Checklist Refresh Token Rotation:**
- ✅ Refresh token armazenado server-side (banco ou Redis) com `familyId`
- ✅ Token marcado como `used` após rotação (nunca deletado — necessário para reuse detection)
- ✅ Reuse detection: se token já usado → revogar toda a família
- ✅ TTL do refresh token: 7 dias (sliding window — renova a cada uso)
- ✅ Access token curto (15min) — não armazenado server-side
- ✅ Endpoint `/auth/refresh` com rate limiting (máx 1 req/10s por usuário)
- ✅ Audit log de rotações e reuse detection (CloudWatch / structured log)

---

