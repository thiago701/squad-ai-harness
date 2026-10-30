---
description: Roda o loop agi-papers (loops/agi-papers-loop.md) — busca, deduplica e cataloga papers/artigos científicos novos sobre AGI em docs/research/agi/, sem commit automático.
argument-hint: "[opcional: foco/subtema da rodada, ex. 'safety' ou 'benchmarks'. Se vazio, cobre as 6 categorias do índice de forma balanceada]"
origin: sandeco-loop
---

Execute o loop especificado em `loops/agi-papers-loop.md`.
Leia esse documento primeiro e siga os passos da volta exatamente.

Pedido do usuário (foco opcional da rodada): **$ARGUMENTS**

Resumo do que rodar:
1. Leia `docs/research/agi/99-Meta/.harvest-state.json` (estado/dedup da rodada anterior).
2. Busque papers/artigos sobre AGI (arXiv, Semantic Scholar/Google Scholar, labs e blogs
   técnicos de ponta), sem filtrar idioma — inclua ao menos 1 busca em português. Se
   `$ARGUMENTS` tiver um foco, concentre a maior parte das buscas nele.
3. Deduplique contra `seen_ids`; aplique o juiz-LLM endurecido da seção "Verificação" do loop
   (relevância = especificamente sobre AGI, encaixa numa das 6 categorias do índice).
4. Escreva uma nota atômica por achado aprovado em `docs/research/agi/notas/` (resumo próprio,
   nunca cópia literal; frontmatter completo) e atualize `docs/research/agi/INDEX.md` +
   `.harvest-state.json`.
5. Rode o check (dedup + validação de frontmatter) e cole a saída no transcript — é a evidência
   que decide a parada.

Condição de parada: sucesso quando pelo menos 1 nota nova válida foi catalogada e indexada;
sem-progresso após 2 rodadas seguidas sem nota nova; bloqueado se uma fonte prioritária falhar
2 rodadas seguidas; esgotado após 20 turnos. Erro ou estouro de teto NUNCA é sucesso.
**Nunca commite ou faça push automaticamente** — o loop só escreve arquivos locais; revisão e
commit ficam com o humano.
