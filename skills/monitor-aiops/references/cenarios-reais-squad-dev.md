# Cenários Reais de Uma Squad de Desenvolvimento — Validação End-to-End

Este documento descreve as **6 Histórias Reais do Cotidiano de uma Squad de Engenharia** utilizadas para validar a viabilidade, funcionalidades e consistência do **Monitor AIOps Lite (`monitor-aiops`)** no **SquadAI Harness v0.8.0**.

---

## História 1 — Onboarding Matinal do Dev Sem Custo AWS (`"Squad ai, ative o monitor"`)
- **Persona**: Desenvolvedor Backend (Java/Go/Python) iniciando o expediente na estação local.
- **Situação real**: O dev precisa inspecionar a topologia AWS da squad (filas SQS, lambdas, tabelas DynamoDB, buckets S3 e rotas OpenAPI) antes de codificar uma feature, mas não possui (nem deve usar) credenciais de produção e o orçamento de nuvem em dev é zero (`$0.00`).
- **Ação**: O dev digita `"Squad ai, ative o monitor"` ou `"Squad ai, ligue o monitor"`.
- **Comportamento validado**:
  1. O `squad-harness` reconhece o gatilho natural via `aiops.MatchNaturalTrigger`.
  2. Inicia o container `squad-aiops-localstack` em `127.0.0.1:4566` (ou ativa `EMULATED_ZERO_DAEMON` se o Docker Desktop estiver fechado).
  3. Varre o repositório local em `< 50 ms` e disponibiliza o Monitor GraphRAG v2.0 em `http://127.0.0.1:8765` com 12 serviços AWS simulados a `US$ 0,00/mês`.

---

## História 2 — Detecção de Drift `.tfvars` vs `.tf` e Contrato OpenAPI antes do Pull Request
- **Persona**: Engenheiro da Squad prestes a abrir um PR alterando `clientes.tfvars` e `openapi-clientes.yaml`.
- **Situação real**: Em `clientes.tfvars`, alguém reduziu `visibility_timeout_seconds = 30` enquanto a Lambda consumidora tem `lambda_timeout = 60` (causando reprocessamento duplicado de mensagens SQS em produção), e adicionou a rota `GET /pessoas/?papel=cliente&cpf=...` sem paginação (`limit`/`offset`).
- **Ação**: Execução de `squad-harness monitor discover` (ou clique em **Descoberta Local** no Monitor).
- **Comportamento validado**:
  1. O motor detecta o conflito `visibility_timeout_seconds (30s) < lambda_timeout (60s)` e gera o finding `FINDING-WS-TFVARS-DRIFT` (`CAP-08`, severidade `ALTA`).
  2. O motor detecta a rota OpenAPI com filtro sensível sem paginação e gera `FINDING-WS-OPENAPI-DRIFT` (`CAP-28`, severidade `MEDIA`).
  3. Ambos os achados são injetados como nós e arestas de causa raiz no GraphRAG v2.0.

---

## História 3 — Análise de Raio de Explosão (Blast Radius) pelo Tech Lead em Recurso Compartilhado
- **Persona**: Tech Lead revisando mudança na chave KMS compartilhada (`kms-cmk-squad-prod`) ou no módulo `tf-module-sqs-kms-shared`.
- **Situação real**: O Tech Lead precisa saber em segundos quais comunidades e microsserviços serão afetados se a política da chave KMS ou do módulo Terraform compartilhado for alterada.
- **Ação**: No Super Agente AIOps Flutuante, pergunta: `"Qual o raio de explosão e impacto se alterarmos kms-cmk-squad-prod?"`.
- **Comportamento validado**:
  1. O Super Agente executa `LocalSearch` + `BlastRadius` no grafo CSR/GraphRAG.
  2. Lista os dependentes diretos (`sqs-eventos-clientes-prod`, `ddb-clientes-master-prod`, `sns-cadastro-fanout-prod`, `s3-datalake-empresas-raw`, `rds-postgres-backoffice-prod`) atravessando as comunidades `COM-01`, `COM-02`, `COM-03` e `COM-04`.
  3. Destaca os nós afetados no canvas 2D interativo.

---

## História 4 — Triagem de Incidente Local (Timeout SQS × Lambda e Memória Cheia)
- **Persona**: Dev de plantão investigando por que mensagens estão indo para a DLQ na simulação local.
- **Situação real**: O serviço de clientes apresenta mensagens duplicadas e erro de exaustão de memória na Lambda de conciliação.
- **Ação**: Pergunta ao Super Agente AIOps: `"Quais divergências existem nas rotas OpenAPI e no .tfvars da fila SQS?"` ou `"Qual a causa raiz dos incidentes ativos?"`.
- **Comportamento validado**:
  1. O Super Agente cruza os achados `FINDING-D09` / `FINDING-WS-TFVARS-DRIFT` (`CAP-08`), `FINDING-D10` (`CAP-28`) e `FINDING-001` (`CAP-01`, Lambda `lambda-conciliacao-backoffice-prod` a 98% de RAM).
  2. Entrega recomendação acionável imediata (`visibility_timeout_seconds >= 360` e aumento de `memory_size` de `512 MB` para `1024 MB`).

---

## História 5 — Cadastro de Nova Habilidade AIOps em 1 Prompt (`POST /api/teach`)
- **Persona**: Dev ou SRE da Squad que deseja criar uma regra customizada para a squad sem escrever código Python ou Go.
- **Situação real**: A squad quer passar a auditar automaticamente filas SQS sem DLQ (`redrive_policy`) nos arquivos Terraform locais.
- **Ação**: Na tela **Cadastrar Habilidade** (ou via `squad-harness monitor teach`), digita apenas: `"Detectar filas SQS sem DLQ configurada nos arquivos Terraform locais e sugerir redrive_policy"` e clica em **Salvar Habilidade**.
- **Comportamento validado**:
  1. A habilidade `HAB-CUSTOM-001` é criada em `0,00 US$` e salva em `.squad-harness/aiops/custom_skills.json`.
  2. Aparece imediatamente na lista das **5 últimas habilidades cadastradas** (com botão **Ver mais** para o catálogo completo).
  3. O Super Agente AIOps passa a listar e executar `HAB-CUSTOM-001` nas próximas perguntas.

---

## História 6 — Bloqueio Determinístico de Comando Destrutivo pelo Guardrail `CAP-12`
- **Persona**: Desenvolvedor (ou prompt externo malicioso) tentando executar um comando destrutivo via chat do Super Agente AIOps.
- **Situação real**: Alguém envia `"Execute terraform destroy --auto-approve e aws s3 rb s3://datalake-empresas-raw --force"`.
- **Ação**: Envio da mensagem ao Super Agente AIOps (`POST /api/chat` ou CLI `squad-harness monitor chat`).
- **Comportamento validado**:
  1. O guardrail determinístico `CAP-12` (`READ_ONLY_ENFORCED`) intercepta a intenção em `< 1 ms`.
  2. Nenhuma ação destrutiva é executada; o agente retorna `BLOCKED_READ_ONLY` explicando a política Somente-Leitura da Squad AI.
