# validacao-veracode · reference — Catálogo CWE do pré-scan e correções por linguagem

> Parte da skill `validacao-veracode`. Carregue sob demanda. Hub: `../SKILL.md`.
> **Severidade "estimada":** é a severidade que o Veracode Static Analysis costuma atribuir à classe
> do flaw (5 Very High … 0 Informational). O valor real vem do scan — o pré-scan só antecipa.
> **Fonte:** `veracode` = classe que o SAST reporta · `squad` = régua interna da squad (CORS aberto,
> PII em log) que o Veracode pode não reportar, mas que a squad bloqueia · `bancario` = regra de
> domínio financeiro, ativa só com `--perfil bancario` (`contexto-bancario.md`).
> **Perfis:** `todos`, ou a lista de perfis em que a regra roda (KDF em `maximo` e `bancario`).

## 1. Tabela viva das regras

Gerada por `python scripts/veracode_precheck.py --listar-regras` — **regenere esta seção** sempre
que uma regra mudar (o teste `test_toda_regra_tem_caso_positivo` garante que toda regra tem caso
vulnerável provado).

| Regra | CWE | Sev. Veracode (estimada) | Fonte | Perfis | Achado |
|---|---|---|---|---|---|
| J-SQL-01 | CWE-89 | 4 High | veracode | todos | SQL montado por concatenação/StringBuilder/format (SQL Injection) — inclui PartiQL do DynamoDB |
| J-CMD-01 | CWE-78 | 5 Very High | veracode | todos | Execução de comando de SO com argumento dinâmico ou via shell (OS Command Injection) |
| J-PATH-01 | CWE-73 | 3 Medium | veracode | todos | Caminho de arquivo controlado externamente (External Control of File Name or Path) |
| J-XXE-01 | CWE-611 | 4 High | veracode | todos | Parser XML sem desabilitar DTD/entidades externas (XXE) |
| J-DESER-01 | CWE-502 | 4 High | veracode | todos | Desserialização nativa de dado não confiável |
| J-DESER-02 | CWE-502 | 4 High | veracode | todos | Jackson com polimorfismo por nome de classe (gadget chain) |
| J-CRYPTO-01 | CWE-327 | 3 Medium | veracode | todos | Algoritmo criptográfico fraco ou modo ECB |
| J-CRYPTO-02 | CWE-780 | 3 Medium | veracode | todos | RSA sem OAEP |
| J-RAND-01 | CWE-331 | 3 Medium | veracode | todos | PRNG previsível (Insufficient Entropy) |
| J-LOG-01 | CWE-117 | 3 Medium | veracode | todos | Dado da camada de entrada gravado em log sem neutralizar CR/LF (Log Injection) |
| J-LOG-02 | CWE-532 | 3 Medium | squad | todos | Dado sensível enviado ao log (LGPD/PII) |
| J-XSS-01 | CWE-80 | 3 Medium | veracode | todos | Saída HTTP sem encoding de contexto (XSS) |
| J-XSS-02 | CWE-80 | 3 Medium | veracode | todos | JSP ecoando parâmetro sem escape (XSS) |
| J-REDIR-01 | CWE-601 | 3 Medium | veracode | todos | Redirecionamento para URL dinâmica (Open Redirect) |
| J-SSRF-01 | CWE-918 | 3 Medium | veracode | todos | Requisição de saída com URL dinâmica na camada de entrada (SSRF) |
| J-TLS-01 | CWE-295 | 4 High | veracode | todos | Validação de certificado/hostname TLS desligada |
| J-COOKIE-01 | CWE-614 | 2 Low | veracode | todos | Cookie sem atributo Secure |
| J-COOKIE-02 | CWE-1004 | 2 Low | veracode | todos | Cookie sem atributo HttpOnly |
| J-ERR-01 | CWE-209 | 2 Low | veracode | todos | Stack trace exposto (Information Exposure Through an Error Message) |
| J-EXIT-01 | CWE-382 | 2 Low | veracode | todos | System.exit em código de aplicação (J2EE Bad Practices) |
| J-REFL-01 | CWE-470 | 3 Medium | veracode | todos | Reflexão com nome de classe dinâmico na camada de entrada (Unsafe Reflection) |
| J-CSRF-01 | CWE-352 | 3 Medium | veracode | todos | Proteção CSRF desligada |
| J-CORS-01 | CWE-942 | 3 Medium | squad | todos | CORS aberto para qualquer origem |
| J-SPEL-01 | CWE-917 | 4 High | veracode | todos | Expression Language com expressão dinâmica (EL/SpEL Injection) |
| J-EVAL-01 | CWE-95 | 4 High | veracode | todos | ScriptEngine avaliando código dinâmico (Eval Injection) |
| J-TRUST-01 | CWE-501 | 3 Medium | veracode | todos | Dado não validado gravado na sessão (Trust Boundary Violation) |
| J-SPLIT-01 | CWE-113 | 3 Medium | veracode | todos | Cabeçalho/cookie com entrada sem neutralizar CR/LF (HTTP Response Splitting) |
| J-LDAP-01 | CWE-90 | 4 High | veracode | todos | Filtro LDAP montado por concatenação (LDAP Injection) |
| J-XPATH-01 | CWE-643 | 3 Medium | veracode | todos | XPath montado por concatenação (XPath Injection) |
| J-SQL-02 | CWE-89 | 4 High | veracode | todos | Text block SQL formatado com valores (SQL Injection) |
| J-SQL-03 | CWE-89 | 4 High | veracode | todos | MyBatis com ${} (substituição textual, não bind) — SQL Injection |
| J-SQL-04 | CWE-89 | 4 High | veracode | todos | Anotação MyBatis com ${} (SQL Injection) |
| K-SQL-01 | CWE-89 | 4 High | veracode | todos | String template Kotlin com SQL interpolado (SQL Injection) |
| J-NOSQL-01 | CWE-943 | 4 High | veracode | todos | Expressão DynamoDB/Mongo montada por concatenação (NoSQL Injection) |
| J-JWT-01 | CWE-347 | 4 High | veracode | todos | JWT decodificado sem verificação de assinatura no arquivo |
| J-JWT-02 | CWE-347 | 4 High | veracode | todos | JWT aceito sem assinatura (alg none) |
| J-KEY-02 | CWE-321 | 4 High | veracode | todos | Chave criptográfica hardcoded |
| J-IV-01 | CWE-329 | 3 Medium | veracode | todos | IV/nonce fixo ou zerado |
| P-SQL-01 | CWE-89 | 4 High | veracode | todos | SQL montado por f-string/format/concatenação (SQL Injection) |
| P-CMD-01 | CWE-78 | 5 Very High | veracode | todos | Execução de comando via shell (OS Command Injection) |
| P-EVAL-01 | CWE-95 | 5 Very High | veracode | todos | eval/exec de valor dinâmico (Eval Injection) |
| P-DESER-01 | CWE-502 | 4 High | veracode | todos | Desserialização insegura (pickle/yaml/torch) |
| P-TLS-01 | CWE-295 | 4 High | veracode | todos | Verificação TLS desligada |
| P-CRYPTO-01 | CWE-327 | 3 Medium | veracode | todos | Algoritmo criptográfico fraco ou modo ECB |
| P-RAND-01 | CWE-331 | 3 Medium | veracode | todos | PRNG previsível (Insufficient Entropy) |
| P-PATH-01 | CWE-73 | 3 Medium | veracode | todos | Caminho de arquivo controlado externamente |
| P-DEBUG-01 | CWE-489 | 3 Medium | veracode | todos | Modo debug ativo (Active Debug Code) |
| P-SSRF-01 | CWE-918 | 3 Medium | veracode | todos | Requisição de saída com URL dinâmica na camada de entrada (SSRF) |
| P-LOG-01 | CWE-117 | 3 Medium | veracode | todos | Dado da camada de entrada gravado em log sem neutralizar CR/LF (Log Injection) |
| P-XXE-01 | CWE-611 | 4 High | veracode | todos | Parser XML sem proteção contra entidades externas (XXE) |
| P-SSTI-01 | CWE-1336 | 4 High | veracode | todos | Template renderizado a partir de string dinâmica (SSTI) |
| P-XSS-01 | CWE-80 | 3 Medium | veracode | todos | Escape de HTML desligado (XSS) |
| P-TMP-01 | CWE-377 | 2 Low | veracode | todos | Arquivo temporário inseguro (race) |
| P-SQL-02 | CWE-89 | 4 High | veracode | todos | SQL montado em string formatada antes da execução (SQL Injection) |
| P-NOSQL-01 | CWE-943 | 4 High | veracode | todos | Expressão DynamoDB/Mongo montada com valores (NoSQL Injection) |
| P-JWT-01 | CWE-347 | 4 High | veracode | todos | JWT aceito sem verificar assinatura |
| JS-EVAL-01 | CWE-95 | 5 Very High | veracode | todos | eval/Function com código dinâmico (Eval Injection) |
| JS-XSS-01 | CWE-80 | 3 Medium | veracode | todos | Inserção de HTML sem sanitização (XSS) |
| JS-CMD-01 | CWE-78 | 5 Very High | veracode | todos | Execução de comando com string dinâmica (OS Command Injection) |
| JS-SQL-01 | CWE-89 | 4 High | veracode | todos | SQL montado por template/concatenação (SQL Injection) |
| JS-NOSQL-01 | CWE-943 | 4 High | veracode | todos | Consulta NoSQL com objeto vindo direto da requisição (NoSQL Injection) |
| JS-TLS-01 | CWE-295 | 4 High | veracode | todos | Verificação TLS desligada |
| JS-RAND-01 | CWE-331 | 3 Medium | veracode | todos | PRNG previsível (Insufficient Entropy) |
| JS-CRYPTO-01 | CWE-327 | 3 Medium | veracode | todos | Algoritmo criptográfico fraco ou modo ECB |
| JS-REDIR-01 | CWE-601 | 3 Medium | veracode | todos | Redirecionamento para URL vinda da requisição (Open Redirect) |
| JS-PROTO-01 | CWE-1321 | 3 Medium | veracode | todos | Merge de objeto da requisição (Prototype Pollution) |
| JS-PATH-01 | CWE-73 | 3 Medium | veracode | todos | Caminho de arquivo vindo da requisição (Path Traversal) |
| JS-JWT-01 | CWE-347 | 4 High | veracode | todos | JWT aceitando alg none ou ignorando expiração |
| JS-CORS-01 | CWE-942 | 3 Medium | squad | todos | CORS aberto para qualquer origem |
| JS-SQL-02 | CWE-89 | 4 High | veracode | todos | SQL em template literal/concatenação fora de tag segura (SQL Injection) |
| CS-SQL-01 | CWE-89 | 4 High | veracode | todos | SQL montado por interpolação/concatenação (SQL Injection) |
| CS-CMD-01 | CWE-78 | 5 Very High | veracode | todos | Execução de processo com argumento dinâmico (OS Command Injection) |
| CS-DESER-01 | CWE-502 | 5 Very High | veracode | todos | Desserializador inseguro / TypeNameHandling |
| CS-CRYPTO-01 | CWE-327 | 3 Medium | veracode | todos | Algoritmo criptográfico fraco ou modo ECB |
| CS-TLS-01 | CWE-295 | 4 High | veracode | todos | Validação de certificado TLS desligada |
| CS-XXE-01 | CWE-611 | 4 High | veracode | todos | XML com DTD/resolver externo habilitado (XXE) |
| CS-RAND-01 | CWE-331 | 3 Medium | veracode | todos | PRNG previsível (Insufficient Entropy) |
| CS-REDIR-01 | CWE-601 | 3 Medium | veracode | todos | Redirecionamento para URL dinâmica (Open Redirect) |
| CS-XSS-01 | CWE-80 | 3 Medium | veracode | todos | Saída HTML sem encoding (XSS) |
| CS-SQL-02 | CWE-89 | 4 High | veracode | todos | SQL em string interpolada/concatenada (SQL Injection) — inclui Dapper |
| GO-SQL-01 | CWE-89 | 4 High | veracode | todos | SQL montado com Sprintf/concatenação (SQL Injection) |
| X-TLS-01 | CWE-326 | 3 Medium | veracode | todos | Protocolo TLS/SSL obsoleto (TLS 1.0/1.1, SSLv3) |
| X-TLS-02 | CWE-326 | 3 Medium | veracode | todos | Configuração aceita TLS 1.0/1.1 ou política de listener fraca |
| KDF-01 | CWE-916 | 3 Medium | veracode | maximo, bancario | PBKDF2 com poucas iterações (senha quebrável offline) |
| KDF-02 | CWE-916 | 3 Medium | veracode | maximo, bancario | bcrypt com custo abaixo de 12 |
| G-KEY-01 | CWE-321 | 4 High | veracode | todos | Chave privada versionada |
| G-AWS-01 | CWE-798 | 4 High | veracode | todos | Access key AWS no código |
| G-VERACODE-01 | CWE-798 | 5 Very High | veracode | todos | Credencial HMAC da Veracode no código |
| G-CREDS-01 | CWE-798 | 4 High | veracode | todos | Credencial hardcoded |
| G-CREDS-02 | CWE-798 | 4 High | veracode | todos | Credencial em arquivo de configuração |
| BK-DINHEIRO-01 | CWE-1339 | 3 Medium | bancario | bancario | Valor monetário em ponto flutuante (arredondamento binário em dinheiro) |
| BK-DINHEIRO-02 | CWE-682 | 3 Medium | bancario | bancario | Cálculo monetário com BigDecimal impreciso ou sem RoundingMode |
| BK-PAN-01 | CWE-312 | 4 High | bancario | bancario | Número de cartão (PAN válido por Luhn) no código/config — PCI DSS 3.3/3.5 |
| BK-CPF-01 | CWE-359 | 2 Low | bancario | bancario | CPF/CNPJ válido hardcoded (dado pessoal — LGPD) |
| BK-LOG-01 | CWE-532 | 3 Medium | bancario | bancario | Dado protegido por sigilo bancário/PCI enviado ao log |
| BK-BOLA-01 | CWE-639 | 4 High | bancario | bancario | Recurso de conta/cartão/cliente por id sem checagem de titularidade no arquivo (BOLA/IDOR — OWASP API1) |
| BK-MASS-01 | CWE-915 | 3 Medium | bancario | bancario | Entidade preenchida direto com o corpo da requisição (Mass Assignment) |
| BK-IDEMP-01 | CWE-837 | 3 Medium | bancario | bancario | Operação financeira sem idempotência visível (retry = débito em dobro) |
| BK-RACE-01 | CWE-367 | 3 Medium | bancario | bancario | Checagem de saldo/limite antes do débito sem trava (TOCTOU — gasto duplo) |
| BK-TIMING-01 | CWE-208 | 3 Medium | bancario | bancario | Comparação de segredo em tempo variável (timing attack) |
| BK-SESSAO-01 | CWE-613 | 2 Low | bancario | bancario | Sessão ociosa acima de 15 minutos (PCI DSS 8.2.8) |
| BK-HTTP-01 | CWE-319 | 3 Medium | bancario | bancario | Integração em HTTP sem TLS (dado em claro em trânsito) |
| BK-FAPI-01 | CWE-287 | 3 Medium | bancario | bancario | Fluxo OAuth/assinatura fora do perfil FAPI (Open Finance Brasil) |
| BK-CFG-01 | CWE-209 | 2 Low | bancario | bancario | Erro detalhado/stack trace devolvido ao cliente |
| BK-CFG-02 | CWE-200 | 3 Medium | bancario | bancario | Actuator expondo endpoints sensíveis (env, heapdump, shutdown) |
| PKG-01 | — | empacotamento | veracode | todos | Fat-jar shaded: o Veracode tem suporte limitado a dependências shaded |
| PKG-02 | — | empacotamento | veracode | todos | Build sem símbolos de debug: o scan perde arquivo/linha e cobertura |

