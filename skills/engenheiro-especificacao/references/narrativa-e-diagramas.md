# Narrativa e Diagramas — reference de `engenheiro-especificacao`

> Extraido do hub (Ciclo 9, progressive disclosure): storytelling de casos de uso + producao de diagramas (Structurizr DSL, C4, sequencia, estados, modelo de dominio).

## Storytelling para Refinamento de Casos de Uso

### A Estrutura da História Perfeita

Cada caso de uso começa como uma narrativa antes de virar especificação técnica:

```
ESTRUTURA NARRATIVA (5 elementos obrigatórios):

1. CONTEXTO:    "Mariana é operadora de caixa num supermercado. São 17h40,
                 horário de pico. Há 8 clientes na fila."

2. TENSÃO:      "O cliente da vez quer pagar com um cartão que deu problema
                 ontem. O sistema precisa validar se o cartão está liberado
                 sem deixar a fila crescer."

3. AÇÃO:        "Mariana insere o cartão no terminal. O sistema consulta
                 em menos de 2 segundos se está bloqueado."

4. RESULTADO:   "O sistema retorna 'Cartão liberado' e o pagamento é
                 processado normalmente."

5. IMPACTO:     "A fila flui. A loja não perde a venda. O cliente sai
                 satisfeito. Mariana mantém o ritmo."

POR QUE STORYTELLING FUNCIONA:
  → Revela requisitos não-funcionais ocultos (2 segundos de resposta)
  → Explicita o contexto de uso real (horário de pico, pressão)
  → Gera empatia no time técnico com o usuário real
  → Torna contradições visíveis ("mas se o cartão está bloqueado, o que acontece?")
  → Facilita identificação de casos de exceção naturalmente
```

### Técnica: Walking Skeleton Story

Conte a história do caminho mais simples possível primeiro — sem exceções:

```
SKELETON STORY — Confirmação de Pedido:

"João acessa o sistema, localiza o pedido #1234 na lista de pendentes,
 clica em Confirmar, vê a tela de confirmação com o resumo do pedido,
 confirma, e recebe a mensagem 'Pedido confirmado com sucesso'.
 Ele segue para o próximo pedido da fila."

DEPOIS adicione as exceções uma a uma:
  → "E se o pedido já estiver confirmado?"
  → "E se o valor estiver abaixo do mínimo?"
  → "E se o cliente não tiver sido notificado?"
  → "E se o João não tiver permissão para confirmar?"

Cada "E se?" vira um fluxo alternativo com sua própria história curta.
```

### Técnica: Story Spine para Épicos

Para histórias maiores (épicos ou features), use a estrutura:

```
Era uma vez...        [contexto do ator e situação atual]
Todo dia...           [o problema/dor que existe hoje]
Até que um dia...     [o sistema novo entra em cena]
Por causa disso...    [a primeira consequência — o que muda]
Por causa disso...    [a segunda consequência — efeito em cadeia]
Por causa disso...    [o impacto final no negócio]
Até que finalmente... [o estado de sucesso desejado]
E desde então...      [o novo normal após o sistema]

EXEMPLO — Sistema de Gestão de Estoque:
"Era uma vez uma loja que vendia 500 produtos diferentes.
 Todo dia os gerentes conferiam o estoque manualmente em planilhas.
 Até que um dia o sistema de gestão foi implantado.
 Por causa disso, o estoque passou a ser atualizado em tempo real.
 Por causa disso, rupturas de estoque caíram 60%.
 Por causa disso, as vendas perdidas diminuíram R$15.000/mês.
 Até que finalmente o gerente parou de vir ao trabalho aos sábados.
 E desde então a equipe foca em atender clientes, não em contar itens."
```

---

## Diagramas como Código — Structurizr DSL + Mermaid

Diagramas de arquitetura devem viver **ao lado do código**, versionados, revisáveis em PR,
automaticamente renderizados. **Structurizr DSL** é o padrão da squad para C4 Model e **Mermaid**
para sequência/estado/flow (renderização nativa no GitHub/GitLab/Obsidian).

