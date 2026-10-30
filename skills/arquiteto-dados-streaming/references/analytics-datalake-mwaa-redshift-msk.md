# Analytics, Streaming, Data Lake, MWAA e Redshift (Agent Toolkit for AWS)

> **Procedência:** absorvido e reescrito em PT-BR a partir de `aws/agent-toolkit-for-aws` (17 skills de `skills/specialized-skills/analytics-skills/*`, 4 skills de `system-table-skills/*` e `creating-data-lake-table`, commit `658b852f0612ca629d56d0a4de52738fb6a58714`, Apache-2.0).

---

## 1. Streaming Gerenciado: Kinesis Data Streams, Amazon MSK e Apache Flink

### 1.1. Kinesis Data Streams (`managing-amazon-kinesis-data-streams`)
- **Modos de capacidade:** use **On-Demand** para tráfego variável ou desconhecido; use **Provisioned** quando o throughput é previsível e dimensionado em shards (**1 MB/s ou 1.000 registros/s na escrita** e **2 MB/s na leitura compartilhada** por shard).
- **Enhanced Fan-Out (EFO):** ative apenas quando houver **> 2–3 consumidores simultâneos** exigindo throughput dedicado de 2 MB/s por shard e latência < 70 ms.
- **Entrega para S3 / Tabelas de Streaming:** use Data Firehose para entrega gerenciada em Parquet/Iceberg no S3 com compactação e particionamento automático.

### 1.2. Amazon MSK — Operação e Migração (`managing-amazon-msk`, `migrate-to-msk`)
- **Avaliação e Migração (`migrate-to-msk`):**
  1. Descoberta do cluster de origem (versão Kafka, contagem de partições, throughput de entrada/saída, retenção, mecanismos SASL/mTLS).
  2. Dimensionamento: prefira instâncias Graviton (`kafka.m7g.*`) com **MSK Provisioned** (com Express Brokers para escala elástica sem rebalanceamento de storage) ou **MSK Serverless** para cargas intermitentes.
  3. Verifique limites rígidos de partições por broker antes de criar tópicos ou reduzir instâncias.
- **Segurança:** exija TLS em trânsito e autenticação **IAM Access Control** para clientes dentro da AWS (elimina gestão manual de segredos SASL/SCRAM).

### 1.3. Managed Service for Apache Flink (`developing-applications-on-managed-service-for-apache-flink`)
- Configure **Checkpointing** com intervalo compatível com o SLA de recuperação e monitore `lastCheckpointDuration` e `lastCheckpointSize`.
- Empacote dependências em fat-JAR enxuto excluindo bibliotecas já providas pelo runtime Flink para evitar conflitos de classloader.
- Em pipelines CDC (Debezium/DMS → MSK → Flink → Iceberg), garanta chave primária determinística e tratamento de eventos *delete/tombstone*.

---

## 2. Data Lakehouse: Catálogo, Ingestão e Consulta (`exploring-data-catalog`, `finding-data-lake-assets`, `connecting-to-data-source`, `creating-data-lake-table`, `ingesting-into-data-lake`, `querying-data-lake`)

1. **Descoberta e Catálogo (`exploring-data-catalog`, `finding-data-lake-assets`):**
   - Sempre inspecione bancos, tabelas, partições e permissões do **AWS Glue Data Catalog** / **Lake Formation** antes de criar novas tabelas, evitando duplicação de assets.
2. **Conexão Segura a Fontes Externas (`connecting-to-data-source`):**
   - Configure Glue Connections / Athena Federated Queries sempre com credenciais armazenadas no **AWS Secrets Manager** e tráfego privado via VPC Endpoints / NAT / sub-rede privada.
3. **Criação de Tabelas e Formato Aberto (`creating-data-lake-table`):**
   - Prefira **Apache Iceberg** gerenciado no Glue Data Catalog para tabelas que sofrem `UPDATE`/`DELETE`/`MERGE` (ACID, time-travel, evolução de schema e *hidden partitioning*), ou Parquet particionado para logs puramente *append-only*.
4. **Ingestão e Qualidade (`ingesting-into-data-lake`):**
   - Para cargas leves/transformações SQL, use **Athena CTAS / INSERT INTO**; para cargas volumosas ou fontes JDBC/SaaS, use **AWS Glue ETL** com **Glue Data Quality (DQDL)** validando completude e unicidade antes de publicar na camada *curated/silver*.
