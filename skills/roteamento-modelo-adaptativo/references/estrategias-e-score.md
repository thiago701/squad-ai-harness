# Estratégias e função de score — detalhe operável

## 1. Função de score

```txt
score(candidato) = SOMA( peso_i * fator_i )    com SOMA(peso_i) = 1,0

se saude == 0,0 (disjuntor ABERTO)  →  score = 0  (candidato eliminado, não descontado)
se candidato < piso da fase          →  candidato eliminado
```

| Fator | Peso | Normalização |
|---|---:|---|
| `saude` | 0,35 | `FECHADO`=1,0 · `MEIO_ABERTO`=0,5 · `ABERTO`=0,0 |
| `fitTarefa` | 0,25 | 1,0 = modelo alvo da fase · 0,6 = um degrau acima · 0,3 = um degrau abaixo (só se o piso permitir) |
| `custoInv` | 0,15 | `1 − (custo_candidato / custo_max_do_pool)`; custo misto = 60% entrada + 40% saída |
| `contexto` | 0,10 | `1,0` se o payload cabe com ≥30% de folga · `0,5` com <30% · `0,0` se não cabe |
| `estabilidade` | 0,10 | `1 − taxa_de_erro_recente` (janela de 20 chamadas) |
| `latenciaInv` | 0,05 | `1 − (p95_candidato / p95_max_do_pool)` |

**Renormalização:** se você customizar pesos, divida cada um pela soma. Um peso solto que faz a
soma dar 1,3 transforma o score em número sem significado comparável entre pools.

**Empate (diferença < 0,05):** vence o mais barato. É o único ponto em que P3 decide sozinho —
e só porque P1 e P2 já empataram.

### Perfis de peso por tier

| Tier | Ajuste sobre os pesos base |
|---|---|
| *(nenhum)* | pesos base acima |
| `:fast` | `latenciaInv` 0,05→0,20; `custoInv` 0,15→0,05; resto renormalizado |
| `:cheap` | `custoInv` 0,15→0,35; `latenciaInv`→0,02; **piso da fase continua valendo** |
| `:pro` | `fitTarefa` 0,25→0,40; `custoInv`→0,02 |
| `:reliable` | `saude` 0,35→0,45; `estabilidade` 0,10→0,20 |

## 2. As seis estratégias

### `prioridade` (padrão)
Lista ordenada, drena o primeiro antes de ir ao próximo. Previsível, depurável, barata. Use como
padrão e só troque com motivo.

### `ultimo-bom` (padrão de sessão)
Aderência ao último caminho que deu certo para aquele especialista **nesta sessão**. Preserva
cache de prompt e coerência de raciocínio. Cede quando a saúde cai, o piso muda ou o contexto
estoura — nunca por diferença marginal de preço.

### `custo-otimizado`
Minimiza custo por chamada. Legítimo em: bateria de benchmark, varredura ampla de arquivos,
classificação em lote, exploração de repositório. **Proibido** em fase com piso `opus`.

### `contexto-otimizado`
Escolhe pela janela de contexto quando o payload é grande. Evita o pior desperdício possível:
mandar um payload de 200k para um modelo de 128k, falhar, e pagar de novo no fallback.

### `painel` (fan-out + juiz)
2–3 especialistas em paralelo sobre a mesma questão + `tech-lead-review` sintetizando um veredito.

**Critério de disparo — só quando o custo de errar supera o custo de perguntar:**

| Dispara | Não dispara |
|---|---|
| Decisão arquitetural irreversível (escolha de stack, modelo de dados, contrato público) | Dúvida de sintaxe ou estilo |
| Achado 🔴 de segurança com divergência entre especialistas | Achado 🟡/🔵 |
| Trade-off P1×P2 sem resposta óbvia | Qualquer coisa que a tabela já resolve |
| Estimativa que vai virar compromisso externo | Tarefa `trivial`/`small` |

Custo real: **~3× tokens + latência do mais lento**. Use com parcimônia — mas use. É a arbitragem
que o `AGENTS.md` já pede ("consenso entre especialistas"), agora com nome, critério e preço
declarado. Um painel que roda em toda decisão é *agent soup* com etiqueta nova (N7 do `RULES.md`).

### `encadeado`
Saída de um alimenta o próximo (spec → arquitetura → código → teste). A Squad **já faz isso** no
`squad-pipeline`; entra na lista para que o vocabulário de roteamento cubra o que já existe, não
para reimplementar.

