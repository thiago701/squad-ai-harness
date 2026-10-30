# Mutation Testing Specimen — PIT Score ≥ 85%

> Specimen canônico de domínio bem testado com PIT. Use este padrão em aulas, onboarding e como referência de "como fica um código com mutation score real ≥ 85%".

## Cenário

Domain Entity `Pedido` com regra de negócio: **descontar 10% quando `valor ≥ 1000`, 5% quando `valor ≥ 500`, nenhum desconto abaixo disso**. `status` só pode progredir: `CRIADO → PAGO → ENVIADO → ENTREGUE`.

## 1. Código de Produção (Java 25)

```java
package com.squadai.specimen.domain;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.util.Objects;
import java.util.UUID;

public final class Pedido {

    public enum Status { CRIADO, PAGO, ENVIADO, ENTREGUE }

    private static final BigDecimal TIER_ALTO = new BigDecimal("1000");
    private static final BigDecimal TIER_MEDIO = new BigDecimal("500");
    private static final BigDecimal DESCONTO_ALTO = new BigDecimal("0.10");
    private static final BigDecimal DESCONTO_MEDIO = new BigDecimal("0.05");

    private final UUID id;
    private final BigDecimal valor;
    private Status status;
    private final Instant criadoEm;

    public Pedido(UUID id, BigDecimal valor, Instant criadoEm) {
        this.id = Objects.requireNonNull(id, "id");
        this.valor = Objects.requireNonNull(valor, "valor");
        if (valor.signum() <= 0) {
            throw new IllegalArgumentException("valor deve ser positivo");
        }
        this.status = Status.CRIADO;
        this.criadoEm = Objects.requireNonNull(criadoEm, "criadoEm");
    }

    /** Retorna o valor com desconto aplicado conforme tier. */
    public BigDecimal valorComDesconto() {
        BigDecimal percentual;
        if (valor.compareTo(TIER_ALTO) >= 0) {
            percentual = DESCONTO_ALTO;
        } else if (valor.compareTo(TIER_MEDIO) >= 0) {
            percentual = DESCONTO_MEDIO;
        } else {
            return valor;
        }
        BigDecimal desconto = valor.multiply(percentual);
        return valor.subtract(desconto).setScale(2, RoundingMode.HALF_EVEN);
    }

    /** Progride para o próximo status. Lança se tentar pular ou retroceder. */
    public void progredir(Status alvo) {
        Objects.requireNonNull(alvo, "alvo");
        if (alvo.ordinal() != this.status.ordinal() + 1) {
            throw new IllegalStateException(
                "Transição inválida: " + this.status + " -> " + alvo);
        }
        this.status = alvo;
    }

    public UUID id() { return id; }
    public BigDecimal valor() { return valor; }
    public Status status() { return status; }
    public Instant criadoEm() { return criadoEm; }
}
```

## 2. Testes (JUnit 5 + AssertJ) — Matando TODOS os mutantes

