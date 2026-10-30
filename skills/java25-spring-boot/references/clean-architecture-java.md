# Clean Architecture em Java 25 + Spring Boot 4

> **Fundações:** Clean Architecture (Robert C. Martin) + Hexagonal Architecture (Alistair Cockburn)
> + DDD (Eric Evans) + SOLID principles, implementados em Java 25 + Spring Boot 4.
>
> **Referência canônica:** GLOSSARIO §6 (Organização de Pacotes).

**Última atualização:** 2026-04-10

---

## 1. Visão Geral

Clean Architecture organiza código em camadas concêntricas:

```
┌─────────────────────────────────────────────────┐
│  Adapters (HTTP, Persistence, Messaging)        │
│  ┌───────────────────────────────────────────┐  │
│  │ Application (Use Cases, Business Processes)  │
│  │ ┌─────────────────────────────────────────┐  │
│  │ │ Domain (Models, Ports, Events)          │  │
│  │ │ Core — deve NUNCA importar externo      │  │
│  │ └─────────────────────────────────────────┘  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘

Regra de ouro: código flui PARA DENTRO (adapters → domain), não para fora.
```

---

## 2. Estrutura de Pacotes Canônica (Java 25 + Spring Boot 4)

```
com.squad.bc.<bounded-context>/
├── domain/
│   ├── model/
│   │   ├── Pedido.java                    # Aggregate Root (record ou class sealed)
│   │   ├── ItemPedido.java                # Entity dentro de Pedido (record)
│   │   ├── Valor.java                     # Value Object (record)
│   │   └── PedidoStatus.java              # Enum ou sealed interface
│   │
│   ├── event/
│   │   ├── PedidoEvent.java               # Sealed interface para eventos domínio
│   │   ├── PedidoCriadoEvent.java         # Record implementando PedidoEvent
│   │   └── PedidoConfirmadoEvent.java
│   │
│   ├── port/
│   │   ├── in/
│   │   │   ├── ConfirmarPedidoUseCase.java
│   │   │   ├── CriarPedidoUseCase.java
│   │   │   └── ListarPedidosUseCase.java
│   │   │
│   │   └── out/
│   │       ├── PedidoRepository.java      # Persistência
│   │       ├── PedidoPublisher.java       # Eventos domínio
│   │       ├── ClienteGateway.java        # Integração externa
│   │       └── PagamentoGateway.java
│   │
│   ├── service/
│   │   └── CalcularFreteService.java      # Domain Service (stateless)
│   │
│   └── exception/
│       ├── PedidoNaoEncontradoException.java
│       └── PedidoInvalidoException.java
│
├── application/
│   ├── usecase/
│   │   ├── ConfirmarPedidoService.java    # Implementação de port.in
│   │   ├── CriarPedidoService.java
│   │   └── ListarPedidosService.java
│   │
│   ├── dto/
│   │   ├── ConfirmarPedidoCommand.java    # Input (record)
│   │   ├── CriarPedidoCommand.java
│   │   ├── PedidoResult.java              # Output (record)
│   │   └── PedidoListResult.java
│   │
│   └── mapper/
│       └── PedidoApplicationMapper.java   # Command ↔ Domain
│
├── adapter/
│   ├── in/
│   │   ├── http/
│   │   │   ├── PedidoController.java      # REST endpoints
│   │   │   ├── dto/
│   │   │   │   ├── CreatePedidoRequest.java   # (record DTO)
│   │   │   │   └── PedidoResponse.java       # (record DTO)
│   │   │   └── mapper/
│   │   │       └── PedidoHttpMapper.java     # Request/Response ↔ Command
│   │   │
│   │   ├── messaging/
│   │   │   └── ClienteEventListener.java  # SQS/SNS listeners
│   │   │
│   │   └── scheduler/
│   │       └── PedidoSyncScheduler.java   # @Scheduled jobs
│   │
│   └── out/
│       ├── persistence/
│       │   ├── entity/
│       │   │   ├── PedidoJpaEntity.java   # @Entity (JPA only)
│       │   │   └── ItemPedidoJpaEntity.java
│       │   ├── repository/
│       │   │   └── PedidoJpaRepository.java   # Spring Data JpaRepository
│       │   ├── adapter/
│       │   │   └── PedidoPersistenceAdapter.java  # Implementa port.out
│       │   └── mapper/
│       │       └── PedidoJpaMapper.java   # JpaEntity ↔ Domain Model
│       │
│       ├── messaging/
│       │   ├── adapter/
│       │   │   ├── SqsPedidoPublisher.java
│       │   │   └── SnsEventPublisher.java
│       │   └── dto/
│       │       └── PedidoEventMessage.java
│       │
│       ├── client/
│       │   ├── http/
│       │   │   ├── ClienteServiceClient.java  # @HttpExchange
│       │   │   └── PagamentoServiceClient.java
│       │   └── dto/
│       │       └── ClienteResponse.java
│       │
│       └── cache/
│           └── PedidoCacheAdapter.java   # Redis/Caffeine
│
└── config/
    ├── PedidoConfig.java                  # @Configuration beans
    ├── PedidoPersistenceConfig.java       # DataSource, transactions
    ├── PedidoSecurityConfig.java          # @EnableMethodSecurity
    └── PedidoObservabilityConfig.java     # OpenTelemetry, logging
```

