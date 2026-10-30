# AWS CDK — assertions, snapshot e cdk-nag

> Reference de `testes-infra-iac-aws`. Base: blog AWS "Testing CDK applications in any language" e
> README do cdk-nag (cdklabs).

## 1. Fine-grained assertions (padrão recomendado)

- Módulo `assertions` (todas as linguagens do CDK): `Template.fromStack()`, `hasResourceProperties`,
  `resourceCountIs`, `hasOutput`.
- Matchers: `Match.objectLike` (padrão), `Match.objectEquals`, `Match.anyValue`, `Match.absent`,
  `Match.serializedJson`; `Capture` para valores gerados.
- Teste a **intenção**: a fila tem DLQ, a tabela tem PITR, o bucket bloqueia acesso público, a função
  tem o timeout e a memória decididos, a role não tem `*`.

```java
// Java + JUnit 5
Template t = Template.fromStack(new PedidosStack(app, "teste"));
t.resourceCountIs("AWS::SQS::Queue", 2);
t.hasResourceProperties("AWS::DynamoDB::Table", Map.of(
    "PointInTimeRecoverySpecification", Map.of("PointInTimeRecoveryEnabled", true)));
t.hasResourceProperties("AWS::Lambda::Function", Match.objectLike(Map.of(
    "Timeout", 10, "MemorySize", 1024)));
```

```typescript
// TypeScript + Jest
const t = Template.fromStack(new PedidosStack(app, 'teste'));
t.hasResourceProperties('AWS::S3::Bucket', {
  PublicAccessBlockConfiguration: { BlockPublicAcls: true, RestrictPublicBuckets: true },
});
```

## 2. Snapshot tests

- "not a mechanism to detect regressions" — servem para **alertar sobre qualquer mudança** do template
  (refatoração, upgrade do CDK). Complemento, nunca o único teste.
- Regravar snapshot exige ler o diff; regravação em massa sem leitura é antipadrão (asserção morta).

## 3. cdk-nag (política como código)

- Rule packs: **AWS Solutions**, HIPAA Security, NIST 800-53 rev4/rev5, PCI DSS 3.2.1, **Serverless**.
- `Aspects.of(app).add(new AwsSolutionsChecks())`; vários packs juntos; relatório CSV.
- **Suppression sempre com `reason`** e escopo restrito (`appliesTo`); sem justificativa = reprovação no review.

```typescript
Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));
NagSuppressions.addResourceSuppressions(bucketDeLogs, [
  { id: 'AwsSolutions-S1', reason: 'Bucket de logs de acesso não registra a si mesmo' },
]);
```

## 4. Camadas completas para CDK

| camada | ferramenta | estágio |
|---|---|---|
| synth + lint | `cdk synth` + cfn-lint no `cdk.out` | PR |
| política | cdk-nag; cfn-guard sobre o synth | PR |
| unitário | assertions (+ snapshot opcional) | PR |
| implantação | `cdk deploy` em conta de teste + teste de fumaça + `cdk destroy` | efêmero |
| mudança | `cdk diff` revisado | antes de produção |
| conformidade | drift, AWS Config | pós-deploy |

Ciclo rápido de teste na nuvem durante o desenvolvimento: `cdk watch` (conta de dev).

## Fontes

- https://aws.amazon.com/blogs/developer/testing-cdk-applications-in-any-language
- https://cdn.jsdelivr.net/npm/cdk-nag@2.37.55/README.md (README do cdklabs/cdk-nag)
