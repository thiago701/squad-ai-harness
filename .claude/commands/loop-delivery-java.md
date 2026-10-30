---
description: Roda o loop delivery-java (loops/delivery-java-loop.md) — ciclo gated de melhoria das entregas Java com benchmark honesto (metas ≥10% em tokens, retrabalho e qualidade), sem commit automático.
argument-hint: "[opcional: eixo-alvo 'tokens'|'retrabalho'|'qualidade', ou modo 'coleta'|'ciclo'. Vazio = gatilho interno decide]"
origin: debate-fundacao-2026-07-03
---

Execute o loop especificado em `loops/delivery-java-loop.md`.
Leia esse documento primeiro e siga os passos da volta exatamente. A régua de medição é
`loops/delivery-java/benchmark-protocolo-v1.md` — ela é BENCHMARK: nenhum candidato pode
alterá-la (mudança de régua = PR humano separado benchmark-vN).

Pedido do usuário (eixo-alvo/modo opcional): **$ARGUMENTS**

Resumo do que rodar:
1. Gatilho interno: leia `loops/delivery-java/_log-ciclos.md`. F0 pendente → modo F0
   (montar PR benchmark-v1 + checklist §9 do protocolo e PARAR no gate humano). Sem F0
   concluída não existe ciclo. Se F0 ok: rode ciclo só se ≥14 dias desde o último OU ≥5
   entregas reais instrumentadas; senão registre no-op de 1 linha e pare.
2. Ciclo (E1–E9): check de instrumento fail-closed → coleta/rollouts dev → ledger de ralos
   (0 tokens) + blame-diagnóstico → minilote de ≤3 edições (≤90 linhas) em branch
   `loop/cand-NNN` → dev-check (banda + dominância) → held-out selado + braço de controle
   contemporâneo → crítica adversarial em contexto limpo → montar PR com evidence pack →
   limpeza + pré-registro hasheado do próximo ciclo.
3. Delegue papéis aos agentes: `loop-medidor-instrumento` (E1/medições),
   `loop-avaliador-heldout` (ciclo 0, E6, cunhagem cega), `loop-critico-adversarial` (E7).
   Executor = squad-pipeline inalterado; otimizador nunca vê held-out.
4. Registre tudo em `docs/relatorios/benchmarks/loop-v1/*.jsonl` (schemas §8 do protocolo)
   e appenda a seção do ciclo em `loops/delivery-java/_log-ciclos.md`.

Condições de parada: vitória (≥10% real nos 3 eixos, líquido, confirmado em tarefa virgem
K=5, ratificado por humano); platô (3 ciclos sem aceite); 2 NEGATIVAs ou 2 leakages em 6
ciclos = suspensão; 2 INVÁLIDO-INSTRUMENTO seguidos = refazer F0; teto por ciclo = ≤18
rollouts candidato + 6 controle + ≤150k overhead (estouro aborta o ciclo, nunca vira
sucesso); 6 ciclos sem vitória encerram o programa.
**Nunca commite, mergeie ou faça push automaticamente** — candidatos vivem em branch
`loop/cand-NNN` e só entram por PR aprovado pelo humano (princípio gated da Squad AI).
