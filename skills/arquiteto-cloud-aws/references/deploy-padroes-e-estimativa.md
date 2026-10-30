# Referência — Deploy "leve" na AWS: serviço padrão por tipo de app e estimativa de custo antes do IaC

> Parte da skill `arquiteto-cloud-aws`. Carregue quando o pedido for **"coloque esta aplicação na AWS"**, "qual serviço usar para hospedar X", "quanto vai custar" ou "gere a infra" para um código que já existe — sem exigir que a pessoa conheça o catálogo da AWS. Compute detalhado em `compute.md`; IaC em `iac.md`; custo contínuo em `finops.md`; PaaS gerenciado (Elastic Beanstalk) em `../../engenheiro-devops/references/elastic-beanstalk.md`. Hub: `../SKILL.md`.

Procedência e licença: ver `docs/ATTRIBUTIONS.md` (colheita de 16/10/2026). Texto reescrito; nomes de serviço, limites e preços mudam — confirme na documentação oficial e na calculadora da AWS antes de fixar qualquer valor.

## 1. Filosofia: reduzir a carga de decisão

Quem chega com código pronto quer o caminho mais direto, não um seminário de serviços. Regras de conduta:

- Escolha o serviço óbvio e **diga em uma frase por quê**; só pergunte quando a ambiguidade for real (ex.: o pedido admite serverless *e* contêiner com razões opostas).
- Não pergunte "Lambda ou Fargate?" quando o tipo de aplicação já responde (tabela da seção 2).
- Fluxo fixo: **analisar o código → recomendar → estimar custo → só então gerar IaC → varrer segurança → implantar com confirmação**. O custo vem *antes* do código para a pessoa poder ajustar o desenho enquanto ainda é barato mudar.
- Dimensione para **dev** (instância pequena, sem redundância, uma AZ) a menos que o pedido diga "produção"/"production-ready". Dev sobredimensionado é o desperdício mais comum; produção subdimensionada por engano é o mais caro.

## 2. Matriz de escolha por tipo de aplicação

| Padrão da aplicação | Padrão recomendado | Quando trocar |
|---|---|---|
| Framework web com processo longo (Django, Rails, Express, FastAPI…) | Fargate atrás de ALB | Pedido explícito de serverless → Lambda + API Gateway; pedido de plataforma gerenciada → Elastic Beanstalk |
| API sem interface | Fargate + ALB | Serverless → API Gateway + Lambda; plataforma gerenciada → Elastic Beanstalk |
| Site estático / SPA | Amplify Hosting | Pede controle fino de cache/edge ou já tem CloudFront → S3 + CloudFront |
| Worker em segundo plano | Fargate | Tarefa curta (abaixo do teto da Lambda) → Lambda |
| Job agendado | EventBridge + Lambda | Execução longa → EventBridge + Fargate |
| Migração de Heroku/Render/Railway | Elastic Beanstalk | Quer orquestração de contêiner → Fargate; quer serverless → Lambda |

**Por que Fargate (e não Lambda) para framework web:** esses frameworks assumem processo de vida longa, pool de conexões e estado em memória do processo. Na Lambda exigem adaptador, sofrem cold start e forçam o modelo requisição/resposta sem sessão. Fargate acomoda o framework sem reescrita. Lambda continua sendo a resposta para carga orientada a evento e para tráfego muito esparso (ver o hub: Lambda vs Fargate por padrão de carga).

**Por que Amplify para estático/SPA:** CI/CD por Git, HTTPS, domínio próprio e CDN vêm prontos, com menos peças do que S3 + CloudFront montados à mão. Troque quando o controle de cache, de funções de borda ou uma infraestrutura CloudFront preexistente pesarem mais que a conveniência.

### 2.1 App Runner e ECS Express Mode

O App Runner foi colocado em **modo de manutenção** pela AWS (a doc oficial trata como mudança de disponibilidade e a imprensa técnica confirma o movimento). Consequência prática: **não recomende App Runner para carga nova**. Para o caso que ele atendia — "tenho uma imagem de contêiner e quero uma URL pública com o mínimo de configuração" — a rota nova é o **ECS Express Mode**, que provisiona sozinho serviço, balanceamento, escala e certificado sobre o ECS/Fargate. Quem já está no App Runner não precisa migrar às pressas, mas o planejamento de migração entra no roadmap. Se o time precisa de controle de rede, sidecars ou capacity providers, vá direto para ECS Fargate completo (`compute.md`).

## 3. Matriz de dados e armazenamento padrão

| Necessidade | Padrão (dev e prod) | Troca |
|---|---|---|
| PostgreSQL / MySQL | Aurora Serverless v2 | "RDS simples" quando o orçamento ou a conformidade pedem instância fixa |
| Documento / API do MongoDB | DocumentDB Serverless | Provisionado quando a carga é estável e previsível |
| Chave-valor / NoSQL | DynamoDB | — |
| Cache | ElastiCache Serverless | — |
| Busca textual | OpenSearch Serverless | — |
| Ativos e uploads | S3 | — |
| Segredos | Secrets Manager | — |
| Configuração não secreta | Parameter Store | — |

