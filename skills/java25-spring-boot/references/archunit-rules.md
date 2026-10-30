# ArchUnit — Testes de Arquitetura como Código

> **Propósito:** Automatizar validação de arquitetura de software em testes JUnit,
> prevenindo regressões arquiteturais e aplicando regras de Clean Architecture + Hexagonal.
>
> **Referência:** GLOSSARIO §6 (Organização de Pacotes), este documento + `clean-architecture-java.md`.

**Última atualização:** 2026-04-10

---

## 1. Visão Geral — Por Que ArchUnit?

Código Java é fácil de escrever, mas fácil de quebrar arquiteturalmente. ArchUnit permite
testar invariantes de arquitetura com a mesma rigorosidade que testes de lógica de negócio:

- **Prevenção de regressão:** evitar imports cruzados entre camadas
- **Validação de padrões:** garantir que controllers não acessam repositories direto
- **Naming conventions:** assegurar que Entities vivem em pacote específico
- **Anti-padrões:** bloquear `System.out.println`, `@Autowired` em campo, etc.

```
SEM ArchUnit:
  Arq review → feedback tardio → rebase frustrado → código quebrado em produção

COM ArchUnit:
  `mvn test` falha imediatamente → desenvolvedor corrige → PR clean
```

---

## 2. Setup Maven

```xml
<!-- pom.xml — dependência de teste -->
<dependency>
    <groupId>com.tngtech.archunit</groupId>
    <artifactId>archunit-junit5</artifactId>
    <version>1.3.0</version>
    <scope>test</scope>
</dependency>
```

---

## 3. Regras Canônicas (Clean Architecture + Hexagonal)

Todas as regras abaixo implementam os invariantes do GLOSSARIO §6:

```java
// ArchitectureTest.java — Arquivo único que centraliza todas as regras

import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.junit5.AnalyzeClasses;
import com.tngtech.archunit.junit5.ArchTest;
import com.tngtech.archunit.library.Architectures;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.*;
import static com.tngtech.archunit.library.freeze.FreezingArchRule.*;

@AnalyzeClasses(packages = "com.squad.pedidos")
class ArchitectureTest {

    // ========== REGRA 1: Domain não importa nada da aplicação ==========
    @ArchTest
    static final ArchRule domain_nao_depende_de_infra =
        noClasses().that().resideInAPackage("..domain..")
            .should().dependOnClassesThat().resideInAnyPackage(
                "..adapter..",
                "..application..",
                "..config..",
                "org.springframework..",
                "jakarta.persistence..",
                "com.fasterxml.jackson.."
            );

    // ========== REGRA 2: Use Cases implementam Ports de entrada ==========
    @ArchTest
    static final ArchRule usecases_implementam_ports_entrada =
        classes().that().resideInAPackage("..application.usecase..")
            .and().haveSimpleNameEndingWith("Service")
            .should().implement(
                JavaClass.Predicates.resideInAPackage("..domain.port.in..")
            );

    // ========== REGRA 3: Adapters OUT implementam Ports de saída ==========
    @ArchTest
    static final ArchRule adapter_out_implementa_ports_saida =
        classes().that().resideInAPackage("..adapter.out..")
            .and().haveSimpleNameEndingWith("Adapter")
            .should().implement(
                JavaClass.Predicates.resideInAPackage("..domain.port.out..")
            );

    // ========== REGRA 4: Controllers NÃO acessam Repositories direto ==========
    @ArchTest
    static final ArchRule controllers_nao_acessam_repositories =
        noClasses().that().resideInAPackage("..adapter.in.http..")
            .should().dependOnClassesThat().resideInAPackage("..adapter.out.persistence..");

    // ========== REGRA 5: JPA Entities vivem isoladas em pacote específico ==========
    @ArchTest
    static final ArchRule jpa_entities_nao_vazam =
        classes().that().areAnnotatedWith(Entity.class)
            .should().resideInAPackage("..adapter.out.persistence.entity..");

    // ========== REGRA 6: Limites de Agregado — Aggregate Root não é acessado externamente ==========
    // Exemplo: Item de Pedido só pode ser acessado via Pedido (Aggregate Root)
    @ArchTest
    static final ArchRule aggregate_root_invariant =
        classes().that().resideInAPackage("..pedido.item..")
            .should().onlyBeAccessed()
            .byClassesThat().resideInAPackage("..pedido..");

    // ========== REGRA 7: Domain Services não têm identidade ==========
    @ArchTest
    static final ArchRule domain_services_sao_stateless =
        classes().that().resideInAPackage("..domain.service..")
            .should().onlyHaveFields()
            .that().areFinal()
            .and().haveRawType(Object.class);  // Apenas dependências finais

    // ========== REGRA 8: Naming Conventions ==========
    @ArchTest
    static final ArchRule controllers_terminam_em_controller =
        classes().that().resideInAPackage("..adapter.in.http..")
            .should().haveSimpleNameEndingWith("Controller");

    @ArchTest
    static final ArchRule adapters_out_terminam_em_adapter =
        classes().that().resideInAPackage("..adapter.out..")
            .should().haveSimpleNameEndingWith("Adapter");

    @ArchTest
    static final ArchRule usecases_terminam_em_service =
        classes().that().resideInAPackage("..application.usecase..")
            .should().haveSimpleNameEndingWith("Service");

    // ========== REGRA 9: Proibir anti-padrões ==========
    @ArchTest
    static final ArchRule nao_use_system_out =
        noClasses().should().callMethodWhere(
            target -> target.getFullName().contains("System.out.println")
                || target.getFullName().contains("System.err.println")
        );

    @ArchTest
    static final ArchRule nao_use_autowired_em_campo =
        noFields().that().areDeclaredInClassesThat()
            .areAnnotatedWith(Component.class)
            .should().beAnnotatedWith(Autowired.class);  // Força constructor injection

    @ArchTest
    static final ArchRule nao_use_junit3_extends_testcase =
        noClasses().that().resideInAPackage("..test..")
            .should().beAssignableTo(
                JavaClass.Predicates.haveNameMatching(".*TestCase")
            );
}
```

