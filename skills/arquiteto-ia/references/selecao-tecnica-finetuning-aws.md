# Escolha da técnica de fine-tuning (SFT × DPO × RLVR × RLAIF) — SageMaker AI

> Reference do `arquiteto-ia`. Procedência: técnicas absorvidas e reescritas das skills
> `finetuning-technique` e `finetuning` (guias de RLVR/RLAIF) do plugin SageMaker AI de
> `awslabs/agent-plugins` (Apache-2.0); ver `docs/ATTRIBUTIONS.md`.
> Trechos marcados **(Squad)** são adaptação nossa, não vêm da fonte.
> Nomes de APIs, modelos de juiz e receitas disponíveis mudam: são o retrato de 18/10/2026 —
> confirme na documentação vigente antes de decidir.

## Quando usar

Já se decidiu que prompt/RAG não bastam e o modelo será ajustado. A pergunta aqui não é "como
treinar", e sim **qual técnica** e **qual sinal de recompensa**, antes de gastar GPU. Depois do
treino, ver `implantacao-modelo-customizado-aws.md` (onde servir) e a skill `ai-evaluation` (medir).
**(Squad)** Antes de ajustar qualquer coisa, tenha uma avaliação-base do modelo sem ajuste: sem ela
não há como dizer que a técnica escolhida melhorou algo.

## Pré-requisito: o caso de uso escrito

Escolher técnica sem especificação é palpite. Registre antes, em um arquivo curto: tarefa, formato
de entrada e saída, o que é "bom", o que é "ruim" e como isso seria medido. É esse texto que
decide a técnica abaixo e, mais tarde, a função de recompensa ou o prompt do juiz.

## Quatro técnicas, uma pergunta cada

| Técnica | Pergunta que a escolhe | Sinal de aprendizado | Exemplos típicos |
|---|---|---|---|
| **SFT** | Existe **uma** resposta certa por entrada? | Imitar respostas-ouro | classificação, extração, saída estruturada |
| **DPO** | Várias respostas são válidas, mas umas são melhores? | Pares preferida × rejeitada **já coletados** | tom, estilo, utilidade, tarefas criativas |
| **RLVR** | Dá para **verificar por programa** se a saída está certa? | Recompensa calculada por regra | código (testes passam), matemática, restrições de formato |
| **RLAIF** | Qualidade é subjetiva e não há dados de preferência? | Recompensa dada por **modelo-juiz** | resumo, diálogo, voz de marca, segurança |

Diferenças que mais confundem:

- **SFT × RLVR:** no SFT o modelo copia o gabarito; no RLVR ele maximiza a recompensa (que pode ser
  similaridade ao gabarito *ou* uma verificação). Com verificação objetiva, RLVR costuma generalizar
  melhor do que decorar exemplos.
- **DPO × RLAIF:** DPO exige um conjunto estático de pares; RLAIF gera o sinal dinamicamente e pode
  ser regerado conforme o modelo melhora.
- **RLVR × RLAIF:** regra determinística versus julgamento de outro modelo.

Quando **não** escolher RLAIF: a resposta é verificável (use RLVR), já existem boas preferências humanas
(use DPO) ou existe gabarito de qualidade (use SFT). **Regra de ouro do juiz:** a qualidade do juiz limita a
qualidade do treino — juiz mais fraco que o modelo treinado não ensina nada útil.

## Validar contra o modelo-base

Nem todo modelo oferece todas as técnicas. A ordem correta é **modelo-base primeiro**, depois técnica,
e a técnica é confirmada contra as receitas que o catálogo do SageMaker declara para aquele modelo
(a fonte lê isso das palavras-chave do conteúdo do hub). Se a técnica escolhida não existe para o modelo,
volte e troque o **modelo** ou a **técnica** — não force. O escopo da fonte cobre só estas quatro; qualquer
outra receita listada deve ser ignorada. Liste também a **licença** do modelo-base já na escolha (ver o
portão de licença em `implantacao-modelo-customizado-aws.md`).

