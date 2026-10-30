# Procedência — verificacao-loop

## v2.1.0 (2026-10-26) — Regra da prova + pulados não contam como verdes

- **Fonte:** levnikolaevich/claude-code-skills, `plugins/quality-assurance-suite/skills/ln-54-codebase-auditor/SKILL.md`
  @ `bb2f0cbf343dd31acdf10e3d6af7064afd8254c7` (2026-10-26) — licença **MIT** (LICENSE conferido).
- **O que entrou (reescrito, sem copiar texto):** estados de evidência por item (provado / descartado /
  não provado / pendente), lista do que não vale como prova (exit 0 sem testes, skip/quarentena,
  auto-relato, evidência anterior à edição) e invalidação seletiva da evidência por estado da árvore.
- **Código:** `scripts/quality/gate_runner.py::gate_testes` passou a ler `skipped` do Surefire —
  só os executados contam; tudo pulado = BLOCKER; pulados > `testes.pulados_max` (padrão 0) = MAJOR.
- **Ganho medido:** `tests/test_gate_runner.py` 54 → 57 testes; os 3 novos eram vermelhos no código
  anterior (suíte com 5/5 testes pulados saía PASS "5 testes verdes") e passam agora; 0 regressão.
- **Ficou de fora:** o preâmbulo "execution contract" da suíte de origem e o restante do auditor.
