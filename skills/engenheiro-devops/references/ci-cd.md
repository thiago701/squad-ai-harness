# Referência — Pipeline CI/CD (GitHub Actions, WIF, Renovate, Maven 4)

> Parte da skill `engenheiro-devops`. Carregue sob demanda. Hub: `../SKILL.md`.
## Pipeline CI/CD — Estrutura Padrão

### GitHub Actions — Java 25 (Spring Boot 4)

```yaml
name: CI/CD Pipeline
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          java-version: '25'
          distribution: 'temurin'
          cache: 'maven'   # cache nativo do ~/.m2/repository

      - name: Lint
        run: ./mvnw spotless:check

      - name: Unit Tests
        run: ./mvnw -T 1C test

      - name: Integration Tests
        run: ./mvnw -T 1C verify -Pintegration-tests
        services:
          postgres:
            image: postgres:16
            env:
              POSTGRES_DB: testdb
              POSTGRES_PASSWORD: test
            ports: ['5432:5432']

  build:
    needs: lint-and-test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          java-version: '25'
          distribution: 'temurin'
          cache: 'maven'

      - name: Build (Maven 4 + Build Cache Extension)
        run: ./mvnw -T 1C -DskipTests package spring-boot:repackage

      - name: Docker Build
        run: docker build -t ${{ github.repository }}:${{ github.sha }} .

  deploy:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      id-token: write    # ← necessário para OIDC / Workload Identity Federation
      contents: read
    steps:
      # Workload Identity Federation — SEM access keys long-lived
      - name: Configure AWS credentials via OIDC
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-actions-deploy
          role-session-name: gh-actions-${{ github.run_id }}
          aws-region: us-east-1

      - name: Deploy to staging
        run: aws ecs update-service --cluster prod --service api --force-new-deployment
```

### Workload Identity Federation — Zero credenciais long-lived na CI

A regra da squad é **nunca** usar `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` como secrets do
GitHub. Use **OIDC + IAM Role trust policy**:

```json
// IAM Role trust policy — confia apenas em PRs do repo específico
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
      },
      "StringLike": {
        "token.actions.githubusercontent.com:sub": "repo:empresa/api-pedidos:ref:refs/heads/main"
      }
    }
  }]
}
```

**Por que é obrigatório:**
- Credenciais vivem minutos (rotação automática por request)
- Vazamento no log não comprometerá nada depois que o job terminar
- Policy de role é auditável e segregada por ambiente (dev/staging/prod)
- Elimina classe inteira de incidentes (ex.: access key vazada em repo público)

### Renovate — Automação de dependências com janelas de merge

Renovate substitui Dependabot para casos complexos (monorepos, versões semânticas, major bumps
separados de minor/patch, rebase automático, schedule de merge).

```json
// renovate.json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:recommended", ":semanticCommits"],
  "schedule": ["every weekend"],
  "timezone": "America/Sao_Paulo",
  "packageRules": [
    {
      "matchUpdateTypes": ["minor", "patch"],
      "automerge": true,
      "automergeType": "pr",
      "platformAutomerge": true
    },
    {
      "matchUpdateTypes": ["major"],
      "dependencyDashboardApproval": true,
      "reviewers": ["team:platform"]
    },
    {
      "matchPackagePatterns": ["^org.springframework.boot"],
      "groupName": "Spring Boot",
      "schedule": ["before 3am on Monday"]
    },
    {
      "matchDepTypes": ["devDependencies"],
      "automerge": true
    }
  ],
  "vulnerabilityAlerts": {
    "enabled": true,
    "schedule": ["at any time"]   // CVEs: abre PR imediatamente
  }
}
```

**Regras-chave:**
- Major bumps sempre manuais (breaking changes requerem análise).
- Minor/patch auto-merge após testes verdes.
- CVEs ignoram schedule → PR imediata.
- Grupos (Spring Boot, AWS SDK) rebate em um único PR para evitar explosão de bumps.

### GitHub Actions — Python 3.12+ (FastAPI)

