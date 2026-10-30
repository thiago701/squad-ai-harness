# Referência — Veracode (AST de Plataforma: SAST, DAST, SCA, IaC, Container, Veracode Fix)

> Parte da skill `engenheiro-seguranca`. Carregue sob demanda. Hub: `../SKILL.md`.
> **Validar código concreto / gatear o PR / triar e mitigar flaw:** skill `validacao-veracode`
> (pré-scan determinístico por CWE + gate fail-closed + lente `rev-veracode` do `tech-lead-review`).
> Esta reference fica com a **adoção e integração** da plataforma.

Veracode é uma plataforma comercial de **Application Security Testing (AST)** que concentra
SAST, DAST, SCA, IaC/Container e remediação assistida por IA (Veracode Fix) com **governança por
política** e trilha de auditoria para compliance. Aqui interessa **como integrar ao pipeline e ao
GATE 2**, não a UI do portal.

## Quando usar Veracode — decisão P1 > P2 > P3 (anti-overengineering)

Veracode é **pago** e adiciona infraestrutura. Aplique a régua da squad antes de adotá-lo:

| Cenário | Ferramenta | Por quê |
|---|---|---|
| Projeto novo / startup / SaaS sem exigência regulatória | OWASP Dependency-Check (SCA) + SpotBugs+FindSecBugs (SAST) + `bandit`/`safety` (Python) | Free, simples, já cobre o essencial. **Default da squad.** |
| Contrato/edital/regulador exige evidência de AST (PCI-DSS, SOC 2, ISO 27001, FedRAMP, BACEN/SUSEP) | **Veracode Policy Scan** (relatório de compliance assinável) | Governança por política + atestado auditável que o tooling free não emite |
| Monorepo grande, alto volume de findings, ruído de falso-positivo insustentável | **Veracode** (SAST + SCA + Fix) | Menor FP em escala, dedup e mitigação com workflow aprovado |
| Precisa testar app/API **rodando** (não só código) | **Veracode DAST / DAST Essentials** | DAST é complementar ao SAST; pega falhas de runtime/config |

> **Regra:** não troque Dependency-Check + SpotBugs por Veracode "porque é melhor". Adote quando
> houver **driver de compliance/contrato** (P3-custo justificado por requisito explícito) ou quando
> o volume/ruído do free tooling deixou de ser gerenciável. Os dois modelos **coexistem**: free no
> dev-loop diário, Veracode no gate de release/compliance.

## Portfólio (o que cada produto faz)

| Produto | Tipo | O que escaneia | Onde roda |
|---|---|---|---|
| **Static Analysis — Pipeline Scan** | SAST rápido | artefato compilado (1ª parte) | CI/CD, por PR — **gating**, minutos |
| **Static Analysis — Policy Scan** (upload & scan) | SAST completo | artefato compilado | release/compliance — horas, gera status de política |
| **Sandbox Scan** | SAST iterativo | artefato | dev itera **sem** afetar compliance da política |
| **Greenlight / IDE Scan** | SAST inline | arquivo aberto | IDE (feedback imediato, shift-left) |
| **SCA (agent-based, ex-SourceClear)** | SCA | manifestos/lockfiles + grafo de dependências | CI ou local (`srcclr`), gera SBOM CycloneDX |
| **Dynamic Analysis / DAST Essentials** | DAST | app/API **em execução** | staging/prod-like |
| **IaC Security** | IaC scan | Terraform/CloudFormation/K8s (misconfig + secrets) | CI |
| **Container Security** | Image scan | imagem/SBOM do container | CI/registry |
| **Veracode Fix** | Remediação por IA (RAG) | flaws **do Pipeline Scan** (não Upload&Scan) → até 5 patches/flaw | CLI/IDE/GitHub — **gated** (humano revisa + **testa** antes do commit) |

## Severidade Veracode → severidade da squad → GATE

Veracode pontua de **5=Very High** a **0=Informational**. Mapeie para o modelo 🔴/🟡 e para os SLAs
de CVE já canônicos em `secrets-cripto.md`:

| Veracode | Squad | GATE 2 | Ação |
|---|---|---|---|
| 5 Very High · 4 High | 🔴 BLOQUEANTE | **trava** o merge | corrigir/mitigar antes do merge |
| 3 Medium | 🟡 Necessário | não trava | backlog prioritário (SLA 30d) |
| 2 Low · 1 Very Low · 0 Info | 🟢 informativo | não trava | backlog normal / aceitar com justificativa |