## RLVR: desenhar a função de recompensa

A recompensa é uma função (Lambda) que recebe as respostas geradas e devolve notas numéricas. Roteiro:

1. **Entender o que é bom, ruim e parcial** olhando a especificação e algumas dezenas de linhas reais do dataset.
2. **Mapear a estrutura da resposta:** que trecho carrega o que se verifica, como é delimitado, se há bloco de
   raciocínio, formatos especiais (frações, LaTeX, Markdown). Decidir se o foco é só a resposta final ou também o raciocínio.
3. **Planejar a verificação:** extrair o trecho, validar formato com parser de verdade (não casamento de texto),
   executar código gerado quando for o caso, escolher a medida de similaridade para respostas parcialmente livres.
4. **Antifraude (mínimo duas defesas):** o modelo vai explorar atalhos — encher de caracteres para parecer longo,
   pular passos, repetir, usar texto de enchimento, ecoar a pergunta, produzir texto sem sentido.
5. **Agregação em camadas (pirâmide):** estrutura (parseável?) → semântica (correto?) → comportamento
   (conciso, seguro, completo?). Não dá crédito a uma camada enquanto a de baixo não for satisfeita.
6. **Gradiente de aprendizado:** cada componente deve devolver notas variadas mesmo para saídas ruins. Um
   componente que dá zero para quase todas as respostas do início do treino achata o sinal e o treino estagna.

Propriedades da função: **determinística** (mesma entrada, mesma nota), **rápida** (da ordem de décimos de segundo,
sem chamadas de rede), **limitada** a um intervalo fixo (a fonte usa de −1 a 1, com *clamp* no fim) e bem comentada.

Teste local com quatro respostas fabricadas — **excelente, parcial, ruim e tentando fraudar** — e confira: notas dentro
do intervalo, ordem esperada (excelente > parcial > ruim) e a fraudulenta **não** entre as melhores. A função é
**sugestão**: uma pessoa revisa antes do treino. **(Squad)** versionar a função e o conjunto de quatro casos como
teste de regressão, e rodar de novo a cada mudança de dataset.

## RLAIF: desenhar o juiz

- Um modelo hospedado no Bedrock julga as saídas durante o treino; a lista de modelos de juiz permitidos e as
  regiões é consultada no SDK na hora, não decorada.
- **Prompt embutido** se um dos quatro roteiros prontos (resumo, fidelidade à fonte, raciocínio passo a passo,
  avaliação geral) encaixa; **prompt próprio** (modelo de texto com variáveis para o pedido e a resposta, registrado
  como avaliador) quando o domínio exige critérios específicos ou saída estruturada.
- Ao escrever o prompt do juiz, responda: o que uma boa resposta tem? o que deve ser penalizado? o juiz devolve nota,
  rótulo ou ranking?
- Registre rastreamento do experimento (nome do experimento e da execução) para comparar rodadas.
- Retreino a partir de um modelo já ajustado é caminho à parte (customização contínua): passa-se o pacote do modelo
  anterior no lugar do nome do modelo-base.

## Checklist (Squad)

- [ ] Caso de uso escrito e avaliação-base do modelo sem ajuste medida.
- [ ] Técnica escolhida pela pergunta da tabela, com a alternativa descartada e o motivo registrados.
- [ ] Combinação modelo-base × técnica confirmada nas receitas do catálogo; licença do modelo exibida.
- [ ] RLVR: função com camadas, ≥2 defesas antifraude, 4 casos de teste e revisão humana antes do treino.
- [ ] RLAIF: juiz tão capaz quanto o modelo treinado (ou mais), prompt versionado, amostra de notas do juiz conferida por pessoa.
- [ ] Custo de treino e de juiz estimado e aprovado no gate; nenhum dado sensível do dataset em notebook versionado.
- [ ] Depois do treino: avaliar (`ai-evaluation`) e só então implantar.
