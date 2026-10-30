# Referência — Aurora DSQL: diagnóstico de consulta lenta (plano, DPU e reescritas)

> Parte da skill `especialista-banco`. Carregue quando o alvo for **Amazon Aurora DSQL** e o pedido for
> "query lenta", "custo de DPU alto", "por que full scan?" ou interpretar um `EXPLAIN`. Hub: `../SKILL.md`.
> Complementa `aurora-dsql.md` (OCC, limites, DDL), que não trata de plano de execução.
> Proveniência: técnicas reescritas a partir de `awslabs/agent-plugins` (Apache-2.0), skill
> `databases-on-aws/dsql`, pasta `references/query-plan`. Nenhum trecho copiado — ver `docs/ATTRIBUTIONS.md`.
> Comportamento do otimizador muda com o serviço: confirme no cluster (`SHOW`, catálogo) antes de afirmar.

## 1. Fluxo em quatro passos

1. **Capturar o plano fresco** no cluster, sempre — mesmo que o usuário descreva ou cole um plano.
   Consulta já reportada como cara (>30 s, DPU alto, timeout): comece com `EXPLAIN` simples (não
   executa) e só depois `EXPLAIN ANALYZE VERBOSE`. Demais casos: direto o `ANALYZE VERBOSE`.
   Extraia: tempo de planejamento, tempo de execução e o bloco *Statement DPU Estimate*.
2. **Juntar evidência** no catálogo: tamanho (`pg_class`), distribuição (`pg_stats`), índices
   (`pg_indexes`), `COUNT(*)` e `COUNT(DISTINCT)` das colunas do filtro.
3. **Experimentar** (só se a consulta original levou ≤ 30 s): variante de join forçado (§5).
4. **Entregar relatório**: gargalo principal, evidência (estimado × real), recomendação com SQL
   antes/depois e impacto esperado. Depois da mudança, **reavaliar** e anexar um adendo
   antes/depois ao mesmo relatório, em vez de abrir outro.

Segurança do passo 1: plano só em modo **somente leitura**. `UPDATE`/`DELETE` são reescritos para o
`SELECT` equivalente (mesma cadeia de joins e `WHERE`); `INSERT`, blocos `DO` e funções são recusados.
Nunca use o modo de escrita da ferramenta SQL só para obter plano. Erro de `EXPLAIN` (tabela ou
coluna inexistente) é relatado literalmente — não invente "semântica DSQL" como causa.

## 2. Lendo o plano DSQL

Os dados ficam em B-Trees; índice secundário também. Além dos nós do PostgreSQL, há nós de
armazenamento: *Full Scan (btree-table)*, *Storage Scan*, *B-Tree Scan*, *Storage Lookup* e
*B-Tree Lookup*. Estrutura em camadas: um scan lógico vira *Storage Scan* com *B-Tree Scan* como
filho. Já o *Index Scan* ganha um ramo **paralelo** de *Storage Lookup* para as colunas que o índice
não cobre. O tempo e as linhas de um filho somam no pai, nunca no ramo irmão.

### 2.1 Três camadas de filtro (a principal alavanca)

| Nível | Onde aparece | Dado trafegado | Como chegar lá |
|---|---|---|---|
| 1 (melhor) | `Index Cond:` no nó de scan | só entradas do índice que casam | igualdade/intervalo em chave do índice, coluna mais seletiva à esquerda |
| 2 | `Filters:` dentro de *Storage Scan/Lookup* | reduzido (filtra no storage) | colocar a coluna do filtro em `INCLUDE` do índice |
| 3 (pior) | `Filter:` acima do *Storage Scan* | tudo atravessa a rede antes do filtro | índice novo, consulta reestruturada ou mudança de schema |

Meta: empurrar predicados do nível 3 → 2 → 1; cada degrau corta transferência, latência e DPU.

### 2.2 Storage Lookup e colunas `INCLUDE`

