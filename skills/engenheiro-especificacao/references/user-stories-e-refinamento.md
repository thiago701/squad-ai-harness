# User Stories e Refinamento — reference de `engenheiro-especificacao`

> Extraido do hub (Ciclo 9): user stories (INVEST + template BDD), User Story Map, refinamento em 4 atos + DoR, e traducao problema->solucao->MVP (Impact Mapping).

## User Stories — Formato e Qualidade

### Estrutura INVEST para User Stories

```
I — Independent:  a story pode ser desenvolvida sem depender de outra
N — Negotiable:   o como pode mudar; o valor de negócio não
V — Valuable:     entrega valor ao usuário ou negócio quando completa
E — Estimable:    o time consegue estimar o esforço
S — Small:        cabe numa sprint (máximo 5 dias de uma pessoa)
T — Testable:     critérios de aceitação são verificáveis objetivamente
```

### Template Completo de User Story

```
┌─────────────────────────────────────────────────────────────────┐
│ US-042 — Confirmação de Pedido                                  │
├─────────────────────────────────────────────────────────────────┤
│ NARRATIVA:                                                      │
│ Como Operador de Atendimento                                    │
│ Quero confirmar pedidos pendentes                               │
│ Para que o processo de separação e entrega seja iniciado        │
│                                                                 │
│ CONTEXTO (storytelling):                                        │
│ Carlos trabalha no centro de distribuição. Às 8h da manhã      │
│ ele abre a fila de pedidos pendentes e precisa confirmar        │
│ todos os pedidos válidos antes que a transportadora chegue      │
│ às 10h. Cada pedido confirmado é uma promessa ao cliente.       │
│                                                                 │
│ CRITÉRIOS DE ACEITAÇÃO (BDD/Gherkin):                          │
│                                                                 │
│ Cenário 1: Confirmação bem-sucedida                            │
│   Dado que existe um pedido PENDENTE com valor R$150,00        │
│   E o operador tem permissão de confirmação                    │
│   Quando o operador clica em "Confirmar Pedido"                │
│   Então o pedido muda para status CONFIRMADO                   │
│   E o cliente recebe email de confirmação em até 1 minuto      │
│   E o pedido aparece na fila de separação do estoque           │
│                                                                 │
│ Cenário 2: Valor abaixo do mínimo                              │
│   Dado que existe um pedido PENDENTE com valor R$8,00          │
│   Quando o operador tenta confirmar                            │
│   Então o sistema exibe "Valor mínimo de pedido é R$10,00"     │
│   E o pedido permanece PENDENTE                                │
│   E nenhuma notificação é enviada                              │
│                                                                 │
│ Cenário 3: Sem permissão                                       │
│   Dado que o usuário logado tem perfil "Visualizador"          │
│   Quando acessa a tela de confirmação                          │
│   Então o botão "Confirmar" não está disponível                │
│   E o sistema exibe "Ação não permitida para seu perfil"       │
│                                                                 │
│ REGRAS DE NEGÓCIO APLICÁVEIS:                                  │
│   RN-010: Valor mínimo R$10,00                                 │
│   RN-011: Apenas PENDENTE pode ser confirmado                  │
│   RN-014: Notificação obrigatória em confirmação               │
│                                                                 │
│ REQUISITOS NÃO-FUNCIONAIS:                                     │
│   Performance: resposta em < 2s para 95% das requisições       │
│   Disponibilidade: funcional durante horário comercial (6h-22h)│
│                                                                 │
│ DEPENDÊNCIAS:                                                   │
│   Depende de: US-038 (Listagem de Pedidos Pendentes)           │
│   Bloqueante para: US-045 (Separação de Estoque)               │
│                                                                 │
│ ESTIMATIVA: 5 pontos (3 dev + 1 test + 1 review)              │
│ SPRINT: Sprint 4                                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## User Story Map — Visão de Produto Completa

```
TÉCNICA: User Story Mapping (Jeff Patton)

ESTRUTURA DO MAPA:
  Eixo horizontal → narrativa do usuário (sequência de atividades)
  Eixo vertical   → profundidade (da mais crítica à mais refinada)

EXEMPLO — Sistema de Pedidos:

ATIVIDADES (backbone):
┌──────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
│  DESCOBRIR   │   SELECIONAR │    PEDIR     │  ACOMPANHAR  │   RECEBER    │
│  produtos    │   produtos   │    compra    │   pedido     │   entrega    │
└──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┘
       │              │              │              │              │
TAREFAS (histórias):
       │              │              │              │              │
  Buscar por       Adicionar      Informar       Ver status     Confirmar
  nome/categoria   ao carrinho    endereço       do pedido      recebimento
       │              │              │              │              │
  Ver detalhes    Alterar        Escolher       Ver histórico  Avaliar
  do produto      quantidade     pagamento      de eventos     entrega
       │              │              │              │              │
  Comparar        Remover        Aplicar        Cancelar       Solicitar
  produtos        do carrinho    cupom          pedido         devolução
       │              │              │
═══════════════════════════════════ MVP (corte horizontal) ════════════
       │              │              │
  Filtrar         Salvar lista   Parcelar
  por preço       de desejos     pagamento

RELEASES:
  MVP (Sprint 1-3):   linha acima do corte
  V1.1 (Sprint 4-6):  linha abaixo do corte
