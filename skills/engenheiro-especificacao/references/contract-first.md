# Contract-First — contratos de API/eventos como parte do Spec Freeze (reference de `engenheiro-especificacao`)

> Materializa o **contract-designer (API-first)** da extensão SDD (`docs/skills/sdd-skill-architecture.md`
> §B) e a **Fase 3 — Arquitetura & Contratos** do loop (`docs/workflows/sdd-development-loop.md`): o
> contrato de API/eventos é **desenhado schema-first** e congelado ANTES do código, não gerado depois.
> Hoje o `aws-lambda-java25-aot` *gera* OpenAPI a partir do código; aqui ele é **fonte de verdade** que
> antecede o código. Liga ao `OpenApiContractTest` (já provado na squad) e ao `spec-code-drift-detector`.

## Fronteira de responsabilidade (importante)

- **Contrato de DADOS (DBML / persistência)** → é do `especialista-banco`. Não duplicar aqui.
- **Contrato de API / eventos (esta reference)** → forma das requisições/respostas HTTP e das mensagens
  assíncronas trocadas entre serviços/consumidores. É o "o quê" do limite externo do sistema.

A spec descreve o comportamento; o contrato fixa **a interface** que materializa esse comportamento.

## Princípio: contrato é fonte de verdade, congelado no Spec Freeze

1. **Schema-first** — o desenho do contrato vem ANTES da implementação. O código se conforma ao
   contrato, nunca o contrário (inverte o fluxo atual "código → OpenAPI gerado").
2. **Versionado** — o contrato é um artefato em `specs/<feature-id>/` (ex.: `openapi.yaml`,
   `asyncapi.yaml`, pacts), com versão semântica; mudança breaking exige bump major + nova decisão.
3. **Congelado** — entra no escopo do **GATE A (Spec Freeze)**: paralelizar slices na Fase 4 só é
   permitido com **interfaces congeladas** (regra medida do loop — sem isso houve regressão de
   wall-clock). Contrato instável quebra a paralelização.

## Os três formatos

| Formato | Para | Papel no Spec Freeze |
|---|---|---|
| **OpenAPI 3.1** | APIs HTTP síncronas (REST) | esquema de cada operação (path, verbo, request/response, erros, `components/schemas`) — congelado antes do handler existir |
| **AsyncAPI** | eventos / mensageria (filas, streams, EventBridge) | esquema de cada evento de domínio (`PedidoConfirmado`, `PagamentoRecusado`), canal, payload, headers |
| **Pact** | contrato consumer-driven | o **consumidor** declara o que espera; o provedor verifica que cumpre — o contrato nasce da necessidade real, não do provedor |

> **Consumer-driven (Pact):** quando há um consumidor conhecido (frontend, outro serviço), o contrato é
> dirigido por ele. O consumidor publica o pact; o provedor o verifica no CI. Isto evita o provedor
> "adivinhar" e expor mais do que alguém usa, e detecta breaking changes do lado certo.

## Liga ao `OpenApiContractTest` (já provado na squad)

O contrato congelado não é decorativo — vira **teste de conformidade** na Fase 5 (testes-antes):

- Cada operação do OpenAPI/AsyncAPI ganha um **teste de contrato** que valida request/response reais
  contra o esquema. Reusa o padrão `OpenApiContractTest` já existente na squad (e o gancho
  Specmatic/Schemathesis citado no `sdd-skill-architecture.md`).
- O teste **falha** se a implementação divergir do contrato — o contrato é o oráculo, não o código.
- AsyncAPI: o payload publicado é validado contra o esquema do evento antes de ir ao broker.

## Liga ao `spec-code-drift-detector` (conformance — Fase 7)

Na Fase 7 (antes do GATE B), o `spec-code-drift-detector` usa o contrato congelado como referência de
conformidade (`sdd-skill-architecture.md`, saídas do detector):

- **operação OpenAPI sem teste de contrato** → drift reportado (bloqueia GATE B);
- **endpoint/evento no código sem operação no contrato** → scope creep (código não rastreado);
- **operação no contrato sem implementação** → requisito órfão.

Ou seja: contract-first (Fase 3) + contract tests (Fase 5) + drift-detector (Fase 7) fecham o ciclo de
conformidade da interface — o contrato é congelado, testado e reconciliado contra o código.

## Checklist de Spec Freeze (parte de contratos)

```
✓ Toda operação síncrona descrita na spec tem path+verbo+schema no OpenAPI 3.1
✓ Todo evento de domínio (EventStorming) tem canal+payload no AsyncAPI
✓ Erros estão no contrato (não só o caminho feliz) — códigos, formato do corpo de erro
✓ Consumidores conhecidos têm pact publicado (consumer-driven)
✓ Versão semântica atribuída; breaking change ⇒ bump major registrado
✓ Contrato referenciado na traceability.md (ReqID → operação → teste de contrato)
✓ Contrato de DADOS delegado ao especialista-banco (não duplicado aqui)
```

## Liga-se a

- **Hub** — eventos de domínio da seção EventStorming viram os schemas AsyncAPI.
- **`references/clarify-gate.md`** — categoria 6 (Integrações) descobre o contrato que aqui é congelado.
- **`especialista-banco`** — dono do contrato de DADOS (DBML); fronteira explícita.
- **SDD** — Fase 3 do loop; `contract-designer` em `sdd-skill-architecture.md` §B; entra no GATE A,
  testado na Fase 5 (`OpenApiContractTest`), reconciliado na Fase 7 (`spec-code-drift-detector`).
