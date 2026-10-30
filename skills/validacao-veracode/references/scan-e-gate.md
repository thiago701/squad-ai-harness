# validacao-veracode · reference — Scan real, gate determinístico e integração ao pipeline

> Parte da skill `validacao-veracode`. Carregue sob demanda. Hub: `../SKILL.md`.
> YAML completo de CI/CodeBuild, credenciais HMAC e decisão de adoção ficam em
> `skills/engenheiro-seguranca/references/veracode.md` — aqui só o que a validação precisa.
> Fontes: docs.veracode.com `/r/Pipeline_Scan_parameters`, `/r/r_pipeline_scan_examples`,
> `/r/CLI_exit_codes`, `/r/veracode_static_scan`, `/r/c_appsec_policies`, `/r/c_findings_v2_examples`.

## 1. Três modos

| Modo | Pré-condição | O que roda | Vale como compliance? |
|---|---|---|---|
| **A — pré-scan** | nenhuma | `veracode_precheck.py` → `veracode_gate.py` | **Não** — antecipação heurística |
| **B — scan real** | credencial **e** autorização para enviar o código ao tenant certo | Pipeline Scan / `veracode static scan` → gate | Pipeline Scan: evidência de PR; Policy Scan: compliance |
| **C — só gate** | já existe `results.json` ou export da Findings API | `veracode_gate.py` | herda o valor da entrada |

A e B se combinam: o gate deduplica (mesmo CWE + arquivo + linha) e marca o achado do scan como
"antecipado pelo precheck" — é a medida de recall do pré-scan ao longo do tempo.

## 2. Comandos do scan real

```bash
# Java — PR gate sem build (contorna fat-jar shaded, PKG-01)
veracode package --java-source --output veracode-artifacts
veracode static scan veracode-artifacts/ --results-file results.json --baseline-file baseline.json

# Pipeline Scan clássico (artefato compilado com símbolos de debug)
java -jar pipeline-scan.jar --veracode_api_id "$VERACODE_API_ID" --veracode_api_key "$VERACODE_API_KEY" \
  --file target/app.jar --json_output_file results.json --baseline_file baseline.json --issue_details true

# Python/JS — empacotamento por fonte
veracode package --source . --output veracode-artifacts --trust
```

Parâmetros úteis do Pipeline Scan: `--fail_on_severity`, `--fail_on_cwe`, `--baseline_file`
(mostra só flaws novos), `--policy_name` (só políticas padrão da Veracode), `--policy_file`
(política local), `--timeout` (padrão e máximo 60 min), `--include` (módulos de 1º nível).

### Exit codes — por que o gate normaliza

| Ferramenta | Exit | Significado |
|---|---|---|
| `pipeline-scan.jar` | N | **número de flaws** que violam o corte (até 200) — não é um veredito |
| `veracode` CLI | 0 | sucesso |
| | 3 | `static scan`: a aplicação **não passou** na política |
| | 4–7 | `package`: falha ao gerar artefato (sem `.class`, build Maven falhou…) |
| | 1, 2, 125–130 | erro genérico, parser, memória, comando, argumento, interrupção |

Um `package` que falhou (4–7) e não gerou `results.json` **não pode** virar verde: sem entrada
válida o gate sai com **exit 2** (bloqueia). Quem decide o merge é o exit do `veracode_gate.py`.

## 3. Formatos que o gate entende

| Entrada | Detectada por | Campos lidos |
|---|---|---|
| Pipeline Scan / CLI `results.json` | `findings[]` | `cwe_id`, `severity` (0–5), `issue_type`/`title`, `files.source_file.{file,line,function_name,qualified_function_name}`, `flaw_match.*` (casamento de baseline), `scan_status` (≠ `SUCCESS` ⇒ fail-closed) |
| Findings REST API v2 (Policy/Sandbox/SCA) | `_embedded.findings[]` | `finding_details.{cwe.id, severity, file_path, file_line_number, procedure}`, `finding_status.{status, resolution, resolution_status, first_found_date}`, `violates_policy`, `scan_type`; em SCA, `component_filename` e `cve.name` |
| Pré-scan | `ferramenta: veracode_precheck` | `achados[]` canônico |

Export da Findings API (só flaws que violam a política, estáticos):
`GET https://api.veracode.com/appsec/v2/applications/{guid}/findings?scan_type=STATIC&violates_policy=TRUE`
(autenticação HMAC; salve a resposta JSON e passe ao gate).

> **Honestidade de schema:** os campos acima seguem a documentação pública e exemplos oficiais.
> Na primeira execução com um `results.json` real do seu tenant, confira que o gate leu o mesmo
> número de flaws que o resumo do scan — formato inesperado sai como **exit 2**, nunca como verde.

## 4. Baseline — dívida explícita, não silenciador

- Baseline = um `results.json` de um scan **aprovado** da branch principal (mesmo formato).
- Casamento: `flaw_match` (hashes de procedimento/protótipo/flaw/causa) quando existe; senão
  `CWE + arquivo + função/linha`. Mover o código de linha não "cria" flaw novo.
