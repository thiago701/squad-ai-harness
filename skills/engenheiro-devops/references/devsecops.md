# engenheiro-devops · DevSecOps
> Quando carregar: SAST/SCA/DAST no pipeline, gate de severidade antes do deploy, SBOM CycloneDX, supply chain (Actions pinadas por SHA, assinatura, proveniência), segredos fora do repo, scanner de segredo, OIDC no lugar de chave, IaC scanning ou evidência `05b-veracode.md`.

Segurança entra como **gate mecânico com exit code**, não como opinião de revisão. O SAST e a política Veracode pertencem à skill irmã
`validacao-veracode` (fluxo V1–V6, perfis `maximo`/`padrao`, `veracode_gate.py`): esta reference **aponta** para ela e cobre o resto da cadeia.

## Onde cada verificação entra
Contexto: o pipeline-base está em `references/ci-cd.md`; aqui cada controle ganha sua etapa e o efeito se falhar.

| Etapa | Verificação | Ferramenta | Se falhar |
|---|---|---|---|
| Pre-commit / PR | segredos; SCA; IaC; SAST (pré-scan + Pipeline Scan); Actions pinadas | gitleaks · OSV-Scanner/Dependency-Check · Trivy config/Checkov · `validacao-veracode` V3–V5 | bloqueia o merge |
| Merge na `main` | build + SBOM; Policy Scan; imagem; assinatura e atestado | CycloneDX · Veracode (V4) · Trivy image · cosign | bloqueia a promoção do artefato |
| Pré-deploy | gate de severidade; verificação de assinatura/SBOM; DAST em hml | `gate_severidade.py` · ZAP baseline ou Veracode Dynamic Analysis | bloqueia o deploy |
| Noturno | bases de CVE atualizadas; drift de IaC | Dependency-Check/Trivy (`dependency-auditing.md`) | abre ticket com SLA |

## SAST, SCA e DAST — o que cada um responde
Contexto: três técnicas com pontos cegos diferentes; nenhuma substitui a outra.
- **SAST (código próprio):** use `skills/validacao-veracode/SKILL.md`. Pontos que importam aqui: V1 (sem autorização e credencial, só pré-scan local;
  código de cliente vai ao tenant do dono), gate fail-closed (`exit 1` BLOQUEADO, `exit 2` entrada inválida — nenhum aprova) e o `review_worker` para o `tech-lead-review`.
- **SCA (dependências e imagem):** OSV-Scanner, OWASP Dependency-Check, Trivy. SLA e governo de bypass já estão em `references/dependency-auditing.md`.
- **DAST (aplicação rodando):** OWASP ZAP em modo baseline (ação oficial do GitHub) ou Veracode Dynamic Analysis, **só contra hml/sandbox**, nunca prod;
  usuários de teste sintéticos com credencial vinda do cofre.

## Política de severidade e gate antes do deploy
Contexto: o gate decide por número (CVSS) e por regra de exceção, nunca por "parece aceitável".

| Severidade | CVSS | Gate | Exceção |
|---|---|---|---|
| Crítica | ≥ 9.0 | bloqueia | **nunca** (corrigir ou desativar) |
| Alta | 7.0–8.9 | bloqueia | só com dono + prazo + registro |
| Média | 4.0–6.9 | não bloqueia; ticket com SLA | — |
| Baixa | < 4.0 | backlog | — |

Sem score CVSS usa-se a severidade textual do scanner (fail-closed). Prazos de patch: tabela de SLA em `dependency-auditing.md`.
A escala 0–5 do Veracode e o corte do perfil `maximo` ficam na skill irmã. **Exceção válida** = `dono`, `registro` (ADR/Jira), `expira`
(≤ prazo da política, ver `dependency-auditing.md` § Governo de Bypasses) e aprovador ≠ autor — este último é garantido por CODEOWNERS/revisão obrigatória
do `excecoes.json`, não pelo script; vencida, o gate volta a bloquear.

