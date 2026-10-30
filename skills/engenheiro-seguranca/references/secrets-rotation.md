# Secrets Manager Rotation + HikariCP Refresh — Snippet Canônico

> Rotação automática de credenciais de banco sem restart de aplicação. Spring Cloud AWS 3.x + HikariCP + AWS Secrets Manager Lambda rotation. Zero downtime.

## Fluxo

```
┌──────────────────┐   cron    ┌─────────────────────┐
│ Secrets Manager  │ ────────▶ │ Lambda de rotação   │
│ (mysql/postgres) │           │ (AWS-managed)       │
└──────────────────┘           └──────────┬──────────┘
        ▲                                 │
        │ lê nova versão AWSCURRENT       ▼
        │                      ALTER USER app_user
┌───────┴──────────┐           WITH PASSWORD 'novo';
│ Spring App       │
│ (HikariCP)       │
└──────────────────┘
        │
        │ scheduled refresh a cada 5min
        ▼
   Busca nova versão → HikariDataSource.getHikariConfigMXBean()
                       .setPassword(novoSecret)
```

## 1. Lambda de Rotação (AWS-managed)

AWS oferece templates prontos: `SecretsManagerRDSPostgreSQLRotationSingleUser` e `SecretsManagerRDSPostgreSQLRotationMultiUser`. **Preferir multi-user** em produção — evita janela onde nenhuma credencial funciona.

```yaml
# CDK Java ou SAM
RotationSchedule:
  Type: AWS::SecretsManager::RotationSchedule
  Properties:
    SecretId: !Ref DbSecret
    RotationLambdaARN: !Sub 'arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:SecretsManagerRDSPostgreSQLRotationMultiUser'
    RotationRules:
      AutomaticallyAfterDays: 30
```

## 2. Dependências (Maven 4)

```xml
<dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>io.awspring.cloud</groupId>
      <artifactId>spring-cloud-aws-dependencies</artifactId>
      <version>3.3.0</version>
      <type>pom</type>
      <scope>import</scope>
    </dependency>
  </dependencies>
</dependencyManagement>

<dependencies>
  <dependency>
    <groupId>io.awspring.cloud</groupId>
    <artifactId>spring-cloud-aws-starter-secrets-manager</artifactId>
  </dependency>
</dependencies>
```

## 3. Configuração (application.yml)

```yaml
spring:
  config:
    import: "aws-secretsmanager:prod/pedidos/db"
  datasource:
    url: ${db.url}                 # resolvido pelo Secrets Manager
    username: ${db.username}
    password: ${db.password}
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5
      max-lifetime: 600000         # 10min — força rotação de conexões
      keepalive-time: 300000       # 5min
      validation-timeout: 2000

app:
  secrets:
    db-secret-id: prod/pedidos/db
    refresh-interval-seconds: 300  # 5min
```

**Ponto crítico — `max-lifetime`**: HikariCP fecha conexões acima desse tempo. Com senha nova, a próxima conexão vai usar a senha atualizada. Sem isso, conexões antigas continuam com a senha velha até falharem.

## 4. Componente de Refresh (Java 25)

```java
package com.squadai.infra.secrets;

import com.zaxxer.hikari.HikariDataSource;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import software.amazon.awssdk.services.secretsmanager.SecretsManagerClient;
import software.amazon.awssdk.services.secretsmanager.model.GetSecretValueRequest;

import javax.sql.DataSource;
import java.time.Duration;
import java.time.Instant;
import java.util.concurrent.atomic.AtomicReference;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

@Component
public class DbPasswordRefresher {

    private static final Logger log = LoggerFactory.getLogger(DbPasswordRefresher.class);

    private final DataSource dataSource;
    private final SecretsManagerClient secretsClient;
    private final ObjectMapper json;
    private final MeterRegistry meters;
    private final String secretId;
    private final AtomicReference<String> currentPasswordHash = new AtomicReference<>("");

    public DbPasswordRefresher(
        DataSource dataSource,
        SecretsManagerClient secretsClient,
        ObjectMapper json,
        MeterRegistry meters,
        @Value("${app.secrets.db-secret-id}") String secretId
    ) {
        this.dataSource = dataSource;
        this.secretsClient = secretsClient;
        this.json = json;
        this.meters = meters;
        this.secretId = secretId;
    }

    /** Executa no startup + a cada 5min (configurável via properties). */
    @Scheduled(fixedDelayString = "${app.secrets.refresh-interval-seconds:300}000",
               initialDelayString = "60000")
    public void refresh() {
        if (!(dataSource instanceof HikariDataSource hikari)) {
            log.warn("DataSource não é HikariCP — rotação inline indisponível");
            return;
        }

        var start = Instant.now();
        try {
            var secret = secretsClient.getSecretValue(
                GetSecretValueRequest.builder().secretId(secretId).build()
            );
            JsonNode payload = json.readTree(secret.secretString());
            String username = payload.get("username").asText();
            String password = payload.get("password").asText();

            // Hash (não o password puro) para detectar mudança sem log sensível
            String newHash = Integer.toHexString(password.hashCode());
            String previousHash = currentPasswordHash.getAndSet(newHash);

            if (!newHash.equals(previousHash)) {
                var mxBean = hikari.getHikariConfigMXBean();
                mxBean.setUsername(username);
                mxBean.setPassword(password);
                hikari.getHikariPoolMXBean().softEvictConnections();
                log.info("DB credentials rotated (soft-evict executed, previousHash={}, newHash={})",
                         previousHash, newHash);
                meters.counter("app.secrets.db.rotations").increment();
            } else {
                log.debug("DB credentials unchanged (hash={})", newHash);
            }
            meters.timer("app.secrets.db.refresh.duration")
                  .record(Duration.between(start, Instant.now()));
        } catch (Exception e) {
            log.error("Falha ao refrescar credenciais", e);
            meters.counter("app.secrets.db.refresh.errors").increment();
            // NÃO relança — app continua com credenciais atuais
        }
    }
}
```

