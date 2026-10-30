# Guia de Uso — Squad AI v2

> Stack-alvo: **Java 25 + Spring Boot 4 / Spring Framework 7 + Aurora PostgreSQL + Testcontainers**.
> Arquitetura: **DDD forte + Clean Architecture + CQRS in-process + Outbox + Cloud Native AWS**.
> Método: **TDD** obrigatório (RED → GREEN → REFACTOR).

---

## 1. Inicialização de Projeto Completo

**Comando:** `"Squad AI, prepare a equipe para o projeto [NOME]."`
**Exemplo:** `"Squad AI, prepare a equipe para o projeto PedidosAPI."`
**Efeito:** Cria infraestrutura em `.agent/skills/squad-ai/.antigravity/equipe/`, identifica skills necessárias e inicia a Fase 1 (Discovery com DDD).

## 2. Inicialização com Skills Específicas

**Comando:** `"Squad AI, prepare a equipe integrando [@skill1 @skill2 @skill3]."`
**Exemplo:** `"Squad AI, prepare a equipe integrando [@engenheiro-especificacao @especialista-banco @especialista-qualidade @tech-lead-review]."`
**Efeito:** Monta a squad apenas com os agentes especificados (o Condutor continua ativo sempre).

## 3. Execução por Fase

**Comando:** `"Squad AI, execute a fase [FASE] do projeto [NOME]."`
**Exemplo:** `"Squad AI, execute a fase DESIGN do projeto PedidosAPI."`
**Efeito:** Ativa os agentes da fase e executa com gatekeeping.

## 4. Scaffold de Projeto (Fase 3)

**Comando:** `"Squad AI, gere o scaffold do projeto [NOME]."`
**Efeito:** Invoca `scripts/generate_project.py` com os parâmetros consolidados na Fase 2 (name, groupId, base-package, contexts) para materializar Maven multi-module, domínio DDD exemplar, Outbox, Flyway, Dockerfile, docker-compose e CI.

Uso direto (sem mensageria de squad):

```bash
python .agent/skills/squad-ai/scripts/generate_project.py \
    --name pedidos-api \
    --group-id com.example \
    --base-package com.example.pedidos \
    --contexts "pedidos,pagamentos" \
    --output ./
```

## 5. Delegação de Tarefa

**Comando:** `"Squad AI, delegue ao [AGENTE] a tarefa de [DESCRIÇÃO]."`
**Exemplo:** `"Squad AI, delegue ao especialista-qualidade a tarefa de escrever testes de integração com Testcontainers para o Outbox do contexto pedidos."`
**Efeito:** Registra atividade em `registro_atividades.json` e notifica o agente.

## 6. Aprovação de Planos

**Fluxo:** Agente submete plano → Condutor avalia → Aprova / Rejeita / Revisa.
**Comando do agente:** `"Condutor, segue meu plano de ação para [ATIVIDADE]."`
**Respostas do Condutor:** `"APROVADO"`, `"REVISÃO_NECESSÁRIA: [motivo]"` ou `"REJEITADO: [motivo]"`.

Enquanto não aprovado, o agente permanece em `SOMENTE_LEITURA` ou `PLANEJAMENTO`.

## 7. Mensageria

- **Mensagem direta:** `"Squad AI, diga ao [AGENTE] que [MENSAGEM]."`
- **Broadcast:** `"Squad AI, avise a todos que [COMUNICADO]."`
- **Status:** `"Squad AI, qual o status das atividades?"`

## 8. Verificação de Fase

**Comando:** `"Squad AI, valide os critérios de passagem da fase [FASE]."`
**Efeito:** Executa o checklist de gatekeeping da fase. Inclui aderência DDD (Fase 1-2-5) e TDD (Fase 3-5).

## 9. Relatório da Squad

**Comando:** `"Squad AI, gere o relatório final do projeto."`
**Efeito:** Produz relatório consolidado com métricas (cobertura, mutation, ArchUnit, DDD/TDD compliance), decisões (ADRs), entregas e lições aprendidas.

## 10. Modos de Execução

| Modo | Quando usar |
|---|---|
| `sequencial` (padrão) | Projeto novo, fluxo clássico Discovery → Deliver |
| `paralelo` | Fases com baixa dependência sobrepõem (ex: Design pode começar com primeiras stories prontas; Build+Test por US individual) |
| `por demanda` | Intervenção pontual — usuário escolhe fase e agentes |

---

## Exemplos de Uso Avançado

### Projeto Java 25 completo (padrão da squad)
```
"Squad AI, prepare a equipe para o projeto PedidosAPI.
Escopo: API REST com bounded contexts 'pedidos' e 'pagamentos'.
Integração: SQS para eventos de pedido confirmado.
Requisito: JWT + auditoria, p95 < 200ms para criar pedido, Aurora Serverless v2.
Modo: sequencial, todas as fases."
```
Entregará: projeto Maven 4 multi-module, domínio DDD com `Pedido`/`PedidoId`/`Money`/`PedidoConfirmado`, CQRS handlers, Outbox table + relay para SQS, ArchUnit verde, Testcontainers rodando, Dockerfile pronto.

### Modernização de monólito legado
```
"Squad AI, analise o projeto atual em Java 17 + Spring Boot 2.7 e proponha:
1) Bounded contexts
2) Plano de migração para Java 25 + Spring Boot 4
3) Introdução gradual de Outbox para eventos
Modo: DISCOVERY + DESIGN apenas, produza ADRs."
```

### Auditoria DDD + segurança
```
"Squad AI, execute auditoria no projeto existente.
Ative: tech-lead-review, especialista-qualidade, engenheiro-seguranca.
Foco: aderência DDD (VOs validados, aggregates com invariantes, bounded contexts) e OWASP Top 10."
```

### Apenas testes com Testcontainers
```
"Squad AI, delegue ao especialista-qualidade a tarefa de ampliar testes de integração:
- Testcontainers Postgres 16
- Cobrir OutboxPoller, PedidoRepository, GlobalExceptionHandler
- Meta: 20% de integração na pirâmide, 0 flakiness no CI.
Modo: por demanda, apenas Fase 4."
```

### Review final antes de merge
```
"Squad AI, execute apenas a Fase REVIEW no PR #123.
Tech Lead deve validar P1>P2>P3, DDD, TDD e DoD. Zero 🔴 para merge."
```

> Frase de invocacao: o orquestrador e acionado por 'Squad AI, prepare a equipe' (id squad-ai).