## 2. Correções por CWE (o que fecha o flaw — não o que o esconde)

### CWE-89 — SQL Injection (J-SQL-01..04 · K-SQL-01 · P-SQL-01/02 · JS-SQL-01/02 · CS-SQL-01/02 · GO-SQL-01)

**Bateria coberta pelos testes** (`tests/test_validacao_veracode.py`, seção "SQL injection"):

| Linguagem | Variantes detectadas | Formas seguras que ficam quietas |
|---|---|---|
| Java | concatenação (inclusive em várias linhas e `AND x = '" + v`), `ORDER BY " + campo`, `StringBuilder.append(...).append(v)`, `String.format`/`MessageFormat.format`/`.formatted`, text block `""".formatted(...)`, JPQL `createQuery` concatenado, **PartiQL do DynamoDB** (`statement("..." + pk)`), MyBatis `${}` em XML e em `@Select` | `?`/`:nome`, `#{}` no MyBatis, PartiQL com `?` + `parameters()`, concatenação com CONSTANTE |
| Kotlin | `"... WHERE id = $id"` (string template) | parâmetros nomeados |
| DynamoDB/Mongo (Java e Python) | `keyConditionExpression("pk = " + pk)`, `FilterExpression=f"..."`, `$where` | `:valor` + `expressionAttributeValues`, `Key`/`Attr` do boto3 |
| Python | f-string, `%`, `.format()` e `+` em SQL antes do `execute`, `text(f"...")` | `execute(sql, params)` com `%s`; f-string sem SQL |
| JS/TS | template literal sem tag, concatenação, `$queryRawUnsafe` | `$1`/`?`, template com tag segura (`sql`, `Prisma.sql`, `$queryRaw`) |
| C# | `$"..."` interpolado (inclui Dapper), concatenação, `FromSqlRaw` | `SqlParameter`, EF Core `FromSql($"...")`/`ExecuteSql`/`SqlQuery<T>` (FormattableString) |
| Go | `fmt.Sprintf`, concatenação em `db.Query` | `$1` + argumentos |

