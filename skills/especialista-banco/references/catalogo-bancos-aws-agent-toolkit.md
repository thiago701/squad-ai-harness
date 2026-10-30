# Catálogo de Bancos de Dados AWS, Vetores e Migração (Agent Toolkit for AWS)

> **Procedência:** absorvido e reescrito em PT-BR a partir de `aws/agent-toolkit-for-aws` (`skills/core-skills/aws-database`, as 15 skills de `skills/specialized-skills/database-skills/*`, `dms-schema-conversion` e `storing-and-querying-vectors`, commit `658b852f0612ca629d56d0a4de52738fb6a58714`, Apache-2.0).

---

## 1. Roteamento e Axiomas de Escolha de Banco na AWS (`aws-database`)

| Caso de Uso | Motor Recomendado | Skill Original Absorvida | Regra de Decisão |
|---|---|---|---|
| Relacional transacional cloud-native de alta disponibilidade | **Amazon Aurora PostgreSQL / MySQL** | `amazon-aurora-postgresql`, `amazon-aurora-mysql`, `creating-amazon-aurora-db-cluster-with-instances` | Storage distribuído em 3 AZs (6 cópias), failover < 30s, Serverless v2 ou Provisioned |
| Relacional distribuído ativo-ativo serverless (OCC) | **Amazon Aurora DSQL** | `aurora-dsql` | Escala sem gerenciamento de instâncias, autenticação IAM obrigatória, concorrência otimista (OCC) sem locks bloqueantes |
| Relacional tradicional ou motores comerciais/legados | **Amazon RDS (PostgreSQL, MySQL, MariaDB, Oracle, SQL Server, Db2)** | `rds-oss`, `rds-oracle`, `rds-sqlserver`, `rds-db2` | Quando exige feature específica de engine não disponível no Aurora ou lift-and-shift comercial |
| NoSQL chave-valor / documento previsível em qualquer escala | **Amazon DynamoDB** | `amazon-dynamodb` | Latência single-digit ms; exige modelagem *access-patterns-first* |
| Cache em memória sub-milissegundo / sessões / rate limit | **Amazon ElastiCache (Valkey / Redis)** | `amazon-elasticache` | Reduz carga de leitura no banco primário e absorve picos; prefira Valkey Serverless/Graviton |
| Documentos JSON compatíveis com MongoDB + busca vetorial | **Amazon DocumentDB (8.0 Serverless)** | `amazon-documentdb` | Schemas flexíveis, agregações MongoDB e índices vetoriais HNSW/IVFFlat |
| Colunar wide-column compatível com Apache Cassandra | **Amazon Keyspaces** | `amazon-keyspaces` | Workloads CQL serverless sem gerenciar nós/compactação |
| Grafos de identidade, fraude, linhagem e GraphRAG | **Amazon Neptune (Database / Analytics)** | `amazon-neptune` | Gremlin/openCypher/SPARQL; separe transacional (Database) de algoritmos analíticos em memória (Analytics) |
| Séries temporais e telemetria de alta ingestão | **Amazon Timestream for InfluxDB** | `timestream-influxdb` | Ingestão contínua por janela temporal, retenção e downsampling |

---

## 2. Aurora PostgreSQL, Aurora MySQL e RDS Open-Source (`amazon-aurora-*`, `rds-oss`)

1. **Decisão `Standard` vs `I/O-Optimized` no Aurora:**
   - No modo `Standard`, paga-se por GB-mês + I/Os consumidos. No `I/O-Optimized`, o custo de compute e storage sobe, mas o custo por operação de I/O é **zero**.
   - **Regra do ponto de equilíbrio:** só migre um cluster para `I/O-Optimized` quando a fatura histórica de I/O ultrapassar **~25% do gasto total do cluster Aurora** (nunca recomende sem medir `VolumeReadIOPs` + `VolumeWriteIOPs`).
2. **Planejamento de Upgrade e Versões LTS:**
   - Sempre valide se a versão atual possui suporte **LTS** oficial da AWS antes de recomendar permanência, evitando cobrança automática de **RDS Extended Support**.
   - Para upgrades major sem downtime perceptível, utilize **RDS/Aurora Blue/Green Deployments** (valide pré-requisitos: logical replication habilitada, ausência de DDLs incompatíveis ou tabelas sem PK no PostgreSQL).
3. **Provisionamento Seguro (`creating-amazon-aurora-db-cluster-with-instances`):**
   - Sempre habilite `StorageEncrypted: true` (KMS), `DeletionProtection: true` em produção, `CopyTagsToSnapshot: true`, autenticação IAM Database Authentication e gerencie a senha master via `ManageMasterUserPassword: true` (Secrets Manager com rotação automática).
