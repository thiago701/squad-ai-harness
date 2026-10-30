# Apache Maven 4 — Guia Completo

> **Status Canônico:** Apache Maven 4 (model 4.1.0) é o padrão **único** da squad.
> Referência: GLOSSARIO §9.

**Última atualização:** 2026-04-10

---

## 1. Visão Geral — Por Que Maven 4?

Maven 4 trouxe melhorias fundamentais após 15 anos em Maven 3:

- **Build Cache Extension:** cache inteligente de artifacts compilados (local + remoto S3)
- **Model 4.1.0:** sintaxe melhorada, parent inferência, root POM nativo
- **mvnd — Maven Daemon:** eliminação de cold start (desnecessário recompilação de boot)
- **Consumer POM (flattened):** POM publicado sem `${revision}` ou referências locais
- **Paralelismo nativo:** `-T 1C`, `-T 2C` para paralelismo inteligente por core

**Benchmarks esperados** (vs Maven 3.9.x):

| Operação | Maven 3 | Maven 4 + mvnd + cache | Ganho |
|---|---|---|---|
| `clean install` (cold) | 45s | 28s | 38% |
| `install` (incremental) | 12s | 1.5s | 87% |
| `test` (classe modificada) | 8s | 0.8s | 90% |
| Startup mvnd (cold) | N/A | 2s | — |

---

## 2. Diferenças: Model 4.0.0 vs Model 4.1.0

### Model 4.0.0 (Maven 4.0.0 — 2024-04)

```xml
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
                             http://maven.apache.org/xsd/maven-4.0.0.xsd">

    <modelVersion>4.0.0</modelVersion>
    <groupId>com.squad</groupId>
    <artifactId>app</artifactId>
    <version>1.0.0</version>
</project>
```

### Model 4.1.0 (Maven 4.1.0+ — 2024-10)

Novidades:

1. **`root="true"` atributo:** marca POM pai sem necessidade de `<parent>` recursivo
2. **Parent inferência:** filho encontra pai automaticamente (mesmo diretório ou ancestral)
3. **Sintaxe de versão:** suporte melhorado a `${revision}`, `${changelist}`, `${sha1}`

```xml
<project xmlns="http://maven.apache.org/POM/4.1.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.1.0
                             http://maven.apache.org/xsd/maven-4.1.0.xsd"
         root="true">

    <modelVersion>4.1.0</modelVersion>
    <groupId>com.squad</groupId>
    <artifactId>parent</artifactId>
    <version>${revision}</version>
    <packaging>pom</packaging>

    <properties>
        <revision>1.0.0-SNAPSHOT</revision>
    </properties>
</project>
```

---

