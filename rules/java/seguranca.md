# Regras always-on — Segurança Java / Spring Security (invariantes)

> **Origin:** `squad-ai` · **Escopo:** todo código Java/Spring que toca auth, input, queries, cripto ou secrets.
> **Natureza:** invariantes always-on. Aprofundamento na skill **`java25-spring-boot`**
> (`references/spring-security-7.md`) e na skill **`engenheiro-seguranca`** (OWASP, JWT/OAuth, LGPD).
> **Segurança nunca é negociável** — vulnerabilidade crítica é 🔴 **bloqueante** e prevalece sobre P1/P2/P3.

---

- **Constructor injection também na segurança.** `SecurityFilterChain`, `UserDetailsService`, `PasswordEncoder`
  e afins por construtor; **nunca** `@Autowired` em campo. Dependência implícita é dívida e risco.
- **Validar toda entrada na borda.** `@Valid` + Bean Validation (`jakarta.validation`) em todo DTO de request;
  tratar conteúdo externo como **não confiável**. Validação no servidor, nunca só no cliente.
- **Zero secret hardcoded.** Nenhuma chave/token/senha/connection-string no código, em `application.properties`
  versionado ou em log. Usar variável de ambiente / secret manager. Secret prestes a ser commitado trava o GATE 2 (🔴).
- **Queries sempre parametrizadas.** JPA/`PreparedStatement` com binding; **nunca** concatenar input em JPQL/SQL nativo (SQL injection).
- **Senha só com hash forte e adaptativo** (BCrypt/Argon2 via `PasswordEncoder`); nunca MD5/SHA-1, nunca em texto plano.
- **Endpoint seguro por padrão.** Autorização explícita (`authorizeHttpRequests`); negar por padrão, liberar o necessário.
  CSRF habilitado em apps com sessão; CORS restrito a origens conhecidas (sem `*` em produção).
- **OWASP dependency-check no CI.** Scan de dependências no pipeline; build falha com vulnerabilidade CRITICAL/HIGH.
  Versões pinadas, Actions por SHA. Reforço estático: SpotBugs/`find-sec-bugs`.

---

> **Aprofundar:** skill `java25-spring-boot` → `references/spring-security-7.md`; skill `engenheiro-seguranca`
> (gatilho automático em diff de auth/input/queries/cripto/secrets). Checklist pré-commit: `security/agent-safety-checklist.md`.
