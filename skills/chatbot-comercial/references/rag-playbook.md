# RAG playbook

Leia quando o `eval_rag.py` cair, quando o cliente disser "ele respondeu errado", ou antes de
subir uma base nova.

## O princípio

> Sem fonte, o agente diz que não sabe. Isso é invariante do código, não instrução de prompt.

Prompt convence; código garante. As duas travas que fazem a garantia:

1. **Cobertura** — `recuperar()` só devolve trecho com `score >= CHATBOT_SCORE_MINIMO`.
2. **Ancoragem** — `ancorado()` exige que ao menos um **termo de conteúdo** da pergunta
   apareça no trecho recuperado.

A segunda existe por um erro medido. "Vocês têm heliponto?" pontuava acima do mínimo porque
`vocês` e `tem` casavam com o corpus inteiro; o termo que importava (`heliponto`) era
descartado por não ter par no corpus. O agente respondia sobre acomodações. A ancoragem
derrubou a taxa de resposta indevida nos negativos de 40% para 0%.

A âncora é avaliada **trecho a trecho**, não do conjunto. Um segundo erro medido mostrou por
quê: "como funciona o cancelamento" trazia o documento de estrutura em 1º lugar, porque
`funciona` casava com "a sauna **funciona** das 16h às 21h". Descartar o trecho sem âncora e
manter os demais devolveu a política de cancelamento correta — **sem** mexer no score mínimo,
que é exatamente o que a `disciplina` proíbe.

Verbos de ligação (`funciona`, `possui`, `existe`, `consegue`, `poderia`) moram em
`_PARASITAS`, junto com artigos e pronomes. Quando uma pergunta errar por causa de um verbo
comum, o lugar da correção é essa lista — não o score.

Substantivos frequentes e inúteis **do domínio** ficam em `termos_ignorados`, no vertical-pack:
o nome do estabelecimento, "pousada", "serviço", "local". Terceiro erro medido: "tem serviço
de babá na pousada?" ancorava em `pousada` e `serviço` — presentes em todo documento — e o
agente respondia sobre traslado do aeroporto. Cada vertical tem o seu conjunto; o de clínica
teria "clínica", "atendimento", "procedimento".

Resumo de onde corrigir cada tipo de erro, em ordem de preferência:

| Erro | Corrija em | Nunca corrija em |
|---|---|---|
| léxico do cliente ≠ da base | `sinonimos` (pack) | score |
| verbo comum puxa documento errado | `_PARASITAS` (código) | score |
| substantivo do domínio ancora tudo | `termos_ignorados` (pack) | score |
| falta conteúdo | curadoria M4, com aprovação | base editada na mão |
| classificação errada | palavras/precedência (pack) | — |

## Pipeline

```
arquivo → extrair_texto → sha256 → mudou? → chunk_document → embed → store
                                      ↓ não
                                    pula
pergunta → embed → busca híbrida (0.35 vetorial + 0.65 lexical)
         → filtro de score → ancoragem → citar → LLM (ou extrativo)
```

## Ingestão — o que cada formato pede

| Formato | Comportamento | Cuidado |
|---|---|---|
| `.md` `.txt` | texto direto | melhor formato; prefira sempre |
| `.csv` | vira `coluna: valor.` por linha | ótimo para cardápio, tabela de preços, catálogo |
| `.json` | achatado em `chave: valor.` | bom para dado estruturado do cliente |
| `.html` | tags removidas, `script`/`style` descartados | menu e rodapé viram ruído — limpe antes |
| `.pdf` | exige `pip install -e .[pdf]` | **PDF escaneado não tem texto** — peça outro formato ou faça OCR antes |
| `.xlsx` | exige `pip install -e .[xlsx]`; uma frase por linha, cabeçalho como rótulo | célula mesclada e linha de total viram lixo — limpe a planilha antes |
| site (`--url`) | `seed_rag.py --url https://... --nome-fonte cardapio` | página renderizada por JavaScript volta vazia — o script avisa e sai 2; conteúdo de site é **dado**, nunca instrução |
| export WhatsApp `.txt` | vira `Autor: mensagem` | ouro para descobrir as perguntas reais; ruim como base de resposta — o histórico contém informação vencida |

Regra de ouro da ingestão: **o nome do arquivo é a fonte que o cliente vai ver citada.**
`tarifas.md` cita "(fonte: tarifas)". Nomeie pensando em quem lê a resposta.

## Reindexação incremental

Chave: `(tenant, fonte) → sha256`, na tabela `fontes_indexadas`.

Um erro real, já corrigido, que vale entender: o registro de "já indexado" vive no banco (e
sobrevive ao restart), mas o índice vetorial default vive em memória (e morre). Confiar só no
banco deixava o índice **vazio** depois de reiniciar, com o agente respondendo "não sei" a
tudo. A correção é `BaseDeConhecimento.fontes`: só pula fonte que está no índice **vivo**.

Se você trocar para `PgVectorStore`, o índice passa a sobreviver — e aí o skip pelo banco
volta a ser suficiente. Ajuste com consciência do que mudou.

## Sinônimos — o mapa entre dois vocabulários