```
// docs/architecture/workspace.dsl — Structurizr DSL (arquivo único, C4 completo)
workspace "Sistema de Pedidos" {
    model {
        cliente = person "Cliente"
        operador = person "Operador"

        pedidos = softwareSystem "Sistema de Pedidos" {
            api = container "API" "Spring Boot 4 + Java 25" "Java, REST"
            web = container "Web App" "React 19" "TypeScript"
            db = container "Banco de Dados" "Postgres 17" "SQL" "Database"
            fila = container "Fila" "Amazon SQS" "AWS"
        }
        gateway = softwareSystem "Gateway de Pagamento" "Externo"

        cliente -> web "usa"
        operador -> web "usa"
        web -> api "chama REST/JSON"
        api -> db "persiste via JPA"
        api -> fila "publica eventos"
        api -> gateway "cobra via HTTPS"
    }
    views {
        systemContext pedidos "Contexto" { include * autolayout lr }
        container pedidos "Containers" { include * autolayout tb }
        theme default
    }
}
```

**Render automático em CI** (GitHub Action):
```yaml
- uses: structurizr/cli-action@v1
  with:
    command: export -workspace docs/architecture/workspace.dsl -format plantuml,mermaid
- run: git diff --exit-code docs/architecture/diagrams/  # falha se diagrama desatualizado
```

**Vantagem:** uma alteração arquitetural vira diff legível no PR. Reviewer vê o diagrama novo
junto com o código que o justifica.

## Diagramas Conceituais — Guia de Produção

### C4 Model — Quatro Níveis de Abstração

```
NÍVEL 1 — CONTEXTO (para stakeholders e C-level):
  Mostra: o sistema como caixa preta + atores externos + sistemas externos
  Pergunta respondida: "O que este sistema faz e com quem se relaciona?"

NÍVEL 2 — CONTAINER (para arquitetos e tech leads):
  Mostra: grandes blocos tecnológicos (app web, API, banco, fila)
  Pergunta respondida: "Como o sistema está dividido em peças tecnológicas?"

NÍVEL 3 — COMPONENTE (para desenvolvedores):
  Mostra: módulos/serviços internos de um container
  Pergunta respondida: "O que existe dentro desta API?"

NÍVEL 4 — CÓDIGO (raramente necessário):
  Mostra: classes e relacionamentos
  Pergunta respondida: "Como este componente é implementado?"
```

```
DIAGRAMA C4 — NÍVEL 1 (CONTEXTO) em texto estruturado:

Sistema: Gestão de Pedidos

Atores externos:
  [Operador]          → usa → [Sistema de Pedidos]
  [Cliente]           → recebe notificações de → [Sistema de Pedidos]
  [Gerente]           → aprova pedidos especiais em → [Sistema de Pedidos]

Sistemas externos:
  [Sistema de Pedidos] → consulta → [Gateway de Pagamento]
  [Sistema de Pedidos] → envia emails via → [Serviço de Email (SES)]
  [Sistema de Pedidos] → autentica usuários via → [Cognito]
  [Sistema de Pedidos] → armazena arquivos em → [S3]
```

### Diagrama de Sequência — Fluxo Detalhado de Interação

```
DIAGRAMA DE SEQUÊNCIA — Confirmar Pedido:

Operador          API            PedidoUseCase      Repositório      Notificador
   │                │                   │                │                │
   │─── POST ──────►│                   │                │                │
   │  /pedidos/     │                   │                │                │
   │  {id}/confirmar│                   │                │                │
   │                │──executar(id)────►│                │                │
   │                │                   │──buscar(id)───►│                │
   │                │                   │◄──Pedido───────│                │
   │                │                   │                │                │
   │                │                   │[valida regras] │                │
   │                │                   │[pedido.confirmar()]             │
   │                │                   │──salvar()──────►│               │
   │                │                   │◄──ok────────────│               │
   │                │                   │──notificar()────────────────────►│
   │                │                   │◄──ok─────────────────────────────│
   │                │◄──PedidoConfirmado─│                │                │
   │◄── 200 OK ─────│                   │                │                │
   │  {status:      │                   │                │                │
   │   CONFIRMADO}  │                   │                │                │

FLUXO ALTERNATIVO — Valor abaixo do mínimo:
   │                │──executar(id)────►│                │
   │                │                   │──buscar(id)───►│
   │                │                   │◄──Pedido(R$5)──│
   │                │                   │[valor < R$10]  │
   │                │◄──ValorMinimo────-─│                │
   │                │   Exception        │                │
   │◄── 422 ────────│                   │                │
   │  {error:       │                   │                │
   │  "Valor mínimo │                   │                │
   │   não atingido"}│                  │                │
```

