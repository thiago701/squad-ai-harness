# Procedência — clean-code-craftsman

## v1.2 (2026-10-28) — Formato de achado com consequência obrigatória

- **Fonte:** hyhmrright/brooks-lint, `skills/_shared/common.md` e `skills/brooks-review/SKILL.md`
  @ `15fa2d49877969f65a25b9f05897cd72fae32d33` — licença **MIT** (verificada via API do GitHub).
- **O que entrou (reescrito, sem copiar texto):** diagnóstico completo antes de qualquer remédio;
  cada achado do Modo Revisão em Sintoma → Fonte → Consequência → Remédio; achado sem consequência
  é descartado como ruído; nota de saúde opcional (100, −15/−5/−1, piso 0) comparável só na mesma régua.
- **Onde:** passos 2–4 do Modo Revisão no `SKILL.md`.
- **Ganho medido:** `tests/test_absorcao_2026_10_28.py` (3 testes da skill vermelhos antes, verdes depois).
- **Ficou de fora:** os 12 livros/6 riscos de decaimento (já cobertos pelo catálogo de smells),
  config `.brooks-lint.yaml`, histórico em arquivo e triagem interativa.

## v1.1 (2026-10-27) — Revisão e limpeza de código gerado por IA

- **Fonte:** Yeachan-Heo/oh-my-claudecode, `skills/ai-slop-cleaner/SKILL.md`
  @ `e10206d8789b0ac4e5214eddbfbd203c1b757dea` — licença **MIT** (verificada via API do GitHub).
- **O que entrou (reescrito, sem copiar texto):** classificar os achados em 5 categorias antes de
  editar; travar comportamento com teste antes da limpeza; passadas isoladas em ordem fixa
  (morto → deduplicar → nomes/erros/fronteiras → testes) com verificação a cada passada;
  preferir apagar a adicionar; quem gerou não aprova a própria limpeza.
- **Onde:** `references/codigo-gerado-por-ia.md` (novo) + ponteiro no Modo Refatoração e no mapa.
- **Ganho medido:** `tests/test_absorcao_2026_10_27.py` — os testes da skill eram vermelhos
  antes (lacuna inexistente) e passam depois; 0 regressão nos testes da skill (`test_clean_code_eval`).
- **Ficou de fora:** comandos, hooks e integração com o runtime da origem.