Além da severidade, o **Policy Scan** devolve um veredito de **política** (`Pass` / `Did Not Pass`)
e o Veracode Level (VL1–VL5). **Política = `Did Not Pass` ⇒ 🔴 trava o GATE 2**, mesmo que nenhum
flaw individual seja Very High (a política pode exigir, ex., score mínimo ou ausência de CWEs-alvo).

## Credenciais (HMAC) — secrets são radiação

Toda integração usa **API ID + API Key** (assinatura HMAC). **Nunca** commitar nem colocar em log.

- Local: `~/.veracode/credentials` (perfil), fora do repo.
- CI: variáveis `VERACODE_API_ID` / `VERACODE_API_KEY` vindas do cofre (GitHub Actions Secrets,
  AWS Secrets Manager, SSM Parameter Store) — injetadas só em runtime.
- SCA agent-based usa um token próprio: `SRCCLR_API_TOKEN`.
- Princípio de menor privilégio: crie uma **API service account** com escopo só de
  `Pipeline Scan`/`Upload and Scan`/`Results API` — não use credencial de humano admin.

## SAST — empacotamento Java: **dois modos** (Java 25 / Spring Boot 4 / Lambda)

Veracode oferece **dois caminhos** de SAST para Java — escolha pelo objetivo (docs: `compilation_java`, `veracode_static_scan`):

| Modo | Comando | Quando | Trade-off |
|---|---|---|---|
| **Source scan (build-free)** | `veracode package --java-source` (zip de `.java`/`.jsp`/`.html`, **sem compilar**) | dev-loop / PR gate / shift-left — rápido | menos cobertura de framework que o compilado |
| **Compiled** (`.jar`/`.war`/`.ear`) | `veracode package` (bytecode 1ª parte + **símbolos de debug**) | release / Policy Scan — cobertura máxima | exige build + cuidado de empacotamento (ver Shade) |

- **Símbolos de debug (modo compilado):** garanta `lines,vars,source` — `maven-compiler-plugin` →
  `<debug>true</debug>` + `<debuglevel>lines,vars,source</debuglevel>`. **Nunca** obfuscar/strippar (Veracode reporta arquivo+linha a partir do debug info).
- **⚠️ Maven Shade NÃO é amigo do Veracode (relevante para a Lambda da squad):** a doc é explícita —
  *"Do not use Maven Shade; Veracode has limited support for shaded dependencies"* e *"avoid nested JAR files (exceto uber-jar Spring Boot)"*. O fat-jar shaded da Lambda Java (ex.: `task-manager-lambda.jar` via `maven-shade-plugin`) cai exatamente nessa limitação. **Recomendação:** no PR gate use **`--java-source` (build-free)** — contorna o shade e ainda é mais rápido; para Policy Scan, empacote via `spring-boot-maven-plugin repackage` (uber-jar é suportado) ou suba as classes de 1ª parte sem o shade.
- **Limites do Pipeline Scan:** máx **60 min/scan**; artefato **≤ 200 MB** (o jar ~16 MB da Lambda está folgado). Suporte JRE 1.4–1.9, 10–26; Spring Boot 1.x–4.x.

```bash
# Build-free (recomendado p/ PR gate da Lambda — contorna a limitação do Maven Shade):
veracode package --java-source --output veracode-artifacts
veracode static scan veracode-artifacts/ \
  --fail-on-severity "Very High, High" \
  --fail-on-cwe "89,80,78,22" \
  --baseline-file baseline.json \
  --results-file results.json
# `veracode static scan` retorna exit code 3 quando há flaw acima do corte → trava o build (GATE 2)
```

### Pipeline Scan (gating por PR) — o que entra no CI

```bash
# Caminho estabelecido: pipeline-scan.jar (baixe dos downloads da Veracode / Maven wrappers)
mvn -q -DskipTests package
java -jar pipeline-scan.jar \
  --veracode_api_id "${VERACODE_API_ID}" \
  --veracode_api_key "${VERACODE_API_KEY}" \
  --file "target/app.jar" \
  --fail_on_severity="Very High, High" \
  --fail_on_cwe="80,89,78,22" \
  --baseline_file "baseline.json" \
  --json_output_file "results.json"
# exit code != 0 quando há flaw acima do corte → trava o build (GATE 2)
```

- **Baseline:** gere um `baseline.json` (`--store_baseline_file`) a partir de um scan limpo para
  **ignorar dívida pré-existente** e falhar só em flaws **novos** do PR. Trate a baseline como
  débito explícito e versionado — nunca como "silenciador" permanente.
