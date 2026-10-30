#!/usr/bin/env python3
"""
Squad AI — Project Generator

Materializa um projeto Java 25 + Spring Boot 4 + Spring 7 seguindo os padrões da squad:
Maven 4 multi-module, Clean Architecture, CQRS + Outbox, DDD forte, Aurora PG, Testcontainers.

Uso:
  python generate_project.py \\
      --name pedidos-api \\
      --group-id com.example \\
      --base-package com.example.pedidos \\
      --contexts "pedidos,pagamentos" \\
      --output ./

Tudo é inline (templates como strings) para baixar a barreira de manutenção e
evitar dependências externas. Python 3.10+.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path


# =========================================================================
# Contexto
# =========================================================================

@dataclass(frozen=True)
class GenCtx:
    name: str
    group_id: str
    base_package: str
    contexts: list[str]
    java_version: str
    output: Path
    db_image: str
    with_example_aggregate: bool

    @property
    def pkg_path(self) -> str:
        return self.base_package.replace(".", "/")


def pascal(s: str) -> str:
    return "".join(part.capitalize() for part in re.split(r"[\s_\-]+", s) if part)


def camel(s: str) -> str:
    p = pascal(s)
    return p[:1].lower() + p[1:] if p else p


def snake(s: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", pascal(s)).lower().replace("-", "_")


# =========================================================================
# Escrita auxiliar
# =========================================================================

def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    print(f"  ✓ {path}")


# =========================================================================
# Templates (inline)
# =========================================================================

def tpl_root_pom(c: GenCtx) -> str:
    modules = "\n        ".join([
        "<module>domain</module>",
        "<module>application</module>",
        "<module>infrastructure</module>",
        "<module>bootstrap</module>",
    ])
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.1.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.1.0 https://maven.apache.org/xsd/maven-4.1.0.xsd">
    <modelVersion>4.1.0</modelVersion>

    <groupId>{c.group_id}</groupId>
    <artifactId>{c.name}</artifactId>
    <version>0.1.0-SNAPSHOT</version>
    <packaging>pom</packaging>

    <properties>
        <maven.compiler.release>{c.java_version}</maven.compiler.release>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
        <spring.boot.version>4.0.0-M2</spring.boot.version>
        <testcontainers.version>1.21.0</testcontainers.version>
        <archunit.version>1.3.0</archunit.version>
        <assertj.version>3.26.3</assertj.version>
        <junit.version>5.11.3</junit.version>
    </properties>

    <dependencyManagement>
        <dependencies>
            <dependency>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-dependencies</artifactId>
                <version>${{spring.boot.version}}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
            <dependency>
                <groupId>org.testcontainers</groupId>
                <artifactId>testcontainers-bom</artifactId>
                <version>${{testcontainers.version}}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
        </dependencies>
    </dependencyManagement>

    <modules>
        {modules}
    </modules>

    <build>
        <pluginManagement>
            <plugins>
                <plugin>
                    <groupId>org.apache.maven.plugins</groupId>
                    <artifactId>maven-compiler-plugin</artifactId>
                    <configuration>
                        <release>{c.java_version}</release>
                        <compilerArgs>
                            <arg>-parameters</arg>
                            <arg>-Xlint:all</arg>
                        </compilerArgs>
                    </configuration>
                </plugin>
                <plugin>
                    <groupId>org.jacoco</groupId>
                    <artifactId>jacoco-maven-plugin</artifactId>
                    <version>0.8.12</version>
                    <executions>
                        <execution>
                            <goals><goal>prepare-agent</goal></goals>
                        </execution>
                        <execution>
                            <id>report</id>
                            <phase>verify</phase>
                            <goals><goal>report</goal></goals>
                        </execution>
                    </executions>
                </plugin>
            </plugins>
        </pluginManagement>
    </build>
</project>
"""


def tpl_mvn_config() -> str:
    return "-T 1C\n--no-transfer-progress\n"


def tpl_gitignore() -> str:
    return textwrap.dedent("""
        target/
        .idea/
        *.iml
        .vscode/
        .DS_Store
        .env
        *.log
        build/
    """).lstrip()


def tpl_env_example() -> str:
    return textwrap.dedent("""
        DB_HOST=localhost
        DB_PORT=5432
        DB_NAME=app
        DB_USER=app
        DB_PASSWORD=app
        DB_POOL_MAX=20
        OTLP_ENDPOINT=http://otel-collector:4317
        OUTBOX_POLL_DELAY=500
    """).lstrip()


def tpl_dockerfile(c: GenCtx) -> str:
    return f"""# syntax=docker/dockerfile:1.7
FROM eclipse-temurin:{c.java_version}-jdk AS build
WORKDIR /src
COPY . .
RUN --mount=type=cache,target=/root/.m2 ./mvnw -T 1C -q -DskipTests package

FROM eclipse-temurin:{c.java_version}-jre AS runtime
RUN groupadd -r app && useradd -r -g app app
WORKDIR /app
COPY --from=build /src/bootstrap/target/bootstrap-*.jar app.jar
USER app
EXPOSE 8080
ENV JAVA_TOOL_OPTIONS="-XX:+UseZGC -XX:+ZGenerational \\
    -Xms512m -Xmx1024m \\
    -Dspring.profiles.active=prod"
ENTRYPOINT ["java","-jar","/app/app.jar"]
"""


def tpl_compose(c: GenCtx) -> str:
    return f"""services:
  postgres:
    image: {c.db_image}
    environment:
      POSTGRES_DB: app
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 5s
      timeout: 3s
      retries: 10

  app:
    build: .
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      SPRING_PROFILES_ACTIVE: dev
      DB_HOST: postgres
      DB_PORT: 5432
      DB_NAME: app
      DB_USER: app
      DB_PASSWORD: app
    ports:
      - "8080:8080"
"""


def tpl_ci_yml(c: GenCtx) -> str:
    return f"""name: ci
on:
  push:
    branches: [main]
  pull_request:
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '{c.java_version}'
          cache: maven
      - name: Build + tests + archunit + jacoco
        run: ./mvnw -T 1C -B verify
      - name: Upload jacoco
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: jacoco-report
          path: '**/target/site/jacoco/'
"""


def tpl_readme(c: GenCtx) -> str:
    contexts_bullets = "\n".join(f"- `{c.base_package}.domain.{ctx}` — contexto **{ctx}**" for ctx in c.contexts)
    return f"""# {c.name}

Projeto gerado pela **Squad AI v2** seguindo:
Java {c.java_version} + Spring Boot 4 + Spring 7, Clean Architecture, CQRS + Outbox,
DDD forte (VOs validados, Aggregates com invariantes), Aurora PostgreSQL, Testcontainers.

## Bounded Contexts

{contexts_bullets}

## Estrutura

- `domain/` — Aggregates, Value Objects, Domain Events (zero dependências de framework)
- `application/` — Use Cases (Commands, Queries), Ports
- `infrastructure/` — Adapters (JPA, REST, Outbox), Flyway migrations
- `bootstrap/` — Spring Boot main + wiring

## Dev local

```bash
# 1) subir Postgres + app
docker compose up --build

# 2) health check
curl -s localhost:8080/actuator/health | jq

# 3) rodar testes
./mvnw -T 1C verify
```

## Variáveis de ambiente

Veja `.env.example`. Em produção, injete via AWS SSM / Secrets Manager.

## Comandos úteis

```bash
./mvnw -pl domain test             # só unitários de domínio
./mvnw -pl infrastructure verify   # integração com Testcontainers
./mvnw -pl infrastructure test -Dtest=CleanArchitectureTest
./mvnw -T 1C clean verify          # build completo
```

## Próximos passos

- Completar os aggregates de cada contexto seguindo DDD (VOs validados, invariantes)
- Adicionar commands/queries à aplicação via TDD
- Configurar OpenTelemetry exporter (OTLP_ENDPOINT)
- Escrever testes de integração para novos fluxos
"""


