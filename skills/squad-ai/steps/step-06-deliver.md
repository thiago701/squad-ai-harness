# Step 6 — Deliver

## Fase 6 — DELIVER

### Objetivo

Preparar para produção e entregar. Foco em **Cloud Native** (12-factor, stateless, observável) e reversibilidade.

---

### 1. Ativar DevOps

```
Instruções para engenheiro-devops:
  - Leia todos os artefatos das fases anteriores
  - Configure deploy (staging → produção)
  - Configure observabilidade (OpenTelemetry + CloudWatch ou equivalente)
  - Documente runbook operacional
  - Documente e ENSAIE rollback plan
```

---

### 2. Checklist de Deploy

```
IMAGEM / BUILD
  □ Dockerfile multi-stage (JDK 25 build → JRE slim runtime)
  □ Imagem ≤ 300 MB (JRE) ou ≤ 100 MB (GraalVM Native, quando aplicável)
  □ User não-root no container
  □ SBOM gerado e assinado (cosign, opcional mas recomendado)

CONFIGURAÇÃO
  □ Variáveis de ambiente documentadas em .env.example
  □ Spring profile `prod` ativo em produção
  □ Zero valores sensíveis em application.yml; tudo via env/SSM/Secrets Manager
  □ Aurora endpoint via env; pool HikariCP configurado

CLOUD NATIVE (12-factor)
  □ Logs em stdout (JSON estruturado)
  □ Stateless (sem sessão local; cache distribuído se necessário)
  □ Boot startup time documentado
  □ Graceful shutdown configurado (spring.lifecycle.timeout-per-shutdown-phase)

HEALTH CHECKS
  □ /actuator/health/liveness  → responde 200 sem dependências externas
  □ /actuator/health/readiness → verifica Aurora, fila, caches
  □ Load balancer configurado para usar readiness

OBSERVABILIDADE
  □ OpenTelemetry exportando traces (OTLP → CloudWatch / X-Ray / Jaeger)
  □ Micrometer expondo métricas (/actuator/prometheus)
  □ Logs com correlation-id e trace-id populados via Scoped Values
  □ Dashboards prontos: latência p50/p95/p99, RPS, erros 5xx, saturação pool JDBC

ALERTAS
  □ SLO de disponibilidade com error budget
  □ Alerta de p95 acima do SLA
  □ Alerta de taxa de erro > threshold
  □ Alerta de lag do Outbox relay (eventos não processados)

SEGURANÇA RUNTIME
  □ TLS obrigatório (ALB / API Gateway terminando)
  □ Spring Security configurado (CSP, HSTS, X-Frame-Options)
  □ Rate limiting ativo se aplicável

ROLLBACK
  □ Estratégia documentada (blue/green, canary, ou re-deploy versão anterior)
  □ Migrations Flyway compatíveis com rollback (aditivas; breaking changes em passos separados)
  □ Dados sensíveis a rollback listados e testados
```

---

### 3. Runbook Operacional

Mínimo em `artefatos/fase-6-deliver/runbook-operacao.md`:

```
□ Como subir a aplicação em cada ambiente (dev/staging/prod)
□ Como inspecionar logs (query padrão no agregador)
□ Como rodar migration manual em emergência
□ Como forçar reprocessamento de outbox
□ Como investigar latência anormal
□ Procedimento de rollback (passo-a-passo)
□ Contatos de emergência (squad owners)
```

Para estrutura completa de runbook (pré-requisitos, diagnóstico em 3 comandos, procedimento, escalação, histórico de uso) e dos outros 4 tipos de documentação da squad (README, API docs, Architecture, Onboarding) com os 5 princípios de escrita, consulte `../references/documentation-guide.md`.

**Guias operacionais complementares (v8.3 — absorção de skills externas de engenharia):**

- `../references/deploy-checklist.md` — checklist executável pré/durante/pós-deploy com **rollback triggers quantitativos** (error rate > 2× baseline, p95 > 3× baseline, 5xx > 1%) + staging → canary → produção + smoke tests obrigatórios. Use antes de cada promoção.
- `../references/incident-response.md` — quando algo em produção degrada: workflow **Triage → Comunicar → Mitigar → Postmortem blameless**, classificação **SEV1-4** com response times + template de 5 Whys. Mitigação **antes** de causa raiz.
- `../references/debug-guide.md` — durante a fase Mitigar (ou se bug recorrente), use o protocolo **Reproduzir → Isolar → Diagnosticar → Corrigir** com hipóteses escritas + teste RED→GREEN. Fix sem teste acompanhante é 🔴 bloqueante.
- `../references/tech-debt-guide.md` — action items de postmortem que não cabem no fix imediato viram cards de dívida categorizados (Code / Architecture / Test / Dependency / Documentation / Infrastructure) com scoring priorizável.

---

### 4. Relatório Final da Squad

O Condutor consolida:

```
RELATÓRIO FINAL — SQUAD AI
━━━━━━━━━━━━━━━━━━━━━━━━━━

PROJETO:      <nome>
SQUAD:        <N> agentes
DURAÇÃO:      <tempo>
BOUNDED CTX:  <lista>

ADERÊNCIA AOS PILARES
  DDD:                  <score aderência VOs/Aggregates/Events>
  Clean Architecture:   <ArchUnit verde? sim/não>
  CQRS + Outbox:        <implementado? idempotência validada?>
  Cloud Native:         <12-factor atendido? observabilidade ativa?>

MÉTRICAS DE QUALIDADE
  Cobertura:            <X>%   (domínio: <X>%)
  Mutation score:       <X>%   (se aplicável)
  Vulnerabilidades:     <N críticas>
  SLAs validados:       <sim/não>
  ADRs:                 <N>

ENTREGAS
  User Stories:         <N>
  Cenários BDD:         <N>
  Aggregates:           <N>
  Value Objects:        <N>
  Domain Events:        <N>
  Use Cases:            <N>
  Endpoints REST:       <N>
  Testes totais:        <N> (unit/integ/arch: <a/b/c>)

TECH DEBT
  <lista priorizada>

LIÇÕES APRENDIDAS
  <insights>

PRÓXIMOS PASSOS
  <recomendações>
```

Salvar em:

```
artefatos/fase-6-deliver/
├── relatorio-final.md
├── runbook-operacao.md
├── rollback-plan.md
├── metricas-qualidade.md
└── licoes-aprendidas.md
```

---

### 5. Encerramento

```bash
python .agent/skills/squad-ai/scripts/squad_manager.py comunicado_geral \
  "squad-ai" "Projeto <NOME> concluído. Relatório em artefatos/fase-6-deliver/."

python .agent/skills/squad-ai/scripts/squad_manager.py registrar_metricas \
  '{"cobertura": 82, "mutation_score": 85, "vulnerabilidades": 0, "slas_ok": true,
    "archunit": "green", "ddd_compliance": "full", "cqrs_outbox": "ok"}'
```

---

### 6. Apresentação ao Usuário

Resumo executivo (3-5 linhas) + métricas + estrutura entregue + tech debt + links para artefatos.

Preferencialmente:

```
Projeto <nome> entregue.
  • Java 25 + Spring Boot 4 + Aurora PG + CQRS/Outbox + DDD forte
  • <N> bounded contexts, <N> aggregates, <N> endpoints
  • Cobertura <X>%, ArchUnit verde, zero vulnerabilidades críticas
  • Deploy + runbook + rollback em artefatos/fase-6-deliver/
```

---

## FIM DO CICLO

A Squad AI completou o ciclo de desenvolvimento. Sistema pronto para produção.