```

---

## Protocolo de Refinamento com o Tech Lead

### Sessão de Refinamento em 4 Atos

```
ATO 1 — CONTEXTO DE NEGÓCIO (Engenheiro de Especificação lidera — 10 min):
  → Apresenta a história com storytelling completo
  → Apresenta as regras de negócio identificadas
  → Apresenta o diagrama de estados ou fluxo relevante
  → Objetivo: todo o time entende o problema antes de pensar em solução

ATO 2 — QUESTÕES DE NEGÓCIO (todos participam — 10 min):
  → Time faz perguntas sobre o negócio
  → Engenheiro de Especificação responde ou registra como "a investigar"
  → Contradições nas regras são identificadas e resolvidas agora
  → Resultado: lista de regras validadas + lista de pontos a confirmar

ATO 3 — DECISÕES TÉCNICAS (Tech Lead lidera — 10 min):
  → Tech Lead apresenta como o time vai implementar
  → Identifica impactos em outros módulos
  → Alinha com as 3 prioridades do ecossistema
  → Resultado: abordagem técnica acordada

ATO 4 — VALIDAÇÃO E ESTIMATIVA (todos — 5 min):
  → Critérios de aceitação revisados em conjunto
  → Estimativa de esforço
  → Definition of Ready confirmada
  → Próximos passos claros

DURAÇÃO TOTAL: máximo 35 minutos por story
REGRA: se não caiu em 35 min, a story está grande demais → dividir
```

### Definition of Ready (DoR) — Checklist do Engenheiro de Especificação

Uma história só entra no sprint quando:

```
NEGÓCIO:
  □ Narrativa de contexto escrita (storytelling presente)
  □ Ator claramente identificado (perfil, não cargo)
  □ Valor de negócio explicitado (por que isso importa?)
  □ Regras de negócio documentadas no formato RN-XXX
  □ Exceções e casos de borda mapeados

CRITÉRIOS DE ACEITAÇÃO:
  □ Pelo menos 3 cenários em formato Dado/Quando/Então
  □ Cenário de sucesso (happy path)
  □ Pelo menos 1 cenário de falha crítica
  □ Cenários de permissão/acesso (se aplicável)

TÉCNICO:
  □ Requisitos não-funcionais explicitados (performance, disponibilidade)
  □ Dependências identificadas (bloqueia? depende de?)
  □ Diagrama de sequência ou fluxo para histórias complexas
  □ Breaking changes sinalizados para o Tech Lead

ESTIMÁVEL:
  □ Time consegue estimar sem precisar de mais informação
  □ Cabe em uma sprint (se não, dividir antes de entrar)
```

---

## Tradução de Problema de Negócio em Solução de Software

### Framework: Problema → Impacto → Solução → MVP

```
PASSO 1 — ENUNCIE O PROBLEMA PRECISO:
  Problema vago:   "O processo de pedidos é lento"
  Problema preciso:"Operadores levam 8 minutos para confirmar um pedido
                   porque precisam alternar entre 3 sistemas diferentes.
                   Com 200 pedidos/dia, são 26 horas desperdiçadas."

PASSO 2 — QUANTIFIQUE O IMPACTO:
  Impacto humano:    "Operadores fazem horas extras às sextas-feiras"
  Impacto financeiro:"R$3.000/mês em horas extras + R$8.000/mês em
                      pedidos cancelados por demora na confirmação"
  Impacto estratégico:"NPS cai quando pedido demora mais de 2h para confirmar"

PASSO 3 — DEFINA A SOLUÇÃO MÍNIMA:
  Não: "Sistema completo de gestão de pedidos com dashboard, relatórios,
        integração com ERP, app mobile e BI"
  Sim: "Tela unificada que mostra os 3 dados necessários lado a lado
        e permite confirmar com 1 clique — reduz 8min para 45s"

PASSO 4 — VALIDE O MVP:
  Hipótese:  "Se confirmar demora < 1 minuto, horas extras caem 80%"
  Métrica:   "Tempo médio de confirmação por pedido"
  Baseline:  "8 minutos hoje"
  Meta:      "< 1 minuto em 90% dos casos"
  Prazo:     "Medir após 2 semanas em produção"
```

### Mapa de Impacto (Impact Mapping — Gojko Adzic)

```
ESTRUTURA:
  POR QUÊ? (objetivo de negócio)
    └── QUEM? (atores que impactam o objetivo)
          └── COMO? (comportamento do ator que impacta o objetivo)
                └── O QUÊ? (entregável de software que viabiliza o comportamento)

EXEMPLO — Reduzir cancelamentos de pedidos em 30%:

POR QUÊ: Reduzir cancelamentos em 30% em 3 meses

  QUEM: Operadores de atendimento
    COMO: Confirmam pedidos mais rápido
      O QUÊ: Tela unificada de confirmação (US-042)
      O QUÊ: Confirmação em lote para pedidos similares (US-048)

  QUEM: Clientes
    COMO: Acompanham status em tempo real (não ligam para cancelar)
      O QUÊ: Notificação automática de status (US-051)
      O QUÊ: Página de rastreamento do pedido (US-055)

  QUEM: Gerentes
    COMO: Identificam gargalos antes de virar cancelamento
      O QUÊ: Dashboard de pedidos travados > 30min (US-060)

RESULTADO: MVP = US-042 + US-051 (menor esforço, maior impacto)
```

---
