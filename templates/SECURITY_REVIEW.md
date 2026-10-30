# Revisão de Segurança — [Nome do Projeto]

<!--
  REVISÃO DE SEGURANÇA
  Quando usar: antes de TODO release em produção e ao alterar autenticação, autorização,
  dados sensíveis ou integrações com agentes IA.
  Quem preenche: engenheiro-seguranca; humano aprova o resultado final.
  Regra absoluta: SEGURANÇA NUNCA É NEGOCIÁVEL. Qualquer item 🔴 BLOQUEIA o release.
  Severidades: 🔴 Bloqueante (corrigir antes do release) · 🟡 Atenção (prazo definido) · 🟢 OK.
-->

| Campo | Valor |
|---|---|
| **Projeto** | [Nome do Projeto] |
| **Versão do documento** | [0.1.0] |
| **Data da revisão** | [AAAA-MM-DD] |
| **Autor(es)/Revisor(es)** | [Nome / Agente] |
| **Status** | [Em andamento \| 🔴 Reprovado \| 🟡 Aprovado com ressalvas \| 🟢 Aprovado] |
| **Escopo revisado** | [commit/tag/release — ex.: v1.2.0, commit abc123] |

---

## 1. Resumo Executivo

<!-- Preencha ao FINAL da revisão. Contagem por severidade e veredito. -->

| Severidade | Quantidade |
|---|---|
| 🔴 Bloqueante | [0] |
| 🟡 Atenção | [0] |
| 🟢 OK | [0] |

**Veredito:** [🟢 Aprovado para release / 🔴 Bloqueado — corrigir itens da seção 10]

## 2. Checklist OWASP Top 10 (2021)

<!-- Avalie cada item contra o código/infra do escopo. Justifique TODA marcação,
     inclusive os 🟢 (ex.: "🟢 — queries 100% parametrizadas via JPA/SQLAlchemy"). -->

| # | Categoria | Status | Evidência / Observação |
|---|---|---|---|
| A01 | Broken Access Control | [🔴/🟡/🟢] | [verificação de ownership em todos os endpoints?] |
| A02 | Cryptographic Failures | [🔴/🟡/🟢] | [TLS 1.2+, dados em repouso com KMS, sem algoritmos fracos] |
| A03 | Injection (SQL/NoSQL/OS/LDAP) | [🔴/🟡/🟢] | [queries parametrizadas, sem concatenação] |
| A04 | Insecure Design | [🔴/🟡/🟢] | [threat model feito? limites de negócio aplicados?] |
| A05 | Security Misconfiguration | [🔴/🟡/🟢] | [headers, CORS restrito, stack trace oculto, portas] |
| A06 | Vulnerable & Outdated Components | [🔴/🟡/🟢] | [ver seção 6] |
| A07 | Identification & Auth Failures | [🔴/🟡/🟢] | [ver seção 3] |
| A08 | Software & Data Integrity Failures | [🔴/🟡/🟢] | [pipeline assinado, dependências com lockfile] |
| A09 | Security Logging & Monitoring Failures | [🔴/🟡/🟢] | [eventos de auth logados, alertas configurados] |
| A10 | SSRF | [🔴/🟡/🟢] | [URLs externas validadas com allowlist] |

## 3. Autenticação e Autorização

| Item | Status | Observação |
|---|---|---|
| Mecanismo de autenticação | [🟢] | [Cognito / OAuth2 / JWT — descreva] |
| Expiração e rotação de tokens | [🟢] | [access ≤ 1h, refresh com rotação] |
| Senhas (se aplicável) | [🟢] | [bcrypt/argon2, política de complexidade] |
| Autorização por recurso (RBAC/ABAC) | [🟢] | [papel verificado no backend, nunca só no frontend] |
| IDOR — controle de ownership | [🟢] | [usuário só acessa o que é dele] |
| Endpoints administrativos | [🟢] | [segregados, MFA exigido] |

## 4. Gestão de Secrets

| Item | Status | Observação |
|---|---|---|
| Nenhum secret no código/repo (scan executado) | [🟢] | [ferramenta: gitleaks/trufflehog em AAAA-MM-DD] |
| Secrets em cofre gerenciado | [🟢] | [AWS Secrets Manager / Parameter Store] |
| Rotação definida | [🟡] | [prazo/periodicidade] |
| Princípio do menor privilégio (IAM) | [🟢] | [roles por serviço, sem `*` em policies] |

