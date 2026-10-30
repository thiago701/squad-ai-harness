# Estratégia de Cobertura 90% — Pragmática, Sustentável, Defensável

> **Quando ler este arquivo:** sempre que o objetivo de qualidade exigir cobertura de testes ≥ 90%, ou quando precisar decidir trade-offs entre line/branch/MC/DC/mutation, configurar quality gates, ou justificar mutantes sobreviventes.

> **Tese central:** 90% **não é uma meta de número** — é o efeito colateral de uma disciplina. Quem persegue o número, escreve testes ruins. Quem persegue o **risco coberto**, atinge o número e dorme tranquilo.

---

## 1. As Quatro Métricas que Importam (e a Única que Engana)

| Métrica | O que mede | Conta como prova de quê | Engana? |
|---|---|---|---|
| **Line coverage** | % de linhas executadas pelos testes | Que o código foi *visitado* | Sim — visitar ≠ verificar |
| **Branch coverage** | % de ramificações (if/else, switch) executadas | Que cada caminho foi *tocado* | Parcialmente — toca não significa observa |
| **MC/DC** (Modified Condition/Decision Coverage) | Para cada condição em decisão composta, se ela isoladamente afeta o resultado | Que cada cláusula booleana **tem efeito provado** | Não, para decisões complexas é a métrica honesta |
| **Mutation score** | % de mutantes (alterações sintéticas no código) que pelo menos um teste detecta | Que o teste *especifica comportamento*, não apenas executa | Não — é a única que prova qualidade real |

### Hierarquia de Confiança

```
Line ≤ Branch ≤ MC/DC ≤ Mutation Score
```

90% de **line** com 30% de **mutation** = teatro. 75% de **line** com 80% de **mutation** = qualidade real.

**Regra prática:** persiga line e branch como **higiene**, persiga mutation como **prova**.

---

## 2. Roadmap Incremental — Como Sair de 40% para 90% Sem Quebrar o Time

A cobertura 90% **não se constrói em sprint único**. É um caminho de 4-12 semanas dependendo do legado. O erro clássico é decretar `mvn jacoco:check minimum=0.90` num projeto de 40% e bloquear todo o time.

### Fase 1 — Diagnóstico (1 semana)

```bash
# Java/Maven
mvn clean verify
open target/site/jacoco/index.html

# Python
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

Coleta:
- Cobertura **atual** por pacote/módulo
- Mutation score **atual** em domínio crítico
- Lista de **classes com 0% de cobertura** (geralmente código morto ou utilities sem teste)
- Lista de **classes com cobertura cosmética** (>80% line + <40% branch)

### Fase 2 — Quick Wins (1-2 semanas)

Foco em **maior ganho com menor esforço**:

1. Apague código morto (não confunda 0% com "ainda vou testar"). Use `unused-code` do IntelliJ ou `vulture` em Python.
2. Teste **classes utility** primeiro — DateFormatters, Validators, Mappers. Cobertura sobe rápido, baixo risco.
3. Teste **happy paths de domínio** — pelo menos um teste por método público de Entity/UseCase.

Resultado típico: 40% → 65%-70%.

### Fase 3 — Branch Coverage (2-4 semanas)

Agora o objetivo muda: cobertura de linhas é proxy, **branch é o real**. Passe a olhar branches descobertos no relatório:

```bash
# JaCoCo: focar em "Missed Branches"
# pytest-cov: pytest --cov --cov-branch --cov-report=html
```

Para cada branch descoberto, escreva o teste do **caminho ausente**. Aplique os 8 eixos preditivos do hub (boundary, invalid input, state transitions, external failure).

Resultado típico: 70% line → 85% line + 75% branch.

### Fase 4 — Mutation Testing (4-8 semanas)

Quando line ≥ 85% e branch ≥ 75%, ative PIT/mutmut em **domínio crítico**:

```bash
# Java
mvn org.pitest:pitest-maven:mutationCoverage \
    -DtargetClasses="com.empresa.pedidos.domain.*"

