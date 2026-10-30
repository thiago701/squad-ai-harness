# Testes em produção — canário, rollback por alarme, sintéticos e flags

> Reference de `estrategia-testes-aws`. Base: docs do SAM/CodeDeploy/AppConfig/CloudWatch Synthetics,
> DevOps Guidance DL.ADS e Amazon Builders' Library ("Automating safe, hands-off deployments").
> Regra da Squad: em produção, **só teste não destrutivo** por padrão; caos e carga em produção exigem
> aprovação explícita, janela, condição de parada e as políticas da AWS e do banco.

## 1. Deploy canário/linear com CodeDeploy (Lambda e ECS)

- SAM: `AutoPublishAlias` + `DeploymentPreference` com `Type`, `Alarms` e `Hooks`.
- Tipos para Lambda: `LambdaCanary10Percent{5,10,15,30}Minutes`, `LambdaLinear10PercentEvery{1Minute,2,3,10Minutes}`,
  `LambdaAllAtOnce` (ou configuração própria). ECS: `ECSCanary10Percent{5,15}Minutes`,
  `ECSLinear10PercentEvery{1,3}Minutes`, `ECSAllAtOnce`.
- **Hooks** `PreTraffic` e `PostTraffic` são Lambdas de validação; falha de hook ou alarme em ALARM →
  **rollback automático**.
- O primeiro deploy é sem `DeploymentPreference` (precisa existir versão anterior).

```yaml
MinhaFuncao:
  Type: AWS::Serverless::Function
  Properties:
    AutoPublishAlias: live
    DeploymentPreference:
      Type: Canary10Percent10Minutes
      Alarms: [!Ref AlarmeErros5xx, !Ref AlarmeLatenciaP99]
      Hooks:
        PreTraffic: !Ref ValidaAntesDoTrafego
        PostTraffic: !Ref ValidaDepoisDoTrafego
```

## 2. Rollback e ondas (DevOps Guidance + Builders' Library)

- **DL.ADS.2** — rollback automático por alarmes (taxa de falha, latência, CPU, memória, erros de log);
  período de espera pós-deploy; bloquear deploy com alarme agregado de alta severidade ou em janela de risco.
- **DL.ADS.3** — ondas progressivas começando por **one-box**; rolling de até **33%** por vez mantendo
  **≥ 66%** saudável; blue/green quando precisar de mais controle.
- **Builders' Library** — one-box com no máximo **~10%** das requisições; **bake time ≥ 1 h** após
  one-box, **≥ 12 h** após a primeira onda regional, **2–4 h** nas demais, com mínimo de pontos de dados;
  alarme agregado (alarmes + canários) desfaz os deploys da equipe na região; deploy só em horário comercial.
- Setores regulados: aprovação manual antes de produção continua válida (DL.CD.7 é opcional).

## 3. CloudWatch Synthetics (canaries)

- Scripts agendados que "follow the same routes and perform the same actions as a customer … even when you
  don't have any customer traffic"; frequência até **1 por minuto**.
- Node.js, Python ou Java, executando como Lambda na conta; navegador headless via Playwright, Puppeteer ou
  Selenium **(terceiros)** em Node/Python.
- Blueprints: heartbeat, **API canary** (multi-step com GET/POST/PUT/PATCH/DELETE, APIs privadas), broken
  link, **visual monitoring** (comparação com baseline), recorder, GUI workflow, **multi checks** (até 10
  checagens HTTP/DNS/SSL/TCP com auth via Secrets Manager).
- Métricas no namespace `CloudWatchSynthetics` (`CanaryName`, `StepName`), screenshots, X-Ray,
  Application Signals (SLO).
- Usos: smoke pós-deploy, canário de usuário em experimento de caos, entrada do alarme de rollback,
  tráfego mínimo para alarmes funcionarem fora do horário.
- Cuidados no banco: conta e massa de teste dedicadas e marcadas; nunca dado real de cliente; segredos do
  canary no Secrets Manager.

## 4. Feature flags e experimentação (AppConfig)

- Perfil de feature flag com atributos e constraints; flags multivariantes por contexto.
- Estratégias de deploy **Linear** ou **Exponential**, com **bake time**: alarme durante o bake →
  **rollback** automático da configuração.
- **DL.ADS.4** — dark launch, deploy em duas fases (preparar/ativar), flags, canary release.
- **QA.NT.4** — A/B em produção com flags até significância estatística (a doc também cita CloudWatch
  Evidently — verifique a disponibilidade atual antes de recomendar).

## 5. SLO como oráculo em produção (Application Signals)

- SLI = métrica + limiar; meta; janela calendário ou móvel; **error budget**.
- Disponibilidade request-based: 5xx = falha, 4xx = sucesso.
- **Burn rate** = taxa de erro na janela / (100% − meta). Alarme multi-janela (curta = 1/12 da longa).
- O SLO é o "teste" contínuo de produção: canary, caos e carga verificam se o error budget aguenta.

## Fontes

- https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/automating-updates-to-serverless-apps.html
- https://docs.aws.amazon.com/codedeploy/latest/userguide/deployment-configurations.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/dl.ads.2-implement-automatic-rollbacks-for-failed-deployments.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/dl.ads.3-use-staggered-deployment-and-release-strategies.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/dl.ads.4-implement-incremental-feature-release-techniques.html
- https://builder.aws.com/content/3ErTKQOTKc5NIw031UePBPxTQ6I/automating-safe-hands-off-deployments
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Synthetics_Canaries.html
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Synthetics_Canaries_Blueprints.html
- https://docs.aws.amazon.com/appconfig/latest/userguide/appconfig-creating-configuration-and-profile-feature-flags.html
- https://docs.aws.amazon.com/appconfig/latest/userguide/appconfig-creating-deployment-strategy.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/qa.nt.4-enhance-user-experience-gradually-through-experimentation.html
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-ServiceLevelObjectives.html
