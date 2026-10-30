# Taxonomia erro → camada — casos de borda

A tabela do hub cobre o comum. Este documento cobre onde a classificação erra.

## 1. Matriz completa

| Classe de erro | Sinal típico | Camada | Ação | Escala ao humano? |
|---|---|---|---|---|
| Indisponibilidade do provedor | timeout, `503`, `502`, conexão recusada | 1 — disjuntor | abre após N falhas | só se todos os fallbacks abrirem |
| Erro interno do provedor | `500` sem corpo útil | 1 — disjuntor | abre após N falhas | idem |
| Rate limit de janela | `429` + `Retry-After` | 2 — cooldown | espera o valor informado | não |
| Rate limit sem dica | `429` sem header | 2 — cooldown | backoff exponencial | não |
| Credencial inválida | `401` | 2 — cooldown curto → **terminal** se repetir | 1 retry, depois terminal | **sim**, ao virar terminal |
| Permissão negada | `403` | 2 — cooldown → terminal | idem `401` | **sim** |
| Quota do modelo esgotada | `429`/`quota` citando o modelo | 3 — lockout | trava o par (especialista, modelo) | não, se houver fallback |
| Modelo inexistente | `404` no modelo | 3 — lockout | trava o par; corrige config | **sim** (é erro de configuração) |
| Contexto insuficiente | `context_length_exceeded` | 3 — lockout | escala para modelo de contexto maior | não |
| Crédito esgotado | `insufficient_credits` | **terminal** | para; não tenta | **sim, imediatamente** |
| Conta banida/suspensa | `banned`, `suspended` | **terminal** | para; não tenta | **sim, imediatamente** |
| Guardrail/política do provedor | `content_filter`, recusa | **nenhuma** | não é falha de infra — reformule ou escale | depende do conteúdo |
| Erro determinístico do próprio trabalho | arquivo não existe, teste falha, prompt inválido, JSON malformado | **nenhuma** | **não repita** — investigue | sim, após 1 tentativa |

## 2. Os três erros de classificação que mais custam

### (a) Abrir disjuntor por `429`
Sintoma: um especialista some do pipeline logo depois de uma rajada de uso.
Causa: `429` foi contado como falha sistêmica.
Custo: o especialista estava 100% saudável; o pipeline degradou sem necessidade e o humano é
acordado à toa.
Correção: `429` **nunca** conta para o contador do disjuntor. Vai para cooldown (2) ou lockout (3).

### (b) Retry em erro determinístico
Sintoma: o mesmo passo roda 5×, sempre com a mesma mensagem, queimando tokens.
Causa: a camada de retry não distingue "pode dar certo da próxima" de "vai falhar igual".
Custo: P3 direto — e pior, esconde a causa raiz atrás de "flakiness".
Correção: erro determinístico **não pertence a nenhuma camada**. Uma tentativa, depois
`error-investigator` ou escalada.

### (c) Terminal tratado como transitório
Sintoma: o orquestrador tenta a mesma credencial expirada indefinidamente, sem avisar ninguém.
Causa: `401` persistente escreveu `indisponivel_ate` em vez de marcar terminal.
Custo: o pipeline nunca completa e o humano só descobre no fim.
Correção: `401`/`403` que repete **promove para terminal** e escala. Terminal **nunca** é
sobrescrito por cooldown transitório.

## 3. Sinais de que o backoff está errado

| Sintoma | Diagnóstico |
|---|---|
| Espera muito maior que a janela real do provedor | Ignorou `Retry-After` e usou backoff local |
| Várias tentativas concorrentes multiplicando o cooldown | Falta guarda anti-manada: uma falha, um incremento |
| Nível de backoff nunca zera | Sucesso não está limpando `nivel_backoff`/`indisponivel_ate` |
| Todo mundo volta ao mesmo tempo depois de uma queda | Falta jitter — some ±20% aleatório à espera |

## 4. Formato do registro de transições

Uma linha JSONL por transição, em `_local-artifacts/resiliencia.jsonl`:

```json
{"ts":"2026-08-15T18:42:10Z","camada":"disjuntor","alvo":"engenheiro-seguranca","de":"FECHADO","para":"ABERTO","motivo":"3 timeouts consecutivos","modelo":null}
{"ts":"2026-08-15T18:47:10Z","camada":"disjuntor","alvo":"engenheiro-seguranca","de":"ABERTO","para":"MEIO_ABERTO","motivo":"janela de reset venceu (leitura preguiçosa)","modelo":null}
{"ts":"2026-08-15T18:47:31Z","camada":"lockout","alvo":"arquiteto-cloud-aws","de":"livre","para":"travado","motivo":"quota esgotada","modelo":"opus"}
```

Três usos concretos do arquivo:

1. **Evidência no relatório final** — "o pipeline rodou degradado das 18:42 às 18:47" é
   informação que o humano precisa antes de aprovar o GATE 2.
2. **Calibração dos limiares** — os números da tabela do hub são ponto de partida. Depois de
   ~50 transições reais, ajuste com dados, não com palpite (regra-zero do V3).
3. **Detecção de padrão** — o mesmo especialista abrindo disjuntor toda semana não é problema de
   resiliência, é bug. Abra o achado.

## 5. Interação com `roteamento-modelo-adaptativo`

As duas skills compartilham estado, em direção única:

```txt
resiliencia-agente  ──(saúde: FECHADO=1.0 · MEIO_ABERTO=0.5 · ABERTO=0.0)──▶  roteamento
```

O roteador **lê** a saúde como fator de score (peso mais alto da função) e **nunca** escreve nela.
E lê sempre via `status()`, nunca o campo cru — senão um especialista já recuperado continua
com score 0 para sempre. Esse é o mesmo bug da seção 6 do hub, visto do outro lado.

## 6. Fork Rápido `retry or stop` (`retry once` | `switch tool` | `stop + ask`)

> **Procedência:** absorvido da camada `JEV · fork layer` do diagrama operacional de `@thedelost` (`CLAUDE CODE REGISTRY TIP`, out/2026). Implementação executável compartilhada em `../../roteamento-modelo-adaptativo/scripts/jev_fork_layer.py`.

Quando uma chamada de ferramenta ou passo de subagente falha, o interceptador avalia a distribuição de probabilidades entre três ações de contenção:

| Saída do Fork | Quando dispara (`sharp -> code`, 0 tokens LLM) | Por que evita desperdício |
|---|---|---|
| **`retry once`** | Falha transitória (`429`, `503`, `rate_limit`) na **primeira ocorrência** (`tentativa == 0`) sem tool substituta imediata. | Limita o retry a uma única repetição controlada sob backoff, sem abrir loop aberto. |
| **`switch tool`** | Falha na tentativa $\ge 1$ quando o passo possui **ferramenta alternativa** capaz de cumprir o mesmo contrato (ex.: API secundária, busca local vs remota). | Contorna gargalo local da ferramenta sem repetir a chamada que acabou de falhar. |
| **`stop + ask`** | Erro determinístico (`arquivo_nao_existe`, `teste_falhou`, `json_malformado`), **bloqueio por hook determinístico (`exit 2` em `PreToolUse`)**, estado terminal (`credito_esgotado`, `credencial_expirada`) ou limite de tentativas atingido (`tentativa >= 2`). | Faz o agente **parar nas regras do sistema** (`exit 2 blocks the call`) ou confirmar com o humano, zerando loops de teimosia. |

Se o sintoma for ambíguo (probabilidade dividida, ex.: $p \in [0,46; 0,61]$ — regime **`split`**), o fork escala uma única consulta curta ao modelo (`Sonnet`) para classificar antes de agir.