---

## 3. Implementação Canônica do Bounded Context `pedido`

### 3.1 Domain Models (Núcleo)

```java
// domain/model/Pedido.java — Aggregate Root
package com.squad.pedidos.domain.model;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.*;
import java.util.record.*;

/**
 * Aggregate Root: Pedido
 * Responsabilidade: manter invariantes do pedido
 * 
 * Invariantes:
 * - Pedido não pode ser confirmado com 0 itens
 * - Pedido não pode ter duração negativa
 * - Total deve ser soma dos itens + frete
 */
public record Pedido(
    Long id,
    ClienteId clienteId,
    List<ItemPedido> itens,
    PedidoStatus status,
    BigDecimal total,
    Instant dataCriacao,
    Instant dataAtualizacao
) {
    // Validações (invariantes)
    public Pedido {
        if (itens == null || itens.isEmpty()) {
            throw new IllegalArgumentException("Pedido deve ter ao menos 1 item");
        }
        if (total == null || total.signum() <= 0) {
            throw new IllegalArgumentException("Total deve ser positivo");
        }
        Objects.requireNonNull(status, "Status não pode ser null");
        Objects.requireNonNull(clienteId, "ClienteId não pode ser null");
    }

    // Factory method — criar novo pedido (confirmado = false)
    public static Pedido criar(ClienteId clienteId, List<ItemPedido> itens, BigDecimal frete) {
        var total = itens.stream()
            .map(ItemPedido::subtotal)
            .reduce(BigDecimal.ZERO, BigDecimal::add)
            .add(frete);

        return new Pedido(
            null,                        // ID gerado pelo banco
            clienteId,
            new ArrayList<>(itens),      // Defensive copy
            PedidoStatus.PENDENTE,
            total,
            Instant.now(),
            Instant.now()
        );
    }

    // Métodos de domínio — ações permitidas
    public Pedido confirmar() {
        if (status != PedidoStatus.PENDENTE) {
            throw new IllegalStateException("Apenas pedidos pendentes podem ser confirmados");
        }
        return new Pedido(
            id,
            clienteId,
            itens,
            PedidoStatus.CONFIRMADO,
            total,
            dataCriacao,
            Instant.now()
        );
    }

    public Pedido cancelar() {
        if (status == PedidoStatus.ENTREGUE) {
            throw new IllegalStateException("Pedido entregue não pode ser cancelado");
        }
        return new Pedido(
            id,
            clienteId,
            itens,
            PedidoStatus.CANCELADO,
            total,
            dataCriacao,
            Instant.now()
        );
    }

    // Query methods — consultas
    public boolean podeSerConfirmado() {
        return status == PedidoStatus.PENDENTE && !itens.isEmpty();
    }

    public BigDecimal getSubtotal() {
        return itens.stream()
            .map(ItemPedido::subtotal)
            .reduce(BigDecimal.ZERO, BigDecimal::add);
    }
}

// domain/model/ItemPedido.java
public record ItemPedido(
    String sku,
    Integer quantidade,
    BigDecimal precoUnitario
) {
    public ItemPedido {
        if (quantidade == null || quantidade <= 0) {
            throw new IllegalArgumentException("Quantidade deve ser positiva");
        }
        if (precoUnitario == null || precoUnitario.signum() <= 0) {
            throw new IllegalArgumentException("Preço deve ser positivo");
        }
    }

    public BigDecimal subtotal() {
        return precoUnitario.multiply(BigDecimal.valueOf(quantidade));
    }
}

// domain/model/ClienteId.java — Value Object
public record ClienteId(Long valor) {
    public ClienteId {
        if (valor == null || valor <= 0) {
            throw new IllegalArgumentException("ClienteId deve ser positivo");
        }
    }
}

// domain/model/PedidoStatus.java — Enum
public enum PedidoStatus {
    PENDENTE, CONFIRMADO, ENTREGUE, CANCELADO
}
```

