# engenheiro-devops · Relatórios State of DevOps
> Quando carregar: citar ou interpretar um "State of DevOps"; localizar o time em um modelo de maturidade; discutir platform engineering; montar plano trimestral de capacidades; justificar prática de entrega perante risco, auditoria ou liderança em contexto de banco.

## Famílias de relatório e como citar
Contexto: "State of DevOps" nomeia pelo menos duas famílias de relatório com editores, metodologias e anos diferentes; citar só o nome do título é citação inválida.
- **Puppet, State of DevOps Report** — editor Puppet (hoje Puppet by Perforce). Edições e parceiros, conforme as fontes consultadas em 11/10/2026: **2018** escrito por Puppet e Splunk, patrocinado por AWS, Cloudability, Cognizant, CyberArk, Diaxion, Eficode e Splunk (press release Puppet/Perforce, 12/09/2018); **2019** apresentado por Puppet, CircleCI e Splunk, tema: segurança integrada à entrega (página do relatório na Splunk); **2020** Puppet, nono ano da pesquisa, temas: plataformas internas e gestão de mudanças (InfoQ, 21/11/2020); **2021** Puppet, décimo ano, patrocínio da CD Foundation com apoio de Armory, CircleCI e Snyk (blog da CD Foundation, 21/07/2021); **2023** publicado como *State of Platform Engineering Report*, 11ª edição (puppet.com); **2024** *State of DevOps Report 2024: The Evolution of Platform Engineering*, também chamado "Platform Engineering Edition" (blog puppet.com, 2024). Não há edição Puppet de 2022 nas fontes consultadas.
- **DORA/Google Cloud, Accelerate State of DevOps Report** — editor DORA, programa de pesquisa do Google Cloud. Lista oficial (dora.dev/publications, consultada em 11/10/2026): *State of DevOps Report* **2014, 2015, 2016 e 2017**, publicados pela DORA com a Puppet; *Accelerate State of DevOps Report* **2018, 2019, 2021, 2022, 2023 e 2024**; em **2025** o relatório passou a se chamar *State of AI-assisted Software Development*. **Não houve relatório em 2020** (a entrada de 2020 é o whitepaper *The ROI of DevOps Transformation*).
- **Puppet, State of Platform Engineering** — *State of Platform Engineering Report*, 2023, apresentado pela Puppet como a 11ª edição do State of DevOps Report (puppet.com/resources/state-of-devops-report); a edição 2024 manteve o foco (*The Evolution of Platform Engineering*).
- **Livro:** Forsgren, Humble, Kim, "Accelerate: The Science of Lean Software and DevOps" (IT Revolution, 2018) — base conceitual das métricas (ver `references/dora-metrics.md`).
- **Formato de citação (obrigatório):** `(relatório, editor, ano/edição, seção ou página)`. Exemplos: "Puppet, State of DevOps Report, 2021, <seção>"; "DORA/Google Cloud, Accelerate State of DevOps Report, 2023, <seção>". Frases como "segundo o State of DevOps" ou "a pesquisa mostra" não valem.
- A estação de trabalho só alcança o GitHub: o relatório é lido por humano e a citação registrada em `docs/` com a página; o agente não confirma número por busca na web.

## O que cada família mede
Contexto: cada família responde a uma pergunta diferente, e misturá-las gera comparação sem sentido.
- **DORA/Google Cloud:** desempenho de entrega de software (vazão e estabilidade), operação/confiabilidade e as **capacidades** técnicas, de processo e culturais associadas a esses resultados. É a fonte das métricas e dos níveis (Elite/High/Medium/Low); limiares variam por edição (`references/dora-metrics.md § Faixas por nível`).
- **Puppet (State of DevOps):** práticas de DevOps e **evolução organizacional** — um modelo por estágios de como a organização amadurece (próxima seção), com foco em automação, padronização e plataformas.
- **Metodologia:** são pesquisas (surveys) com respondentes autodeclarados; mostram associação, não prova de causa no seu contexto. A Puppet 2018 descreve questionário oferecido em inglês e mais quatro idiomas, com análise estatística para derivar os estágios; a DORA mantém capítulo "Methodology" em cada edição — leia metodologia e demografia da edição antes de citar amostra. O efeito no seu time só se prova medindo (oráculo abaixo).
- Nenhum percentual, tamanho de amostra ou "X vezes melhor" deve ser reproduzido sem (relatório, editor, ano, página); número que o agente não leu na edição recebe a marca `<ler na edição citada>` até um humano o ler.

