# OWASP API Security Top 10 (2023) e cadeia de suprimentos

> Carregado sob demanda pelo `engenheiro-seguranca`. Fecha as duas lacunas conclusivas medidas
> em 2026-09-14 (`reports/mapa-capacidades.json`): **OWASP API Top 10** e **assinatura/proveniência**
> estavam ausentes de 100 % das skills varridas.
>
> O Top 10 *web* já estava coberto. Ele **não** cobre API: as falhas que dominam APIs são de
> **autorização por objeto** e de **exposição de recurso**, não de XSS ou CSRF.

## 1. OWASP API Security Top 10 (2023) — o que procurar no diff

| # | Risco | Como aparece no código | Teste que prova |
|---|---|---|---|
| **API1** | **BOLA** — Broken Object Level Authorization | `findById(id)` sem checar se o `id` pertence ao chamador | requisição autenticada como usuário A pedindo objeto de B → **403**, nunca 200 nem 404 genérico |
| **API2** | Broken Authentication | JWT sem validar `iss`/`aud`/`exp`; refresh sem rotação; `alg: none` aceito | token expirado, assinado por outro emissor e com `alg` trocado → 401 nos três |
| **API3** | Broken Object **Property** Level Authorization | mass assignment (`@RequestBody` direto na entidade); resposta devolvendo o objeto inteiro | POST com campo `role: ADMIN` → ignorado; resposta não contém campo sensível |
| **API4** | Unrestricted Resource Consumption | sem rate limit, sem paginação máxima, sem cap de payload, sem timeout em I/O | `?limit=1000000` → 400; payload acima do cap → 413 |
| **API5** | Broken **Function** Level Authorization | endpoint administrativo sem RBAC; verbo HTTP não coberto pela regra | usuário comum chamando `DELETE /admin/...` → 403 |
| **API6** | Unrestricted Access to Sensitive Business Flows | fluxo de valor (compra, transferência, cadastro) sem antiautomação | N requisições/minuto no fluxo → bloqueio ou desafio |
| **API7** | **SSRF** | URL vinda do usuário usada em cliente HTTP | URL apontando para `169.254.169.254` e para IP privado → recusada |
| **API8** | Security Misconfiguration | CORS `*` com credenciais; stack trace no corpo; TLS opcional; bucket público | resposta de erro não contém classe/stack; `Access-Control-Allow-Origin` explícito |
| **API9** | Improper Inventory Management | `/v1` esquecido no ar; ambiente de homologação exposto; endpoint sem documentação | inventário de rotas efetivas × rotas documentadas = 0 diferença |
| **API10** | Unsafe Consumption of APIs | confiar na resposta de terceiro sem validar/limitar | resposta gigante ou malformada do parceiro → erro tratado, não OOM |

### Padrão de revisão em Lambda + API Gateway

- **Authorizer não substitui autorização por objeto.** O authorizer diz *quem é*; o handler tem
  de dizer *se este quem pode este objeto*. API1 é a falha nº 1 em serverless justamente porque
  o time acha que o authorizer resolveu.
- **Toda `QueryCommand` no DynamoDB** deve ter a chave de tenant/dono **na PK ou na condição**,
  nunca só num filtro pós-leitura: `FilterExpression` lê o item antes de descartá-lo.
- **`Resource: "*"` na policy IAM da função** é achado **CRITICAL** por definição — Lambda tem
  escopo estreito por natureza, não há caso legítimo de curinga total em produção.
- **Mensagem de erro** devolvida ao cliente não repete o motivo interno. `ENTRADA_INVALIDA` +
  catálogo externo; nunca `"coluna cpf_titular viola constraint uk_cpf"`.

## 2. Cadeia de suprimentos — proveniência do que você entrega

### 2.1 Pin: tag é mutável, SHA não

```yaml
# ❌ a tag v4 pode apontar para outro commit amanhã
- uses: actions/checkout@v4
# ✅ imutável, e o Dependabot continua atualizando com o comentário
- uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8  # v4.2.2
```

Vale igual para `.pre-commit-config.yaml` (`rev:`), imagens Docker (`@sha256:…` em vez de `:latest`)
e dependências Maven/npm (lockfile versionado).

### 2.2 SBOM: o inventário do que foi realmente entregue

```bash
syft scan dir:. -o cyclonedx-json=reports/sbom.cyclonedx.json
```

Gere o SBOM **no mesmo build que produz o artefato** e versione-o junto. SBOM gerado depois, a
partir do repositório, descreve outra coisa — e a pergunta que ele precisa responder (*"esta
versão em produção contém a lib vulnerável?"*) só tem valor se a resposta for do artefato certo.

### 2.3 Assinatura e proveniência

```bash
# assina o binário sem gerenciar chave (OIDC keyless)
cosign sign-blob --yes target/cobaia-native --bundle target/cobaia-native.sigstore

# verifica na entrada do ambiente de destino
cosign verify-blob target/cobaia-native \
  --bundle target/cobaia-native.sigstore \
  --certificate-identity-regexp '^https://github\.com/<org>/<repo>/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

| Nível SLSA | O que garante | Custo |
|---|---|---|
| L1 | build com processo documentado e proveniência gerada | baixo |
| **L2** | proveniência **assinada** por serviço de build hospedado | baixo-médio — **alvo prático** |
| L3 | build isolado e não falsificável | alto |

> Assinar sem **verificar na entrada** não protege ninguém. A verificação vai no deploy, e
> falha de verificação é **BLOCKER**, nunca aviso.

### 2.4 Dependência: o que checar antes de adicionar

1. A dependência resolve um problema que o projeto **tem hoje**? (YAGNI é controle de segurança:
   cada dependência é superfície de ataque permanente.)
2. Manutenção viva — último release, issues de segurança respondidas.
3. Transitivas: `mvn dependency:tree` / `npm ls` — a superfície real é a árvore, não o `pom`.
4. Licença compatível.
5. `osv-scanner` limpo **antes** de entrar, não depois.

## 3. Severidade (alinhada ao `verificacao-loop` v2)

| Achado | Severidade |
|---|---|
| BOLA/BFLA explorável, RCE, segredo válido versionado, `Resource: "*"` em produção | **BLOCKER** |
| SSRF sem allow-list, JWT sem validar emissor, CVE Critical/High em dependência de runtime | **BLOCKER** |
| CORS `*` com credenciais, stack trace exposto, ausência de rate limit em fluxo de valor | **CRITICAL** |
| Action/imagem pinada por tag, SBOM ausente, CVE Medium acima do tolerado | **MAJOR** |
| Falta de assinatura em artefato interno, log sem correlação | **MINOR** |

> **Limiar de confiança 80 %** e **prova obrigatória** (arquivo, linha, cenário) valem aqui como
> em todo achado da Squad. Suspeita sem prova não entra no relatório — ela vira investigação.