```yaml
name: CI/CD Pipeline
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Lint
        run: ruff check . && ruff format --check .

      - name: Type check
        run: mypy src/

      - name: Unit Tests
        run: pytest tests/unit -v --tb=short

      - name: Integration Tests
        run: pytest tests/integration -v --tb=short
        services:
          postgres:
            image: postgres:16
            env:
              POSTGRES_DB: testdb
              POSTGRES_PASSWORD: test
            ports: ['5432:5432']

  build:
    needs: lint-and-test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Docker Build
        run: docker build -t ${{ github.repository }}:${{ github.sha }} .
```

### Apache Maven 4 — Build Rápido como Requisito (P2)

Build lento é dívida técnica silenciosa. Apache Maven 4 (versão 4.0.0+, lançado em 2025) trouxe recursos que igualam — e em muitos cenários superam — o Gradle em velocidade:

- **`mvnd` (Maven Daemon)**: pool de processos Maven residentes, elimina overhead de startup da JVM e cache classloader entre builds
- **Maven Build Cache Extension**: cache incremental oficial de goals, comparável ao build cache do Gradle
- **Paralelismo nativo** via `-T 1C` (uma thread por core)
- **Consumer POM** (model 4.1.0): POM reduzido publicado no repositório, builds mais leves para consumidores
- **Maven Shell (`mvnsh`)**: um único processo Maven vivo enquanto o shell está aberto
- **`mvnup`**: ferramenta oficial para migração automática de POMs antigos

```xml
<!-- .mvn/extensions.xml — ativa o build cache oficial do Maven 4 -->
<extensions>
  <extension>
    <groupId>org.apache.maven.extensions</groupId>
    <artifactId>maven-build-cache-extension</artifactId>
    <version>1.2.0</version>
  </extension>
</extensions>
```

```xml
<!-- .mvn/maven.config — defaults OBRIGATÓRIOS em todo projeto -->
-T 1C
--batch-mode
--no-transfer-progress
-Dstyle.color=always
```

```properties
# .mvn/jvm.config — heap dedicado ao processo Maven
-Xmx2g
-XX:+HeapDumpOnOutOfMemoryError
-XX:+UseG1GC
```

Tempos esperados com **Maven 4 + mvnd + build cache**:
```
  mvnd compile               →  1-3s   (compilação incremental, daemon quente)
  mvnd test                  →  5-15s  (surefire paralelo, forkCount=1C)
  mvnd spring-boot:run       →  2-4s   (startup com DevTools)
  mvnd package               →  5-10s  (gera JAR + repackage)
  mvnd verify                → 15-30s  (build completo + integration tests)

  Se o build completo passa de 30s, investigue:
    □ A extension do build cache está em .mvn/extensions.xml?
    □ -T 1C está no .mvn/maven.config? (paralelismo por subprojeto)
    □ surefire/failsafe estão com forkCount=1C e reuseForks=true?
    □ Está usando mvnd em dev? (daemon evita warm-up da JVM)
    □ Há testes flaky causando retry? (elimine-os)
```

**Pipeline CI com cache do Maven 4:**

```yaml
# GitHub Actions — cache que faz diferença real
- uses: actions/setup-java@v4
  with:
    java-version: '25'
    distribution: 'temurin'
    cache: 'maven'   # cache automático de ~/.m2/repository

- name: Restore Maven Build Cache
  uses: actions/cache@v4
  with:
    path: ~/.m2/build-cache
    key: ${{ runner.os }}-mvn-buildcache-${{ hashFiles('**/pom.xml') }}
    restore-keys: ${{ runner.os }}-mvn-buildcache-

- name: Build
  run: ./mvnw -T 1C -Dmaven.build.cache.enabled=true verify
```

**Wrapper obrigatório (`./mvnw`)**: todo projeto deve usar Maven Wrapper, garantindo versão fixa do Maven 4.x independente do que o dev tem instalado:

```bash
mvn wrapper:wrapper -Dmaven=4.0.0
```

---