## Modelo de evolução por estágios da Puppet
Contexto: o *2018 State of DevOps Report* (Puppet) descreve a evolução em estágios sucessivos — **Stage 0: Build the foundation; Stage 1: Normalize the technology stack; Stage 2: Standardize and reduce variability; Stage 3: Expand DevOps practices; Stage 4: Automate infrastructure delivery; Stage 5: Provide self-service capabilities** — e nomeia cinco práticas de fundação: *Configure Monitoring and Alerts*, *Reuse Deployment Patterns*, *Implement a Configuration Management Tool*, *Reuse Test Patterns*, *Empower Teams* (puppet.com, "DevOps foundations"). Use os nomes em inglês ao citar, porque são o que o leitor do relatório procura.

| Estágio | O que muda (de → para) | Evidência medida no repo |
|---|---|---|
| Build the foundation (base) | de práticas ad hoc → controle de versão, build reprodutível, pipeline como código | `./mvnw` em todo repo; workflow versionado; nada configurado só na UI |
| Normalize the technology stack | de stacks heterogêneas → poucas tecnologias e versões suportadas | inventário de runtimes/versões (Java, Spring Boot, imagens base); Renovate ativo |
| Standardize and reduce variability | de cada time com seu pipeline → caminhos padrão reutilizáveis | workflow reutilizável (`workflow_call`) adotado por N de M repos; `quality-budget.yaml` por serviço |
| Expand DevOps practices | de práticas em alguns times → testes, segurança, observabilidade e flags em todos | GATE 2 no pipeline; eventos DORA coletados; `05b-veracode.md` por entrega |
| Automate infrastructure delivery | de infraestrutura por tickets/console → IaC aplicada por pipeline | Terraform com `plan` no PR e `apply` só por pipeline com aprovação; zero mudança manual em prod |
| Provide self-service capabilities | de pedir ao time central → equipes consomem capacidades por conta própria | criar serviço novo a partir de template, sem ticket, com controles embutidos |

- Estágios são **sequenciais por dependência**: automatizar infraestrutura sobre uma stack não normalizada multiplica a variabilidade em vez de reduzi-la.
- Um mesmo banco pode estar em estágios diferentes por domínio (core legado vs. canais digitais); localize **por serviço ou por domínio**, não pela empresa inteira.

## Como um time de banco se localiza
Contexto: a localização é um diagnóstico com evidência, não uma autodeclaração; cada estágio só é "cumprido" quando a evidência da tabela acima existe e foi medida.
1. Para cada estágio, responda com um comando ou consulta (ex.: quantos repos usam o workflow padrão; quantos aplicam Terraform fora do pipeline). Resposta "achamos que sim" conta como não.
2. O estágio do time é o **último com evidência completa**; o seguinte é o candidato do trimestre.
3. Self-service em banco não é ausência de controle: significa guardrails como código (políticas, aprovações, trilha) executados no caminho padrão. Se o caminho padrão é mais lento que o desvio, o desvio vence — meça os dois.
4. Registre a localização em `docs/` com data e as consultas; reavalie por trimestre.

## Platform engineering nas edições recentes
Contexto: platform engineering é o tema central das edições Puppet de 2023 (*State of Platform Engineering Report*) e 2024 (*The Evolution of Platform Engineering*); a Puppet 2020 já associava evolução DevOps ao uso de plataformas internas (InfoQ, 21/11/2020). O *2024 Accelerate State of DevOps Report* (DORA) traz a seção "Platform Engineering Offers A Boost But Not For Everyone": ganhos de produtividade e desempenho organizacional quando bem feita, maiores em organizações grandes, com quedas de desempenho durante a iniciativa e risco de a plataforma virar obstáculo (InfoQ, 11/2024). Leia a seção original, inclusive as ressalvas, antes de defender ou criticar a prática.
- **O que é:** disciplina de construir e operar uma **plataforma interna de desenvolvimento** (caminhos padrão, templates, pipelines, ambientes, catálogo) tratada como **produto**: usuários são os desenvolvedores, há roadmap, SLO da própria plataforma e medição de adoção.
- **O que NÃO é:**
  - não é um "time de DevOps central" renomeado, que recebe tickets e opera pelos outros;
  - não é isentar o time de produto de operar o que construiu (a equipe dona do serviço continua dona do SLO e do plantão);
  - não é "instalar um portal" (um portal como o Backstage é ferramenta, não a plataforma);
  - não é padronização imposta sem caminho de saída documentado nem sem medir adoção.
