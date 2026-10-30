# Referência — Operação e Segurança de Dados (observabilidade, resiliência, OWASP, LGPD/GDPR, KMS, RLS)

> Parte da skill `especialista-banco`. Carregue sob demanda. Hub: `../SKILL.md`.
## 10. Observabilidade + Cloud Native Resilience

### 10.1 Métricas, Traces, Logs

- **Métricas Micrometer**: `hikaricp.connections.active/idle/pending`, `jpa.query.*`, `flyway.schema.version`, `dynamodb.request.duration`, `mongodb.command.duration`
- **Traces OpenTelemetry**: auto-instrumentation do JDBC/MongoDB/DynamoDB + attributes `db.system`, `db.statement` (sanitizado via `SpanProcessor`), `db.operation`, `db.name`
- **Logs estruturados JSON** com `trace_id`/`span_id`/`correlation_id` propagados
- **Slow queries**: `log_min_duration_statement=500ms` no Postgres, export via CloudWatch Logs Insights; DynamoDB throttled metrics via CloudWatch
- **Alertas**: `p99 > SLA`, `deadlocks > 0`, `replication_lag > 5s`, `connections > 80% pool`, DynamoDB `UserErrors > 0`, `ProvisionedThroughputExceeded > 0`
- **Correlation ID** propagado via [[Correlation ID Middleware]] com Scoped Values (end-to-end VT → JDBC → SQS → Lambda)

### 10.2 Health Probes específicos de banco

Ver [[Health Probes]]. Configuração Spring Boot Actuator:

```yaml
management:
  endpoint:
    health:
      probes:
        enabled: true
      show-details: when-authorized
      group:
        readiness:
          include: db, redis, diskSpace
        liveness:
          include: ping      # NUNCA incluir db em liveness (reinício cascata)
```

**Regra**: `db` só em **readiness** (remove do LB), nunca em **liveness** (evita restart loop quando RDS tem blip).

### 10.3 Circuit Breaker em chamadas de banco críticas

Para queries externas (read replicas remotos, OpenSearch, Neo4j), envelopar com Resilience4j — ver [[Circuit Breaker]]:

```java
@CircuitBreaker(name = "searchDb", fallbackMethod = "searchFallback")
@Bulkhead(name = "searchDb", type = Bulkhead.Type.SEMAPHORE)
public List<Result> search(Query q) { /* ... */ }

private List<Result> searchFallback(Query q, Throwable t) {
    log.warn("Fallback para cache em memória", t);
    return cache.getOrDefault(q.hash(), List.of());
}
```

### 10.4 Backup, PITR e Disaster Recovery

- **RDS/Aurora**: Automated Backups + PITR (até 35 dias); snapshot cross-region para DR
- **Aurora Global Database** para RPO < 1s cross-region
- **DynamoDB**: PITR habilitado (restore point-in-time dos últimos 35 dias) + on-demand backup
- **S3**: versioning + Object Lock (WORM) para dados de compliance
- **Exercícios de restore**: trimestrais, medindo RTO/RPO reais — ver [[arquiteto-cloud-aws]]

### 10.5 RDS Proxy e pooling externo

Para Lambda + RDS: **RDS Proxy** com IAM auth elimina cold start de conexão e reuso seguro.
Para serviços long-running em ECS: **HikariCP** com Virtual Threads é suficiente (ver [[Virtual Threads vs HikariCP]]).

---

## 11. Segurança de Dados (OWASP + LGPD/GDPR)

- **Criptografia em trânsito**: TLS 1.3 obrigatório, verificação de certificado (`sslmode=verify-full` no Postgres, `ssl=true&sslMode=VERIFY_IDENTITY` no MySQL)
- **Password hashing no servidor de BD**: PostgreSQL 14+ padrão **SCRAM-SHA-256** (substituto de `md5`). Forçar via `ALTER SYSTEM SET password_encryption = 'scram-sha-256';` + `pg_reload_conf()` e garantir `pg_hba.conf` com `scram-sha-256` (nunca `trust`/`md5`). Migrar usuários legados com `ALTER USER ... PASSWORD '...'` após definir o parâmetro
- **Criptografia em repouso**: KMS-managed — RDS/Aurora (`StorageEncrypted=true`), DynamoDB (SSE-KMS), S3 (SSE-KMS + bucket key), EBS (volumes gp3 criptografados)
- **PII Redaction**: ver [[engenheiro-seguranca]] — `@Sensitive` em colunas sensíveis, `PiiRedactor` + `MaskingJsonGeneratorDecorator` no logback, mascarar em logs antes de sair da aplicação
- **Least privilege**: um DB user por app; `SELECT/INSERT/UPDATE` por tabela, nunca `SUPERUSER` em prod. IAM Database Authentication no RDS/Aurora quando possível (zero-password)
- **Secrets**: **AWS Secrets Manager** com rotação automática (Lambda rotation), Parameter Store para não-secretos. Nunca credenciais em `application.yml` (usar `${SPRING_DATASOURCE_PASSWORD}`)
- **Rotação**: `spring.cloud.aws.secretsmanager` refresh + HikariCP `dataSource.user`/`password` atualizados sem restart
- **Row Level Security** (PostgreSQL) para multi-tenant: `CREATE POLICY tenant_isolation ON tabela USING (tenant_id = current_setting('app.tenant_id')::uuid)`
- **Connection-level tenant propagation**: `SET LOCAL app.tenant_id = '...'` no início de cada `@Transactional`, propagado via [[Correlation ID Middleware]] + Scoped Values
- **SQL Injection**: sempre `PreparedStatement` (Spring Data/JPA fazem por default); em SQL nativo usar `@Param` / `:named`; proibido string concatenation
- **LGPD/GDPR**: direito ao esquecimento → soft delete + job de hard delete após período de retenção; consentimento registrado em tabela `consents(user_id, purpose, granted_at, revoked_at)`
- **Audit trail append-only**: quando requerido por compliance, `audit_log(id, actor, action, entity, entity_id, before_jsonb, after_jsonb, at)` + trigger; nunca permitir `UPDATE`/`DELETE`
- **Checklist OWASP A03:2021 Injection**: queries dinâmicas proibidas sem bind vars; A02 Cryptographic Failures: TLS + KMS; A04 Insecure Design: threat modeling em mudanças de schema

---

