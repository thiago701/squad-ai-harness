# Serverless — testar na nuvem (Lambda, API Gateway, Step Functions, eventos)

> Reference de `estrategia-testes-aws`. Base: Lambda Developer Guide, Prescriptive Guidance "Testing
> serverless applications on AWS", aws-samples/serverless-test-samples, docs do SAM e da TestState API.

## 1. A recomendação central: "test in the cloud"

- Lambda Guide: "Cloud-based tests provide the **most accurate** measure of quality". O CI deve rodar
  testes "against a suite of resources provisioned in the cloud before promoting your code".
- PG: "we recommend that you focus on testing in the cloud as much as possible" — vale para unitário,
  integração e E2E.
- O que **só a nuvem pega** (PG, página de desafios): ação IAM faltando na role, falha na invocação
  SQS→Lambda, visibility timeout baixo gerando duplicidade, evento acima do limite de tamanho.
- "You don't need to test these managed services. However, you must test how your code integrates with them."

## 2. Mock × emulador × nuvem

| técnica | serve para | não pega | posição da AWS |
|---|---|---|---|
| mock | lógica complexa com muitas variações; falhas difíceis de reproduzir; SaaS de terceiro | IAM, quotas, limite de payload, efeitos colaterais | "Don't use mocks of cloud services to validate the proper implementation of those service integrations"; **nunca em E2E** |
| emulador (SAM local, DynamoDB Local; LocalStack **(terceiro)**) | feedback offline, ambiente regulado sem nuvem | IAM (identidade placeholder), quotas, novidades dos serviços | "**Use emulators sparingly** … you must still test in the cloud" |
| nuvem | integração, configuração, IAM, quotas, API atual | — (custa tempo e dinheiro) | **prioridade** em todas as fases |

Código coberto por unitário com mock "should also be covered by testing in the cloud" (PG).

## 3. Código testável — handler fino

- "Your Lambda function handler should be a **slim adapter**" (Lambda Guide).
- Fronteira externa (handler): extrai `event`/`context`, valida, formata a resposta → teste de
  integração focado. Fronteira interna (domínio): lógica pura, sem objetos do runtime → unitários
  abrangentes, "without mocking Lambda objects" (PG).
- Clientes do SDK inicializados **fora do handler** e injetáveis (classe, parâmetro ou fábrica).
- Hexagonal (PG): `domain/tests`, `adapters/tests`, `entrypoints/api/tests`.

## 4. Ferramentas por linguagem

| linguagem | unitário | observação |
|---|---|---|
| Java | `com.amazonaws:aws-lambda-java-tests` (`EventLoader`, `@Event`, `@Events`, `@HandlerParams` com `@ParameterizedTest`), JUnit 5 e Mockito **(terceiros)** | Powertools Java Tracing exige `LAMBDA_TASK_ROOT` nos testes (via surefire/Gradle `environmentVariables`); transforme eventos reais que falharam em casos de regressão |
| Python | botocore `Stubber` (AWS), Moto **(terceiro)**, Powertools | fixture `lambda_context` do Powertools; `POWERTOOLS_IDEMPOTENCY_DISABLED` para testar só o negócio; Tracer desligado fora da Lambda |
| Node/TS | aws-sdk-client-mock **(terceiro, divulgado pela AWS)**, Jest/Vitest | `POWERTOOLS_DEV=true` + `--silent` silencia logs |

## 5. SAM CLI para teste

| comando | uso |
|---|---|
| `sam local invoke <Id> -e evento.json` | depuração local em contêiner; chamadas a outros serviços **vão para recursos reais**; não usar com código não confiável |
| `sam local start-api` / `start-lambda` | o mesmo teste roda contra o endpoint local (`127.0.0.1:3001`) e contra a função implantada, sem mudar código |
| `sam local generate-event` | fixtures de eventos |
| `sam remote invoke` | invoca na nuvem: Lambda, SQS, Kinesis, Step Functions |
| `sam remote test-event {list,get,put,delete}` | eventos de teste compartilháveis (EventBridge Schema Registry) |
| `sam sync` (SAM Accelerate) / CDK watch | ciclo rápido de teste na nuvem; nome de stack único por desenvolvedor |

Teste de integração típico: roda **na máquina ou no CI**, lê os outputs da stack implantada
(`sam list stack-outputs --stack-name …` ou `AWS_SAM_STACK_NAME`) e chama os recursos reais.

