# Testes reversos dirigidos pelo consumidor — APIs REST, API Gateway, Lambda/ECS

> Doutrina da skill `contrato-reverso`. Ferramenta: `scripts/cr.py` (stdlib + PyYAML).
> Formato: `references/formato-contrato.md`. Fluxo por fase: `references/fluxo-projeto-novo.md`.
> Evidência medida: `references/caso-validacao.md`.

## 1. O que "reverso" significa aqui

A análise parte do **consumidor** e anda até o backend; a execução segue o caminho real:

```
análise:   expectativa do consumidor → contrato publicado → integração no Gateway → comportamento do backend
execução:  frontend/microserviço → API Gateway → Lambda/ECS → dependências → resposta ao consumidor
```

Três evidências **distintas** — aprovar uma não aprova as outras:

| evidência | camada | pergunta |
|---|---|---|
| conformidade da especificação | A | o OpenAPI promete o que o consumidor usa? |
| configuração do Gateway | B | rotas, autorizador, CORS, payload, limites atendem contrato e consumidor? |
| compatibilidade da implementação | C1 | o handler real, com Gateway simulado do SAM, atende? |
| funcionamento pelo Gateway implantado | C2 | o endpoint do ambiente autorizado atende? |

Teste que chama a Lambda direto (ou o mock) é C1 no máximo. **Nunca declare compatibilidade de
ponta a ponta sem C2.** Sem C2, o relatório diz "não comprovado" — e isso é a resposta certa.

## 2. De onde vêm as expectativas (e por que não do OpenAPI do backend)

Ordem de preferência: código do cliente / SDK → testes do cliente → contratos de consumo já
aprovados → exemplos aprovados → tráfego **sanitizado** → incidentes → documentação → hipótese.
Toda interação registra `origem: {tipo, ref}`. Derivar tudo do OpenAPI do próprio backend
reproduz o erro que ele compartilha com a implementação — se a única fonte for ele, use
`tipo: openapi-exemplo` e o relatório marca "mesma fonte do provedor". Sem acesso ao consumidor:
`limitacao` no contrato + `hipotese` nas expectativas inferidas. Exemplo real (caso Task Manager):
o README promete 409 em `POST /tasks` e o OpenAPI não — só aparece porque a expectativa veio do README.

## 3. O que verificar (escolha pelo risco da mudança)

- **Estrutura:** método, rota, versão, parâmetros, headers, content-type, status.
- **Campos:** obrigatório × opcional, **ausência × `null`**, tipo, formato (date-time), enum, precisão, serialização.
- **Semântica:** paginação, filtro (`todos`), ordenação (`ordenado_por`), contagens (`igual_tamanho_de`, `soma_de`), eco do enviado, efeitos colaterais na jornada (capturas).
- **Segurança:** 401 sem token, isolamento entre usuários (404, nunca 403/200), expiração.
- **Navegador:** CORS + preflight (origem, métodos, headers incluindo `authorization`, credenciais × `*`).
- **Gateway:** autorizador por rota, formato de payload (1.0 × 2.0), rota sombreada por `{param}`, estágio nomeado.
- **Limites:** timeout do cliente × função × integração; throttling (429) declarado; idempotência em retries de escrita.
- **Coexistência de versões:** o contrato de cada versão de consumidor ativa é um arquivo; todos rodam.

**Mudança "aditiva" que quebra:** valor novo de enum para consumidor com `enums_fechados`;
mudança de ordenação; campo que vira opcional; `null` onde antes havia valor; omissão de `null`
(`NON_NULL`) para cliente que distingue ausente de nulo.

### Respostas que o backend nunca vê (só B e C2 enxergam)

| situação | quem responde | o que o consumidor recebe |
|---|---|---|
| sem rota no HTTP API | Gateway | 404 `{"message":"Not Found"}` |
| JWT ausente/inválido (autorizador JWT) | Gateway | 401 `{"message":"Unauthorized"}` em `application/json` — **não** é problem+json |
| throttling (`DefaultRouteSettings`) | Gateway | 429 |
| integração acima do limite (30 s no HTTP API) | Gateway | 503/504 |
| preflight sem `CorsConfiguration` | Gateway | sem headers CORS → navegador bloqueia |
| estágio nomeado (`/prod/...`) | Gateway → backend | path pode chegar com o prefixo — **comprovar em C2** |

## 4. Suíte enxuta por projeto — regras de admissão

Eficiência = **proteção ÷ (tempo + custo)**. Quantidade de testes não é qualidade.

1. Antes de criar um teste, nomeie o **risco desprotegido** e verifique se um teste existente pode
   ser aprimorado (ex.: um campo a mais no contrato em vez de um teste novo).
2. **Camada mais rápida que prova:** contrato estático (A/B) > in-process (C1) > Gateway real (C2).
   Ponta a ponta só para jornada/integração que exige essa abrangência.
