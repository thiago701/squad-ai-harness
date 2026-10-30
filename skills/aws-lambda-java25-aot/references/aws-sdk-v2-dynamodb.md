# AWS SDK v2 + DynamoDB Enhanced Client

Padrões de uso do Enhanced Client com modelagem single-table, queries e
patterns AOT-friendly em GraalVM Native.

## Índice

1. [Por que SDK v2 Enhanced Client](#por-que-sdk-v2-enhanced-client)
2. [Configuração do cliente — single instance Lambda-friendly](#configuração-do-cliente--single-instance-lambda-friendly)
3. [BeanTableSchema — entidades single-table](#beantableschema--entidades-single-table)
4. [SingleTableRepository — patterns canônicos](#singletablerepository--patterns-canônicos)
5. [Queries por GSI](#queries-por-gsi)
6. [Batch writes e transactions](#batch-writes-e-transactions)
7. [DynamoDB Streams — handler patterns](#dynamodb-streams--handler-patterns)
8. [Reflection hints obrigatórios](#reflection-hints-obrigatórios)

## Por que SDK v2 Enhanced Client

SDK v1 (`aws-java-sdk-dynamodb`) é deprecated, pesado, sem suporte AOT, e
usa thread pools tradicionais que conflitam com virtual threads. SDK v2
(`software.amazon.awssdk:dynamodb-enhanced`) tem:

- HTTP client modular (use `url-connection-client` para AOT, não `apache-client`)
- Suporte oficial a GraalVM Native (com hints adicionais para entidades)
- Builder pattern thread-safe, instanciável uma vez no escopo da Lambda
- Mappers anotação-based (`@DynamoDbBean`) para deserialização typed

## Configuração do cliente — single instance Lambda-friendly

Lambda **não** se beneficia de connection pool tradicional para DynamoDB —
DynamoDB é HTTP, e cada Lambda Container processa 1 request por vez. Use
um `DynamoDbEnhancedClient` único, instanciado em `@Configuration` e
reutilizado em invocações dentro da mesma instância warm:

```java
package com.example.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import software.amazon.awssdk.enhanced.dynamodb.DynamoDbEnhancedClient;
import software.amazon.awssdk.enhanced.dynamodb.DynamoDbTable;
import software.amazon.awssdk.enhanced.dynamodb.TableSchema;
import software.amazon.awssdk.http.urlconnection.UrlConnectionHttpClient;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.dynamodb.DynamoDbClient;

import java.time.Duration;

@Configuration
public class DynamoDbConfig {

    @Bean
    public DynamoDbClient dynamoDbClient() {
        return DynamoDbClient.builder()
            .region(Region.of(System.getenv("AWS_REGION")))
            .httpClientBuilder(UrlConnectionHttpClient.builder()
                .socketTimeout(Duration.ofSeconds(3))
                .connectionTimeout(Duration.ofMillis(500)))
            .build();
    }

    @Bean
    public DynamoDbEnhancedClient dynamoDbEnhancedClient(DynamoDbClient client) {
        return DynamoDbEnhancedClient.builder()
            .dynamoDbClient(client)
            .build();
    }

    @Bean
    public DynamoDbTable<SingleTableItem> singleTable(DynamoDbEnhancedClient enhanced) {
        String tableName = System.getenv("SINGLE_TABLE_NAME");
        return enhanced.table(tableName, TableSchema.fromBean(SingleTableItem.class));
    }
}
```

**Pontos críticos**:

- `UrlConnectionHttpClient` (não `ApacheHttpClient`) — sem deps Netty/Apache,
  AOT-friendly, leve.
- Timeouts agressivos — DynamoDB é fast (sub-10ms p99), timeout alto só
  esconde bugs. 3s socket / 500ms connection é razoável.
- `TableSchema.fromBean(...)` — usa reflection na entidade. Por isso o
  `RuntimeHints` precisa registrar `BeanTableSchema` e cada entidade.

## BeanTableSchema — entidades single-table

Cada item da tabela é representado por uma classe Java com anotações.
A skill gera **um record por entidade DBML** + uma classe `SingleTableItem`
para o "shape" base.

### SingleTableItem (shape base)

```java
package com.example.model;

import software.amazon.awssdk.enhanced.dynamodb.mapper.annotations.*;

@DynamoDbBean
public class SingleTableItem {
    private String pk;
    private String sk;
    private String type;     // _type discriminator
    private String gsi1pk;
    private String gsi1sk;
    private String gsi2pk;
    private String gsi2sk;
    // atributos de qualquer entidade — wide row
    private String name;
    private String email;
    private String status;
    private Long total;
    // etc.

    @DynamoDbPartitionKey public String getPk() { return pk; }
    public void setPk(String pk) { this.pk = pk; }

    @DynamoDbSortKey public String getSk() { return sk; }
    public void setSk(String sk) { this.sk = sk; }

    @DynamoDbAttribute("_type") public String getType() { return type; }
    public void setType(String type) { this.type = type; }

    @DynamoDbSecondaryPartitionKey(indexNames = "GSI1") public String getGsi1pk() { return gsi1pk; }
    public void setGsi1pk(String gsi1pk) { this.gsi1pk = gsi1pk; }

    @DynamoDbSecondarySortKey(indexNames = "GSI1") public String getGsi1sk() { return gsi1sk; }
    public void setGsi1sk(String gsi1sk) { this.gsi1sk = gsi1sk; }

    @DynamoDbSecondaryPartitionKey(indexNames = "GSI2") public String getGsi2pk() { return gsi2pk; }
    public void setGsi2pk(String gsi2pk) { this.gsi2pk = gsi2pk; }

    @DynamoDbSecondarySortKey(indexNames = "GSI2") public String getGsi2sk() { return gsi2sk; }
    public void setGsi2sk(String gsi2sk) { this.gsi2sk = gsi2sk; }

    // Demais getters/setters...
}
```

`@DynamoDbBean` exige getters/setters JavaBeans (não records puros) porque
o BeanTableSchema usa reflection para escrever propriedades. Em projetos
mais novos, AWS SDK v2 tem suporte experimental a records via
`StaticTableSchema.builder()`, mas o padrão estável continua sendo
`@DynamoDbBean` com classe mutável.

### Records de entidade (camada de domínio)

```java
public record User(String id, String email, String name, Instant createdAt) {

    public SingleTableItem toItem() {
        SingleTableItem item = new SingleTableItem();
        item.setPk("USER#" + id);
        item.setSk("USER#" + id);
        item.setType("USER");
        item.setGsi1pk("EMAIL#" + email);
        item.setGsi1sk("USER#" + id);
        item.setName(name);
        item.setEmail(email);
        return item;
    }

    public static User fromItem(SingleTableItem item) {
        return new User(
            item.getPk().substring("USER#".length()),
            item.getEmail(),
            item.getName(),
            null   // populate se houver atributo createdAt
        );
    }
}
```

Records ficam imutáveis e expressivos no domain layer; a conversão
explícita para `SingleTableItem` mantém o boundary claro.

## SingleTableRepository — patterns canônicos

```java
package com.example.repository;

import software.amazon.awssdk.enhanced.dynamodb.*;
import software.amazon.awssdk.enhanced.dynamodb.model.*;
import org.springframework.stereotype.Repository;
import com.example.model.*;

import java.util.List;
import java.util.stream.Collectors;

@Repository
public class SingleTableRepository {

    private final DynamoDbTable<SingleTableItem> table;

    public SingleTableRepository(DynamoDbTable<SingleTableItem> table) {
        this.table = table;
    }

    // Get user by id (PK base)
    public User getUserById(String id) {
        SingleTableItem item = table.getItem(Key.builder()
            .partitionValue("USER#" + id)
            .sortValue("USER#" + id)
            .build());
        return item != null ? User.fromItem(item) : null;
    }

    // Get user by email (GSI1)
    public User getUserByEmail(String email) {
        return table.index("GSI1")
            .query(QueryConditional.keyEqualTo(Key.builder()
                .partitionValue("EMAIL#" + email)
                .build()))
            .stream()
            .flatMap(page -> page.items().stream())
            .findFirst()
            .map(User::fromItem)
            .orElse(null);
    }

    // List orders of a user (PK base + SK begins_with)
    public List<Order> listOrdersByUser(String userId) {
        return table.query(QueryConditional.sortBeginsWith(Key.builder()
                .partitionValue("USER#" + userId)
                .sortValue("ORDER#")
                .build()))
            .stream()
            .flatMap(page -> page.items().stream())
            .filter(item -> "ORDER".equals(item.getType()))
            .map(Order::fromItem)
            .collect(Collectors.toList());
    }

    public void saveUser(User user) {
        table.putItem(user.toItem());
    }

    public void deleteUser(String id) {
        table.deleteItem(Key.builder()
            .partitionValue("USER#" + id)
            .sortValue("USER#" + id)
            .build());
    }
}
```

## Queries por GSI

GSIs são acessados via `table.index("GSI1")`. Padrões úteis:

### Query simples (PK do GSI)

```java
table.index("GSI1")
    .query(QueryConditional.keyEqualTo(Key.builder()
        .partitionValue("EMAIL#" + email).build()))
    .stream();
```

### Query com SK begins_with

```java
table.index("GSI2")
    .query(QueryConditional.sortBeginsWith(Key.builder()
        .partitionValue("STATUS#PENDING")
        .sortValue("ORDER#")
        .build()))
    .stream()
    .flatMap(p -> p.items().stream())
    .toList();
```

### Query com SK between (range)

```java
table.index("GSI2")
    .query(QueryConditional.sortBetween(
        Key.builder().partitionValue("STATUS#PENDING").sortValue("2026-01-01").build(),
        Key.builder().partitionValue("STATUS#PENDING").sortValue("2026-12-31").build()
    ))
    .stream();
```

### Paginação

DynamoDB queries são paginadas por padrão (1MB ou 100 items). Use
`scanIndexForward(false)` para ordem descendente, `limit(N)` para limitar:

```java
QueryEnhancedRequest req = QueryEnhancedRequest.builder()
    .queryConditional(QueryConditional.sortBeginsWith(...))
    .scanIndexForward(false)   // mais recentes primeiro
    .limit(20)
    .build();

table.query(req).stream().findFirst()
    .ifPresent(page -> {
        List<SingleTableItem> items = page.items();
        Map<String, AttributeValue> lastKey = page.lastEvaluatedKey();
        // lastKey vira cursor para próxima página
    });
```

## Batch writes e transactions

### Batch (até 25 items, sem ACID)

```java
WriteBatch.Builder<SingleTableItem> batch = WriteBatch.builder(SingleTableItem.class)
    .mappedTableResource(table);

for (User u : users) batch.addPutItem(u.toItem());

enhancedClient.batchWriteItem(BatchWriteItemEnhancedRequest.builder()
    .writeBatches(batch.build())
    .build());
```

### Transactional (até 100 items, ACID, custo 2x)

```java
TransactWriteItemsEnhancedRequest req = TransactWriteItemsEnhancedRequest.builder()
    .addPutItem(table, user.toItem())
    .addPutItem(table, order.toItem())
    .addUpdateItem(table, TransactUpdateItemEnhancedRequest.builder(SingleTableItem.class)
        .item(inventoryDecrement)
        .conditionExpression(Expression.builder()
            .expression("stock > :zero")
            .putExpressionValue(":zero", AttributeValue.fromN("0"))
            .build())
        .build())
    .build();

enhancedClient.transactWriteItems(req);
```

Use transactional para invariantes cross-entity (ex: criar Order +
decrementar Inventory atomicamente).

## DynamoDB Streams — handler patterns

DynamoDB Streams capturam INSERT/MODIFY/REMOVE em tempo real. O handler
recebe `DynamodbEvent` com lista de records:

```java
package com.example.handler;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.events.DynamodbEvent;
import com.amazonaws.services.lambda.runtime.events.models.dynamodb.AttributeValue;
import software.amazon.lambda.powertools.logging.Logging;
import software.amazon.lambda.powertools.metrics.Metrics;

import org.springframework.stereotype.Component;
import java.util.function.Function;

@Component
public class DynamoDbStreamHandler implements Function<DynamodbEvent, Void> {

    @Logging(logEvent = true)
    @Metrics(captureColdStart = true)
    @Override
    public Void apply(DynamodbEvent event) {
        for (DynamodbEvent.DynamodbStreamRecord record : event.getRecords()) {
            String eventName = record.getEventName();   // INSERT | MODIFY | REMOVE
            Map<String, AttributeValue> newImage = record.getDynamodb().getNewImage();
            Map<String, AttributeValue> oldImage = record.getDynamodb().getOldImage();

            String type = newImage != null
                ? newImage.get("_type").getS()
                : oldImage.get("_type").getS();

            switch (eventName) {
                case "INSERT" -> handleInsert(type, newImage);
                case "MODIFY" -> handleUpdate(type, oldImage, newImage);
                case "REMOVE" -> handleRemove(type, oldImage);
                default -> { /* unknown */ }
            }
        }
        return null;
    }

    private void handleInsert(String type, Map<String, AttributeValue> img) {
        // ex: enviar evento para EventBridge, atualizar cache, notificar webhook
    }
    // ...
}
```

**Padrões importantes**:

- Use `_type` discriminator para rotear lógica por entidade.
- DynamoDB Streams entrega **at-least-once**; idempotência é obrigatória.
  Use `@Idempotent` do PowerTools (ver `lambda-powertools-java.md`).
- Configure `BatchSize` no template SAM (default 100, máximo 1000) — equilibra
  throughput vs tempo de execução.
- Configure `MaximumBatchingWindowInSeconds` para acumular records antes
  de invocar a Lambda — reduz custo em workloads com burst.

## Reflection hints obrigatórios

Sem estes hints, a Lambda em modo nativo dá `NullPointerException` ou
`ClassNotFoundException` no primeiro acesso ao DynamoDB:

```java
@Override
public void registerHints(RuntimeHints hints, ClassLoader cl) {
    // SDK v2 internals
    Stream.of(
        software.amazon.awssdk.enhanced.dynamodb.mapper.BeanTableSchema.class,
        software.amazon.awssdk.enhanced.dynamodb.mapper.StaticTableSchema.class,
        software.amazon.awssdk.enhanced.dynamodb.mapper.ImmutableTableSchema.class
    ).forEach(c -> hints.reflection().registerType(c,
        MemberCategory.INVOKE_DECLARED_METHODS,
        MemberCategory.INVOKE_DECLARED_CONSTRUCTORS
    ));

    // SingleTableItem + cada entidade do domínio
    Stream.of(
        SingleTableItem.class, User.class, Order.class, OrderItem.class /* ... */
    ).forEach(c -> hints.reflection().registerType(c,
        MemberCategory.INVOKE_DECLARED_CONSTRUCTORS,
        MemberCategory.DECLARED_FIELDS,
        MemberCategory.INVOKE_DECLARED_METHODS,
        MemberCategory.PUBLIC_FIELDS
    ));

    // Annotations do Enhanced Client (registradas a runtime via reflection)
    Stream.of(
        DynamoDbBean.class, DynamoDbPartitionKey.class, DynamoDbSortKey.class,
        DynamoDbSecondaryPartitionKey.class, DynamoDbSecondarySortKey.class,
        DynamoDbAttribute.class
    ).forEach(c -> hints.reflection().registerType(c, MemberCategory.INVOKE_DECLARED_METHODS));
}
```

A skill gera essa classe `NativeHints` automaticamente, populando a lista
de entidades a partir do schema DBML parseado.