*Storage Lookup* significa que o índice resolveu o filtro, mas faltaram colunas projetadas: há uma
ida extra ao storage por linha. Correção: criar o índice com as colunas faltantes em `INCLUDE`
(`CREATE INDEX ASYNC ...`), para virar *Index Only Scan*. Custo: as colunas são copiadas em cada
entrada do índice — inclua só o que os caminhos mais consultados precisam. Sinal de alerta: total de
I/O de lookup (`linhas reais × loops`) acima de ~10 000.

### 2.3 Aritmética que evita erro de leitura

- `actual time` é **por iteração**: duração do nó = `tempo_final × loops`. Ordene os nós por duração
  total e comece pelo mais caro.
- **Erro de estimativa** = razão estimado × real: 2–5× menor (anotar); 5–50× significativo (olhar
  estatísticas); 50×+ severo (predicados correlacionados ou estatística velha). Registre nó, tabela,
  método de acesso e filtros de cada caso relevante.
- **Amplificação em Nested Loop**: se o lado externo veio muito maior que o estimado, o custo do lado
  interno cresce na mesma proporção (tempo por loop × linhas reais do externo). Hash ou Merge Join
  teriam sido melhores naquela cardinalidade.
- **Desperdício de filtro** = removidas ÷ (removidas + retornadas): <10% desprezível; 10–50% considere
  índice composto; >50% forte candidato a empurrar o filtro para o índice. Dentro de loops, multiplique
  por `loops`.
- **Hash que "cresceu"** (`Buckets: originally N, now M`) indica subestimação do lado de construção;
  rastreie até o scan de origem.
- **Custo (`startup..total`)**: nos planos DSQL parece alto de propósito (modela idas e voltas
  distribuídas; ~100 de partida é normal). Não compare custos entre consultas — a métrica de
  antes/depois é o **DPU** (e o *Read DPU* é o sinal principal em leitura: alto com filtro seletivo
  significa filtro no nível 2 ou 3 quando poderia estar no 1). Tempo de relógio oscila com a carga.
- **Valores impossíveis** (nó com linhas reais ≥ 10× o total da tabela, comum em *Storage Lookup* com
  muitos loops): costuma ser defeito só do relatório do `EXPLAIN`. Confirme que o resultado da query
  está correto, sinalize como possível bug do serviço e prepare um pedido de suporte.
- **Projeções largas** (`SELECT *`, tabela com 50+ colunas ou linha >5 KB) aumentam I/O nos lookups e
  memória nos hash joins.

## 3. Índice existe e não é usado: coerção de tipo

Suspeite quando **todas** valem: há índice cuja primeira coluna é a do `WHERE`; o plano faz *Full
Scan*; o tipo do literal difere do tipo declarado da coluna; e o catálogo de operadores B-Tree
(`pg_amop`) não registra o par de tipos. Sem operador cruzado registrado, o planejador aplica cast
linha a linha e perde a ordenação do índice: resultado correto, desempenho péssimo.

- No momento da fonte, o cruzamento só é aceito dentro da família de inteiros (smallint/integer/
  bigint); texto, numeric, uuid, timestamp, date, boolean etc. exigem tipo idêntico. **Não afirme isso
  ao usuário sem consultar `pg_amop` no cluster** — o serviço pode ampliar o suporte.
- Correção: cast explícito do **literal** (`WHERE col = 42::integer`) e, na aplicação, parâmetros com o
  tipo certo (em Java/JDBC, bind com `setInt`/`setLong`/`setObject` do tipo da coluna, não `String`).
  **Não altere o tipo da coluna** para acomodar o predicado: mascara a causa e pode quebrar outras queries.
- Quantifique pela amplificação de scan: linhas processadas no *Full Scan* ÷ linhas esperadas pela
  seletividade em `pg_stats`.

## 4. Reescritas que valem tentar (conforme o padrão no plano)