3. Uma combinação por camada — não repita em unitário, contrato, integração e E2E sem justificar.
4. Partição de equivalência, fronteiras e combinações representativas; PBT com limite explícito
   de exemplos e tempo.
5. Consolidar/remover redundância **só depois** de provar (bench de mutação) que a detecção se mantém.
6. Menos arquivos com o mesmo trabalho executado não é otimização; mover a suíte para segundo
   plano não esconde lentidão.
7. Orçamento por nível (`contracts/consumidores/orcamento.json` do projeto). Crescimento relevante exige:
   proteção nova + impacto no tempo + justificativa (o relatório gera `ORCAMENTO-EXCEDIDO`).
8. **Nunca** reduza a suíte cortando cenário crítico.

### Teste gerado pela Squad só entra com:

- risco protegido e **origem do resultado esperado** (não "o que o código faz hoje");
- dados isolados e reprodutíveis, execução determinística (o modelo não reinterpreta nada a cada run);
- **evidência de detecção**: falha numa regressão/violação representativa (mutação seletiva —
  `cr.py bench` ou PIT no domínio);
- custo proporcional ao benefício e contribuição sobre os testes existentes.

### Anti-Goodhart (inegociável)

Proibido: enfraquecer asserção, atualizar snapshot em massa, apagar teste que falhou, aceitar o
comportamento atual como correto para ficar verde, aceitar mudança de contrato silenciosamente.
Mudança intencional → `divergencias-aceitas.yaml` com responsável, prazo e migração (humano).
Instabilidade é bug a diagnosticar — repetir até passar não é evidência.

## 5. Execução contínua por impacto (sem CI novo)

| nível | camadas | quando | orçamento |
|---|---|---|---|
| rápido | A+B | toda alteração; observador local | ≤ 2 s (meta p90 1 s) |
| direcionado | A+B+C1 | código do provedor, contrato, OpenAPI | ≤ 30 s (meta p90 15 s) |
| direcionado + suíte | + suíte completa | código **transversal** (serialização, auth, borda, DTO, config), build, arquivo sem regra (incerto) | ≤ 300 s |
| ampliado | + C2 | Gateway mudou; nightly; antes de promover | ≤ 300 s + ambiente |

`--nivel auto` escolhe pelo diff; incerteza **amplia**. Preserve uma regressão ampliada periódica
(rotina noturna local) para achar buracos da seleção incremental. O observador faz debounce,
cancela a execução superada, roda uma por vez e trava contra duplicata. Cache por hash de conteúdo
das entradas (contrato + OpenAPI + SAM + fonte do provedor) — nunca por data.

## 6. Restrições corporativas

Nada em `.github/workflows`, nada que dependa de permissão administrativa ou de CI novo.
Harness local do projeto (na Squad: `ops/run.py contrato-reverso*`), comandos reprodutíveis, hooks locais só como
complemento (não são bloqueio central). Saída com código: 0 aprovado · 1 reprovado · 2 inconclusivo.
Credenciais só por variável (`CDC_TOKEN_<IDENTIDADE>`), nunca no arquivo nem no relatório;
ambiente `producao: true` só roda métodos seguros.

## 7. Procedimento da Squad (comece por UM fluxo crítico)

1. **Diagnóstico:** consumidores conhecidos, OpenAPI, template do Gateway (mesmo repo ou não),
   tipo de API/integração, duração das suítes, o que não é protegido. Separe fato, hipótese e indisponível.
2. **Contrato do consumidor** com origem por expectativa; jornada em ordem, com capturas.
3. `verificar --nivel rapido` → corrija ou registre aceite (humano).
4. **C1:** verificador in-process do provedor lendo o mesmo arquivo — `cr.py iniciar` copia o
   template Java/JUnit (`../templates/java-junit/`); edite só `criarHandler()` (dublês nas portas de saída).
5. **Bench** com mutações quebradoras e compatíveis do próprio fluxo; aceite = detecta todas,
   zero falso positivo, seleção por impacto não perde detecção, estável, feedback mais rápido.
6. **Matriz** consumidor → expectativa → endpoint → Gateway → serviço → teste → evidência (sai no relatório).
7. Só então amplie para o próximo fluxo.

## 8. Limites atuais da ferramenta (não prometa além disso)

- Gateways: SAM (HTTP e REST), CloudFormation/CDK e Terraform (estático ou `terraform show -json`).
  Terraform estático não avalia expressões (vira pendente). ALB/ECS sem API Gateway, WebSocket e VTL
  não são lidos — verifique por C2. Detalhes: `references/gateways-e-stacks.md`.
- C1 para Java (JUnit), Python e Node (runner + fábrica). Outros stacks: verificador próprio que grave o mesmo "observado".
- Ordenação/paginação feitas pelo banco só se provam com o banco real (integração) ou em C2.
