# Papéis da comissão — catálogo e adaptação

Regra: **ortogonais, não redundantes**. Cada papel responde a perguntas que os outros não respondem. Seis é o teto útil; mais que isso vira ruído e custo.

| Papel | Doutrina (skill) | Pergunta que só ele responde | Entregáveis mínimos | Modelo |
|---|---|---|---|---|
| **A Minimalista** | `arquiteto-minimalista` | "Qual é o menor conjunto de peças que cumpre o pedido? O que NÃO entra?" | topologia mínima (contagem de peças), gatilho objetivo para a 1ª peça extra (ex.: Lambda), vetos | opus |
| **B Plataforma & FinOps** | `arquiteto-cloud-aws` (ou a nuvem do projeto) | "Isso existe, quanto custa e onde quebra?" | fatos com **URL oficial**, tabela de custo por 3 cenários de volume, limites (timeout, payload, free tier), latência | opus/sonnet |
| **C Segurança & Privacidade** | `engenheiro-seguranca` | "O que vaza, quem entra, o que a lei/política exige?" | STRIDE ≤ 8 linhas, minimização de dados, controles 🔴 (GATE 2) vs 🟠 com custo/esforço | opus |
| **D UX/Frontend** | `ui-ux-pro-max` / `especialista-frontend` | "O que a tela precisa receber para não ter regra de negócio no cliente?" | estrutura e estados da tela, **contrato JSON** com exemplo, wireframe textual, A11y | sonnet |
| **E Domínio & Dados** | `engenheiro-especificacao` (+ `especialista-banco`) | "Quais são as entidades, as regras e os dados iniciais — e o que é fato vs hipótese?" | glossário, modelo de dados com padrões de acesso, templates de API, regras de seed FATO/HIPÓTESE, casos de borda como fixtures | sonnet/opus |
| **F Ad hoc** | a tecnologia/abordagem que o usuário trouxe | "Isso ajuda de verdade aqui? Com que evidência?" | inventário de onde ajuda/não ajuda, custo, condição de adoção (benchmark), vetos | sonnet |
| **Revisor independente** | `tech-lead-review` | "O produto final cobre o que o usuário pediu, verbatim?" | ver `revisao-independente.md` | opus |

## Adaptação por projeto
- Sem frontend → troque D por **Operação/Observabilidade** (`engenheiro-devops`).
- Integração pesada → E ganha `arquiteto-dados-streaming`; B foca em contratos/limites de terceiros.
- Java/Lambda → B usa `aws-lambda-java25-aot` como doutrina secundária.
- Usuário cita uma tecnologia específica ("avalie X") → **sempre** um papel F dedicado; nunca diluir em outro papel.

## Erros que o caso real mostrou
- Papel F chegou depois (ajuste do usuário em voo): o brief ganhou um **adendo §7** com os fatos já levantados (ex.: lidos do repo da Squad) para o F não começar do zero.
- B e A concordavam e C discordava (REST × HTTP API): o motor decidiu por P1, mas **incorporou as preocupações de C como mitigações nomeadas** — C aprovou na R2. Arbitrar não é descartar.