# Python
mutmut run --paths-to-mutate=src/dominio/
```

Cada mutante sobrevivente vira issue. Aplique o protocolo da §5 (Classificar/Documentar/Cobrir).

Resultado: 85% line + 75% branch + **65%-80% mutation** em domínio crítico = **90%+ na média do projeto**.

### Fase 5 — Sustentação (contínua)

A regra "**toda PR deixa cobertura ≥ a anterior**" entra como quality gate. Detalhes em §4.

---

## 3. Cobertura Por Camada — Metas Diferenciadas

Cobertura uniforme é **antipattern**. Domínio 90%, infraestrutura 60% é certo. Forçar 90% em código de boilerplate (configs, getters/setters, exceções) é desperdício.

| Camada | Line target | Branch target | Mutation target | Por quê |
|---|---|---|---|---|
| **Domain** (`domain/`, `model/`) | ≥ 95% | ≥ 90% | ≥ 80% | Coração do negócio. Bug aqui é incidente. |
| **Application** (use cases, services) | ≥ 90% | ≥ 85% | ≥ 70% | Orquestração crítica. Bug aqui é regressão. |
| **Infrastructure** (repositórios, gateways) | ≥ 80% | ≥ 70% | n/a (use IT) | Coberto por **integration tests** (Testcontainers), não unit. |
| **API/Controller** | ≥ 85% | ≥ 75% | n/a (use IT) | Coberto por slice tests + contract tests. |
| **DTOs, Records, Configs** | ≥ 60% | n/a | n/a | Sem lógica. Não vale teste manual. |
| **Generated code** (mappers, OpenAPI) | excluir | excluir | excluir | `<exclude>` no JaCoCo/pytest-cov. |

### Excluir adequadamente é parte da estratégia

```xml
<!-- pom.xml -->
<plugin>
    <groupId>org.jacoco</groupId>
    <artifactId>jacoco-maven-plugin</artifactId>
    <configuration>
        <excludes>
            <exclude>**/*Application.class</exclude>
            <exclude>**/config/**</exclude>
            <exclude>**/dto/**</exclude>
            <exclude>**/generated/**</exclude>
            <exclude>**/*MapperImpl.class</exclude>   <!-- MapStruct -->
        </excludes>
    </configuration>
</plugin>
```

```ini
# .coveragerc (Python)
[run]
omit =
    */migrations/*
    */tests/*
    */__init__.py
    */config.py
    */generated/*
```

**Documente cada exclusão no commit message** ("excludes config — sem lógica testável"). Caso contrário, alguém vai apagar a exclusão e quebrar o build.

---

## 4. Quality Gates no Pipeline — Configuração Real

### 4.1 JaCoCo + Maven (Java)

```xml
<plugin>
    <groupId>org.jacoco</groupId>
    <artifactId>jacoco-maven-plugin</artifactId>
    <version>0.8.12</version>
    <executions>
        <execution>
            <id>prepare-agent</id>
            <goals><goal>prepare-agent</goal></goals>
        </execution>
        <execution>
            <id>report</id>
            <phase>verify</phase>
            <goals><goal>report</goal></goals>
        </execution>
        <execution>
            <id>check</id>
            <phase>verify</phase>
            <goals><goal>check</goal></goals>
            <configuration>
                <rules>
                    <!-- Regra global: 90% line, 80% branch -->
                    <rule>
                        <element>BUNDLE</element>
                        <limits>
                            <limit><counter>LINE</counter>   <minimum>0.90</minimum></limit>
                            <limit><counter>BRANCH</counter> <minimum>0.80</minimum></limit>
                        </limits>
                    </rule>
                    <!-- Regra de domínio: 95% line, 90% branch -->
                    <rule>
                        <element>PACKAGE</element>
                        <includes>
                            <include>com.empresa.pedidos.domain.*</include>
                        </includes>
                        <limits>
                            <limit><counter>LINE</counter>   <minimum>0.95</minimum></limit>
                            <limit><counter>BRANCH</counter> <minimum>0.90</minimum></limit>
                        </limits>
                    </rule>
                    <!-- Regra anti-regressão por classe: novas classes com >= 80% -->
                    <rule>
                        <element>CLASS</element>
                        <limits>
                            <limit>
                                <counter>LINE</counter>
                                <minimum>0.80</minimum>
                            </limit>
                        </limits>
                        <excludes>
                            <exclude>com.empresa.pedidos.legacy.*</exclude>
                        </excludes>
                    </rule>
                </rules>
            </configuration>
        </execution>
    </executions>
</plugin>
```

### 4.2 PIT (Mutation Testing) + Maven

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
            <param>com.empresa.pedidos.domain.*</param>
            <param>com.empresa.pedidos.application.*</param>
        </targetClasses>
        <targetTests>
            <param>com.empresa.pedidos.*Test</param>
        </targetTests>
        <mutationThreshold>80</mutationThreshold>          <!-- falha build se < 80% -->
        <coverageThreshold>85</coverageThreshold>          <!-- line coverage prerequisite -->
        <withHistory>true</withHistory>                     <!-- incremental -->
        <historyInputFile>${project.build.directory}/pit-history.bin</historyInputFile>
        <historyOutputFile>${project.build.directory}/pit-history.bin</historyOutputFile>
        <timestampedReports>false</timestampedReports>
        <outputFormats>
            <param>HTML</param>
            <param>XML</param>
            <param>CSV</param>
        </outputFormats>
        <mutators>
            <mutator>STRONGER</mutator>                      <!-- conjunto recomendado -->
        </mutators>
    </configuration>
    <executions>
        <execution>
            <id>pitest</id>
            <phase>verify</phase>
            <goals><goal>mutationCoverage</goal></goals>
        </execution>
    </executions>
</plugin>
```

**Histórico incremental** é essencial. Sem `withHistory=true`, PIT roda tudo do zero a cada build (>10min em projeto médio). Com histórico, roda só o que mudou (segundos).

### 4.3 Python — pytest-cov + mutmut

```ini
# pyproject.toml ou setup.cfg
[tool.pytest.ini_options]
addopts = "--cov=src --cov-branch --cov-report=html --cov-report=term-missing --cov-fail-under=90"
testpaths = ["tests"]

[tool.coverage.run]
source = ["src"]
branch = true
omit = [
    "*/migrations/*",
    "*/__init__.py",
    "*/config.py",
]

