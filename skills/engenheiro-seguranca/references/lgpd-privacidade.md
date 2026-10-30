# Referência — LGPD / Privacidade — Testes Automatizados de PII Redaction (Testcontainers + Logback)

> Parte da skill `engenheiro-seguranca`. Carregue sob demanda. Hub: `../SKILL.md`.
## Testes Automatizados de PII Redaction

Garantir que dados sensíveis não vazem em logs é crítico para LGPD/GDPR. Os testes devem validar que **toda saída JSON logada tem campos mascarados**.

### Setup — Fixture com Testcontainers + Logback

```java
// test/java/.../logging/PiiRedactionTest.java
@SpringBootTest
public class PiiRedactionTest {

    private ListAppender<ILoggingEvent> listAppender;

    @BeforeEach
    public void setupLogging() {
        // Criar appender que captura eventos de log em memória
        var logger = (Logger) LoggerFactory.getLogger("ROOT");
        listAppender = new ListAppender<>();
        listAppender.start();
        logger.addAppender(listAppender);
    }

    @AfterEach
    public void teardownLogging() {
        var logger = (Logger) LoggerFactory.getLogger("ROOT");
        logger.detachAppender(listAppender);
    }

    // ── TESTE 1: CPF NUNCA APARECE EM LOGS ────────────────────────────────
    @Test
    void shouldRedactCpfInStructuredLogs() {
        String cpf = "12345678900";
        String cpfFormatted = "123.456.789-00";
        
        log.info("Usuário criado", 
            Map.of("cpf", cpfFormatted, "email", "user@example.com"));

        var event = findLogEventContaining("Usuário criado");
        String message = event.getFormattedMessage();
        
        // CPF nunca aparece em plain
        assertThat(message)
            .doesNotContain(cpf)
            .doesNotContain(cpfFormatted);
        
        // CPF é mascarado
        assertThat(message)
            .contains("12*.***.***-00");  // formato mascarado
    }

    // ── TESTE 2: EMAIL NUNCA APARECE EM LOGS ──────────────────────────────
    @Test
    void shouldRedactEmailInStructuredLogs() {
        String email = "usuario.secreto@empresa.com";
        
        log.info("Login realizado", Map.of("email", email));

        var event = findLogEventContaining("Login realizado");
        String message = event.getFormattedMessage();
        
        assertThat(message)
            .doesNotContain(email)
            .doesNotContain("usuario.secreto")
            .doesNotContain("empresa.com");
        
        // Email é mascarado
        assertThat(message)
            .contains("us***@***om");
    }

    // ── TESTE 3: CARTÃO NUNCA APARECE ────────────────────────────────────
    @Test
    void shouldRedactCreditCardInStructuredLogs() {
        String card = "4111-1111-1111-1111";
        
        log.info("Pagamento processado", Map.of("card", card, "amount", "150.00"));

        var event = findLogEventContaining("Pagamento processado");
        String message = event.getFormattedMessage();
        
        assertThat(message)
            .doesNotContain(card)
            .doesNotContain("4111")
            .doesNotContain("1111");
        
        // Apenas últimos 4 dígitos aparecem
        assertThat(message)
            .contains("****-****-****-1111");
    }

    // ── TESTE 4: TELEFONE NUNCA APARECE ───────────────────────────────────
    @Test
    void shouldRedactPhoneInStructuredLogs() {
        String phone = "(11) 98765-4321";
        
        log.info("Contato armazenado", Map.of("phone", phone));

        var event = findLogEventContaining("Contato armazenado");
        String message = event.getFormattedMessage();
        
        assertThat(message)
            .doesNotContain(phone)
            .doesNotContain("98765")
            .doesNotContain("4321");
        
        // Telefone é mascarado
        assertThat(message)
            .contains("(11) 9****-**21");  // formato típico brasileiro
    }

    // ── TESTE 5: SENHAS/TOKENS NUNCA LOGAM ─────────────────────────────────
    @Test
    void shouldNeverLogPasswordOrToken() {
        String password = "SuperSecretP@ss123";
        String token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...";
        
        // Código nunca deveria logar essas informações
        // Se o desenvolvedor tentar:
        // log.info("Auth token", Map.of("token", token));
        
        // O log estruturado deve omitir completamente
        var clienteDTO = new ClienteDTO(
            id = 1,
            nome = "João",
            password = password,  // Campo @Sensitive
            token = token
        );
        
        // Usar Jackson para serializar
        ObjectMapper mapper = new ObjectMapper();
        String json = mapper.writeValueAsString(clienteDTO);
        
        assertThat(json)
            .doesNotContain(password)
            .doesNotContain(token);
        
        // Ou log como null / [REDACTED]
        assertThat(json)
            .containsPattern("\"password\"\\s*:\\s*(null|\"\\[REDACTED\\]\")");
    }

    // ── TESTE 6: Mapper JSON customizado com MaskingJsonGeneratorDecorator ────
    @Test
    void shouldRedactPiiViaJsonGeneratorDecorator() throws Exception {
        // Usar logstash-logback-encoder com MaskingJsonGeneratorDecorator
        String jsonLog = """
            {
              "message": "Pedido criado",
              "cpf": "123.456.789-00",
              "email": "user@example.com",
              "cartao": "4111-1111-1111-1111",
              "timestamp": "2026-04-10T10:30:00Z"
            }
            """;
        
        ObjectMapper mapper = new ObjectMapper();
        JsonNode logNode = mapper.readTree(jsonLog);
        
        // Aplicar máscaras via regex (conforme logback-spring.xml)
        String cpfValue = logNode.get("cpf").asText();
        String emailValue = logNode.get("email").asText();
        String cardValue = logNode.get("cartao").asText();
        
        // Após aplicação de MaskingJsonGeneratorDecorator:
        assertThat(applyMask(cpfValue, "\\d{3}\\.\\d{3}\\.\\d{3}-\\d{2}"))
            .isEqualTo("***CPF***");
        
        assertThat(applyMask(emailValue, "[\\w.]+@[\\w.]+\\.\\w+"))
            .isEqualTo("***EMAIL***");
        
        assertThat(applyMask(cardValue, "\\d{4}[-\\s]?\\d{4}[-\\s]?\\d{4}[-\\s]?\\d{4}"))
            .isEqualTo("***CARD***");
    }

    // ── TESTE 7: Integração com cliente HTTP — Headers NUNCA logam senhas ────
    @Test
    void shouldNotLogAuthorizationHeaderValues() {
        var req = HttpRequest.newBuilder()
            .uri(URI.create("http://api.example.com/pedidos"))
            .header("Authorization", "Bearer eyJhbGciOiJIUzI1NiIs...")
            .header("X-API-Key", "sk-prod-abcd1234efgh5678")
            .build();
        
        // Usar RestClient com interceptor que redacta headers sensíveis
        // O log nunca deve conter o valor completo
        String loggedRequest = serializeWithRedaction(req);
        
        assertThat(loggedRequest)
            .contains("Authorization: [REDACTED]")
            .contains("X-API-Key: [REDACTED]")
            .doesNotContain("Bearer eyJ");
    }

    // ── HELPER METHODS ─────────────────────────────────────────────────────
    
    private ILoggingEvent findLogEventContaining(String substring) {
        return listAppender.list.stream()
            .filter(event -> event.getFormattedMessage().contains(substring))
            .findFirst()
            .orElseThrow(() -> new AssertionError("Log event not found: " + substring));
    }

    private String applyMask(String value, String pattern) {
        if (Pattern.matches(pattern, value)) {
            return "***MASKED***";  // Exemplo simplificado
        }
        return value;
    }

    private String serializeWithRedaction(HttpRequest req) {
        // Implementação real usaria RestClient + CustomLoggingInterceptor
        return req.toString();
    }
}
```