# -------------------- domain module --------------------

def tpl_domain_pom(c: GenCtx) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.1.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <modelVersion>4.1.0</modelVersion>
    <parent>
        <groupId>{c.group_id}</groupId>
        <artifactId>{c.name}</artifactId>
        <version>0.1.0-SNAPSHOT</version>
    </parent>
    <artifactId>{c.name}-domain</artifactId>

    <dependencies>
        <!-- ZERO dependências de framework em runtime -->
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.assertj</groupId>
            <artifactId>assertj-core</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
"""


def tpl_domain_exception(c: GenCtx) -> str:
    return f"""package {c.base_package}.domain.common;

/** Violação de invariante ou regra de domínio. */
public class DomainException extends RuntimeException {{
    public DomainException(String message) {{ super(message); }}
    public DomainException(String message, Throwable cause) {{ super(message, cause); }}
}}
"""


def tpl_domain_event(c: GenCtx) -> str:
    return f"""package {c.base_package}.domain.common;

import java.time.Instant;

/**
 * Fato de negócio ocorrido. Imutável. Emitido pelos aggregates em mudanças de estado relevantes.
 * Implementações devem ser records.
 */
public interface DomainEvent {{
    Instant ocorridoEm();
}}
"""


def tpl_money_vo(c: GenCtx) -> str:
    return f"""package {c.base_package}.domain.common.vo;

import {c.base_package}.domain.common.DomainException;

import java.math.BigDecimal;
import java.util.Currency;
import java.util.Objects;

/** Value Object: valor monetário com moeda. Validado no construtor. */
public record Money(BigDecimal amount, Currency currency) {{
    public Money {{
        Objects.requireNonNull(amount, "amount não pode ser nulo");
        Objects.requireNonNull(currency, "currency não pode ser nulo");
        if (amount.scale() > currency.getDefaultFractionDigits()) {{
            throw new DomainException("scale incompatível com moeda " + currency);
        }}
        if (amount.signum() < 0) {{
            throw new DomainException("amount não pode ser negativo");
        }}
    }}

    public Money add(Money other) {{
        Objects.requireNonNull(other, "other");
        if (!currency.equals(other.currency)) {{
            throw new DomainException("moedas incompatíveis: " + currency + " vs " + other.currency);
        }}
        return new Money(amount.add(other.amount), currency);
    }}

    public Money multiply(int factor) {{
        if (factor < 0) throw new DomainException("factor negativo");
        return new Money(amount.multiply(BigDecimal.valueOf(factor)), currency);
    }}

    public static Money zero(Currency currency) {{
        Objects.requireNonNull(currency, "currency");
        return new Money(BigDecimal.ZERO.setScale(currency.getDefaultFractionDigits()), currency);
    }}
}}
"""


def tpl_money_test(c: GenCtx) -> str:
    return f"""package {c.base_package}.domain.common.vo;

import {c.base_package}.domain.common.DomainException;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.Currency;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class MoneyTest {{

    private static final Currency BRL = Currency.getInstance("BRL");

    @Test
    void deveSomarValoresDaMesmaMoeda() {{
        var a = new Money(new BigDecimal("10.00"), BRL);
        var b = new Money(new BigDecimal("5.50"), BRL);
        assertThat(a.add(b)).isEqualTo(new Money(new BigDecimal("15.50"), BRL));
    }}

    @Test
    void deveRejeitarSomaComMoedasDiferentes() {{
        var brl = new Money(new BigDecimal("10.00"), BRL);
        var usd = new Money(new BigDecimal("10.00"), Currency.getInstance("USD"));
        assertThatThrownBy(() -> brl.add(usd))
            .isInstanceOf(DomainException.class)
            .hasMessageContaining("moedas incompatíveis");
    }}

    @Test
    void deveRejeitarAmountNegativo() {{
        assertThatThrownBy(() -> new Money(new BigDecimal("-1.00"), BRL))
            .isInstanceOf(DomainException.class);
    }}

    @Test
    void deveRejeitarScaleIncompativel() {{
        assertThatThrownBy(() -> new Money(new BigDecimal("1.000"), BRL))
            .isInstanceOf(DomainException.class);
    }}
}}
"""


def tpl_aggregate_id(c: GenCtx, ctx: str) -> str:
    P = pascal(ctx)
    return f"""package {c.base_package}.domain.{ctx}.vo;

import {c.base_package}.domain.common.DomainException;

import java.util.Objects;
import java.util.UUID;

/** Identidade do aggregate {P}. Value Object. */
public record {P}Id(UUID value) {{
    public {P}Id {{
        Objects.requireNonNull(value, "{camel(ctx)}Id não pode ser nulo");
    }}
    public static {P}Id novo() {{
        return new {P}Id(UUID.randomUUID());
    }}
    public static {P}Id of(String raw) {{
        try {{ return new {P}Id(UUID.fromString(raw)); }}
        catch (IllegalArgumentException e) {{
            throw new DomainException("{camel(ctx)}Id inválido: " + raw, e);
        }}
    }}
}}
"""


def tpl_aggregate_event(c: GenCtx, ctx: str) -> str:
    P = pascal(ctx)
    return f"""package {c.base_package}.domain.{ctx}.event;

import {c.base_package}.domain.common.DomainEvent;
import {c.base_package}.domain.{ctx}.vo.{P}Id;

import java.time.Instant;

/** Eventos de domínio do aggregate {P}. Conjunto fechado via sealed. */
public sealed interface {P}Event extends DomainEvent
    permits {P}Event.{P}Criado, {P}Event.{P}Atualizado {{

    {P}Id {camel(ctx)}Id();

    record {P}Criado({P}Id {camel(ctx)}Id, Instant ocorridoEm) implements {P}Event {{
        public {P}Criado({P}Id id) {{ this(id, Instant.now()); }}
    }}

    record {P}Atualizado({P}Id {camel(ctx)}Id, Instant ocorridoEm) implements {P}Event {{
        public {P}Atualizado({P}Id id) {{ this(id, Instant.now()); }}
    }}
}}
"""


def tpl_aggregate_root(c: GenCtx, ctx: str) -> str:
    P = pascal(ctx)
    camel_ctx = camel(ctx)
    return f"""package {c.base_package}.domain.{ctx}.model;

import {c.base_package}.domain.common.DomainException;
import {c.base_package}.domain.{ctx}.event.{P}Event;
import {c.base_package}.domain.{ctx}.vo.{P}Id;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Objects;

