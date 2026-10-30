# Documentar código herdado: engenharia reversa com rastreabilidade

Quando carregar: o usuário herdou um serviço sem especificação ("entender esse sistema", "documentar esse serviço", "o time saiu"). Aqui a spec não nasce de entrevista: nasce do código. O risco é produzir um texto bonito que ninguém consegue conferir. Esta técnica trata o código como única fonte de verdade e exige que cada afirmação possa ser verificada.

## Princípios

1. **Explicar o porquê, não só o quê.** Listar componentes não ajuda quem chega sem contexto. Procure motivos em comentários, TODOs, mensagens de commit e nomes de branch, e escreva por que a arquitetura tem este formato.
2. **Seguir o fluxo de ponta a ponta.** Para cada endpoint ou consumidor de mensagem, trace o caminho completo: entrada, transformações, chamadas externas, timeouts, pontos de falha, resposta. É o mapa que serve de madrugada, no incidente.
3. **Aprofundar o trecho complexo.** Máquinas de estado, motores de regra, pipelines e algoritmos próprios do domínio merecem explicação no nível da implementação, não um parágrafo genérico.
4. **Extrair o conhecimento implícito.** Valores fixos, números mágicos, comportamento que muda por ambiente e premissas não escritas somem quando a equipe sai. Registre-os como item próprio.
5. **O código vence a documentação.** Descreva o que existe. Toda divergência entre README/wiki e código vira achado.
6. **Contagens são conferidas por comando**, não de memória: liste o diretório e conte.

## Cada afirmação carrega sua fonte

- Cite `caminho:linha` (ou `caminho:inicio-fim`) com link relativo à raiz analisada e âncora `#L<linha>`. Em tabela, a fonte vai numa coluna; em texto corrido, num bloco "Fontes" logo após o parágrafo, com uma frase dizendo o que cada citação mostra.
- Some o nome do símbolo à linha (`handleRequest()`), porque o número de linha envelhece e o nome permite reencontrar o trecho.
- Antes de publicar, releia o arquivo citado e confira que aquelas linhas sustentam a frase. Citar de memória é o erro mais comum.
- Evite citar arquivo inteiro, exceto se for pequeno.

### Marcadores de incerteza (um por tipo de lacuna)

| Marcador | Quando usar |
|---|---|
| `[INFERIDO]` | dedução razoável sem evidência direta; diga em que se baseia |
| `[DESCONHECIDO]` | não dá para saber olhando o código |
| `[RISCO]` | modo de falha sem tratamento |
| `[SEM-JUSTIFICATIVA]` | decisão arquitetural cuja razão não aparece em lugar nenhum |
| `[NAO-VERIFICADO]` | citação que não pôde ser conferida; explique por quê |
| `[NAO-USADO]` | símbolo ou arquivo que nenhum caminho de execução alcança (candidato a código morto) |

Regra: nunca apresente inferência como fato. O leitor precisa distinguir, só pela marcação, o que é citado, o que é deduzido e o que é ignorado.

## Método de análise (três passadas antes de escrever)

1. **Mapa:** estrutura de pastas e pontos de entrada, para delimitar o escopo.
2. **Leitura e perguntas:** leia os arquivos centrais e anote dúvidas (quem chama isto? onde se configura? o que acontece no erro?).
3. **Caça às respostas:** busque as respostas no repositório inteiro (grep por rotas, modelos, handlers de erro) e siga as dependências entre módulos.
4. **Só então escreva**, relendo os arquivos para obter as linhas exatas.

Seções transversais (modos de falha, configuração, segurança, divergências) ficam por último, porque dependem de tudo que foi aprendido.

## Cobertura e testes

- Enumere **todos** os arquivos-fonte não gerados; cada um aparece em alguma tabela ou, no mínimo, num inventário. O que define símbolos que ninguém importa recebe `[NAO-USADO]`.
- Documente o que os testes verificam, onde há lacuna de cobertura e como ler uma falha. Testes mostram o comportamento esperado e os casos de borda.
- Passagem de divergências: depois da análise, releia README, arquivos de instrução do agente, descrição do pacote e metadados, e marque cada alegação sem lastro no código (funcionalidade citada mas inexistente, tipo de recurso diferente, componente que não existe). Em legado, esta é a saída mais valiosa.

## Modos de falha acionáveis

Para cada falha, escreva como detectar (métrica, padrão de log, sintoma) e como recuperar (comandos reais), não só a descrição. O leitor é quem está de plantão.

## Código-fonte e infraestrutura

- **Aplicação:** extraia definições de API, modelo de dados, dependências internas, integrações externas e configuração (variáveis de ambiente, flags, referências a segredos).
- **IaC (CDK, CloudFormation, Terraform):** mapeie recursos, relações e topologia de rede, e ligue cada recurso ao componente que o usa. Em CDK a infraestrutura é código de aplicação; faça uma passada única cobrindo as duas coisas.
- **Sem IaC:** deduza a infraestrutura pelos clientes de SDK, strings de conexão e variáveis de ambiente, e marque `[INFERIDO]`.

## Bases grandes

- Mantenha um quadro de progresso em arquivo (seções feitas e pendentes) para poder retomar se a sessão cair.
- Se o ambiente permitir agentes em paralelo, distribua seções independentes; a visão geral e as seções transversais ficam na sessão principal, que monta o resultado.

## Esqueleto do documento

Visão geral e propósito; arquitetura e por que ela é assim; fluxos ponta a ponta; modelo de dados; integrações; configuração e implícitos; modos de falha com detecção e recuperação; segurança; testes e lacunas; divergências doc × código; inventário de arquivos; glossário de termos do domínio.

## Checklist antes de entregar

- [ ] Toda afirmação tem fonte conferida ou marcador de incerteza.
- [ ] Contagens vieram de comando.
- [ ] Todo arquivo-fonte aparece na documentação.
- [ ] Divergências doc × código listadas.
- [ ] Cada modo de falha tem detecção e recuperação.
- [ ] Decisões sem justificativa registradas como `[SEM-JUSTIFICATIVA]`, não inventadas.

## Relação com outras skills

O resultado alimenta a spec congelada e a matriz de rastreabilidade; o `spec-code-drift-detector` usa as divergências como ponto de partida, e o `diagramador` desenha os fluxos já documentados.
