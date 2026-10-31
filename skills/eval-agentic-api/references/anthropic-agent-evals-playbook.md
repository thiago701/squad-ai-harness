# Playbook Científico — Demystifying Evals for AI Agents Aplicado a APIs

> Baseado nos princípios de engenharia de avaliação de agentes da Anthropic ([*Demystifying Evals for AI Agents*](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)) adaptados ao ciclo de construção e migração de APIs da Squad AI.

---

## 1. Anatomia Formal de um Agent Eval para APIs

Ao desenvolver ou migrar uma API com agentes autônomos, testes unitários tradicionais são necessários, porém insuficientes: agentes operam em múltiplos turnos, tomam decisões arquiteturais e podem produzir código que compila mas viola sutilmente contratos de consumidores ou invariantes de produção.

O framework `eval-agentic-api` estrutura toda entrega em **5 primitivos formais**:

### 1.1. `Task` (Tarefa / Caso de Avaliação)
Cada `Task` é uma especificação autocontida e verificável:
- **Contexto de Entrada (`input_spec`):** história de negócio, rota HTTP (`method`, `path`, `headers`, `query`, `body`), estado inicial do banco/mocks e restrições de SLA (ex.: `p95 <= 80 ms`).
- **Contrato Alvo (`expected_outcome_spec`):** status HTTP exato, JSON Schema / exemplo canônico de resposta, cabeçalhos obrigatórios (`Content-Type`, `X-Correlation-Id`), efeitos colaterais esperados no armazenamento (ou ausência deles em chamadas idempotentes/erros `4xx`).

### 1.2. `Trial` (Tentativa de Execução $i \in \{1..k\}$)
Como LLMs e sistemas distribuídos possuem estocasticidade, uma única execução bem-sucedida não prova confiabilidade. Cada `Task` é submetida a múltiplos `Trials` ($k \ge 5$) com:
- Variações realistas de payload (valores limítrofes, ordens distintas de chaves JSON, concorrência).
- Ambiente limpo e determinístico entre `Trials` (containers/LocalStack/bancos em memória reiniciados a cada tentativa).

### 1.3. `Transcript` (Trajetória / Rastro de Execução)
Tudo o que acontece durante o `Trial`:
- Quais arquivos o agente leu, criou ou editou;
- Quais comandos de compilação, lint e teste executou;
- Quantos turnos/retries precisou até convergir;
- Logs estruturados emitidos pela API durante a requisição.

### 1.4. `Outcome` (Estado Final no Ambiente — A Verdade Soberana)
O estado real produzido no mundo externo ao término do `Trial`:
- O payload JSON efetivamente retornado na porta HTTP / handler Lambda;
- O registro real gravado na tabela DynamoDB/PostgreSQL;
- A definição real do API Gateway / OpenAPI 3.1.

> **Regra de Ouro da Anthropic (*Grade the Outcome, Not the Path*):**
> Nunca reprove um agente porque ele escreveu um método auxiliar com nome diferente do esperado no `Transcript`, e nunca aprove um agente só porque ele afirmou no `Transcript` *"Todos os contratos foram preservados"*. O Grader inspeciona o **`Outcome` real** (resposta HTTP + estado persistido + diff do contrato).

---

## 2. As 3 Camadas de `Graders` (Avaliadores)

A combinação de três tipos de Graders equilibra **velocidade/determinismo (C0)**, **julgamento arquitetural (C2)** e **governança humana (Gates)**:

| Camada | Tipo de Grader | Custo / Latência | O que avalia na API | Peso no Scorecard |
|---|---|---|---|---|
| **G1** | **Code-Based Graders (Determinísticos)** | US$ 0 · `< 5 ms` | Compilação limpa, paridade estrutural e de tipos do JSON, códigos HTTP (`200/201/400/401/403/404/409/422/500`), bench de mutações de contrato (`contrato-reverso`), `lint_logs` (zero PII/secrets) e Tribunal JEV. | **60% (Bloqueante: exige 100% em contrato)** |
| **G2** | **Model-Based Graders (Rubrica Calibrada)** | Baixo (Haiku/Sonnet) | Aderência idiomática à stack (`Go`, `Java 25`, `Rust`, `Python`), Clean Architecture/DDD, simplicidade (`P1 > P2 > P3`), clareza de erros RFC 9457 e ausência de código hardcoded. | **25%** |
| **G3** | **Human Graders (Calibração & Gates)** | Humano no comando | **GATE 1:** valida as 4 perguntas-chave, arquitetura AWS e estratégia de reuso de infra. **GATE 2:** aprova o Scorecard final e o diff antes do commit/deploy. | **15% (Poder de Veto)** |

---

## 3. Métricas de Confiabilidade: `pass@k` vs. `pass^k`

O artigo *Demystifying Evals for AI Agents* destaca a distinção crítica entre duas métricas baseadas em $k$ `Trials` onde a probabilidade de sucesso por tentativa é $p$:

