# Dataset de fine-tuning e de avaliação — validar antes de gastar, transformar com função testada

> Procedência: técnica inspirada nas skills `dataset-evaluation` e `dataset-transformation` de
> `awslabs/agent-plugins` (Apache-2.0), reescrita com palavras próprias. Os pontos marcados
> **[Squad]** são adaptação da casa. Ver `docs/ATTRIBUTIONS.md`.

Treino que falha na primeira hora por esquema errado custa menos que o que termina e produz
lixo, mas os dois custam mais que uma checagem de dez segundos. Esta página cobre o que vem
**antes** do job de treino ou de avaliação: confirmar que o arquivo serve ao propósito e, se não
servir, convertê-lo de forma reproduzível.

## 1. Treino e avaliação não têm o mesmo formato

| Propósito | O que o arquivo precisa ter | Dependência |
|---|---|---|
| Treino | Esquema da **técnica** (SFT, DPO, RLVR, RLAIF) no dialeto da **família do modelo** | Modelo-base e técnica já decididos |
| Avaliação geral | Pares consulta/resposta de referência | Independe de modelo e de técnica |
| Avaliação com pontuador próprio | Esquema do pontuador (matemática simbólica, execução de código contra casos de teste, função Lambda do cliente) | Tipo de pontuador já escolhido |

Regras que decorrem da tabela:

- Não bloqueie a validação de um dataset de **avaliação** pedindo modelo e técnica; eles não entram na conta.
- Dataset de treino exige os dois. Se faltarem, volte à decisão de técnica (ver `selecao-tecnica-finetuning-aws.md`) em vez de adivinhar.
- Modelos de famílias diferentes usam dialetos diferentes para a *mesma* técnica: de um lado pares simples
  (prompt/completion, prompt/chosen/rejected, mensagens com campo de verificação); do outro, conversas com
  versão de esquema, papéis em blocos de conteúdo e, em preferência, candidatos rotulados como preferido
  ou não. Confira a família antes de reaproveitar um arquivo "que já funcionou".
- Pontuador de código executa a resposta com entrada padrão e compara a saída padrão: o dataset
  precisa trazer listas de entradas e saídas esperadas, **de mesmo tamanho**, como texto. Pontuador
  matemático compara valor, então a resposta de referência deve ser só o valor, não a explicação.

## 2. Como validar

1. **Localizar** o arquivo (caminho local ou URI de objeto) e confirmar permissão de leitura. Se não achar, ajude a localizar; não invente caminho.
2. **Rodar um detector de formato** que receba apenas o caminho e devolva quais esquemas o arquivo satisfaz. Compare o resultado com a técnica e o modelo que você já decidiu.
3. **Classificar o veredito** em três saídas, nunca em "ok/não ok":
   - válido para o propósito pretendido;
   - válido, mas para **outra** técnica ou outra família de modelo (avise e proponha converter);
   - inválido para qualquer par técnica/modelo (aponte o primeiro campo que quebra e proponha transformar).
4. **Se for treinar**, conferir que o dado estará no armazenamento da **mesma região** do job. Região diferente é falha de última hora que o detector de formato não vê.

Higiene da checagem: valide o arquivo onde ele está. Não baixe o conjunto inteiro nem faça cópia local só
para olhar o formato; é lento, duplica dado possivelmente sensível e deixa resíduo fora do controle de acesso.

**[Squad]** Além do formato, reserve a checagem de **conteúdo** que o detector não faz: duplicatas exatas,
prompts vazios, comprimento muito desigual entre `chosen` e `rejected` (o modelo aprende "o mais longo ganha"),
respostas de referência que contradizem o prompt, dado pessoal (LGPD) e sobreposição com o conjunto de avaliação
(vazamento). Formato válido não é dado bom.

## 3. Como transformar

Conversão de esquema é onde nasce o bug silencioso (campo trocado de lugar, papel errado, linha descartada
sem aviso). Trate-a como código, não como edição ad hoc:

1. **Origem e destino explícitos.** Peça uma amostra de 1 a 2 registros da origem e o esquema de destino
   (treino: técnica + família do modelo; avaliação: formato nomeado ou um registro de exemplo do usuário).
   Formato nomeado se busca na documentação viva do serviço; se estiver sem rede, use cópia offline e **diga que ela pode estar desatualizada**.
2. **Uma função pura**: recebe a tabela de entrada e devolve a tabela de saída, sem ler nem gravar arquivo. É o que a torna testável.
3. **Teste na amostra** antes de qualquer execução em massa: grave a amostra, rode a função, mostre a saída e só então peça aprovação.
4. **Script de execução separado** que importa a função, lê a entrada, grava a saída e aceita caminhos por argumento. Nome de saída padrão: `<original>_<formato-destino>.jsonl`.
5. **Saída em linhas JSON** (uma por registro), salvo pedido em contrário.
6. **Contar e conferir no fim**: registros lidos × gravados; qualquer diferença exige explicação (descarte deliberado documentado), nunca silêncio.

### Onde executar

| Tamanho do arquivo | Recomendação |
|---|---|
| Abaixo de ~50 MB | Execução local |
| Acima de ~50 MB | Job de processamento gerenciado, com entradas e saídas declaradas e logs acompanhados |

Limite é ponto de partida, não lei; o que decide é memória disponível e tempo. Em qualquer caso o
usuário **aprova o modo de execução** antes de rodar, e o agente transforma sozinho apenas a amostra de
teste. A execução completa é uma célula/comando entregue para o humano rodar (ou que o agente roda com ferramenta
própria de notebook, depois de perguntar).

## 4. Disciplina de conversa **[Squad]**

A fonte conduz o usuário passo a passo, uma decisão por vez, esperando confirmação. Aproveitamos o que serve
a um fluxo gated e descartamos o excesso:

- Uma decisão por turno, e cada pausa termina em pergunta direta. Mantém o humano no controle do gate.
- Só leia o material de referência quando chegar o passo que o exige.
- Não narre o que vai fazer; relate o resultado.
- **Não adotamos** a proibição rígida de sair do roteiro: se a amostra mostrar que a premissa está errada
  (ex.: o dataset já está no destino), diga isso e pare.

## 5. Checklist de gate

- [ ] Propósito (treino ou avaliação) declarado e, se treino, técnica e família do modelo conhecidas.
- [ ] Veredito de formato em uma das três saídas, com o campo que quebra quando inválido.
- [ ] Checagem de conteúdo feita: duplicatas, vazios, viés de comprimento, LGPD, vazamento para a avaliação.
- [ ] Armazenamento na região do job de treino.
- [ ] Função de transformação pura, testada na amostra, com contagem lidos × gravados.
- [ ] Modo de execução (local × gerenciado) aprovado por humano; nenhuma execução em massa feita pelo agente.
- [ ] Nenhum dado do dataset em notebook versionado ou em log.

## 6. Anti-padrões

| Anti-padrão | Efeito |
|---|---|
| Validar só o formato e treinar | Treina com duplicata, vazamento e viés de comprimento |
| Reaproveitar o arquivo de uma família de modelo em outra | Esquema "quase igual" falha tarde ou treina errado |
| Transformar com script inline descartável | Sem teste, sem rastro, sem reuso |
| Baixar o dataset inteiro só para olhar | Cópia solta de dado potencialmente pessoal |
| Descartar linhas inválidas sem contar | Dataset menor que o esperado e ninguém sabe por quê |
