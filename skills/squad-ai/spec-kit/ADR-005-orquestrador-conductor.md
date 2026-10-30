# ADR-005 — Orquestrador Conductor (padrão Sakana Fugu Ultra)

| Campo | Valor |
|---|---|
| **Projeto** | Squad AI Skill-Orchestrator |
| **ADR** | ADR-005 |
| **Data** | 2026-06-23 |
| **Autor(es)** | Squad AI (arquiteto-minimalista) |
| **Status** | **Aceito** (2026-07-02 — aprovação do Tech Lead humano; adoção fiada no `squad-pipeline` §Contrato Conductor) |
| **Decisores** | Tech Lead (humano) |

---

## Contexto

A orquestração atual da Squad AI (`squad-pipeline` + `.claude/agents` + `orchestration/tool-routing-policy.md`) é gated e madura, mas o roteamento é **estático**: uma árvore de decisão fixa por *blast radius* (arquivos/deps) e por tipo de tarefa. A topologia de comunicação entre agentes é **implícita** (escolha binária paralelo↔sequência), os papéis são **fixos por subagente**, e não há um *test-time scaling* recursivo nem um contrato declarativo de workflow.

Os papers do Sakana Fugu (TRINITY, Conductor, Technical Report — ICLR 2026) descrevem um contrato de coordenação superior: o orquestrador **emite um workflow declarativo** (subtask + worker + access_list) em que o `access_list` é a topologia de comunicação de primeira classe, com papéis Thinker/Worker/Verifier, isolamento intra-workflow (anti-colapso), memória compartilhada persistente e recursão (`SELF`). Crucialmente, o paper do Conductor (Fig. 11) demonstra que **o contrato funciona sem treino** quando um modelo forte é apenas promptado com ele — o que torna a adoção viável já, sob P1.

É preciso decidir **como** absorver esse modelo sem violar os princípios imutáveis (P1>P2>P3; gated, não autônomo; segurança/supply-chain primeiro) e sem reescrever o motor que já funciona.

## Decisão

**Decidimos:** adotar o **contrato Conductor como camada de planejamento do `squad-pipeline`** (Fase 1 — "Conductor-as-a-prompt"), formalizado em `orchestration/conductor/` (blueprint + system prompt + contrato de workflow + referências). O motor passa a **emitir o workflow declarativo** (3 listas alinhadas + roles + budget); os gates e subagentes existentes **assumem** os papéis de Verifier e Worker do scaffold. **Não** treinamos modelo agora (Fase 2 fica como roadmap, condicionada a um conjunto de tarefas verificáveis).

**Justificativa resumida:** é a opção que captura o ganho do scaffold com **mudança mínima** (P1) e custo quase nulo (P3), preservando integralmente o caráter *gated* e a segurança de supply chain.

## Alternativas Consideradas

### Opção A — [Escolhida] Contrato Conductor por prompt (Fase 1), sobre o motor atual

| Prós | Contras |
|---|---|
| Mudança mínima: não reescreve o `squad-pipeline` | Ganho de seleção fina fica abaixo de um orquestrador treinado |
| Fundamentada (Conductor sem treino já supera workers — Fig. 11) | Depende da disciplina do prompt (sem garantia de pesos) |
| Custo ~zero; reversível (é documentação + prompt) | — |

### Opção B — Treinar um orquestrador pequeno agora (Fase 2: TRINITY/sep-CMA-ES ou Conductor/GRPO)

| Prós | Contras |
|---|---|
| Seleção de agente ótima; menor latência (caminho Fugu) | Exige dataset verificável com gabarito que **ainda não temos** |
| Estado da arte real | Alto custo/complexidade — viola P1 e P3 nesta fase |

**Por que foi rejeitada:** sem tarefas verificáveis de domínio, evolução/RL não têm sinal. Systematizar antes de validar é *Premature Systematizer*.

### Opção C — Refatorar subagentes e `tool-routing-policy` para o novo contrato

| Prós | Contras |
|---|---|
| Integração mais profunda do contrato | Invasivo; risco de regressão num motor que já funciona |

**Por que foi rejeitada:** viola P1 (mudança grande antes de validar o contrato em 3–4 tarefas reais). Fica para depois da Fase 1.

## Consequências

### Positivas

- Topologias ricas (chain, best-of-N com agregador dinâmico, debate, recursão) ficam **declarativas** e auditáveis via `access_list`.
- *Orchestration collapse* e a tensão isolamento↔contexto passam a ser tratados explicitamente.
- O Cérebro-Vault/ReasoningBank ganha papel formal no contrato (retrieve antes de planejar, remember após sintetizar).
- A recursão `SELF` adiciona auto-correção **até o GATE** — sem quebrar o "gated, não autônomo".

### Negativas / Riscos Assumidos

- Sem treino, a *seleção fina* de worker é heurística (mitigação: revisor de família distinta + agregador dinâmico, já na `tool-routing-policy`).
- Risco de over-orquestração (criar workflow onde 1 worker bastava) — mitigado pela Constituição §1/§4 (1-shot para trivial) e pela validação em 3–4 tarefas antes de qualquer skill.

## Custo da Reversão

| Aspecto | Avaliação |
|---|---|
| **Classificação** | Baixo (dias) |
| **O que precisaria mudar** | Remover `orchestration/conductor/` e reverter o INDEX/ATTRIBUTIONS; o motor volta ao estado atual |
| **Estimativa de esforço** | < 1 dia |
| **Sinal de alerta para reverter** | Workflows inflados sem ganho de qualidade medível, ou aumento de custo/latência sem retorno em 3–4 tarefas-piloto |

## Smoke Test — ADR vivo (R4)

| Campo | Valor |
|---|---|
| **smoke_test** | N/A (decisão de processo/contrato; sem oráculo estrutural nesta fase) |
| **tipo** | N/A |
| **valida_em** | Piloto manual: 3–4 tarefas reais comparando workflow Conductor vs roteamento atual (qualidade, passos, custo) |
| **se_falhar** | Sem ganho ⇒ manter o roteamento atual e arquivar a Fase 1 |

## Referências

- [Blueprint do Orquestrador Conductor](../../orchestration/conductor/README.md)
- [Contrato de workflow](../../orchestration/conductor/workflow-contract.md)
- [System prompt operacional](../../orchestration/conductor/ORCHESTRATOR_PROMPT.md)
- [Referências dos papers](../../orchestration/conductor/REFERENCES.md) · [ATTRIBUTIONS — Sakana AI](../../docs/ATTRIBUTIONS.md)
- ADR relacionado: [ADR-004 — Piloto gated SkillOpt-Sleep](./ADR-004-piloto-skillopt-sleep.md)

---

## Histórico

| Data | Evento |
|---|---|
| 2026-06-23 | Proposto por Squad AI (arquiteto-minimalista), derivado dos papers Sakana Fugu |
| 2026-07-02 | **Aceito** pelo Tech Lead humano — junto da ativação do MCP `squad-context` (evidência: docs/mcp-lab) |