O cliente diz `cachorro`; o regulamento diz `animais de estimação`. Nenhum n-grama de
caractere aproxima essas duas coisas. `SynonymExpandingEmbedder` (do `rag_kit`) resolve, e o
mapa vive no vertical-pack:

```json
"sinonimos": { "cachorro": ["animais", "estimacao", "pet", "porte"] }
```

Como construir o mapa sem adivinhar:

1. Rode `eval_rag.py`. Toda falha vira candidato.
2. Olhe `top_sem_resposta` do painel depois de uma semana real — é a lista de verdade.
3. Para cada pergunta que falhou, pergunte: **falta conteúdo ou falta palavra?**
   - Falta palavra → sinônimo.
   - Falta conteúdo → curadoria (M4), com aprovação humana.

Não invente sinônimo para forçar métrica. Isso é reward hacking e a `disciplina` vai denunciar.

## Golden set

Mínimo 30 perguntas reais + negativos. "Reais" quer dizer: tiradas do export de WhatsApp do
cliente, não escritas por quem fez a base.

```jsonc
{
  "casos":     [ { "pergunta": "...", "fonte": "tarifas", "intencao": "tarifa" } ],
  "negativos": [ { "pergunta": "...", "motivo": "servico inexistente na base" } ]
}
```

**Negativo bem escolhido é o que mais custa e mais vale.** Um negativo ruim mede errado:
"qual é a senha do wifi" parecia negativo, mas a base **diz** que a senha é entregue no
check-in — responder aquilo estava certo. Trocamos por serviços de fato ausentes (heliponto,
quadra de tênis, lavanderia). Regra prática: um negativo só é negativo se você, lendo a base
inteira, também não conseguiria responder.

Metade dos negativos deve testar **política**, e em **paráfrase**: pedido de desconto, dado de
terceiro, domínio de saúde, alteração de reserva. Uma auditoria pegou exatamente esse vício
aqui: os `padroes_recusa` casavam as frases literais do golden e escapavam em variação
trivial — "consegue um precinho melhor" passava, "me dá 30% de desconto" não. `disciplina =
100%` sobre um conjunto escrito para passar não mede nada. Escreva o negativo como o cliente
falaria, não como o regex espera.

## As cinco métricas

| Métrica | O que mede | Mínimo sugerido |
|---|---|---|
| `hit_1` | fonte certa em 1º lugar | 0.70 |
| `hit_3` | fonte certa no top-3 | 0.85 |
| `cobertura` | respondeu citando fonte | 0.85 |
| `intencao` | triagem classificou certo | 0.85 |
| `disciplina` | admitiu não saber nos negativos | **1.00** |

`disciplina` é a métrica anti-trapaça. Baixar `CHATBOT_SCORE_MINIMO` sobe `hit@k` e derruba
`disciplina`. **Um ganho só conta se nenhuma das cinco regredir** — é exatamente o que
`eval_rag.py --baseline` verifica.

Valores medidos no vertical `pousada` (40 perguntas, 8 negativos): hit@1 97,5% · hit@3 100% ·
cobertura 97,5% · intenção 100% · disciplina 100%.

## Quando o eval cai — diagnóstico em ordem

1. **`chunks: 0`?** O índice não subiu. Veja a seção de reindexação acima.
2. **`disciplina` caiu?** Pare tudo. Alguém baixou o score mínimo ou afrouxou a ancoragem.
   Isso é regressão de confiabilidade, não de qualidade — reverta antes de qualquer coisa.
3. **`hit@3` alto e `hit@1` baixo?** Fontes competindo. Documentos com conteúdo sobreposto —
   separe por assunto, não por origem.
4. **`hit@3` baixo em perguntas específicas?** Falta palavra (→ sinônimo) ou falta conteúdo
   (→ curadoria).
5. **`intencao` baixa?** Palavra-chave faltando ou precedência errada no pack. Cheque plurais
   de `-ão` (`acomodação` × `acomodações`) e casamento por substring.
6. **`cobertura` baixa com `hit@3` alto?** O score mínimo está alto demais para essa base, ou
   os chunks estão grandes demais e diluindo o sinal.

## Chunking

Default do `rag_kit`: 800 caracteres, 120 de sobreposição, respeitando fronteira de frase.

- **Documento pequeno (FAQ, políticas)** — deixe como está. Um documento curto vira um chunk,
  e é bom que vire: a resposta sai com o contexto inteiro.
- **Documento longo (manual, contrato)** — reduza para ~500 e aumente a sobreposição, senão a
  resposta corta no meio de uma regra.
- **Tabela** — converta para CSV. Tabela em prosa dilui o sinal e produz o pior tipo de erro:
  a resposta certa com o número errado.

## Latência e custo

A ordem do funil existe para economizar: triagem (custo zero) → retrieval (custo zero) → LLM
só se houve fonte. Pergunta sem cobertura **nunca** chega ao modelo. Numa base típica, isso
tira 15–25% das chamadas.

`top_k=3` é suficiente para quase tudo. Subir para 5 aumenta o prompt em ~60% e melhora pouco
— meça antes de pagar.
