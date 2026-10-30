# Ciclo de Agentes de IA na AWS: Amazon Bedrock e Bedrock AgentCore (Agent Toolkit for AWS)

> **Procedência:** absorvido e reescrito em PT-BR a partir de `aws/agent-toolkit-for-aws` (`skills/core-skills/amazon-bedrock`, `aws-ai-ml`, `plugins/aws-startup-advisor/skills/llm-to-bedrock`, `agent-advisor` e as 8 skills de `plugins/aws-agents/skills/*`: `agents-get-started`, `agents-build`, `agents-connect`, `agents-debug`, `agents-deploy`, `agents-harden`, `agents-optimize`, `agents-pay`, commit `658b852f0612ca629d56d0a4de52738fb6a58714`, Apache-2.0).

---

## 1. Panorama de APIs do Amazon Bedrock (`amazon-bedrock`, `aws-ai-ml`, `llm-to-bedrock`)

1. **Use sempre a API `Converse` / `ConverseStream` (não `InvokeModel` legado) para texto e tool use:**
   - Unifica o formato de mensagens, `system` prompts, `toolConfig`, `guardrailConfig` e *prompt caching* entre famílias de modelos (Claude, Nova, Llama, Mistral).
   - Habilite **Cross-Region Inference Profiles** (`us.anthropic.claude-...`, `global.*`) para resiliência contra throttling regional e maior cota de throughput.
2. **Migração de OpenAI / Gemini / Anthropic Direto para Bedrock (`llm-to-bedrock`):**
   - Mapeie `messages` e `tools` para o contrato `converse` / `converse_stream` do `boto3` (`bedrock-runtime`).
   - Substitua chaves de API estáticas (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) por **IAM Roles** com permissão `bedrock:InvokeModel` e `bedrock:InvokeModelWithResponseStream` restrita aos ARNs dos Foundation Models e Inference Profiles autorizados.
3. **Knowledge Bases (RAG Gerenciado):**
   - Após criar ou atualizar uma Knowledge Base e disparar `start-ingestion-job`, **nunca declare a base pronta antes que o status da ingestão atinja `COMPLETE`** (verifique `statistics.numberOfDocumentsFailed == 0`).

---

## 2. Escolha de Runtime para Agentes de IA na AWS (`agent-advisor`)

| Requisito do Agente | Runtime Recomendado | Justificativa |
|---|---|---|
| Sessões longas com estado, memória gerenciada, gateway MCP, browser/code-interpreter isolado e observabilidade OTel nativa | **Amazon Bedrock AgentCore Runtime** | Isolamento por sessão, ciclo de vida completo de agentes, identidade outbound e ferramentas nativas |
| Agente stateless acionado por eventos curtos (< 15 min) ou webhooks simples | **AWS Lambda (ou Lambda MicroVMs)** | Escala a zero e simplicidade operacional (P1) |
| Orquestração determinística de passos com aprovação humana e retries auditáveis | **AWS Step Functions + Bedrock** | Combina grafo determinístico (ASL) com chamadas pontuais ao LLM |
| Containers customizados com GPU ou dependências pesadas residentes | **Amazon ECS Fargate / EKS** | Controle total sobre imagem e recursos |

---

## 3. Ciclo Completo de Engenharia de Agentes (`plugins/aws-agents/skills/*`)

### 3.1. Construção e Memória (`agents-get-started`, `agents-build`)
- Desenvolva localmente validando contratos de entrada/saída antes de empacotar para deploy.
- **Ferramentas de execução segura (`agents-build`):** quando o agente precisar executar código dinâmico ou navegar na web, utilize os ambientes isolados do **AgentCore Code Interpreter** e **AgentCore Browser** — nunca execute `eval`/`exec`/subprocessos arbitrários no processo principal do agente.
- **Memória em 2 camadas:** separe memória de curto prazo (contexto da sessão/turnos recentes) de memória de longo prazo (fatos extraídos e preferências por usuário/namespace).

### 3.2. Conexão a Ferramentas e APIs via Gateway (`agents-connect`)
- **Regra padrão:** prefira registrar APIs externas, funções Lambda e servidores MCP como **alvos do AgentCore Gateway** em vez de embutir chamadas HTTP e credenciais diretamente no código do agente.
- O Gateway centraliza autenticação inbound, injeção de credenciais outbound (OAuth2 / API Keys / SigV4 via AgentCore Identity) e descoberta semântica de ferramentas.

### 3.3. Deploy, Versionamento e Depuração (`agents-deploy`, `agents-debug`)
- **Pré-voo antes do deploy (`agents-deploy`):** valide permissões da execution role, região do Bedrock, disponibilidade do Inference Profile e variáveis de ambiente; versione endpoints para permitir rollback imediato.
- **Diagnóstico estruturado (`agents-debug`):**
  - *Model Access Denied / ResourceNotFound:* verifique se o Inference Profile regional/global corresponde à região configurada e se a role tem permissão tanto no `inference-profile/*` quanto no `foundation-model/*`.
  - *Falha de Tool Call:* inspecione traces OpenTelemetry no CloudWatch GenAI Observability verificando o payload enviado ao Gateway e o status da credencial outbound.

### 3.4. Hardening de Segurança e Otimização (`agents-harden`, `agents-optimize`, `agents-pay`)
- **Hardening (`agents-harden`):**
  1. Escopo mínimo de IAM na role do agente (separe permissões de invocação de modelo das permissões de negócios).
  2. Nunca passe credenciais de API no prompt ou contexto do LLM; use injeção de token no Gateway (o LLM nunca vê o segredo).
  3. Anexe **Bedrock Guardrails** (filtros de conteúdo, bloqueio de tópicos proibidos, redact de PII e *Contextual Grounding Check* contra alucinação em RAG).
- **Otimização de Custo, Latência e Qualidade (`agents-optimize`):**
  1. Ative **Prompt Caching** (`cachePoint`) nos prefixos estáticos (instruções de sistema, schemas de tools e documentos base).
  2. Roteie subtarefas simples de classificação/extração para modelos menores/rápidos (ex.: Haiku / Nova Micro/Lite) e escale apenas raciocínio complexo para modelos topo de linha (P3).
  3. Meça sistematicamente com suítes de avaliação (*evals*) antes e depois de qualquer alteração de prompt ou modelo.
- **Pagamentos Agênticos Controlados (`agents-pay`):**
  - Qualquer capacidade de pagamento ou transação financeira por agente exige limites estritos de valor por transação/período, carteira segregada e **confirmação humana explícita (N3)** acima do limiar autorizado.
