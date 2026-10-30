# Auditoria de saúde do eval — antes de confiar no número

> Referência da skill `ai-evaluation`. Procedência: técnica de `anthropics/skills`
> (`skills/claude-api/shared/evals/eval-audit.md`, Apache-2.0), reescrita e adaptada.

Um eval quebrado produz números com cara de confiança apontando na direção errada — e otimizar
em cima dele só multiplica o erro. Regra prática: o resultado mais surpreendente de uma rodada
quase sempre é bug do eval, não fato sobre o modelo. Rode esta auditoria **uma vez ao construir**
o eval (cada item vira requisito de construção) e **de novo antes da primeira rodada paga** e antes
de iterar sobre ele. Pré-requisito: o eval roda de ponta a ponta em poucos casos (ou existe um
arquivo de resultados recente); muita "discussão de qualidade" é sobre código que nem executa.

## 1. Os cinco blocos

| Bloco | Pergunta | Falha típica |
|---|---|---|
| Desenho das tarefas | Os casos estão certos e distinguem os sistemas comparados? | critério ambíguo, gabarito errado, resposta decorável |
| Desenho do harness | O código em volta da chamada ao modelo é neutro? | falha de infra contada como falha do modelo |
| Higiene de métricas | Custo e latência refletem o modelo, não a instalação? | tokens estimados, cache morno × frio, retry na latência |
| Desenho do avaliador | A função que dá a nota premia o que o enunciado pede? | rígido demais, leniente demais, burlável |
| Poder de detecção | Há sinal suficiente para a decisão em jogo? | ruído maior que o efeito buscado |

## 2. Casos — auditar em três degraus (o conjunto pode ter centenas)

1. **Script sobre tudo (barato, exaustivo):** taxa de duplicata exata e aproximada, balanço por
   rótulo/categoria, distribuição de tamanho de prompt e de resposta esperada, campos faltantes,
   linhas malformadas.
2. **Amostra estratificada para leitura atenta:** 20–50 casos (estratificar pela primeira tag; sem
   tag, aleatório). Peça que um humano leia alguns também — olho humano em caso cru acha o que
   checklist não acha.
3. **Auditor por caso com LLM** (só acima de poucas centenas): uma chamada isolada por caso, com
   veredito estruturado, e agregação por tipo de bandeira. **Pergunte antes** — custa N chamadas de
   modelo barato; informe a estimativa. Bandeiras úteis: ambíguo · gabarito suspeito · respondível
   de memória · avaliador estrito demais · avaliador leniente demais · burlável por atalho · outro.
   Veredito final por caso: `ok | revisar | quebrado`.

Verificações por caso (na amostra do degrau 2):

- **Critério sem ambiguidade:** dois especialistas independentes concordariam em passa/falha?
  Cuidado com os dois extremos — sub-especificado (formato ou arquivo de saída não dito) e
  super-especificado (o prompt é receita passo a passo, nada sobra para o modelo decidir).
- **Existe solução de referência e ela passa** no avaliador. Taxa 0% em todas as variantes é, mais
  vezes, caso quebrado do que caso difícil. Rode a referência pelo avaliador.
- **Gabarito correto:** re-derive de forma independente ~10 respostas esperadas. Benchmarks
  famosos carregam erro de rótulo; ele limita a nota máxima por motivo alheio ao modelo.
- **Origem do gabarito, registrada como tag:** escrito por humano · verificado por humano · saída
  de modelo (qual?). Se o gabarito é saída de modelo, a comparação por similaridade premia
  *imitar aquele modelo*; numa migração isso faz o incumbente vencer por construção. Nunca use a
  saída do modelo A como gabarito quando a pergunta é A × B — prefira rubrica ou juiz par a par.
- **Sem artefato de anotação:** um baseline trivial (constante, classe majoritária, tamanho do
  enunciado) não pode pontuar bem acima do acaso.
