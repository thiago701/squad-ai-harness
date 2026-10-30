# Referência — Elastic Beanstalk: PaaS gerenciado na AWS (Standard x Cluster)

> Parte da skill `engenheiro-devops`. Carregue quando o pedido for **deploy em Elastic Beanstalk (EB)**, "alternativa ao Heroku", "não quero operar servidor nem orquestrador" ou migração de Heroku/Render/Railway. Pipeline genérico em `ci-cd.md`; contêiner em `containers.md`; Lambda em `lambda-deploy.md`. Hub: `../SKILL.md`.

Procedência e licença: ver `docs/ATTRIBUTIONS.md` (colheita de 15/10/2026). Texto reescrito; nomes de opções, plataformas, versões e preços mudam — confira na documentação oficial da AWS antes de fixar.

## 1. Quando EB é (e não é) a resposta

EB é serviço de **gestão de aplicação**: você entrega código ou imagem e a AWS opera o ciclo de vida (patch, escala, saúde, rollback, deploy). ECS/EKS são serviços de **gestão de infraestrutura**: você define e opera a plataforma. A diferença não é a ferramenta de IaC (todas aceitam CDK, CloudFormation e Terraform), e sim **quem responde pelo ciclo de vida depois do deploy**.

| Sinal do pedido | Rota |
|---|---|
| Pede EB explicitamente, ou "plataforma gerenciada", "estilo Heroku", patching automático | EB |
| App web/API/worker em runtime padrão e pouca vontade de mexer em infra | EB |
| Pede serverless ou carga nativamente orientada a evento (trigger de S3, request/response sem sessão) | Lambda — outro modelo de programação (stateless, cold start, teto de 15 min) |
| Quer controle fino de orquestração de contêiner | ECS |
| Time já domina Kubernetes e quer acesso direto | EKS |
| Site estático/SPA | Amplify Hosting no front; API separada |
| Já existe task definition/Fargate | Manter, não migrar |

Armadilha de interpretação: "não quero gerenciar servidor" **não** significa "quero serverless". EB também tira o servidor das costas e preserva o modelo normal (processo longo, conexão persistente, threads).

## 2. Escolha do modo — antes de gerar qualquer coisa

Os dois modos só compartilham a API: um namespace do modo Standard passado a um ambiente Cluster é **rejeitado**, não ignorado.

- **Standard**: a aplicação roda em EC2 (plataforma por linguagem, Docker ou Windows).
- **Cluster**: contêiner em EKS Auto Mode gerenciado, sem manifesto Kubernetes nem `kubectl`.

**Porta de entrada do Cluster (verificar primeiro):** todos os serviços precisam ser réplicas idênticas e intercambiáveis **e** todo estado durável (upload, sessão, cache, arquivo de trabalho) já precisa viver fora do contêiner. O disco da réplica é efêmero, perde-se a cada deploy, escala ou mudança que exige reinício, e **não existe volume persistente** nesse modo. Quem falha no teste vai para Standard ou muda a aplicação antes; "tem vários serviços" não anula a regra. Sessão em memória, trava de arquivo local e agendador singleton também não sobrevivem.

| Sinal | Modo |
|---|---|
| Código-fonte em runtime padrão; Windows/.NET Framework | Standard |
| Worker consumindo fila SQS | Standard |
| Grava upload, sessão ou arquivo de trabalho em disco local | Standard |
| Uma aplicação pequena, custo é a prioridade | Standard |
| Vários serviços com tráfego privado entre si | Cluster |
| Quer Kubernetes por baixo sem operá-lo; OpenTelemetry gerenciado; deploy/escala mais rápidos | Cluster |

Só uma imagem de contêiner não decide (o Standard tem plataforma Docker) — pergunte. Não proponha migrar ambiente Standard que funciona: **não há conversão in-place**, só ambiente novo e troca de CNAME.

## 3. Standard: padrões e plataforma

**Defaults (assuma dev, salvo se o usuário disser produção):**

| Item | Dev | Produção |
|---|---|---|
| Web | com balanceador, min=1/max=1 | com balanceador, multi-AZ |
| Worker | Auto Scaling min=1/max=1 | min=2/max=4 |
| Instância | pequena (família t3) | média ou maior |
| Deploy | all-at-once | rolling com lote adicional |
| Saúde | enhanced | enhanced |
| Atualização gerenciada | semanal | em janela de manutenção |
| HTTPS | certificado ACM no ALB | idem |

Use sempre ambiente balanceado para web: instâncias em subnet privada atrás do ALB, TLS via ACM e escalar depois vira mudança de configuração, não troca de tipo. Em dev com min=max=1 há breve indisponibilidade no deploy; para zero-downtime use min=1/max=2 com rolling. Worker não tem balanceador.

**Web x worker:** listener HTTP/rotas → web; consumidor de fila sem servir HTTP → worker; os dois → ambiente web e ambiente worker separados. O worker recebe cada mensagem do daemon SQS do EB por **POST HTTP** em caminho configurável (padrão `/`) — a aplicação expõe um endpoint, sem SDK de fila. Tarefas periódicas usam `cron.yaml`. Threads em segundo plano dentro do processo dispensam um worker à parte.

**Plataforma para Java:** `.jar` com servidor embutido (Spring Boot, Quarkus) → plataforma Corretto; `.war` → Tomcat. As duas exigem **artefato já construído** (`mvn package`/`gradle build` antes de zipar); linguagens interpretadas aceitam código-fonte e constroem na instância. Se há `Dockerfile` e também runtime de linguagem detectado, ou várias linguagens, pergunte. Use Amazon Linux 2023 (Windows só para .NET Framework/IIS) e a versão de runtime mais recente, salvo restrição declarada.