| Padrão observado | Reescrita |
|---|---|
| vários `OR` na mesma coluna | `IN (...)` |
| `LEFT JOIN` com `WHERE` que rejeita nulo da tabela da direita | `INNER JOIN` |
| filtro numa coluna de join que não chega à outra tabela | repetir o filtro dos dois lados |
| `IN (subconsulta)`, `EXISTS` correlacionado, subconsulta escalar correlacionada no `SELECT` | desaninhar em join (ou join com agregação prévia) |
| função/conta aplicada à coluna indexada no predicado | mover a conta para o lado constante |
| `GROUP BY` depois de join com colunas de dimensão | agregar na subconsulta antes do join |
| `NOT IN` com subconsulta grande ou anulável | `NOT EXISTS` (também corrige a armadilha do `NULL`) |
| `UNION ALL` aninhado | achatar |
| `COUNT(*)` estourando tempo em tabela enorme e contagem aproximada aceitável | ler `reltuples` de `pg_class` com `GREATEST(reltuples, 0)`; avise que pode estar defasado (e `-1` = nunca analisada). Se a contagem tem de ser exata, não aplicar |
| joins em número acima do limiar de programação dinâmica | dividir em CTEs com até o limiar de tabelas cada e juntar os resultados; **leia o limiar no cluster** com `SHOW join_collapse_limit` |
| `LIMIT` pequeno + ordenação + colunas fora do índice, com *Storage Lookup* de muitos loops | **materialização tardia**: CTE que acha as N chaves só com colunas do índice, depois join para buscar o resto |

Sempre apresente SQL original e reescrito lado a lado e diga quando a reescrita **não** se aplica
(ex.: filtro já seletivo, todas as colunas já no índice, contagem exata exigida).

## 5. Experimentos de planejador (somente se a consulta original ≤ 30 s)

- **Linha de base**: o `EXPLAIN ANALYZE VERBOSE` normal.
- **Só merge join**: `SET LOCAL` desligando hash join e nested loop e ligando merge join, seguido do
  `EXPLAIN ANALYZE VERBOSE`, **numa única transação** (cada experimento em chamada própria, para o
  `SET LOCAL` não vazar). O SQL do usuário entra como um único item da lista — nunca concatenado em
  outra string — e precisa começar por `SELECT`. Qualquer falha: parar e relatar, sem SQL de recuperação.
- Compare tempo, DPU, linhas varridas e estrutura. Se a alternativa for mais rápida, o modelo de custo
  escolheu mal; se for mais lenta, a escolha original estava certa apesar do erro de estimativa.
- Se o planejador **usou a estratégia desligada mesmo assim** (penalidade ~10 bilhões somada ao custo),
  não há alternativa viável: o problema é o padrão de acesso (full scan, falta de índice), não o join.
- **Acima de 30 s**: não rode; registre no relatório que foi pulado e entregue o SQL manual (`SET` de
  sessão + `EXPLAIN ANALYZE VERBOSE`) para o cliente testar no `psql`.
- **Predicado redundante**: o otimizador infere por transitividade (`A=B` e `B=C` ⇒ `A=C`; `B=42` ⇒
  `A=42`), mas **não** regra de negócio (ex.: "pedidos de um usuário têm o mesmo tenant do usuário").
  Se a regra existe e casaria o início de um índice composto, escreva o predicado explicitamente e
  compare com o original.

## 6. Checklist rápido P1.DB para DSQL

- [ ] Plano capturado fresco, em modo somente leitura; DML convertido para `SELECT`.
- [ ] Métrica de comparação = DPU total (antes/depois), não custo nem tempo isolado.
- [ ] Predicados do filtro estão no nível 1 sempre que possível; `Storage Lookup` justificado ou eliminado por `INCLUDE`.
- [ ] Tipos dos parâmetros da aplicação iguais aos das colunas indexadas (sem coerção).
- [ ] Erros de estimativa ≥ 5× investigados (estatística velha ou predicados correlacionados).
- [ ] Reescrita proposta traz original × novo e a condição em que não se aplica.
- [ ] Relatório inclui o convite para reavaliar após a mudança.