/**
 * Aggregate Root exemplo do contexto "{ctx}".
 *
 * Regras aplicadas:
 *  - Identidade via Value Object ({P}Id)
 *  - Sem setters públicos: mutações por métodos do domínio
 *  - Invariantes validadas antes de mudar estado
 *  - Eventos emitidos em cada mudança relevante e consumidos via pullEvents()
 *
 * Complete com os campos, invariantes e comportamentos reais do seu domínio.
 */
public final class {P} {{

    private final {P}Id id;
    private String nome;
    private final Instant criadoEm;
    private Instant atualizadoEm;
    private final List<{P}Event> eventosPendentes = new ArrayList<>();

    private {P}({P}Id id, String nome, Instant criadoEm) {{
        this.id = id;
        this.nome = nome;
        this.criadoEm = criadoEm;
        this.atualizadoEm = criadoEm;
    }}

    public static {P} criar(String nome) {{
        validarNome(nome);
        var agora = Instant.now();
        var agg = new {P}({P}Id.novo(), nome.trim(), agora);
        agg.eventosPendentes.add(new {P}Event.{P}Criado(agg.id));
        return agg;
    }}

    /** Reconstrução a partir da persistência — não emite evento. */
    public static {P} reconstruir({P}Id id, String nome, Instant criadoEm, Instant atualizadoEm) {{
        var agg = new {P}(id, nome, criadoEm);
        agg.atualizadoEm = atualizadoEm;
        return agg;
    }}

    public void renomear(String novoNome) {{
        validarNome(novoNome);
        if (novoNome.trim().equals(this.nome)) return;
        this.nome = novoNome.trim();
        this.atualizadoEm = Instant.now();
        eventosPendentes.add(new {P}Event.{P}Atualizado(id));
    }}

    private static void validarNome(String nome) {{
        Objects.requireNonNull(nome, "nome");
        if (nome.isBlank()) throw new DomainException("nome não pode ser vazio");
        if (nome.length() > 200) throw new DomainException("nome excede 200 caracteres");
    }}

    public {P}Id id() {{ return id; }}
    public String nome() {{ return nome; }}
    public Instant criadoEm() {{ return criadoEm; }}
    public Instant atualizadoEm() {{ return atualizadoEm; }}

    public List<{P}Event> pullEvents() {{
        var copy = List.copyOf(eventosPendentes);
        eventosPendentes.clear();
        return copy;
    }}

    public List<{P}Event> eventosPendentes() {{
        return Collections.unmodifiableList(eventosPendentes);
    }}
}}
"""


def tpl_aggregate_test(c: GenCtx, ctx: str) -> str:
    P = pascal(ctx)
    return f"""package {c.base_package}.domain.{ctx}.model;

import {c.base_package}.domain.common.DomainException;
import {c.base_package}.domain.{ctx}.event.{P}Event;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class {P}Test {{

    @Test
    void deveCriarAggregateComEventoEmitido() {{
        var agg = {P}.criar("exemplo");

        assertThat(agg.id()).isNotNull();
        assertThat(agg.nome()).isEqualTo("exemplo");
        assertThat(agg.pullEvents())
            .singleElement()
            .isInstanceOf({P}Event.{P}Criado.class);
    }}

    @Test
    void deveRejeitarNomeVazio() {{
        assertThatThrownBy(() -> {P}.criar("  "))
            .isInstanceOf(DomainException.class)
            .hasMessageContaining("vazio");
    }}

    @Test
    void deveEmitirEventoAoRenomear() {{
        var agg = {P}.criar("inicial");
        agg.pullEvents();  // descarta evento de criação

        agg.renomear("novo");

        assertThat(agg.nome()).isEqualTo("novo");
        assertThat(agg.pullEvents())
            .singleElement()
            .isInstanceOf({P}Event.{P}Atualizado.class);
    }}

    @Test
    void naoDeveEmitirEventoSeRenomearParaMesmoNome() {{
        var agg = {P}.criar("igual");
        agg.pullEvents();

        agg.renomear("igual");

        assertThat(agg.pullEvents()).isEmpty();
    }}
}}
"""


# -------------------- application module --------------------

def tpl_application_pom(c: GenCtx) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.1.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <modelVersion>4.1.0</modelVersion>
    <parent>
        <groupId>{c.group_id}</groupId>
        <artifactId>{c.name}</artifactId>
        <version>0.1.0-SNAPSHOT</version>
    </parent>
    <artifactId>{c.name}-application</artifactId>

    <dependencies>
        <dependency>
            <groupId>{c.group_id}</groupId>
            <artifactId>{c.name}-domain</artifactId>
            <version>0.1.0-SNAPSHOT</version>
        </dependency>

        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.assertj</groupId>
            <artifactId>assertj-core</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.mockito</groupId>
            <artifactId>mockito-junit-jupiter</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
"""


def tpl_repo_port(c: GenCtx, ctx: str) -> str:
    P = pascal(ctx)
    return f"""package {c.base_package}.application.{ctx}.port;

import {c.base_package}.domain.{ctx}.model.{P};
import {c.base_package}.domain.{ctx}.vo.{P}Id;

import java.util.Optional;

/** Port para persistência do aggregate {P}. Implementado em infrastructure/. */
public interface {P}RepositoryPort {{
    Optional<{P}> findById({P}Id id);
    void save({P} aggregate);
}}
"""


def tpl_outbox_port(c: GenCtx) -> str:
    return f"""package {c.base_package}.application.common.port;

import {c.base_package}.domain.common.DomainEvent;

import java.util.List;

/** Port do Outbox transacional. Implementado em infrastructure/. */
public interface OutboxPort {{
    void enqueue(List<? extends DomainEvent> events);
}}
"""


def tpl_create_command(c: GenCtx, ctx: str) -> str:
    P = pascal(ctx)
    return f"""package {c.base_package}.application.{ctx}.command;

import java.util.Objects;

/** Command para criar um novo {P}. */
public record Criar{P}Command(String nome) {{
    public Criar{P}Command {{
        Objects.requireNonNull(nome, "nome");
    }}
}}
"""


def tpl_create_handler(c: GenCtx, ctx: str) -> str:
    P = pascal(ctx)
    cam = camel(ctx)
    return f"""package {c.base_package}.application.{ctx}.command;

import {c.base_package}.application.common.port.OutboxPort;
import {c.base_package}.application.{ctx}.port.{P}RepositoryPort;
import {c.base_package}.domain.{ctx}.model.{P};
import {c.base_package}.domain.{ctx}.vo.{P}Id;

/**
 * Use Case: criar novo {P}.
 * POJO — sem Spring. O bean é registrado via @Configuration em infrastructure/.
 */
public class Criar{P}Handler {{

    private final {P}RepositoryPort repo;
    private final OutboxPort outbox;

    public Criar{P}Handler({P}RepositoryPort repo, OutboxPort outbox) {{
        this.repo = repo;
        this.outbox = outbox;
    }}

    public {P}Id handle(Criar{P}Command cmd) {{
        var {cam} = {P}.criar(cmd.nome());
        repo.save({cam});
        outbox.enqueue({cam}.pullEvents());
        return {cam}.id();
    }}
}}
"""


