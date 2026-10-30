# Environment Configuration & Compatibility Review (etapa obrigatória do Code Review)

> **Pergunta que esta etapa responde:** o código que estou aprovando é compatível com a **estrutura, versão,
> ambiente, infraestrutura e dependências externas** que vão fornecer cada configuração? Não basta "a
> configuração existe": *código correto + configuração existente + contrato incompatível = falha em produção.*
> Executor: `configuration-compatibility-review` (`scripts/gates/compat_config/`, núcleo `scripts/compat/`).

## 1. Cadeia avaliada — Configuration as Contract

`Código → Configuração → Infraestrutura → Secrets/Vault → Ambiente → Versão → Dependências externas`

Atributos de contrato de cada configuração: nome · existência · tipo · estrutura · schema · obrigatoriedade ·
nullable · formato · versão · consumidor · ambiente · origem · dependência · fallback.

## 2. Como rodar

```bash
python -m scripts.gates verificar --checkpoint review --destino <branch> --monitor 300   # todas as etapas
python -m scripts.gates verificar --checkpoint review --somente configuration-compatibility-review   # PARCIAL
python -m scripts.gates compat-relatorio --checkpoint review                              # relatório + perguntas
```

## 3. De onde vem a estrutura (nunca do valor do segredo)

| Nível | Fonte | Confiança | Pode bloquear sozinho? |
|---|---|---|---|
| `demonstrado` | evidência de metadados `squad/config-schema-evidencia/v1` (tipo, nomes de campos, versão — sem valores), em caminho **declarado** em `configurationCompatibilityReview.evidencias` da política revisada, com o ambiente no nome do arquivo e dentro da validade (no deploy, a do deploy) | 95 | sim (`BLOCKER`) |
| `iac` | Terraform/CloudFormation do repositório (`jsonencode({...})`, `GenerateSecretString`, `aws_ssm_parameter`, variáveis de Lambda/ECS e o elo variável → segredo) | 88 | não — vai a `HIGH` |
| `declarado` | contrato de configuração versionado (formato abaixo) | 85 | não — vai a `HIGH` |
| `config` | `application[-amb].yml/.properties`, `.env` (forma do literal); `.env.example/.sample/.template/.dist` não são provedores | 75 | não |

Contrato de configuração (`**/config-contract*.yaml`, `**/config-contracts/*.yaml` ou o glob da política):

```yaml
configuration:
  name: DATABASE_SECRET
  provider: AWS Secrets Manager
  environments:
    dev:  {structure: {type: STRING}, version: v1}
    hml:  {structure: {type: JSON}, fields: {username: STRING, password: STRING, host: STRING}, version: v2}
    prod: {structure: {type: JSON}, fields: {username: STRING, password: STRING, host: STRING}, version: v2}
```

## 4. Lado consumidor (código)

Secrets Manager (SDK Java v2, wrappers `getSecret*`, Powertools, boto3, SDK JS), Parameter Store, variáveis de
ambiente e propriedades Spring (`@Value` com o tipo do campo). Estrutura esperada pela janela após a leitura:
parse JSON + campos lidos → `JSON {campos}`; conversão → `INTEGER/BOOLEAN/URL/DURATION`; uso direto → `STRING`.
**Compatibilidade retroativa valorizada:** `try/catch` do parse com caminho legado, teste de formato,
leitura dual — o consumidor que aceita os dois formatos é compatível com os dois ambientes.

## 5. Detectores (`scripts/compat/detectores.py`)

| Detector | Tipos | O que detecta |
|---|---|---|
| `config-estrutura-ambiente` | TYPE_MISMATCH · STRUCTURE_MISMATCH · SECRET_FORMAT_CHANGE · UNVERIFIED_ENVIRONMENT_COMPATIBILITY | estrutura esperada × fornecida por ambiente; mudança do consumidor sem como verificar o ambiente |
| `config-drift-ambientes` | ENVIRONMENT_DRIFT | DEV ≠ HML ≠ PROD |
| `config-versao` | VERSION_MISMATCH | app exige schema vN, ambiente tem vM (`BLOCKER — CONFIGURATION VERSION MISMATCH` com evidência) |
| `config-nome` | MISSING · RENAMED · REMOVED_CONFIGURATION | consumida sem fornecimento; renomeada (`PAYMENT_URL → PAYMENT_BASE_URL`); removida de todo o deploy |
| `config-ordem-deploy` | INFRASTRUCTURE_DEPENDENCY_CHANGE | **DEPLOYMENT ORDER RISK** (app nova exige infra nova e infra nova quebra app antiga) |
| `config-migracao` | SCHEMA_EVOLUTION | breaking change sem leitura dual nem plano de migração |
| `config-contrato-externo` | EXTERNAL_CONTRACT_CHANGE · AUTHORIZATION_SCOPE_CHANGE · AUTHENTICATION_CHANGE | `/v1 → /v2`, scopes OAuth, mecanismo de autenticação × configuração |

