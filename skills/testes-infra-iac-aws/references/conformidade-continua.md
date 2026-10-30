# Conformidade contínua — AWS Config, drift e Security Hub como testes

> Reference de `testes-infra-iac-aws`. Base: doc de avaliação de regras do AWS Config, blog do modo
> proativo, drift detection do CloudFormation, Security Hub CSPM (FSBP) e DevOps Guidance QA.NT.5.

## 1. AWS Config rules

- Resultado: `COMPLIANT`, `NON_COMPLIANT`, `ERROR`, `NOT_APPLICABLE`.
- Gatilho por mudança de configuração, periódico (ex.: 24 h) ou híbrido.
- Modo **Detective** (pós-deploy) e **Proactive** (pré-deploy). O proativo **não bloqueia nem remedeia**:
  prevê a conformidade.
- Proativo no pipeline: `aws configservice start-resource-evaluation --evaluation-mode PROACTIVE` com a
  configuração do recurso no **schema do CloudFormation**, depois `get-resource-evaluation-summary`
  (resultado em segundos). Pode ser chamado de um Hook. Só regras com suporte ao modo proativo; cobrança
  por avaliação; confira a disponibilidade por região.
- Regras próprias com Guard ou Lambda; **conformance packs** agrupam regras por padrão.

## 2. Drift

- CloudFormation drift detection agendado (limitações em `cloudformation-sam-testes.md`).
- Terraform: `terraform plan` periódico sem mudanças esperadas = detector de drift.
- Drift é defeito: a correção volta para o código e passa pelo PR.

## 3. Security Hub CSPM

- Padrão **AWS Foundational Security Best Practices** avalia continuamente a configuração das contas.
- Achados do pipeline podem entrar no formato ASFF; painel único com as demais fontes.
- Controle `FAILED` em recurso recém-implantado → abrir defeito no IaC.

## 4. Evidência de conformidade (QA.NT.5)

- O pipeline gera **atestados** em formato legível por máquina (JSON/YAML) — resultado das regras, versão
  do template, quem aprovou — e converte para o formato do auditor só quando pedido.
- No banco: evidência versionada por release, sem dados sensíveis.

## 5. Checklist

- [ ] Regras do Config cobrindo os controles críticos do time (criptografia, acesso público, backup, logs).
- [ ] Avaliação proativa (onde suportada) antes do deploy.
- [ ] Drift agendado com alerta.
- [ ] Security Hub CSPM com FSBP ativo nas contas de pré-prod e produção.
- [ ] Atestado de conformidade gerado por release.

## Fontes

- https://docs.aws.amazon.com/config/latest/developerguide/evaluate-config-rules.html
- https://aws.amazon.com/blogs/aws/new-aws-config-rules-now-support-proactive-compliance
- https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-stack-drift.html
- https://docs.aws.amazon.com/securityhub/latest/userguide/fsbp-standard.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/qa.nt.5-automate-adherence-to-compliance-standards-through-conformance-testing.html