Por que serverless v2 como padrão relacional: escala para perto do mínimo no dev e cresce no prod, então **uma só escolha serve aos dois ambientes**. A conta fecha de forma diferente do "instância pequena de RDS" — o piso de capacidade do serverless v2 pode ficar acima do custo de uma instância mínima em carga ociosa; apresente essa troca em vez de escondê-la. Detalhes de modelagem em `dados.md`.

**IaC padrão:** CDK em TypeScript quando nada foi dito (expressivo, bom suporte de editor, gera CloudFormation); se o repositório já tem `terraform/`, `cdk.json` ou um `template.yaml` de SAM, **siga o que existe** — consistência vale mais que preferência. Pedidos explícitos ("terraform", "cloudformation", "sam") prevalecem.

## 4. Dev x produção — o que muda de verdade

| Componente | Dev | Produção |
|---|---|---|
| Tarefas Fargate | fração de vCPU e pouca memória | ao menos 1 vCPU e 2 GB, mais de uma tarefa |
| Aurora Serverless v2 | faixa baixa de ACU | faixa maior, com réplica/multi-AZ |
| ALB | uma AZ aceitável | multi-AZ |
| VPC | 1 pública + 1 privada | multi-AZ, subnets privadas por camada |
| Criptografia S3 | SSE-S3 | SSE-KMS com chave gerenciada pelo cliente (trilha de auditoria, rotação, acesso cross-account) |

O gatilho é linguístico e deve ser explícito: só "produção", "prod" ou "production-ready" promovem o dimensionamento. Registre na resposta qual perfil foi assumido, para a pessoa corrigir cedo.

## 5. Estimativa de custo antes do IaC

Fluxo:

1. Liste **todos** os serviços da arquitetura proposta (inclua ALB, NAT, logs e segredos — os esquecidos).
2. Consulte preço da **região real** (API de preços da AWS ou calculadora); nunca fixe valor de memória.
3. Converta em mensal com premissas de uso explícitas.
4. Apresente o total **antes** de gerar qualquer código.

Formato da apresentação — sempre quatro partes: (a) quebra por serviço, (b) total mensal, (c) premissas (24/7? quantas requisições? quanto de tráfego de saída?) e (d) dicas de otimização quando houver (ver `finops.md`).

Armadilhas de custo que a estimativa precisa nomear, porque costumam ficar fora da conta:

- **NAT Gateway**: cobra por hora *e* por GB processado; em dev com tarefas em subnet privada ele pode custar mais que o próprio compute. Considere VPC endpoints para S3/ECR quando o tráfego justificar.
- **Balanceador**: custo fixo por hora independe do tráfego; uma só ALB com regras por caminho/host atende vários serviços de dev.
- **Logs sem retenção**: ingestão e armazenamento do CloudWatch crescem sem teto até alguém definir retenção.
- **Serviço sem taxa própria** (caso do Elastic Beanstalk): o custo é o dos recursos criados por baixo — consulte EC2, ALB e EBS, não "o serviço".
- **Banco serverless em ambiente ocioso**: vale o piso de capacidade, não zero; se o dev fica parado à noite, ver agendamento de desligamento em `finops.md`.
- **Build de imagem na nuvem** (CodeBuild/ECR) entra na conta quando a plataforma constrói a imagem por você.

Ordem de grandeza (para calibrar, **não** para cotar): app web pequeno em Fargate + Aurora Serverless v2 + ALB fica na casa de dezenas a poucas centenas de dólares por mês em dev e sobe para algumas centenas em produção; site estático de baixo tráfego cabe em poucos dólares; API serverless de baixo tráfego, em dezenas. Qualquer número entregue à pessoa deve vir da consulta de preços do momento, com as premissas ao lado.

## 6. Checklist antes de gerar o IaC

- [ ] Tipo de aplicação identificado e serviço padrão escolhido com justificativa de uma frase.
- [ ] Perfil assumido (dev ou prod) dito em voz alta.
- [ ] App Runner fora das opções para carga nova; ECS Express Mode considerado quando a necessidade é "contêiner com URL e mínimo de configuração".
- [ ] IaC alinhado ao que o repositório já usa.
- [ ] Custo mensal com quebra e premissas apresentado e aceito.
- [ ] Padrões de segurança aplicados sem perguntar (criptografia em repouso, HTTPS, subnets privadas para compute, menor privilégio) e varredura estática do IaC antes do deploy — ver `auth-e-api.md`, `iac.md` e a skill `engenheiro-seguranca`.
- [ ] Confirmação humana antes do `deploy` efetivo (gated).
