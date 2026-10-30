# Referência — Secrets & Supply Chain (Auditoria de Dependências, Rotação Automática de Secrets, AWS Secrets Manager)

> Parte da skill `engenheiro-seguranca`. Carregue sob demanda. Hub: `../SKILL.md`.
## Auditoria de Dependências

### SLA Canônico por Severidade de CVE

Qualquer dependência com CVE encontrada **deve ser remedida dentro do prazo**:

| Severidade | CVSS | SLA | Ação | Bloqueante? |
|---|---|---|---|---|
| **CRITICAL** | 9.0–10.0 | **24 horas** | Patch imediato ou remover dependência | 🔴 SIM |
| **HIGH** | 7.0–8.9 | **7 dias** | Agendado para próximo release | 🔴 SIM |
| **MEDIUM** | 4.0–6.9 | **30 dias** | Backlog prioritário | 🟡 NÃO |
| **LOW** | 0.1–3.9 | Próximo release | Backlog normal | 🟡 NÃO |

**Aplicação:** Toda build de CI/CD falha se existe CVE CRITICAL ou HIGH não remediada. Bloqueia merge para main.

### Java (OWASP Dependency-Check)

```xml
<!-- pom.xml — Apache Maven 4, OWASP Dependency-Check plugin -->
<plugin>
    <groupId>org.owasp</groupId>
    <artifactId>dependency-check-maven</artifactId>
    <version>10.0.4</version>
    <executions>
        <execution>
            <phase>verify</phase>
            <goals>
                <goal>check</goal>
            </goals>
        </execution>
    </executions>
    <configuration>
        <!-- Build falha se CVE >= 7.0 (HIGH ou CRITICAL) -->
        <failBuildOnCVSS>7.0</failBuildOnCVSS>
        <formats>
            <format>HTML</format>
            <format>JSON</format>
        </formats>
        <nvdApiKeyEnvironmentVariable>NVD_API_KEY</nvdApiKeyEnvironmentVariable>
        <!-- Verificar também dependências transitivas -->
        <skipConfigurationFileValidation>false</skipConfigurationFileValidation>
    </configuration>
</plugin>
```

```bash
# Executar manualmente
mvn dependency-check:check

# Gera relatórios em target/dependency-check-report.{html,json}
```

### Python (Safety + Bandit)

```bash
# Verificar vulnerabilidades em dependências
pip install safety bandit

# Scan de dependências — falha se CRITICAL ou HIGH
safety check --full-report --json > safety-report.json

# Scan de código — detecta padrões inseguros (SQL injection, hardcoded secrets, etc)
bandit -r src/ -f json -o bandit-report.json -ll  # -ll = HIGH e CRITICAL

# No CI/CD:
- name: Security Scan
  run: |
    safety check --fail-on-alert       # falha em CRITICAL/HIGH
    bandit -r src/ -ll --fail-under 5  # falha se score < 5
```

### Referência: Pipeline CI/CD Completo

Ver `engenheiro-devops/SKILL.md` seção "Auditoria de Dependências em CI/CD" para integração de:
- OWASP Dependency-Check (Java)
- Safety + Bandit (Python)
- GitHub Dependabot / GitLab Dependency Scanning
- Alertas no Slack/email quando CVE CRITICAL detectada
- Automação de pull request com patches (se disponível)

> **SCA enterprise (compliance):** quando precisar de *reachability*, risco de licença, SBOM
> CycloneDX ou atestado auditável (PCI/SOC 2/ISO), o caminho é o **Veracode SCA** — ver
> `references/veracode.md`. O Dependency-Check segue como default free no dev-loop; os dois coexistem.

---

---

## Renovação Automática de Secrets

### AWS Secrets Manager com Rotação Automática

Secrets estáticos são vulnerabilidades; secrets rotacionados reduzem janela de exposição se houver vazamento:

```java
// Configuração Spring Cloud AWS Secrets Manager
@Configuration
public class SecretsManagerConfig {

    @Bean
    public SecretsManagerProperties secretsManagerProperties() {
        return new SecretsManagerProperties();
    }

    @Bean
    public SecretsManagerPropertySourceLocator secretsManagerPropertySourceLocator(
            SecretsManagerProperties properties) {
        return new SecretsManagerPropertySourceLocator(properties);
    }
}
```

```yaml
# application-prod.yml
spring:
  cloud:
    aws:
      secrets-manager:
        enabled: true
        region: us-east-1
        # Prefixo para buscar secrets — ex: app/prod/db-password
        prefix: app/prod
        # Name substitution para normalizar nomes
        name-substitution: "_"

# IMPORTANTE: Usar @RefreshScope em beans que dependem de secrets
# Quando o secret é rotacionado, Spring reinjecta a dependência
```

