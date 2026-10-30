# Referência — As 5 métricas do Squad AI Benchmark

> Parte da skill `squad-benchmark`. Carregue sob demanda ao registrar uma nova
> medição ou ao calibrar/discutir qualquer fórmula. Hub: [`../SKILL.md`](../SKILL.md).

Cada métrica guarda **dois valores**:

- `valor_bruto` — o número na sua unidade natural (%, pts, multiplicador x).
- `valor_normalizado` — o mesmo valor projetado na escala comum **0–100** do gráfico.

As metas e o baseline "sem Squad AI" ficam na tabela `metas` (semeada no `init`).
As fórmulas de normalização estão reproduzidas no rodapé do dashboard (transparência
do método). **C e E podem ser refinadas depois sem migração de schema** — só muda o
cálculo do `valor_normalizado` das medições futuras.

---

## A — Entregas com menos retrabalho

- **O que mede:** % de entregas aceitas **sem retrabalho** no período (uma entrega que
  precisou de correção pós-aceite conta contra).
- **Unidade bruta:** `%` (0–100).
- **Normalização:** direto — o bruto já está na escala 0–100.
- **Meta:** ≥ **90**.
- **Protocolo:** `A = entregas_aceitas_sem_retrabalho / entregas_totais × 100`, medido
  sobre a janela do marco (ex.: desde o marco anterior). Fonte: histórico de PRs/tarefas.

## B — Redução de custos/tokens

- **O que mede:** % de redução de custo/tokens **vs. o baseline sem Squad AI** (fazer a
  mesma tarefa manualmente / sem o ecossistema).
- **Unidade bruta:** `%` (0–100).
- **Normalização:** `min(100, valor_bruto)` — teto em 100 (redução > 100% não faz sentido).
- **Meta:** ≥ **60**.
- **Baseline sem Squad AI:** o custo/tokens de referência é registrado uma vez; o marco
  guarda a **% de redução** já calculada. `B = (custo_baseline − custo_com_squad) / custo_baseline × 100`.

## C — Qualidade do código e testes

- **O que mede:** score composto **0–100** de qualidade. Pode vir das skills `review` /
  `clean-code-craftsman` (cobertura de testes + code smells + critérios dos OAs).
- **Unidade bruta:** `pts` (0–100).
- **Normalização:** direto.
- **Meta:** ≥ **85**.
- **Fórmula sugerida (refinável):**
  ```
  C = 0.45 × cobertura_testes(%)              # 0–100
    + 0.35 × (100 − densidade_smells_norm)    # menos smells = mais pontos
    + 0.20 × criterios_OA_atendidos(%)        # % de critérios de aceite verdes
  ```
  Os pesos são um ponto de partida; recalibre conforme a maturidade da suíte e registre
  a mudança aqui. Como é `direto`, mudar a fórmula não exige migração de schema.

## D — Velocidade de entrega

- **O que mede:** **multiplicador x** de velocidade vs. o baseline manual sem Squad AI
  (ex.: 5.2x = entregou 5,2 vezes mais rápido).
- **Unidade bruta:** `x` (multiplicador, > 0).
- **Normalização:** `min(100, valor/7 × 100)` — **7x é a meta e vale 100**. Ex.: 5.2x →
  `5.2/7×100 = 74.3`; 7x → 100; 8x → 100 (teto).
- **Meta:** **7x** (= 100 normalizado). É a única métrica cuja meta normalizada é 100 —
  por isso a **linha de referência pontilhada em 100** no gráfico.
- **Baseline sem Squad AI:** 1x (execução manual). Registrado na tabela `metas`.

## E — Capacidade cognitiva do Cérebro (inspirado em AGI)

- **O que mede:** índice composto **0–100** do "Cérebro"/Vault do Squad AI — proxy da
  capacidade cognitiva do ecossistema.
- **Unidade bruta:** `pts` (0–100).
- **Normalização:** direto.
- **Meta:** ≥ **80**.
- **Fórmula sugerida (refinável):**
  ```
  E = 0.40 × skills_ativas_norm          # nº de skills ativas, normalizado a um teto
    + 0.30 × conexoes_vault_norm         # densidade de conexões no vault Obsidian
    + 0.30 × taxa_acerto_delegacao(%)    # % de tarefas delegadas concluídas com sucesso
  ```
  `*_norm` = valor projetado em 0–100 contra um teto de referência (ex.: 50 skills = 100).
  Recalibre os tetos conforme o Cérebro cresce e registre a mudança aqui.

---

## Resumo — metas e normalização (o que vai no rodapé do dashboard)

| Cód. | Meta bruta | Meta normalizada | Fórmula de normalização |
|------|-----------|------------------|-------------------------|
| A | ≥ 90 % | 90 | direto (já é 0–100) |
| B | ≥ 60 % | 60 | `min(100, valor_bruto)` |
| C | ≥ 85 pts | 85 | direto (já é 0–100) |
| D | 7x | 100 | `min(100, valor/7 × 100)` |
| E | ≥ 80 pts | 80 | direto (já é 0–100) |

> **% da meta atingida** (cards) = `valor_normalizado / meta_normalizada × 100`.
> Ex.: A com bruto 82 → `82/90 = 91,1%`. D com 5.2x → `74.3/100 = 74,3%`.

---

## Diagnóstico FinOps de Enxame — *Kept Output Ratio* e Eficiência de Elenco (v1.1.0)

> **Procedência:** protocolo de avaliação de enxames absorvido de `@thedelost` (out/2026): *"give the first team a job with an obvious finish line: one reviewed PR, one researched brief, one failing test turned green. then look at how much of that output you actually kept, and what it cost to produce. a bigger roster earns its place when it moves that number. the download is free. paying four agents to repeat the same investigation is not."*

Para evitar que o aumento do número de agentes infle a Métrica **E** (capacidade/catálogo) enquanto degrada silenciosamente **A** (retrabalho) e **B** (custo/tokens), audite três indicadores operacionais em tarefas com linha de chegada objetiva (1 PR revisado, 1 especificação pesquisada, 1 teste falho tornado verde):

1. **Taxa de Output Mantido (*Kept Output Ratio* — alimenta A):**
   ```txt
   kept_output_pct = (artefatos_ou_linhas_mantidas_no_commit_final / total_produzido_pelos_agentes) × 100
   ```
   Se 4 subagentes produzem 2.000 linhas de análise/código e apenas 250 linhas sobrevivem no commit final (`12,5%`), 87,5% dos tokens gerados foram descarte.
2. **Custo por Output Mantido (alimenta B):**
   ```txt
   custo_por_entrega_mantida = custo_total_usd_da_corrida / entregas_mantidas_sem_retrabalho
   ```
3. **Índice de Investigação Repetida (*Duplicate Investigation Count*):**
   Número de vezes que $\ge 2$ agentes na mesma corrida leram os mesmos arquivos ou repetiram a mesma busca por falta de handoff estruturado ou de leitura prévia do ledger (`research.md`). Meta obrigatória: **`0` repetições**.

**Regra de Justificativa de Elenco (*Roster Justification Rule*):** adicionar um novo subagente a uma rotina ou pipeline só se mantém se elevar `kept_output_pct` (Métrica A) ou reduzir `custo_por_entrega_mantida` (Métrica B) em relação ao time menor.