- **Sem vazamento de rótulo:** a resposta (ou paráfrase) não aparece em prompt, exemplos
  few-shot, system, descrição de ferramenta nem arquivo legível pelo agente — comum quando o
  few-shot foi montado copiando do conjunto-ouro.
- **Não decorável:** para entidades reais e nomeadas, o modelo acerta sem fazer o trabalho que o
  teste pretendia? Use sujeitos obscuros ou sintéticos quando o alvo é recuperação/uso de ferramenta.
- **Dificuldade vem do problema, não da redação:** enunciado ofuscado mede decifrar prompt.
- **Casos agênticos — sintoma, não investigação:** se o prompt já traz a linha de log, o teste que
  falha ou o arquivo, o eval mede leitura de dica. Dê o que um usuário plausivelmente relataria.
- **Distribuição e formato realistas:** compare uma amostra com o tráfego de produção, inclusive
  o formato (turno único não captura efeitos de contexto longo ou agente).
- **Margem de dificuldade:** baseline ~95%+ não discrimina no topo (a iteração vai mexer em
  custo/latência — diga isso de antemão); tudo perto de 0% é, em geral, bug de caso ou avaliador.
  Perto do teto, o que sobra é quirk de formato e desempate do avaliador: avise que os últimos
  pontos podem não medir mais o que o eval foi feito para medir.
- **Balanço de classes:** reporte o baseline da classe majoritária junto; havendo positivos e
  negativos, prefira precisão/revocação/especificidade a acurácia sozinha.
- **Cobertura nos dois sentidos:** quem testa "busca quando deve" também testa "não busca quando
  não deve" (idem recusa, ferramenta, escalonamento); senão o "sempre busca" tira 100%.
- **Uma capacidade por caso** quando o objetivo é diagnosticar *por que* variantes diferem.
- **Inversão como detector de fumaça:** variante claramente fraca vencendo a forte num item é,
  quase sempre, bug de caso/avaliador — olhe esses primeiro.
- **Validade temporal:** casos com fatos vivos (preços, datas, versões) têm gabarito datado; marque
  quando foi verificado pela última vez.
- **Casos gerados:** conserte o gerador e regenere; remendar item a item deixa os irmãos do bug.

## 3. Harness — o problema central é a conflação

Sempre que algo que **não é modelo** cai na mesma coluna de um resultado do modelo, o eval atribui
ao modelo o defeito do encanamento.

- **Falha de infra ≠ falha de modelo.** Timeout, 429/529 após retries, saída não parseável,
  resposta cortada em `max_tokens`, ferramenta que lançou exceção, avaliador que falhou:
  tentativa sem saída pontuável vai para um arquivo lateral de erros (`errors.jsonl`, com classe
  da falha), **nunca** para o de resultados — senão ocupa o slot `(caso, repetição)`, impede
  retomar e pontua infraestrutura como erro do modelo. Linha com saída carrega `stop_reason` e
  `status: truncated` quando cortou, para ser contada e exibida, mas não promediada como errada.
  Recusa é desfecho avaliado (métrica própria), não erro — recusa-zero e capacidade-zero não se somam.
- **"Sem resposta" ≠ "resposta negativa".** Em detecção, classificação e recuperação onde "nada"
  é resposta válida, o avaliador distingue *afirmar que não há* de *não produzir resposta*
  (vazio, crash, truncado). Se caem no mesmo rótulo, um runner que quebra em toda entrada empata
  com um que procurou direito e não achou nada.
- **Estado limpo e isolado por tentativa:** sem arquivos, linhas, histórico git, variáveis de
  ambiente ou cache de tentativa anterior. Estado compartilhado vaza efeito entre casos e torna o
  resultado dependente da ordem.
- **Ambiente completo e funcional:** pacote ausente que derruba todas as variantes mede o ambiente.
- **Preparação determinística:** semente fixa, iteração ordenada onde a ordem chega ao modelo ou ao
  avaliador, sem caminho dependente de relógio; use os parâmetros de amostragem de produção.
