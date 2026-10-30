# Checklist de Revisão de Código — Clean Code

Use este checklist como guia durante revisões. Não é para marcar mecanicamente — é para garantir que você não está esquecendo dimensões importantes.

## 1. Primeira leitura — você entende?

- [ ] **Você consegue dizer em uma frase o que o código faz?** Se não, o código já é confuso.
- [ ] **Os nomes na primeira tela contam a história?** Variáveis, funções, classes — leitura como prosa.
- [ ] **O nível de abstração faz sentido?** Detalhes baixos não invadindo lógica alta?

## 2. Nomes (`references/naming.md`)

- [ ] **Revelam intenção?** `elapsedDays` em vez de `d`?
- [ ] **Sem desinformação?** Não chamar `accountList` o que não é uma `List`?
- [ ] **Distinções significativas?** Nada de `data`, `info`, `temp`, `Manager` sem motivo?
- [ ] **Pronunciáveis?** Você consegue falar sobre eles em reunião?
- [ ] **Pesquisáveis?** Constantes mágicas (`7`, `42`) viraram constantes nomeadas?
- [ ] **Sem codificações húngaras?** `m_str_username` é um cheiro de legado?
- [ ] **Uma palavra por conceito?** Não misturar `fetch`, `get`, `retrieve` sem distinção?

## 3. Funções (`references/functions.md`)

- [ ] **Pequenas?** Idealmente até 20 linhas. Mais que 30 — explique o porquê.
- [ ] **Fazem uma coisa só?** Você consegue extrair outra função com nome significativo? Ela faz mais de uma.
- [ ] **Um nível de abstração?** A primeira linha e a última estão pensando o mesmo nível?
- [ ] **Poucos argumentos?** Zero, um, dois. Três é o limite saudável.
- [ ] **Sem argumentos flag?** Booleano sinaliza duas funções escondidas em uma.
- [ ] **Sem efeitos colaterais escondidos?** O nome promete tudo o que ela faz?
- [ ] **Sem misturar comando e consulta?** Modifica **ou** retorna, não ambos?

## 4. Comentários (`references/comments.md`)

- [ ] **Cada comentário sobrevive à pergunta**: "Posso transmitir isso no código?"
- [ ] **Sem código comentado?** (Sempre apagar.)
- [ ] **Sem histórico de mudanças?** (Vive no controle de versão.)
- [ ] **Sem TODOs antigos?** Se vivem mais de uma sprint, são mentira.
- [ ] **Sem Javadocs vazios** que apenas repetem assinatura?
- [ ] **Comentários que sobrevivem dizem o porquê**, não o quê?

## 5. Formatação (`references/formatting.md`)

- [ ] **Topo do arquivo dá panorama?** Detalhes descem.
- [ ] **Linhas em branco separam conceitos** distintos?
- [ ] **Conceitos relacionados estão juntos** verticalmente?
- [ ] **Variáveis declaradas perto do uso?**
- [ ] **Funções dependentes próximas?**
- [ ] **Largura de linha modesta** (≤ 120 colunas)?

## 6. Objetos vs Estruturas de Dados (`references/objects-and-data.md`)

- [ ] **Objetos escondem dados, expõem comportamento?**
- [ ] **Estruturas de dados expõem dados, sem comportamento?**
- [ ] **Sem híbridos** (objeto que também é estrutura de dados)?
- [ ] **Lei de Demeter respeitada?** Sem `a.b().c().d()` (train wrecks)?
- [ ] **DTOs são DTOs?** Sem lógica de negócio embutida?

## 7. Tratamento de Erros (`references/error-handling.md`)

- [ ] **Exceções, não códigos de retorno?**
- [ ] **Try/catch separado da lógica feliz?** (Extraído em sua própria função?)
- [ ] **Exceções com contexto suficiente** para diagnosticar?
- [ ] **Exceções definidas pelo que o caller precisa fazer**, não pela origem técnica?
- [ ] **Sem retornar `null`?** Use lista vazia, `Optional`, ou special case?
- [ ] **Sem passar `null`** como argumento?

## 8. Testes (`references/tests.md`)

- [ ] **Testes existem?** Se não, escrever um pelo menos antes de qualquer mudança.
- [ ] **F.I.R.S.T.?** Fast, Independent, Repeatable, Self-validating, Timely.
- [ ] **BUILD-OPERATE-CHECK** visível em cada teste?
- [ ] **Linguagem de domínio** do teste (não APIs do sistema diretamente)?
- [ ] **Um conceito por teste?**
- [ ] **Bordas testadas?** Vazio, null, off-by-one, primeiro, último?
- [ ] **Testes rápidos** (segundos, não minutos)?

## 9. Classes (`references/classes.md`)

- [ ] **Pequenas?** Você descreve em uma frase sem "e/ou"?
- [ ] **SRP?** Uma única razão para mudar?
- [ ] **Coesas?** Métodos compartilham variáveis, ou parecem duas classes presas em uma?
- [ ] **Encapsuladas?** Mínimo de coisas públicas?
- [ ] **Dependem de abstrações** (não de detalhes concretos)?

## 10. Smells frequentes (`references/smells-catalog.md`)

Faça uma varredura final pelos seis mais comuns:

- [ ] **G5 Duplicação** — qualquer trecho repetido (mesmo com pequenas variações)?
- [ ] **G30 Faz mais de uma coisa** — função/classe com múltiplas responsabilidades?
- [ ] **N1 Nomes pouco descritivos** — vagos, ambíguos, ruidosos?
- [ ] **F1 Argumentos demais** — quatro ou mais?
- [ ] **G6 Nível de abstração misturado** — alto e baixo na mesma função?
- [ ] **C5 Código comentado** — qualquer bloco comentado fora?

## Veredito final

Após o checklist, classifique:

- **Limpo** — pequenos ajustes, nada estrutural. Aprovar com sugestões.
- **Quase limpo** — alguns smells importantes mas localizados. Refatorar antes de prosseguir.
- **Sujo** — múltiplos smells, falta estrutura. Refatoração significativa antes de adicionar features.
- **Suja escura** — refatoração estrutural ou reescrita. Não construa em cima.

E **lembre**: o objetivo não é perfeição. É **significativamente melhor** do que estava. Seja gentil consigo mesmo e com o time — Clean Code é uma jornada, não um destino.
