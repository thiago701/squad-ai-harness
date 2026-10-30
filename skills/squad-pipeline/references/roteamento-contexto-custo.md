# squad-pipeline · reference — Roteamento de skill/contexto via MCP e orçamento de tokens (P3)

> Conteúdo movido VERBATIM do hub `../SKILL.md` (ciclo 4 do Loop V3, 2026-07-09) — progressive
> disclosure. **Nota de resolução de paths:** os caminhos relativos abaixo permanecem como no hub e
> se resolvem a partir de `skills/squad-pipeline/` (raiz da skill), não deste subdiretório.

## Roteamento de skill e contexto via MCP `squad-context` · ativado 2026-07-02

Com o servidor `squad-context` ativo (`.mcp.json`; evidência: `docs/mcp-lab/RELATORIO-OTIMIZACAO-MCP-SQUAD-AI.md`,
−95,2% de contexto fixo, top-3 100%), o motor **não** carrega o catálogo de skills inline. O fluxo é:

1. **Rotear:** `squad_skill_search(query=<tarefa>, k=3)` → top-3 com score (determinístico, auditável).
2. **Disclosure progressivo:** `squad_skill_card(name)` (≤1.600 chars) e só escalar a
   `level='full'` se o card não bastar para a fase.
3. **Contexto canônico:** `squad_project_context(topic)` no lugar de recarregar AGENTS.md/política.
4. **Rastreabilidade:** decisões de arquitetura/review relevantes → `squad_decision_log(action='append',
   agent=<skill>, decision=…, tags=[…])`; antes do Plano, `action='query'` no domínio da tarefa
   (complementa o RETRIEVE da Fase 0.5).

**Fallback:** servidor indisponível ⇒ fluxo antigo (catálogo/descriptions), sem bloquear o pipeline.
**Regra de honestidade:** a economia só existe se o catálogo inline NÃO for injetado junto — não usar os dois.

## Consciência de custo — orçamento de tokens por tarefa (P3) · R3

O roteamento de modelo **corta** custo; o orçamento o **torna visível e governável**.

1. **No Plano (Fase 3):** declare um orçamento por tier em `.claude/pipeline/<slug>/custo.md`
   (modelo em `../../templates/CUSTO.md`). Tetos: trivial ~10k · small ~40k · standard ~150k · large ~500k.
2. **A cada fase:** registre modelo usado + tokens estimados vs reais (acumulado).
3. **Alerta 80%:** ao cruzar 80% do orçamento, **pare e pergunte** ao humano
   (continuar / re-rotear p/ modelo mais barato / re-escopar). Nunca estoure em silêncio.
4. **No relatório final (`99-relatorio.md`):** consolide real vs orçado + economia de
   roteamento. Atualize `../../squad-ai/metricas/custo_tokens.json` (consumido pelo `/squad-cost`).

> Custo é cláusula P3 — **abaixo** de Simplicidade e Performance. O orçamento **informa**, não
> tiraniza: estourar para entregar simples e correto é aceitável **com registro**; estourar
> por desperdício de contexto (MCPs demais, re-leitura) é o que o alerta caça.