## 5. Por que `softEvictConnections()`?

- **Não** fecha conexões em uso (espera retornar ao pool)
- Marca conexões ociosas para substituição imediata
- Novas conexões usam a senha atualizada
- Conexões em transação terminam normalmente com a senha antiga
- Zero interrupção do tráfego

## 6. Teste (Testcontainers + LocalStack)

```java
@Testcontainers
@SpringBootTest(properties = {
    "app.secrets.refresh-interval-seconds=1"
})
class DbPasswordRefresherTest {

    @Container
    static LocalStackContainer ls = new LocalStackContainer(DockerImageName.parse("localstack/localstack:4"))
        .withServices(LocalStackContainer.Service.SECRETSMANAGER);

    @Container
    static PostgreSQLContainer<?> db = new PostgreSQLContainer<>("postgres:16-alpine");

    @Autowired DbPasswordRefresher refresher;
    @Autowired SecretsManagerClient sm;

    @Test
    void deveAtualizarCredenciaisQuandoSecretMuda() {
        sm.updateSecret(r -> r.secretId("prod/pedidos/db")
            .secretString("{\"username\":\"app\",\"password\":\"nova-senha-42\"}"));
        await().atMost(3, SECONDS).until(() ->
            meterRegistry.counter("app.secrets.db.rotations").count() == 1.0);
    }
}
```

## 7. Observabilidade

Métricas emitidas:
- `app.secrets.db.rotations` (counter) — rotações detectadas
- `app.secrets.db.refresh.duration` (timer) — latência da busca no Secrets Manager
- `app.secrets.db.refresh.errors` (counter) — falhas (alertar se > 3 em 10min)

Dashboards Grafana/CloudWatch devem plotar:
- Tempo desde última rotação (`time()` - `last(rotations_timestamp)`)
- Taxa de erros > 0 por 5min → **PagerDuty**

## 8. Checklist de Deploy

- [ ] Secret configurado no Secrets Manager com payload JSON `{username, password, host, port, dbname}`
- [ ] Lambda de rotação ativa (multi-user preferencial)
- [ ] IAM role da app com `secretsmanager:GetSecretValue` **apenas** no ARN específico
- [ ] `max-lifetime: 600000` em HikariCP
- [ ] `@Scheduled` refresh job ativo (`@EnableScheduling`)
- [ ] Alertas de `app.secrets.db.refresh.errors > 3/10min`
- [ ] Logs **não** contêm senha em claro (apenas hash)
- [ ] Teste de integração com rotação simulada

## 9. Anti-padrões

- ❌ Reiniciar pod/container a cada rotação — desnecessário e disruptivo
- ❌ Logar a senha (mesmo mascarada parcialmente)
- ❌ Rotação manual semestral/anual — padronize 30 dias automático
- ❌ IAM role com `secretsmanager:*` — use least privilege por ARN
- ❌ `max-lifetime: 1800000` (30min) — conexões antigas demais quando rotação acontece

## Conexões

- Parte de `engenheiro-seguranca/SKILL.md` (seção A02 Cryptographic Failures + Secrets Management)
- Complementa `especialista-banco/SKILL.md` (seção 11 Segurança de Dados)
- Cross-reference: `arquiteto-cloud-aws` (Secrets Manager catálogo) + `engenheiro-devops` (CI/CD roles)
