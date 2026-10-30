# Inspector, Security Hub, GuardDuty, WAF e segredos — varredura contínua

> Reference de `testes-seguranca-aws`. Base: docs e blogs do Amazon Inspector (Lambda, ECR, CI/CD, code
> security), Amazon Q Developer code reviews, Security Hub CSPM (FSBP), GuardDuty, guia de boas práticas de
> WAF da AWS, git-secrets (awslabs), SEC11-BP02 e DevOps Guidance QA.ST. No banco, a política de SAST é a do
> **Veracode** (`validacao-veracode`); os serviços abaixo complementam.

## 1. Amazon Inspector

| capacidade | o que faz | detalhes |
|---|---|---|
| **code security** (jun/2025) | SAST, SCA e IaC no repositório | integra com GitHub e GitLab self-managed; gatilhos on-demand, push/PR, agendado; SAST detecta hardcoded secrets, XSS, injection; IaC: CloudFormation, Terraform, CDK; comentários de correção no PR para Critical/High |
| **Lambda standard scanning** | dependências das funções | varre no deploy/update e quando surge CVE novo; exclui funções sem invocação/update há 90 dias; só `$LATEST`; não suporta função cifrada com CMK |
| **Lambda code scanning** | código da função | exige o standard ativo |
| **ECR enhanced scanning** | imagens no registry | contínuo |
| **CI/CD container scanning** | imagem no build | `inspector-sbomgen` gera SBOM CycloneDX e `inspector-scan` avalia → aprova/reprova o build; cobrado por scan |

O **CodeGuru Security foi descontinuado em 20/11/2025**: SEC11-BP02 e QA.ST.4 ainda o citam; use Inspector
code security (CI/repositório) e Q Developer (IDE).

## 2. Amazon Q Developer — code reviews (IDE)

SAST, segredos, IaC, qualidade e SCA por diff, arquivo ou projeto. Os **plugins de IDE perdem suporte em
30/04/2027** (sucessor indicado: Kiro). Não é gate: é feedback local.

## 3. Segredos

- **git-secrets** (awslabs): `git secrets --install` (hooks), `--register-aws` (padrões de credencial AWS),
  `--scan-history`. gitleaks **(terceiro)** cumpre o mesmo papel (o repo da Squad já usa).
- Falha de segredo no build é **imediata** (DPRA). Segredo vazado: revogar primeiro, limpar depois.

## 4. Postura e ameaça em execução

- **Security Hub CSPM** — padrão **AWS Foundational Security Best Practices (FSBP)** avalia continuamente
  a configuração; recebe achados do pipeline no formato ASFF. É o "teste contínuo" da postura.
- **GuardDuty** — Runtime Monitoring (EKS, ECS on Fargate com agente gerenciado, EC2) e **Lambda
  Protection** (atividade de rede das funções, sem agente). Achado de GuardDuty em pré-prod durante teste é
  evidência a investigar, não ruído.
- **AWS Config** — regras como testes de conformidade (ver `testes-infra-iac-aws`).

## 5. AWS WAF — testar regra sem derrubar o legítimo

Fluxo recomendado pela AWS: todas as regras em **Count** com ação padrão Allow, **com logs**, coletando 1 a
2 semanas; promover a **Block** nesta ordem — reputação de IP e IP anônimo, regras rate-based (limiar
tirado dos logs), regras com exceções (via labels), e manter em Count as que conflitam. Versão nova de
managed rule entra em Count, é comparada e depois promovida. Em pré-prod, teste automatizado: requisição
maliciosa conhecida → bloqueada; jornada legítima → passa.

## 6. Normalização e gate (QA.ST.1/ST.2, SEC11-BP02)

- Achados em escala comum (**CVSS**), formatos **SARIF/OCSF**, painel único, ticket automático com severidade.
- Decida explicitamente **onde bloquear e onde só notificar**; mesmas ferramentas no IDE, review e CI.
- Métricas: falso positivo, MTTD, MTTR, defeitos escapados.

## Fontes

- https://aws.amazon.com/blogs/security/shifting-vulnerability-detection-left-with-amazon-inspector-code-security-capabilities
- https://docs.aws.amazon.com/inspector/latest/user/scanning-lambda.html
- https://aws.amazon.com/id/blogs/aws/three-new-capabilities-for-amazon-inspector-broaden-the-realm-of-vulnerability-scanning-for-workloads/
- https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/code-reviews.html
- https://docs.aws.amazon.com/securityhub/latest/userguide/fsbp-standard.html
- https://docs.aws.amazon.com/guardduty/latest/ug/runtime-monitoring.html
- https://docs.aws.amazon.com/guardduty/latest/ug/lambda-protection.html
- https://aws.github.io/aws-security-services-best-practices/ja/guides/waf/operationalizing/docs/
- https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/sec_appsec_automate_testing_throughout_lifecycle.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/security-testing.html
- https://aws.amazon.com/blogs/devops/building-end-to-end-aws-devsecops-ci-cd-pipeline-with-open-source-sca-sast-and-dast-tools
- awslabs/git-secrets (README; espelho consultado na pesquisa — confira o original no GitHub)