### 3.2 Domain Events

```java
// domain/event/PedidoEvent.java — Sealed interface
package com.squad.pedidos.domain.event;

import java.time.Instant;

public sealed interface PedidoEvent permits
    PedidoCriadoEvent,
    PedidoConfirmadoEvent,
    PedidoCanceladoEvent {

    Long pedidoId();
    Instant timestamp();
}

// Implementações (records)
public record PedidoCriadoEvent(
    Long pedidoId,
    Long clienteId,
    java.math.BigDecimal total,
    Instant timestamp
) implements PedidoEvent {
    public PedidoCriadoEvent(Long pedidoId, Long clienteId, java.math.BigDecimal total) {
        this(pedidoId, clienteId, total, Instant.now());
    }
}

public record PedidoConfirmadoEvent(
    Long pedidoId,
    Instant timestamp
) implements PedidoEvent {}

public record PedidoCanceladoEvent(
    Long pedidoId,
    String motivo,
    Instant timestamp
) implements PedidoEvent {}
```

### 3.3 Domain Ports (Contatos com Exterior)

```java
// domain/port/in/ConfirmarPedidoUseCase.java
package com.squad.pedidos.domain.port.in;

import com.squad.pedidos.domain.model.Pedido;

/**
 * Porta de entrada (driver port): Use case de confirmação de pedido
 * Implementada por: application/usecase/ConfirmarPedidoService
 */
public interface ConfirmarPedidoUseCase {
    Pedido confirmar(Long pedidoId);
}

// domain/port/out/PedidoRepository.java
public interface PedidoRepository {
    Pedido salvar(Pedido pedido);
    Pedido encontrarPorId(Long id);
    List<Pedido> listarPorCliente(Long clienteId);
}

// domain/port/out/PedidoPublisher.java — Domain events
public interface PedidoPublisher {
    void publicar(PedidoEvent evento);
}
```

### 3.4 Domain Service (Lógica Stateless)

```java
// domain/service/CalcularFreteService.java
package com.squad.pedidos.domain.service;

import java.math.BigDecimal;
import com.squad.pedidos.domain.model.ItemPedido;

/**
 * Domain Service: stateless, sem identidade
 * Responsabilidade: cálculos específicos de domínio
 */
public class CalcularFreteService {

    public BigDecimal calcularFrete(List<ItemPedido> itens, String cep) {
        var peso = itens.stream()
            .mapToDouble(i -> i.quantidade() * 0.5)  // 500g por item
            .sum();

        if (peso < 1.0) {
            return BigDecimal.valueOf(5.0);      // Mínimo
        } else if (peso < 10.0) {
            return BigDecimal.valueOf(10.0);
        } else {
            return BigDecimal.valueOf(20.0);
        }
    }
}
```

