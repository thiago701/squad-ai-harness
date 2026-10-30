# DR, failover, restauração e AWS Resilience Hub

> Reference de `testes-resiliencia-caos-aws`. Base: REL09-BP04 (restauração periódica), REL13-BP03
> (testes de DR), DevOps Guidance QA.NT.6, página do Resilience Hub e doc do Route 53 ARC (zonal autoshift).

## 1. Cadência recomendada (DevOps Guidance QA.NT.6)

| teste | frequência | observação |
|---|---|---|
| caos (FIS/Resilience Hub) | no pipeline, após o deploy | começar em teste, depois produção com raio limitado |
| recuperação de dados | mensal ou trimestral, e após migração/mudança de schema | ex.: após deploy de schema, testar a integridade do backup |
| disaster recovery | semestral ou anual | janela fora de pico, com aviso; automatize sub-tarefas e checagens |

Multirregião: nunca derrube todas as regiões; comece por uma. Sempre retrospectiva.

## 2. Teste de restauração (REL09-BP04)

1. Restaure **em recurso novo e isolado** (DynamoDB PITR/backup, RDS snapshot/PITR, S3 versionado,
   AWS Backup) — nunca por cima do original.
2. **Valide os dados**: checksum, contagem, último registro esperado.
3. Meça **tempo × RTO** (timestamps do CloudTrail ou dos jobs do AWS Backup) e **perda × RPO**.
4. Notifique falha (SNS/OpsCenter) e **automatize** (EventBridge + Lambda ou Step Functions).
5. Destrua o restaurado e registre a evidência.

Antipadrões: assumir que o backup existe; restaurar sem consultar os dados; não ter runbook.

## 3. Failover e DR (REL13-BP03 — risco alto se ausente)

- Antipadrão explícito: **nunca testar failover em produção**.
- Teste cada caminho de recuperação contra RTO/RPO; evite caminhos raramente exercitados (réplica sem
  capacidade para assumir).
- Faça failover para o standby **regularmente, independentemente de necessidade**.
- **AWS Elastic Disaster Recovery**: drills sem redirecionar tráfego.
- Multi-AZ (RDS, ElastiCache) com FIS (`aws:rds:failover-db-cluster`, interrupção de energia de AZ);
  multirregião (Aurora Global, DynamoDB global tables) com o cenário Cross-Region: Connectivity e o runbook.

## 4. Route 53 ARC — zonal shift e zonal autoshift

- Zonal shift move o tráfego para fora de uma AZ com problema; **zonal autoshift** faz isso
  automaticamente quando a AWS detecta impacto.
- Com autoshift, **practice runs são obrigatórios**: a AWS desloca o tráfego de uma AZ cerca de uma vez
  por semana para provar que o recurso aguenta; execução interrompida por condição de bloqueio não conta.
- Pressupõe recursos **pré-escalados em todas as AZs**. O FIS pode disparar (`aws:arc:start-zonal-autoshift`).

## 5. AWS Resilience Hub

- Políticas de resiliência com **SLO de disponibilidade, RTO, RPO** e estratégia de DR.
- **Assessment** da aplicação contra as políticas e o Well-Architected, com recomendações priorizadas,
  descoberta de dependências e **testes de resiliência** sugeridos (inclusive experimentos do FIS) e
  alarmes.
- REL09-BP04 usa o Resilience Hub para checar se RTO/RPO são atingíveis.
- Uso na Squad: rodar o assessment ao fechar a arquitetura e a cada mudança relevante; transformar as
  recomendações em itens do plano de testes.

## 6. Evidência mínima de DR

| item | evidência |
|---|---|
| último restore testado | data, recurso, duração medida, perda medida, validação dos dados |
| último failover | data, caminho, RTO medido, problemas encontrados |
| runbook | versão, dono, última execução |
| alarmes | prova de que dispararam no teste |

Sem evidência recente dentro da cadência: **DR não comprovado** (inconclusivo, nunca aprovado).

## Fontes

- https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_backing_up_data_periodic_recovery_testing_data.html
- https://docs.aws.amazon.com/de_de/wellarchitected/latest/reliability-pillar/rel_planning_for_recovery_dr_tested.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/qa.nt.6-experiment-with-failure-using-resilience-testing-to-build-recovery-preparedness.html
- https://aws.amazon.com/resilience-hub/
- https://docs.aws.amazon.com/r53recovery/latest/dg/arc-zonal-autoshift.how-it-works.html
- https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/test-reliability.html