def tpl_create_handler_test(c: GenCtx, ctx: str) -> str:
    P = pascal(ctx)
    cam = camel(ctx)
    return f"""package {c.base_package}.application.{ctx}.command;

import {c.base_package}.application.common.port.OutboxPort;
import {c.base_package}.application.{ctx}.port.{P}RepositoryPort;
import {c.base_package}.domain.{ctx}.event.{P}Event;
import {c.base_package}.domain.{ctx}.model.{P};
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class Criar{P}HandlerTest {{

    @Mock {P}RepositoryPort repo;
    @Mock OutboxPort outbox;

    @Test
    void devePersistirAggregateEEnfileirarEventoCriado() {{
        var handler = new Criar{P}Handler(repo, outbox);

        var id = handler.handle(new Criar{P}Command("teste"));

        assertThat(id).isNotNull();
        var aggCaptor = ArgumentCaptor.forClass({P}.class);
        verify(repo).save(aggCaptor.capture());
        assertThat(aggCaptor.getValue().nome()).isEqualTo("teste");

        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<?>> eventsCaptor = ArgumentCaptor.forClass(List.class);
        verify(outbox).enqueue((List) eventsCaptor.capture());
        assertThat(eventsCaptor.getValue())
            .anyMatch(e -> e instanceof {P}Event.{P}Criado);
    }}
}}
"""


def tpl_query(c: GenCtx, ctx: str) -> str:
    P = pascal(ctx)
    return f"""package {c.base_package}.application.{ctx}.query;

import {c.base_package}.domain.{ctx}.vo.{P}Id;

import java.util.Objects;

public record Buscar{P}PorIdQuery({P}Id id) {{
    public Buscar{P}PorIdQuery {{
        Objects.requireNonNull(id, "id");
    }}
}}
"""


def tpl_query_view(c: GenCtx, ctx: str) -> str:
    P = pascal(ctx)
    return f"""package {c.base_package}.application.{ctx}.query;

import java.time.Instant;
import java.util.UUID;

/** View de leitura — DTO de Query, NÃO é o Aggregate. */
public record {P}View(UUID id, String nome, Instant criadoEm, Instant atualizadoEm) {{ }}
"""


def tpl_query_port(c: GenCtx, ctx: str) -> str:
    P = pascal(ctx)
    return f"""package {c.base_package}.application.{ctx}.port;

import {c.base_package}.application.{ctx}.query.{P}View;
import {c.base_package}.domain.{ctx}.vo.{P}Id;

import java.util.Optional;

public interface {P}QueryPort {{
    Optional<{P}View> buscarPorId({P}Id id);
}}
"""


def tpl_query_handler(c: GenCtx, ctx: str) -> str:
    P = pascal(ctx)
    return f"""package {c.base_package}.application.{ctx}.query;

import {c.base_package}.application.{ctx}.port.{P}QueryPort;

import java.util.Optional;

public class Buscar{P}PorIdHandler {{

    private final {P}QueryPort queries;

    public Buscar{P}PorIdHandler({P}QueryPort queries) {{
        this.queries = queries;
    }}

    public Optional<{P}View> handle(Buscar{P}PorIdQuery q) {{
        return queries.buscarPorId(q.id());
    }}
}}
"""


# -------------------- infrastructure module --------------------

def tpl_infra_pom(c: GenCtx) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.1.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <modelVersion>4.1.0</modelVersion>
    <parent>
        <groupId>{c.group_id}</groupId>
        <artifactId>{c.name}</artifactId>
        <version>0.1.0-SNAPSHOT</version>
    </parent>
    <artifactId>{c.name}-infrastructure</artifactId>

    <dependencies>
        <dependency>
            <groupId>{c.group_id}</groupId>
            <artifactId>{c.name}-application</artifactId>
            <version>0.1.0-SNAPSHOT</version>
        </dependency>

        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <scope>runtime</scope>
        </dependency>
        <dependency>
            <groupId>org.flywaydb</groupId>
            <artifactId>flyway-core</artifactId>
        </dependency>
        <dependency>
            <groupId>org.flywaydb</groupId>
            <artifactId>flyway-database-postgresql</artifactId>
        </dependency>
        <dependency>
            <groupId>com.fasterxml.jackson.core</groupId>
            <artifactId>jackson-databind</artifactId>
        </dependency>

        <!-- Tests -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-testcontainers</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.testcontainers</groupId>
            <artifactId>junit-jupiter</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.testcontainers</groupId>
            <artifactId>postgresql</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>com.tngtech.archunit</groupId>
            <artifactId>archunit-junit5</artifactId>
            <version>1.3.0</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
"""


def tpl_jpa_entity(c: GenCtx, ctx: str) -> str:
    P = pascal(ctx)
    table = snake(ctx)
    return f"""package {c.base_package}.infrastructure.persistence.{ctx};

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "{table}")
public class {P}JpaEntity {{

    @Id
    @Column(name = "id", nullable = false, updatable = false)
    private UUID id;

    @Column(name = "nome", nullable = false, length = 200)
    private String nome;

    @Column(name = "criado_em", nullable = false)
    private Instant criadoEm;

    @Column(name = "atualizado_em", nullable = false)
    private Instant atualizadoEm;

    protected {P}JpaEntity() {{}}

    public {P}JpaEntity(UUID id, String nome, Instant criadoEm, Instant atualizadoEm) {{
        this.id = id;
        this.nome = nome;
        this.criadoEm = criadoEm;
        this.atualizadoEm = atualizadoEm;
    }}

    public UUID getId() {{ return id; }}
    public String getNome() {{ return nome; }}
    public Instant getCriadoEm() {{ return criadoEm; }}
    public Instant getAtualizadoEm() {{ return atualizadoEm; }}

    // setters package-private para mapper
    void setNome(String nome) {{ this.nome = nome; }}
    void setAtualizadoEm(Instant t) {{ this.atualizadoEm = t; }}
}}
"""


def tpl_jpa_repo(c: GenCtx, ctx: str) -> str:
    P = pascal(ctx)
    return f"""package {c.base_package}.infrastructure.persistence.{ctx};

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface {P}JpaRepository extends JpaRepository<{P}JpaEntity, UUID> {{
}}
"""


def tpl_jpa_mapper(c: GenCtx, ctx: str) -> str:
    P = pascal(ctx)
    return f"""package {c.base_package}.infrastructure.persistence.{ctx};

import {c.base_package}.domain.{ctx}.model.{P};
import {c.base_package}.domain.{ctx}.vo.{P}Id;

import org.springframework.stereotype.Component;

@Component
class {P}Mapper {{

    {P}JpaEntity toEntity({P} agg) {{
        return new {P}JpaEntity(agg.id().value(), agg.nome(), agg.criadoEm(), agg.atualizadoEm());
    }}

    {P} toDomain({P}JpaEntity e) {{
        return {P}.reconstruir(new {P}Id(e.getId()), e.getNome(), e.getCriadoEm(), e.getAtualizadoEm());
    }}
}}
"""


def tpl_repo_adapter(c: GenCtx, ctx: str) -> str:
    P = pascal(ctx)
    return f"""package {c.base_package}.infrastructure.persistence.{ctx};

import {c.base_package}.application.{ctx}.port.{P}RepositoryPort;
import {c.base_package}.domain.{ctx}.model.{P};
import {c.base_package}.domain.{ctx}.vo.{P}Id;

import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
class {P}RepositoryAdapter implements {P}RepositoryPort {{

