# Avaliação de modelo customizado (LLM-juiz × avaliador programático)

> Referência da skill `ai-evaluation`. Cobre o caso em que o modelo avaliado foi ajustado
> (fine-tuning) ou escolhido num serviço gerenciado — exemplo concreto: Amazon SageMaker +
> Amazon Bedrock Evaluations — e a pergunta é **qual régua usar** e **que armadilhas de
> execução evitar**. Os números e limites citados vêm da documentação da fonte em 17/10/2026
> e **podem mudar**: confirme na documentação vigente antes de gatilhar uma decisão.
> Todo resultado daqui entra no scorecard com o selo da §1 da skill.

## 1. Pré-condição: sem conjunto de avaliação, não há avaliação

Os dois tipos de avaliador exigem um conjunto de avaliação com entrada e resposta de
referência. Se ele não existe, a resposta honesta é "não dá para avaliar ainda" — não improvise
um conjunto a partir das próprias saídas do modelo (isso mede o modelo contra ele mesmo).
Valide o formato do conjunto **antes** de gastar uma execução paga; formato errado costuma
só falhar no meio do job.

## 2. Escolher a régua pela força do sinal e pelo custo

| Tipo | Quando é a melhor régua | Custo/risco |
|---|---|---|
| **Programático** (comparação exata, regex, verificador de matemática, teste de código, função própria) | Existe resposta verificável por código: classificação, extração, número, teste de entrada/saída, conformidade de formato | Barato, determinístico, reprodutível. Cego a qualidade subjetiva |
| **LLM-juiz** | O que importa é subjetivo: utilidade, coerência, tom, fidelidade ao contexto (RAG), segurança | Uma chamada de modelo por amostra: mais caro, não determinístico e capaz de alucinar o veredito |

Procedimento de decisão (faça nesta ordem, usando só o que ainda não sabe):

1. Tem conjunto de avaliação? Se não, pare (§1).
2. O modelo é de uma família que o juiz gerenciado não suporta? Então só o programático existe.
3. Dê a cada régua uma nota de sinal — **forte / média / fraca** — para *esta* tarefa.
   Programático forte: resposta objetivamente certa ou errada. Juiz fraco: tarefa de resposta
   única, onde o juiz só acrescenta risco de erro.
4. Programático forte → use-o, mesmo que o juiz também funcionasse. Juiz forte e programático
   fraco → juiz. Ambos médios ou fortes → pese custo: pergunte (1–5) o quanto o custo importa.
5. Sinal programático fraco **e** custo crítico → programático, mas declare no relatório que o
   sinal é limitado (selo `proxy`).

Atenção à lei de Goodhart (§riscos da skill): o programático mais barato frequentemente mede
só o formato. Combine "formato correto" (programático) com "conteúdo bom" (juiz) quando os dois
importam, em vez de escolher um.

## 3. LLM-juiz: métricas

- **Métricas prontas** cobrem qualidade (correção, completude, fidelidade ao contexto,
  utilidade, coerência, relevância, seguir instruções, tom profissional) e IA responsável
  (dano, estereótipo, recusa). Parta de um conjunto-base por tarefa e ajuste:
  QA/matemática → correção, completude, fidelidade, relevância; resumo → completude, coerência,
  relevância; assistente geral → utilidade, relevância, seguir instruções; segurança → dano,
  estereótipo, recusa.
- Se o usuário discordar da sugestão, descubra o porquê e ajuste — concordar por reflexo
  vicia a régua.
- **Métrica customizada** é um prompt de avaliação mais uma escala de notas. Estrutura que
  funciona, nesta ordem: (1) papel do juiz (opcional); (2) descrição da tarefa, em frase
  completa (a fonte exige ao menos 15 palavras); (3) critério e rubrica (opcional); (4) as
  variáveis de entrada **por último** — pergunta, resposta do modelo e resposta de referência.
