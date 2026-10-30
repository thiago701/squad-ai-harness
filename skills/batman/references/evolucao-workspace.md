# Evolução do Workspace — melhoria contínua do projeto, ciclo a ciclo

> O segundo dever do turno: **melhorar continuamente o projeto confiado** — código,
> testes, performance, documentação e estrutura — com passos pequenos, medidos e
> reversíveis (N2), priorizados por P1>P2>P3.

## 1. Fonte de trabalho (o que o turno melhora)

1. **Backlog do check-in** (`scheduler/logs/checkin-*.md`) — o que o humano deixou.
2. **Débitos catalogados** (`docs/relatorios/batman/debitos-*.md` dos turnos anteriores).
3. **Sinais do próprio workspace:** testes vermelhos, gates com achados, drift de
   registry, referências quebradas, complexidade crescente, códigos repetidos.
4. **Oportunidades JEV:** decisões repetitivas candidatas a decisão tipada.

## 2. Passo de melhoria (um por ciclo — pequeno e reversível)

```
1. SELECIONAR  — próximo item da fila por P1>P2>P3 (simplicidade primeiro)
2. BASELINAR   — medir o estado atual (teste verde? métrica? comportamento?)
3. MELHORAR    — mudança mínima com TDD (teste que falha → muda → verde)
4. EVIDENCIAR  — antes/depois: tempo, tokens, cobertura, nº de testes, diff
5. REGISTRAR   — journal + relatório matinal (o que, por quê, evidência)
6. AVALIAR     — regressões? gates verdes? senão, reverter (é N2, reversível)
```

Regra de ouro: **cada ciclo muda pouco e mede muito**. O turno inteiro soma muitos
passos pequenos — nunca um refactor épico de madrugada.

## 3. Saúde do workspace (medida a cada ciclo)

O runner mantém `tmp/batman/workspace-health-<data>.json` (temporário, gitignored):

```json
{"ts": "...", "ciclo": 3, "bateria_ok": 5, "bateria_falhas": 0,
 "mudancas_no_tree": 380, "itens_plano_pendentes": 2, "gatilhos_abertos": 1}
```

- **Saúde sobe** quando: bateria verde, itens do plano concluídos, mudanças com teste.
- **Saúde cai** quando: falhas na bateria, ociosidade, dívida nova sem teste.

## 4. Frentes permanentes de evolução (rotação automática)

Sem trabalho novo na fila, o ciclo roda estas frentes em rotação (cada uma gera
evidência nova, nunca repete cegamente):

1. **Testes** — gaps de cobertura, flakiness, asserts fracos (mutation em mente).
2. **Performance** — benchmarks determinísticos, tempos do próprio turno, hot paths.
3. **Qualidade estrutural** — auditoria, calistenia, defesa, registry, evals.
4. **Documentação** — README/CHANGELOG/WORKING-CONTEXT sincronizados com o disco.
5. **Dívida** — re-catalogar débitos e marcar resolvidos com evidência.

## 5. Limites (o que a evolução do workspace NUNCA faz)

- Nada de commit/push/merge/delete/deps novas/credenciais (N3 — sempre gated).
- Nada de "melhorar" sem teste ou medição (anti-teatro absoluto).
- Nada de mudar arquivo fora do workspace confiado ou fora da allow-list.
- Regressão em qualquer gate → **reverte a própria mudança** e registra o negativo.
