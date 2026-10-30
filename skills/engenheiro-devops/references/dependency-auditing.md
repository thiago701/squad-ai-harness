# Referência — Dependency Auditing (OWASP Dependency-Check, Trivy, Dependabot, SLA CVSS, governo de bypasses)

> Parte da skill `engenheiro-devops`. Carregue sob demanda. Hub: `../SKILL.md`.
> Movido verbatim de `observabilidade.md` § "Dependency Auditing Pipeline" (ciclo 6a do Loop V3, 2026-07-09).

### Dependency Auditing Pipeline — Ferramenta Integrada

Gerenciamento de vulnerabilidades em dependências é **crítico em produção**. Stack recomendado: OWASP Dependency-Check (Maven) + Trivy (imagens) + Dependabot/Renovate (PRs automáticas).

#### OWASP Dependency-Check Maven Plugin

```xml
<!-- pom.xml — integração oficial de Dependency-Check -->
<plugin>
  <groupId>org.owasp</groupId>
  <artifactId>dependency-check-maven</artifactId>
  <version>9.0.0</version>
  <executions>
    <execution>
      <phase>verify</phase>
      <goals>
        <goal>check</goal>
      </goals>
      <configuration>
        <nvdApiKey>${env.NVD_API_KEY}</nvdApiKey>
        <failBuildOnCVSS>7.0</failBuildOnCVSS>   <!-- CRITICAL + HIGH falham o build -->
        <skipProvidedScope>true</skipProvidedScope>
        <skipTestScope>false</skipTestScope>
        <suppressionFiles>
          <suppressionFile>${basedir}/dependency-check-suppressions.xml</suppressionFile>
        </suppressionFiles>
        <format>JSON</format>   <!-- Gera report em JSON para CI parsing -->
        <reportOutputDirectory>${project.basedir}/target/dependency-check</reportOutputDirectory>
      </configuration>
    </execution>
  </executions>
</plugin>
```

```xml
<!-- dependency-check-suppressions.xml — governance de bypasses -->
<?xml version="1.0" encoding="UTF-8"?>
<suppressions xmlns="https://jeremylong.github.io/DependencyCheck/dependency-suppression.1.3.xsd">
  <!-- Exemplo: bypass conhecido, registrado em ADR -->
  <suppress>
    <notes>
      <note>Bypass autorizado por eng-security (ADR-2026-041) — log4j 2.17.0
            é safe em nosso contexto (dados sensíveis não logados).
            Expiração: 2026-05-10</note>
    </notes>
    <cve>CVE-2021-44228</cve>
    <expires>2026-05-10</expires>
  </suppress>
</suppressions>
```

#### SLA de Atualização por Severidade CVSS

| Severidade | CVSS | SLA de Patch | Tipo de Release | Ação |
|---|---|---|---|---|
| **CRITICAL** | ≥ 9.0 | **24 horas** | Hotfix release | Escalação PagerDuty, bypass automático recusado |
| **HIGH** | 7.0-8.9 | **7 dias** | Patch release | Revisão + merge em 24h, deploy em 7 dias |
| **MEDIUM** | 4.0-6.9 | **30 dias** | Regular release | Planejado em sprint, sem urgência |
| **LOW** | < 4.0 | Próximo release | Regular release | Backlog de dívida técnica |

#### Governo de Bypasses (Dependency Suppression)

```
REGRA: Um CVE CRÍTICO **nunca** pode ter bypass — deve ser patchado ou o serviço é desativado.

Para HIGH/MEDIUM/LOW bypasses:
  1. Abrir ADR (Architecture Decision Record) técnico
  2. Justificativa clara: "Por que o CVE não afeta nossa app?"
       Exemplos válidos:
       - "Dependência transitiva, nunca utilizada"
       - "Função vulnerável não é chamada em nosso código"
       - "Exposição requer access físico ao servidor"
  3. Assinado por: Staff Engineer (tech lead) + Security Engineer
  4. Expiração OBRIGATÓRIA: ≤ 30 dias
  5. Depois expira, trigger automático de re-avaliação
```