## 3. POM Modelo Completo (Spring Boot 4 + Java 25)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.1.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.1.0
                             http://maven.apache.org/xsd/maven-4.1.0.xsd"
         root="true">

    <modelVersion>4.1.0</modelVersion>

    <!-- Coordenadas -->
    <groupId>com.squad.pedidos</groupId>
    <artifactId>pedidos-service</artifactId>
    <version>${revision}</version>
    <packaging>jar</packaging>
    <name>Pedidos Service</name>
    <description>Microserviço de Pedidos — Java 25 + Spring Boot 4</description>

    <!-- Versionamento CI-friendly -->
    <properties>
        <revision>1.0.0-SNAPSHOT</revision>
        <changelist></changelist>
        <sha1></sha1>

        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
        <java.version>25</java.version>
        <maven.compiler.release>25</maven.compiler.release>
        <maven.compiler.source>25</maven.compiler.source>
        <maven.compiler.target>25</maven.compiler.target>

        <!-- POM publicado sem ${revision} (flattened) -->
        <maven.consumer.pom.flatten>true</maven.consumer.pom.flatten>

        <!-- Dependências core -->
        <spring-boot.version>4.0.0</spring-boot.version>
        <spring-cloud.version>2024.0.0</spring-cloud.version>
    </properties>

    <!-- Parent Spring Boot 4 -->
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>4.0.0</version>
        <relativePath/> <!-- lookup parent from repository -->
    </parent>

    <!-- Dependências -->
    <dependencies>
        <!-- Spring Boot Starters -->
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
            <artifactId>spring-boot-starter-opentelemetry</artifactId>
        </dependency>

        <!-- Database -->
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <version>42.7.0</version>
            <scope>runtime</scope>
        </dependency>

        <!-- Test -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.testcontainers</groupId>
            <artifactId>testcontainers</artifactId>
            <version>1.19.0</version>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <!-- Spring Boot Maven Plugin -->
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
                <executions>
                    <execution>
                        <goals>
                            <goal>repackage</goal>
                        </goals>
                    </execution>
                </executions>
            </plugin>

            <!-- Compiler Plugin — JDK 25 -->
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <configuration>
                    <source>25</source>
                    <target>25</target>
                    <release>25</release>
                    <!-- Enable preview features (Virtual Threads, Structured Concurrency) -->
                    <compilerArgs>
                        <arg>--enable-preview</arg>
                    </compilerArgs>
                </configuration>
            </plugin>

            <!-- Surefire (Unit Tests) — paralelismo por core -->
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>
                <configuration>
                    <forkCount>1C</forkCount>          <!-- 1 fork por core disponível -->
                    <reuseForks>true</reuseForks>      <!-- Reusar JVM (mais rápido) -->
                    <argLine>-XX:TieredStopAtLevel=1 --enable-preview</argLine>
                </configuration>
            </plugin>

            <!-- Failsafe (Integration Tests) -->
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-failsafe-plugin</artifactId>
                <configuration>
                    <forkCount>1C</forkCount>
                    <reuseForks>true</reuseForks>
                </configuration>
            </plugin>

            <!-- JaCoCo (Code Coverage) -->
            <plugin>
                <groupId>org.jacoco</groupId>
                <artifactId>jacoco-maven-plugin</artifactId>
                <version>0.8.11</version>
                <executions>
                    <execution>
                        <goals>
                            <goal>prepare-agent</goal>
                        </goals>
                    </execution>
                    <execution>
                        <id>report</id>
                        <phase>test</phase>
                        <goals>
                            <goal>report</goal>
                        </goals>
                    </execution>
                </executions>
            </plugin>
        </plugins>
    </build>
</project>
```

---

## 4. Configuração Mínima Obrigatória (.mvn/extensions.xml)

```xml
<!-- .mvn/extensions.xml — Build Cache Extension (Maven 4) -->
<extensions xmlns="http://maven.apache.org/EXTENSIONS/1.2.0">
    <extension>
        <groupId>org.apache.maven.extensions</groupId>
        <artifactId>maven-build-cache-extension</artifactId>
        <version>1.2.0</version>
    </extension>
</extensions>
```

```properties
# .mvn/maven.config
-T 1C
--batch-mode
--no-transfer-progress
```

**Explicação:**
- `-T 1C` = paralelismo automático (1 thread por core disponível)
- `--batch-mode` = sem interatividade (CI-friendly)
- `--no-transfer-progress` = sem barras de progresso (CI logs limpos)

---

## 5. Maven Daemon (mvnd) — Eliminando Cold Start

### Instalação

**macOS (Homebrew):**
```bash
brew install mvndaemon
mvnd --version
```

**Linux (SDK Manager):**
```bash
sdk install maven 4.1.0-mvnd.latest
mvnd --version
```

**Manual (qualquer OS):**
```bash
# 1. Download
curl -L https://dist.apache.org/repos/asf/dist/maven/mvnd/1.0.0/apache-maven-mvnd-1.0.0-linux-amd64.zip -o mvnd.zip
unzip mvnd.zip

# 2. Adicionar ao PATH
export PATH=/opt/mvnd/bin:$PATH

# 3. Verificar
mvnd --version
```

### Comparação: mvn vs mvnd

```bash
# Maven tradicional (cold start — Inicializa JVM do Maven)
$ time mvn clean install
real    0m28.345s
user    0m52.123s