- 🔴 herdado ⇒ `APROVADO_COM_RESSALVAS` + **card de dívida com prazo** (SLA canônico da squad: Very High 24 h, High 7 dias,
  Medium 30 dias — `engenheiro-seguranca/references/secrets-cripto.md`). 🔴 novo ⇒ `BLOQUEADO`.
- Atualize a baseline só a partir da branch principal verde, nunca de dentro do PR que a usa.

### SLA de correção (todos os perfis; bloqueante no `bancario`)

- O gate calcula a idade do flaw a partir de `finding_status.first_found_date` (Findings API) e compara
  com o SLA: padrão Very High 1 d · High 7 d · Medium 30 d · Low 90 d; `--sla-dias "5=1,4=15,3=45"`
  aplica a política da instituição; `--hoje AAAA-MM-DD` deixa o cálculo reprodutível.
- 🔴 com SLA vencido: **BLOQUEADO** no perfil `bancario` (herdado não salva); ressalva nos demais.
- O `results.json` do Pipeline Scan não traz data — ali o herdado continua ressalva.

### Gate de release (`--release`)

Exige evidência do Policy Scan: um export da Findings API entre as entradas **ou**
`--status-politica Passed|Conditional Pass`. Sem isso: `BLOQUEADO` (fail-closed). No perfil
`bancario`, sem nenhum scan real o gate anota "compliance não atestada" mesmo fora do release.

## 5. Políticas, status e Veracode Levels

- Status de política: **Passed** · **Did Not Pass** (falhou scan exigido, nível-alvo ou estourou
  grace period) · **Conditional Pass** (flaws dentro do grace period) · **Not Assessed**.
  Passe ao gate com `--status-politica "<status>"`: `Did Not Pass` ⇒ BLOQUEADO; `Conditional Pass` ⇒ ressalva.
- **Veracode Levels** VL1 (teste automatizado) … VL5 (automatizado + manual, sem flaws
  significativos), com variantes `+SCA`; cada nível exige score mínimo e proíbe severidades.
- Perfil `maximo` desta skill ≈ política *Veracode Recommended Medium* + CWEs críticos sempre
  bloqueantes; perfil `padrao` ≈ *Veracode Recommended High*.

## 6. Ligando ao pipeline

### Local (pre-commit, sem credencial)

```yaml
  - repo: local
    hooks:
      - id: veracode-precheck
        name: Pré-scan Veracode (perfil máximo, só arquivos alterados)
        entry: python skills/validacao-veracode/scripts/veracode_precheck.py . --desde HEAD --falhar
        language: system
        pass_filenames: false
```

### CI (GitHub Actions) — Modo A sempre, Modo B quando há segredo

```yaml
      - name: Pré-scan Veracode
        run: python skills/validacao-veracode/scripts/veracode_precheck.py . --desde origin/${{ github.base_ref }} --json pre.json --md pre.md
      - name: Pipeline Scan
        if: ${{ env.VERACODE_API_ID != '' }}
        run: veracode static scan veracode-artifacts/ --results-file results.json --baseline-file baseline.json || true
      - name: Gate Veracode (decide o merge)
        run: |
          ENTRADAS="pre.json"; [ -f results.json ] && ENTRADAS="$ENTRADAS results.json"
          python skills/validacao-veracode/scripts/veracode_gate.py $ENTRADAS --perfil maximo \
            $( [ -f baseline.json ] && echo --baseline baseline.json ) --md veredito.md --json veredito.json
```

O `|| true` no scan é deliberado: o exit do scan não é veredito (§2); o **gate** decide, e sem
`results.json` válido no Modo B ele não tem como aprovar o que não viu.

### Squad pipeline

`squad-pipeline` → após TDD e `engenheiro-seguranca` (G7) → **V3–V5 desta skill** → artefato
`.claude/pipeline/<slug>/05b-veracode.md` → `tech-lead-review` (lente `rev-veracode`) → GATE 2.

## 7. Calibração medida (2026-10-02)

| Medida | Resultado |
|---|---|
| Testes (`tests/test_validacao_veracode.py`) | 140 casos verdes — toda regra com caso vulnerável provado, 34 casos de código seguro equivalente, gate, CLI e robustez (console cp1252, poda de `node_modules`, git sem lock) |
| Ampliação de 04/10 (SQLi + perfil bancário) | 298 casos verdes (107 regras); amostra de ~1.066 arquivos reais: 4 classes de falso-positivo corrigidas com teste de regressão (`or '...'` em f-string lido como SQL, "valor" genérico, `GenerateSecret: false` lido como credencial, métrica `base_valor`); 2 residuais conhecidos fora do domínio financeiro |
| Amostra real do repo (`app/`, `scripts/`, `labs/`) | ~920 arquivos |
| Falso-positivo encontrado | 1 (P-LOG-01 em log de boot do `ai-photobooth`) → regra ajustada para exigir indício de entrada + teste de regressão |
| Achados verdadeiros | `maven-shade-plugin` nas Lambdas Java (PKG-01), MD5/SHA-1 para IDs, `eval` em `scripts/saga/patchboard.py`, vulnerabilidades plantadas dos datasets de review |
| Recall contra o Veracode real | **não medido** — exige `results.json` de um tenant; o gate já registra "antecipado pelo precheck" para medir quando houver |