### 3.5 Application Use Cases

```java
// application/usecase/ConfirmarPedidoService.java
package com.squad.pedidos.application.usecase;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.squad.pedidos.domain.model.Pedido;
import com.squad.pedidos.domain.port.in.ConfirmarPedidoUseCase;
import com.squad.pedidos.domain.port.out.PedidoRepository;
import com.squad.pedidos.domain.port.out.PedidoPublisher;
import com.squad.pedidos.domain.event.PedidoConfirmadoEvent;

/**
 * Use Case: Confirmar Pedido
 * Orquestra operações do domínio
 */
@Service
public class ConfirmarPedidoService implements ConfirmarPedidoUseCase {

    private final PedidoRepository repository;
    private final PedidoPublisher publisher;

    public ConfirmarPedidoService(PedidoRepository repository, PedidoPublisher publisher) {
        this.repository = repository;
        this.publisher = publisher;
    }

    @Override
    @Transactional
    public Pedido confirmar(Long pedidoId) {
        // 1. Recuperar
        var pedido = repository.encontrarPorId(pedidoId);

        // 2. Chamar domínio (método puro)
        var confirmado = pedido.confirmar();  // Pode lançar exceção de negócio

        // 3. Persistir
        var salvo = repository.salvar(confirmado);

        // 4. Publicar evento (sempre depois de salvar)
        publisher.publicar(new PedidoConfirmadoEvent(pedidoId, Instant.now()));

        // 5. Retornar
        return salvo;
    }
}

// application/dto/ConfirmarPedidoCommand.java
public record ConfirmarPedidoCommand(Long pedidoId) {}

// application/dto/PedidoResult.java
public record PedidoResult(
    Long id,
    Long clienteId,
    List<ItemResult> itens,
    String status,
    java.math.BigDecimal total
) {}
```

### 3.6 Adapters IN (HTTP)

```java
// adapter/in/http/PedidoController.java
package com.squad.pedidos.adapter.in.http;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import com.squad.pedidos.domain.port.in.ConfirmarPedidoUseCase;
import com.squad.pedidos.adapter.in.http.dto.CreatePedidoRequest;
import com.squad.pedidos.adapter.in.http.dto.PedidoResponse;

/**
 * Adapter de entrada: REST HTTP
 * Responsabilidade: parsing HTTP, orquestração de use cases
 */
@RestController
@RequestMapping("/api/pedidos")
public class PedidoController {

    private final ConfirmarPedidoUseCase confirmarUseCase;
    private final PedidoHttpMapper mapper;

    public PedidoController(ConfirmarPedidoUseCase confirmarUseCase, PedidoHttpMapper mapper) {
        this.confirmarUseCase = confirmarUseCase;
        this.mapper = mapper;
    }

    @PostMapping("/{pedidoId}/confirmar")
    public ResponseEntity<PedidoResponse> confirmar(@PathVariable Long pedidoId) {
        var pedido = confirmarUseCase.confirmar(pedidoId);
        return ResponseEntity.ok(mapper.toPedidoResponse(pedido));
    }

    @GetMapping("/{pedidoId}")
    public ResponseEntity<PedidoResponse> obter(@PathVariable Long pedidoId) {
        // Chamar use case de consulta
        // ...
    }
}

// adapter/in/http/dto/CreatePedidoRequest.java
public record CreatePedidoRequest(
    Long clienteId,
    List<ItemRequest> itens,
    java.math.BigDecimal frete
) {}

public record ItemRequest(String sku, Integer quantidade, java.math.BigDecimal precoUnitario) {}

// adapter/in/http/dto/PedidoResponse.java
public record PedidoResponse(
    Long id,
    Long clienteId,
    List<ItemResponse> itens,
    String status,
    java.math.BigDecimal total
) {}

// adapter/in/http/mapper/PedidoHttpMapper.java
@Component
public class PedidoHttpMapper {
    public PedidoResponse toPedidoResponse(Pedido pedido) {
        return new PedidoResponse(
            pedido.id(),
            pedido.clienteId().valor(),
            pedido.itens().stream()
                .map(i -> new ItemResponse(i.sku(), i.quantidade(), i.precoUnitario()))
                .toList(),
            pedido.status().toString(),
            pedido.total()
        );
    }
}
```

