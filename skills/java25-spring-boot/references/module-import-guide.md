# Module Import (JEP 511 / 491) — Guia Prático

> **Status no Java 25:** Preview (2ª rodada). Finalização prevista para Java 26.
> **Flag de compilação:** `--enable-preview --release 25`.

## O que é

Module Import é um **atalho de import**: em vez de enumerar várias classes de um mesmo módulo, você importa **tudo o que o módulo exporta** com uma única linha.

```java
// ── sintaxe tradicional (muitos imports) ──────────────
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.Collections;
import java.util.stream.Collectors;
import java.util.stream.Stream;

// ── com JEP 491 (uma linha) ───────────────────────────
import module java.base;
```

`import module java.base;` traz **todos** os pacotes exportados por `java.base` (inclui `java.util`, `java.util.stream`, `java.lang`, `java.time`, `java.nio.file`, etc.).

## Quando usar (e quando NÃO usar)

### ✅ Use em

- **Scripts e ferramentas internas** (tarefas de build, geradores, análise ad-hoc) onde legibilidade do topo do arquivo não é prioridade e você só quer escrever código.
- **Exemplos didáticos e documentação viva** — tutoriais, labs, code snippets em readme onde imports distraem do ponto.
- **Prototipagem rápida** em experimentos antes de estabilizar API.
- **Scaffolds e templates iniciais** — a Squad AI usa em gerações iniciais; depois o `goal:refactor` pode reexpandir.

### ❌ Evite em

- **Código de produção da Clean Architecture** (domain, application, infrastructure) — a Squad AI mantém imports explícitos em production code. Motivos:
  - ArchUnit rules dependem de imports explícitos para detectar violações de camada.
  - Code review mais claro: quem vê `import java.sql.Connection` sabe que o arquivo toca SQL; com `import module java.sql` a pista some.
  - Tooling de dependency analysis (jdeps, SBOM) ainda assume imports explícitos.
- **Bibliotecas publicadas** — consumidores podem estar em JDKs mais antigos; module import exige Java 22+.

## Exemplo: Script CLI Interno

```java
// File: tools/check-outbox-lag.java
// Comando: java --enable-preview --release 25 tools/check-outbox-lag.java

import module java.base;
import module java.net.http;
import module java.sql;

public class OutboxLagCheck {
    public static void main(String[] args) throws Exception {
        var url = args.length > 0 ? args[0] : "jdbc:postgresql://localhost:5432/app";
        var threshold = Duration.ofMinutes(5);

        try (var conn = DriverManager.getConnection(url, "app", System.getenv("DB_PASS"));
             var stmt = conn.prepareStatement("""
                 SELECT COUNT(*) AS lag_count
                 FROM outbox_event
                 WHERE published_at IS NULL
                   AND created_at < NOW() - INTERVAL '5 minutes'
                 """)) {

            var rs = stmt.executeQuery();
            if (rs.next()) {
                var count = rs.getInt("lag_count");
                System.out.println("Events em lag > 5min: " + count);
                System.exit(count > 0 ? 1 : 0);
            }
        }
    }
}
```

Um único arquivo, três module imports, roda direto com `java` launcher (JEP 458 Multi-File Source-Code Programs). **Não há projeto Maven, não há classpath** — ótimo para runbook de operação.

## Módulos mais úteis para importar

| Módulo | Conteúdo típico |
|--------|-----------------|
| `java.base` | `java.util.*`, `java.lang.*`, `java.time.*`, `java.io.*`, `java.nio.*`, `java.util.stream.*`, `java.util.concurrent.*` |
| `java.sql` | JDBC (`Connection`, `DriverManager`, `PreparedStatement`, `ResultSet`) |
| `java.net.http` | `HttpClient`, `HttpRequest`, `HttpResponse` |
| `java.xml` | DOM, SAX, StAX |
| `java.logging` | `java.util.logging.*` |
| `java.management` | JMX |
| `jdk.httpserver` | `com.sun.net.httpserver.*` (servidor HTTP embutido) |

## Compatibilidade e Migração

1. **Compilação:** necessário `--enable-preview --release 25` no `javac` e na JVM. No Maven:
   ```xml
   <plugin>
     <artifactId>maven-compiler-plugin</artifactId>
     <configuration>
       <release>25</release>
       <compilerArgs>
         <arg>--enable-preview</arg>
       </compilerArgs>
     </configuration>
   </plugin>
   ```
2. **IDE:** IntelliJ IDEA 2025.1+ e VS Code (Extension Pack for Java 1.30+) já suportam. Mantenha `Project Settings → Language Level = "25 (Preview)"`.
3. **Conflitos de nome:** se dois módulos exportam mesma classe (raro), você recebe erro `ambiguous`. Resolva com import específico **após** o module import:
   ```java
   import module java.base;      // traz java.util.Date
   import java.sql.Date;         // específico vence (ou use FQN)
   ```
4. **Linters/Formatters:** Checkstyle 11+, Spotless 3+ e google-java-format 1.24+ entendem `import module`. Verifique versão antes de ativar em projeto existente.

## Recomendação da Squad AI

- **Production code:** imports explícitos (status quo). Não adote em `domain/`, `application/`, `infrastructure/`.
- **Scripts e tooling:** `import module java.base;` liberado.
- **Documentação viva e snippets de `references/`:** use quando a densidade de imports distrai do exemplo.
- **Scaffold gerado:** o `generate_project.py` **não** usa module import por padrão — mantém compilabilidade em Java 22/23 caso o time rode downlevel temporariamente.

## Checklist

```
□ --enable-preview no compilador e na JVM (até finalização)
□ IDE com Language Level 25 (Preview)
□ Checkstyle/Spotless atualizados
□ Módulo importado é estável (java.base, java.sql, java.net.http)
□ Não há conflito de nome entre módulos importados
□ Não usado em production code da Clean Architecture
□ ArchUnit continua verde (imports explícitos nas camadas)
```

## Referências cruzadas

- `squad-ai/references/ddd-guide.md` §6.1 — Recursos Java 25 em DDD
- `java25-spring-boot/references/migration-guide.md` — Migração SB3→SB4
- [[Java 25 Features]] no vault Obsidian