# Maven Daemon (reutiliza JVM)
$ time mvnd clean install
real    0m1.823s    # ⚡ 15x mais rápido!
user    0m0.234s
```

### Quando Usar mvnd vs mvn

| Scenario | mvnd | mvn | Razão |
|----------|------|-----|-------|
| Dev local iterativo | ✅ | ❌ | Cold start não importa |
| CI/CD (fresh container) | ❌ | ✅ | Não há daemon anterior |
| IDE (IntelliJ, VS Code) | ✅ | — | Maven delegate reutiliza processo |
| One-off builds | ❌ | ✅ | Startup overhead não justifica |

---

## 6. Build Cache Extension — Cache Local e Remoto

### Configuração Local (Default)

```xml
<!-- .mvn/extensions.xml — Já inclui cache local por padrão -->
<extensions xmlns="http://maven.apache.org/EXTENSIONS/1.2.0">
    <extension>
        <groupId>org.apache.maven.extensions</groupId>
        <artifactId>maven-build-cache-extension</artifactId>
        <version>1.2.0</version>
    </extension>
</extensions>
```

Cache é armazenado em `~/.m2/cache/maven-build-cache/`.

### Configuração Remoto (S3)

```xml
<!-- .mvn/build-cache-config.xml — Ativar cache remoto S3 -->
<cache>
    <local>
        <location>${user.home}/.m2/cache/maven-build-cache</location>
    </local>
    <remotes>
        <remote>
            <id>maven-s3-cache</id>
            <url>s3://my-team-maven-cache/builds</url>
            <type>s3</type>
        </remote>
    </remotes>
</cache>
```

**AWS Credentials via IAM Role (ECS/EC2):**
```bash
# Variáveis de ambiente — IAM role fornece credenciais temporárias
export AWS_REGION=us-east-1
export AWS_S3_BUCKET=my-team-maven-cache
```

### Como Funciona

1. **Hash de inputs:** Maven computa hash de:
   - `pom.xml` (dependências, versões)
   - Código-fonte Java (arquivos modificados)
   - Properties e configurações

2. **Cache hit:** Se hash igual a build anterior:
   - Artifacts não são recompilados
   - Download de cache local ou S3
   - Build em 0.5-1.0s

3. **Cache miss:** Se hash diferente:
   - Compilação normal
   - Artifacts salvos no cache
   - Próxima execução idêntica reutiliza

**Impacto real:**
```
Primeira build:          28s (cold, sem cache)
Segunda build idêntica:  0.8s (cache hit)
Terceira build + 1 arquivo mudado: 1.2s (compilação incremental)
```

---

## 7. Paralelismo `-T 1C`, `-T 2C`, `-T 4`

```bash
# Automático (1 thread por core)
mvnd clean install -T 1C

# Múltiplos cores
mvnd clean install -T 2C   # 2 threads por core (arriscado)
mvnd clean install -T 4    # 4 threads fixos

# Modo série (quando há race conditions)
mvnd clean install -T 1
```

**Regra:** Começar com `-T 1C`. Se testes falharem com race conditions, usar `-T 1` (série).

---

## 8. CI-Friendly Versioning com ${revision}

```xml
<!-- pom.xml -->
<version>${revision}${changelist}</version>

<properties>
    <revision>1.0.0</revision>
    <changelist>-SNAPSHOT</changelist>
</properties>
```

**CI pipeline:**
```bash
# Jenkins / GitHub Actions — override de versão
mvnd clean deploy \
    -Drevision=1.0.0 \
    -Dchangelist= \
    -Dsha1=.git-$(git rev-parse --short HEAD)

# Resultado: artifact publicado como 1.0.0.git-abc1234
```

---

## 9. Checklist de Migração Gradle → Maven 4 via mvnup

A ferramenta `mvnup` converte projetos Gradle automaticamente:

```bash
# 1. Instalar mvnup
sdk install maven 4.1.0

# 2. Executar conversão
mvnup .

