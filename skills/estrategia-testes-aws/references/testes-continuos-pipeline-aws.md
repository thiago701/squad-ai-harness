# Testes contínuos no pipeline — o que roda em cada estágio

> Reference de `estrategia-testes-aws`. Base: DevOps Guidance (DL.CI, DL.CD, DL.ADS, QA.TEM), REL08-BP02,
> AWS Deployment Pipeline Reference Architecture (DPRA), docs de CodeBuild/CodePipeline/CodeDeploy e
> Amazon Builders' Library. **Restrição da Squad:** não crie nem altere `.github/workflows` ou pipeline
> corporativo sem pedido explícito — a mesma matriz roda no harness local do projeto (`ops/run.py` ou
> equivalente) e o pipeline do banco chama os mesmos comandos.

## 1. Princípios

- **DL.CI.3** — QA automático em todo build: estágios pré-deploy com testes funcionais, não funcionais e
  de segurança. **Quebrar o build** só para falha de build, achado de segurança de alta severidade e
  conformidade inegociável; o resto vira feedback para o dev. Política de qualidade aplicada **no CD,
  por ambiente**, com mecanismo de exceção.
- **DL.CI.5** — comece cedo e em paralelo o que demora; deixe para depois o que falha pouco.
- **DL.CD.3** — QA **depois de cada deploy** (funcional, não funcional, segurança, dados): "Deployments
  to environments is the ideal enforcement point for quality assurance".
- **REL08-BP02** (risco alto se ausente) — falha de teste aborta o deploy; **mesmo mecanismo de deploy
  em todos os ambientes**.
- **DL.ADS.1** — validar em alpha/beta/gamma; one-box; zeta (fala só com endpoints de produção para
  testar compatibilidade).

## 2. Matriz por estágio (DPRA + Builders' Library + DevOps Guidance)

| estágio | testes e controles | gate | tempo-alvo |
|---|---|---|---|
| local / pré-commit | unitário, lint, segredos (git-secrets/gitleaks), cfn-lint, cdk-nag, Guard | feedback local | segundos |
| build (PR) | unitário com relatório, cobertura, **SAST**, **SCA + SBOM**, **segredos** (falha imediata), IAM Access Analyzer, CDK assertions, `terraform test` com `plan`, scan de imagem; artefato construído e assinado **uma vez** | bloqueante | **< 10 min** (DPRA) |
| ambiente efêmero (PR/branch) | integração na nuvem, contrato, smoke, `terraform test` com `apply` + destroy, TaskCat | bloqueante | minutos |
| Beta | integração e aceitação (poucos E2E), mudanças de banco seguras para rollback | bloqueante | **< 30 min** |
| Gamma (igual a produção, mesmas regiões) | alarmes na IaC com rollback, **sintéticos**, **load curto** comparado a execuções anteriores, **DAST**, autorização, **FIS como regressão** ("Any significant deviation should fail the pipeline") | bloqueante | **< 30 min** |
| periódico (fora do commit) | stress (~mensal), soak (trimestral/semestral), restore de backup (mensal/trimestral), DR (semestral/anual), pentest, game day | retro + backlog | — |
| produção | deploy progressivo (one-box, ondas, canário/linear), **bake time**, rollback automático por alarme, sintéticos contínuos, flags | alarme agregado → rollback | — |

A DPRA não fixa cobertura mínima, bake time nem limiar de erro: esses valores vêm do SLO do serviço.

## 3. CodeBuild — relatórios

- Testes: JUnit XML, Cucumber JSON, NUnit/NUnit3, TestNG, TRX — seção `reports:` do buildspec.
- Cobertura: **JaCoCo XML**, Cobertura XML, Clover, SimpleCov, LCOV (linha e branch).
- **Relatórios expiram em 30 dias** — exporte para S3 se precisar de histórico (QA.TEM.3: resultados
  centralizados, versionados, criptografados, com escrita restrita e política de retenção).
- Batch builds com **testes paralelos** em ambientes isolados (`codebuild-tests-run`, divisão de
  testes) e relatórios mesclados.