## 3. As treze estratégias descartadas — e por quê

`fill-first` · `weighted` · `round-robin` · `p2c` · `least-used` · `random` · `strict-random` ·
`headroom` · `reset-window` · `reset-aware` · `context-relay` · `cache-optimized` · `auto`

Todas resolvem o mesmo problema: **balancear carga entre muitas credenciais equivalentes**. A
Squad tem um punhado de modelos, não centenas de chaves. Importar esse maquinário aqui seria
complexidade acidental sem problema correspondente — o que o `arquiteto-minimalista` chama pelo
nome e o P1 proíbe.

Se um dia a Squad rodar dezenas de contas em paralelo, `p2c` e `headroom` são os primeiros dois a
reconsiderar.

## 4. Formato do registro de decisão

```json
{"ts":"2026-08-15T18:40:02Z","canal":"squad/design:pro","fase":"DESIGN","especialista":"arquiteto-minimalista","modelo":"opus","score":0.87,"estrategia":"ultimo-bom","piso":"opus","preteridos":[{"modelo":"sonnet","motivo":"abaixo do piso"},{"modelo":"haiku","motivo":"abaixo do piso"}],"tokens_estimados":12400}
```

Agregações que esse arquivo habilita:

| Pergunta | Como responder |
|---|---|
| Quanto custou cada fase nesta sessão? | soma de `tokens_estimados` por `fase` |
| A aderência está segurando ou trocando demais? | % de decisões com `estrategia=ultimo-bom` |
| Algum piso foi furado? | `modelo` abaixo do `piso` — deve ser **zero**, sempre |
| Os pesos estão calibrados? | correlação entre `score` alto e retrabalho baixo |
| Vale ligar `painel`? | custo de retrabalho das decisões arquiteturais × 3× do painel |

A última linha é a mais importante: **os pesos da §1 são ponto de partida, não verdade**. Depois
de ~100 decisões registradas, recalibre com os dados. Congelar palpite como se fosse medição foi
exatamente o erro que a série V1–V2 dos benchmarks cometeu — e que a V3 corrigiu com a regra-zero.

## 5. JEV Fork Layer — Corte Calibrado `sharp` vs `split` (v1.1.0)

> **Procedência:** padrão de bifurcação `JEV · fork layer` absorvido e reescrito a partir do diagrama operacional de `@thedelost` (`CLAUDE CODE REGISTRY TIP · 10 REPOS · ONE .CLAUDE FOLDER`, out/2026). Implementação stdlib em `../scripts/jev_fork_layer.py`.

Em vez de consumir chamadas de LLM para cada micro-decisão de orquestração, o `jev_fork_layer.py` avalia a distribuição de probabilidades das opções candidatas em três bifurcações (`which agent`, `which skill`, `retry or stop`):

| Regime | Condição matemática | Quem executa | Custo de LLM | Exemplo de log |
|---|---|---|---|---|
| **`sharp`** | $p_1 \ge 0,75$ **e** $(p_1 - p_2) \ge 0,20$ | **`code`** (determinístico) | **0 tokens** | `jev: which agent    -> reviewer     p=0.94 sharp -> code` |
| **`split`** | $p_1 < 0,75$ **ou** $(p_1 - p_2) < 0,20$ | **`sonnet 5.5`** (ou piso da fase) | 1 chamada curta de desempate | `jev: which skill    -> review-pr    p=0.54 split -> sonnet 5.5` |

### Tripla de contenção no fork `retry or stop`
Quando uma ferramenta ou passo falha, o fork `retry or stop` decide entre três ações exclusivas:
1. **`retry once`** ($p \approx 0,86$ `sharp -> code`): falha transitória (`429`, `503`) na primeira tentativa (`tentativa == 0`).
2. **`switch tool`** ($p \approx 0,90$ `sharp -> code`): falha de ferramenta na tentativa $\ge 1$ quando existe ferramenta alternativa equivalente registrada.
3. **`stop + ask`** ($p \approx 0,97$ `sharp -> code`): erro determinístico (`teste_falhou`, `arquivo_nao_existe`, `exit_2_hook`), estado terminal (`credito_esgotado`, `credencial_expirada`) ou limite de tentativas atingido (`tentativa >= 2`). Para imediatamente e confirma com o humano.