- **Limite de andaime ≠ limite de modelo:** ferramenta faltando, orçamento de passos curto, política
  de desistir cedo ou template que descarta contexto parecem incapacidade. Varie o andaime com o
  modelo fixo (ou o inverso) para atribuir à camada certa.
- **Limites de contexto/tokens não cortam caso algum:** compare o maior prompt e a maior resposta
  correta plausível com a janela e o `max_tokens`; corte aparece como `truncated`, não como erro.
- **Retry com backoff e jitter, e registrado:** 429 sem retry vira falha espúria (e pode fazer uma
  variante ou um horário parecer pior); retry sem espera multiplica custo sem aparecer. Limite de
  tentativas e contagem de tentativas por linha. Se o runner repete o *caso* inteiro, decida qual
  nota vale (padrão estrito: passou só no retry = falha) e some o uso de todas as tentativas.
- **Teto de tempo por caso, independente de vivacidade do stream:** conexão em streaming pode
  emitir keepalive para sempre e derrotar timer de inatividade. Estourou → vai para `errors.jsonl`
  como timeout, nunca como zero.
- **O modelo que serviu é o pedido:** leia `model` da *resposta* num caso-fumaça e afirme em toda
  chamada; divergência além da resolução documentada de alias falha a tentativa em voz alta. Nota
  servida pelo modelo errado não mede nada — cruze o agregado com o registro de uso/cobrança uma vez.
- **Config do eval = config de produção:** compare system, ferramentas, versão, amostragem e
  andaime; o runner chama o ponto de entrada real do app (reimplementar a chamada mede outra coisa).
- **Trajetórias completas salvas** por (caso, repetição): mensagens, chamadas e resultados de
  ferramenta, erros e as entradas/saídas do próprio avaliador. É o hábito de maior alavancagem para
  depurar uma nota surpreendente sem reexecutar.
- **Várias repetições com variância reportada** (ver `repeticoes-e-reducao.md`); diferença menor
  que a oscilação entre rodadas não significa nada.
- **Reprodutível no tempo:** dependências fixadas, conjunto e avaliador versionados juntos; nota de
  antes e depois de mudar o avaliador não é comparável.
- **Teste com oráculo e com nulo antes da primeira rodada cheia:** (a) as respostas de referência
  (ou variante que deveria dar ~100%) e (b) baseline nulo (saída vazia, constante, classe
  majoritária) pela pipeline inteira. Oráculo que não passa → harness ou avaliador quebrado; nulo
  que não falha → avaliador leniente. Dois runs, minutos, e pega a maioria dos erros de fiação.

## 4. Higiene de métricas

- **Tokens vêm da API** (`usage`: entrada, saída, leitura e escrita de cache por linha), não de
  estimativa por tamanho de string — estimativa é capaz de inverter uma comparação de custo.
- **Custo derivado dos tokens gravados e do modelo real da linha** (incluindo tarifa de cache),
  nunca de tarifa fixa assumida; o custo do **juiz** em coluna separada (`judge_model`,
  `judge_usage`), para não esconder nem diluir diferenças entre variantes.
- **Taxa de acerto de cache comparável entre variantes:** uma variante com cache morno e outra
  fria carrega diferença de custo/latência que é artefato da ordem de execução.
- **Latência medida nas fronteiras certas:** só a última requisição bem-sucedida; retry do cliente,
  espera de backoff, fila local atrás de semáforo e pós-processamento ficam fora da coluna de
  latência do modelo (wall-clock total em coluna à parte).
- **Quebra por chamada em eval agêntico:** tokens, custo e tempo por chamada de modelo e de
  ferramenta, senão ferramenta lenta e modelo lento se confundem.
- **Desempenho ao lado da qualidade**, por variante, em números absolutos primeiro.

## 5. Avaliador (função nota)