# 3. Revisar arquivo pom.xml gerado
cat pom.xml
```

### Passos Pós-Conversão

1. **Revisar dependências:**
   - Verificar `scope` (compile, test, runtime)
   - Remover exclusões desnecessárias
   - Garantir compatibilidade de versão

   ```bash
   mvnd dependency:tree | grep "CONFLICT"
   ```

2. **Configurar Surefire/Failsafe:**
   ```xml
   <configuration>
       <forkCount>1C</forkCount>
       <reuseForks>true</reuseForks>
   </configuration>
   ```

3. **Ativar Build Cache Extension:**
   - Criar `.mvn/extensions.xml`
   - Criar `.mvn/maven.config`

4. **Ativar mvnd:**
   ```bash
   mvnd --version
   mvnd clean install  # primeira execução
   ```

5. **Benchmark antes/depois:**
   ```bash
   # Gradle (histórico)
   ./gradlew clean build -x test  → 18s

   # Maven 4 + mvnd + cache
   mvnd clean install -DskipTests  → 1.2s
   ```

6. **Atualizar CI:**
   - GitHub Actions: `mvn` → `mvnd`
   - Jenkins: criar `.mvn/extensions.xml` no workspace
   - GitLab CI: imagem Docker com mvnd pré-instalado

---

## 10. Troubleshooting

### "mvnd travado no Windows"

**Sintoma:** `mvnd` para de responder durante build.

**Solução:**
```bash
# Matar daemon
mvnd --kill

# Limpar cache daemon
rm -rf %USERPROFILE%\.mvnd

# Reiniciar
mvnd clean install
```

### "Build Cache não inicializa"

**Sintoma:** aviso "Build Cache Extension not active".

**Solução:**
```bash
# 1. Verificar extensions.xml
cat .mvn/extensions.xml

# 2. Verificar permissões
ls -la .mvn/

# 3. Forçar cache:
mvnd clean install -Dmaven.build.cache.enabled=true
```

### "Dependency conflict após migração"

**Sintoma:** `DependencyResolutionException: Could not find artifact`.

**Solução:**
```bash
# 1. Gerar árvore de dependências
mvnd dependency:tree > deps.txt

# 2. Procurar conflito
grep "CONFLICT" deps.txt

# 3. Usar dependencyManagement para fixar versão
<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-dependencies</artifactId>
            <version>${spring-cloud.version}</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>
```

### "Testes em paralelo falham por race condition"

**Sintoma:** testes falham com `-T 2C` mas passam com `-T 1`.

**Solução:**
```xml
<!-- Use reuseForks=false para isolamento total -->
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-surefire-plugin</artifactId>
    <configuration>
        <forkCount>1</forkCount>         <!-- 1 fork por arquivo de teste -->
        <reuseForks>false</reuseForks>   <!-- Cada teste = JVM nova -->
    </configuration>
</plugin>
```

**Trade-off:** mais lento (~5s em vez de 2s) mas 100% isolado.

---

## 11. Benchmarks Esperados (Tabela Resumo)

| Operação | Maven 3 | Maven 4 padrão | Maven 4 + mvnd + cache | Ganho vs M3 |
|---|---|---|---|---|
| `clean install` (cold, sem cache) | 45s | 32s | 28s | 38% |
| `clean install` (cache hit) | N/A | 2.5s | 1.5s | 97% |
| `install` (fonte modificada) | 12s | 8s | 1.2s | 90% |
| `test` (1 classe modificada) | 8s | 5s | 0.8s | 90% |
| Startup daemon mvnd | N/A | N/A | 2s cold, 0.1s warm | — |
| Build parallelizado (-T 2C) | N/A | 18s | 1.8s | — |

---

## Referências

- [Apache Maven 4 Release](https://maven.apache.org/release-notes.html)
- [Maven Build Cache Extension](https://github.com/apache/maven-build-cache-extension)
- [Maven Daemon (mvnd)](https://github.com/apache/maven-mvnd)
- GLOSSARIO §9 (padrão da squad)