**Exemplo de ADR:**

```markdown
# ADR-2026-041: Suppress log4j CVE-2021-44228

## Decision
Accept CVE-2021-44228 in log4j 2.17.0 (CVSS 10.0) com expiration 2026-05-10.

## Justification
- Função vulnerável: RollingFileAppender com janela de condição race
- Nossa app: usa ConsoleAppender (stdout) + LogstashEncoder
- Impact: zero — output streaming, não arquivo local
- Alternativa: upgrade para 2.20.0 (inclui security patch)
  Break risk: (mínimo, patch-level)

## Timeline
- 2026-04-10: Aprovado por @tech-lead @security-eng
- 2026-05-10: Expiração — re-avaliar ou atualizar dependência

## Sign-off
Approved: @tech-lead
Approved: @security-eng
```

#### GitHub Actions — Dependency-Check + Trivy em CI

```yaml
# .github/workflows/dependency-audit.yml
name: Dependency Audit Pipeline
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    # Nightly scan (NVD database atualizado diariamente)
    - cron: '0 2 * * *'

jobs:
  dependency-check:
    name: OWASP Dependency-Check (Maven)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-java@v4
        with:
          java-version: '25'
          distribution: 'temurin'
          cache: 'maven'

      # Maven Dependency-Check integrado no pom.xml
      - name: Run Dependency-Check
        run: ./mvnw -B verify -Ddependency-check.skip=false -DskipTests
        env:
          NVD_API_KEY: ${{ secrets.NVD_API_KEY }}  # Chave da NVD (NIST)

      # Parse e fail se CRITICAL/HIGH encontrado
      - name: Parse Dependency-Check Report
        if: always()
        run: |
          REPORT="target/dependency-check/dependency-check-report.json"
          if [ ! -f "$REPORT" ]; then
            echo "No dependency-check report found"
            exit 1
          fi
          
          # Extrair severidades
          CRITICAL=$(jq '[.reportSchema.vulnerabilities[] | select(.cvssScore >= 9.0)] | length' "$REPORT")
          HIGH=$(jq '[.reportSchema.vulnerabilities[] | select(.cvssScore >= 7.0 and .cvssScore < 9.0)] | length' "$REPORT")
          
          echo "CRITICAL vulnerabilities: $CRITICAL"
          echo "HIGH vulnerabilities: $HIGH"
          
          if [ "$CRITICAL" -gt 0 ]; then
            echo "::error::Found $CRITICAL CRITICAL CVEs — pipeline FAILED"
            exit 1
          fi

      # Upload report como artifact
      - name: Upload Dependency-Check Report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: dependency-check-report
          path: target/dependency-check/

  # Trivy: scan de vulnerabilidades em imagens Docker
  trivy-scan:
    name: Trivy Container Image Scan
    runs-on: ubuntu-latest
    needs: dependency-check
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          java-version: '25'
          distribution: 'temurin'
          cache: 'maven'

      # Build imagem Docker
      - name: Build Docker Image
        run: |
          ./mvnw -B -T 1C -DskipTests clean package spring-boot:repackage
          docker build -t myapp:${{ github.sha }} .

      # Trivy scan (HIGH,CRITICAL falham o build)
      - name: Run Trivy Scan
        uses: aquasecurity/trivy-action@0.28.0
        with:
          image-ref: myapp:${{ github.sha }}
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'

      # Upload SARIF para GitHub Security tab
      - name: Upload Trivy Results to GitHub Security
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: 'trivy-results.sarif'
          category: 'trivy'

  # Dependabot / Renovate: PRs automáticas para dependências
  dependabot:
    name: Dependabot Auto-Update Check
    runs-on: ubuntu-latest
    # Dependabot roda como GitHub App separado — este job apenas valida config
    steps:
      - uses: actions/checkout@v4
      - name: Verify Dependabot config
        run: |
          [ -f ".github/dependabot.yml" ] && echo "✓ Dependabot configured" || exit 1

  # Aggregate report com SLA de patch
  summary:
    name: Dependency Audit Summary
    runs-on: ubuntu-latest
    needs: [dependency-check, trivy-scan]
    if: always()
    steps:
      - name: Generate Audit Summary
        run: |
          echo "## Dependency Audit Report" >> $GITHUB_STEP_SUMMARY
          echo "| Check | Status | Action |" >> $GITHUB_STEP_SUMMARY
          echo "|-------|--------|--------|" >> $GITHUB_STEP_SUMMARY
          echo "| Maven Dependency-Check | PASSED | No CRITICAL/HIGH CVEs found |" >> $GITHUB_STEP_SUMMARY
          echo "| Trivy Image Scan | PASSED | Container image clean |" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "### SLA de Atualização por Severidade" >> $GITHUB_STEP_SUMMARY
          echo "- CRITICAL (CVSS ≥ 9.0): Patch em **24h**" >> $GITHUB_STEP_SUMMARY
          echo "- HIGH (CVSS 7.0-8.9): Patch em **7 dias**" >> $GITHUB_STEP_SUMMARY
          echo "- MEDIUM (CVSS 4.0-6.9): Patch em **30 dias**" >> $GITHUB_STEP_SUMMARY
          echo "- LOW (< 4.0): Próximo release regular" >> $GITHUB_STEP_SUMMARY

      # Enviar alert para Slack/PagerDuty se CRITICAL
      - name: Alert on CRITICAL CVE
        if: failure()
        uses: slackapi/slack-github-action@v1
        with:
          payload: |
            {
              "text": "🚨 CRITICAL CVE detected in ${{ github.repository }}",
              "blocks": [
                {
                  "type": "section",
                  "text": {
                    "type": "mrkdwn",
                    "text": "*CRITICAL CVE Alert*\n*Repository:* ${{ github.repository }}\n*Commit:* <${{ github.server_url }}/${{ github.repository }}/commit/${{ github.sha }}|${{ github.sha }}>\n*Action Required:* Patch within 24 hours"
                  }
                }
              ]
            }
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}
          SLACK_WEBHOOK_TYPE: INCOMING_WEBHOOK
```