**Configuração Logback (logback-spring.xml):**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <springProperty name="LOG_FILE" source="logging.file.name" defaultValue="logs/app.log"/>

  <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
    <encoder class="net.logstash.logback.encoder.LogstashEncoder">
      <!-- Aplicar MaskingJsonGeneratorDecorator para redactar PII -->
      <jsonGeneratorDecorator class="net.logstash.logback.mask.MaskingJsonGeneratorDecorator">
        
        <!-- Máscara para CPF: 123.456.789-00 -->
        <valueMask>
          <value>\d{3}\.\d{3}\.\d{3}-\d{2}</value>
          <mask>***CPF***</mask>
        </valueMask>
        
        <!-- Máscara para Email: usuario@example.com -->
        <valueMask>
          <value>[\w.]+@[\w.]+\.\w+</value>
          <mask>***EMAIL***</mask>
        </valueMask>
        
        <!-- Máscara para Cartão: 4111-1111-1111-1111 -->
        <valueMask>
          <value>\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}</value>
          <mask>***CARD***</mask>
        </valueMask>
        
        <!-- Máscara para Telefone: (11) 98765-4321 -->
        <valueMask>
          <value>\(\d{2}\)\s?9?\d{4}-?\d{4}</value>
          <mask>***PHONE***</mask>
        </valueMask>
        
        <!-- Redactar qualquer "password" ou "token" field -->
        <fieldMask>
          <field>password</field>
          <field>token</field>
          <field>api_key</field>
          <field>secret</field>
          <mask>[REDACTED]</mask>
        </fieldMask>
      </jsonGeneratorDecorator>
    </encoder>
  </appender>

  <root level="INFO">
    <appender-ref ref="STDOUT"/>
  </root>
</configuration>
```

**Checklist Testes de PII:**
- ✅ CPF mascarado em logs (exemplo: `12*.***.***-00`)
- ✅ Email mascarado em logs (exemplo: `us***@***om`)
- ✅ Cartão mascarado em logs (exemplo: `****-****-****-1111`)
- ✅ Telefone mascarado em logs (exemplo: `(11) 9****-**21`)
- ✅ Senhas/tokens NUNCA logam — omitir ou `[REDACTED]`
- ✅ MaskingJsonGeneratorDecorator configurado no logback-spring.xml
- ✅ Testes capturam ListAppender e validam saída
- ✅ Integração com RestClient — headers sensíveis redactados



---

