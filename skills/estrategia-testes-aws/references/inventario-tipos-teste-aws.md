# Inventário — tipos de teste segundo a AWS

> Reference de `estrategia-testes-aws`. Pesquisa de 17/10/2026 em fontes oficiais da AWS (Lambda
> Developer Guide, Prescriptive Guidance, Well-Architected, DevOps Guidance, blogs e aws-samples).
> **(terceiro)** = não é da AWS. URLs no fim. Mudanças recentes que alteram recomendações antigas
> estão na seção 0 — leia antes de citar material com mais de um ano.

## 0. Avisos de atualidade (verificados em 17/10/2026)

| tema | situação | o que fazer |
|---|---|---|
| Step Functions Local | a doc oficial agora diz "**unsupported**", sem paridade de recursos | use a **TestState API** (aceita mocks desde nov/2025, inclusive Map, Parallel, `.sync`, `.waitForTaskToken`) |
| Amazon CodeGuru Security | fim do suporte em **20/11/2025**; SEC11-BP02 e DevOps Guidance QA.ST.4 ainda o citam | SAST pelo **Amazon Inspector code security** (CI/repositório) e Amazon Q Developer (IDE); no banco, Veracode |
| Amazon Q Developer (plugins de IDE) | fim do suporte em **30/04/2027**; a AWS indica o **Kiro** | o `/test` (Java e Python, um arquivo por vez) tem prazo; revise sempre o diff gerado |
| Whitepaper "Practicing CI/CD" | marcado "for historical reference only" | é a única fonte AWS com proporção da pirâmide (~70% unitário) — cite com essa ressalva |
| Device Farm | só em `us-west-2` (Oregon) | considere residência de dados e pipelines multirregião |
| Cobrança do INIT do Lambda | desde 01/08/2025 o INIT entra no Billed Duration (ZIP + runtime gerenciado + on-demand) | cold start agora é custo, além de latência |
| Numeração do REL12 | o DevOps Guidance usa a numeração antiga | no pilar Reliability atual: BP03 escala/desempenho, BP04 caos, BP05 game days |

## 1. Definições oficiais (serverless e geral)

- **Unitário** — "Tests that run against an isolated block of code" (Lambda Guide); o Prescriptive
  Guidance (PG) define pelo **isolamento do componente**, não pela ausência de rede: um teste unitário
  pode rodar na nuvem (ex.: fila SQS de teste + Lambda implantada) e de quebra valida IAM, timeout e memória.
  DevOps Guidance **QA.FT.1** (FOUNDATIONAL): isolado, rápido, repetível, local e no CI, com TDD.
- **Integração** — "two or more components or services that interact, typically in a cloud
  environment". **QA.FT.2** (FOUNDATIONAL): componentes reais, **isolados de produção e de ambientes
  compartilhados**, setup/teardown por IaC, execução paralela.
- **Ponta a ponta (E2E)** — "verify behavior across an entire application". **Sem mocks** (PG).
- **Aceitação** — **QA.FT.3** (FOUNDATIONAL): comportamento observável do ponto de vista do usuário
  em ambiente parecido com produção, em três formas: E2E pelo pipeline (BDD; Device Farm ou Selenium),
  UAT com usuários reais, e **sintético** contínuo (inclusive em produção).
- **Emulador** — aplicação, muitas vezes de terceiro, que imita um serviço de nuvem.
- **Mock/fake** — substitui uma dependência por uma simulação dentro do teste.
- **Não funcional** — **QA.NT**: estático (NT.1), desempenho (NT.2), UX/acessibilidade (NT.3),
  experimentação A/B (NT.4), conformidade (NT.5), resiliência (NT.6), contrato (NT.7), sustentabilidade (NT.8).
- **Segurança** — **QA.ST**: gestão de vulnerabilidades, normalização de achados, avaliação de risco,
  SAST, DAST, SCA (ST.1–ST.6, base), pentest/red team (ST.7), IAST (ST.8, opcional).
- **Dados** — **QA.DT**: qualidade, profiling, lógica de transformação, anomalia, métricas incrementais.

## 2. Tabela por tipo

