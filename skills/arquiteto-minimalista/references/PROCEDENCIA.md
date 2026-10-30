# Procedência — arquiteto-minimalista

## v1.1 (2026-10-27) — Teste da deleção e regra das costuras

- **Fonte:** mattpocock/skills, `skills/engineering/codebase-design/SKILL.md` e
  `skills/engineering/improve-codebase-architecture/SKILL.md`
  @ `59db609eb1e18aaf59b63284d0e52255aff0c63c` — licença **MIT** (verificada via API do GitHub).
- **O que entrou (reescrito, sem copiar texto):** teste da deleção para decidir se um módulo se paga;
  costura com um adaptador é hipotética e só vira real com o segundo adaptador concreto; começar a
  refatoração macro pelos pontos quentes do histórico e registrar em ADR as recusas com motivo.
- **Onde:** duas linhas na tabela "Heurísticas Rápidas de Decisão" + três parágrafos logo abaixo.
- **Ganho medido:** `tests/test_absorcao_2026_10_27.py` (critério YAGNI agora objetivo e verificável):
  vermelho antes, verde depois; 0 regressão.
- **Ficou de fora:** o vocabulário próprio da origem (deep modules, etc.) e o fluxo interativo dela.
