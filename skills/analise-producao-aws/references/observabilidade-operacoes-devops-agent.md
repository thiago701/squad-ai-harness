# Observabilidade, Operações e AWS DevOps Agent (Agent Toolkit for AWS)

> **Procedência:** absorvido e reescrito em PT-BR a partir de `aws/agent-toolkit-for-aws` (caminhos upstream: skills/core-skills/aws-observability, as 5 skills de skills/specialized-skills/operations-skills/* e as 7 skills de operações em plugins/aws-agents-for-devsecops/skills/*, commit `658b852f0612ca629d56d0a4de52738fb6a58714`, Apache-2.0).

---

## 1. Observabilidade Unificada no CloudWatch (`aws-observability`, `setting-up-cloudwatch-observability`, `setting-up-cloudwatch-alarm-notifications`)

1. **Instrumentação e Telemetria (`setting-up-cloudwatch-observability`):**
   - Combine os 3 sinais: **Logs estruturados JSON** (com `correlationId`/`traceId`), **Métricas dimensionadas** (Embedded Metric Format — EMF, sem chamadas extras de API) e **Traces distribuídos** (X-Ray / OpenTelemetry via CloudWatch Application Signals).
   - Defina sempre política de retenção (`RetentionInDays`) e criptografia KMS em todos os Log Groups criados.
2. **Canais de Notificação de Alarmes (`setting-up-cloudwatch-alarm-notifications`):**
   - Todo alarme crítico de produção deve ter ações definidas para os estados `ALARM` ( e opcionalmente `OK` / `INSUFFICIENT_DATA`) publicando em um tópico **Amazon SNS** criptografado com KMS.
   - Garanta que a Access Policy do tópico SNS permita `sns:Publish` ao principal `cloudwatch.amazonaws.com` com condição `aws:SourceAccount`.

---

## 2. Auditoria Multi-Região e Monitoramento de Rede (`setting-up-cloudtrail-multi-region`, `aws-network-monitoring`)

- **CloudTrail Multi-Região (`setting-up-cloudtrail-multi-region`):**
  - Habilite `IsMultiRegionTrail: true`, `IncludeGlobalServiceEvents: true` e **`EnableLogFileValidation: true`** (digest SHA-256 contra adulteração de logs).
  - Envie logs para bucket S3 com `BlockPublicAccess`, criptografia SSE-KMS e integração com CloudWatch Logs Insights para detecção rápida de chamadas sensíveis (`Delete*`, `PutBucketPolicy`, `AssumeRole`, `StopLogging`).
- **Monitoramento de Rede (`aws-network-monitoring`):**
  - Utilize **VPC Flow Logs**, **CloudWatch Network Monitor** (sondas sintéticas para conectividade híbrida VPN/Direct Connect) e **VPC Reachability Analyzer** para provar matematicamente se um bloqueio de rede decorre de Route Table, Security Group, NACL ou Network Firewall sem precisar enviar pacotes reais.

---

## 3. Diagnóstico Sistemático de Falhas de Aplicação (`troubleshooting-application-failures`)

Em modo **estritamente somente leitura** (respeitando `guarda_somente_leitura.py`):

1. **Descobrir os Log Groups do serviço afetado** (`describe-log-groups` por prefixo do componente: `/aws/lambda/...`, `/aws/ecs/...`, `/aws/vendedlogs/states/...`).
2. **Isolar a janela temporal exata** do incidente (5–15 min antes do primeiro alarme até o presente).
3. **Executar queries focadas no CloudWatch Logs Insights:**
   - Agrupar por tipo de erro/exceção (`stats count(*) by errorType, status bin(1m)`).
   - Identificar o primeiro componente que falhou na cadeia causal (*root trigger* vs *cascading timeouts*).
4. **Cruzar com eventos de mudança:** deploys recentes no ECS/Lambda/CloudFormation, alterações de configuração/segredos ou esgotamento de quotas/throttling (`Throttles`, `ConcurrentExecutions`, `DatabaseConnections`).

---

## 4. Investigação de Incidentes e Prontidão de Release com AWS DevOps Agent (`plugins/aws-agents-for-devsecops`)

Fluxos operacionais absorvidos das 7 skills do **AWS DevOps Agent** (`investigating-incidents-with-aws-devops-agent`, `analyzing-release-readiness`, `running-release-tests`, `chatting-with-aws-devops-agent`, `coordinating-multi-space-devops-agent`, `setup-devops-agent`, `setup`):

1. **Investigação de Causa Raiz (`investigating-incidents-with-aws-devops-agent`):**
   - Forneça contexto objetivo na abertura da investigação: sintoma observado, timestamp inicial (ISO 8601 UTC), região, serviço/alarme disparado e commits/deploys recentes.
   - Acompanhe o progresso das hipóteses testadas e exija no relatório final a separação explícita entre **evidência observada**, **correlação** e **causa raiz confirmada**.
2. **Análise de Prontidão de Release e Execução de Testes (`analyzing-release-readiness`, `running-release-tests`):**
   - Antes de promover uma mudança para produção, valide: saúde atual dos alarmes do serviço, cobertura de testes de release, ausência de regressões de latência/erro no ambiente de estágio e plano de rollback testado.
3. **Coordenação Multi-Space (`coordinating-multi-space-devops-agent`):**
   - Em ambientes com múltiplos AgentSpaces (por conta ou unidade de negócio), descubra e fixe o espaço correto na sessão antes de despachar consultas operacionais, autenticando sempre via **SigV4** com credenciais temporárias IAM.