```python
# gate_severidade.py — uso: gate_severidade.py trivy.json excecoes.json  (excecoes: {"excecoes":[{id,dono,registro,expira}]})
import json, sys, datetime as dt
LIMITE, CRITICO = 7.0, 9.0
FALLBACK = {"CRITICAL": 9.0, "HIGH": 7.0}                  # sem CVSS => severidade textual (fail-closed)
try:
    rel = json.load(open(sys.argv[1]))
    exc = {e["id"]: e for e in json.load(open(sys.argv[2]))["excecoes"]}
except (OSError, ValueError, KeyError, IndexError) as erro:
    print("entrada invalida:", erro); sys.exit(2)          # exit 2 também NÃO aprova
hoje, bloq = dt.date.today().isoformat(), []
for r in rel.get("Results", []):
    for v in r.get("Vulnerabilities") or []:
        score = max((c.get("V3Score", 0) for c in (v.get("CVSS") or {}).values()), default=0) \
                or FALLBACK.get(v.get("Severity"), 0)
        e = exc.get(v["VulnerabilityID"], {})
        valida = all(e.get(k) for k in ("dono", "registro", "expira")) and e["expira"] >= hoje and score < CRITICO
        if score >= LIMITE and not valida:
            bloq.append((v["VulnerabilityID"], score, v.get("PkgName")))
for b in bloq:
    print("BLOQUEIA", *b)
sys.exit(1 if bloq else 0)
```

## SBOM CycloneDX e supply chain
Contexto: SBOM, pinagem, assinatura e proveniência respondem "o que está dentro do artefato e quem o produziu".
- **SBOM por build:** `./mvnw org.cyclonedx:cyclonedx-maven-plugin:makeAggregateBom` gera `target/bom.json`; para imagem, `syft <imagem> -o cyclonedx-json`
  (ou Trivy com formato CycloneDX). O SBOM viaja com o artefato e tem hash registrado.
- **Actions pinadas por SHA de commit** (tag é móvel). Os exemplos de `ci-cd.md` usam tags por legibilidade; em banco, pine. O Dependabot (`github-actions`) atualiza os SHAs.
- **Dependências pinadas:** versões Maven explícitas com `maven-enforcer-plugin`; `uv.lock`/`poetry.lock` com hashes; imagem base por digest (`FROM img@sha256:<digest>`).
- **Assinatura:** `cosign sign --key awskms:///<alias>` (ou keyless se Fulcio/Rekor forem aprovados) e `cosign verify` no pré-deploy.
- **Proveniência:** `actions/attest-build-provenance` + `gh attestation verify <artefato> -R <org>/<repo>`. Disponibilidade (GitHub Docs, "Use artifact attestations", consultado em 11/10/2026): em Free/Pro/Team só para repositórios públicos; **repositório privado ou interno exige GitHub Enterprise Cloud**; indisponível em planos legados. Sem GHEC, a alternativa é Sigstore/cosign com OIDC do Actions ou assinatura com chave no KMS do banco.

```yaml
# trecho de workflow — SHAs obtidos com: gh api repos/<org>/<acao>/git/ref/tags/<tag> ; permissões mínimas por job
permissions: {contents: read}
jobs:
  build:
    runs-on: ubuntu-latest
    permissions: {contents: read, id-token: write, attestations: write}   # elevação só neste job
    steps:
      - uses: actions/checkout@<sha-40-hex>                # vX.Y.Z
      - uses: actions/setup-java@<sha-40-hex>              # vX.Y.Z
        with: {java-version: '25', distribution: temurin, cache: maven}
      - run: ./mvnw -B -DskipTests package org.cyclonedx:cyclonedx-maven-plugin:makeAggregateBom
      - uses: actions/upload-artifact@<sha-40-hex>         # vX.Y.Z
        with:
          name: build-${{ github.sha }}
          path: |
            target/*.jar
            target/bom.json
      - uses: actions/attest-build-provenance@<sha-40-hex> # vX.Y.Z
        with: {subject-path: 'target/*.jar'}
```

## Segredos fora do repositório
Contexto: segredo commitado é incidente, mesmo em repo privado; a defesa é detectar cedo, não ter chave de longa duração e saber rotacionar.
- **Detecção em duas camadas:** hook de pre-commit (framework `pre-commit` com o hook do gitleaks, baixado do GitHub) **e** `gitleaks dir .` no CI (histórico: `gitleaks git`).
  Ative também secret scanning e push protection do GitHub se o plano permitir.
- **Sem chave no repo, workflow ou imagem:** segredos de runtime em Secrets Manager/Parameter Store via role; CI com **OIDC/WIF** (`ci-cd.md` § Workload Identity Federation).
- **Vazou = comprometido:** revogar/rotacionar primeiro, depois limpar histórico, registrar a lição no `error_ledger`. Periodicidade de rotação: <conforme política do banco>.

