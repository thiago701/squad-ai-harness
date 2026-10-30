# Referência — Dados (RDS, DynamoDB, ElastiCache)

> Parte da skill `arquiteto-cloud-aws`. Carregue este arquivo sob demanda quando a tarefa tocar este eixo. Hub: `../SKILL.md`.
### Banco de Dados — RDS, DynamoDB, ElastiCache

#### RDS PostgreSQL — Relacional Gerenciado

```
Free tier RDS: db.t3.micro por 750h/mês durante 12 meses (20GB SSD)
Após free tier: db.t3.micro ~$15/mês | db.t3.small ~$28/mês

Configuração mínima recomendada para início:
  - db.t3.micro (free tier) ou db.t3.small (pós-free)
  - Multi-AZ: NÃO no início (dobra o custo — ative quando SLA exigir)
  - Backup automático: 7 dias (incluído no preço)
  - Performance Insights: ative (gratuito por 7 dias de retenção)
```

```python
# Python — SQLAlchemy async + RDS Proxy (evita connection pool exhaustion em Lambda)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os

# RDS Proxy: gerencia pool de conexões — crítico para Lambda (sem estado persistente)
DATABASE_URL = os.environ["DATABASE_URL"]  # via Secrets Manager

engine = create_async_engine(
    DATABASE_URL,
    pool_size=5,         # Lambda: mantenha baixo (cada instância tem seu pool)
    max_overflow=2,
    pool_pre_ping=True,  # detecta conexões mortas
    pool_recycle=300,    # recicla conexões a cada 5min (RDS fecha idle após 8h)
)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Dependency FastAPI — sessão por request
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

#### DynamoDB — NoSQL com Free Tier Permanente

```
Free tier DynamoDB: 25GB storage + 25 WCU + 25 RCU — PERMANENTE (não expira)
Suficiente para: ~200 milhões de leituras/mês ou ~100 milhões de escritas

Quando DynamoDB brilha:
  ✓ Sessões de usuário (TTL automático)
  ✓ Carrinho de compras, preferências
  ✓ Rate limiting distribuído
  ✓ Configurações de feature flags
  ✓ Dados com acesso por chave única e alta escala

Quando NÃO usar DynamoDB:
  ✗ Queries complexas com múltiplos filtros (use RDS)
  ✗ Transações multi-tabela complexas (use RDS)
  ✗ Relatórios e analytics (use Athena + S3)
```

```python
# Python — DynamoDB com boto3 (simples, sem ORM pesado)
import boto3
from datetime import datetime, timedelta

dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

class SessaoRepository:
    def __init__(self):
        self.tabela = dynamodb.Table("sessoes-usuario")

    def salvar(self, user_id: str, dados: dict, ttl_horas: int = 24) -> None:
        self.tabela.put_item(Item={
            "pk":         f"USER#{user_id}",
            "sk":         "SESSAO#ATIVA",
            "dados":      dados,
            "expires_at": int((datetime.utcnow() + timedelta(hours=ttl_horas)).timestamp()),
            # TTL automático do DynamoDB — zero código de limpeza!
        })

    def buscar(self, user_id: str) -> dict | None:
        response = self.tabela.get_item(
            Key={"pk": f"USER#{user_id}", "sk": "SESSAO#ATIVA"}
        )
        return response.get("Item")
```

#### DynamoDB — Single-Table Design e GSI

```
Single-Table Design: todas as entidades de um bounded context na mesma tabela.
Reduz custos (1 tabela = 1 free tier) e latência (1 query em vez de JOINs).

Modelagem por Access Patterns — defina ANTES de criar a tabela:
  1. Listar pedidos por cliente (PK=CUSTOMER#id, SK=ORDER#timestamp)
  2. Buscar pedido por ID (PK=ORDER#id, SK=ORDER#id)
  3. Listar itens de um pedido (PK=ORDER#id, SK=ITEM#seq)
  4. Buscar pedidos por status (GSI: GSI1PK=STATUS#pendente, GSI1SK=timestamp)
```

```java
// Java 25 — Single-Table Design com DynamoDbEnhancedClient
// Cada entidade usa a mesma tabela, diferenciada por PK/SK pattern

@DynamoDbBean
public class PedidoItem {
    private String pk;          // CUSTOMER#uuid ou ORDER#uuid
    private String sk;          // ORDER#timestamp ou ITEM#seq
    private String gsi1pk;      // STATUS#pendente, STATUS#confirmado
    private String gsi1sk;      // timestamp ISO (para ordenação)
    private String entityType;  // "PEDIDO" ou "ITEM"
    private Map<String, String> dados;

    @DynamoDbPartitionKey
    public String getPk() { return pk; }

    @DynamoDbSortKey
    public String getSk() { return sk; }

    @DynamoDbSecondaryPartitionKey(indexNames = "GSI1")
    public String getGsi1pk() { return gsi1pk; }

    @DynamoDbSecondarySortKey(indexNames = "GSI1")
    public String getGsi1sk() { return gsi1sk; }
}

// Query por access pattern: "pedidos pendentes, mais recentes primeiro"
var pedidosPendentes = tabela.index("GSI1")
    .query(r -> r.queryConditional(
        QueryConditional.sortGreaterThan(
            Key.builder().partitionValue("STATUS#pendente")
                         .sortValue("2025-01-01").build()
        )))
    .stream()
    .flatMap(page -> page.items().stream())
    .toList();
```

```
GSI (Global Secondary Index) — quando usar:
  ✓ Precisa consultar por atributo que não é PK/SK (status, data, email)
  ✓ Máximo 20 GSIs por tabela (suficiente para qualquer caso real)
  ✓ Custo: provisioned WCU/RCU do GSI (incluído no free tier se tabela no free tier)

LSI (Local Secondary Index) — quando usar:
  ✓ Mesmo partition key, sort key diferente
  ✓ Deve ser criado na criação da tabela (não pode adicionar depois)
  ✓ Máximo 5 LSIs por tabela

Checklist DynamoDB:
  □ Access patterns definidos ANTES de modelar tabela
  □ Single-table design quando entidades compartilham contexto
  □ TTL habilitado para dados temporários (sessões, tokens, cache)
  □ GSI apenas para queries frequentes (cada GSI = custo extra de write)
  □ On-demand capacity para workloads imprevisíveis (dev/staging)
  □ Provisioned + auto-scaling para workloads estáveis (prod com baseline)
```

---