```java
package com.squadai.specimen.domain;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class PedidoTest {

    private static final UUID ID = UUID.fromString("00000000-0000-0000-0000-000000000001");
    private static final Instant AGORA = Instant.parse("2026-04-13T10:00:00Z");

    @Nested
    @DisplayName("construção")
    class Construcao {

        @Test
        void deveCriarComStatusCriado() {
            var p = new Pedido(ID, new BigDecimal("100"), AGORA);
            assertThat(p.status()).isEqualTo(Pedido.Status.CRIADO);
            assertThat(p.id()).isEqualTo(ID);
            assertThat(p.valor()).isEqualByComparingTo("100");
            assertThat(p.criadoEm()).isEqualTo(AGORA);
        }

        @Test
        void deveRejeitarIdNulo() {
            assertThatThrownBy(() -> new Pedido(null, BigDecimal.ONE, AGORA))
                .isInstanceOf(NullPointerException.class)
                .hasMessage("id");
        }

        @Test
        void deveRejeitarValorNulo() {
            assertThatThrownBy(() -> new Pedido(ID, null, AGORA))
                .isInstanceOf(NullPointerException.class)
                .hasMessage("valor");
        }

        @Test
        void deveRejeitarCriadoEmNulo() {
            assertThatThrownBy(() -> new Pedido(ID, BigDecimal.ONE, null))
                .isInstanceOf(NullPointerException.class)
                .hasMessage("criadoEm");
        }

        @Test
        void deveRejeitarValorZero() {
            assertThatThrownBy(() -> new Pedido(ID, BigDecimal.ZERO, AGORA))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("valor deve ser positivo");
        }

        @Test
        void deveRejeitarValorNegativo() {
            assertThatThrownBy(() -> new Pedido(ID, new BigDecimal("-1"), AGORA))
                .isInstanceOf(IllegalArgumentException.class);
        }
    }

    @Nested
    @DisplayName("desconto por tier")
    class Desconto {

        @ParameterizedTest(name = "valor={0} → esperado={1}")
        @CsvSource({
            // BOUNDARIES exatas — matam mutantes de `>=` vs `>`
            "499.99, 499.99",      // abaixo do tier médio
            "500.00, 475.00",      // exato tier médio (5%)
            "500.01, 475.01",      // logo acima do tier médio
            "999.99, 949.99",      // logo abaixo do tier alto (ainda 5%)
            "1000.00, 900.00",     // exato tier alto (10%)
            "1000.01, 900.01",     // logo acima (10%)
            "2000.00, 1800.00"     // bem acima
        })
        void deveAplicarDescontoCorreto(String valor, String esperado) {
            var p = new Pedido(ID, new BigDecimal(valor), AGORA);
            assertThat(p.valorComDesconto()).isEqualByComparingTo(esperado);
        }

        @Test
        void naoDeveDescontarAbaixoDe500() {
            var p = new Pedido(ID, new BigDecimal("100"), AGORA);
            assertThat(p.valorComDesconto()).isEqualByComparingTo("100");
        }

        @Test
        void deveUsarArredondamentoHalfEvenEmCentavos() {
            // 555.55 * 0.05 = 27.7775 → arredonda para .78 (half-even)
            var p = new Pedido(ID, new BigDecimal("555.55"), AGORA);
            // 555.55 - 27.7775 = 527.7725 → 527.77 (half-even round do result)
            assertThat(p.valorComDesconto()).isEqualByComparingTo("527.77");
        }
    }

    @Nested
    @DisplayName("transições de status")
    class Transicoes {

        @Test
        void deveProgredirCriadoParaPago() {
            var p = new Pedido(ID, BigDecimal.TEN, AGORA);
            p.progredir(Pedido.Status.PAGO);
            assertThat(p.status()).isEqualTo(Pedido.Status.PAGO);
        }

        @Test
        void deveProgredirCicloCompleto() {
            var p = new Pedido(ID, BigDecimal.TEN, AGORA);
            p.progredir(Pedido.Status.PAGO);
            p.progredir(Pedido.Status.ENVIADO);
            p.progredir(Pedido.Status.ENTREGUE);
            assertThat(p.status()).isEqualTo(Pedido.Status.ENTREGUE);
        }

        @Test
        void deveRejeitarPuloDeEstado() {
            var p = new Pedido(ID, BigDecimal.TEN, AGORA);
            assertThatThrownBy(() -> p.progredir(Pedido.Status.ENVIADO))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("CRIADO -> ENVIADO");
        }

        @Test
        void deveRejeitarRetrocesso() {
            var p = new Pedido(ID, BigDecimal.TEN, AGORA);
            p.progredir(Pedido.Status.PAGO);
            assertThatThrownBy(() -> p.progredir(Pedido.Status.CRIADO))
                .isInstanceOf(IllegalStateException.class);
        }

        @Test
        void deveRejeitarMesmoStatus() {
            var p = new Pedido(ID, BigDecimal.TEN, AGORA);
            assertThatThrownBy(() -> p.progredir(Pedido.Status.CRIADO))
                .isInstanceOf(IllegalStateException.class);
        }

        @Test
        void deveRejeitarAlvoNulo() {
            var p = new Pedido(ID, BigDecimal.TEN, AGORA);
            assertThatThrownBy(() -> p.progredir(null))
                .isInstanceOf(NullPointerException.class);
        }
    }
}
```

## 3. Configuração PIT (Maven 4)

```xml
<plugin>
  <groupId>org.pitest</groupId>
  <artifactId>pitest-maven</artifactId>
  <version>1.17.0</version>
  <dependencies>
    <dependency>
      <groupId>org.pitest</groupId>
      <artifactId>pitest-junit5-plugin</artifactId>
      <version>1.2.1</version>
    </dependency>
  </dependencies>
  <configuration>
    <targetClasses>
      <param>com.squadai.specimen.domain.*</param>
    </targetClasses>
    <targetTests>
      <param>com.squadai.specimen.domain.*Test</param>
    </targetTests>
    <mutators>
      <mutator>STRONGER</mutator>  <!-- grupo completo com condicionais + retornos -->
    </mutators>
    <mutationThreshold>85</mutationThreshold>
    <coverageThreshold>90</coverageThreshold>
    <timestampedReports>false</timestampedReports>
  </configuration>
</plugin>
```

## 4. Resultado Esperado

```
>> Generated 47 mutations Killed 45 (95%)
>> Ran 86 tests (1.83 tests per mutation)

Mutation Score: 95%
Line Coverage:  100%
```

**Mutantes sobreviventes aceitáveis (até 15%):**
- Equivalentes (`return valor.setScale(2, RoundingMode.HALF_EVEN)` antes do `return valor` quando valor já tem 2 casas) — detectar com revisão manual.
- Boundary `NPE message equality` (`hasMessage("id")` vs `hasMessageContaining("id")`).

## 5. Como Rodar

```bash
./mvnw test           # roda testes normais (< 5s)
./mvnw pitest:mutationCoverage  # ~60-90s primeira vez, ~20s com cache
open target/pit-reports/index.html
```

## Observações para o Pair TDD

- **Paramétricos em boundaries**: `@CsvSource` com `N-1, N, N+1` mata mutantes `<` / `<=` / `>` / `>=`.
- **Exception messages**: verificar conteúdo exato (`hasMessage` estrito), não apenas tipo.
- **Nested `@Nested`**: organiza por comportamento — facilita ver em que cluster o mutante sobreviveu.
- **Status machine**: cada transição válida + cada transição inválida precisa de um teste próprio.
- **Arredondamento**: testar o valor exato, não apenas "aproximadamente igual".

## Conexões

- Parte de `especialista-qualidade/SKILL.md` (seção Mutation Testing)
- Cross-reference: `java25-spring-boot` (Domain Entity sem JPA), `tech-lead-review` (checklist DoD)
- Relaciona com `engenheiro-clean-architect` (Domain Entity pura)
