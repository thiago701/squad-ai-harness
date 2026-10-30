# Arquitetura AI-First — IA como camada de primeira classe

> Referência da skill `arquiteto-ia`. Complementa `agentes.md` (agentes/A2A) e `guardrails.md`.
> Aplica-se a produtos em que a IA **é** o produto, não um endpoint adicionado ao backend.

## 1. O sintoma que esta referência corrige

Numa arquitetura "IA como API", o cliente do modelo é chamado de dentro do serviço de negócio.
Consequências previsíveis, todas caras:

- Trocar de fornecedor exige mexer em regra de negócio.
- Não existe um lugar único para medir latência, custo e qualidade da IA.
- Timeout, retry e fallback ficam espalhados em `try/except` de vários serviços.
- Operação offline é impossível sem reescrever.
- Nenhum teste roda sem chamar (e pagar) o provedor.

**AI-First** significa que a orquestração de IA é uma **camada nomeada**, com contrato próprio,
telemetria própria e testes próprios — do mesmo jeito que persistência é uma camada.

## 2. As camadas

```text
┌──────────────────────────────────────────────┐
│ Experience Layer      UI, kiosk, tempos, cópia│
├──────────────────────────────────────────────┤
│ Application Layer     casos de uso, sessão,   │
│                       jobs, políticas         │
├──────────────────────────────────────────────┤
│ AI Orchestration      workflow, State, router,│  ← a camada que quase todo projeto esquece
│                       prompts, guardrails,    │
│                       avaliação, telemetria   │
├──────────────────────────────────────────────┤
│ AI Providers          cloud · GPU local ·     │
│                       determinístico (mock/   │
│                       filtro)                 │
├──────────────────────────────────────────────┤
│ Infrastructure        storage, fila, banco,   │
│                       logs                    │
├──────────────────────────────────────────────┤
│ Hardware Adapters     câmera, impressora,     │
│                       display                 │
└──────────────────────────────────────────────┘
```

**Regra de dependência:** as setas apontam só para baixo. A camada de aplicação conhece a
interface da orquestração; nunca o SDK de um fornecedor. Nenhuma camada acima conhece "OpenAI",
"Gemini", "Bedrock" ou o nome de um modelo.

## 3. Os cinco contratos que definem a camada

| Contrato | Responsabilidade | Erro típico quando falta |
|---|---|---|
| **Provider** | Uma operação de IA, com custo, latência e erro tipados | SDK importado no domínio |
| **Router** | Escolher a cadeia de providers por regras observáveis | Fornecedor hard-coded; sem plano B |
| **Workflow** | Sequência, State explícito, timeout e retry por etapa | Fluxo escondido em `if` aninhado |
| **Guardrail** | Safety de entrada e de saída, allowlist, limites | Conteúdo impróprio chega ao usuário |
| **Evaluation** | Baseline, métrica, gate de aceite de mudança | Mudança de prompt entra sem número |

Implemente na ordem **Provider → Workflow → Router → Guardrail → Evaluation**. Criar todos os
contratos antes de ter um caso de uso funcionando é overengineering — o `arquiteto-minimalista`
arbitra.

## 4. Degradação como requisito de arquitetura

Todo caminho de IA precisa de um **terminal que não pode falhar**: uma resposta determinística,
local, barata e instantânea. Ela não é "plano B" — é parte do desenho.

```text
Provider premium → Provider padrão → Provider local → Resultado determinístico
                                                      (nunca falha, nunca é tela de erro)
```

Um produto de IA sem terminal determinístico tem disponibilidade igual à do seu fornecedor mais
frágil. Esse é o cálculo que decide se o produto funciona num evento com Wi-Fi ruim.

## 5. Não fechar a porta do edge

Decisões que **não** custam nada hoje e preservam a operação local amanhã:

- Nenhum SDK de nuvem fora de `providers/`.
- Configuração de provedor por arquivo/env, nunca por código.
- Assets resolvidos de disco local; CDN é cache, não fonte.
- Storage local como fonte da verdade; nuvem é réplica opcional.
- Identificadores gerados localmente (sem depender de serviço remoto para criar uma sessão).
- Health check de conectividade que alterna o router automaticamente.

## 6. Telemetria é parte do contrato, não um extra

Toda operação de IA emite, sem exceção: `session_id`, provedor, modelo, versão do prompt, seed,
latência por etapa, custo realizado, resultado do guardrail, e o veredito de qualidade quando
houver. Sem isso não existe benchmark, não existe diagnóstico e não existe decisão de custo.

## 7. Skills relacionadas

`engenheiro-langgraph` (workflow e State) · `ai-imagem-generativa` (providers e router de imagem) ·
`visao-computacional` (pré/pós determinístico) · `inferencia-gpu-local` (edge/GPU) ·
`ai-evaluation` (baseline e gate) · `orquestrador-multiagente` (coordenação multiagente) ·
`arquiteto-minimalista` (arbitragem de overengineering) · `engenheiro-seguranca` (guardrails, LGPD).
