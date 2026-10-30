# Procedência & Verificação — absorção de 2026-07-15

> **Origem:** material técnico colado pelo usuário Thiago (documento "Orquestração Avançada de Modelos de
> Linguagem e Sistemas Multiagentes"). Tratado como **input externo** conforme a política de supply chain
> da Squad (`security/security-policy.md`, `auditoria-skill-externa`): nenhum código executável foi
> importado; o conteúdo é descritivo/arquitetural. Sem sinais de prompt injection detetados.

## Verificação leve (web, 2026-07-15)

| Âncora | Status | Nota |
|---|---|---|
| IAL-Scan: 6.549 repos → 68 falhas/47 projetos, 91,9% precisão | ✅ **CONFIRMADO** | arXiv 2607.01641 (jul/2026). 74 achados potenciais → 68 confirmados. Bate exato |
| OpenTelemetry GenAI: spans CLIENT p/ LLM, atributos `gen_ai.*` | ✅ **CONFIRMADO** | Convenções em *Development*; client spans estáveis, agent/framework experimentais |
| W3C Trace Context `traceparent` (formato/propagação) | ✅ **CONFIRMADO** | Padrão W3C; formato do exemplo é válido |
| gVisor (Sentry em Go, user-space) vs Firecracker (microVM/KVM) — modelo de isolamento | ✅ **CONFIRMADO** | Descrição correta dos mecanismos e do trade-off segurança×I/O |
| Cold-starts sandbox (Docker <90ms, gVisor ~150ms, Firecracker <2s, WASM <10ms) | 🟡 **APROX.** | Ordem de grandeza correta; números exatos variam por fonte/config |
| Padrões Saga / Event Sourcing / partição Kafka por chave | ✅ **CONFIRMADO** | Padrões-padrão de EDA; descrição fiel |
| Ganho STORM +18,7 (Commit0-Lite) / +1,4 (PaperBench) | ⚠️ **USER-PROVIDED** | Não confirmado nesta passagem (arXiv 2605.20563 citado pelo usuário) |
| Falha de MAS em produção 41–87% | ⚠️ **USER-PROVIDED** | Faixa citada; não verificada independentemente |
| Tabela de frameworks (setup min, linhas, tokens) | ⚠️ **ILUSTRATIVO** | Comparativo vendor-ish; o *modelo de controlo* é robusto, os minutos não |
| ≈93 escritas de persistência p/ conversa simples | ⚠️ **USER-PROVIDED** | Plausível (estilo LangGraph); não verificado |
| Overhead de telemetria (LangSmith ~0% … Langfuse ~15%) | ⚠️ **USER-PROVIDED** | Ilustrativo; depende de carga/config |
| Taxonomia `ag2.span.type` (conversation/agent/llm/tool/…) | ✅ **CONFIRMADO (AG2)** | Específica do AG2/AutoGen; não é universal entre frameworks |

## Regra de uso
Ao citar qualquer linha marcada ⚠️/🟡 como fundamento de decisão, sinalize a procedência. Os **padrões**
(coordenação como camada, checkpoint no supervisor, plano-como-contrato, salvaguardas de término,
zero-trust, observabilidade assíncrona) são a parte **robusta** e acionável; os **números** são
secundários e, quando user-provided, servem de ordem de grandeza — não de fato.

## Fontes consultadas na verificação
- arXiv 2607.01641 — "When Agents Do Not Stop: Uncovering Infinite Agentic Loops in LLM Agents"
- OpenTelemetry — Generative AI semantic conventions (gen-ai-spans) e blog GenAI observability
- Northflank / field guides — sandboxing de agentes (gVisor, Firecracker, WASM), 2026
- W3C — Trace Context (traceparent)
- Citações originais do usuário: refs 1–39 do documento absorvido (arXiv + blogs de fornecedores)

## Absorção v1.1.0 (2026-10-18)
- Fonte: https://github.com/openai/openai-agents-python — commit `9abc9182d06dbd28330af888306031269d57a175`, licença MIT (© 2025 OpenAI).
- Entrou: guardrails com tripwire (exceção tipada que interrompe a execução; modos bloqueante × paralelo; escopo 1º/último agente) e filtro de entrada de handoff que remove itens de ferramenta/raciocínio.
- Reescrito em stdlib (`scripts/handoff_guard.py`); acréscimo nosso: fail-closed quando a guarda quebra. Conteúdo externo tratado como dado; nada executado.

## Absorção v1.2.0 (2026-10-24)
- Fonte: arquitetura de multi-agentes publicada por `@thedelost` (`https://x.com/thedelost/status/2114016386896773177`, vídeo *CLAUDE CODE REGISTRY TIP · 10 REPOS · ONE .CLAUDE FOLDER*) e artigo técnico citado de `@hanakoxbt` (`https://x.com/i/article/2111940327145918464`, *How to Build an AI Quant Research Team with Claude Code*).
- Entrou: (a) separação das 3 primitivas em `.claude/` (`subagents` contexto isolado, `skills` carregamento progressivo, `hooks` determinísticos `exit 2`) e higiene de ingestão seletiva; (b) desacoplamento *Analyst vs. Desk* com barreira `THE LINE` e veredito imutável de 3 estados (`DATA_VALIDATED`, `TRADE_OFF`, `NO_EDGE`) sob corte temporal obrigatório; (c) topologia de 5 papéis (`lead`/`scout`/`sweeper`/`skeptic`/`librarian`) com detecção de platô (`plateau` vs `isolated_peak`); (d) ledger compartilhado (`research.md`) com as 4 leis invariantes anti-reteste.
- Reescrito em português brasileiro em `references/equipe-pesquisa-vereditos-ledger.md` e implementado do zero em stdlib (`scripts/veredito_plat_ledger.py`, eval `evals/eval_veredito_plat_ledger.py`). Conteúdo externo tratado como dado; nenhum código externo copiado.