Também emitidos: histórico (commits que tocaram a configuração e qual parte da cadeia mudou — "cadeia
parcialmente atualizada") e blast radius local (classe consumidora → clientes → serviços → APIs → testes).

## 6. Severidade, confiança e natureza

- Severidade `INFO < WARNING < NEEDS_CONFIRMATION < HIGH < BLOCKER`; confiança `≥95 comprovada · ≥80 forte
  evidência indireta · ≥60 provável · ≥40 requer confirmação · <30 não bloqueia`.
- Cada afirmação sai rotulada **FACT · EVIDENCE · INFERENCE · QUESTION · RECOMMENDATION** (correspondem às
  marcas `[OK]/[AN]/[GAP]` da política de evidências).

## 7. Política de bloqueio (proporcional)

| Situação | Resultado |
|---|---|
| consumidor espera JSON **e** ambiente demonstradamente STRING, sem fallback | `BLOCKER` (bloqueia push/merge) |
| propriedade exigida removida de **toda** a configuração de deploy conhecida, saindo de IaC ou de ambiente demonstrado | `BLOCKER` |
| idem, saindo só de contrato ou arquivo de configuração | `HIGH` (confirmável) |
| incompatibilidade só por IaC/contrato (não observada no ambiente) | `HIGH` |
| não verificável (ambiente sem evidência) | `NEEDS_CONFIRMATION` + perguntas |
| `NEEDS_CONFIRMATION`/`HIGH` em review, push e merge | **não bloqueia** ("LIBERADO COM CONFIRMAÇÃO PENDENTE") |
| `NEEDS_CONFIRMATION`/`HIGH` no **deploy** ou em checkpoint fora da lista branca | bloqueia até confirmação humana na política revisada |
| deploy sem `--implantado <revisão em execução no ambiente>` | `INCONCLUSIVE` (a base seria o próprio destino e o diff, vazio) |

Confirmação (`configurationCompatibilityReview.confirmacoes`): objeto, ambiente, `resposta: compativel |
incompativel`, justificativa, `aprovacao{por,em,referencia}` de humano em `aprovadoresExcecoes`, `validaAte`.
O agente não confirma nada; `BLOCKER` não se confirma — corrige-se a causa ou a evidência.

## 8. Perguntas: só quando necessárias, sempre específicas

Ruim: "Está tudo correto no ambiente?". Bom: "O código passou a desserializar `PAYMENT_SECRET` como JSON com
`clientId`, `clientSecret` e `scope`. O IaC disponível só referencia o recurso e não permite validar o schema.
PROD já fornece essa estrutura?". Não pergunte o que a automação descobre (estrutura em IaC, evidência,
contrato). Leitura nova de escalar não vira pergunta.

## 9. Migração segura e ordem de deploy

1. aplicação suporta V1 + V2 → 2. deploy da aplicação → 3. migrar a configuração → 4. validar o ambiente →
5. remover suporte a V1. Nunca "alterar segredo → alterar aplicação" sem garantia de ordem.

## 10. Saída

Bloco **CONFIGURATION COMPATIBILITY REVIEW** (status, componente, configuração, consumidor anterior/novo,
esquema esperado, evidência por ambiente, confiança, risco, blast radius, verificações, recomendação), a
**Environment Compatibility Matrix** e o export para as Regras Preditivas do Trace2Local
(`.cache/gates/compat/insights-configuracao.json`, campos do record `Insight`).

## 11. Limites declarados

`@ConfigurationProperties`, nomes dinâmicos e Kotlin DSL não são resolvidos (aparecem como lacuna); Vault e
Kubernetes Secrets só entram via contrato/evidência; o consumidor de runtime do Trace2Local é `[GAP]`.