[tool.coverage.report]
exclude_also = [
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
fail_under = 90
show_missing = true
skip_covered = false
```

```bash
# Mutation testing — Python
pip install mutmut
mutmut run --paths-to-mutate=src/dominio/ --tests-dir=tests/unit/

# Quality gate via wrapper
python -c "
import subprocess
out = subprocess.check_output(['mutmut', 'results', '--all'], text=True)
killed = out.count('killed')
survived = out.count('survived')
score = killed / (killed + survived) if (killed + survived) > 0 else 1.0
assert score >= 0.80, f'Mutation score {score:.0%} < 80%'
print(f'Mutation score: {score:.0%} OK')
"
```

### 4.4 SonarQube — Quality Gate centralizada

```yaml
# .sonarqube/sonar-project.properties (ou via UI)
sonar.projectKey=pedidos
sonar.sources=src/main/java
sonar.tests=src/test/java
sonar.java.coveragePlugin=jacoco
sonar.coverage.jacoco.xmlReportPaths=target/site/jacoco/jacoco.xml
sonar.coverage.exclusions=**/dto/**,**/config/**,**/Application.java

# Quality gate
sonar.qualitygate.wait=true     # bloqueia o build se gate falhar
```

Configure o **Quality Gate** no SonarQube com:

| Condição | Operador | Threshold | Aplicação |
|---|---|---|---|
| Coverage on New Code | < | 90% | falha |
| Branch Coverage on New Code | < | 80% | falha |
| Duplicated Lines on New Code | > | 3% | falha |
| Maintainability Rating on New Code | pior que | A | falha |
| Reliability Rating on New Code | pior que | A | falha |
| Security Rating on New Code | pior que | A | falha |
| Security Hotspots Reviewed on New Code | < | 100% | falha |

**"On New Code"** é a chave: aplica o gate apenas ao que mudou no PR, não ao legado. Permite avanço sem bloqueio retroativo.

### 4.5 GitHub Actions — exemplo completo

```yaml
# .github/workflows/quality.yml
name: Quality Gates
on: [pull_request, push]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }   # full history para Sonar diff

      - uses: actions/setup-java@v4
        with: { java-version: '25', distribution: 'temurin' }

      - name: Unit + Integration tests
        run: ./mvnw verify -Dgroups='!performance'

      - name: Coverage gate (JaCoCo)
        run: ./mvnw jacoco:check
        # `check` falha o build se `<rules>` violadas

      - name: Mutation testing (incremental)
        run: ./mvnw org.pitest:pitest-maven:mutationCoverage
        # falha se mutationThreshold violado

      - name: Upload reports
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: coverage-reports
          path: |
            target/site/jacoco/
            target/pit-reports/

      - name: SonarQube scan
        env:
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
        run: ./mvnw sonar:sonar
