# Referência — Aurora DSQL (PostgreSQL distribuído serverless: OCC, limites e DDL)

> Parte da skill `especialista-banco`. Carregue sob demanda quando o alvo for **Amazon Aurora DSQL**
> (não Aurora PostgreSQL clássico). Hub: `../SKILL.md`. Para failover multi-região, ver
> `../../arquiteto-cloud-aws/references/aurora-dsql-failover.md`.
> Proveniência: técnicas reescritas a partir de `awslabs/agent-plugins` (Apache-2.0), skill
> `databases-on-aws/dsql`. Nenhum trecho copiado — ver `docs/ATTRIBUTIONS.md`.
> Valores numéricos mudam com o serviço: confirme na página oficial de quotas antes de decisão cara.

## 1. Quando escolher (e quando não)

| Situação | Escolha | Por quê |
|---|---|---|
| OLTP relacional multi-região ativo-ativo, sem servidor para dimensionar | **DSQL** | Escrita distribuída com consistência forte, sem cluster para dimensionar |
| Muito `serial`, arrays, procedures, `CREATE DATABASE`, extensões variadas | Aurora PostgreSQL clássico | DSQL recusa esses recursos (ver §4) |
| Linhas "quentes" (contador global, saldo único) com alta concorrência | Repensar o modelo ou outro motor | Concorrência otimista transforma contenção em retentativa (ver §2) |

## 2. Concorrência otimista (OCC): toda escrita precisa de retry

DSQL não trava linhas: valida no `COMMIT`. Se outra transação mexeu nas mesmas linhas, o commit
falha com SQLSTATE `40001`. Regras:

1. **Retry é obrigatório** em todo caminho de escrita, e também de leitura (ver `OC001` abaixo).
   Prefira os conectores oficiais do DSQL (JDBC, Python, Node), que já trazem retry e token IAM.
2. **Só `40001` é retentável.** Violação de FK (`23503`) e demais erros sobem imediatamente.
3. **Backoff exponencial com jitter**, teto baixo: ~5 tentativas, base ~50 ms, atraso máximo ~5 s
   (bem abaixo do limite de 5 min por transação).
4. **Dois sabores de `40001`**, distintos pelo marcador no fim da mensagem:
   - `OC000` — conflito de escrita real; o backoff resolve.
   - `OC001` — o catálogo de schema em cache da sessão ficou velho porque *qualquer* mudança de
     catálogo foi confirmada (`CREATE`/`ALTER`/`DROP`, mas também `GRANT`/`REVOKE`). Fica no loop de
     retry também: a primeira retentativa atualiza o cache. Se persistir, alguém continua mudando
     o catálogo — serialize as migrações em vez de aumentar tentativas.
   Registre o marcador a cada tentativa; sem ele, um loop esgotado não diz qual das duas causas era.
5. **Não alimente o loop com queda de conexão** (`SSL SYSCALL error: EOF detected`): o resultado
   do commit é *desconhecido*. Confirme o estado por leitura (ou chave de idempotência) antes de repetir.
6. **Transações idempotentes**: `INSERT ... ON CONFLICT DO NOTHING`; `UPDATE` condicionado ao
   estado esperado (`WHERE status = 'processing'`); em saldo, grave o valor esperado, não o delta
   cego (`SET balance = $novo WHERE balance = $antigo`).

Mitigação de conflito: transações curtas; PK UUID (distribui escrita); contadores fragmentados ou
sequência com `CACHE` grande; lotes pequenos (100–500 linhas) mesmo com teto de 3.000; particionar
por região quando a mesma linha é escrita de regiões diferentes.

## 3. Limites que mudam o desenho (valores de referência)

| Limite | Ordem de grandeza | Erro típico |
|---|---|---|
| Linhas modificadas por transação | 3.000 | `54000` "transaction row limit exceeded" |
| Tamanho da transação (inclui entradas de índice) | 10 MiB | `54000` "transaction size limit" |
| Idade da transação | 5 min | `54000` "transaction age limit" |
| Índices por tabela | 24 (PK e cada `UNIQUE` contam) | `54000` |
| Colunas por índice/PK | 8 | `54011` |
| Linha / coluna não indexada | 2 MiB / 1 MiB | `54000` |
| `varchar` declarado / `char` declarado | 65.535 / 4.096 bytes | `54000` já no DDL |

Pontos que o número sozinho não mostra:

- **Identifique o limite pela mensagem, não pelo código**: `54000` e `0A000` cobrem dezenas de casos.
  Compare por prefixo, sem diferenciar maiúsculas; o texto não é contrato estável — na dúvida, caia
  para a classe do SQLSTATE e confira a doc.