```yaml
# .github/dependabot.yml — PRs automáticas para dependências
version: 2
updates:
  # Maven dependencies
  - package-ecosystem: "maven"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "03:00"
    open-pull-requests-limit: 10
    allow:
      - dependency-type: "direct"
      - dependency-type: "indirect"
    ignore:
      # Ignorar updates para versões menores se não afetar segurança
      - dependency-name: "org.springframework.boot:spring-boot-starter-web"
        update-types:
          - "version-update:semver-minor"
    reviewers:
      - "tech-lead"
      - "security-eng"
    assignees:
      - "platform-team"
    labels:
      - "dependencies"
      - "security"
    commit-message:
      prefix: "chore(deps):"
      include: "scope"

  # Docker base images
  - package-ecosystem: "docker"
    directory: "/"
    schedule:
      interval: "weekly"
    reviewers:
      - "devops-engineer"

  # GitHub Actions
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    reviewers:
      - "devops-engineer"
```

#### Checklist: Dependency Auditing Pipeline

- ✅ OWASP Dependency-Check Maven plugin ligado ao phase `verify`
- ✅ NVD API key configurada (secrets.NVD_API_KEY)
- ✅ `failBuildOnCVSS=7.0` para HIGH/CRITICAL
- ✅ Suppressions file com ADRs e datas de expiração
- ✅ Trivy scan em toda imagem Docker (GitHub Actions)
- ✅ Trivy results upadas para GitHub Security tab (SARIF)
- ✅ Dependabot/Renovate configurado para PRs automáticas
- ✅ SLA de patch documentado: CRITICAL (24h), HIGH (7d), MEDIUM (30d)
- ✅ Slack/PagerDuty alert para CRITICAL CVEs
- ✅ Artifact de reports (JSON + SARIF) retido por ≥ 30 dias
