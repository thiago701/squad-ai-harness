# Execução observável do review — grafo, monitor ASCII, watchdog e gates de entrega

> Parte da skill `tech-lead-review`. Hub: `../SKILL.md`. Regras dos gates: `governance/politica-gates-entrega.md`.
> Marcas/níveis: `governance/politica-evidencias-sigilo-qualidade.md`. Diagnóstico, riscos e benchmark que
> motivaram este desenho: `docs/evolucao-aws-2026-10-08/execucao-observavel.md`.

## 1. Como rodar

```bash
python -m scripts.revisao executar --monitor 300                              # checagens mecânicas
python -m scripts.revisao executar --monitor 300 --gates-entrega review --destino master
python -m scripts.revisao grafo                                               # grafo + caminho crítico
python -m scripts.revisao retomar <id>                                        # reaproveita só o que segue válido
python -m scripts.gates verificar --checkpoint review --destino master --monitor 300
```

O grafo vem da pipeline REAL (`ops/run.py::t_gate`) + gates de entrega + consolidação — o monitor exibe
exatamente os nós executados; não existe lista paralela que desatualize.

## 2. Ler o monitor

| Marca | Estado | Leitura correta |
|---|---|---|
| `[OK]` | aprovado | evidência do nó registrada |
| `[>>]` | executando | "progresso há Ns" = avanço verificável; "atividade há Ns" = só heartbeat |
| `[..]` | pendente / na fila / aguardando | o motivo diz qual dependência, worker ou recurso falta |
| `[!!]` | bloqueado | gate em BLOCKED/INCONCLUSIVE/STALE ou dependência externa |
| `[ER]` | falhou / timeout | timeout nunca vira aprovação; processo e filhos foram encerrados |
| `[--]` | não aplicável / não executado | justificativa verificável (verificação equivalente) — ou **NÃO EXECUTADO** (binário ausente): nó opcional, listado como ressalva, nunca conta como aprovado |
| `[CA]` | cancelado | não executado e por quê (bloqueador definitivo, orçamento, Ctrl+C) |

Relatório inicial, mini-relatório a cada 300 s (relógio do runtime, thread própria), alerta imediato de
bloqueio/falha/suspeita de travamento e relatório final — também em cancelamento. Sem percentual nem
previsão de término. A linha **Push** só repete a decisão central; o monitor nunca decide.

## 3. Travamento × lentidão × espera

- **Heartbeat sem progresso** além de `sem_progresso_s` → alerta "suspeita de travamento" (com atividade) ou
  "provável travamento" (sem atividade). Passar de 5 minutos, sozinho, não é travamento.
- **Deadline do nó** (1º início + `timeout_s`, limitado pelo orçamento total) → watchdog cancela e mata o grupo
  de processos; o nó vira `[ER]` com o diagnóstico; dependentes são cancelados com motivo.
- **Retry** só para erro transitório, com backoff + jitter, dentro do MESMO prazo; permissão e configuração
  inválida nunca repetem.
- **Espera por pessoa/DBA/acesso** não segura a revisão: o gate gera a tarefa `gate-dep-*`, termina bloqueado e a
  retomada revalida tudo que venceu ou mudou.

## 4. Achados dos gates de entrega no laudo

Use os subagentes `database-schema-gate` e `environment-infrastructure-gate` (`.claude/agents/`). Cada achado
entra no laudo com a marca da política comum: divergência comprovada `[DIV]`, segredo/credencial `[SEC]`,
verificação impossível `[GAP]`, observação `[AN]`. INCONCLUSIVE e STALE bloqueiam como BLOCKED. O veredito
READY exige `gates de entrega = LIBERADO` (G5.5) e nenhum nó obrigatório reprovado (G5.6).

## 5. Nunca

Transformar timeout em aprovação, cancelamento em sucesso, ausência de resposta em "não aplicável",
heartbeat em evidência ou falha de acesso em alinhamento; editar política/exceção para liberar o próprio
bloqueio; usar `--no-verify` ou outra identidade para publicar.
