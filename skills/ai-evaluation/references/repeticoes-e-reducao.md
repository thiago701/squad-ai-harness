# Repetições e redução de notas — saída não determinística

> Procedência: técnica observada nos *score reducers* `pass_at`, `pass_k` e `majority` do
> [UKGovernmentBEIS/inspect_ai @ ec6211f](https://github.com/UKGovernmentBEIS/inspect_ai/blob/ec6211f9dbe9305d3803ff668dbf261686cdd2ef/src/inspect_ai/scorer/_reducer/reducer.py)
> (licença MIT, 3k★, commit 16/10/2026) e na métrica pass^k do τ-bench. Reescrita com nossas
> palavras; nenhum código copiado. Eval: `evals/eval_repeticoes.py`.

## Quando repetir

Seed fixa (§3 do SKILL.md) só vale quando o provedor honra a seed. Agente com ferramentas, LLM
com temperatura > 0 ou API que ignora seed é **não determinístico**: rode **k ≥ 3 repetições**
(épocas) por caso, todas registradas na telemetria com `epoca: 1..k`. Custo cresce k×: use o
eval-set rápido (N ≥ 30) para as repetições e o completo só no aceite final.

## Os dois estimadores

Com **n** repetições de um caso e **c** acertos:

| Métrica | Pergunta | Estimador sem viés |
|---|---|---|
| **pass@k** | "em k tentativas, acerta pelo menos uma?" — *capacidade* | `1 − C(n−c, k) / C(n, k)` (1,0 se n−c < k) |
| **pass^k** | "em k tentativas, acerta todas?" — *confiabilidade* | `C(c, k) / C(n, k)` |

Exemplo: n = 10, c = 7, k = 3 → pass@3 = 0,992 · pass^3 = 0,292. O atalho `p**k` daria
0,343 — superestima a confiabilidade justamente quando n é pequeno. Reporte n, c e k ao lado.

**Qual gatilha decisão:** agente/automação que o usuário roda uma vez → gate em **pass^k**.
Geração com reranking ou humano escolhendo entre k saídas → pass@k. Nunca troque a métrica
depois de ver o número (regra de §7: decisão definida antes de medir).

## Repetição sem nota

Repetição que estourou timeout, quebrou o parser ou não recebeu nota do juiz **não** é zero
(contaminaria a qualidade com falha de infraestrutura) e **não** é descartada em silêncio (o
caso viraria "100%" com 1 de 3 execuções). Regra: se sobrarem menos de k repetições pontuadas,
o caso fica **indefinido** — sai do numerador e do denominador, e a contagem de indefinidos
entra no scorecard como linha própria. Taxa de indefinidos > 5% bloqueia a leitura do resultado.

## Painel de juízes (LLM-as-judge ou humanos)

Com vários juízes por item, use **maioria estrita**: um valor vence só com mais da metade dos
votos. A **abstenção conta no denominador** (juiz que falhou retém o voto, não baixa a régua).
Sem maioria → item **sem nota**, re-julgado ou descartado como em §5 do SKILL.md — nunca
desempate pela ordem em que os juízes foram declarados.

## Confiabilidade do painel (flip_rate e entropia)

O veredito acima diz **o que** o painel decidiu; ele não diz **o quanto** o painel concorda.
Um 2×1 e um 3×0 dão o mesmo veredito, mas o primeiro vira com a troca de um único juiz.
Reporte, por item, ao lado do veredito:

- **Votos válidos** e **abstenções**. A abstenção fica fora das métricas abaixo e é
  contada à parte (no veredito ela continua no denominador, como na seção anterior).
- **flip_rate** = `1 − max(passa, não_passa) / válidos`, com `passa = #(nota ≥ limiar)`.
  Vai de 0 (unânime) a 0,5 (empate).
- **Entropia do resultado** = `−Σ p·log2 p` sobre as duas contagens (ignora contagem zero).
  Vai de 0 a 1 bit.
- **Desvio-padrão populacional** das notas válidas (0 com um só voto).

Exemplo: notas 0,2 · 0,7 · 0,9 com limiar 0,5 → veredito "passa" (2 de 3), flip_rate = 0,333,
entropia = 0,918 bit. O mesmo veredito com 0,8 · 0,7 · 0,9 tem flip_rate 0.

Use as duas métricas para priorizar re-julgamento e avaliação humana (§5 do SKILL.md): itens
com flip_rate alto são onde o juiz é menos confiável, não onde o modelo é pior.

**Armadilha:** o mesmo juiz repetido com temperatura 0 tende a repetir a nota, então flip_rate 0
não prova estabilidade — só prova determinismo. Para medir estabilidade de um juiz único, repita
com temperatura > 0 ou use juízes diferentes.

Fonte: técnica reescrita a partir de truera/trulens 2.16.0 (`src/feedback/trulens/feedback/jury.py`,
MIT, commit `a7f242b`). Divergência consciente: o TruLens descarta o voto do juiz que falhou no
próprio veredito; a Squad mantém a abstenção no denominador do veredito e só a exclui das
métricas de confiabilidade.