### 3.7 Adapters OUT (Persistence)

```java
// adapter/out/persistence/entity/PedidoJpaEntity.java
package com.squad.pedidos.adapter.out.persistence.entity;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;

/**
 * JPA Entity: CONFINADA neste pacote
 * Nunca sai para fora de adapter/out/persistence/entity/
 * Mapeamento completo ORM
 */
@Entity
@Table(name = "pedidos")
public class PedidoJpaEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private Long clienteId;

    @Column(nullable = false)
    private String status;  // PENDENTE, CONFIRMADO, ENTREGUE, CANCELADO

    @Column(nullable = false)
    private BigDecimal total;

    @Column(nullable = false)
    private Instant dataCriacao;

    @Column(nullable = false)
    private Instant dataAtualizacao;

    @OneToMany(cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.EAGER)
    @JoinColumn(name = "pedido_id")
    private List<ItemPedidoJpaEntity> itens = new ArrayList<>();

    // Getters/Setters (usados apenas por JPA)
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    // ... etc
}

// adapter/out/persistence/repository/PedidoJpaRepository.java
@Repository
public interface PedidoJpaRepository extends JpaRepository<PedidoJpaEntity, Long> {
    List<PedidoJpaEntity> findByClienteId(Long clienteId);
}

// adapter/out/persistence/adapter/PedidoPersistenceAdapter.java
/**
 * Adapter OUT: implementa PedidoRepository (port.out)
 * Converte entre Domain Model e JPA Entity
 */
@Component
public class PedidoPersistenceAdapter implements PedidoRepository {

    private final PedidoJpaRepository jpaRepository;
    private final PedidoJpaMapper mapper;

    public PedidoPersistenceAdapter(PedidoJpaRepository jpaRepository, PedidoJpaMapper mapper) {
        this.jpaRepository = jpaRepository;
        this.mapper = mapper;
    }

    @Override
    public Pedido salvar(Pedido pedido) {
        var entity = mapper.toJpaEntity(pedido);
        var saved = jpaRepository.save(entity);
        return mapper.toDomainModel(saved);
    }

    @Override
    public Pedido encontrarPorId(Long id) {
        return jpaRepository.findById(id)
            .map(mapper::toDomainModel)
            .orElseThrow(() -> new PedidoNaoEncontradoException(id));
    }

    @Override
    public List<Pedido> listarPorCliente(Long clienteId) {
        return jpaRepository.findByClienteId(clienteId).stream()
            .map(mapper::toDomainModel)
            .toList();
    }
}

// adapter/out/persistence/mapper/PedidoJpaMapper.java
@Component
public class PedidoJpaMapper {

    public PedidoJpaEntity toJpaEntity(Pedido pedido) {
        var entity = new PedidoJpaEntity();
        entity.setId(pedido.id());
        entity.setClienteId(pedido.clienteId().valor());
        entity.setStatus(pedido.status().toString());
        entity.setTotal(pedido.total());
        entity.setDataCriacao(pedido.dataCriacao());
        entity.setDataAtualizacao(pedido.dataAtualizacao());
        entity.setItens(pedido.itens().stream()
            .map(i -> {
                var itemEntity = new ItemPedidoJpaEntity();
                itemEntity.setSku(i.sku());
                itemEntity.setQuantidade(i.quantidade());
                itemEntity.setPrecoUnitario(i.precoUnitario());
                return itemEntity;
            })
            .toList());
        return entity;
    }

    public Pedido toDomainModel(PedidoJpaEntity entity) {
        return new Pedido(
            entity.getId(),
            new ClienteId(entity.getClienteId()),
            entity.getItens().stream()
                .map(i -> new ItemPedido(i.getSku(), i.getQuantidade(), i.getPrecoUnitario()))
                .toList(),
            PedidoStatus.valueOf(entity.getStatus()),
            entity.getTotal(),
            entity.getDataCriacao(),
            entity.getDataAtualizacao()
        );
    }
}
```