---

## 4. Layered Architecture Check (Alternativa Simplificada)

Para projetos mais simples (não múltiplos bounded contexts):

```java
@AnalyzeClasses(packages = "com.example")
class LayeredArchitectureTest {

    @ArchTest
    static final ArchRule layered_architecture = Architectures.layeredArchitecture()
        .consideringAllDependencies()

        // Definir camadas
        .layer("Domain").definedBy("..domain..")
        .layer("Application").definedBy("..application..")
        .layer("Adapter").definedBy("..adapter..")
        .layer("Config").definedBy("..config..")

        // Regras de acesso
        .whereLayer("Adapter").mayNotBeAccessedByAnyLayer()
        .whereLayer("Application").mayOnlyBeAccessedByLayers("Adapter", "Config")
        .whereLayer("Domain").mayOnlyBeAccessedByLayers("Application", "Adapter")
        .whereLayer("Config").mayAccessAnyLayer();
}
```

**Matriz de acesso:**

```
      ┌─────────┬────────────┬─────────┬────────┐
      │ Domain  │ Application│ Adapter │ Config │
├─────┼─────────┼────────────┼─────────┼────────┤
│Domain │   ✓     │     ❌     │   ❌    │   ❌   │
├─────┼─────────┼────────────┼─────────┼────────┤
│Appl │   ✓     │     ✓      │   ❌    │   ❌   │
├─────┼─────────┼────────────┼─────────┼────────┤
│Adapt│   ✓     │     ✓      │   ✓     │   ❌   │
├─────┼─────────┼────────────┼─────────┼────────┤
│Config│  ✓     │     ✓      │   ✓     │   ✓    │
└─────┴─────────┴────────────┴─────────┴────────┘
```

---

## 5. Freestyle Rules (Casos Customizados)

```java
@ArchTest
static final ArchRule custom_no_reflection_in_domain =
    noClasses().that().resideInAPackage("..domain..")
        .should().callMethodWhere(
            target -> target.getFullName().contains("java.lang.reflect")
                || target.getFullName().contains("java.lang.Class.forName")
        );

@ArchTest
static final ArchRule dto_tem_prefixo_ou_sufixo_correto =
    classes().that().resideInAPackage("..adapter.in.http.dto..")
        .should()
        .haveSimpleNameEndingWith("Request")
        .orShould()
        .haveSimpleNameEndingWith("Response")
        .orShould()
        .haveSimpleNameEndingWith("DTO");
```

---

## 6. Freezing Rules (Tolerância Temporária)

Se uma regra já é violada no código existente, usar `FreezingArchRule` para permitir
estado atual mas prevenir novos problemas:

```java
@ArchTest
static final ArchRule domain_nao_importa_spring_FROZEN =
    freeze(
        noClasses().that().resideInAPackage("..domain..")
            .should().dependOnClassesThat().resideInAPackage("org.springframework..")
    );

// Mensagem ao falhar:
// "Frozen rule violated: 5 existing violations detected
//  Cannot add new violations. Please fix and then unfreeze."
```