- Pipeline Scan é **rápido (minutos)** e não afeta a política — ideal para o dev-loop/PR.

### GitHub Actions (Java) — Pipeline Scan + Veracode Fix

```yaml
jobs:
  veracode-sast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with: { distribution: temurin, java-version: '25' }
      - run: mvn -q -DskipTests package
      - name: Veracode Pipeline Scan
        uses: veracode/veracode-pipeline-scan-action@v1.0.16
        with:
          vid: ${{ secrets.VERACODE_API_ID }}
          vkey: ${{ secrets.VERACODE_API_KEY }}
          file: target/app.jar
          fail_build: true
          fail_on_severity: "Very High, High"
      # Opcional: sugerir patch de remediação por IA (gated — abre PR para revisão humana)
      - name: Veracode Fix
        if: failure()
        uses: veracode/veracode-fix@v1
        with:
          vid: ${{ secrets.VERACODE_API_ID }}
          vkey: ${{ secrets.VERACODE_API_KEY }}
          inputFile: results.json
```

### Policy Scan (release/compliance) — Upload & Scan

```yaml
      - name: Veracode Policy Scan
        uses: veracode/uploadandscan-action@0.2.6
        with:
          appname: 'minha-app'
          version: ${{ github.run_id }}
          filepath: target/app.jar
          vid: ${{ secrets.VERACODE_API_ID }}
          vkey: ${{ secrets.VERACODE_API_KEY }}
          createprofile: false
          scantimeout: 30
          failbuild: true        # falha se a política = "Did Not Pass"
```

## AWS — credenciais via Secrets Manager no CodeBuild

```yaml
# buildspec.yml — pipeline-scan no CodeBuild com HMAC do Secrets Manager
version: 0.2
env:
  secrets-manager:
    VERACODE_API_ID:  "veracode/ci:api_id"
    VERACODE_API_KEY: "veracode/ci:api_key"
phases:
  build:
    commands:
      - mvn -q -DskipTests package
  post_build:
    commands:
      # baixe o pipeline-scan.jar (endpoint de downloads do Pipeline Scan da Veracode)
      - java -jar pipeline-scan.jar
          --veracode_api_id "$VERACODE_API_ID" --veracode_api_key "$VERACODE_API_KEY"
          --file target/*.jar --fail_on_severity="Very High, High"
```

- IAM: a role do CodeBuild precisa só de `secretsmanager:GetSecretValue` no secret específico
  (+ `kms:Decrypt` da chave do secret) — least privilege.
- Alinha ao deploy canary: um flaw 🔴 no scan deve **abortar o deploy** (gatilho de rollback junto
  ao CVE CRITICAL do Dependency-Check — ver `arquiteto-cloud-aws`/`engenheiro-devops`).

## SCA — Veracode SCA (agent-based) vs OWASP Dependency-Check

- **Default da squad** continua o **OWASP Dependency-Check** (free, NVD) — ver `secrets-cripto.md`.
- **Veracode SCA** (ex-SourceClear) adiciona: grafo de dependências (direto × transitivo),
  *reachability* (a função vulnerável é realmente chamada?), risco de **licença** e **SBOM CycloneDX**.

```bash
export SRCCLR_API_TOKEN="${SRCCLR_API_TOKEN}"   # do cofre, nunca commitado
srcclr scan --recursive --bom                    # gera SBOM CycloneDX (sbom.json)
# falha o build conforme política de licença/severidade configurada
```

## Python — SAST e SCA

```bash
# SAST: empacote o fonte (Veracode analisa .py); a CLI unificada cuida do zip
veracode package --source . --output veracode-artifacts --trust
veracode static scan veracode-artifacts/ --fail-on-severity="Very High, High"

# SCA: a partir de requirements.txt / poetry.lock / Pipfile.lock
srcclr scan --recursive
```

> Veracode SAST de Python é **source-based**: garanta `requirements.txt`/lockfile resolvíveis para
> o SCA, e que o app **importe/rode** (sem erro de sintaxe) para o SAST mapear data-flow.

## DAST — testar a API **rodando** (OpenAPI → scanner)

SAST/SCA não enxergam falha de runtime/config; uma API pública (API Gateway) pede DAST complementar.
Veracode DAST ingere a **especificação** e ataca os endpoints como um atacante (docs: `Scan_web_applications_and_APIs`):

