# Matriz de combinação — risco × tipo de teste × estágio × custo

> Reference de `estrategia-testes-aws`. Síntese da Squad sobre as recomendações da AWS (PG serverless,
> DevOps Guidance, REL08/REL12, Builders' Library). Use para montar o plano: comece pelos riscos, não
> pelas ferramentas.

## 1. Risco → teste que prova na camada mais barata

| risco | camada mais barata que prova | complemento obrigatório na AWS |
|---|---|---|
| regra de negócio errada | unitário (lógica pura) | — |
| mapeamento de evento/resposta errado | unitário do handler com evento real (`aws-lambda-java-tests`, sample events do Powertools) | integração na nuvem |
| permissão IAM faltando ou ampla demais | Access Analyzer no PR (validate-policy, custom checks) | integração na nuvem (só ela prova a role efetiva) |
| timeout, memória, tamanho de payload | — (não se mocka com fidelidade) | integração na nuvem + Power Tuning |
| evento assíncrono perdido ou duplicado | — | test harness na nuvem (listener + polling com SLA) |
| quebra de contrato com consumidor | contrato estático (`contrato-reverso`) | verificação no Gateway implantado |
| workflow com retry/catch errado | TestState API com mock | execução real na conta efêmera |
| regressão de latência | load curto em Gamma comparado ao histórico | — |
| não aguentar o pico | carga/stress em pré-prod com quotas checadas | sintético + alarme em produção |
| dependência fora do ar | FIS em pré-prod (stop condition) | game day; regressão automática |
| backup inútil / failover que não funciona | restore e failover reais medindo RTO/RPO | cadência mensal/semestral |
| vulnerabilidade de código ou dependência | SAST/SCA/segredos no PR | Inspector contínuo; DAST em pré-prod |
| BOLA/IDOR | teste automatizado com duas identidades em efêmero/pré-prod | DAST e pentest com foco em lógica |
| template inseguro ou que substitui recurso | cfn-lint + Guard + assertions no PR | change set/plan revisado; drift e Config |
| release piora produção | — | canário/linear com alarme e rollback; bake time |

## 2. Combinações por arquitetura

### API serverless (API Gateway + Lambda + DynamoDB)
- PR: unitário do domínio e do handler, contrato estático, IaC estático/política, Access Analyzer, SAST/SCA.
- Efêmero: integração chamando o endpoint real; isolamento entre usuários (BOLA); erros 4xx/5xx do Gateway.
- Gamma: E2E das jornadas críticas, load curto, DAST, FIS (latência/erro na Lambda ou no DynamoDB).
- Produção: canário 10% + alarmes 5xx/p99 + canary sintético da jornada principal.

### Orientado a eventos (EventBridge/SQS/SNS/Kinesis)
- Unitário por consumidor; schema test no produtor (EventBridge Schema Registry) e contract test no consumidor.
- Efêmero: harness com listener e ID de correlação; DLQ e reprocessamento; idempotência com duplicata real.
- Gamma: carga com picos (backlog e taxa de escalonamento); FIS de throttling de API (`inject-api-throttle-error`).

### Contêiner (ECS/Fargate + ALB)
- Unitário + integração com Testcontainers **(terceiro)** para o código.
- Efêmero/Gamma: IAM da task, rede, health check, escalonamento (degraus maiores que o período do gatilho).
- FIS: `aws:ecs:stop-task`, latência e perda de pacotes na task, cenário de AZ.

### Workflow (Step Functions)
- TestState API por estado (mocks, retry/catch, Map); execução real da máquina na efêmera; caos nas tarefas.

### Infra compartilhada (rede, contas, Terraform/CDK de plataforma)
- PR: lint, política, unitário de template; efêmero: TaskCat ou `terraform test` com apply; contínuo: Config,
  drift, Security Hub CSPM.

## 3. Custo × confiança

- Nuvem custa mais e é mais lenta, porém é a única evidência de IAM, quotas e configuração. Mitigue com
  stack por branch, recursos caros compartilhados, `command = plan` onde não precisa criar recurso e
  ambiente em escala de produção **sob demanda** (paga só enquanto o teste roda).
- Mock e emulador são baratos, mas dão falsa confiança fora da lógica pura.
- Frequências do DevOps Guidance equilibram custo e risco: load a cada mudança; stress mensal; soak
  trimestral/semestral; restore mensal/trimestral; DR semestral/anual.
- Custos residuais esquecidos: dashboards do Distributed Load Testing, versões SnapStart em cache, FIS por
  minuto de ação, Access Analyzer por check, Inspector por scan, logs em DEBUG sob carga.

## 4. Orçamentos de tempo sugeridos (ponto de partida)

| estágio | orçamento | origem |
|---|---|---|
| build | < 10 min | DPRA |
| Beta / Gamma | < 30 min cada | DPRA |
| bake em produção | ≥ 1 h após one-box; 2–12 h por onda | Builders' Library |
| feedback local | segundos (unitário) | prática da Squad |

## Fontes

- https://docs.aws.amazon.com/prescriptive-guidance/latest/serverless-application-testing/best-practices.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/serverless-application-testing/challenges.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/qa.nt.2-validate-system-reliability-with-performance-testing.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/qa.nt.6-experiment-with-failure-using-resilience-testing-to-build-recovery-preparedness.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/qa.nt.7-verify-service-integrations-through-contract-testing.html
- https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/test-reliability.html
- https://aws-samples.github.io/aws-deployment-pipeline-reference-architecture/application-pipeline/index.html
- https://builder.aws.com/content/3ErTKQOTKc5NIw031UePBPxTQ6I/automating-safe-hands-off-deployments
- https://raw.githubusercontent.com/aws-samples/serverless-test-samples/main/typescript-test-samples/schema-and-contract-testing/README.md
- https://docs.aws.amazon.com/prescriptive-guidance/latest/load-testing/test-types.html