**Workflow:**
1. Marcar regra com `freeze()` quando há violations existentes
2. Novos commits não podem AUMENTAR o número de violations
3. Quando todas as violations forem corrigidas, remover `freeze()`

---

## 7. Integração CI (GitHub Actions)

```yaml
# .github/workflows/archunit.yml
name: Architecture Tests

on: [push, pull_request]

jobs:
  archunit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up JDK 25
        uses: actions/setup-java@v4
        with:
          java-version: '25'
          distribution: 'temurin'
      
      - name: Run Architecture Tests
        run: mvn test -Dtest=*ArchitectureTest
      
      - name: Upload ArchUnit Report
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: archunit-violations
          path: target/archunit-reports/
```

**Output esperado:**
```
[INFO] --- maven-surefire-plugin:3.0.0:test (default-test) @ pedidos-service ---
[INFO] Running com.squad.pedidos.ArchitectureTest
[INFO] Tests run: 9, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 2.543 s
[INFO] BUILD SUCCESS
```

---

## 8. Exemplo Real Completo (Bounded Context `pedido`)

Estrutura:
```
com/squad/pedidos/
├── domain/
│   ├── model/
│   │   ├── Pedido.java          (Aggregate Root)
│   │   └── ItemPedido.java      (entidade dentro de Pedido)
│   ├── port/
│   │   ├── in/
│   │   │   └── ConfirmarPedidoUseCase.java
│   │   └── out/
│   │       └── PedidoRepository.java
│   ├── event/
│   │   └── PedidoConfirmadoEvent.java
│   └── exception/
│       └── PedidoNaoEncontradoException.java
│
├── application/
│   ├── usecase/
│   │   └── ConfirmarPedidoService.java
│   └── dto/
│       └── ConfirmarPedidoCommand.java
│
├── adapter/
│   ├── in/
│   │   └── http/
│   │       ├── PedidoController.java
│   │       └── dto/
│   │           ├── PedidoRequest.java
│   │           └── PedidoResponse.java
│   └── out/
│       ├── persistence/
│       │   ├── entity/
│       │   │   └── PedidoJpaEntity.java
│       │   ├── PedidoJpaRepository.java
│       │   ├── PedidoPersistenceAdapter.java
│       │   └── PedidoJpaMapper.java
│       └── messaging/
│           └── PedidoPublisher.java
│
└── config/
    └── PedidoConfig.java
```

**Teste de arquitetura correspondente:**

```java
@AnalyzeClasses(packages = "com.squad.pedidos")
class PedidoArchitectureTest {

    @ArchTest
    static final ArchRule domain_isolado =
        noClasses().that().resideInAPackage("..domain..")
            .should().dependOnClassesThat().resideInAnyPackage(
                "..adapter..", "..application..", "..config..",
                "org.springframework..", "jakarta.persistence.."
            );

    @ArchTest
    static final ArchRule pedido_entity_confinada =
        classes().that().areAnnotatedWith(Entity.class)
            .should().resideInAPackage("..adapter.out.persistence.entity..");

    @ArchTest
    static final ArchRule controller_nao_acessa_repository =
        noClasses().that().resideInAPackage("..adapter.in.http..")
            .should().dependOnClassesThat().resideInAPackage(
                "..adapter.out.persistence.."
            );

    @ArchTest
    static final ArchRule item_pedido_acesso_limitado =
        classes().that().haveSimpleNameStartingWith("ItemPedido")
            .should().onlyBeAccessedByClassesThat()
            .resideInAPackage("..domain.model..");
}
```

---

## 9. Checklist de Implementação

- [ ] Dependência ArchUnit adicionada ao `pom.xml` (scope test)
- [ ] Arquivo de teste único `ArchitectureTest.java` criado
- [ ] Pacotes analisados configurados em `@AnalyzeClasses`
- [ ] Regra 1: Domain isolado
- [ ] Regra 2: Use cases implementam ports entrada
- [ ] Regra 3: Adapters OUT implementam ports saída
- [ ] Regra 4: Controllers não acessam repositories
- [ ] Regra 5: JPA Entities confinadas
- [ ] Naming conventions validadas
- [ ] Anti-padrões bloqueados (System.out, @Autowired field)
- [ ] CI configurada (maven-surefire ou GitHub Actions)
- [ ] Documentação arquitetural atualizada

---

## Referências

- [ArchUnit Official Docs](https://www.archunit.org/)
- [ArchUnit GitHub](https://github.com/TNG/ArchUnit)
- GLOSSARIO §6 — Organização de Pacotes
- `clean-architecture-java.md` — Exemplo completo de projeto

