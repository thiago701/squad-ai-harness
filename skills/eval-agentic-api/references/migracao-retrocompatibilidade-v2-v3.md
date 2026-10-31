# Playbook de Migração de API com Engenharia Reversa e Retrocompatibilidade (`v1` → `v2`/`v3`)

> Guia operacional para quando o usuário responde **`3b) Migração de API existente`** e **`4b) Confirmar URLs/responses legados e gerar v2/v3`** na skill `eval-agentic-api`.

---

## 1. O Gate Obrigatório de Migração (Repositórios e Reuso de Infraestrutura)

Nenhuma linha de código de migração pode ser escrita antes de cruzar o **Gate de Descoberta de Origem e Infraestrutura**:

1. **Coleta Obrigatória dos Repositórios (Gate Bloqueante):**
   - Repositório ou diretório do **código-fonte legado** (ex.: Node.js/Express, Java 8/Spring 2, Python/Flask/Django, PHP, C#/.NET Framework, Ruby).
   - Repositório ou arquivos de **infraestrutura e contratos atuais** (OpenAPI/Swagger, Terraform `.tf`, AWS SAM `template.yaml`, Serverless `serverless.yml`, CloudFormation, configurações do API Gateway).
2. **Decisão Explícita sobre a Infraestrutura Atual:**
   - **Opção A — Reusar Infraestrutura Atual (*In-Place / Route Swap no mesmo API Gateway*):**
     - Mantém o mesmo domínio, Custom Domain Name, Authorizers (Cognito/Lambda Authorizer), Usage Plans, API Keys e WAF do API Gateway existente.
     - Aponta as rotas migradas (`v1`) para o novo compute (`Lambda` / `Step Functions` / `ECS`) via stage variables ou canary deployment (`10% -> 50% -> 100%`).
   - **Opção B — Infraestrutura Nova com Strangler Fig (*Side-by-Side*):**
     - Provisiona novo stack IaC modular mantendo o roteamento transparente na borda (CloudFront / API Gateway HTTP Proxy) até desativar o legado.

---

## 2. Protocolo de Engenharia Reversa Determinística do Contrato Legado

Para garantir **zero impacto nos clientes atuais**, o agente extrai do código legado a **Matriz de Invariantes do Contrato `v1`**:

| Dimensão do Contrato | O que deve ser preservado 100% na rota legada (`v1`) | Como o Code-Based Grader valida |
|---|---|---|
| **URLs, Paths e Verbos HTTP** | Caminhos exatos (incluindo trailing slashes, case-sensitivity de path params e query strings aceitas). | Comparação de tabela de rotas API Gateway legada vs. nova (`route_parity == 1.00`). |
| **Formato e Tipos do JSON de Saída** | Nomes exatos das chaves (`camelCase`, `snake_case` ou misto legado), tipos primitivos (não trocar `"123.45"` string por `123.45` float se o legado enviava string!), presença de `null` vs. omissão de chave (`omitempty`). | **AST/Schema JSON Diff Grader** + bench de mutações do `contrato-reverso`. |
| **Códigos de Status HTTP e Erros** | Status codes exatos para sucesso (`200`, `201`, `204`) e falha (`400`, `401`, `403`, `404`, `409`, `422`, `500`), além do formato exato do corpo de erro legado. | `Trials` de caminhos infelizes comparando status + payload de erro contra snapshots do legado. |
| **Headers e Autenticação** | Headers de resposta (`X-Request-Id`, paginação, CORS) e claims extraídos do JWT/Authorizer. | Inspeção direta do `Outcome` HTTP em cada `Trial`. |

---

## 3. Arquitetura Dual-Contract: Preservando `v1` Enquanto Evolui `v2` / `v3`

Durante a engenharia reversa de uma API legada, é comum encontrar dívidas técnicas no contrato antigo (ex.: campos com nomes confusos, falta de paginação, erros inconsistentes, acoplamento com tabelas antigas).

**Regra de Ouro:** **Nunca "conserte" o contrato quebrando a rota `v1` dos clientes em produção.** Use o padrão **Core Único + Adaptadores de Contrato Versionados (`v1` Legacy Adapter + `v2` Modern Contract)**:

```text
Clientes Atuais (Apps/Parceiros) ──► GET /v1/pedidos/{id} ──► [Adapter v1 (100% Retrocompatível)] ──┐
                                                                                                    ├──► [Domínio Limpo na Nova Stack (Go/Java/Rust/Python)]
Novos Clientes / Evolução        ──► GET /v2/orders/{id}  ──► [Adapter v2 (Contrato Refinado)]    ──┘
```

### O que entra no `v1` (Congelado para Retrocompatibilidade Máxima):
- Mesmas URLs e verbos HTTP do sistema legado;
- Mesmo JSON de resposta (traduzido a partir do novo domínio por um *Presenter/DTO v1* testado por *Golden Files*);
- Mesmo comportamento de códigos HTTP.

### O que entra no `v2` / `v3` (Evolução Refinada com o Humano):
- Nomenclatura padronizada e semântica;
- Envelope de erro moderno (**RFC 9457 Problem Details**);
- Paginação eficiente (*cursor-based pagination*);
- Novos campos de negócio, hiperlinks ou metadados de rastreabilidade (`trace_id`, `schema_version`);
- Documentação OpenAPI 3.1 gerada e validada automaticamente.

---

## 4. Critério de Aceite de Migração no Scorecard de Evals

Uma migração via `eval-agentic-api` só recebe veredito **`READY` para o GATE 2** quando simultaneamente:

1. **Paridade de Rota e Contrato `v1`:** `100%` dos casos do conjunto legado passam nos $k = 5$ `Trials` (**$\text{pass}\text{\textasciicircum}5 = 1.00$**).
2. **Bench de Mutações (`contrato-reverso`):** `100%` das mutações destrutivas simuladas (remover campo obrigatório do `v1`, alterar tipo de campo do `v1`, trocar status HTTP) são barradas pelos Code-Based Graders (**`mutation_kill_rate = 1.00`**).
3. **Validação da Rota `v2` (se solicitada):** `100%` dos novos contratos passam em $\text{pass}\text{\textasciicircum}5 = 1.00$ sem causar regressão nem interferência nas rotas `v1`.
4. **Infraestrutura e Segurança:** estratégia de reuso/migração do API Gateway validada pelo `engenheiro-iac` e zero achados 🔴 do `engenheiro-seguranca`.