```yaml
reports:
  junit:
    files: ['target/surefire-reports/*.xml']
    file-format: JUNITXML
  cobertura:
    files: ['target/site/jacoco/jacoco.xml']
    file-format: JACOCOXML
```

## 4. CodePipeline — gates

- Test actions: CodeBuild, Device Farm (e ferramentas de terceiros).
- **Stage conditions**: entrada (Fail/Skip — ex.: alarme ativo, fora da janela), on failure (Rollback),
  on success (Rollback/Fail). Regras: `CloudWatchAlarm`, `CodeBuild`, `Commands`, `DeploymentWindow`,
  `LambdaInvoke`, `VariableCheck`.
- **Stage rollback** manual ou automático para a última execução bem-sucedida.

## 5. Ambientes e dados de teste (QA.TEM)

- **QA.TEM.1** — ambientes dedicados e parecidos com produção (no mínimo staging monitorado), por IaC;
  acesso humano excepcional e auditado.
- **QA.TEM.2** — test beds **imutáveis e efêmeros** por execução; restauração automática de dados;
  **não apague logs e dados úteis para depuração** junto com o test bed.
- **QA.TEM.4** — repositório de dados de teste versionado e **sanitizado** (masking, encryption,
  tokenization) com contrato; nunca produção sem ofuscação.
- **QA.TEM.5** — paralelismo com isolamento de dados.
- **DL.LD.8** — datasets sintéticos (inclusive gerados por IA para casos de borda).
- Banco: dado real de cliente fora de produção é proibido; credenciais só por variável de ambiente ou
  Secrets Manager.

## 6. Seleção de testes (QA.FT.4, opcional)

Antes de selecionar, otimize: paralelize, remova obsoletos, reordene. Depois, análise de impacto. Seleção
preditiva só com controles: suíte completa assíncrona, aprovação da cobertura e **nunca excluir testes de
segurança** nem aplicar em sistema crítico.

## 7. Antipadrões (DevOps Guidance e REL08-BP02)

Check-in raro; build e teste manuais; build agendado em vez de por commit; testar só em produção; feedback
inútil; deploy direto em produção; ignorar rollback e compatibilidade de dados; lançamento abrupto;
contornar falha de teste para acelerar; pular teste em fluxo emergencial; testar em ambiente diferente de
produção; teste instável sem quarentena e sem correção da causa.

## Modelo de plano (copiar para o projeto)

```markdown
| estágio | tipos | conta/ambiente | ferramenta | oráculo | tempo-alvo | quem aprova | status |
|---|---|---|---|---|---|---|---|
| build | unitário, SAST, SCA, segredos, IaC estático | CI | ... | 0 falha, 0 achado alto | < 10 min | automático | |
| efêmero | integração, contrato | conta teste | ... | jornada X ok | < 15 min | automático | |
| gamma | E2E, load curto, DAST, FIS | pré-prod | ... | SLO mantido | < 30 min | automático | |
| produção | canário + sintético | prod | ... | alarmes verdes no bake | — | alarme | |
Inconclusivos (motivo): ...
```

## Fontes

- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/dl.ci.3-ensure-automated-quality-assurance-for-every-build.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/dl.ci.5-sequence-build-actions-strategically-for-prompt-feedback.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/dl.cd.3-integrate-quality-assurance-into-deployments.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/dl.ads.1-test-deployments-in-pre-production-environments.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/test-environment-management.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/qa.ft.4-balance-developer-feedback-and-test-coverage-using-advanced-test-selection.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/dl.ld.7-establish-sandbox-environments-with-spend-limits.html
- https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_tracking_change_management_functional_testing.html
- https://aws-samples.github.io/aws-deployment-pipeline-reference-architecture/application-pipeline/index.html
- https://docs.aws.amazon.com/codebuild/latest/userguide/test-reporting.html
- https://docs.aws.amazon.com/codebuild/latest/userguide/code-coverage-report.html
- https://docs.aws.amazon.com/codebuild/latest/userguide/parallel-test.html
- https://docs.aws.amazon.com/codepipeline/latest/userguide/stage-conditions.html
- https://docs.aws.amazon.com/codepipeline/latest/userguide/stage-rollback.html