- **Concordância enunciado–avaliador:** o enunciado pede "pelo menos X" e o avaliador só passa em
  "mais que X"; pede explicação e só se confere o número — isso pune quem obedece.
- **Nota o resultado, não o caminho:** exigir sequência exata de ferramentas ou frase específica
  reprova quem resolveu de outro jeito válido.
- **Agente que age sobre ambiente: nota o estado final, não a transcrição.** Execute em área
  descartável e pontue o que ficou (testes passam, diff aplica, arquivos/linhas esperados existem,
  nada proibido foi tocado, passos dentro do orçamento); rubrica ou juiz par a par só para o que
  checagem não vê (legibilidade, mínimo do diff, qualidade da descrição do PR). Juiz lendo
  transcrição de código nota a narração.
- **Não rígido demais:** espaço, caixa, `4` × `4.0`, cerca de markdown, unidade, separador de
  milhar, frase em volta da resposta — normalize os dois lados ou aceite formas equivalentes.
- **Não leniente demais:** escreva uma resposta errada-mas-plausível e confirme que falha.
- **À prova de trapaça:** hard-code da saída esperada, leitura do gabarito, tratamento especial por
  nome de teste, string vazia aceita por regex frouxa, política degenerada que otimiza a métrica,
  injeção de instrução na entrada do juiz. Sob pressão de otimização, modelos acham esses caminhos.
- **Gabarito inalcançável pelo modelo sob teste** — estruturalmente (não em arquivo do sandbox,
  repositório clonado, histórico de commit, prompt de avaliador visível, web aberta). "Não olhe"
  no prompt não é defesa.
- **Leia as falhas:** se mais de ~1 em 10 das saídas marcadas erradas parecem erro do avaliador,
  conserte-o antes de qualquer rodada cheia.
- **Determinístico, ou com variância medida:** rode o avaliador duas vezes sobre a mesma saída.
- **Verificações atômicas > nota holística:** `{correto, formatado, conciso}` separados, uma
  chamada de juiz por propriedade; mais reprodutível e diagnóstico.
- **Agregação responde à pergunta:** média para qualidade típica; para comportamento raro e de alto
  risco (apagar dado, ação irreversível) vale falha-se-qualquer-um ou pior caso.
- **Crédito parcial e penalidades não tornam "não fazer nada" a política ótima.**
- **Saída grande:** o avaliador não trunca, nem estoura tempo, nem quebra; quebra do avaliador é
  `status: error`, não falha do modelo.

### Quando o avaliador é um LLM-juiz

- **Viés de posição:** em comparação par a par, sorteie A/B por caso (ou pontue nas duas ordens e promedie).
- **Viés de verbosidade:** instrua o juiz a não premiar tamanho por si só.
- **Autopreferência:** juiz da mesma família do modelo testado favorece saída parecida com a sua;
  não use o próprio modelo sob teste como juiz; para casos apertados, outra família ou júri pequeno.
- **Sem deferência a rótulo:** não diga qual resposta é "referência", "baseline" ou "humana".
- **Rubrica concreta,** com propriedades verificáveis (não "qual é melhor?"); o texto candidato é
  **dado não confiável, nunca instrução**; saída estruturada para parse determinístico.
- **Calibrado contra rótulo humano:** algumas dezenas de casos rotulados de forma independente;
  concordância bem abaixo de ~90% nos casos óbvios = ajuste o prompt do juiz antes de deixá-lo
  orientar mudanças.
- **Testado com negativos conhecidos:** string vazia, "não sei" e resposta confiante à pergunta
  errada — o juiz precisa reprovar os três.

## 6. Poder de detecção — o eval enxerga a mudança que você busca?

Um eval correto em tudo acima ainda pode ser inútil para a decisão por falta de resolução. Cheque
**antes** da primeira rodada cheia (descobrir depois de várias rodadas pagas é o jeito caro).