### Diagrama de Estados — Ciclo de Vida de Entidades

```
DIAGRAMA DE ESTADOS — Pedido:

                    ┌─────────────────────────────────────────────┐
                    │              CICLO DE VIDA DO PEDIDO         │
                    └─────────────────────────────────────────────┘

         [criado]
            │
            ▼
      ┌──────────┐
      │ PENDENTE │ ◄─────────────────────────────┐
      └────┬─────┘                               │ (reabrir — se política permitir)
           │                                     │
     ┌─────┴──────────────────┐                  │
     │                        │                  │
     ▼ [operador confirma]    ▼ [operador cancela]│
┌───────────┐            ┌──────────┐            │
│ CONFIRMADO│            │CANCELADO │            │
└─────┬─────┘            └──────────┘            │
      │                                          │
      │ [estoque separado]                       │
      ▼                                          │
┌───────────┐                                    │
│ EM PREPARO│──── [problema encontrado] ─────────┘
└─────┬─────┘
      │ [entregue a transportadora]
      ▼
┌───────────┐
│  ENVIADO  │
└─────┬─────┘
      │ [confirmação de recebimento]
      ▼
┌───────────┐
│ ENTREGUE  │◄──────── estado final positivo
└───────────┘

REGRAS DE TRANSIÇÃO (Regras de Negócio derivadas do diagrama):
  RN-010: PENDENTE → CONFIRMADO: requer valor >= R$10,00
  RN-011: PENDENTE → CANCELADO:  qualquer operador pode cancelar
  RN-012: CONFIRMADO → CANCELADO: apenas gerente pode cancelar após confirmação
  RN-013: ENVIADO → qualquer:     nenhuma transição permitida após envio
  RN-014: ENTREGUE → qualquer:    estado terminal — imutável
```

### Modelo de Domínio — Entidades e Relacionamentos

```
MODELO DE DOMÍNIO — E-commerce (linguagem de negócio, não técnica):

┌─────────────────────────────────────────────────────────────────┐
│                    BOUNDED CONTEXT: PEDIDOS                     │
│                                                                 │
│  ┌──────────────────┐         ┌─────────────────────────────┐   │
│  │    PEDIDO        │         │      ITEM DE PEDIDO         │   │
│  │ (Aggregate Root) │ 1 ───► N│                             │   │
│  │                  │         │  quantidade                 │   │
│  │  id              │         │  preço unitário             │   │
│  │  status          │         │  subtotal (derivado)        │   │
│  │  valor total     │         │                             │   │
│  │  criado em       │         └──────────────┬──────────────┘   │
│  │  confirmado em   │                        │ N                │
│  └────────┬─────────┘                        ▼ 1                │
│           │ N                        ┌──────────────┐           │
│           ▼ 1                        │   PRODUTO    │           │
│  ┌──────────────────┐                │  (ref. ao    │           │
│  │    CLIENTE       │                │   Catálogo)  │           │
│  │  (Value Object   │                └──────────────┘           │
│  │   referência)    │                                           │
│  └──────────────────┘                                           │
│                                                                 │
│  EVENTOS DE DOMÍNIO:                                            │
│  → PedidoCriado         → PedidoConfirmado                      │
│  → PedidoCancelado      → PedidoEnviado                         │
│  → PedidoEntregue                                               │
└─────────────────────────────────────────────────────────────────┘

          │ PedidoConfirmado     │ PedidoCancelado
          ▼                     ▼
┌──────────────────┐   ┌──────────────────┐
│BOUNDED CONTEXT:  │   │BOUNDED CONTEXT:  │
│  NOTIFICAÇÕES    │   │    ESTOQUE       │
│                  │   │                  │
│ (consome eventos │   │ (consome eventos │
│  e envia email)  │   │  e repõe itens)  │
└──────────────────┘   └──────────────────┘
```

---