    private final {P}JpaRepository jpa;
    private final {P}Mapper mapper;

    {P}RepositoryAdapter({P}JpaRepository jpa, {P}Mapper mapper) {{
        this.jpa = jpa;
        this.mapper = mapper;
    }}

    @Override
    public Optional<{P}> findById({P}Id id) {{
        return jpa.findById(id.value()).map(mapper::toDomain);
    }}

    @Override
    public void save({P} aggregate) {{
        jpa.save(mapper.toEntity(aggregate));
    }}
}}
"""


def tpl_query_adapter(c: GenCtx, ctx: str) -> str:
    P = pascal(ctx)
    table = snake(ctx)
    return f"""package {c.base_package}.infrastructure.persistence.{ctx};

import {c.base_package}.application.{ctx}.port.{P}QueryPort;
import {c.base_package}.application.{ctx}.query.{P}View;
import {c.base_package}.domain.{ctx}.vo.{P}Id;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
class {P}QueryJdbcAdapter implements {P}QueryPort {{

    private final JdbcClient jdbc;

    {P}QueryJdbcAdapter(JdbcClient jdbc) {{ this.jdbc = jdbc; }}

    @Override
    public Optional<{P}View> buscarPorId({P}Id id) {{
        return jdbc.sql(\"\"\"
            SELECT id, nome, criado_em, atualizado_em
              FROM {table}
             WHERE id = :id
            \"\"\")
            .param("id", id.value())
            .query({P}View.class)
            .optional();
    }}
}}
"""


def tpl_outbox_entity(c: GenCtx) -> str:
    return f"""package {c.base_package}.infrastructure.outbox;

import {c.base_package}.domain.common.DomainEvent;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "outbox_events")
public class OutboxEventEntity {{

    @Id
    @Column(name = "id")
    private UUID id;

    @Column(name = "aggregate_type", nullable = false, length = 100)
    private String aggregateType;

    @Column(name = "aggregate_id", nullable = false, length = 100)
    private String aggregateId;

    @Column(name = "event_type", nullable = false, length = 200)
    private String eventType;

    @Column(name = "payload", nullable = false, columnDefinition = "jsonb")
    private String payload;

    @Column(name = "headers", nullable = false, columnDefinition = "jsonb")
    private String headers = "{{}}";

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "processed_at")
    private Instant processedAt;

    @Column(name = "attempts", nullable = false)
    private int attempts;

    protected OutboxEventEntity() {{}}

    public static OutboxEventEntity novo(DomainEvent e, ObjectMapper mapper, String correlationId) {{
        var out = new OutboxEventEntity();
        out.id = UUID.randomUUID();
        out.aggregateType = e.getClass().getEnclosingClass() != null
            ? e.getClass().getEnclosingClass().getSimpleName()
            : e.getClass().getSimpleName();
        out.aggregateId = extractAggregateId(e);
        out.eventType = e.getClass().getSimpleName();
        try {{ out.payload = mapper.writeValueAsString(e); }}
        catch (Exception ex) {{ throw new IllegalStateException("Falha ao serializar evento", ex); }}
        try {{ out.headers = mapper.writeValueAsString(java.util.Map.of("correlationId", correlationId)); }}
        catch (Exception ex) {{ /* ignore */ }}
        out.createdAt = Instant.now();
        out.attempts = 0;
        return out;
    }}

    private static String extractAggregateId(DomainEvent e) {{
        try {{
            var m = e.getClass().getMethods();
            for (var method : m) {{
                if (method.getName().endsWith("Id") && method.getParameterCount() == 0) {{
                    Object v = method.invoke(e);
                    return v == null ? "" : v.toString();
                }}
            }}
        }} catch (Exception ignored) {{}}
        return "";
    }}

    public void markProcessed(Instant when) {{ this.processedAt = when; }}
    public void markFailure() {{ this.attempts++; }}

    public UUID getId() {{ return id; }}
    public String getEventType() {{ return eventType; }}
    public Instant getProcessedAt() {{ return processedAt; }}
}}
"""


def tpl_outbox_repo(c: GenCtx) -> str:
    return f"""package {c.base_package}.infrastructure.outbox;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;
import java.util.UUID;

public interface OutboxEventJpaRepository extends JpaRepository<OutboxEventEntity, UUID> {{

    @Query(\"\"\"
        SELECT o FROM OutboxEventEntity o
         WHERE o.processedAt IS NULL
         ORDER BY o.createdAt
        \"\"\")
    List<OutboxEventEntity> findUnprocessed(org.springframework.data.domain.Pageable page);
}}
"""


def tpl_outbox_adapter(c: GenCtx) -> str:
    return f"""package {c.base_package}.infrastructure.outbox;

import {c.base_package}.application.common.port.OutboxPort;
import {c.base_package}.domain.common.DomainEvent;
import {c.base_package}.infrastructure.rest.CorrelationScope;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
class OutboxJpaAdapter implements OutboxPort {{

    private final OutboxEventJpaRepository repo;
    private final ObjectMapper mapper;

    OutboxJpaAdapter(OutboxEventJpaRepository repo, ObjectMapper mapper) {{
        this.repo = repo;
        this.mapper = mapper;
    }}

    @Override
    public void enqueue(List<? extends DomainEvent> events) {{
        if (events.isEmpty()) return;
        var cid = CorrelationScope.current();
        var entities = events.stream()
            .map(e -> OutboxEventEntity.novo(e, mapper, cid))
            .toList();
        repo.saveAll(entities);
    }}
}}
"""


def tpl_outbox_relay(c: GenCtx) -> str:
    return f"""package {c.base_package}.infrastructure.outbox;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.PageRequest;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;

@Component
class OutboxPollerRelay {{

    private static final Logger log = LoggerFactory.getLogger(OutboxPollerRelay.class);
    private static final int BATCH_SIZE = 100;

    private final OutboxEventJpaRepository repo;

    OutboxPollerRelay(OutboxEventJpaRepository repo) {{ this.repo = repo; }}

    @Scheduled(fixedDelayString = "${{outbox.poll.delay-ms:500}}")
    @Transactional
    public void poll() {{
        var batch = repo.findUnprocessed(PageRequest.of(0, BATCH_SIZE));
        if (batch.isEmpty()) return;
        log.debug("Outbox: processando {{}} eventos", batch.size());
        for (var evt : batch) {{
            try {{
                // TODO: publicar em SQS / Kafka / listener in-process
                log.info("Outbox publishing: type={{}} id={{}}", evt.getEventType(), evt.getId());
                evt.markProcessed(Instant.now());
            }} catch (RuntimeException ex) {{
                log.warn("Falha publicando evento {{}}: {{}}", evt.getId(), ex.getMessage());
                evt.markFailure();
            }}
        }}
    }}
}}
"""


def tpl_correlation_scope(c: GenCtx) -> str:
    return f"""package {c.base_package}.infrastructure.rest;

/**
 * Correlation-id por request usando ScopedValue (Java 25).
 * Substitui ThreadLocal com segurança para Virtual Threads.
 */
public final class CorrelationScope {{

    public static final ScopedValue<String> CORRELATION_ID = ScopedValue.newInstance();

    private CorrelationScope() {{}}