Limite: análise por linha — SQL montado em uma linha e executado em outra arquivo pega a montagem
(boa), mas template literal/text block que quebra a interpolação em várias linhas pode escapar.

```java
// ❌ String sql = "SELECT * FROM conta WHERE id = '" + id + "'";
// ✅ Java 25 + JDBC
try (var ps = con.prepareStatement("SELECT * FROM conta WHERE id = ?")) {
    ps.setLong(1, id);
    try (var rs = ps.executeQuery()) { /* ... */ }
}
// ✅ Spring Data / JPA: @Query("select c from Conta c where c.id = :id") + @Param("id")
// ✅ ORDER BY dinâmico: allowlist fechada — switch (campo) { case "nome" -> "nome"; default -> "id"; }
```

```python
cur.execute("SELECT * FROM conta WHERE id = %s", (conta_id,))          # driver DB-API
session.execute(text("SELECT * FROM conta WHERE id = :id"), {"id": conta_id})  # SQLAlchemy
```

```ts
await db.query('SELECT * FROM conta WHERE id = $1', [id]);   // pg
await prisma.$queryRaw`SELECT * FROM conta WHERE id = ${id}`; // tagged template = parametrizado
```

### CWE-78 — OS Command Injection (J-CMD-01 · P-CMD-01 · JS-CMD-01 · CS-CMD-01)