- **Como medir (no repo):** tempo para o primeiro deploy de um serviço novo; fração de repos no caminho padrão; lead time dos serviços dentro vs. fora da plataforma; chamados ao time da plataforma por serviço (queda = autonomia).
- **Em banco:** a plataforma é o lugar natural para embutir controles (SBOM, scan, aprovação de produção, trilha) uma vez só, em vez de por squad.

## Recorte financeiro — indústrias altamente reguladas
Contexto: nas fontes consultadas, serviços financeiros aparece como **categoria de respondentes** — na Puppet 2020 foi a segunda maior, atrás de tecnologia (InfoQ, 21/11/2020) —, não como capítulo próprio; a Puppet 2024 destaca que, para a maioria dos respondentes, segurança entrou na plataforma desde o início (blog puppet.com, 2024). Descreva o tipo de achado e **nunca** reproduza um número sem leitura humana da edição: todo valor citado leva (relatório, editor, ano, página) ou a marca `<ler na edição citada>`.
- **Roteiro de leitura** (o que procurar na edição, nesta ordem):
  1. comparação de desempenho de entrega entre setores regulados e não regulados, e se o relatório a apresenta como diferença ou como equivalência;
  2. tratamento de **aprovação de mudança**: aprovação externa pesada vs. revisão por pares com automação como evidência;
  3. **segregação de funções** e conformidade como código (evidência gerada pelo pipeline);
  4. **legado** e arquitetura fortemente acoplada como limitador de frequência e lead time;
  5. segurança na cadeia de entrega (SBOM, scan, dependências).
- **Tradução para o banco:** aprovação humana em produção continua (GATE humano), mas a evidência chega pronta do pipeline (GATE 2, `05b-veracode.md`, SBOM); a revisão por pares via PR com branch protegida atende segregação **se o autor não puder aprovar o próprio PR** — validar com Compliance/Auditoria.
- **Janelas e legado:** a janela de mudança limita frequência por política; meça a espera à parte (`references/dora-metrics.md § Armadilhas`) para não atribuir ao time o que é calendário.
- **Cuidado de citação:** achado de "indústria regulada" sem edição, ano e página não entra em documento de risco ou de auditoria.

## Qual relatório responde a qual pergunta
Contexto: antes de abrir um relatório, escreva a pergunta do time; isso evita buscar no relatório errado e importar o número errado.

| Pergunta do time | Família | O que ler na edição | Como medir no repo |
|---|---|---|---|
| Entregamos rápido e com estabilidade? | DORA/Google Cloud | definição das métricas e faixas por nível | `references/dora-metrics.md` |
| Quais práticas explicam a diferença entre equipes? | DORA/Google Cloud | catálogo de capacidades | presença da prática no pipeline (consulta por capacidade) |
| Em que estágio de evolução estamos? | Puppet | modelo de estágios | tabela de evidências em "Modelo de evolução" |
| Vale montar uma plataforma interna? | Puppet e DORA/Google Cloud (edições recentes) | seção de platform engineering, com ressalvas | tempo do primeiro deploy, adoção do caminho padrão |
| Como bancos/regulados se comportam? | ambas | recorte por setor e por regulação | espera por janela e por aprovação, medida à parte |

- Estágio e métrica se complementam: o estágio diz **qual prática construir**; a métrica DORA diz **se a construção melhorou a entrega**. Mudar de estágio sem mexer em nenhuma métrica é sinal de ritual, não de evolução.

## Registro de leitura de um relatório
Contexto: como o agente não confirma números por busca, o humano que leu o relatório deixa um registro curto que torna as citações verificáveis por quem vier depois.
- Arquivo `docs/leituras/<relatorio>-<ano>.md`, uma tabela com: relatório, editor, ano/edição, seção ou página, afirmação resumida **em palavras próprias**, definição da métrica naquela edição, metodologia/amostra (**<como descrita na edição>**), data e autor da leitura.
- Mudou a definição entre edições (ex.: nome da métrica de recuperação, número de níveis)? Anote a diferença; comparar edições sem anotar isso produz tendência falsa.
- A leitura não autoriza mudança por si só: vira hipótese no plano trimestral e segue o GATE 1.