- **Formatos aceitos:** **OpenAPI 2.0/3.0/3.1** (a squad **já gera** `app/openapi/openapi.yaml`!), Postman Collection 2.1, HAR — sempre com a **base URL** onde a API está hospedada.
- **Tie-in direto:** aponte o DAST para o `openapi.yaml` do projeto + a base URL do API Gateway publicado.
- **APIs autenticadas (Cognito/JWT):** forneça **login script**/credenciais válidas para o scanner autenticar antes de crawlear (senão só toca o 401).
- **DAST Essentials** (Quick scan não-invasivo + Full scan) × **Dynamic Analysis** (escala/cobertura) — mesmo engine; integra CI/SCM/ticketing via REST API + scans agendados.
- **Quando:** após deploy em staging/prod-like — **não** no PR local (exige o app rodando). Complementa, não substitui, o Pipeline Scan.

## Fluxo de mitigação de flaws (gated)

Quando um flaw não é um bug real (falso-positivo, mitigado por design, compensado por outro
controle): proponha **mitigation** no Veracode (`Mitigate by Design` / `False Positive` /
`Approved by Policy`) com **evidência técnica**. A mitigação **só vale após aprovação de um
revisor** (separação de papéis — quem corrige ≠ quem aprova). Nunca "aceite" flaw 🔴 sem trilha.

## Checklist de adoção

- ✅ Driver de adoção é **compliance/contrato** ou ruído insustentável — não "é melhor" (P1>P2>P3).
- ✅ API service account com escopo mínimo; HMAC no cofre (Secrets Manager/SSM/Actions Secrets).
- ✅ **Pipeline Scan** em todo PR (rápido, `--fail-on-severity "Very High, High"`, com `baseline.json`); para Lambda com fat-jar **shaded**, prefira **`--java-source` (build-free)** e evite a limitação do Maven Shade.
- ✅ **Policy Scan** no release com `failbuild: true` (`Did Not Pass` ⇒ trava GATE 2).
- ✅ Artefato com **símbolos de debug** (não strippar); preferir `veracode package`.
- ✅ **SCA** (Dependency-Check no dia a dia; Veracode SCA quando precisar de reachability/licença/SBOM).
- ✅ Severidade 5/4 mapeada a 🔴 bloqueante; mitigação **gated** (aprovador ≠ autor).
- ✅ Flaw 🔴 aborta deploy (gatilho de rollback, junto ao CVE CRITICAL).

## Anti-padrões

- **"Scan sem símbolos de debug"** — sobe `.jar` strippado → PreScan falha ou cobertura pobre. Use `veracode package` com `lines,vars,source`.
- **"Scan do fat-jar shaded"** — Veracode tem **suporte limitado a deps shaded** (Maven Shade); para Lambda use `--java-source` (build-free) ou `spring-boot repackage` (uber-jar), nunca o artefato cru do `maven-shade-plugin`.
- **"Só Sandbox, nunca Policy"** — itera no sandbox mas nunca promove à política → zero evidência de compliance.
- **"Baseline como silenciador"** — usar baseline para esconder dívida em vez de pauta-la e remediá-la.
- **"HMAC no YAML/código"** — credencial Veracode hardcoded é o mesmo crime de secret no fonte (🔴).
- **"Veracode no lugar do free tooling no dev-loop"** — scan pago lento em todo commit; use Pipeline Scan no PR e Dependency-Check/SpotBugs no loop local.
- **"Mitigação sem revisor"** — autor marcando o próprio flaw como falso-positivo quebra separação de papéis.
- **"SAST sem DAST em API pública"** — SAST não vê falha de runtime/config; app exposto pede DAST complementar.

## Fontes (docs.veracode.com — verificado 2026-06)

- Pipeline Scan: `/r/Pipeline_Scan`, `/r/r_pipeline_scan_commands`, `/r/Run_a_Pipeline_Scan_from_the_Command_Line`
- CLI unificada: `/r/Veracode_CLI`, `/r/veracode_static_scan` (exit code 3; flags `--results-file`/`--baseline-file`/`--fail-on-severity`/`--fail-on-cwe`/`--policy-file`)
- Empacotamento Java: `/r/compilation_java` (`--java-source` build-free; debug `lines,vars,source`; **sem Maven Shade**; uber-jar Spring Boot OK)
- SCA agent-based: `/r/Agent_Based_Scans`
- DAST (apps + APIs): `/r/Scan_web_applications_and_APIs` (OpenAPI 2.0/3.0/3.1, Postman 2.1, HAR; login scripts p/ auth)
- Veracode Fix: `/r/About_Veracode_Fix` (RAG, só Pipeline Scan, ≤5 patches/flaw, testar após aplicar)
- Limites Pipeline Scan: 60 min/scan, artefato ≤ 200 MB.