| tipo | quando | serviços/ferramentas AWS | terceiros comuns | antipadrões citados pela AWS |
|---|---|---|---|---|
| unitário (lógica pura) | build, a cada commit, local | botocore `Stubber` (Python), `aws-lambda-java-tests` (Java: `EventLoader`, `@Event`), Powertools (fixtures de contexto, env vars de teste), CodeBuild test reports | pytest, JUnit 5, Mockito, Jest/Vitest, Moto, aws-sdk-client-mock | cobertura alta com asserção fraca; teste escrito depois do defeito; mock de serviço "provando" integração |
| unitário na nuvem (componente isolado) | stack do dev/branch | SAM `sync`, `remote invoke`, CDK watch | — | achar que função "só de cálculo" dispensa nuvem (timeout, memória e permissão de log não se mockam com fidelidade) |
| workflow (Step Functions) | build/CI via API | **TestState API** (`INFO`/`DEBUG`/`TRACE`, mocks, `retryIndex`/`catchIndex`) | — | depender do Step Functions Local (sem suporte) |
| integração | conta efêmera / Beta | SAM (`start-lambda`, `remote invoke`, `remote test-event`), Parameter Store para config da stack, DynamoDB Local (complementar) | LocalStack, Testcontainers | só local/emulador; conta compartilhada sem fronteira; tocar produção |
| assíncrono (EDA) | conta efêmera | **test harness** implantado com a app: listener + DynamoDB/S3 + polling com SLA como timeout | — | testar "através" da fronteira em vez de na fronteira |
| contrato e schema | build do produtor e do consumidor | EventBridge Schema Registry (schema tests) | Pact, Spring Cloud Contract | só schema test (não pega regra de negócio) |
| E2E / aceitação | Beta/Gamma | CodePipeline test actions, Device Farm (dispositivo real e navegador desktop) | Selenium, Appium, Playwright | E2E demais (lento e caro); mock em E2E |
| sintético | Gamma + produção, contínuo | CloudWatch Synthetics (até 1/min), Application Signals, X-Ray | Playwright/Puppeteer/Selenium dentro do canary | sem alarme ligado ao canary |
| desempenho/carga | Gamma (load a cada mudança) | Distributed Load Testing on AWS, Lambda Power Tuning, X-Ray | JMeter, k6, Locust, Artillery | ver `testes-carga-desempenho-aws` |
| segurança | build (SAST/SCA/segredos) + Gamma (DAST) | Inspector, IAM Access Analyzer, Security Hub CSPM, GuardDuty | ZAP, gitleaks | ver `testes-seguranca-aws` |
| resiliência | Gamma → produção controlada | AWS FIS, Resilience Hub, Elastic Disaster Recovery, ARC | — | ver `testes-resiliencia-caos-aws` |
| infra (IaC) | PR + conta efêmera + contínuo | cfn-lint, cfn-guard, Hooks, change sets, drift, TaskCat, CDK assertions, cdk-nag, Config | Checkov, tflint, `terraform test` | ver `testes-infra-iac-aws` |
| em produção | produção | CodeDeploy canário/linear + alarmes + hooks, AppConfig (flags + bake time), CodePipeline stage conditions | — | deploy direto em produção; lançamento abrupto |
| dados | pipelines de dados | Glue DataBrew | Deequ (awslabs), Spark | ambiente de teste que não espelha os dados de produção |

## 3. Formato da suíte ("pirâmide" × serverless)

- Whitepaper de CI/CD (histórico): pirâmide de Cohn **(terceiro)**, ~70% unitários na base.
- Blog AWS Compute (2021): em serverless há **mais integração que unitário** (forma "hexagonal").
- Lambda Guide e PG: não prescrevem proporção — mandam **focar em integração** e **priorizar a nuvem**.
- "Honeycomb" é termo do Spotify **(terceiro)**; não aparece em fonte AWS. Se usar, atribua e ligue à
  recomendação da AWS de dar ênfase à integração na nuvem.
- Regra da Squad que concilia tudo: lógica pura em unitário (muitos, rápidos); cada integração com
  serviço gerenciado provada **na nuvem** pelo menos uma vez; E2E só para jornada crítica.

## 4. Métricas que a AWS sugere

- Funcional (QA.FT): densidade de defeitos, taxa de aprovação, **taxa de defeitos escapados**, tempo de
  execução, cobertura (funções, statements, branches) e razão feature/bug. Use mutação para medir a
  qualidade das asserções.
- Ambiente (QA.TEM): tempo de provisionamento do test bed e tempo de execução dos casos.
- Não funcional (QA.NT): disponibilidade, latência (percentis e trimmed mean), limiar de carga de pico,
  utilização, tempo de restauração × RTO, **Apdex** = (satisfeitos + tolerantes/2) / total
  (satisfeito ≤ T, tolerante ≤ 4T).
- Segurança (QA.ST): taxa de falso positivo, MTTD, MTTR, taxa de descoberta de vulnerabilidades.

## Fontes

- Lambda — testing guide: https://docs.aws.amazon.com/lambda/latest/dg/testing-guide.html
- Lambda — python testing: https://docs.aws.amazon.com/lambda/latest/dg/python-testing.html
- PG serverless testing: https://docs.aws.amazon.com/prescriptive-guidance/latest/serverless-application-testing/introduction.html · https://docs.aws.amazon.com/prescriptive-guidance/latest/serverless-application-testing/techniques.html · https://docs.aws.amazon.com/prescriptive-guidance/latest/serverless-application-testing/best-practices.html · https://docs.aws.amazon.com/prescriptive-guidance/latest/serverless-application-testing/faq.html
- DevOps Guidance QA: https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/quality-assurance.html
- Functional testing: https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/functional-testing.html
- Non-functional testing: https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/non-functional-testing.html
- Security testing: https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/security-testing.html
- Step Functions TestState: https://docs.aws.amazon.com/step-functions/latest/dg/test-state-isolation.html
- Step Functions Local (unsupported): https://docs.aws.amazon.com/step-functions/latest/dg/sfn-local.html
- Whitepaper CI/CD (histórico): https://docs.aws.amazon.com/whitepapers/latest/practicing-continuous-integration-continuous-delivery/testing-stages-in-continuous-integration-and-continuous-delivery.html
- Blog — Getting started with testing serverless applications: https://aws.amazon.com/blogs/compute/getting-started-with-testing-serverless-applications/
- Q Developer, fim do suporte dos plugins: https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/q-developer-ide-end-of-support.html
- Device Farm: https://docs.aws.amazon.com/devicefarm/latest/developerguide/welcome.html
- Cobrança do INIT: https://aws.amazon.com/blogs/compute/aws-lambda-standardizes-billing-for-init-phase/
- aws-samples/serverless-test-samples: https://github.com/aws-samples/serverless-test-samples