## 5. Validação de Entrada e Saída

| Item | Status | Observação |
|---|---|---|
| Validação de schema em todas as entradas | [🟢] | [Bean Validation / Pydantic] |
| Sanitização contra XSS | [🟢] | [encoding na saída, CSP configurada] |
| Upload de arquivos | [🟢/N.A.] | [tipo, tamanho, antivírus, fora do webroot] |
| Limites de tamanho de payload | [🟢] | [max body size configurado] |
| Mensagens de erro sem vazamento interno | [🟢] | [RFC 7807, sem stack trace em prod] |

## 6. Dependências Vulneráveis

<!-- Rode os scanners e cole o resumo. CVE crítico/alto sem correção = 🔴. -->

- **Ferramentas:** [OWASP dependency-check / `pip-audit` + `safety` / `npm audit` / Dependabot]
- **Data do scan:** [AAAA-MM-DD]

| Dependência | CVE | Severidade | Ação |
|---|---|---|---|
| [lib X 1.2.3] | [CVE-2026-XXXX] | [Alta] | [atualizar para 1.2.4 até DD/MM] |

## 7. Dados Sensíveis e LGPD

| Item | Status | Observação |
|---|---|---|
| Inventário de dados pessoais mapeado | [🟢] | [quais campos: CPF, e-mail... ver DATA_MODEL.md] |
| Base legal definida por finalidade | [🟢] | [consentimento/contrato/legítimo interesse] |
| Minimização (coleta só do necessário) | [🟢] | [...] |
| Criptografia em trânsito e repouso | [🟢] | [TLS 1.3 / KMS] |
| Dados pessoais fora de logs | [🟢] | [masking configurado] |
| Retenção e descarte definidos | [🟡] | [ver DATA_MODEL.md §retenção] |
| Atendimento a direitos do titular (acesso/exclusão) | [🟡] | [processo definido?] |

## 8. Segurança de Agentes IA

<!-- Preencher se o sistema usa LLMs/agentes. Caso contrário, marcar N.A. e justificar. -->

| Item | Status | Observação |
|---|---|---|
| Prompt injection (direto e indireto via dados) | [🔴/🟡/🟢] | [entradas de usuário isoladas do system prompt?] |
| Guardrails de saída | [🟢] | [validação de schema, filtros de conteúdo] |
| Tool use com menor privilégio | [🟢] | [agente só acessa ferramentas necessárias] |
| Ações destrutivas exigem aprovação humana | [🟢] | [human-in-the-loop para writes críticos] |
| Vazamento de dados via prompt/contexto | [🟢] | [PII não enviada ao modelo sem necessidade] |
| Rate limit e teto de custo por agente | [🟡] | [budget e quota configurados] |
| Logs de decisões do agente (auditoria) | [🟢] | [prompts e respostas auditáveis] |

## 9. Infraestrutura e Rede

| Item | Status | Observação |
|---|---|---|
| Security groups restritivos | [🟢] | [sem 0.0.0.0/0 em portas internas] |
| WAF em endpoints públicos | [🟡] | [AWS WAF — regras gerenciadas] |
| Rate limiting / anti-brute-force | [🟢] | [por IP e por usuário] |
| Imagens de container escaneadas | [🟢] | [ECR scan / Trivy] |

## 10. Plano de Mitigação

<!-- TODO item 🔴 e 🟡 entra aqui com responsável e prazo. 🔴 bloqueia release até resolver. -->

| # | Achado | Severidade | Ação corretiva | Responsável | Prazo | Status |
|---|---|---|---|---|---|---|
| 1 | [descrição do achado] | [🔴] | [correção] | [nome] | [AAAA-MM-DD] | [Aberto] |
| 2 | [descrição do achado] | [🟡] | [correção] | [nome] | [AAAA-MM-DD] | [Aberto] |

## 11. Aprovação

| Papel | Nome | Decisão | Data |
|---|---|---|---|
| Engenheiro de Segurança | [nome/agente] | [Pendente] | [AAAA-MM-DD] |
| Tech Lead (humano) | [nome] | [Pendente] | [AAAA-MM-DD] |

---

## Histórico de Revisões

| Versão | Data | Autor | Mudança |
|---|---|---|---|
| 0.1.0 | [AAAA-MM-DD] | [autor] | Revisão inicial |