- **O limite de 10 MiB conta também as escritas em índices secundários**; lote com vários índices
  cabe menos dados brutos do que parece. Dimensione por tentativa: o `DETAIL` do erro informa o
  tamanho contabilizado e dá a razão para escalar o lote.
- **O orçamento de bytes da chave é compartilhado** entre todas as colunas da chave, e o índice
  secundário carrega a PK junto — PK larga encolhe o espaço do índice. Conte bytes, não caracteres.
- **Colunas removidas continuam contando** no teto cumulativo; tabela que sofreu muito
  `ADD`/`DROP COLUMN` deve ser recriada (com aprovação), não remendada.
- **Mensagem de erro de pacote grande**: conexão fechada sem erro → parece falha de rede e o retry
  reenvia o mesmo comando para sempre. EOF logo após statement grande é problema de tamanho.
- **`25P02` mascara a causa**: leia o *primeiro* erro da transação, não o último.

## 4. O que o DSQL recusa (checar antes de portar schema)

`serial` (use UUID), colunas array, `CREATE PROCEDURE`,
`CREATE DATABASE`, ordenação ou opclass em chave de índice, `CREATE INDEX` sem `ASYNC`,
`CONCURRENTLY`, `ADD COLUMN` com constraint inline, `ALTER COLUMN ... TYPE`, FK adicionada depois
sem `NOT VALID`, `VALIDATE CONSTRAINT` síncrono, funções não-IMMUTABLE em índice ou coluna gerada.
Rode o linter de DDL do DSQL (ou revisão manual contra esta lista) em **todo** DDL externo ou gerado
antes de executar, e pare diante de qualquer item sem correção automática.

## 5. DDL e migração no DSQL

- **Índices**: sempre `CREATE INDEX ASYNC`; espere `pg_index.indisvalid = true` antes de depender
  dele (e antes de criar FK que apoia em índice único assíncrono). Um índice ainda em construção já
  ocupa uma das 24 vagas.
- **Constraints em tabela existente** (CHECK, FK, UNIQUE sobre índice pronto): adicione `NOT VALID`
  (vale para escritas novas na hora, sem varrer o legado) e depois `ALTER TABLE ASYNC ... VALIDATE
  CONSTRAINT`, acompanhando o job até estado terminal. Falha deixa a constraint `NOT VALID`; corrija
  as linhas indicadas no detalhe do job e repita.
- **Alterações diretas suportadas**: `DROP NOT NULL`, `SET/DROP DEFAULT`, renomear coluna/tabela,
  `ADD COLUMN` simples, `DROP CONSTRAINT`.
- **Exigem recriar a tabela**: mudar tipo de coluna, `SET NOT NULL`, adicionar/alterar PK.
  Recriação é último recurso e destrutiva: apresente o plano, confirme backup, peça aprovação em cada
  ponto sem volta, copie em lotes (500–1.000 linhas, respeitando 3.000 linhas/10 MiB/5 min),
  confira contagem de linhas, só então troque nomes e recrie índices com `ASYNC`.
- **Nunca `DROP TABLE ... CASCADE`** para contornar dependência. Tabela com FK entrante ou view
  dependente sai do roteiro genérico e ganha plano dedicado aprovado.
- **Um DDL por transação**: não agrupe dois comandos de catálogo (inclui `GRANT`/`REVOKE`).
- **FK é suportada** e deve ser usada por padrão. Em modelo multi-tenant, a chave do tenant entra
  nas duas pontas (`NOT NULL`); `MATCH FULL` quando chave composta parcial deve ser rejeitada. FK
  garante integridade, não autorização.

## 6. Ponte com o fluxo DBML-first

- No DBML, marque o alvo DSQL em nota do projeto e **gere a lista de recusas da §4** como checklist
  do DDL derivado (sem `serial`, sem array, índices `ASYNC`).
- Na camada Java: use o conector JDBC do DSQL (ou envolva a transação em retry de `40001`) e teste
  o caminho de retry com Testcontainers/duplo de teste que injete `40001` — ver `especialista-qualidade`.
- Geração JPA: chave UUID gerada na aplicação evita *hot spot* e deixa o `INSERT` idempotente.

## 7. Checklist P1.DB para DSQL

- [ ] Todo caminho de escrita (e leitura sensível a `OC001`) tem retry só de `40001`, com backoff+jitter.
- [ ] Transações idempotentes e curtas; lote ≤ 500 linhas na prática.
- [ ] Nenhum recurso recusado no DDL; índices `ASYNC` validados antes do uso.
- [ ] Migração de constraint em duas fases (`NOT VALID` → `VALIDATE ASYNC`).
- [ ] Nenhuma recriação de tabela sem plano, backup e aprovação explícita.
- [ ] Limites (3.000 linhas, 10 MiB, 5 min, 24 índices) revisados contra o volume real.
