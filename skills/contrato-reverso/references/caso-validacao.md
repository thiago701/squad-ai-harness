# Caso de validação medido (17/10/2026, v1.1.0)

> Evidência de que a skill funciona, e de onde ela ainda não chega. Relatório completo e arquivos
> do bench: `docs/evolucao-contrato-reverso-2026-10-17/` no repositório squad-ai-harness.
> Bench num contêiner de 2 vCPU, Maven quente. Os números absolutos mudam por máquina; as proporções devem se manter.

## Projetos

| projeto | papel no teste | stack | Gateway |
|---|---|---|---|
| Task Manager (`app/`) | contrato revisado à mão a partir do README (fontes independentes do OpenAPI) | Java 25 Lambda, JUnit | HTTP API, JWT Cognito, estágio `prod`, throttling, CORS parametrizado |
| Agenda Clínica (`app/agenda-clinica-lambda`) | **projeto novo**: `iniciar` + revisão mínima + `criarHandlerV2()` de 3 linhas | Java 25 Lambda | HTTP API sem autorizador, CORS parametrizado |
| Pedidos (`demo/serverless-pedidos`) | C1 pelo runner Python (`tests/cdc_fabrica.py`) | Python Lambda | SAM REST API (v1) |
| Exemplo Node (`exemplos/node-rest-api`) | C1 pelo runner Node (`test/cdc-fabrica.mjs`) | Node ESM | SAM REST API (v1) |

Paridade de leitores: o mesmo Gateway em SAM, CDK (`cdk.out`), CloudFormation REST, Terraform HCL e
`terraform show -json` produz o mesmo modelo normalizado (`exemplos/gateways/`, coberto por teste).

## Bench (mutações em cópia temporária; linha de base repetida, estável)

| | Task Manager | Agenda (novo) | Pedidos (Python) |
|---|---|---|---|
| mutações (quebra / compatível) | 26 / 8 | 13 / 5 | 8 / 2 |
| ANTES — suíte existente | 9/26 · 0 FP · 12,05 s | 5/13 · 0 FP · 48,05 s | 3/8 · **1 FP** · 0,45 s |
| DEPOIS rápido (A+B) | 19/26 · 0 FP · **0,17 s** | 9/13 · 0 FP · **0,15 s** | 4/8 · 0 FP · 0,11 s |
| DEPOIS direcionado (A+B+C1) | **26/26** · 0 FP · 5,1 s | **13/13** · 0 FP · 3,46 s | **8/8** · 0 FP · 0,17 s |
| DEPOIS seleção por impacto | **26/26** · 0 FP · 5,12 s | **13/13** · 0 FP · 3,42 s | **8/8** · 0 FP · 0,15 s |
| proteção do Gateway antes | **0/7** | **0/3** | **0/4** |

Exemplo Node: 19/19 quebras, 0/5 FP, direcionado 0,19 s.
Estação de trabalho (VM, pasta montada): direcionado aprovado nos três — 21,6 s · 23,8 s · 0,9 s.

O que só a nova abordagem pega: required removido, enum novo em enum fechado, tipo trocado e `null` novo no
contrato; rota, path, autorizador, CORS e payload 1.0/2.0 no Gateway; serialização renomeada; `null` omitido;
`Content-Type` errado.

## Lições que viraram regra da skill

1. **Rota removida nem sempre quebra.** Sem a rota `/tasks/summary`, `GET /tasks/summary` cai em
   `/tasks/{taskId}` e o handler, que roteia pelo path, responde certo. A camada B registra
   `B-ROTA-SOMBREADA` (risco) e o bench só gera remoção de rota quando nenhuma outra a atende.
2. **Query obrigatória esquecida:** o rascunho da Agenda não enviava `de`/`ate` e só C1 pegou. A camada A
   ganhou `A-QUERY-OBRIGATORIA` e o `iniciar` passou a gerar as query obrigatórias com valores do schema.
3. **Sem autorizador, as claims não chegam ao backend.** O Gateway simulado só injeta JWT em rota autenticada;
   tirar o `DefaultAuthorizer` quebra todo consumidor autenticado (não é só "rota pública").
4. **Rascunho e verificador não adaptado nunca aprovam:** o veredito fica inconclusivo, com o motivo dito.
5. **Cancelar o observador mata a árvore de processos** (verificar → Maven → JVM). Matar só o pai deixava JVM órfã.
6. **Template malformado é quebra, não traceback.** O SAM do Pedidos era YAML inválido e a ferramenta caía;
   agora vira `B-ARQUIVO-MALFORMADO`.
7. **REST API v1 muda o que o consumidor vê:** rota inexistente é 403 `Missing Authentication Token`, e o CORS
   da resposta real é responsabilidade do Lambda (proxy) — C1/C2 checam `C-CORS-RESPOSTA`.
8. **Terraform estático não chuta:** expressão não literal vira pendente (`B-LEITURA-PARCIAL`); para exatidão,
   `terraform show -json`.
9. **Suíte antiga também erra para o lado do falso positivo:** a do Pedidos reprovava campo novo compatível
   (leitor não tolerante). O contrato do consumidor só afirma o que ele lê.
10. **Ambientes que proíbem exclusão** (pastas montadas): a ferramenta não apaga o observado anterior, exige
   que o novo seja mais recente que a execução.

## Achados reais e destino

Com o padrão recomendado aprovado pelo dono, foram corrigidos no projeto: CORS (parâmetro
`CorsAllowedOrigins`, sem `*`), as duas formas do 401 do Gateway e o 429 no OpenAPI, `required` na Agenda e o
template inválido do Pedidos. Seguem abertos: estágio nomeado (pendente de C2), rota sombreada (risco),
tipo do consumidor (hipótese) e README × OpenAPI no 409 de `POST /tasks`.

## Não comprovado

C2 (Gateway implantado) não rodou: sem endpoint nem tokens; ficou com o dono. Ordenação feita pelo banco
não é provada em C1. Consumidores reconstruídos, sem código de cliente real.