## 6. Step Functions — TestState API

- Testa um estado isolado (ou a definição inteira com `stateName`) **sem criar a state machine**.
- Níveis: `INFO`, `DEBUG` (mostra cada transformação: `afterInputPath`, `afterParameters`,
  `afterResultSelector`, `afterResultPath`), `TRACE` (HTTP Task; `revealSecrets` exige permissão própria).
- **Mocks** (`result` ou `errorOutput`): com mock o `roleArn` é opcional; obrigatório para Map,
  Parallel, Activity, `.sync`, `.waitForTaskToken`. Validação do mock contra o modelo da API
  (`fieldValidationMode` STRICT/PRESENT/NONE).
- Verifica: qual Catch pega o erro (`catchIndex`), qual Retry se aplica (`retryIndex`, backoff),
  transformações de dados, Map (`afterItemsPath`, tolerância a falhas) e propagação de erro.
- Depois, uma execução real da máquina na conta efêmera fecha a integração.

## 7. Fluxos assíncronos — test harness

- Infra de teste implantada **junto com a aplicação**, só em ambiente de teste (parâmetro
  `DeployTestResources=true|false` no template): listener nos mesmos eventos, armazenamento do
  resultado (DynamoDB/S3) e **polling** no teste.
- SLA da operação assíncrona = timeout do polling; **ID único por execução** (correlação); harness na
  IaC; limpeza ao final.
- Teste **na fronteira, não através dela** (regra do EventBridge, endpoint, workflow, stream): verifique
  sincronamente o máximo possível; cada teste assíncrono com escopo estreito.

## 8. Ambientes isolados

- Ideal: conta por desenvolvedor. Conta compartilhada: **stack por dev/branch** com prefixo único.
- Compartilhe o caro (cluster RDS) e isole o barato (Lambda, estágio do API Gateway, tabela DynamoDB).
- Configuração por stack no Parameter Store; alertas de custo e limites de tamanho/tipo de recurso.
- DevOps Guidance DL.LD.7: sandbox com **limite de gasto**, ciclo de vida efêmero automatizado e sem
  conectividade com redes internas.

## 9. Matriz do sample Java oficial (`apigw-lambda-ddb`)

| teste | técnica | ferramentas |
|---|---|---|
| unitário | handler isolado, DynamoDB mockado | JUnit 5, Mockito, aws-lambda-java-tests |
| local com contêiner | emulação | LocalStack **(terceiro)**, Docker |
| integração | tabela real implantada | SDK + credenciais da conta de teste |
| E2E | stack inteira na AWS (API → DynamoDB, ARNs, permissões) | HTTP + SDK |
| carga | na nuvem antes da primeira ida a produção, pico esperado + 10% ou mais | Artillery **(terceiro)** |

## Fontes

- https://docs.aws.amazon.com/lambda/latest/dg/testing-guide.html
- https://docs.aws.amazon.com/lambda/latest/dg/testing-functions.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/serverless-application-testing/techniques.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/serverless-application-testing/best-practices.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/serverless-application-testing/challenges.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/serverless-application-testing/faq.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/best-practices.html
- https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-using-automated-tests.html
- https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/using-sam-cli-remote-invoke.html
- https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/using-sam-cli-remote-test-event.html
- https://docs.aws.amazon.com/step-functions/latest/dg/test-state-isolation.html
- https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.html
- https://aws.amazon.com/blogs/opensource/testing-aws-lambda-functions-written-in-java/
- https://aws.amazon.com/blogs/devops/unit-testing-aws-lambda-with-python-and-mock-aws-services/
- https://aws.amazon.com/blogs/developer/mocking-modular-aws-sdk-for-javascript-v3-in-unit-tests/
- https://docs.aws.amazon.com/powertools/python/latest/utilities/idempotency/
- https://docs.aws.amazon.com/powertools/java/latest/core/tracing/
- https://raw.githubusercontent.com/aws-samples/serverless-test-samples/main/Serverless-Testing-Principles.md
- https://raw.githubusercontent.com/aws-samples/serverless-test-samples/main/python-test-samples/async-lambda-dynamodb/README.md
- https://raw.githubusercontent.com/aws-samples/serverless-test-samples/main/java-test-samples/apigw-lambda-ddb/README.md