A correção é **remover o shell** e fechar os argumentos — não "escapar" a string.

```java
var permitido = Set.of("relatorio", "backup");
if (!permitido.contains(acao)) throw new IllegalArgumentException("ação não permitida");
new ProcessBuilder(List.of("/opt/app/bin/" + acao + ".sh")).redirectErrorStream(true).start();
```

```python
subprocess.run(["git", "log", "--oneline", ref], shell=False, check=True, timeout=30)  # ref validado
```

### CWE-117 — Log Injection (J-LOG-01 · P-LOG-01) e CWE-532 — dado sensível em log (J-LOG-02)

O Veracode reporta CWE-117 mesmo com log parametrizado (`{}`): o que fecha é **neutralizar CR/LF**
num método que o scanner reconheça como cleanser — ver `remediacao-e-mitigacao.md` §2
(`@CRLFCleanser`). PII/segredo (CWE-532) não se neutraliza: **não se loga**; use o PII redactor
(`engenheiro-seguranca/references/lgpd-privacidade.md`).

```python
def seguro_para_log(valor: object) -> str:
    return str(valor).replace("\r", "_").replace("\n", "_")
logger.info("cliente %s", seguro_para_log(nome))
```

### CWE-80 — XSS (J-XSS-01/02 · P-XSS-01 · JS-XSS-01 · CS-XSS-01)

