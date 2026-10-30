# Clarify Gate — caça de ambiguidade (reference de `engenheiro-especificacao`)

> Materializa o **ambiguity-killer** da extensão SDD (`docs/skills/sdd-skill-architecture.md` §B, linha
> "ambiguity-killer (clarify-gate)") e a **Fase 1 — Discovery & Clarificação** do loop
> (`docs/workflows/sdd-development-loop.md`). Estilo Spec Kit `/clarify`: ANTES do Spec Freeze e do plan,
> caça ambiguidades, força perguntas de esclarecimento e registra uma seção **Clarifications** na spec.
> Princípio 5 do hub (especificação executável) e o anti-padrão "Critério de aceitação vago" são a régua.

## Por que existe

A extensão SDD coloca um **gate de clarificação** na Fase 1: o planejamento fica **bloqueado** enquanto
houver ambiguidade crítica aberta. A spec viva só "congela" (GATE A) depois que toda ambiguidade
bloqueante virou decisão registrada com fonte. Isto converte a bússola do hub ("um dev que nunca ouviu
falar do negócio consegue implementar só com este documento?") em um passo executável e auditável.

## Categorias de ambiguidade (varredura forçada)

Para cada feature, varra TODAS as seis categorias — não pule nenhuma por achar "óbvia". Cada categoria
que não puder ser respondida com uma frase verificável vira uma pergunta de esclarecimento.

| # | Categoria | Caça (o que perguntar) |
|---|---|---|
| 1 | **Atores / permissões** | Quem dispara? Quem pode/não pode (RBAC)? Há ator de sistema? Quem autoriza exceção? (liga ao RN Tipo 4 — Permissão do hub) |
| 2 | **Dados / formato / limites** | Tipos, unidades, formato (CPF? ISO-8601? centavos?), obrigatório vs opcional, min/max, cardinalidade, default, nulabilidade, precisão monetária |
| 3 | **Fluxos alternativos** | E se o recurso não existe? Concorrência (dois confirmam o mesmo)? Idempotência? Reprocessamento? Estado inválido na transição? |
| 4 | **Erros & exceções** | O que falha e como o sistema reage? Mensagem ao usuário? Rollback? Retry? Dead-letter? Quem é notificado? |
| 5 | **NFR (não-funcionais)** | Latência (p95/p99), throughput, volume esperado, retenção, SLA/SLO, custo-teto (P3), privacidade/LGPD. (vago "deve ser rápido" é proibido) |
| 6 | **Integrações** | Sistemas externos, contratos de API/evento, sincronicidade, time-out, fallback se o terceiro cair, quem é dono do contrato |

> Categoria 6 (contratos) entrega o gancho para `references/contract-first.md` — o contrato vira artefato
> congelado na Fase 3. Aqui só se **descobre** que a integração existe e o que ela exige.

## Perguntas de esclarecimento FORÇADAS

Regras do gate:

1. **Toda ambiguidade vira pergunta numerada** com a categoria, opções candidatas e o impacto de não
   decidir. Não há "deixa pra depois" silencioso.
2. **A resposta tem dono e fonte** (`Fonte: Maria Silva (Gerente Comercial) — 2026-06-26`), igual ao
   FORMATO PADRÃO DE REGRA do hub (RN-XXX).
3. **Ambiguidade sem resposta = item BLOQUEANTE**, registrado como `[ABERTA]` até virar decisão.
4. **Cada decisão vira critério de aceite testável** (Dado/Quando/Então) ou regra de negócio (RN-XXX) —
   uma clarificação que não muda a spec não era ambiguidade real.

Template de pergunta:

```
CLQ-007 [Dados/limites] — Precisão do valor do pedido
  Ambiguidade: "valor mínimo R$10,00" — armazenar em centavos (int) ou decimal? Arredondamento?
  Opções:      (a) BigDecimal scale 2, HALF_EVEN  (b) long centavos
  Impacto se não decidir: erro de arredondamento em fatura → bug financeiro silencioso.
  Decisão:     (a) BigDecimal scale 2, HALF_EVEN
  Fonte:       João (Tech Lead) — 2026-06-26
  Vira:        RN-014 + critério BDD no caso de uso US-042
```

## Seção "Clarifications" na spec

Registre na spec (`SPEC_FREEZE_v1.md`, antes do freeze) uma seção fixa:

```
## Clarifications
| ID      | Categoria        | Ambiguidade            | Decisão                | Fonte             | Status   |
|---------|------------------|------------------------|------------------------|-------------------|----------|
| CLQ-001 | Atores/permissões| Quem aprova desconto>20%| Apenas gerente         | Maria — 2026-06-26| RESOLVIDA|
| CLQ-007 | Dados/limites    | Precisão do valor      | BigDecimal scale 2     | João — 2026-06-26 | RESOLVIDA|
| CLQ-011 | Integrações      | Fallback gateway caiu  | —                      | —                 | ABERTA   |
```

A seção é a evidência do gate: rastreável, com fonte, consumível pela `traceability.md` na Fase 4.

## O GATE — zero ambiguidade bloqueante antes do plan

```
GATE DE CLARIFICAÇÃO (Fase 1 → não passa para Planning/Spec Freeze enquanto):
  ✗ existir qualquer CLQ com Status = ABERTA marcada como bloqueante
  ✗ existir critério de aceite com termo vago ("rápido", "intuitivo", "correto")
  ✗ existir RN Tipo 4 (permissão) sem ator/autorizador definido
  ✓ toda ambiguidade das 6 categorias respondida OU explicitamente diferida como não-bloqueante
```

Herdado do gate do `squad-pipeline` (a decisão go/no-go é do humano; gated, não autônomo).

### Exceção explícita: "skip clarification" para spike

Para **spike / prova de conceito / descarte planejado**, o autor pode marcar a feature com
`skip clarification` no topo da spec — o gate libera o planejamento com ambiguidades abertas, MAS:

- o motivo fica registrado (`skip clarification: spike de viabilidade, código descartável`);
- nenhum artefato do spike entra no fluxo de produção sem reabrir o gate;
- é a ÚNICA forma de pular o gate — silêncio nunca conta como skip.

## Liga-se a

- **Hub** — RN Tipo 4 (Permissão), FORMATO PADRÃO DE REGRA, anti-padrão "Critério de aceitação vago",
  Princípio 5 (especificação executável). Esta reference é o passo executável daquilo.
- **`references/contract-first.md`** — categoria 6 (Integrações) descobre o contrato que será congelado.
- **SDD** — Fase 1 do loop; `ambiguity-killer` em `sdd-skill-architecture.md` §B; alimenta o GATE A.