```bash
# teste sintético: o scanner TEM que pegar um segredo gerado em runtime (formato do detector; nunca um segredo real)
t=$(mktemp -d) && cd "$t" && git init -q
printf 'aws_key = "AKIA%s"\n' "$(LC_ALL=C tr -dc 'A-Z2-7' </dev/urandom | head -c16)" > cfg.txt
gitleaks dir . --no-banner --redact >/dev/null; test $? -eq 1 && echo "OK: segredo sintético detectado"
```

## IaC scanning
Contexto: Terraform, CloudFormation, Dockerfile e manifestos também carregam vulnerabilidades (exposição, permissão, criptografia).
- `trivy config --severity HIGH,CRITICAL --exit-code 1 .` e/ou `checkov -d .`; CloudFormation com `cfn-lint`. Em Terraform, escaneie também o plano
  (`terraform show -json plan.out`), que já resolve variáveis.
- Regras mínimas declaradas no repo: sem entrada `0.0.0.0/0` em porta administrativa, sem bucket público, criptografia em repouso, sem `*:*` em IAM, logs ligados, tags obrigatórias.
- Exceção de IaC segue o mesmo formato (dono, prazo, registro) em arquivo versionado — nunca `skip` anônimo. `apply` em produção só por pipeline, com aprovação nominal (`references/chatops.md`).

## Evidência: `05b-veracode.md` e anexos
Contexto: o GATE 2 do `squad-pipeline` confere artefatos, não declarações.
- `.claude/pipeline/<slug>/05b-veracode.md` (+ `veredito.json`) é a evidência de SAST, gerada por `validacao-veracode` e anexada ao `06-review.md`.
  `achados_criticos > 0` bloqueia a transição para `commit` (`contracts/pipeline-state-machine.json`).
- Convenção desta reference: anexar ao lado `sbom.cdx.json`, `trivy.json`, `gitleaks.json`, `excecoes.json` e `gate-severidade.txt`. O gate SECURITY do
  `verificacao-loop` (0 Critical/High, 0 segredos, SBOM gerado) precisa desses arquivos para existir como prova.

## Oráculo — como provar que foi feito
- **Gate reprova CVE alta sintética:** fixture com `CVE-0000-0001` (fictício, CVSS 8.1) → `gate_severidade.py` sai `1`; com exceção válida sai `0`; vencida sai `1`; arquivo ausente sai `2`.
- **SBOM por build:** `jq -e '.bomFormat=="CycloneDX" and (.components|length>0)' target/bom.json` sai `0` e o arquivo está no artefato do run.
- **Scanner pega segredo sintético:** o bloco de teste acima imprime "OK" (gitleaks sai `1` com o segredo plantado).
- **Pinagem:** `! grep -rEn 'uses: +[^./ ][^ ]*@' .github/workflows | grep -vE '@[0-9a-f]{40}( |$)'` sai `0` (nenhuma Action fora de SHA).
- **Assinatura/proveniência no pré-deploy:** `cosign verify` (ou `gh attestation verify`) sai `0`; senão o deploy não inicia.
- **SAST:** `veredito.json` e `05b-veracode.md` existem para o commit; `BLOQUEADO` deixa o pipeline vermelho.

## Anti-padrões
- **Gate por opinião:** "parece seguro" sem score, regra ou exit code.
- **Exceção eterna:** supressão sem dono, prazo e registro (ou para CVE crítica).
- **Action por tag móvel:** `@v4`/`@main` aceitando código novo sem revisão.
- **SBOM de enfeite:** gerado uma vez, fora do build e fora do artefato.
- **Scan só noturno:** a CVE chega à produção antes de alguém vê-la.
- **Segredo "só no privado":** chave long-lived no repo, `.env` versionado ou `ARG` de Dockerfile.
- **Cleanser de fachada / baseline eterno:** armadilhas do SAST, descritas em `validacao-veracode`.
- **DAST em produção:** teste ativo fora de ambiente autorizado.

## Checklist de banco
- [ ] Código só vai ao Veracode com autorização explícita e no tenant do dono (V1 de `validacao-veracode`).
- [ ] Gate de severidade fail-closed; Crítica sem exceção; demais exceções com dono, prazo e registro.
- [ ] DAST e testes ativos somente em hml/sandbox, em janela de mudança e com ciência de Segurança.
- [ ] Segredos no cofre, rotação conforme política, CI com OIDC, nenhuma credencial em log.
- [ ] SBOM, relatórios de scan e assinatura retidos como trilha de auditoria e anexados ao GATE 2.
- [ ] Mudança de IaC em produção: plano revisado, `apply` aprovado nominalmente, aprovador ≠ solicitante.