    public static String current() {{
        return CORRELATION_ID.orElse("unknown");
    }}
}}
"""


def tpl_correlation_filter(c: GenCtx) -> str:
    return f"""package {c.base_package}.infrastructure.rest;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.MDC;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.Optional;
import java.util.UUID;

@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
class CorrelationFilter extends OncePerRequestFilter {{

    private static final String HEADER = "X-Correlation-Id";
    private static final String MDC_KEY = "correlationId";

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
            throws ServletException, IOException {{
        var cid = Optional.ofNullable(req.getHeader(HEADER))
            .filter(s -> !s.isBlank())
            .orElseGet(() -> UUID.randomUUID().toString());
        res.setHeader(HEADER, cid);
        MDC.put(MDC_KEY, cid);
        try {{
            ScopedValue.where(CorrelationScope.CORRELATION_ID, cid)
                .run(() -> runChecked(chain, req, res));
        }} catch (WrappedServletException e) {{
            throw e.servlet;
        }} catch (WrappedIOException e) {{
            throw e.io;
        }} finally {{
            MDC.remove(MDC_KEY);
        }}
    }}

    private void runChecked(FilterChain chain, HttpServletRequest req, HttpServletResponse res) {{
        try {{ chain.doFilter(req, res); }}
        catch (ServletException e) {{ throw new WrappedServletException(e); }}
        catch (IOException e) {{ throw new WrappedIOException(e); }}
    }}

    private static class WrappedServletException extends RuntimeException {{
        final ServletException servlet;
        WrappedServletException(ServletException e) {{ super(e); this.servlet = e; }}
    }}

    private static class WrappedIOException extends RuntimeException {{
        final IOException io;
        WrappedIOException(IOException e) {{ super(e); this.io = e; }}
    }}
}}
"""


def tpl_exception_handler(c: GenCtx) -> str:
    return f"""package {c.base_package}.infrastructure.rest;

import {c.base_package}.domain.common.DomainException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.net.URI;

/** Errors padronizados em ProblemDetail (RFC 9457). */
@RestControllerAdvice
class GlobalExceptionHandler {{

    @ExceptionHandler(DomainException.class)
    ProblemDetail onDomain(DomainException ex) {{
        var p = ProblemDetail.forStatusAndDetail(HttpStatus.UNPROCESSABLE_ENTITY, ex.getMessage());
        p.setType(URI.create("about:blank#domain-violation"));
        p.setTitle("Violação de regra de domínio");
        p.setProperty("correlationId", CorrelationScope.current());
        return p;
    }}

    @ExceptionHandler(MethodArgumentNotValidException.class)
    ProblemDetail onValidation(MethodArgumentNotValidException ex) {{
        var p = ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, "Dados inválidos");
        p.setType(URI.create("about:blank#validation"));
        p.setTitle("Validação");
        p.setProperty("errors", ex.getBindingResult().getFieldErrors().stream()
            .map(f -> java.util.Map.of("field", f.getField(), "message", String.valueOf(f.getDefaultMessage())))
            .toList());
        p.setProperty("correlationId", CorrelationScope.current());
        return p;
    }}

    @ExceptionHandler(Exception.class)
    ProblemDetail onUnexpected(Exception ex) {{
        var p = ProblemDetail.forStatusAndDetail(HttpStatus.INTERNAL_SERVER_ERROR, "Erro inesperado");
        p.setType(URI.create("about:blank#internal"));
        p.setTitle("Erro interno");
        p.setProperty("correlationId", CorrelationScope.current());
        return p;
    }}
}}
"""


def tpl_controller(c: GenCtx, ctx: str) -> str:
    P = pascal(ctx)
    return f"""package {c.base_package}.infrastructure.rest.{ctx};

import {c.base_package}.application.{ctx}.command.Criar{P}Command;
import {c.base_package}.application.{ctx}.command.Criar{P}Handler;
import {c.base_package}.application.{ctx}.query.Buscar{P}PorIdHandler;
import {c.base_package}.application.{ctx}.query.Buscar{P}PorIdQuery;
import {c.base_package}.application.{ctx}.query.{P}View;
import {c.base_package}.domain.{ctx}.vo.{P}Id;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.net.URI;

@RestController
@RequestMapping("/{ctx}")
class {P}Controller {{

    private final Criar{P}Handler criar;
    private final Buscar{P}PorIdHandler buscar;

    {P}Controller(Criar{P}Handler criar, Buscar{P}PorIdHandler buscar) {{
        this.criar = criar;
        this.buscar = buscar;
    }}

    public record Criar{P}Request(@NotBlank @Size(max = 200) String nome) {{}}

    @PostMapping
    ResponseEntity<Void> criar(@Valid @RequestBody Criar{P}Request body) {{
        var id = criar.handle(new Criar{P}Command(body.nome()));
        return ResponseEntity.created(URI.create("/{ctx}/" + id.value())).build();
    }}

    @GetMapping("/{{id}}")
    ResponseEntity<{P}View> buscar(@PathVariable String id) {{
        return buscar.handle(new Buscar{P}PorIdQuery({P}Id.of(id)))
            .map(ResponseEntity::ok)
            .orElseGet(() -> ResponseEntity.notFound().build());
    }}
}}
"""


def tpl_app_wiring(c: GenCtx) -> str:
    ctx_lines = []
    for ctx in c.contexts:
        P = pascal(ctx)
        ctx_lines.append(f"""
    @Bean
    {c.base_package}.application.{ctx}.command.Criar{P}Handler criar{P}Handler(
            {c.base_package}.application.{ctx}.port.{P}RepositoryPort repo,
            {c.base_package}.application.common.port.OutboxPort outbox) {{
        return new {c.base_package}.application.{ctx}.command.Criar{P}Handler(repo, outbox);
    }}

    @Bean
    {c.base_package}.application.{ctx}.query.Buscar{P}PorIdHandler buscar{P}PorIdHandler(
            {c.base_package}.application.{ctx}.port.{P}QueryPort queries) {{
        return new {c.base_package}.application.{ctx}.query.Buscar{P}PorIdHandler(queries);
    }}
""")
    handlers = "\n".join(ctx_lines)
    return f"""package {c.base_package}.infrastructure.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class ApplicationWiring {{
{handlers}
}}
"""


def tpl_flyway_v1(c: GenCtx) -> str:
    tables = []
    for ctx in c.contexts:
        table = snake(ctx)
        tables.append(f"""
CREATE TABLE IF NOT EXISTS {table} (
    id UUID PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL,
    atualizado_em TIMESTAMPTZ NOT NULL
);""")
    return "-- V1: esquema inicial gerado automaticamente pelo generator\n" + "\n".join(tables) + "\n"


def tpl_flyway_v2() -> str:
    return """-- V2: Outbox transacional
