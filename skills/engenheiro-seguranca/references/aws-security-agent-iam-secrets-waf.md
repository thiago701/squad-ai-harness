# Segurança AWS: IAM, Auth, Secrets Manager, WAF/Shield e AWS Security Agent (Agent Toolkit for AWS)

> **Procedência:** absorvido e reescrito em PT-BR a partir de `aws/agent-toolkit-for-aws` (`skills/core-skills/aws-auth`, `aws-iam`, `aws-security`, `plugins/aws-core/skills/aws-secrets-manager`, `creating-secrets-using-best-practices`, `securing-s3-buckets`, `waf`, `shieldadvanced` e as 6 skills de segurança em `plugins/aws-agents-for-devsecops/skills/*`, commit `658b852f0612ca629d56d0a4de52738fb6a58714`, Apache-2.0).

---

## 1. Autenticação com Amazon Cognito: User Pool vs Identity Pool (`aws-auth`)

1. **Decisão inicial obrigatória:**
   - **Cognito User Pool:** diretório de usuários e provedor OIDC/OAuth 2.0 (emite `id_token`, `access_token`, `refresh_token`) para autenticar usuários em APIs (API Gateway, ALB, AppSync) e SPAs/Mobile.
   - **Cognito Identity Pool (Federated Identities):** troca um token de identidade por **credenciais AWS temporárias (STS)** para o cliente acessar serviços AWS diretamente (ex.: upload direto no S3 ou IoT Core).
2. **Regras Críticas de Segurança em Auth:**
   - Em SPAs (Angular) e apps mobile, use **Authorization Code Grant com PKCE** (Managed Login) — nunca Implicit Flow e nunca armazene `client_secret` no frontend.
   - Autorize APIs validando o **`access_token`** (escopos e grupos), **não** o `id_token` (a menos que o autorizador exija claims de perfil e valide `aud` + `token_use`).
   - Habilite **Passkeys (WebAuthn)** e MFA adaptativo onde suportado.

---

## 2. Políticas e Roles IAM de Privilégio Mínimo (`aws-iam`)

- **Geração e revisão de políticas:**
  1. Toda permissão exige escopo de `Action` específico, `Resource` por ARN parametrizado e `Condition` quando aplicável (`aws:SourceArn`, `aws:SourceAccount`, `aws:PrincipalOrgID`, `aws:ViaAWSService`).
  2. **Prevenção de Confused Deputy em Trust Policies:** ao permitir que um serviço AWS (`events.amazonaws.com`, `states.amazonaws.com`, `scheduler.amazonaws.com`) assuma uma role, inclua sempre `Condition` com `aws:SourceAccount` e `aws:SourceArn`.
  3. **Restrição em `iam:PassRole`:** nunca conceda `iam:PassRole` com `Resource: "*"`; restrinja ao ARN exato da role de execução e adicione a condição `iam:PassedToService`.

---

## 3. Gestão de Segredos (`aws-secrets-manager`, `creating-secrets-using-best-practices`)

1. **Criação e Armazenamento (`creating-secrets-using-best-practices`):**
   - Criptografe segredos em produção com chave **KMS Customer Managed Key (CMK)** dedicada (permite auditoria independente no CloudTrail e controle fino via Key Policy).
   - Habilite **rotação automática** (rotação gerenciada para RDS/Aurora/Redshift/DocumentDB ou função Lambda rotacionadora seguindo os 4 passos: `createSecret` → `setSecret` → `testSecret` → `finishSecret`).
2. **Consumo sem Vazar em Código ou Variáveis de Ambiente (`aws-secrets-manager`):**
   - Em CloudFormation/SAM/ECS Task Definitions, use referências dinâmicas `{{resolve:secretsmanager:meu-segredo:SecretString:chave}}` (nunca grave o valor resolvido em disco).
   - Em execução local/CLI, utilize `asm-exec` ou busca em memória com cache TTL (AWS Parameters and Secrets Lambda Extension) para evitar chamadas repetitivas à API e nunca expor o segredo na linha de comando (`ps aux`).

---

## 4. Adequação de Serviços de Segurança AWS (`aws-security`)

- **GuardDuty, Security Hub, Inspector e Detective:**
  - **Amazon GuardDuty:** detecção contínua de ameaças em CloudTrail, VPC Flow Logs, DNS Logs, EKS, S3, RDS e Lambda.
  - **Amazon Inspector:** varredura contínua de vulnerabilidades (CVEs) em EC2, imagens ECR e código/dependências de funções Lambda.
  - **Amazon Detective:** investigação forense em grafo correlacionando achados do GuardDuty a fluxos de rede e chamadas de API.
- **Evitar sobreposição desnecessária de custo:** ao proteger CloudFront + ALB, associe o WAF no **CloudFront** e trave o ALB para aceitar tráfego exclusivamente do CloudFront (via Managed Prefix List `com.amazonaws.global.cloudfront.origin-facing` + header secreto rotacionado), evitando pagar duas Web ACLs idênticas quando uma camada de borda resolve.

---

## 5. Fluxos DevSecOps com AWS Security Agent (`plugins/aws-agents-for-devsecops`)

Padrões operacionais absorvidos das 6 skills do **AWS Security Agent** (sempre sob a política **gated** da Squad AI — nenhuma ação externa sem aprovação humana):

1. **Modelagem de Ameaças em Specs (`threat-modeling-with-aws-security-agent`):**
   - Antes de codificar, submeta documentos de especificação/arquitetura (`.prd.md`, `.plan.md`, diagramas) à análise de ameaças (STRIDE, fronteiras de confiança, fluxo de dados sensíveis e controles mitigadores).
2. **Diff Scan Rápido vs Full Scan (`diff-scanning-with-aws-security-agent`, `scanning-with-aws-security-agent`):**
   -Durante o ciclo de desenvolvimento, execute **diff scan** apenas sobre os arquivos alterados desde a referência Git base; reserve o **full scan** para marcos de release/homologação.
   - Armazene relatórios exportados em pasta local ignorada pelo Git (`.security-agent/`), nunca comitando artefatos brutos de vulnerabilidade.
3. **Remediação Guiada e Pentest Autorizado (`remediating-with-aws-security-agent`, `pentesting-with-aws-security-agent`):**
   - Triagem em 4 estágios: descobrir scans (somente leitura) → exportar achados → priorizar por severidade/explorabilidade → aplicar correção mínima com teste de regressão e revalidar.
   - Pentest automatizado **exige verificação prévia de propriedade do domínio-alvo** e autorização explícita do responsável pelo ambiente (nunca contra ambientes não-autorizados).