- **Piso de ruído × margem × menor ganho que valeria entregar.** Com o baseline no nº de
  repetições real, calcule o piso de ruído da métrica-alvo: meia-largura do IC95 da diferença
  pareada em n × R (para taxa de acerto, ~`1/√(n·R)`; 25 casos × 2 reps ≈ ±14 pontos; 100 × 2 ≈ ±7).
  Compare com a **margem** (teto − baseline) e com o **menor ganho que o dono entregaria**. Se o
  piso excede qualquer um, diga já, com números, e ofereça alavancas em ordem de custo: mais
  repetições (desenho pareado rende mais), mais casos, métrica par a par ou contínua em vez de
  binária, ou reduzir a casos discriminantes para iterar com confirmação no conjunto completo no fim.
  Casos e repetições são dois botões do mesmo dial: dimensione juntos.
- **Treino e teste da mesma população.** Se haverá hill-climb com divisão, sorteie a divisão
  (estratificada pela primeira tag) — **nunca por nota de baseline**. Treino montado com os piores
  casos garante que o analisador só veja patologia e compra regressão à média (esses casos
  "melhoram" no reteste só por acaso). Sintoma: ganho saudável no treino com held-out plano.
  Confira no baseline que as médias de treino e teste concordam dentro do ruído; se não, re-sorteie.
- **O mecanismo está ligado:** o que a nota deveria depender (ferramenta, memória, arquivo de
  instruções) — desligue e veja a nota cair; ligue e veja nas transcrições que ele engata. Se a
  nota mal mexe nos dois casos, o eval não mede a alavanca que você vai puxar.
- **O número do título recomputa das linhas brutas:** recalcule a partir dos `grade` por caso; não
  confie em campo agregado. Confusão média × soma e por-repetição × por-caso fabrica "avanço" fantasma.

## 7. Como reportar achados

- Tom de **observação e sugestão**, não de sentença: quem montou o eval costuma ter contexto
  (prazo, restrição, escolha deliberada) que o auditor não vê.
- **Severidade:** primeiro o que torna o número ativamente enganoso (infra pontuada como falha,
  "sem resposta" = "negativo", gabarito alcançável, gabarito derivado do modelo comparado, divisão
  escolhida por nota, piso de ruído maior que o efeito, juiz não determinístico); depois o que só
  adiciona ruído ou limita generalidade.
- **Específico e com evidência:** arquivo, função, id do caso, linha da transcrição.
- **Diga quando está tudo bem** — auditoria sem achados é resultado válido; não fabrique ressalva.
- **Curto:** os poucos pontos que importam à decisão, não todo desvio do ideal.
- **Ofereça consertar** o que é pequeno (campo `status`, semente fixa, normalização, sorteio A/B,
  novo sorteio da divisão).

Duas práticas que valem mesmo sem achados: tratar o eval como **suíte viva** (falha nova de
produção vira caso; item saturado é endurecido; juiz é recalibrado quando deriva) e, de tempos em
tempos, pedir a um modelo forte que leia casos, rubrica e algumas transcrições nota-das e aponte
onde uma pessoa razoável discordaria do rótulo (o auditor por caso do §2 é a versão em escala).

## 8. Checklist de aceite do eval (antes da 1ª rodada paga)

- [ ] Rodou de ponta a ponta em poucos casos; oráculo passa e nulo falha.
- [ ] Origem do gabarito registrada; sem vazamento; ~10 respostas re-derivadas.
- [ ] Falha de infra, truncamento e recusa em colunas próprias (nada vira zero).
- [ ] Modelo servido conferido na resposta; config = produção; trajetórias gravadas.
- [ ] Tokens e custo da API (juiz à parte); cache comparável; latência sem retry/fila.
- [ ] Avaliador lido nas falhas (<~10% erro dele), determinístico ou com variância medida;
      juiz calibrado e testado com negativos.
- [ ] Piso de ruído calculado e menor que margem e menor ganho relevante.
- [ ] Divisão treino/teste sorteada, não escolhida por nota; título recomputado das linhas.
