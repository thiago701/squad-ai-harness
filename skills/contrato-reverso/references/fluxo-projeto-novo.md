# Fluxo em projeto novo — codificar, revisar, testar, evoluir

> Como a Squad aplica a skill `contrato-reverso` do primeiro commit em diante. Cada fase tem
> **entrada, ação, saída verificável e gate**. Comece por UM fluxo crítico; amplie depois de medir.

`CR` = `python <skill>/scripts/cr.py` (instalada: `~/.claude/skills/contrato-reverso/scripts/cr.py`).

## 0. Diagnóstico (antes de qualquer código ou teste)

| pergunte | onde olhar | registre como |
|---|---|---|
| quem consome? (frontend, microserviço, parceiro) | código cliente, SDK, specs de produto, tráfego sanitizado | fato / hipótese / indisponível |
| contrato publicado existe? | `openapi*.yaml`, `swagger*` | caminho |
| que Gateway e integração? | SAM (HTTP/REST), CloudFormation/CDK (`cdk.out`), Terraform (`*.tf` ou `terraform show -json`), ALB/ECS | formato + HTTP ou REST API (ALB/ECS puro: só C2) |
| mesmo repositório ou separados? | backend, Gateway, infra, consumidor | caminhos/repos |
| quanto custa testar hoje? | duração da suíte, preparação de ambiente, instáveis | números medidos (não estimados) |

Saída: 5 linhas com fatos, hipóteses e indisponíveis. **Nunca** misture os três.

## 1. CODIFICAR — contrato antes do código

1. `CR iniciar --raiz . --consumidor <nome> --tipo navegador|servico [--origem-navegador https://...]`
   gera o **rascunho** (`rascunho: true`, origens `openapi-exemplo`; sem OpenAPI, as rotas do Gateway
   viram interações `hipotese`) e o verificador C1 do stack: JUnit (Java), `tests/cdc_fabrica.py` (Python)
   ou `test/cdc-fabrica.mjs` (Node).
2. **Substitua as expectativas pelas do consumidor real**: só os campos que ele LÊ; `presenca`/`nulo`
   como ele trata; `enums_fechados` onde há switch exaustivo; jornada na ordem do uso com capturas;
   identidades para isolamento; `origem` apontando arquivo/linha da fonte. Sem acesso ao consumidor:
   `limitacao` + `hipotese`, explícitos.
3. Remova `rascunho: true` só depois disso (enquanto existir, o veredito é no máximo inconclusivo).
4. Adapte a fábrica do C1 (Java `criarHandlerV1/V2`, Python `criar_handler`, Node `criarHandler`):
   handler real + dublês nas portas de saída (nunca nuvem).
5. Escreva o código **até `CR verificar --nivel direcionado` aprovar** (TDD pelo consumidor).

Gate: contrato revisado + C1 executando (não "inconclusivo") + quebras = 0 ou aceitas por humano.

## 2. REVISAR — checklist de compatibilidade em todo PR que toca API

- [ ] `CR impacto` diz o nível; o nível rodou e o relatório está anexado (veredito + versões avaliadas)?
- [ ] Mudança "aditiva"? Enum novo × `enums_fechados`; campo que virou opcional; `null` novo; omissão de `null`; ordenação.
- [ ] Gateway mudou? Rotas (sombra por `{param}`), autorizador, CORS, payload 1.0/2.0, estágio — e **C2 planejado**.
- [ ] Respostas do próprio Gateway (401 do autorizador, 404 sem rota, 429, 503/504) estão no contrato e o consumidor as trata?
- [ ] Mudança intencional de contrato tem aceite com responsável, prazo e migração (`divergencias-aceitas.yaml`)?
- [ ] Nenhuma asserção enfraquecida, snapshot regravado em massa ou teste removido para passar?
- [ ] Testes novos têm risco, origem do esperado e evidência de detecção (bench/mutação)?

Gate: veredito `aprovado`, ou `reprovado` só por divergência aceita; `inconclusivo` não passa como aprovado.

## 3. TESTAR — contínuo, por impacto e orçamento

| quando | comando | orçamento |
|---|---|---|
| a cada salvamento (local) | `CR observar` (rápido → direcionado conforme o diff) | rápido ≤ 2 s |
| antes do push | `CR verificar --nivel auto` | direcionado ≤ 30 s |
| código transversal / build / incerto | automático: `direcionado + suíte completa` | ≤ 300 s |
| Gateway alterado, nightly, antes de promover | `CR verificar --nivel ampliado --ambiente dev --alvo <url>` | ≤ 300 s + ambiente |

Sem CI novo: harness local do projeto, hooks locais como complemento, rotina noturna local para a
regressão ampliada periódica. Tokens só por `CDC_TOKEN_<IDENTIDADE>`; produção só GET/OPTIONS/HEAD.

## 4. EVOLUIR — suíte que melhora sem inchar

1. **Incidente, falha reproduzível ou mudança de consumidor** → nova interação/campo no contrato
   (camada mais rápida que prova), com `origem: {tipo: incidente, ref: ...}`.
2. **Prove a utilidade:** `CR bench` — mutações automáticas do contrato/Gateway + `mutacoes.yaml` do
   código. Aceite: detecta todas as quebras, 0 falso positivo, seleção por impacto não perde
   detecção, linha de base estável, feedback mais rápido que a suíte anterior.
3. **Enxugue com prova:** só remova/una teste redundante se o bench mostrar a mesma detecção.
4. **Orçamento:** `ORCAMENTO-EXCEDIDO` exige justificar a proteção extra ou compensar.
5. **Amplie:** próximo fluxo crítico só depois do bench verde no atual.
6. **Instabilidade:** diagnostique (dado compartilhado? relógio? ordem?) — nunca "rodar de novo até passar".

## Papéis na Squad

| skill | o que faz com esta skill |
|---|---|
| `squad-pipeline` | chama `iniciar` no SCAFFOLD de API nova e `verificar --nivel auto` no gate de TESTE |
| `especialista-qualidade` | aplica as regras de suíte enxuta e admissão de testes gerados |
| `spec-code-drift-detector` | drift spec↔código; esta skill cobre consumidor↔contrato↔Gateway↔implementação |
| `tech-lead-review` / `review` | usa o checklist da fase REVISAR |
| `aws-lambda-java25-aot`, `java25-spring-boot` | stack do provedor; C1 Java pronto via template |