---

## 4. Padrões de Mapper

### Opção 1: Mapper Manual (Recomendado para Agregados Complexos)

Você controla mapeamento, invariantes:

```java
@Component
public class PedidoJpaMapper {
    public Pedido toDomain(PedidoJpaEntity entity) {
        // Validação, lógica customizada
        return new Pedido(...);
    }
}
```

**Vantagens:**
- Controle total sobre conversão
- Fácil debugar
- Invariantes respeitados

**Desvantagens:**
- Boilerplate
- Manutenção em 2 lugares (Entity + Domain)

### Opção 2: MapStruct (Boilerplate automático)

```xml
<!-- pom.xml -->
<dependency>
    <groupId>org.mapstruct</groupId>
    <artifactId>mapstruct</artifactId>
    <version>1.5.5.Final</version>
</dependency>
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-compiler-plugin</artifactId>
    <configuration>
        <annotationProcessorPaths>
            <path>
                <groupId>org.mapstruct</groupId>
                <artifactId>mapstruct-processor</artifactId>
                <version>1.5.5.Final</version>
            </path>
        </annotationProcessorPaths>
    </configuration>
</plugin>
```

```java
@Mapper(componentModel = "spring")
public interface PedidoJpaMapper {
    @Mapping(source = "clienteId.valor", target = "clienteId")
    PedidoJpaEntity toJpaEntity(Pedido pedido);

    @Mapping(source = "clienteId", target = "clienteId.valor")
    Pedido toDomain(PedidoJpaEntity entity);
}
```

**Vantagens:**
- Menos boilerplate
- Compile-time validation

**Desvantagens:**
- Menos controle
- Lógica complexa não encaixa bem

---

## 5. Configuração Spring Boot 4

```java
// config/PedidoConfig.java
package com.squad.pedidos.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import com.squad.pedidos.domain.port.out.PedidoRepository;
import com.squad.pedidos.domain.port.out.PedidoPublisher;
import com.squad.pedidos.domain.port.in.ConfirmarPedidoUseCase;
import com.squad.pedidos.application.usecase.ConfirmarPedidoService;
import com.squad.pedidos.domain.service.CalcularFreteService;

/**
 * Spring Configuration: beans de domínio e use cases
 */
@Configuration
public class PedidoConfig {

    @Bean
    CalcularFreteService calculadorFrete() {
        return new CalcularFreteService();
    }

    @Bean
    ConfirmarPedidoUseCase confirmarPedidoUseCase(
        PedidoRepository repository,
        PedidoPublisher publisher) {
        return new ConfirmarPedidoService(repository, publisher);
    }
}
```

---

## 6. Validação de Arquitetura (ArchUnit)

Ver `archunit-rules.md` para testes automatizados que garantem:
- Domain não importa Spring
- Controllers não acessam repositories
- Entities confinadas em pacote específico
- Use cases implementam ports

---

## 7. Checklist de Implementação

- [ ] Estrutura de pacotes criada conforme GLOSSARIO §6
- [ ] Domain Models (records) implementados
- [ ] Ports (in/out) definidas
- [ ] Domain Services sem estado
- [ ] Use Cases implementam ports.in
- [ ] Adapters implementam ports.out
- [ ] Mappers (Domain ↔ JPA, ↔ HTTP) funcionando
- [ ] Controllers orquestram use cases
- [ ] ArchUnit validando invariantes
- [ ] Testes unitários em Domain
- [ ] Testes de integração em Application
- [ ] Testes E2E em Adapter.in

---

## Referências

- Robert C. Martin — "Clean Architecture" (2017)
- Alistair Cockburn — "Hexagonal Architecture" (2005)
- Eric Evans — "Domain-Driven Design" (2003)
- GLOSSARIO §6 — Organização de Pacotes
- `archunit-rules.md` — Validação automática