CREATE TABLE IF NOT EXISTS outbox_events (
    id UUID PRIMARY KEY,
    aggregate_type VARCHAR(100) NOT NULL,
    aggregate_id VARCHAR(100) NOT NULL,
    event_type VARCHAR(200) NOT NULL,
    payload JSONB NOT NULL,
    headers JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    attempts INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_outbox_unprocessed
    ON outbox_events (created_at)
    WHERE processed_at IS NULL;
"""


def tpl_archunit_test(c: GenCtx) -> str:
    base = c.base_package
    return f"""package {base}.infrastructure.arch;

import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

import static com.tngtech.archunit.library.Architectures.layeredArchitecture;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

@AnalyzeClasses(packages = "{base}", importOptions = ImportOption.DoNotIncludeTests.class)
class CleanArchitectureTest {{

    @ArchTest
    static final ArchRule dominioSemFramework = noClasses()
        .that().resideInAPackage("..domain..")
        .should().dependOnClassesThat().resideInAnyPackage(
            "jakarta..", "org.springframework..", "org.hibernate..",
            "com.fasterxml.jackson..", "software.amazon.."
        );

    @ArchTest
    static final ArchRule camadas = layeredArchitecture().consideringAllDependencies()
        .layer("Domain").definedBy("..domain..")
        .layer("Application").definedBy("..application..")
        .layer("Infrastructure").definedBy("..infrastructure..")
        .layer("Bootstrap").definedBy("..{base.split('.')[-1]}")  // pacote raiz do bootstrap
        .whereLayer("Domain").mayOnlyBeAccessedByLayers("Application", "Infrastructure", "Bootstrap")
        .whereLayer("Application").mayOnlyBeAccessedByLayers("Infrastructure", "Bootstrap")
        .whereLayer("Infrastructure").mayOnlyBeAccessedByLayers("Bootstrap");

    @ArchTest
    static final ArchRule semThreadLocal = noClasses()
        .should().dependOnClassesThat()
        .haveFullyQualifiedName("java.lang.ThreadLocal");
}}
"""


def tpl_integration_test(c: GenCtx, ctx: str) -> str:
    P = pascal(ctx)
    cam = camel(ctx)
    return f"""package {c.base_package}.infrastructure.persistence.{ctx};

import {c.base_package}.application.{ctx}.command.Criar{P}Command;
import {c.base_package}.application.{ctx}.command.Criar{P}Handler;
import {c.base_package}.infrastructure.outbox.OutboxEventJpaRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@Testcontainers
class {P}IntegrationTest {{

    @Container @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("{c.db_image}");

    @Autowired Criar{P}Handler criar;
    @Autowired {P}JpaRepository jpaRepo;
    @Autowired OutboxEventJpaRepository outboxRepo;

    @Test
    void deveCriarAggregateEPersistirEventoNoOutboxMesmaTransacao() {{
        var id = criar.handle(new Criar{P}Command("teste-{cam}"));

        assertThat(jpaRepo.findById(id.value())).isPresent();
        assertThat(outboxRepo.findAll())
            .extracting(e -> e.getEventType())
            .contains("{P}Criado");
    }}
}}
"""


# -------------------- bootstrap module --------------------

def tpl_bootstrap_pom(c: GenCtx) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.1.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <modelVersion>4.1.0</modelVersion>
    <parent>
        <groupId>{c.group_id}</groupId>
        <artifactId>{c.name}</artifactId>
        <version>0.1.0-SNAPSHOT</version>
    </parent>
    <artifactId>{c.name}-bootstrap</artifactId>

    <dependencies>
        <dependency>
            <groupId>{c.group_id}</groupId>
            <artifactId>{c.name}-infrastructure</artifactId>
            <version>0.1.0-SNAPSHOT</version>
        </dependency>
        <dependency>
            <groupId>net.logstash.logback</groupId>
            <artifactId>logstash-logback-encoder</artifactId>
            <version>8.0</version>
        </dependency>

        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <finalName>bootstrap</finalName>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
"""


def tpl_application_java(c: GenCtx) -> str:
    return f"""package {c.base_package};

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.domain.EntityScan;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableJpaRepositories(basePackages = "{c.base_package}.infrastructure")
@EntityScan(basePackages = "{c.base_package}.infrastructure")
@EnableScheduling
public class Application {{
    public static void main(String[] args) {{
        SpringApplication.run(Application.class, args);
    }}
}}
"""


def tpl_application_yml(c: GenCtx) -> str:
    return f"""spring:
  application:
    name: {c.name}
  threads:
    virtual:
      enabled: true
  datasource:
    url: jdbc:postgresql://${{DB_HOST:localhost}}:${{DB_PORT:5432}}/${{DB_NAME:app}}
    username: ${{DB_USER:app}}
    password: ${{DB_PASSWORD:app}}
    hikari:
      maximum-pool-size: ${{DB_POOL_MAX:20}}
      minimum-idle: ${{DB_POOL_MIN:5}}
      connection-timeout: 5000
      max-lifetime: 1800000
  jpa:
    hibernate:
      ddl-auto: validate
    properties:
      hibernate.jdbc.batch_size: 50
      hibernate.order_inserts: true
      hibernate.order_updates: true
  flyway:
    enabled: true
    baseline-on-migrate: false
  lifecycle:
    timeout-per-shutdown-phase: 30s

server:
  shutdown: graceful

management:
  endpoints:
    web:
      exposure:
        include: health,info,prometheus,metrics,flyway
  endpoint:
    health:
      probes:
        enabled: true
      group:
        liveness:
          include: livenessState
        readiness:
          include: readinessState,db

outbox:
  poll:
    delay-ms: 500
"""


def tpl_application_dev_yml() -> str:
    return """spring:
  config:
    activate:
      on-profile: dev
logging:
  level:
    root: INFO
    org.hibernate.SQL: DEBUG
"""


def tpl_application_prod_yml() -> str:
    return """spring:
  config:
    activate:
      on-profile: prod
logging:
  level:
    root: INFO
management:
  tracing:
    sampling:
      probability: 0.1
"""


def tpl_logback() -> str:
    return """<configuration>
    <appender name="JSON" class="ch.qos.logback.core.ConsoleAppender">
        <encoder class="net.logstash.logback.encoder.LogstashEncoder">
            <includeMdcKeyName>correlationId</includeMdcKeyName>
            <includeMdcKeyName>traceId</includeMdcKeyName>
            <includeMdcKeyName>spanId</includeMdcKeyName>
        </encoder>
    </appender>
    <root level="INFO">
        <appender-ref ref="JSON"/>
    </root>
</configuration>
"""


def tpl_application_test(c: GenCtx) -> str:
    return f"""package {c.base_package};

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@SpringBootTest
@Testcontainers
class ApplicationTest {{

    @Container @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("{c.db_image}");

    @Test void contextoSobe() {{
        // smoke test — garante que o contexto Spring sobe com todos os beans wireados
    }}
}}
"""


# =========================================================================
# Orquestração da geração
# =========================================================================

def generate(c: GenCtx) -> None:
    root = c.output / c.name
    if root.exists():
        print(f"! Destino já existe: {root}. Abortando.")
        sys.exit(2)

    print(f"\nGerando projeto em {root}")
    print(f"  base package: {c.base_package}")
    print(f"  contexts:     {', '.join(c.contexts)}")
    print()

    # raíz
    write(root / "pom.xml", tpl_root_pom(c))
    write(root / ".mvn" / "maven.config", tpl_mvn_config())
    write(root / ".gitignore", tpl_gitignore())
    write(root / ".env.example", tpl_env_example())
    write(root / "Dockerfile", tpl_dockerfile(c))
    write(root / "docker-compose.yml", tpl_compose(c))
    write(root / ".github" / "workflows" / "ci.yml", tpl_ci_yml(c))
    write(root / "README.md", tpl_readme(c))

    # domain
    domain_main = root / "domain" / "src" / "main" / "java" / c.pkg_path / "domain"
    domain_test = root / "domain" / "src" / "test" / "java" / c.pkg_path / "domain"
    write(root / "domain" / "pom.xml", tpl_domain_pom(c))
    write(domain_main / "common" / "DomainException.java", tpl_domain_exception(c))
    write(domain_main / "common" / "DomainEvent.java", tpl_domain_event(c))
    write(domain_main / "common" / "vo" / "Money.java", tpl_money_vo(c))
    write(domain_test / "common" / "vo" / "MoneyTest.java", tpl_money_test(c))

    for ctx in c.contexts:
        P = pascal(ctx)
        write(domain_main / ctx / "vo" / f"{P}Id.java", tpl_aggregate_id(c, ctx))
        write(domain_main / ctx / "event" / f"{P}Event.java", tpl_aggregate_event(c, ctx))
        if c.with_example_aggregate:
            write(domain_main / ctx / "model" / f"{P}.java", tpl_aggregate_root(c, ctx))
            write(domain_test / ctx / "model" / f"{P}Test.java", tpl_aggregate_test(c, ctx))

    # application
    app_main = root / "application" / "src" / "main" / "java" / c.pkg_path / "application"
    app_test = root / "application" / "src" / "test" / "java" / c.pkg_path / "application"
    write(root / "application" / "pom.xml", tpl_application_pom(c))
    write(app_main / "common" / "port" / "OutboxPort.java", tpl_outbox_port(c))

    for ctx in c.contexts:
        P = pascal(ctx)
        write(app_main / ctx / "port" / f"{P}RepositoryPort.java", tpl_repo_port(c, ctx))
        write(app_main / ctx / "port" / f"{P}QueryPort.java", tpl_query_port(c, ctx))
        write(app_main / ctx / "command" / f"Criar{P}Command.java", tpl_create_command(c, ctx))
        write(app_main / ctx / "command" / f"Criar{P}Handler.java", tpl_create_handler(c, ctx))
        write(app_main / ctx / "query" / f"Buscar{P}PorIdQuery.java", tpl_query(c, ctx))
        write(app_main / ctx / "query" / f"{P}View.java", tpl_query_view(c, ctx))
        write(app_main / ctx / "query" / f"Buscar{P}PorIdHandler.java", tpl_query_handler(c, ctx))
        write(app_test / ctx / "command" / f"Criar{P}HandlerTest.java", tpl_create_handler_test(c, ctx))

    # infrastructure
    infra_main = root / "infrastructure" / "src" / "main" / "java" / c.pkg_path / "infrastructure"
    infra_test = root / "infrastructure" / "src" / "test" / "java" / c.pkg_path / "infrastructure"
    infra_res = root / "infrastructure" / "src" / "main" / "resources" / "db" / "migration"
    write(root / "infrastructure" / "pom.xml", tpl_infra_pom(c))
    write(infra_main / "rest" / "CorrelationScope.java", tpl_correlation_scope(c))
    write(infra_main / "rest" / "CorrelationFilter.java", tpl_correlation_filter(c))
    write(infra_main / "rest" / "GlobalExceptionHandler.java", tpl_exception_handler(c))
    write(infra_main / "outbox" / "OutboxEventEntity.java", tpl_outbox_entity(c))
    write(infra_main / "outbox" / "OutboxEventJpaRepository.java", tpl_outbox_repo(c))
    write(infra_main / "outbox" / "OutboxJpaAdapter.java", tpl_outbox_adapter(c))
    write(infra_main / "outbox" / "OutboxPollerRelay.java", tpl_outbox_relay(c))
    write(infra_main / "config" / "ApplicationWiring.java", tpl_app_wiring(c))
    write(infra_res / "V1__init_schema.sql", tpl_flyway_v1(c))
    write(infra_res / "V2__outbox.sql", tpl_flyway_v2())
    write(infra_test / "arch" / "CleanArchitectureTest.java", tpl_archunit_test(c))

    for ctx in c.contexts:
        P = pascal(ctx)
        write(infra_main / "persistence" / ctx / f"{P}JpaEntity.java", tpl_jpa_entity(c, ctx))
        write(infra_main / "persistence" / ctx / f"{P}JpaRepository.java", tpl_jpa_repo(c, ctx))
        write(infra_main / "persistence" / ctx / f"{P}Mapper.java", tpl_jpa_mapper(c, ctx))
        write(infra_main / "persistence" / ctx / f"{P}RepositoryAdapter.java", tpl_repo_adapter(c, ctx))
        write(infra_main / "persistence" / ctx / f"{P}QueryJdbcAdapter.java", tpl_query_adapter(c, ctx))
        write(infra_main / "rest" / ctx / f"{P}Controller.java", tpl_controller(c, ctx))
        write(infra_test / "persistence" / ctx / f"{P}IntegrationTest.java", tpl_integration_test(c, ctx))

    # bootstrap
    boot_main = root / "bootstrap" / "src" / "main" / "java" / c.pkg_path
    boot_test = root / "bootstrap" / "src" / "test" / "java" / c.pkg_path
    boot_res = root / "bootstrap" / "src" / "main" / "resources"
    write(root / "bootstrap" / "pom.xml", tpl_bootstrap_pom(c))
    write(boot_main / "Application.java", tpl_application_java(c))
    write(boot_res / "application.yml", tpl_application_yml(c))
    write(boot_res / "application-dev.yml", tpl_application_dev_yml())
    write(boot_res / "application-prod.yml", tpl_application_prod_yml())
    write(boot_res / "logback-spring.xml", tpl_logback())
    write(boot_test / "ApplicationTest.java", tpl_application_test(c))

    print(f"\n✅ Projeto {c.name} gerado em {root}")
    print("\nPróximos passos:")
    print(f"  cd {root}")
    print("  docker compose up --build")
    print("  ./mvnw -T 1C verify   # (depois de adicionar wrapper, ou mvn se instalado)")


# =========================================================================
# CLI
# =========================================================================

def parse_args(argv=None) -> GenCtx:
    p = argparse.ArgumentParser(description="Squad AI — Java 25 + Spring Boot 4 project generator")
    p.add_argument("--name", required=True)
    p.add_argument("--group-id", required=True)
    p.add_argument("--base-package", required=True)
    p.add_argument("--contexts", required=True, help="vírgula-separados; ex: 'pedidos,pagamentos'")
    p.add_argument("--java-version", default="25")
    p.add_argument("--output", default=".")
    p.add_argument("--db-image", default="postgres:16-alpine")
    p.add_argument("--no-example-aggregate", action="store_true",
                   help="não gera aggregate root exemplo por contexto")
    a = p.parse_args(argv)

    return GenCtx(
        name=a.name,
        group_id=a.group_id,
        base_package=a.base_package,
        contexts=[c.strip() for c in a.contexts.split(",") if c.strip()],
        java_version=a.java_version,
        output=Path(a.output).resolve(),
        db_image=a.db_image,
        with_example_aggregate=not a.no_example_aggregate,
    )


if __name__ == "__main__":
    ctx = parse_args()
    generate(ctx)
