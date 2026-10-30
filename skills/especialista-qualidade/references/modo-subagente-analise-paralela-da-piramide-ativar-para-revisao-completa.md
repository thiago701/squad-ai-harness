# especialista-qualidade · Modo Subagente — Análise Paralela da Pirâmide (Ativar para Revisão Completa)

> Reference da skill `especialista-qualidade` (movida da SKILL.md em 11/10/2026 — hub + references, I3). Carregue só quando a tarefa pedir este tema.

## Modo Subagente — Análise Paralela da Pirâmide (Ativar para Revisão Completa)

> **Threshold de ativação:** usuário pede revisão completa de suite de testes OU solicita criar
> testes para uma feature/classe com múltiplas camadas. Para pedidos de "um teste específico"
> ou questões conceituais, resposta direta é mais eficiente.

### 4 Workers por Camada da Pirâmide (via Task)

| Worker | Camada | Input | O que analisa |
|---|---|---|---|
| `qual-unit` | Unitária | código da classe + testes existentes | gaps de cobertura, test smells, mutation score |
| `qual-integration` | Integração | configs Testcontainers + ITs existentes | cenários faltantes, setup/teardown, @ServiceConnection |
| `qual-functional` | Funcional | user stories + BDD scenarios existentes | cobertura de ACs, Gherkin faltante, contrato de API |
| `qual-perf` | Performance | SLA definido + JMH/k6 existentes | thresholds, regressions, SLAs sem teste |

### Sequência de Execução

```
1. GATE 1 — ativar modo subagente?
   SE pedido de revisão completa OR feature multi-camada: SIM → prosseguir
   SE um teste específico OR questão conceitual: NÃO → resposta direta

2. EXTRAIR contexto por camada:
   ctx_unit    = código da(s) classe(s) + testes unitários existentes
   ctx_integ   = testes de integração + configs Testcontainers
   ctx_func    = user stories + cenários BDD + testes de contrato
   ctx_perf    = SLAs definidos + scripts k6/JMH existentes

3. LANÇAR 4 workers EM PARALELO com Task:
   Todos correm simultaneamente com seus contextos isolados.

4. CIRCUIT BREAKER:
   MAX_WORKERS = 4 | MAX_RETRIES = 2 | TIMEOUT = 120s

5. SÍNTESE — você (supervisor) detecta lacunas inter-camadas:
   Ex: cobertura unitária alta + zero testes de contrato = risco oculto
   Ex: 95% line coverage + mutation score 40% = testes frágeis
   Emite relatório de saúde da suite + plano de melhoria priorizado
```

### Prompt Padrão dos Workers

```
Você é um especialista em testes de [CAMADA] rodando como subagente isolado.
Contexto fornecido:

{ctx_WORKER}

Analise EXCLUSIVAMENTE a camada [CAMADA] da pirâmide de testes.
Não invente lacunas — só reporte o que você viu (ou não viu) no contexto fornecido.

Retorne APENAS este JSON:
{
  "worker": "qual-[camada]",
  "status": "success|partial|failed",
  "cobertura_estimada": "0-100%",
  "lacunas": [
    {
      "tipo": "cenário faltante | test smell | coverage gap | sem SLA testado",
      "descricao": "o que está faltando e por quê importa",
      "prioridade": "critica|alta|media|baixa",
      "sugestao": "como criar o teste que resolve isso"
    }
  ],
  "saude_camada": "SAUDAVEL|FRAGILIDADES|CRITICA",
  "resumo": "max 2 linhas"
}
```

---