```

---

## 5. Decisão 90% vs 100% — Quando Aceitar Mutantes Sobreviventes

100% de mutation score é matematicamente alcançável mas economicamente irracional. A pergunta certa é: **qual mutante posso documentar ao invés de cobrir?**

### Tabela de Decisão

| Tipo de mutante sobrevivente | Cobrir? | Documentar? | Por quê |
|---|---|---|---|
| Null check removido | Sim, sempre | Não | Bug latente |
| Boundary `>` → `>=` quando valor exato é alcançável em produção | Sim | Não | Bug iminente |
| Boundary `>` → `>=` quando valor exato é matematicamente impossível | Não | Sim | Mutante equivalente |
| Operação aritmética (`+` → `-`, `*` → `/`) | Sim, sempre | Não | Falsos comuns |
| Return value mutation | Sim, sempre | Não | Falta de assert |
| Conditional negation (`==` → `!=`) | Sim, sempre | Não | Inversão semântica |
| Void method call removed | Sim, sempre | Não | Side effect não verificado |
| String literal mutation | Depende | Talvez | Se a string é texto-livre, documente; se é chave, cubra |
| Inline constant mutation (`return 1` → `return 0`) em código de framework | Não | Sim | Equivalente — exemplo: `equals/hashCode` gerado |

### Como documentar mutante equivalente

```java
public boolean podeProcessar(Pedido p) {
    // PIT-EQUIVALENT: > vs >= é equivalente porque DESCONTO_MAX é uma BigDecimal não-fracionária,
    // e a regra de negócio (BR-104) garante que valores nunca chegam exatamente em DESCONTO_MAX
    // (validação anterior em CalculadorDesconto.aplicar arredonda para 2 casas + 0.01).
    return p.getValor().compareTo(DESCONTO_MAX) > 0;
}
```

Comentário **deve incluir** três coisas: que é mutante equivalente, qual a regra de negócio que torna equivalente, e onde está a validação que garante a regra. Sem isso, vira excusa para cobertura cosmética.

### Threshold final recomendado

```
Mutation Score Target:
  - Domínio crítico:        ≥ 80%  (perseguir 85%, aceitar 80%)
  - Application:            ≥ 70%
  - Demais camadas:         n/a (cobrir com IT)
```

100% é apropriado **apenas** em código de algoritmo isolado (calculadora financeira, parser, formatter) — onde toda mutação é semanticamente significativa.

---

## 6. Sintomas de Cobertura Cosmética — Diagnóstico Rápido

Sinais de que o projeto tem **número alto + qualidade baixa**:

| Sintoma | O que está realmente errado | Como confirmar |
|---|---|---|
| `@Test void test() { service.fazer(); }` sem `assertThat` | Nenhum contrato verificado | `grep -L "assertThat\|assertEquals\|verify"  src/test` |
| Testes que passam mesmo com `// TODO: implementar` | Mock retornando default não é assert | Remover método e ver se quebra |
| `mvn jacoco:report` mostra 92% mas mutation 35% | Visita ≠ verificação | Rodar PIT |
| Time evita refatorar porque "vai quebrar 200 testes" | Testes acoplados a implementação | Refatorar 1 método e contar quantos quebram |
| Nomes tipo `test1()`, `testMethod()`, `testSuccess()` | Não há especificação | `grep "test[0-9]\|testMethod\|testSuccess" src/test` |
| Setup gigante (`setUp()` com 30+ linhas) | Acoplamento entre testes | Verificar se há shared mutable state |
| Asserts apenas de tipo (`isInstanceOf` sem `satisfies`) | Confirma forma, não conteúdo | Mutar return e ver quantos quebram |

**Protocolo de diagnóstico:**

```bash
# 1. Confirmar cobertura cosmética
mvn jacoco:report
RATIO_COSMETIC=$(./scripts/calc_assert_per_test.sh)
echo "Asserts/Test: $RATIO_COSMETIC"  # < 2 = suspeito

# 2. Mutation pilot em pacote crítico
mvn pitest:mutationCoverage -DtargetClasses="com.empresa.pedidos.domain.Pedido"
# Score < 50% = confirmado: cobertura cosmética

# 3. Plano: priorizar reescrita > expansão
```

---

## 7. Cobertura Não-Funcional — Para Não Esquecer

Cobertura 90% **não** garante:

- **Performance**: cubra com testes de carga (ver `performance-tests.md`)
- **Segurança**: cubra com SAST (SonarQube, Snyk), DAST (OWASP ZAP), dependency scan
- **Concorrência**: cubra com testes de race usando `StructuredTaskScope` (ver `java25-spring7-testing.md` §3)
- **Tolerância a falha**: cubra com chaos engineering (Toxiproxy, fault injection)
- **Observabilidade**: testes que verificam métricas, traces, logs estruturados
- **Acessibilidade**: testes E2E com axe-core
- **Compatibilidade de schema**: contract testing (Pact bidirecional)

