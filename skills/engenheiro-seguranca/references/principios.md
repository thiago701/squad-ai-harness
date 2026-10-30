# Referência — Princípios Inegociáveis (Defense in Depth, Least Privilege, Input Guilty, Secrets, PII Redaction, IA+Guardrails)

> Parte da skill `engenheiro-seguranca`. Carregue sob demanda. Hub: `../SKILL.md`.
## Princípios Inegociáveis

### 1. Defense in Depth (Defesa em Profundidade)
- Nunca confie em uma única camada de proteção.
- Validação no frontend + backend + banco de dados.
- Autenticação + autorização + rate limiting + logging.
- Se uma camada falhar, a próxima deve segurar.

### 2. Least Privilege (Menor Privilégio)
- Todo componente acessa apenas o mínimo necessário.
- Service accounts com permissões específicas, nunca admin.
- Tokens com escopos limitados e TTL curto.
- Database users com permissões por operação (read-only onde possível).

### 3. Input is Guilty Until Proven Innocent
- TODA entrada do usuário é potencialmente maliciosa.
- Validação de tipo, formato, tamanho e conteúdo em TODA fronteira do sistema.
- Parametrização obrigatória para queries SQL — zero concatenação de strings.
- Output encoding para prevenir XSS.

### 4. Secrets são Radiação — Distância Máxima do Código
- Zero secrets no código-fonte (nem em repos privados).
- Environment variables ou secrets manager (AWS Secrets Manager, Vault).
- Rotação de secrets automatizada quando possível.
- Se vazou, revogue imediatamente — não "depois do deploy".

### 5. PII Redaction — Dados Sensíveis Nunca em Logs

Dados pessoais (PII) em logs são violação de LGPD/GDPR e risco de vazamento.
Toda informação sensível DEVE ser mascarada antes de logar.

```java
// Java 25 — PII Redaction com Pattern Matching em Structured Logging

// 1. Anotação para marcar campos sensíveis
@Target(ElementType.RECORD_COMPONENT)
@Retention(RetentionPolicy.RUNTIME)
public @interface Sensitive {}

// 2. Record com campos sensíveis marcados
public record ClienteDTO(
    Long id,
    String nome,
    @Sensitive String cpf,
    @Sensitive String email,
    @Sensitive String telefone,
    String cidade
) {}

// 3. Redactor que mascara campos @Sensitive automaticamente
public final class PiiRedactor {

    private PiiRedactor() {}

    public static String redact(String value) {
        if (value == null || value.length() < 4) return "***";
        return value.substring(0, 2) + "***" + value.substring(value.length() - 2);
    }

    // Redação de CPF: 123.456.789-00 → 12*.***.***-00
    public static String redactCpf(String cpf) {
        if (cpf == null) return "***";
        return cpf.substring(0, 2) + "*.***.***-" + cpf.substring(cpf.length() - 2);
    }

    // Redação de email: usuario@example.com → us***@***om
    public static String redactEmail(String email) {
        if (email == null) return "***";
        var parts = email.split("@");
        return parts[0].substring(0, 2) + "***@***" + parts[1].substring(parts[1].length() - 2);
    }

    // Redação de cartão: 4111 1111 1111 1111 → ****-****-****-1111
    public static String redactCard(String card) {
        if (card == null || card.length() < 4) return "***";
        return "****-****-****-" + card.substring(card.length() - 4);
    }
}

// 4. Logback layout customizado que intercepta e mascara PII
// Alternativa: usar logstash-logback-encoder com MaskingJsonGeneratorDecorator
```

```yaml
# logback-spring.xml — Mascaramento via regex no encoder JSON
# <encoder class="net.logstash.logback.encoder.LogstashEncoder">
#   <jsonGeneratorDecorator class="net.logstash.logback.mask.MaskingJsonGeneratorDecorator">
#     <valueMask>
#       <value>\d{3}\.\d{3}\.\d{3}-\d{2}</value>    <!-- CPF -->
#       <mask>***CPF***</mask>
#     </valueMask>
#     <valueMask>
#       <value>[\w.]+@[\w.]+\.\w+</value>             <!-- Email -->
#       <mask>***EMAIL***</mask>
#     </valueMask>
#     <valueMask>
#       <value>\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}</value> <!-- Cartão -->
#       <mask>***CARD***</mask>
#     </valueMask>
#   </jsonGeneratorDecorator>
# </encoder>
```

```
CHECKLIST PII REDACTION:
  □ CPF/CNPJ NUNCA em logs (mascarar: 12*.***.***-00)
  □ Email NUNCA em logs (mascarar: us***@***om)
  □ Número de cartão NUNCA em logs (mascarar: ****-****-****-1111)
  □ Telefone NUNCA em logs (mascarar: (11) 9****-**34)
  □ Senhas/tokens NUNCA logados (nem mascarados — omitir completamente)
  □ Endereço IP pode ser logado para auditoria (verificar política local)
  □ Dados médicos (CID, diagnóstico) NUNCA em logs
  □ MaskingJsonGeneratorDecorator configurado no logback-spring.xml
  □ Testes automatizados verificando que PII não aparece em logs
```

### 6. Segurança de IA é Segurança de Software + Guardrails
- Agentes de IA sem guardrails são vulnerabilidades walking.
- Input guardrail: valide e sanitize toda entrada antes de enviar ao LLM.
- Output guardrail: valide toda saída do LLM antes de executar ou exibir.
- Nunca delegue decisões críticas de negócio ao LLM sem validação determinística.

---