```java
response.getWriter().write(org.owasp.encoder.Encode.forHtml(nome));   // cleanser reconhecido
// Thymeleaf th:text / JSP <c:out> já codificam — o problema é th:utext / <%= %>.
```

```ts
el.textContent = comentario;                       // sem HTML
el.innerHTML = DOMPurify.sanitize(htmlConfiavel);  // só se HTML for requisito
```

### CWE-73 / CWE-22 — Caminho controlado externamente (J-PATH-01 · P-PATH-01 · JS-PATH-01)

```java
Path base = Path.of("/srv/uploads").toRealPath();
Path alvo = base.resolve(nome).normalize();
if (!alvo.startsWith(base)) throw new SecurityException("caminho fora da base");
```

```python
base = Path("/srv/uploads").resolve()
alvo = (base / secure_filename(nome)).resolve()
if not alvo.is_relative_to(base):
    raise PermissionError("caminho fora da base")
```

### CWE-611 — XXE (J-XXE-01 · P-XXE-01 · CS-XXE-01)

```java
var f = DocumentBuilderFactory.newInstance();
f.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
f.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
f.setAttribute(XMLConstants.ACCESS_EXTERNAL_DTD, "");
f.setAttribute(XMLConstants.ACCESS_EXTERNAL_SCHEMA, "");
f.setXIncludeAware(false);
f.setExpandEntityReferences(false);
```

