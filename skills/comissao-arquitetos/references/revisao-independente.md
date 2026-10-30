# Revisão independente pré-GATE 1

**Por quê.** Quem produziu não enxerga o que pressupôs. No caso de referência, 6 especialistas + 3 rodadas deixaram passar: (1) o timeout de 30 s da integração do API Gateway HTTP contra uma Step Function dimensionada para 290 s; (2) 15 resíduos de versão (v2 → v2.1 não propagada); (3) uma soma errada; (4) um desvio de requisito ("a SF acessa o OneDrive") não apresentado ao usuário. O revisor independente pegou todos em uma passada.

## Regras
1. Agente **novo** (não retome nenhum membro da comissão).
2. Lê **só o produto final** (SPEC, PLANO, ADRs, README). **Proibido** ler a pasta `comissao/` — o raciocínio contamina.
3. Recebe os **critérios do usuário verbatim**, numerados.
4. Não edita nada; grava um relatório.

## Prompt
```
Você é o revisor independente (não participou da produção) de um PLANO + SPEC.
Carregue `tech-lead-review`. Leia, nesta ordem: <README>, <SPEC>, <PLANO>, <ADRs>. Não leia <comissao/>.
Critérios de aceite do usuário, verbatim: 1. ... 9. ...
Produza:
A) Matriz de cobertura: critério × COBERTO/PARCIAL/AUSENTE × onde × o que falta.
B) Consistência interna: contradições entre SPEC, PLANO e ADRs (nomes, chaves, enums, limites, contagens), com arquivo:seção.
C) Erros técnicos sobre a plataforma, com confiança (alta/média/"suspeito").
D) Buracos que um dev encontraria ao construir (top 10 por impacto).
E) Veredito: PRONTO / PRONTO COM AJUSTES (lista ordenada) / NÃO PRONTO.
Grave em <caminho> e responda com 10 linhas.
```

## O que ela costuma achar (checklist para o motor antecipar)
- Limites de serviço cruzados (timeout do gateway × duração do workflow; payload; tamanho de saída de Map/estado).
- Chave/hash com campo opcional (data nula → chave indefinida → idempotência quebrada).
- Campo do contrato sem fonte no modelo de dados (ex.: "evidências de <data>" sem item que guarde a data).
- Enum usado no texto mas ausente da lista de enums (ex.: status `GRAVADA`).
- Mesma palavra com dois significados entre documentos (ex.: "Fase 2").
- Requisito do usuário reinterpretado sem pergunta explícita.
- Arquivo de entrada citado pelo usuário que a spec troca por outro sem dizer por quê.
- Ferramenta de teste que não cobre um tipo de estado (ex.: `TestState` não executa `Map`).

## Depois da revisão
Aplicar **todos** os 🔴 e 🟡; 🔵 viram "decisão de implementação" com aceite na tarefa. Subir versão (v2.2), registrar na ata, e só então o GATE 1.
