# Revisão e limpeza de código gerado por IA

Código escrito por agente costuma funcionar e, mesmo assim, crescer demais: wrappers que só
repassam chamadas, comentários que repetem o código, `try/except` genérico "por segurança",
parâmetros que nunca variam, testes que só exercitam o caminho feliz. Este roteiro serve para
revisar ou enxugar esse tipo de entrega sem trocar um problema por outro.

## 1. Classifique antes de editar

Leia o trecho inteiro e rotule cada achado em **uma** destas cinco categorias. Achado que não
cabe em nenhuma provavelmente é gosto pessoal — descarte.

| Categoria | Sinais típicos em código de agente |
|---|---|
| **Duplicação** | o mesmo bloco reescrito em vez de reaproveitado; helpers quase iguais em arquivos vizinhos |
| **Código morto** | funções/flags sem chamador, ramos impossíveis, imports e parâmetros que nada usa, TODO "para o futuro" |
| **Abstração desnecessária** | interface com um único implementador, wrapper de repasse, fábrica para um tipo só, config para um valor que nunca muda |
| **Violação de fronteira** | camada de domínio importando infraestrutura, util genérico que conhece regra de negócio, erro engolido longe de quem sabe tratá-lo |
| **Teste ausente** | comportamento novo sem teste, teste que só confere que "não lançou exceção", mock que testa o mock |

## 2. Trave o comportamento

Antes da primeira edição, garanta um teste que falharia se o comportamento observável mudasse.
Se não houver, escreva um teste de caracterização (o que o código faz hoje, certo ou errado).
Sem essa trava, limpeza vira reescrita às cegas.

## 3. Passadas isoladas, sempre nesta ordem

Cada passada é um passo pequeno com verificação (testes verdes) ao final. Não misture passadas
no mesmo diff — se algo quebrar, você sabe qual delas foi.

- **Passada 1 — remover o morto.** Apague o que não tem chamador nem efeito. É a passada mais
  barata e diminui a superfície das seguintes.
- **Passada 2 — deduplicar.** Una os blocos repetidos que sobraram; desfaça abstrações de um
  implementador só, trazendo o código de volta para quem o usa.
- **Passada 3 — nomes, erros e fronteiras.** Renomeie pelo domínio, troque `except` genérico
  por tratamento no nível que entende o erro, devolva cada responsabilidade à sua camada.
- **Passada 4 — reforçar testes.** Feche as lacunas da categoria "teste ausente" e troque
  asserções vazias por asserções sobre resultado.

Na dúvida entre adicionar e apagar, apague. O diff de uma boa limpeza costuma ter saldo negativo
de linhas.

## 4. Quem escreveu não aprova a própria limpeza

No Modo Revisão, o agente (ou pessoa) que gerou o código não aprova a própria limpeza: o
veredito final vem de outra passada de revisão — `tech-lead-review` ou outro revisor — com os
testes da etapa 2 como evidência.

## Quando parar

Pare quando as cinco categorias não tiverem achado de impacto real. Não persiga estilo: o
objetivo é remover o excesso que o gerador deixou, não reescrever o código no seu gosto.
