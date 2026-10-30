# Testes de autorização em APIs na AWS (BOLA/IDOR, autorizador, multi-tenant)

> Reference de `testes-seguranca-aws`. A AWS não tem página dedicada a BOLA/IDOR pelo nome; o que ela
> oferece de mais próximo é o **teste de isolamento entre tenants** (blog APN "Testing SaaS solutions on
> AWS"), a autorização por objeto do **Amazon Verified Permissions/Cedar** e o posicionamento de DAST
> (QA.ST.5) e pentest com foco em lógica de negócio (SEC11-BP03). O protocolo abaixo é a prática da Squad
> derivada disso. Respostas do próprio Gateway (401/403/404/429) entram no contrato via `contrato-reverso`.

## 1. O que testar

| ameaça | teste | resultado esperado |
|---|---|---|
| BOLA/IDOR horizontal | usuário A lê/altera/apaga objeto de B pelo ID | 403 ou 404, sem vazar existência; nada muda no banco |
| escalonamento vertical | usuário comum chama rota administrativa | 403 |
| sem credencial | token ausente, expirado, assinatura inválida, outro issuer/audience | 401 do autorizador (corpo do Gateway) |
| identidade forjada | header de identidade enviado pelo cliente (`X-User-Id` etc.) | ignorado; identidade só do token/claims |
| tenant cruzado | tenant A acessa recurso do tenant B, inclusive recursos **recém-criados** | negado; política de isolamento aplicada ao recurso novo |
| enumeração | IDs sequenciais | IDs imutáveis não adivinháveis (UUID) + autorização mesmo assim |
| throttling por plano | tenant de plano menor excede limite | 429 conforme o plano |

## 2. Como automatizar

- **Duas identidades de teste** (A e B) por ambiente, emitidas pelo provedor real (Cognito/IdP) da conta
  de teste; tokens por variável de ambiente (`CDC_TOKEN_A`, `CDC_TOKEN_B` ou equivalente), nunca em arquivo.
- Para cada endpoint com ID de objeto: A cria → B tenta ler/alterar/apagar → confere status **e** estado
  (o objeto não mudou).
- Rodar no **ambiente efêmero/pré-prod** (integração) e repetir no **DAST**; incluir no pentest o
  roteiro de lógica de negócio.
- Unitário da regra de autorização (domínio): "dono == principal", default deny.

## 3. API Gateway e autorizadores

- **Autorizador JWT/Cognito** (HTTP API) e **Cognito/Lambda authorizer** (REST API): o 401 vem do Gateway
  (`{"message":"Unauthorized"}`), não do backend — o cliente precisa tratar.
- Autorizador garante **autenticação**; autorização por objeto continua sendo do backend (ou do Verified
  Permissions). Teste os dois.
- Rota inexistente: HTTP API 404, REST API 403 "Missing Authentication Token" — não confundir com negação.
- Autorizador Lambda com contexto próprio: só o teste no Gateway implantado prova (C2 em `contrato-reverso`).

## 4. Verified Permissions / Cedar (quando usado)

- Política por objeto (`resource.owner == principal`), **default deny**, `forbid` como guarda-corpo, IDs
  imutáveis. Teste as políticas com casos que permitem e casos que negam, versionados junto do código.

## 5. Evidência no relatório

Endpoint, identidades usadas (sem token), requisição sanitizada, status obtido, estado do recurso antes e
depois, severidade e correção. Nunca registrar token, cookie ou dado real.

## Fontes

- https://aws.amazon.com/blogs/apn/testing-saas-solutions-on-aws
- https://aws.amazon.com/blogs/security/get-the-best-out-of-amazon-verified-permissions-by-using-fine-grained-authorization-methods
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/qa.st.5-evaluate-runtime-security-with-dynamic-application-security-testing.html
- https://docs.aws.amazon.com/wellarchitected/latest/framework/sec_appsec_perform_regular_penetration_testing.html