- A escala precisa de definição por nota, não só de números; escala binária ("aceitável /
  inaceitável") é mais estável que escala de 1–10 e mais fácil de calibrar com humanos.
- Limite da fonte: até **10** métricas customizadas por job, combináveis com as prontas.
- Valide o JSON das métricas com um validador antes de submeter e **itere o texto do prompt**
  depois de ver resultados reais: ninguém garante que o juiz interprete a rubrica como você quis.

## 4. LLM-juiz: escolha do modelo juiz e limites

- O serviço aceita só uma lista restrita de modelos juiz, que varia por região, e modelos em
  ciclo de vida *legacy* falham na execução. Antes de listar opções, consulte o status do
  modelo na região e **filtre os ativos**.
- A skill **lista** os juízes disponíveis; **quem escolhe é o humano**. Se pedirem orientação,
  só o trade-off: modelo menor é mais rápido e barato, maior julga melhor tarefas de
  raciocínio longo. Não faça recomendação nominal.
- Limite de tamanho: o juiz gerenciado da fonte aceita no máximo **1.000 linhas por job**.
  Conjunto maior precisa ser amostrado antes — avise na hora de validar o conjunto, não depois
  da falha. Amostre com seed fixa e registre-a (§3 da skill).
- O juiz é um **proxy** da percepção humana até ser calibrado: correlacione as notas dele com
  o painel humano (§5 da skill) antes de usar o resultado como gate automático.
- Comparar "modelo ajustado × modelo base" no mesmo job reaproveita o mesmo juiz e o mesmo
  conjunto — é a comparação limpa. Compare só braços que fazem o mesmo trabalho.

## 5. Avaliador programático como função (Lambda) — contratos que quebram em silêncio

- A função recebe, por amostra: identificador, resposta do modelo, o prompt e a resposta de
  referência; devolve por amostra um identificador, uma nota agregada e uma lista de métricas
  nomeadas. Defina as métricas da lista de antemão — nota única esconde onde o modelo falha.
- **O formato do retorno difere por família de modelo**: em uma, o corpo da resposta é uma
  *string* JSON; em outra (Nova, na fonte), é a lista já estruturada. Errar isso não dá exceção
  óbvia — dá job que roda e não pontua. Teste a função com uma amostra de cada formato.
- Na família que usa mensagens, a resposta do modelo é a **última mensagem do assistente**.
- O avaliador precisa ser **registrado** no catálogo do serviço (a função de recompensa vira um
  conteúdo de hub) — passar o identificador cru da função Lambda é rejeitado. Valide o registro
  antes de usar: existe, está disponível e é do tipo função de recompensa.
- O papel de execução do job precisa de permissão para invocar aquela função.
- Verificadores prontos de matemática e de código **não funcionam** para a família Nova: o
  pipeline termina sem erro e sem pontuar. Se o resultado vier vazio, suspeite disso antes de
  suspeitar do modelo — e confira que houve pelo menos uma nota por amostra (`N_notas == N_amostras`).

## 6. Armadilhas de execução

1. **Confiança do papel**: o serviço de avaliação precisa assumir o papel; sem ele na política
   de confiança, o job falha com "acesso negado ao assumir o papel". Isso é comum ao rodar com
   credenciais temporárias/SSO. Inspecione a política de confiança do papel e adicione o
   principal do serviço, ou use um papel que já o confie.
2. **ARN de pacote de modelo**: o válido termina em versão numérica. ARN de *grupo* ou sem
   versão deve ser resolvido para a última versão; ARN de outro recurso (conjunto, job) é
   erro de digitação. Confirme que o recurso existe antes de submeter.
3. **Tempo e dinheiro**: o job leva dezenas de minutos a horas e cobra por amostra julgada.
   Ofereça três modos — o humano roda; roda-e-espera; dispara-e-consulta-depois — e nunca
   bloqueie um agendamento sem humano esperando por um job longo.
4. **Termos do serviço**: o serviço gerenciado pode trafegar dados entre regiões da mesma
   geografia e tem preço e termos próprios. Exija **confirmação explícita** do humano antes de
   gerar/submeter, e não diga que aceitou por ele. Dado pessoal no conjunto reabre o risco de
   consentimento já listado na skill.
5. **Registro de experimento**: grave o resultado num rastreador de experimentos (nome
   `<projeto>-eval`) para que fique ao lado do resto — é o baseline do próximo ciclo.

## 7. Checklist antes de aceitar o resultado

- [ ] Conjunto de avaliação versionado, formato validado, tamanho dentro do limite do juiz.
- [ ] Régua escolhida por força de sinal e custo, com a justificativa no relatório.
- [ ] Juiz: lista filtrada por região/ativo, escolha feita pelo humano, correlação humana medida.
- [ ] Função programática: formato de retorno testado por família de modelo; N de notas = N de amostras.
- [ ] Papel de execução com confiança e permissão de invocação conferidas.
- [ ] Confirmação humana dos termos/custos registrada antes da submissão.
- [ ] Selo de origem em cada número (`medido` / `proxy`), baseline congelado.

## 8. Acerto de ferramentas (agente que chama tools) — régua programática

Antes de mandar um juiz LLM decidir se o agente "usou as ferramentas certas", meça de forma
determinística. Cada chamada é `(nome, argumentos)`; o caso de teste traz a lista esperada.

- **Exato** — 1 só se as listas têm o mesmo tamanho e cada posição bate em nome e argumentos;
  qualquer diferença dá 0. Use quando a ordem e o conjunto são contrato (fluxo de pagamento).
- **Sem ordem** (padrão) — para cada esperada, pegue a chamada ainda não usada de mesmo nome com
  o maior subscore; cada chamada casa uma vez só.
- **Com ordem** — LCS ponderado entre esperadas e chamadas (a diagonal só conta quando o nome
  bate): pune ordem trocada sem zerar o caso inteiro.
- **Subscore de argumentos** (opcional) — dicionários iguais valem 1; senão, cada chave comum com
  valor igual soma 1/|união das chaves| (dicionário aninhado entra recursivo). Comparação estrita:
  normalize caixa/espaço antes, se o contrato permitir.
- **Score = soma dos subscores ÷ nº de esperadas.** Isso é **recall**: chamada extra não
  penaliza. Publique ao lado a **precisão = casadas ÷ chamadas**, senão um agente que chama tudo
  tira nota cheia. Lista esperada vazia: 1 se o agente não chamou nada, 0 se chamou.
- O juiz LLM entra só depois, e só para o que a régua não vê (a escolha era razoável dado o
  catálogo?). Se usar os dois, o veredito do caso é o **mínimo** entre eles.

Exemplo de acerto de ferramentas (com ordem): esperadas `[busca, reservar, confirmar]`, chamadas
`[busca, listar, reservar, listar]` → LCS casa `busca, reservar` → recall = 0,67 e precisão = 0,50.
Recall sozinho esconderia as duas chamadas inúteis.

Proveniência: técnica reescrita a partir de confident-ai/deepeval (`tool_correctness.py`,
Apache-2.0, @5410e382) e dos modos de trajetória de langchain-ai/agentevals (MIT, @946ad15b);
a precisão ao lado é acréscimo da Squad. Eval: `evals/eval_acerto_ferramentas.py`.
