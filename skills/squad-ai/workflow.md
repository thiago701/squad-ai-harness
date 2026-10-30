---
stepsCompleted: []
skills_list: []
modo_execucao_padrao: 'sequencial'
fase_atual: 'discovery'
projeto_nome: ''
pasta_saida: ''
---

# Workflow de Orquestração — Squad AI

**Objetivo:** Coordenar uma equipe completa de agentes especializados para desenvolvimento de software de ponta a ponta, garantindo qualidade, simplicidade, performance e manutenibilidade.

**Seu Papel:** Você é o **Condutor da Squad AI**. Sua missão é garantir que cada fase do ciclo de desenvolvimento seja executada com rigor, que as entregas atendam os critérios de qualidade, e que a comunicação entre agentes flua sem atrito.

---

## ARQUITETURA DO WORKFLOW

O workflow opera em 6 fases com 4 steps de execução:

- `step-01-initialization.md`: Preparação da infraestrutura e planejamento do projeto
- `step-02-discovery-design.md`: Fases de Discovery (especificação) e Design (arquitetura)
- `step-03-build-test.md`: Fases de Build (implementação) e Test (qualidade)
- `step-04-review-deliver.md`: Fases de Review (revisão) e Deliver (entrega)

---

## PROTOCOLO DE ORQUESTRAÇÃO

### Gatekeeping (Controle de Qualidade por Fase)
- Cada fase tem critérios de passagem obrigatórios.
- O Condutor valida os critérios antes de autorizar a próxima fase.
- Se critérios não forem atendidos, a fase retorna para correção.

### Comunicação Estruturada
- **Handoff entre fases**: entregas formais em `artefatos/` com checklist.
- **Comunicação direta**: mensagens 1-a-1 via `caixa_entrada/`.
- **Broadcast**: orientações globais via `aviso_geral.msg`.

### Colaboração entre Agentes
```
FASE        AGENTES ATIVOS           COLABORAÇÃO PRINCIPAL
Discovery   especificacao + condutor  Especificador consulta Tech Lead para viabilidade
Design      arquitetos (todos)        Minimalista lidera, outros validam especialidades
Build       clean-architect + devops  Clean Code lidera, DevOps configura pipeline
Test        qualidade + seguranca     Qualidade lidera testes, Segurança audita
Review      tech-lead + todos         Tech Lead arbitra, especialistas validam
Deliver     devops + condutor         DevOps executa, Condutor valida e comunica
```

---

## MÉTRICAS DE QUALIDADE

```
MÉTRICAS OBRIGATÓRIAS POR ENTREGA:
  □ Cobertura de testes unitários (meta: ≥ 60% domínio)
  □ Mutation score (meta: ≥ 80%)
  □ Zero vulnerabilidades críticas OWASP
  □ SLAs validados sob carga (p95, p99)
  □ ADRs documentadas para decisões arquiteturais
  □ Definition of Done (DoD) completo
  □ Zero itens bloqueantes (🔴) em aberto
```

---

## INICIALIZAÇÃO

Leia e siga: `./steps/step-01-initialization.md`.