4. **Exportação Analítica sem Impacto Transacional (`exporting-rds-to-s3`):**
   - Para alimentar Data Lakes ou auditorias históricas sem onerar o cluster primário, use `aws rds start-export-task` sobre um snapshot RDS/Aurora exportando diretamente para **Apache Parquet** no S3 criptografado com KMS.

---

## 3. DynamoDB Baseado em Axiomas (`amazon-dynamodb`)

1. **Enumerar 100% dos padrões de acesso antes do schema:** documente entidade, frequência (RPS), tamanho médio do item e requisito de consistência (eventual vs forte).
2. **Prevenção de Hot Partitions:** uma partição física suporta até **1.000 WCU** ou **3.000 RCU**. Chaves de partição de baixa cardinalidade (`status`, `data_dia`, `tenant_unico`) exigem *write sharding* (sufixo determinístico por hash ou aleatório `0..N-1`) + *scatter-gather* na leitura.
3. **TTL nunca é "armazenamento gratuito imediato":** a expiração por TTL ocorre em background (até ~48h); filtre sempre `expiresAt > :now` nas queries de negócio caso o item expirado não possa ser lido.

---

## 4. ElastiCache, DocumentDB, Keyspaces, Neptune, Timestream e Motores Comerciais

- **ElastiCache (`amazon-elasticache`):**
  - Prefira **Valkey** (menor custo em Serverless e instâncias Graviton).
  - Exija TLS em trânsito, `TransitEncryptionEnabled: true`, `AtRestEncryptionEnabled: true` e injeção de segredos com renovação de token (`AUTH` sem derrubar conexões ativas).
- **DocumentDB (`amazon-documentdb`):**
  - Padrão recomendado para novos clusters: **DocumentDB Serverless na versão 8.0** com TLS habilitado e verificação de operadores suportados antes de migrar queries MongoDB.
- **Keyspaces (`amazon-keyspaces`):**
  - Calcule capacidade em RCU/WCU considerando o tamanho da linha arredondado em blocos de 4 KB (leitura) e 1 KB (escrita); valide features Cassandra não suportadas (ex.: triggers, materialized views, agregações sem partition key) antes da migração.
- **Neptune (`amazon-neptune`):**
  - Use **Neptune Database** para consultas OLTP de baixa latência e **Neptune Analytics** para algoritmos de centralidade/PageRank/WCC e busca vetorial combinada com travessia de grafo (*GraphRAG*).
- **RDS Comercial (`rds-oracle`, `rds-sqlserver`, `rds-db2`):**
  - Diagnostique conectividade separando camada de rede (Security Group / NACL / sub-redes), autenticação (Kerberos / Active Directory / IAM / SSL) e parâmetros específicos de driver (Oracle CMAN/TNS, SQL Server Multi-Subnet Failover, Db2 code page/collation e BYOK KMS).

---

## 5. Armazenamento e Consulta de Vetores (`storing-and-querying-vectors`)

Escolha o motor vetorial na AWS conforme a arquitetura já existente (P1 — evite criar infraestrutura nova se o banco atual resolve):

| Cenário | Escolha Recomendada |
|---|---|
| Já utiliza PostgreSQL / Aurora PostgreSQL e volume < 10–20M vetores | **Aurora PostgreSQL com `pgvector` (HNSW)** |
| Busca híbrida (BM25 lexical + k-NN semântico) em alta escala | **Amazon OpenSearch Service / Serverless Vector Engine** |
| Armazenamento vetorial puro de baixo custo em S3 com filtro de metadados | **Amazon S3 Vectors** (ideal para grandes volumes com latência de dezenas de ms) |
| Grafo + similaridade vetorial (GraphRAG) | **Amazon Neptune Analytics** |
| Aplicações baseadas em documentos JSON | **Amazon DocumentDB Vector Search** |

- **Regra de filtragem de metadados:** declare apenas chaves de baixa/média cardinalidade necessárias ao filtro pré-busca (`filterable metadata`); identificadores de texto longo devem ficar como metadados não-filtráveis para não estourar limites de índice.

---

## 6. Conversão de Schema com AWS DMS (`dms-schema-conversion`)

Ao migrar bancos heterogêneos (ex.: Oracle ou SQL Server → Aurora PostgreSQL):
1. Crie o Migration Project com Data Providers de origem e destino e S3 bucket intermediário criptografado.
2. Execute ` start-metadata-model-assessment` para gerar o relatório de compatibilidade e classificar **Action Items** por complexidade (automático vs intervenção manual em PL/SQL / T-SQL).
3. Converta e revise objetos incompatíveis (packages, sinônimos, tipos proprietários) antes de aplicar o DDL no destino.