## Como usar um relatório sem cargo cult
Contexto: relatório é fonte de hipóteses; a decisão sai da medição do próprio time.
- **Linha de base própria primeiro** (≥ 4 semanas, ver `references/dora-metrics.md`); depois compare consigo mesmo, trimestre a trimestre.
- **No máximo 1–2 capacidades por trimestre.** Nomes de capacidades do catálogo da DORA (confirmar a lista na edição/site vigente): trunk-based development, continuous integration, test automation, deployment automation, monitoring and observability, loosely coupled architecture.
- Cada capacidade escolhida vem com **hipótese, métrica medida, critério de saída e data de revisão**.
- Não copie percentuais para slide; não rotule o time "Elite" ou "Low" por analogia; não compare squads entre si.
- Mudança de prática passa pelo GATE 1 (plano com oráculo por passo) e produção só com aprovação humana.

## Plano trimestral — modelo
Contexto: um quadro por trimestre, no máximo duas linhas; célula com `<...>` não preenchida reprova o plano.

| Capacidade | Hipótese | Métrica de baseline (medida) | Consulta/fonte | Critério de saída | Revisão |
|---|---|---|---|---|---|
| <capacidade 1> | <o que deve melhorar e por quê> | <valor medido, n, janela ≥ 4 semanas> | <caminho do script ou query> | <direção + guarda-corpo> | <data> |
| <capacidade 2, opcional> | ... | ... | ... | ... | ... |

- Exemplo de preenchimento sem número inventado: capacidade "test automation"; baseline "reruns por semana no CI (consulta em `dora/eventos.jsonl` ou log do job), `n` e semanas"; saída "mediana fora do intervalo semanal da baseline, CFR não pior".
- Lições do trimestre vão para `memory/error_ledger.jsonl` e para o `aprendizado-continuo` (promoção gated, nunca automática).

## Oráculo — como provar que foi feito
Contexto: o GATE 2 verifica citações e plano trimestral por comando e por artefato, não por leitura.
- **Citação:** toda menção a relatório traz editor e ano; este comando sai com exit 1 se houver menção sem eles:

```bash
f=docs/plano-trimestral.md   # ajuste o caminho
if grep -nE 'State of DevOps' "$f" | grep -vE '(Puppet|DORA|Google Cloud)[^|]*(19|20)[0-9]{2}'; then
  echo "VIOLACAO: citacao sem editor+ano"; exit 1; fi
```
- **Plano:** no máximo duas linhas de capacidade; nenhuma célula `<...>` restante; baseline com consulta, `n` e janela ≥ 4 semanas (saída de script, não prosa).
- **Número:** nenhum percentual ou tamanho de amostra de relatório sem `<confirmado em: relatório, editor, ano, página>`.
- **Localização por estágio:** cada "cumprido" aponta a consulta que o prova.

## Anti-padrões
Contexto: formas recorrentes de usar mal um relatório State of DevOps.
- **Cargo cult de percentuais:** reproduzir números do relatório como se fossem do seu time.
- **Citação sem capa:** "segundo o State of DevOps", sem editor, ano e página.
- **Estágio-troféu:** declarar "estamos no último estágio" sem evidência medida.
- **Pulo de estágio:** automatizar infraestrutura sem normalizar a stack.
- **Plataforma = DevOps central renomeado:** fila de tickets com nome novo.
- **Plano lista de desejos:** dez capacidades no trimestre, nenhuma concluída.
- **Benchmark entre squads:** transformar métrica de aprendizado em ranking.
- **Cherry-picking:** escolher a edição ou o recorte que favorece a conclusão já decidida.

## Checklist de banco
Contexto: condições de banco para citar relatórios e planejar capacidades sem violar regulação, segregação ou sigilo.
- [ ] Regulatório: achado de "indústria regulada" citado só com edição, ano e página; qualquer norma aplicável confirmada com Compliance.
- [ ] Janela de mudança: espera por janela medida à parte; meta de vazão não força mudança fora de janela.
- [ ] Segregação de ambientes e de funções: autor não aprova o próprio PR; produção só com aprovação humana explícita.
- [ ] Dados sensíveis: planos e relatórios sem dados de cliente, segredo ou URL interna.
- [ ] Trilha de auditoria: localização por estágio, plano trimestral e consultas versionados em `docs/`, revisados por PR.