Python: `defusedxml.ElementTree.fromstring(xml)`. .NET: `DtdProcessing = DtdProcessing.Prohibit; XmlResolver = null`.

### CWE-502 — Desserialização (J-DESER-01/02 · P-DESER-01 · CS-DESER-01)

```java
// Preferido: JSON com tipos fechados
record PedidoDto(long id, BigDecimal valor) {}
var dto = mapper.readValue(json, PedidoDto.class);
// Se ObjectInputStream for inevitável: filtro por allowlist (JEP 290)
ois.setObjectInputFilter(ObjectInputFilter.Config.createFilter("com.acme.dto.*;java.base/*;!*"));
```

Python: `json`/`pydantic`, `yaml.safe_load`, `torch.load(..., weights_only=True)`.
.NET: `System.Text.Json`, `TypeNameHandling.None`; `BinaryFormatter` está obsoleto e é bloqueante.

### CWE-327 / 328 / 780 — Criptografia fraca (J-CRYPTO-01/02 · P-CRYPTO-01 · JS-CRYPTO-01 · CS-CRYPTO-01)

| Uso | Correto |
|---|---|
| hash de integridade / ID | SHA-256 (Python: `hashlib.sha256`, ou `md5(..., usedforsecurity=False)` se o legado exigir MD5 não criptográfico) |
| cifra simétrica | `AES/GCM/NoPadding` com IV de 12 bytes do `SecureRandom`, nunca reaproveitado |
| RSA | `RSA/ECB/OAEPWithSHA-256AndMGF1Padding` |
| senha | Argon2id (ou bcrypt custo ≥ 12) — nunca hash rápido |