5. **Consulta Eficiente (`querying-data-lake`):**
   - Selecione um Athena Workgroup com limite de bytes escaneados por query (`BytesScannedCutoffPerQuery`), projete apenas as colunas necessárias (nunca `SELECT *` em tabelas colunares) e filtre sempre pelas colunas de partição.

---

## 3. Amazon Redshift e Migração de Data Warehouse (`redshift-guide`, `migrating-to-amazon-redshift`)

### 3.1. Regra Cardinal: "Redshift NÃO é PostgreSQL" (`redshift-guide`)
Embora use protocolo wire derivado do Postgres 8.0.2, o Redshift é um motor **colunar MPP**. Corrija imediatamente erros comuns de LLMs:
- **Sem índices secundários (`CREATE INDEX` não existe):** a performance vem de **`DISTKEY`** (`KEY`, `EVEN`, `ALL` ou `AUTO`) para evitar redistribuição de rede (*data skew*) em `JOIN`s e **`SORTKEY`** (composta ou intercalada) para *zone maps* (pular blocos de 1 MB em filtros `WHERE`).
- **Constraints (`PRIMARY KEY`, `UNIQUE`, `FOREIGN KEY`) são informativas para o otimizador**, **não** são impostas na escrita (exceto `NOT NULL`) — a deduplicação deve ocorrer no pipeline de carga (`COPY` + staging table + `MERGE`).
- **Carga em lote:** nunca faça milhares de `INSERT`s unitários; carregue sempre via comando **`COPY`** a partir do S3 em Parquet/ORC/CSV compactado usando role IAM.

### 3.2. Migração End-to-End (`migrating-to-amazon-redshift`)
- Siga o ciclo: inventário do DW legado (Snowflake/Teradata/BigQuery/Oracle) → tradução de DDL/tipos/stored procedures → validação sintática e semântica → carga histórica via S3/`COPY` → reconciliação de contagens e agregados financeiros.

---

## 4. Amazon OpenSearch, MWAA (Airflow), Clean Rooms e System Tables

- **Amazon OpenSearch Service (`amazon-opensearch-service`):**
  - Classifique primeiro a capacidade: busca textual/híbrida, observabilidade de logs/traces (PPL) ou busca vetorial/RAG. Dimensione shards entre **10 GB e 50 GB** por shard (evite *oversharding* com centenas de shards minúsculos).
- **Ciclo Completo de Apache Airflow em MWAA (`authoring-mwaa-workflow`, `testing-mwaa-workflow`, `debugging-mwaa-workflow`, `upgrading-mwaa-environments`):**
  1. **Autoria:** mantenha o código de topo do arquivo da DAG livre de chamadas de rede ou consultas a banco/Secrets Manager (o scheduler reparseia os arquivos continuamente; I/O no top-level trava o parsing).
  2. **Testes:** valide sintaxe, importação de plugins e conexões antes de disparar execuções reais.
  3. **Depuração:** diferencie falhas de Task (logs da task no CloudWatch), falhas de Scheduler (timeout de DAG parsing / CPU) e falhas de Worker (OOM / fila Celery / permissões da Execution Role IAM).
  4. **Upgrade (Airflow 2 → 3):** execute o checklist de pré-voo verificando provedores depreciados, versão do Python, `requirements.txt` com `--constraint` oficial e janela de manutenção com backup de metadados.
- **AWS Clean Rooms (`aws-cleanrooms`):**
  - Depure colaborações verificando em cadeia: permissões Lake Formation na tabela base, política do bucket S3, chave KMS compartilhada com o principal do Clean Rooms e regras de análise (Aggregation vs List vs Custom SQL).
- **Consultas Diretas em System Tables (`querying-aws-cloudwatch`, `querying-aws-redshift`, `querying-aws-s3`, `querying-aws-sagemaker-catalog`):**
  - Use as tabelas de sistema oficiais (`SYS_*` / `STL_*` / `SVV_*` no Redshift, S3 Inventory/Metadata Tables, CloudWatch Logs Insights e SageMaker Unified Studio Catalog) para auditoria operacional sem varrer objetos brutos.
