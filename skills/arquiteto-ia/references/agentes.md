# Referência — Agentes de IA (taxonomia, anatomia, ReAct/Plan-Execute/Supervisor, A2A)

> Parte da skill `arquiteto-ia`. Carregue sob demanda. Hub: `../SKILL.md`.
## Taxonomia de Sistemas de IA

### Tipos de Integração LLM

| Tipo | Quando Usar | Complexidade | Controle |
|---|---|---|---|
| **LLM Call direto** | Geração simples, classificação, extração | Mínima | Total |
| **RAG** | Respostas baseadas em documentos/conhecimento próprio | Baixa | Alto |
| **Tool Use (Function Calling)** | Agente precisa executar ações no sistema | Média | Alto |
| **Agente único** | Fluxo iterativo com memória e ferramentas | Média | Médio |
| **Pipeline sequencial** | Múltiplas transformações de dados via LLM | Média | Alto |
| **Multi-agente orquestrado** | Tarefas complexas que exigem especialização | Alta | Médio |
| **A2A autônomo** | Agentes colaborativos com autonomia real | Muito Alta | Baixo |

### Quando NÃO usar LLM
```
NÃO use LLM para:
  ✗ Cálculos financeiros precisos (use código determinístico)
  ✗ Validações de regras de negócio críticas (use código testável)
  ✗ Consultas a banco de dados (use SQL — LLM pode alucinar)
  ✗ Operações idempotentes que precisam de resultado idêntico
  ✗ Dados em tempo real sem RAG/grounding (alucinação garantida)

USE LLM para:
  ✓ Interpretar linguagem natural do usuário
  ✓ Gerar texto estruturado (JSON, relatórios, resumos)
  ✓ Classificar e categorizar conteúdo
  ✓ Extrair informações de texto não estruturado
  ✓ Raciocínio contextual e síntese de informações
  ✓ Geração de código com revisão humana
```

---

## Arquitetura de Agentes — Princípios e Padrões

### Anatomia de um Agente Bem Projetado
```
┌─────────────────────────────────────────────────────────────┐
│                        AGENTE                               │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   MEMÓRIA    │    │   NÚCLEO     │    │ FERRAMENTAS  │  │
│  │              │    │  (LLM + 	   │    │              │  │
│  │ - Contexto   │◄──►│   Prompt)    │◄──►│ - Tool 1     │  │
│  │ - Histórico  │    │              │    │ - Tool 2     │  │
│  │ - State      │    │              │    │ - Tool N     │  │
│  └──────────────┘    └──────┬───────┘    └──────────────┘  │
│                             │                               │
│                    ┌────────▼────────┐                      │
│                    │   GUARDRAILS    │                      │
│                    │ - Input filter  │                      │
│                    │ - Output filter │                      │
│                    │ - Rate limits   │                      │
│                    └─────────────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

### Padrões de Arquitetura de Agentes

**Padrão 1 — ReAct (Reason + Act):** agente raciocina, age, observa, repete.
```
Thought → Action → Observation → Thought → Action → ... → Final Answer
```
Ideal para: tarefas que exigem múltiplos passos com feedback entre eles.

**Padrão 2 — Plan-and-Execute:** agente planeja todos os passos, depois executa.
```
Plan: [Step1, Step2, Step3] → Execute Step1 → Execute Step2 → Execute Step3
```
Ideal para: tarefas com estrutura previsível onde planejar antes melhora qualidade.

**Padrão 3 — Supervisor/Worker:** orquestrador delega para agentes especializados.
```
Supervisor → Worker A (especialista em pesquisa)
           → Worker B (especialista em cálculo)
           → Worker C (especialista em escrita)
           ← Resultado consolidado
```
Ideal para: tarefas que exigem especialização — cada worker é simples e focado.

**Padrão 4 — Pipeline sequencial:** saída de um agente é entrada do próximo.
```
Raw Input → [Agente Extrator] → [Agente Validador] → [Agente Formatador] → Output
```
Ideal para: transformações de dados em etapas claras e auditáveis.

### Protocolo A2A (Agent-to-Agent)
```
Princípios do A2A:
1. Cada agente expõe uma interface clara (Agent Card) com: nome, descrição, capacidades, inputs esperados
2. Comunicação via mensagens estruturadas — nunca texto livre entre agentes
3. Agente produtor não conhece consumidor (desacoplamento)
4. Cada agente é testável isoladamente com inputs sintéticos
5. Falha de um agente não cascateia sem tratamento explícito
6. Estado compartilhado via store central — não via passagem em cadeia

Agent Card mínimo:
  name: "extrator-dados-fiscais"
  description: "Extrai CNPJ, valor e data de notas fiscais em texto"
  input_schema: { type: "text", format: "nota_fiscal_raw" }
  output_schema: { cnpj: str, valor: Decimal, data: date }
  capabilities: ["extração", "validação-cnpj"]
  fallback: "retorna null fields com reason quando extração falha"
```

---