```java
// Serviço que depende de secret — usa @RefreshScope
@Component
@RefreshScope  // ← permite atualização sem restart
public class DatabaseConnectionService {
    
    @Value("${db-password}")  // Injetado do Secrets Manager
    private String dbPassword;
    
    @Value("${db-host}")
    private String dbHost;
    
    public DataSource createDataSource() {
        return DataSourceBuilder.create()
            .url("jdbc:postgresql://" + dbHost + "/mydb")
            .password(dbPassword)
            .driverClassName("org.postgresql.Driver")
            .build();
    }
}
```

### Health Check para Secrets Expirados

Implementar `/actuator/health/secrets` que valida se o secret atual é recente (≤ rotation period):

```java
// Health indicator customizado
@Component
public class SecretsHealthIndicator extends AbstractHealthIndicator {

    private static final long ROTATION_PERIOD_DAYS = 30;

    @Autowired private SecretsManagerClient secretsClient;

    @Override
    protected void doHealthCheck(Health.Builder builder) {
        try {
            // Buscar metadata do secret (incluindo lastRotated)
            var describeRequest = DescribeSecretRequest.builder()
                .secretId("app/prod/db-password")
                .build();

            var response = secretsClient.describeSecret(describeRequest);
            
            Instant lastRotated = response.lastRotatedDate() != null
                ? Instant.ofEpochMilli(response.lastRotatedDate().getTime())
                : response.createdDate() != null
                    ? Instant.ofEpochMilli(response.createdDate().getTime())
                    : Instant.now();

            // Validar se secret está "fresco" (não expirou)
            long daysOld = ChronoUnit.DAYS.between(lastRotated, Instant.now());
            
            if (daysOld > ROTATION_PERIOD_DAYS) {
                builder.down()
                    .withDetail("secret_id", "app/prod/db-password")
                    .withDetail("days_since_rotation", daysOld)
                    .withDetail("rotation_period_days", ROTATION_PERIOD_DAYS)
                    .withDetail("status", "EXPIRED - pod não recebe tráfego");
            } else {
                builder.up()
                    .withDetail("secret_id", "app/prod/db-password")
                    .withDetail("days_since_rotation", daysOld)
                    .withDetail("rotation_period_days", ROTATION_PERIOD_DAYS);
            }

        } catch (Exception e) {
            builder.down()
                .withDetail("error", e.getMessage());
        }
    }
}
```

```yaml
# application-prod.yml — Configuração Health
management:
  health:
    secretsManager:
      enabled: true
  endpoint:
    health:
      probes:
        enabled: true
  endpoints:
    web:
      exposure:
        include: health,metrics
```

### Startup Check — Pod não passa readiness se secret expirou

```java
// ApplicationReadyEvent — verifica secrets na inicialização
@Component
@EventListener(ApplicationReadyEvent.class)
public class SecretsStartupValidator {

    @Autowired private SecretsManagerClient secretsClient;
    @Autowired private HealthEndpoint healthEndpoint;

    public void onApplicationReady(ApplicationReadyEvent event) throws Exception {
        // Chamar /actuator/health/readiness manualmente
        var health = healthEndpoint.health();
        
        // Se secretsHealthIndicator retornar DOWN, falhar a inicialização
        if (health.getStatus() == Status.DOWN) {
            log.error("Secrets não estão válidas na inicialização — pod NÃO PASSARÁ readiness");
            throw new IllegalStateException("Secrets expirados ou inválidos");
        }
        
        log.info("Secrets válidos — pod pronto para receber tráfego");
    }
}
```

**Configuração Kubernetes:**

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-backend
spec:
  template:
    spec:
      containers:
      - name: app
        image: app:latest
        env:
        - name: SPRING_CLOUD_AWS_SECRETS_MANAGER_ENABLED
          value: "true"
        - name: SPRING_CLOUD_AWS_REGION
          value: "us-east-1"
        
        # Readiness probe — falha se secrets expirados
        readinessProbe:
          httpGet:
            path: /actuator/health/readiness
            port: 8080
          initialDelaySeconds: 15
          periodSeconds: 5
          timeoutSeconds: 2
          failureThreshold: 2  # 2 falhas consecutivas = removido do LB
        
        # Liveness probe — nunca checka secrets (só JVM alive)
        livenessProbe:
          httpGet:
            path: /actuator/health/liveness
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
          failureThreshold: 3
```

**Checklist Rotação de Secrets:**
- ✅ AWS Secrets Manager com rotation schedule configurado (30 dias típico)
- ✅ Spring Cloud AWS Secrets Manager bean registrado
- ✅ @RefreshScope aplicado em beans que usam secrets
- ✅ Health indicator `/actuator/health/secrets` valida lastRotatedDate
- ✅ Se secret expirado → pod não passa readiness → removido do LB
- ✅ Startup check garante que secrets são válidos antes de aceitar tráfego
- ✅ Pod reiniciado automaticamente se secrets expirarem (readiness falha, Kubernetes restart)

---