90% de cobertura **estática** sem essas dimensões = falsa segurança. A meta de "qualidade preditiva" é **cobertura + as dimensões dinâmicas**.

---

## 8. Métricas de Saúde da Suíte (Trend que Importa)

A suíte de testes precisa ser tratada como produto. Métricas para acompanhar **mensalmente**:

| Métrica | Aceitável | Saudável | Como medir |
|---|---|---|---|
| Tempo total da suíte unit | < 2min | < 30s | CI duration |
| Tempo total da suíte integration | < 10min | < 3min | CI duration |
| Tempo total da suíte E2E | < 20min | < 8min | CI duration |
| Flakiness rate (rerun rate) | < 2% | < 0.5% | CI history (Buildkite test analytics, GitHub flaky tests, etc.) |
| Tests added per week | > 5 | > 15 | git log + diff |
| Tests removed/refactored per week | > 1 | > 5 | git log + diff |
| Coverage trend | estável | crescente | Sonar history |
| Mutation trend | estável | crescente | PIT history (CSV) |
| Mean time to failure detection | < 1 dia | < 1h | issue history |
| Test/code ratio (LOC) | 1:1 | 2:1 | `cloc` |

**Vermelho em qualquer:** stop the line e investigue.

---

## 9. Anti-Receita: o Que NÃO Fazer

1. **Decretar 90% sem roadmap** — quebra o time, gera revolta, leva a coverage cosmética em 2 sprints.
2. **Forçar 90% em pacotes de geração de código** — desperdício, mascara problemas reais.
3. **Aceitar mutantes sobreviventes sem documentar** — 6 meses depois ninguém lembra por que sobreviveu.
4. **Excluir pacotes "porque é difícil testar"** — refatore o pacote para ser testável; difícil de testar = mal desenhado.
5. **Quality gate só em main, não em PR** — bug entra antes de ser detectado.
6. **Comparar cobertura entre projetos diferentes** — métrica por projeto, não por organização. Um parser puro tem 99%; um aggregator de eventos tem 75% e está ótimo.
7. **Reportar cobertura sem reportar mutation** — número sem qualidade.
8. **Agente que sobe coverage adicionando testes triviais** — `assertThat(x).isNotNull()` pra tudo destrói a confiança da suíte.

---

## 10. Checklist Sustentável (Use a Cada Sprint Review)

```
COBERTURA QUANTITATIVA:
□ Line coverage projeto inteiro    >= 90%?
□ Branch coverage projeto inteiro  >= 80%?
□ Line coverage domínio            >= 95%?
□ Branch coverage domínio          >= 90%?
□ Mutation score domínio crítico   >= 80%?

COBERTURA QUALITATIVA:
□ Cada teste tem nome que documenta o contrato (não 'test1')?
□ Cada teste tem ao menos 2 asserções verificando comportamento (não tipo)?
□ Os 8 eixos preditivos foram aplicados (boundary, invalid, state, etc.)?
□ Os mutantes sobreviventes em domínio crítico estão documentados?
□ Não há `@Disabled` sem issue link?

PIPELINE:
□ JaCoCo gate ativo no CI?
□ PIT roda em domínio crítico no CI?
□ SonarQube quality gate "On New Code" ativo?
□ Cobertura cai = build falha?
□ Mutation cai = build falha?

SUSTENTAÇÃO:
□ Tempo da suíte unit < 1min?
□ Flakiness < 1%?
□ Última revisão de exclusões < 90 dias atrás?
□ Time sabe diferenciar line × branch × mutation?
```

---

## 11. Frases para Defender 90% em Reunião

> "90% de cobertura não é a meta — é o efeito colateral de aplicarmos os 8 eixos preditivos. Quem persegue o número escreve testes ruins."

> "Line coverage é higiene, mutation score é prova. Posso ter 100% de linhas cobertas e zero confiança real."

> "Um mutante sobrevivente é uma lacuna de contrato — ou cubro, ou documento por que é equivalente. Aceitar sem decisão é dívida invisível."

> "Cobertura no PR ≥ cobertura no main é gate barato e não-político. Não bloqueia legado, mas impede novos buracos."

> "Se eu não consigo testar, é porque o design não permite. A solução é refatorar o código, não relaxar a meta."

---

**Próximo passo sugerido:** se ainda não viu, leia `references/mutation-specimen.md` para entender concretamente como classificar e cobrir mutantes em domínio bancário.