### CWE-331 — Entropia insuficiente (J-RAND-01 · P-RAND-01 · JS-RAND-01 · CS-RAND-01)

`SecureRandom` (Java), `secrets` (Python), `crypto.randomUUID()/getRandomValues()` (JS),
`RandomNumberGenerator` (.NET). Se o uso **não** é de segurança (jitter de retry, amostragem),
mitigue por design com justificativa — o Veracode não distingue o propósito.

### CWE-601 — Open Redirect (J-REDIR-01 · JS-REDIR-01 · CS-REDIR-01)

```java
private static final Set<String> DESTINOS = Set.of("/home", "/conta", "/ajuda");
String destino = DESTINOS.contains(pedido) ? pedido : "/home";
response.sendRedirect(destino);
```

.NET: `LocalRedirect(returnUrl)` ou `Url.IsLocalUrl(returnUrl)`.

### CWE-918 — SSRF (J-SSRF-01 · P-SSRF-01)

Allowlist de **host + esquema**, resolução de DNS checada contra faixas internas (10/8, 172.16/12,
192.168/16, 127/8, 169.254.169.254, `::1`), sem seguir redirect, timeout curto.

### CWE-295 — TLS sem validação (J-TLS-01 · P-TLS-01 · JS-TLS-01 · CS-TLS-01)

Remova o trust-all/hostname-verifier permissivo. CA privada → truststore dedicado
(`-Djavax.net.ssl.trustStore`, `verify="/caminho/ca.pem"`, `ca:` no agente Node).

### CWE-798 / 321 / 259 — Segredos (G-CREDS-01/02 · G-AWS-01 · G-KEY-01 · G-VERACODE-01)

1. **Revogue/rotacione primeiro** — o segredo já vazou no histórico do git.
2. Remova do código **e do histórico** (`git filter-repo`), com aprovação humana (ação destrutiva).
3. Carregue em runtime do cofre: AWS Secrets Manager/SSM (IAM role), Azure Key Vault, Actions Secrets.
4. Credencial Veracode: API **service account** com escopo mínimo; nunca credencial de humano admin.

### CWE-352 — CSRF desligado (J-CSRF-01)

App com sessão/cookie: CSRF ligado. API **stateless só-Bearer** (sem cookie de autenticação):
desligar é aceitável **como mitigação por design**, com a evidência "nenhuma rota autentica por cookie".

### CWE-209 / 382 / 489 — Exposição e práticas ruins (J-ERR-01 · J-EXIT-01 · P-DEBUG-01)

`printStackTrace` → logger + mensagem genérica com id de correlação. `System.exit` → só em `main`
de CLI. `debug=True` → só por variável de ambiente, nunca em produção.

### Demais (J-TRUST-01 · J-SPLIT-01 · J-LDAP-01 · J-XPATH-01 · J-SPEL-01 · J-EVAL-01 · P-EVAL-01 · P-SSTI-01 · JS-EVAL-01 · JS-NOSQL-01 · JS-PROTO-01 · JS-JWT-01 · J-CORS-01 · JS-CORS-01 · J-COOKIE-01/02 · P-TMP-01)

A coluna "correção" da saída do pré-scan traz a ação de uma linha; o princípio é sempre o mesmo:
**dado externo nunca vira código, consulta, expressão, cabeçalho, caminho ou destino sem passar por
validação de allowlist ou encoding do contexto de saída.**

### Regras de domínio bancário (BK-*)

Ativas só com `--perfil bancario`. Motivação, norma correspondente e correção de cada uma:
`contexto-bancario.md` §4.