### 3.1. $\text{pass}@k = 1 - (1 - p)^k$ (Métrica de Capacidade / Descoberta)
Mede a probabilidade de **pelo menos 1 tentativa em $k$** ter sucesso.
- **Quando usar:** durante a exploração inicial ou geração de protótipo/scaffold quando queremos saber se a arquitetura proposta é capaz de resolver o problema.
- **Armadilha:** se $p = 0.70$, com $k = 5$ temos $\text{pass}@5 = 1 - 0.30^5 = 99.76\%$. Parece excelente, mas **30% das chamadas falham**!

### 3.2. $\text{pass}\text{\textasciicircum}k = p^k$ (Métrica de Consistência / Produção e Migração)
Mede a probabilidade de **todas as $k$ tentativas consecutivas** passarem sem nenhuma falha.
- **Quando usar:** **OBRIGATÓRIO** para aprovar APIs e migrações de contrato no `eval-agentic-api`. Clientes integrados ao API Gateway esperam determinismo e confiabilidade em cada chamada.
- **Impacto numérico ($k = 5$):**
  - Se $p = 0.70 \implies \text{pass}\text{\textasciicircum}5 = 0.70^5 = 16.8\%$ 🔴 **REPROVADO**
  - Se $p = 0.80 \implies \text{pass}\text{\textasciicircum}5 = 0.80^5 = 32.8\%$ 🔴 **REPROVADO**
  - Se $p = 0.90 \implies \text{pass}\text{\textasciicircum}5 = 0.90^5 = 59.0\%$ 🟡 **INSUFICIENTE**
  - Se $p = 0.99 \implies \text{pass}\text{\textasciicircum}5 = 0.99^5 = 95.1\%$ 🟢 **APROVADO (Geral)**
  - Se $p = 1.00 \implies \text{pass}\text{\textasciicircum}5 = 1.00^5 = 100.0\%$ 🟢 **OBRIGATÓRIO (Code Graders de Contrato)**

---

## 4. Matriz "Decida por Mim" — Escolha da Solução AWS (Pergunta 2d)

Quando o usuário escolhe **`2d) Decida por mim`**, aplique esta tabela de decisão sob a função de arbitragem **`P1-Simplicidade > P2-Performance > P3-CustoBaixo`**:

| Perfil da História da API | Solução AWS Recomendada | Justificativa Arquitetural |
|---|---|---|
| **API REST/HTTP síncrona, stateless, payload `< 6 MB`, execução `< 30 s`, tráfego variável ou com ociosidade** | **AWS Lambda** (+ API Gateway HTTP API) | **Vence em P1 (Simplicidade) e P3 (Custo Zero em idle)**. Com Go (`provided.al2023` arm64), Rust ou Java 25 AOT/SnapStart, entrega p99 `< 50 ms` sem gerenciar servidores. |
| **Workflow de negócio com múltiplas etapas, chamadas a parceiros externos, necessidade de Saga/compensação, retries declarativos ou espera de callback (`.sync` / task token)** | **AWS Step Functions** (Express para síncrono `< 5 min` alta vazão; Standard para auditoria longa / exatamente-uma-vez) | **Vence em P1 (Simplicidade)**: elimina código de estado/orquestração manual e filas intermediárias frágeis; integra direto com API Gateway e DynamoDB. |
| **API de alta vazão contínua 24x7, conexões long-lived (WebSockets pesados/gRPC/pools TCP densos), payloads `> 6 MB`, processamento `> 15 min` ou latência ultra-estável sem qualquer cold start** | **AWS ECS Fargate (Graviton arm64)** (+ ALB / API Gateway Private Integration) | **Vence em P2 (Performance previsível) e P3 em carga constante alta**, sem o custo operacional de administrar cluster EKS/Kubernetes. |
| **API híbrida: entrada HTTP rápida que dispara orquestração transacional entre microserviços** | **API Gateway + Step Functions Express + AWS Lambda** | Combina validação de contrato na borda, orquestração visual resiliente e funções puras de domínio por etapa. |

---

## 5. Prevenção da Lei de Goodhart e *Reward Hacking* em Agent Evals

Agentes otimizados para passar em evals podem tentar atalhos (*reward hacking*). Os Graders do `eval-agentic-api` aplicam 4 travas obrigatórias:

1. **Proibição de Resposta Hardcoded (Dynamic Input Mutation):** cada `Task` roda com pelo menos 2 conjuntos de entradas dinâmicas (nominal + held-out com valores gerados por seed). Se o handler retornar um JSON estático fixo, o segundo `Trial` reprova imediatamente.
2. **Proibição de Editar o Teste/Grader para Passar (Immutability Lock):** durante a Fase 4 (auto-correção), os arquivos de contrato e graders em `.evals/` são somente-leitura para o subagente implementador.
3. **Verificação de Efeito Colateral Real:** em operações `POST`/`PUT`/`DELETE`, o Grader consulta o estado posterior (`GET` ou banco/repositório) para provar que a mutação realmente ocorreu.
4. **Simetria de Erros:** uma API que retorna `200 OK` com `{"error": "falhou"}` no corpo para esconder erro de validação é **reprovada** pelo Code Grader de semântica HTTP (a menos que esse comportamento seja um requisito explícito de retrocompatibilidade legada `v1` documentado na Pergunta 4b).
