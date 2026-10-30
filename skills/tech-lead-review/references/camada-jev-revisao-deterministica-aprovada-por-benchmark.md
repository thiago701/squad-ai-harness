# tech-lead-review · Camada JEV — revisão determinística aprovada por benchmark

> Reference da skill `tech-lead-review` (movida da SKILL.md em 11/10/2026 — hub + references, I3). Carregue só quando a tarefa pedir este tema.

## Camada JEV — revisão determinística aprovada por benchmark

> **Proposta 1 aprovada** (`labs/jev-ecosystem/docs/04-propostas-evolucao.md`) — 44 PRs,
> Quality Gate anti-regressão. A camada é **aditiva**: doutrina, severidades e protocolos
> desta skill permanecem; a JEV entra como primeiro estágio de decisão.

1. **JEV First (obrigatório para PRs):** antes do julgamento LLM/humano, executar a camada
   determinística (`labs/jev-code-review/src/jev_review` — ~47 microdecisões tipadas
   Choice/Score/Noul + evidências + veredito). Modo padrão = cenário C (JevSim):
   recall **1,000** · veredito **1,000** · US$ 0 · 3 ms (baseline v4-pro: 0,868 · 0,364 ·
   US$ 0,0018/PR · 4,6 s).
2. **Pre-Report Gate vira código:** achado sem evidência cai; confiança < 0,8 rebaixa
   severidade; sem evidência = descartado — a prosa virou regra executada.
3. **Escalação estrita (cenário D):** segurança critical/high e regressão HIGH escalam ao
   LLM obrigatoriamente; demais casos a JEV encerra. **Cap de severidade** em achados de
   escalação não-segurança (ciclo 7: over-blocking 27/44 → veredito 0,886). PR de alto
   risco → modo híbrido D-strict (US$ 0,0005/PR; recall 0,959; veredito 0,932).
4. **Medição contínua:** re-rodar o benchmark (`labs/jev-code-review`) a cada mudança de
   prompt desta skill — o gate anti-regressão decide, não a opinião.

> **Honestidade:** os números são do piso determinístico (JevSim); a validação do Jev real
> (TypeSafe) é pendente (chave externa). Detalhes: `references/review-jev.md`.