## 4. Configuração e customização (Standard)

- **Precedência (o último vence):** defaults da plataforma → configurações salvas → `.ebextensions/*.config` → propriedades de ambiente (console/CLI/API).
- Em AL2023, prefira **platform hooks** (`prebuild`, `predeploy`, `postdeploy`) para tarefas de shell; `.ebextensions` fica para option settings e recursos.
- `container_commands` com `leader_only: true` para o que roda em uma instância só (migração de banco, aquecimento de cache).
- `Procfile` define o processo. No worker ele sobe o servidor HTTP que recebe o POST do daemon, não um consumidor de broker.
- **Segredos:** a integração nativa com Secrets Manager injeta o valor como variável de ambiente, sem SDK na aplicação (exige plataforma de março/2025 em diante — verifique). Nunca segredo em `.ebextensions` ou no código; banco e segredos como recursos separados, fora do ciclo de vida do ambiente.
- **Proxy reverso:** o nginx encaminha para a porta 5000. Se a aplicação escuta em outra, defina `PORT`; porta divergente dá 502.
- **Health check:** endpoint dedicado (`/health`), nunca `/` se este consulta banco ou faz trabalho pesado. Se a aplicação não tem rota de saúde, crie uma mínima que devolve 200 — sem ela o deploy reverte.

| Política de deploy | Uso | Indisponibilidade |
|---|---|---|
| All at once | dev | sim |
| Rolling | produção, sensível a custo | não (capacidade parcial) |
| Rolling com lote adicional | produção, capacidade cheia | não |
| Immutable | produção, mais seguro | não |
| Traffic splitting | canário | não |

## 5. Cluster: o que evitar errar

- **Quatro defaults que surpreendem — defina de propósito:** limite máximo de réplicas (padrão 10 vira surpresa de custo); caminho do health check do ALB (padrão `/`); subnets (padrão é pública da VPC default e **não muda depois**); probes de readiness (desligadas até serem habilitadas).
- A porta do serviço é injetada como `PORT` e sobrepõe qualquer `PORT` que você passe. Aplicação com porta fixa no código falha **em silêncio** (pod saudável, health check falhando): a causa mais comum. Compare a porta em que a app logou com a configurada.
- `AWS_REGION` não é injetada; variáveis e segredos são **uma opção única** com objeto JSON, não uma opção por variável.
- **Imutável depois de criar** (`NoChange`): papéis de cluster/nó/observabilidade e subnets. Mudar exige ambiente novo e troca de CNAME — confirme a rede antes do primeiro create. A versão do Kubernetes também fica fixa durante a vida do cluster.
- HTTPS: com ALB criado pelo EB só existe listener 443 (porta 80 fechada) e o certificado do domínio do ambiente é gerado e renovado. Teste sempre por `https://`; `http://` fica pendurado até estourar e parece deploy quebrado. Com ALB **do usuário** (por ARN), listeners e TLS são dele — não presuma nada nem ajuste opções de certificado esperando efeito; o ARN precisa ser de ALB, não de NLB.
- Não mexa no cluster com `kubectl`/`eksctl` nem edite a stack CloudFormation: o EB deixa de reconhecê-lo, pausa a manutenção e falha atualizações. Ler é seguro. O EB mantém nós e add-ons, mas **não** atualiza o runtime nem a imagem da aplicação — isso continua com o time.
- Logs vão para quatro grupos CloudWatch de nome fixo, compartilhados por todos os ambientes da conta/região (separados por nome de stream) e **sem retenção**. Defina retenção depois do primeiro ambiente; o custo cresce sozinho.

## 6. Verificação de deploy e diagnóstico

"Ready/Green/Ok" significa que o ambiente roda, não que a aplicação funciona; um update que falhou pode reverter e continuar `Ready`. Verifique nesta ordem: (1) status do ambiente; (2) eventos de severidade ERROR vazios; (3) uma requisição real que exercite o comportamento pedido — em aplicação multisserviço, no serviço que depende dos demais.

Diagnóstico em ordem: eventos (lista de ERROR vazia é informação: a configuração não bate com a aplicação) → saúde com as causas → target group (timeout na porta é a pista mais forte) → contagem de réplicas (estável = app viva e inalcançável, não em crash loop) → logs da aplicação, único lugar onde ela fala.

## 7. Migração de Heroku, Render ou Railway

`DATABASE_URL` → banco provisionado à parte (RDS/Aurora) e entregue por segredo; `REDIS_URL` → ElastiCache com endpoint por propriedade; chaves de add-on → Secrets Manager; `PORT` → ver proxy reverso; `Procfile` funciona no mesmo formato; credencial AWS explícita no código → remover e usar o perfil IAM da instância.

## 8. IaC e segurança

- Padrão: AWS CLI (sem ferramenta extra): bucket de storage → aplicação → upload do bundle → versão da aplicação → ambiente com option settings → `wait environment-updated`; deploys seguintes criam versão nova e atualizam o ambiente. Resolva a plataforma listando as solution stacks disponíveis, não codifique o nome. CDK ou Terraform quando o repositório já os usa; ambos passam por scan estático (cfn-nag/checkov) antes do deploy.
- Aplique sem perguntar: instâncias em subnet privada (worker com NAT para saída), HTTPS no ALB, perfil IAM de menor privilégio derivado do uso real de SDK no código, security group do ALB em 443 e instâncias só aceitando tráfego do ALB, saúde enhanced e atualizações gerenciadas ligadas.
- **Custo:** o EB não cobra taxa; paga-se os recursos. Ordem de grandeza para dev (uma instância pequena + ALB) na casa de dezenas de dólares/mês; produção com várias instâncias sobe para centenas. Consulte preços da região no momento — números envelhecem.
