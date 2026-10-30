# Changelog

Todas as mudanças notáveis do SquadAI Harness são documentadas aqui.
O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

## [0.8.0] — 2026-10-29 — SquadAI Harness v0.8.0

> Reengenharia arquitetural do plano de controle e cognição para **Golang 1.24.3** (`CGO_ENABLED=0`, zero dependências externas), evolução do cérebro cognitivo com **Software Engineering Knowledge Graph (SEKG) + GraphRAG (Local, Global e DRIFT Search)**, e formalização da identidade oficial **SquadAI Harness v0.8.0** (`squad-ai-harness`). ADRs 020 a 027 em [`docs/adrs/ADR-020-arquitetura-golang-sekg-squadai-harness-v080.md`](docs/adrs/ADR-020-arquitetura-golang-sekg-squadai-harness-v080.md) e notas da release em [`docs/releases/v0.8.0.md`](docs/releases/v0.8.0.md).

### Adicionado
- **Runtime Nativo Unificado em Go 1.24.3 (`cmd/squad-harness`, `internal/*`, `pkg/contracts`):**
  - Binário estático único (`squad-harness` / `squad-harness.exe`) com teto de memória `GOMEMLIMIT=256MiB` (`heap_alloc_mb = 4,53 MB` medido na estação).
  - **Supervisão Windows Job Objects (`internal/runtime/jobobject`):** integração direta com `kernel32.dll` (`CreateJobObjectW`, `SetInformationJobObject` com `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` + `JOB_OBJECT_LIMIT_JOB_MEMORY`, `AssignProcessToJobObject`, `TerminateJobObject`) e leitura nativa de memória física via `GlobalMemoryStatusEx`, erradicando árvores de processos órfãos no Windows 11.
  - **Guarda de Sistema de Arquivos em User-Space (`internal/security/fsguard`):** confinamento estrito contra *path traversal*, ADS (`:`), nomes de dispositivos Win32 (`CON`, `NUL`, `COM1`..`LPT9`) e escape de symlinks (`filepath.EvalSymlinks`), mitigando `GO-2026-4970` e `GO-2026-4602` na stdlib do Go 1.24.3.
  - **Hooks Hot-Path Sub-Milissegundo (`internal/hooks`):** `PreToolUse`, `PostToolUse` e `StopHook` em Go com leitura não-bloqueante de `stdin` (`ModeCharDevice` + timeout de 100 ms) e *tail streaming* de transcript (latência medida na estação: **0,67 ms** vs 87–7.400 ms em Python).
  - **Coletor Único de Estado Git (`internal/runtime/gitstate`):** consolidação dos 8 wrappers Git duplicados em um único coletor `Singleflight` baseado em `git status --porcelain=v2 --branch`.
  - **Motor de Execução em DAG (`internal/dag`) e Catálogo em Passagem Única (`internal/catalog`):** carregamento concorrente e validação de frontmatter, UTF-8, Linha de Defesa de Prompt (6 bullets) e drift de registry das **106 skills canônicas** em **41,2 ms** de validação (**177 ms** de carga fria).
  - **Motor JEV de 25 Especialistas em Goroutines + Tribunal `Critic -> Judge` (`internal/jev`):** fan-out paralelo completo com arbitragem `P1 > P2 > P3` e cláusula pétrea de segurança em **1,12 ms** (**0,51 ms** aquecido).
  - **Analisador Preventivo Sonar-First (`internal/sonar`), Linters AWS ASL/VTL (`internal/aws`) e Decisão Central `DecidirEntrega` (`internal/gates`):** unificação nativa dos 4 gates de entrega (`environment-infrastructure-gate`, `database-schema-gate`, `configuration-compatibility-review`, `interoperability-contract-gate`).
- **Cérebro Cognitivo com SEKG + GraphRAG (`internal/cognitive/*`):**
  - **Software Engineering Knowledge Graph (`internal/cognitive/sekg`):** grafo CSR compacto em memória (`uint32`, 199 nós, 192 arestas no repositório), indexador determinístico (US$ 0 de LLM), algoritmo de **Leiden** em 3 fases (movimentação local gulosa, refinamento conectado e agregação hierárquica em **35 comunidades**), analisador de raio de impacto 1-hop/2-hop e persistência atômica em `.squad-harness/sekg.db` (**22,6 ms** de indexação).
  - **Motores GraphRAG (`internal/cognitive/graphrag`):** implementação nativa de **Local Search** (entidades + vizinhança CSR 1-hop/2-hop em **1,99 ms**), **Global Search** (Map-Reduce sobre relatórios de comunidades de Leiden em **< 1 ms**) e **DRIFT Search** (*Primer* global + *Follow-Up* local iterativo em **24,05 ms**).
  - **Memória Multicamada `M0–M3` com Quarentena Anti-Alucinação (`internal/cognitive/memory`):** separação estrita entre `HYPOTHESIS`, `OBSERVED` e `VERIFIED`, exigindo evidência de oráculo (`V2+`) e 0 bloqueios de segurança para promoção ao conhecimento canônico.
  - **Roteador Híbrido BM25 (`internal/cognitive/router`) e `CognitiveHarness` de 10 Estágios (`internal/cognitive/harness`):** internação de tokens com `unique.Make[string]` (Go 1.24) e execução completa dos 10 estágios da Camada 0 em **7,89 ms** (com SEKG em cache).
- **Orquestração de Recursos Computacionais e Evolução Contínua:**
  - **`CognitiveComputeRouter` (`internal/compute`):** roteamento explícito `C0 (Go Determinístico, 0 tokens) -> C1 (NPU/GPU/CPU Assist) -> C2 (LLM Especialista)` com governança de VRAM de 3 inquilinos e disjuntor em 3 camadas.
  - **Scheduler Inteligente de 8 Dimensões + IMO (`internal/scheduler`):** controle de admissão de memória (`Livre - Reserva >= Custo_EWMA`, $\alpha=0,30$), anti-starvation e isolamento `--strict-mcp-config`.
  - **Servidor MCP JSON-RPC 2.0 Unificado (`internal/mcp`):** `squad-harness mcp` via stdio expondo `squad_preflight`, `squad_sekg_query`, `squad_sekg_impact`, `squad_jev_tribunal`, `squad_gate_status` e `squad_compute_status`.
  - **Motor `Cultivator` (`internal/cognitive/cultivator`):** promoção controlada de melhorias de skills com oráculo anti-regressão *held-out*.
- **Correção imediata de processos órfãos no Nightly Runner:** `scheduler/scripts/squad-nightly-runner.ps1` atualizado na linha 307 para matar a árvore inteira (`taskkill /PID $proc.Id /T /F`) em caso de timeout.

### Adicionado
- **Clean code verificável nas skills de Lambda e nos pipelines** (28/10/2026, noite) — uma régua só, a do Sonar-First (cognitiva ≤ 15 = S3776, ciclomática ≤ 15 = S1541, parâmetros ≤ 7 = S107, **zero supressão inline**), agora medida também pelo linter da stack:
  - **`aws-lambda-go` 1.1.0** — padrão **Go 1.24** por decisão do dono (`go 1.24.3` + `toolchain go1.24.13`; `aws-lambda-go` v1.54.0, pois a v1.55 exige Go 1.26), com alerta de fim de suporte e `govulncheck` (28 vulnerabilidades alcançáveis com 1.24.13 e 44 com 1.24.3 em 28/10/2026 — o número só cresce; o gate não é silenciado: exige aceite de risco ou upgrade; `os.Root` não confina no 1.24 — GO-2026-4970 —, então a skill valida o nome antes; `GOTOOLCHAIN=go1.24.13` fixo, porque `toolchain` é só um mínimo); recursos do 1.24 testados (diretiva `tool`, `os.Root`, `omitzero`, `b.Loop`, `synctest` experimental, `GOFIPS140`); `references/clean-code-go.md` com antes→depois (exemplo ruim: 17 achados de 13 linters; lab: 0, depois de corrigir 14 achados reais — `%w`, `nilerr`, `errcheck`).
  - **`golang-pro` 2.1.0** — gate canônico `references/clean-code-e-lint.md` (`.golangci.yml` do golangci-lint v2, validado no v2.8.0 e no v2.15.0); saiu a permissão de `//nolint` com justificativa.
  - **`aws-lambda-python` 1.1.0** — `references/clean-code-python.md` e gate `ruff` (C90/PL/FBT/ERA/TRY/T20…) + `complexipy` 8.3.0; zero `# noqa`/`# type: ignore`; `mypy --strict` também nos testes; exemplo ruim (cognitiva 32, 13 achados) × bom (0); 2 evals novos.
  - **`tech-lead-review` 1.6** — lente `rev-clean` (PASSO 1e, laudo `05d-clean.md`, checklist P1.CLEAN) e regra estrutural × comportamental (refatoração em commit/PR próprio antes da regra nova; heurística de tamanho do Google eng-practices); `references/lente-clean-code.md`.
  - **`squad-pipeline` 1.6.0** — config do linter no scaffold, estrutural antes de comportamental na Fase 5, validação incremental e `05d-clean.md` antes do GATE 2. **`verificacao-loop` 2.2.0** — STATIC mede a régua (achado = MAJOR); linhas de clean code para Go e Python em `comandos-por-stack.md`.
  - Gate de supressão inline cobre as formas que calam a ferramenta sem aparecer como `noqa`/`nolint` (`# ruff: noqa`, `# mypy: ignore-errors`, `# complexipy: ignore`, `#nosec`, `lint:ignore`); comando `rc=0; grep … || rc=$?; test "$rc" -eq 1` — `! grep` dava verde com pasta ausente e `grep …; test $? -eq 1` morre com `bash -e`. Teto afrouxado sem ADR = BLOCKER no `verificacao-loop` / 🔴 no review.
- **Skill `aws-lambda-python` 1.0.0** (28/10/2026) — Lambda em Python 3.14/3.13 (arm64) de produção: handler fino + init reaproveitável (`botocore.Config` com timeouts), SQS com falha parcial em stdlib e com Powertools 3.38 (padrão e FIFO; documentado que o `BatchProcessor` **levanta** quando todas falham e com `Records` vazio, e que `raise_on_no_idempotency_key` é `False` por padrão), Parser/Idempotency (com `payload_validation_jmespath` e teste que prova a ausência do 2º efeito), HTTP API v2 com validação Pydantic (422 sem ecoar a entrada), pacote com `uv` e wheels `manylinux2014_aarch64` (tamanhos e tempo de import medidos, indicativos), SnapStart (ganchos `snapshot_restore_py`, unicidade, cobrança para Python), Managed Instances (concorrência por processos, memória × processos), durable functions (SDK 3.0 + runner local), streaming (não nativo em Python), migração de `python3.10` (descontinuado em 31/10/2026) e `3.11` (AL2). SAM validado com `cfn-lint` 1.59.0 e transformado com `aws-sam-translator` 1.115.0 (achado: o evento SQS anexa `AWSLambdaSQSQueueExecutionRole`, ampla); teste de invariantes do template para o que o `cfn-lint` não pegou (runtime inexistente, `MaximumConcurrency` fora da faixa, `FunctionResponseTypes` inválido); contrato com o runtime real (`awslambdaric` 4.2.3) contra o Runtime API simulado. Código das references gerado dos arquivos testados (20 testes `pytest`, `ruff` e `mypy --strict` limpos, Python 3.14.6). 9 evals.
- **Skill `aws-lambda-go` 1.0.0** (28/10/2026) — Lambda em Go (1.27.3, `aws-lambda-go` v1.55.1) sobre `provided.al2023`, separada da `aws-lambda-go-rust` (decisão do dono: separar Go e Rust): SQS (padrão/FIFO), Kinesis/DynamoDB Streams ordenados, S3, EventBridge, HTTP v2, streaming por Function URL, margem de prazo antes do deadline (o `ctx` do aws-lambda-go expira no deadline), SnapStart só via imagem de contêiner, durable functions (SDK Go v1.0.0, ressalvado), build no Windows (`build-lambda-zip`); SAM validado com `cfn-lint` 1.59.0 e 8 `bootstrap` testados contra o Runtime API simulado. 9 evals.
- **`aws-lambda-go-rust` 1.1.0** passa a cobrir Rust + comparação Go × Rust (`references/go-lambda.md` vira ponteiro; 7 evals); ponteiros de roteamento atualizados em `golang-pro` 2.0.1, `go-cloud-services` 1.0.1 e `python-pro` 1.0.1; `manifest.json`: perfil novo `backend-python`, `aws-lambda-go` no `backend-go` e as duas skills novas no `completo`.
- **Skill `logs-observabilidade` 1.0.0** (28/10/2026) — doutrina de escrita de logs da Squad + lente determinística de review (`rev-logs`):
  - Hub + 7 references com fontes oficiais: logs por eventos (catálogo `dominio.entidade.acao`, níveis semânticos, linha canônica, amostragem/buffering), correlação (`trace_id`/`span_id`/`correlation_id`, Spring Boot 4 + Micrometer Tracing, MDC × Virtual Threads × `ScopedValue`, OTel appender, Python `contextvars`), CloudWatch (Powertools v2 Logging/Metrics, ALC `LogFormat=JSON`, retenção/classe/custo, data protection policy com `CpfCode-BR`/`Cnpj-BR`, Logs Insights de bolso), Datadog (atributos reservados/standard, Unified Service Tagging, `dd.trace_id` 128-bit, Sensitive Data Scanner, Logging without Limits), mascaramento canônico com antes → depois (`***.982.247-**`, `**** **** **** 1111`, `[TOKEN:****6789]`) em três camadas, e filtros que **barram** segredos (OWASP/CWE-532/CWE-117, configurações perigosas, famílias do gitleaks).
  - `scripts/lint_logs.py` (stdlib pura; `verificar | mascarar | selftest | catalogo`): 20 regras LOG-xx em dois perfis (`segredos` para push, `completo` para review), detectores validados por dígito verificador/Luhn/prefixo de bandeira (zero falso positivo em 1.594 arquivos do repo), trecho sempre mascarado no relatório, supressão só com motivo (`// log-ok: ...`), códigos 0/1/2 como o `contrato-reverso`.
  - `templates/` reutilizáveis: Java (`Mascara`, `FiltroSegredos` TurboFilter, `MascaraJsonDecorator` para logstash-logback-encoder, `logback-spring.xml`), Python (`logging_json.py` com JSON + contextvars + filtro de bloqueio + máscara), CloudWatch `data-protection-policy.json`, Datadog `sensitive-data-scanner.tf.example`; `exemplos/ruim` × `exemplos/bom` (selftest da lente).
  - `tests/test_logs_observabilidade.py` (78 testes: formatos canônicos são contrato).
- **Pipeline de code review com lente de logs:** `tech-lead-review` 1.4 (PASSO 1c lente `rev-logs`, checklist **P1.LOG** no fluxo de 5 passos, heurísticas 🔴/🟡 de logs, lente no modo multi-dimensão); `squad-pipeline` 1.5.0 (gatilho automático **logs** → `05c-logs.md`; 🔴 trava o GATE 2); `ops/run.py` targets `log-lint` (selftest + perfil `segredos`, dentro do composto `gate`) e `log-lint-review`; links cruzados em `engenheiro-seguranca`, `java-coding-standards`, `dd-logs`, `datadog-lambda-java`.
- Proposta para `quality/quality-gates.md` (arquivo protegido — PR humano com ADR-018): `governance/freeze-patches/quality-gates-logs.patch.md` + `docs/adrs/ADR-018-lente-logs-observabilidade.md`.
- `.gitleaks.toml`: fixtures sintéticas da lente alistadas por caminho exato (`skills/logs-observabilidade/exemplos/ruim/*`, `tests/test_logs_observabilidade.py`).
- **Skill `python-memoria` 1.0.0** (28/10/2026) — otimização de memória RAM em Python como habilidade reutilizável + lente determinística de review (`rev-mem`):
  - Hub + 7 references com fontes oficiais: runtime/alocador (custo por objeto, pymalloc/arenas, "RSS não volta", GC gerações/`freeze`/incremental 3.14, free-threading/JIT, slots/`msgspec`/`array`/`memoryview`), padrões de código com antes → depois (iterar vs materializar, acumulação, caches com limite, retenção de exceções, I/O em blocos), dados (pandas dtypes/usecols/chunksize/CoW/pyarrow, polars lazy, numpy views/memmap, arrow/parquet, DuckDB), concorrência/processos (backpressure, fork+COW+`gc.freeze`, `shared_memory`, reciclagem gunicorn/celery), medição/profiling (tracemalloc vs RSS/HWM, memray, scalene, pympler, objgraph, roteiro de vazamento, benchmark reproduzível), produção (Lambda MemorySize/Power Tuning/SnapStart, containers cgroup/OOMKilled/`MALLOC_ARENA_MAX`/jemalloc, import time, modelos e agentes de IA).
  - `scripts/lint_memoria.py` (AST, stdlib; `verificar | medir | selftest | catalogo`): 18 regras mecânicas MEM-xx + 5 de leitura, perfis `review` (🟡+🔵) e `observacional` (só 🟡, SLI), densidade achados/1k linhas, supressão `# mem-ok: <motivo>`, testes fora por padrão; `scripts/memoria/orcamento.py`: orçamento de memória em teste (`with orcamento(max_pico_mb=…)`, decorador, `medir(fn, repeticoes)` para vazamento, RSS/HWM por SO via stdlib — Linux `/proc`, macOS `ru_maxrss`, Windows psapi/ctypes; `heap=False` para número de produção); `templates/pytest/conftest_memoria.py` (fixture + marker `@pytest.mark.memoria`); `exemplos/ruim` × `exemplos/bom`; `tests/test_python_memoria.py` (32 testes).
  - Diagnóstico da própria Squad (caso de validação): 715 arquivos / 117k linhas → 13 🟡 e 105 🔵 (1,0 achado/1k linhas; perfil observacional 0,11/1k) — baseline do SLI em `ops/logs/python-memoria`.
- **Auditoria de memória RAM da própria Squad AI (28/10/2026, missão "Intelligent Memory Optimization") — só auditoria, benchmark e plano; nenhuma mudança de produção:** relatório `docs/relatorios/memoria/2026-10-28-auditoria-memoria-squad-ai.md` (árvore de processos com os 11 campos, mapa de consumo medido, causas-raiz, alternativas com protótipo, arquitetura-alvo IMO, metas recalibradas, plano em 5 fases com aceite/rollback, roadmap, 6 diagramas Mermaid) + `docs/adrs/ADR-019-intelligent-memory-orchestrator.md` (admissão por memória como módulo JEV; sem daemon). Achados centrais (medidos em container Linux como proxy): processos Python da Squad são muitos, pequenos e curtos (hook de escrita 23–34 MB / 87 ms / 6 execve; 0,75 interpretador por chamada de ferramenta); memória ociosa ≈ 0 (MCP `squad-context` 28 MB estável); a suíte `pytest` fica em ~240 MB por 4,3 min com pico isolado de 526 MB causado por **um teste** (`test_zip_bomba_agregada_detectada`, 300 MB de bytes) e cria 13 261 processos por rodada (git ×10 948), rodando 3× por `gate`; o Batman lança até 3 `claude -p` em paralelo sem olhar RAM (`decidir_workers` = CPU e demanda). Instrumento novo na skill `python-memoria` (**1.1.0**): `scripts/memoria/arvore.py` + subcomando `lint_memoria.py arvore -- <cmd>` (RSS/USS/PSS por processo, pico da árvore em RSS e PSS, simultâneos, série temporal, `ru_maxrss`, `--execs` via strace); `ops/bench_memoria.py` (22 cenários reais da Squad mapeados nos 8 da missão, 3 repetições, mediana + faixa, JSON/Markdown locais) e target observacional `ops/run.py mem-bench`; +10 testes (`tests/test_python_memoria.py`, 43). Pendências do dono descobertas: `generate_copilot.py --check` desatualizado no `master` limpo (gate para no 2º passo), MCPs `cultivator`/`dora` quebrados ainda em `.mcp.json`, decisão sobre o hook `graphify` (caminho protegido).
- **Auditoria de memória — Fase 2 executada (28/10/2026, noite, a pedido do mantenedor após o GATE 2):** `ops/processos.py` (`matar_arvore`, `esperar_ou_matar`, `popen_arvore`) e **timeout passa a matar a árvore** no Batman (`agenda.executar_llm`, `portfolio.rodar_det`) e no `ops/run.py` em todo SO (CR-8; antes `proc.kill()` só na raiz — 3 testes provam o neto morto); **workers headless só com os MCPs do projeto** (`agenda.mcp_por_escopo`: `--strict-mcp-config --mcp-config scheduler/batman-mcp.json` › `.mcp.json` › nenhum; rollback `SQUAD_BATMAN_MCP=todos`; container: 7 → 4 processos, 14 → 10 execve; estação ESTIMADO 0,7 → ≈ 0,35 GB por worker); **hook de escrita enxuto** (`hooks/scan_secrets.py` lê o payload do stdin em thread com prazo, linta só o arquivo escrito, raiz do repo sem `git`: 6 → 2 execve, 0,8 → 0,12 s; rollback `SQUAD_HOOK_MODO=completo`); **hook Stop em streaming** (`scripts/extract_telemetry.py`: 142 → 22 MB com transcript de 21 MB); **teste dono do pico** (`test_zip_bomba_agregada_detectada`: +240 → 0 MB de HWM); **1 pytest por `gate`** (`ops/run.py`: 29 → 27 passos, 3 → 1 interpretador; targets avulsos mantêm); `hooks/graphify_guard.py` condicionado a CLI + `graphify-out/graph.json` (1 execve, 14 MB, 0,06 s; rollback `SQUAD_GRAPHIFY_GUARD=sempre`) + 2 patches para caminhos protegidos em `governance/freeze-patches/` (`settings-hooks-graphify`, `mcp-json-remover-quebrados`) para PR humano; **suíte completa medida após a Fase 2: pico 526 → 382 MB (−27 %), média 227 / p90 281, 0 órfão**; 2ª revisão independente (Anexo E: 4 IMP + 8 MENOR, todos tratados — o piso da admissão foi removido por violar a propriedade "nunca admite se livre − reserva < custo"). Pendentes da Fase 2: 2.5 (testes sem `git` real), 2.6 (harness em 1 processo), 2.7 (`slots`). +12 testes (`test_ops_processos.py`, `test_hooks_graphify_guard.py`, BA10b/BA10c, bateria com timeout, hook enxuto ×5, gate com 1 pytest).
- **Auditoria de memória — 2ª rodada (28/10/2026, tarde): baseline real da estação + revisão independente.** Bench rodado na estação pessoal (Windows 11, 8 CPU, 16 GB; `ops/run.py mem-bench` + `mem-bench-estacao --repo-java app/calendario-lambda`) e os "NÃO MEDIDOS" fechados: **cada worker `claude -p` do Batman custa 0,7 GB e 17–18 processos na estação (15 s para responder 1 palavra) — metade são 3 MCPs AWS de escopo de usuário via `uvx` (372 MB + 99 MB de `conhost` + 8 s) carregados em todo job, enquanto o `squad-context` do projeto nem sobe no headless** (CR-7 → `--strict-mcp-config --mcp-config .mcp.json`, −50 % de RAM por worker); Linux: 294 MB (Node 261), 3 workers 886 RSS / 598 PSS; **hook de escrita 7,4 s por `Edit` na estação** (×80 o Linux: `git diff HEAD` 8 s a frio + lint de 87 arquivos não rastreados — origem do timeout de 20 s); `mvnw test` 745 MB / 78 s; `graphify` fora do PATH do PowerShell; Windows = RSS +10–30 % e duração ×2–×9. Revisão independente (subagente com contexto limpo, 23 achados, Anexo D do relatório) derrubou 2 pontos: **hipótese de órfãos reaberta** — Batman (`agenda.py:532`, `portfolio.py:448`) e `ops/run.py` no Windows matam só a raiz no timeout (CR-8, ≈ 0,45 GB de órfãos por job estourado) — e geradores de dados não versionados (agora em `ops/bench_memoria_extras/`: plugin `rss_por_teste.py`, `mcp_longrun.py`, `sim_despachante.py`); hook Stop medido no caminho real (42 MB → 142 MB com transcript de 21 MB, CR-9); regra de admissão do IMO corrigida (piso só com 0 workers vivos, `espera_max`/aging anti-starvation, `--resume` fora do ramo "não cabe"); "suíte roda 3×" → 1 suíte + 2 subconjuntos; CR-1 reclassificada (ausência e magnitude comprovadas; efeito OOM = hipótese a confirmar pelo ledger); metas recalibradas com número da estação. Instrumento (`python-memoria` **1.2.0**): `--stdin` (payload real de hook), `matar_arvore` no timeout (psutil/`killpg`/`taskkill /T`), **varredura de órfãos por sessão após a saída da raiz** (`orfaos_apos_saida`), média/p50/p90 sobre todas as amostras, reamostragem sem perder o último ponto, fd do strace fechado, `::inconclusivo::` no Windows sem psutil; bench: 8 cenários `--estacao` (graphify com payload, `claude -p` ×1/+Read/×3/job de review, `mvn`, `uv`), `pytest-tech-debt`/`pytest-registry` alinhados com o gate, target `mem-bench-estacao`; `hooks/graphify_guard.py` (achado na estação) versionado; +5 testes (48).
- **`python-memoria` 1.0.1 → 1.1.0 — pesquisa incorporada (28/10/2026):** relatório do agente de pesquisa gravado como procedência em `docs/relatorios/pesquisa-memoria-python-2026-10-28.md` (✅ verificado / 📏 medido / ⛔ não verificado; só o verificado entrou). Correções e números nas references: **GC incremental do 3.14 revertido no 3.14.5** (gh-142516; regra de leitura MEM-22: serviço longo ≥ 3.14.5 ou 3.13.x), thresholds do GC (700→2000 no 3.13), `forkserver` padrão em POSIX no 3.14, pandas 3.0 (CoW padrão, `str` Arrow), polars `streaming=True` removido em 1.31 / 2.0 com streaming padrão, DuckDB `memory_limit` 80 % da RAM, glibc `M_MMAP_THRESHOLD` dinâmico até 32 MiB + caso `MALLOC_*_THRESHOLD_`, free-threading (`None` 32 B, QSBR, `MIMALLOC_PURGE_DELAY`), JIT +10-20 %, PEP 810 `lazy import` (3.15), SnapStart Python (hooks, unicidade pós-restore), Lambda 1 769 MB = 1 vCPU, OOMKilled 137/`memory.oom.group`, quantização de embeddings e bytes/vetor do FAISS, benchmark msgspec (JSON 77 MiB: 68 vs 295 vs 406 MiB; `Struct(gc=False)` 105 vs 212 MiB), custo por objeto medido (`slots` −30 a −60 %); `memory_profiler` marcado como não mantido; avaliação das 4 skills de performance Python do hub (nenhuma madura em memória) em `references/medicao-profiling.md` §5.
- **Review e shift-left de memória:** `rules/python/memoria.md` (invariante always-on do pack python) + ponteiro em `rules/python/idiomas.md`; bloco "Memória RAM ao escrever código" no hub do `python-pro`; `tech-lead-review` 1.5 (PASSO 1d lente `rev-mem`, checklist **P2.MEM**, heurística 🟡, reference); `ops/run.py` targets `mem-lint` (selftest + observacional, dentro do `gate-full`, nunca bloqueia) e `mem-lint-review`; proposta para o G8 da régua protegida em `governance/freeze-patches/quality-gates-memoria.patch.md`.
- **Correção (logs):** as fixtures de artefato de log da `logs-observabilidade` (`*.log`) eram ignoradas pelo `.gitignore` e não entraram no commit — selftest do `log-lint` falhava em clone limpo; renomeadas para `app-2026-10-27.log.txt` (ruim) e `app-2026-10-27.jsonl` (bom), allowlist do gitleaks ajustada. O bloco "Logs ao escrever código" de 6 hubs de stack (`quarkus-java-aot`, `python-pro`, `golang-pro`, `rust-pro`, `typescript-pro`, `nodejs-pro`) foi movido para o fim do hub (estava antes da Linha de Defesa).
- **Shift-left de logs (código já nasce certo, 28/10/2026):** `rules/comum/logs.md` (invariante always-on do pack comum); bloco "Logs ao escrever código" nos hubs de 10 skills de stack (`java25-spring-boot`, `java-pro`, `spring-modern-expert`, `aws-lambda-java25-aot`, `quarkus-java-aot`, `python-pro`, `golang-pro`, `rust-pro`, `typescript-pro`, `nodejs-pro`); `squad-pipeline` 1.5.1 (Fase 4 copia templates + catálogo de eventos, Fase 5 teste antes → depois, validação incremental por arquivo); hook `PostToolUse` `hooks/scan_secrets.py` roda a lente `segredos` em arquivos alterados/novos no instante da escrita (fail-open; +4 testes); `AGENTS.md` §5 e `rules/comum/seguranca.md` apontam para a doutrina.

## [0.7.0] — 2026-10-20

### Adicionado
- **Prontidão Corporativa & Bancária (Enterprise Ready):**
  - Script de bootstrap corporativo automatizado [`scripts/setup-empresa.ps1`](scripts/setup-empresa.ps1) (Windows 11 PowerShell-first) e [`scripts/setup-empresa.sh`](scripts/setup-empresa.sh) (Linux/macOS/WSL) para clone e onboarding em 1 comando.
  - Template de ambiente seguro [`.env.example`](.env.example) com isolamento de credenciais, suporte a proxy corporativo (Zscaler, Fortinet, BlueCoat) e certificados SSL internos (CA bundle).
  - Guia completo de homologação e onboarding corporativo em [`docs/GUIA_CLONE_EMPRESA.md`](docs/GUIA_CLONE_EMPRESA.md) em conformidade com **BACEN Res. 4.893**, **LGPD** e **PCI-DSS v4.0**.
  - Dependências de desenvolvimento e testes organizadas e delimitadas em [`requirements-dev.txt`](requirements-dev.txt), preservando a execução do ecossistema central em **Python 3.13 stdlib pura** (zero supply chain).
- **Usabilidade & Heurísticas de UX de Classe Mundial:**
  - Promoção da skill [`especialista-frontend`](skills/especialista-frontend/SKILL.md) para a versão **1.2.0**.
  - Absorção das **10 Heurísticas de Nielsen** adaptadas a SPAs modernas e reatividade por Signals, Leis de UX (Fitts, Hick, Miller, Jakob, Postel, Pico-Fim) e Teoria da Carga Cognitiva de Sweller em [`skills/especialista-frontend/references/usabilidade-heuristicas-ergonomia.md`](skills/especialista-frontend/references/usabilidade-heuristicas-ergonomia.md).
  - Princípios da Gestalt em UI e os 10 mandamentos do bom design de Dieter Rams (*Menos, porém melhor*) em [`skills/especialista-frontend/references/ergonomia-minimalismo-ux.md`](skills/especialista-frontend/references/ergonomia-minimalismo-ux.md).
- **Acessibilidade Digital Universal & Inclusão PcD (LBI & WCAG 2.2 AA/AAA):**
  - Engenharia inclusiva completa para Pessoas com Deficiência (PcD) e tecnologias assistivas: suporte a leitores de tela (NVDA, VoiceOver, JAWS, TalkBack), acionadores/switches para deficiência motora, zoom de até 400% sem scroll horizontal (Reflow WCAG 1.4.10), canal duplo (cor + ícone + texto) contra daltonismo, e respeito estrito a `prefers-reduced-motion`.
  - Conformidade com a **Lei Brasileira de Inclusão da Pessoa com Deficiência (LBI - Lei nº 13.146/2015, Art. 63)** e eMAG em [`skills/especialista-frontend/references/acessibilidade-pcd-tecnologias-assistivas.md`](skills/especialista-frontend/references/acessibilidade-pcd-tecnologias-assistivas.md).
  - Guia técnico de novos critérios do WCAG 2.2 (Focus Appearance, Target Size 24x24px, Redundant Entry) e testes automatizados com `@axe-core/playwright` em [`skills/especialista-frontend/references/acessibilidade-wcag22-a11y.md`](skills/especialista-frontend/references/acessibilidade-wcag22-a11y.md).
- **Style Guide & Design Tokens (Padrão W3C DTCG):**
  - Arquitetura de tokens de design em 3 camadas (primitivos, semânticos, componentes), escala de espaçamento modular 8pt, tipografia fluida com `clamp()` e os 7 estados canônicos de componentes interativos em [`skills/especialista-frontend/references/style-guide-design-system.md`](skills/especialista-frontend/references/style-guide-design-system.md).
- **UX Writing Construtivo, Gestão de Erros & Empty States:**
  - Tríade de mensagens de erro (*O que aconteceu* + *Por que* + *Como resolver*), empty states acionáveis e skeletons com efeito shimmer que reduzem a latência percebida em 20% em [`skills/especialista-frontend/references/ux-writing-empty-states.md`](skills/especialista-frontend/references/ux-writing-empty-states.md).
- **Notas da release:** [`docs/releases/v0.7.0.md`](docs/releases/v0.7.0.md).
- **Rotina diária instala nas ferramentas agênticas do home** (18/10/2026): a rotina `sync-claude` passou a rodar `install-squad-ai.py instalar-todos --destinos claude,codex,gemini --so-detectados --quiet`.
- **Testes na AWS — 5 skills novas** (17/10/2026, noite): `estrategia-testes-aws`, `testes-carga-desempenho-aws`, `testes-resiliencia-caos-aws`, `testes-seguranca-aws` e `testes-infra-iac-aws`.
- **`contrato-reverso` 1.1.0** (17/10/2026): testes reversos dirigidos pelo consumidor para projetos novos com API REST atrás do API Gateway (Lambda/ECS).
- **Régua de maturidade de criptografia operacionalizada** (16/10/2026): KMS declarativo e verificação de chaves.

### Corrigido
- `engenheiro-iac`: segredo no Terraform com argumentos write-only (`value_wo`); `sensitive = true` não tira o valor do state.

## [Não lançado] — 2026-10-09

Compatibilidade de configuração e de contratos. Laudo e evidências: [`docs/evolucao-compat-contratos-2026-10-09/`](docs/evolucao-compat-contratos-2026-10-09/README.md).

### Adicionado
- **`configuration-compatibility-review`** (`scripts/gates/compat_config/`): *Configuration as Contract* — consumidor no código × provedores por ambiente (IaC, configuração, contrato declarado, evidência demonstrada só por metadados), Environment Compatibility Matrix, 7 detectores para os 14 tipos de incompatibilidade (formato de secret, drift, `VERSION MISMATCH`, ausente/renomeada/removida, `DEPLOYMENT ORDER RISK`, migração, contrato externo/escopo/autenticação), blast radius local e histórico git.
- **`interoperability-contract-gate`** (`scripts/gates/interop/`): contratos como primeira classe (OpenAPI, AsyncAPI, Avro, Protobuf, JSON Schema, DTOs Java), diff semântico por direção (SAFE…BREAKING, sem confiar em SemVer), compatibilidade Avro com modos e ordem de atualização, sinais comportamentais e de mensageria, grafo de consumidores (Backstage, CODEOWNERS, repositórios declarados, IaC, runtime) com classes KNOWN/INFERRED/POSSIBLE/UNKNOWN, `POSSIBLY_INACTIVE` sem remoção, upstream (`PROVIDER_CONTRACT_MISMATCH`) e validação de consumidores só por comando explícito.
- **Núcleo reutilizável** (`scripts/compat/`): modelo de forma, leitores, diff, Avro, motor de risco proporcional, catálogo, confirmação humana, calibração (`governance/compat-calibracao.jsonl`) e ponte Trace2Local (export com os campos do record `Insight`; entrada de runtime).
- Estado **`NEEDS_CONFIRMATION`** na decisão central: só dos dois gates novos; libera planejamento/review/push/merge (lista branca) **com confirmação pendente** e bloqueia o deploy e qualquer outro checkpoint até confirmação humana registrada na política revisada.
- `verificar --checkpoint deploy --implantado <sha>`: no deploy as etapas de compatibilidade comparam com a revisão em execução no ambiente; sem ela (ou sem base nenhuma) ficam INCONCLUSIVE.
- Status remoto: com confirmação pendente, contexto adicional `<contexto>/confirmacao` em `pending`.
- Revisão independente: 2 falhas críticas (falso PASS no deploy depois do merge; evidência de validação forjada rebaixando BLOCKER) e 8 outras, corrigidas com teste — [`revisao-independente.md`](docs/evolucao-compat-contratos-2026-10-09/revisao-independente.md).
- Subagentes `configuration-compatibility-review` e `interoperability-contract-gate`; referências no `tech-lead-review`; `AGENTS.md` §10 e §11 (as 10 perguntas de Contract Safety); comandos `compat-relatorio`, `interop-validar-consumidores`, `compat-desfecho`, `compat-incidente`, `compat-calibracao`.

### Alterado
- `scripts/gates/orquestrador.py`: `--somente` de um gate que a política vigente ainda não exige roda em caráter consultivo (resultado PARCIAL, nunca libera) em vez de terminar em "política inválida".
- `scripts/gates/notificacao.py`: achado que pede confirmação não é anunciado como "bloqueado" fora do deploy.
- Política e esquema dos gates de entrega com as duas seções novas (ativas após o merge revisado).

## [Não lançado] — 2026-10-08

Evolução AWS + gates de entrega + review observável. Laudo e evidências: [`docs/evolucao-aws-2026-10-08/`](docs/evolucao-aws-2026-10-08/README.md).

### Adicionado
- **Política comum** de evidências, sigilo e qualidade (`governance/politica-evidencias-sigilo-qualidade.md`): marcas `[OK]/[AN]/[GAP]/[DIV]/[SEC]`, níveis de validação V0–V5, formato de achado, fontes oficiais com data.
- **Skills AWS** com 9 seções e evals: `orquestracao-step-functions`, `api-gateway-integracoes`, `tempo-real-aws`, `analise-producao-aws`; hub `arquiteto-cloud-aws` com roteamento, fatos verificados na documentação oficial (5 afirmações antigas corrigidas) e protocolo de planejamento com 7 artefatos.
- **Ferramentas AWS** (`scripts/aws/`): lint ASL (24 regras) e VTL (8 regras), simulador de caminho ASL, coerência diagrama × ASL × IaC × VTL, contratos JSON Schema, seletor ECS × Lambda, guarda de análise de produção somente leitura. Holdout cego independente: precisão 1,000 · recall 0,922 (3 defeitos corrigidos depois).
- **Cenário de referência** sintético (`labs/aws-referencia-ordens/`): ASL, VTL, contratos, SAM, Java (JUnit + Velocity real, 62 casos) e aceitação em Robot Framework.
- **Gates de entrega** (`scripts/gates/`): `database-schema-gate` (PostgreSQL `pg_catalog` somente leitura, Flyway, JPA, DynamoDB) e `environment-infrastructure-gate` (segredos de todo commit a enviar, configuração por ambiente, Terraform estático + evidências, AWS somente leitura, endpoints), com decisão central única, política lida da base revisada, snapshot do commit entregue, tarefas `gate-dep-*` e notificações deduplicadas. Subagentes homônimos em `.claude/agents/`.
- **Execução observável** (`scripts/execucao/`, `scripts/revisao/`): grafo da pipeline real, monitor ASCII a cada 300 s, watchdog com deadline e orçamento, cancelamento com grupo de processos, retomada por assinatura, fatias de pytest balanceadas (histórico local ou referência versionada) e benchmark. Medido na mesma árvore: 3,19× (frio) e 3,51× (aquecido), mesmos casos e mesmo veredito.
- Propostas da camada remota (`governance/freeze-patches/`): workflow com o código dos gates vindo da base, ruleset, CODEOWNERS e guarda de comando (PreToolUse) — não aplicadas (decisão humana).

### Alterado
- `ops/run.py`: prazo por passo com encerramento do grupo de processos; alvos `gates-entrega`, `database-schema-gate`, `environment-infrastructure-gate`, `revisao`, `aws`.
- `ops/hooks/pre-push`: gates de entrega nativos antes do Docker; fail-closed sem Python ou sem os gates.
- `scripts/git/squad_sync.py`: o push do harness só executa com os gates aprovados (sha da branch enviada).
- `skills/squad-ai/fase-gates.yaml`: G3.5 (planejamento — era G3.4; renumerado no merge com o master, onde G3.4 é o oráculo executável do plano), G5.5 (gates de entrega) e G5.6 (review observável).
- `.gitleaks.toml`: `^hooks/` ancorado na raiz.

### Corrigido
- `test_validador_reprova_defesa_mutilada` editava um arquivo rastreado durante o teste (corrida com execução paralela).
- Higiene de segredos: literais sintéticos de teste montados em tempo de execução.

## [0.6.0] — 2026-10-01


### Adicionado
- **Instalador multi-destino** (`install-squad-ai.py detectar | instalar-todos`): `~/.claude`, `~/.dsh` e `%LOCALAPPDATA%/RAI/CLI` (ou `~/.resolveai`) — só os presentes —, em paralelo, com backup/manifesto por destino; layout só-skills para Codex/Qwen/Cline/`~/.agents/skills` com metadados em `~/.squad-ai/instalacoes/<id>/`; detecção de 9 ferramentas agênticas com sugestão (sem instalar sozinho). Skill nova `instalar-skills`; perfil `minimo` passa a incluí-la. 11 testes (`tests/test_installer_destinos.py`).
- **Batman v2** (`scripts/batman/agenda.py`, `shift.py turno|proximo|concluir|executar|descobrir|vigia`, `instalar-vigia.ps1`): só o horário-limite encerra; fila recursiva persistente; descoberta de trabalho; motor LLM por job; vigia. 15 testes novos.
- **Aceleração por estação** (`scripts/accel/`): perfil da estação, adaptador OpenVINO (buckets B×L, `CACHE_DIR`, nireq ótimo, partição), `calibrar` (cenários A–G, paridade, memória compartilhada, telemetria), `kit_noturno`, `NeuralEmbedder` (cards e5-small/bge-small/MiniLM com revisão e SHA-256), ADR-014.
- `--podar` no instalador (`install` e `instalar-todos`): remove, com backup, o que este instalador pôs e a fonte não tem mais; sem a flag, só aponta os órfãos. O `rollback` devolve o que foi podado. 9 testes (`tests/test_installer_podar.py`).
- Relatórios: revisão da SPEC-NPU-GPU do fork, SPEC v2, relatório do ciclo heterogêneo, skills candidatas a remoção.
- Notas da release: [`docs/releases/v0.6.0.md`](docs/releases/v0.6.0.md).

### Removido
- **54 skills fora de engenharia de software** (grupos A, B e C da curadoria de 01/10/2026): o pacote de marketing (47 em `.claude/skills/` + o índice `marketingskills`), as arquivadas `crewai`, `microsoft-skillopt` e `understand-anything`, e `voicebox`, `humanizer` e `aws-ai-practitioner`. Catálogo residente medido (cl100k): 24.862 → 16.280 tokens; overhead fixo por sessão 49.282 → 40.507. Quem já tinha instalado: `instalar-todos --podar`.

### Alterado
- `DecisionCache`: `hit_policy` (`cosine` | `assist_only` | `verified`), limiar por espaço, `space_id` com reindexação, indexação incremental e em lote — compatível com o comportamento anterior.
- `VectorRouter`: indexação em lote e reindexação quando o espaço do embedder muda.
- Batman: a fila vazia não encerra mais o turno (teste BT6 atualizado para a nova semântica).
- `.claude/CLAUDE.md` sem os blocos de roteamento de marketing e da `humanizer`; a Linha de Defesa continua.
- Baseline de overhead fixo regravado (D9) depois do conserto do instrumento: 40.507 tokens sob cl100k.

### Corrigido
- Medição do catálogo (`scripts/token_opt/context_ab.py`): `description: >` era lida como ">" e 70 das 76 skills entravam vazias no catálogo.
- Gate de Object Calisthenics verde de novo: `evaluate_with_jev` (102 linhas, 4 níveis) e o `main` do agregador do CAP refatorados, com 6 testes de caracterização escritos antes.
- `.github/copilot-instructions.md` não listava a `instalar-skills` (o `generate_copilot --check` reprovaria).
- Instalador: duas execuções no mesmo segundo não sobrescrevem mais o backup uma da outra.

### Segurança
- Secret scan (gitleaks 8.28) da árvore e de todos os commits da release: nenhum segredo real; 6 arquivos de fixture sintética alistados por caminho exato em `.gitleaks.toml`. `pip-audit` sobre `constraints.txt`: sem vulnerabilidades conhecidas.

### Rejeitado (com evidência)
- HIT de cache por cosseno em qualquer espaço medido (negativo difícil pontua acima da paráfrase); limiar global; forma fixa [1,128]; INT4; JEV determinístico na NPU.

## 2026-09-29 — labs/haw-runtime v2 (runtime heterogêneo sem simulação)

- REJEITADO como evidência o scaffold HAW v1 (telemetria `random`, workloads `asyncio.sleep`, NPU presumida).
- Novo: `hw_probe` (OpenVINO), telemetria real + `DeviceLedger`, scheduler v2 (EWMA, stealing por custo, DAG/caminho crítico, backpressure, circuit breaker), `ov_bench`, `affinity`, `hetero_bench`, `run_kit.ps1`, 17 testes.
- Medido (CPU 2 vCPU): slots de CPU = núcleos 1,22× (8 slots 1,01×); req. em voo = OPTIMAL_NIREQ 1,85×; INT4 REJECT (cos 0,936); roteador semântico REJECT vs híbrido (r@1 0,309 × 0,993).
- Handoff: `docs/handoff/handoff-haw-2026-09-29.md`.

## [Não lançado]

### Adicionado — Go e Rust em nível profissional (2026-10-03)
- **11 skills** (`origin: squad-ai`, hub + references + evals, pt-BR), compiladas e testadas com Go 1.27 e Rust 1.99 (edição 2024); atribuições em `docs/ATTRIBUTIONS.md` §25:
  - **Go:** `golang-pro` **v2.0.0** (Go 1.27; hub enxuto + 4 references), `go-concurrency-expert`, `go-performance-engineer`, `go-cloud-services`, `go-error-investigator`.
  - **Rust:** `rust-pro`, `rust-async-services` (tokio/axum), `rust-unsafe-security` (unsafe/FFI, Miri, fuzzing, supply chain), `rust-performance-engineer`, `rust-error-investigator`.
  - **Compartilhada:** `aws-lambda-go-rust` — Lambda em Go e Rust sobre `provided.al2023` (SQS com falha parcial padrão e FIFO, HTTP API v2, init/deadline/concorrência, idempotência com lease, Managed Instances para Rust, migração `go1.x`/`provided.al2`, SAM validado com `cfn-lint`, teste local com Runtime API simulado).
- Perfis `backend-go` e `backend-rust` em `manifest.json` (herdam `minimo`) e as 11 skills em `completo`.
- `install-squad-ai.py`: as skills Go/Rust entram no domínio **backend** do índice (`SKILLS-INDEX.md`).
- `error-investigator` passa a despachar para `go-error-investigator` e `rust-error-investigator`.

### Alterado
- `golang-pro`: de Go 1.26 para **1.27**; `references/go-1.26.md` substituída por `go-1.27.md` + `idiomas-e-padroes.md`, `testes.md`, `tooling-e-qualidade.md`; evals de 2 para 6.

### Adicionado
- **`validacao-veracode` v1.1.0 — perfil `bancario` e bateria de SQL injection:** 107 regras (eram 73). SQLi agora cobre concatenação em várias linhas, `StringBuilder.append`, `MessageFormat`/text block formatado, JPQL, **PartiQL e expressões do DynamoDB**, MyBatis `${}`, Kotlin, f-string/`%`/`format` em Python, template literal sem tag, C# interpolado/Dapper e Go `Sprintf`. Perfil `bancario` (BACEN CMN 4.893 alterada pela 5.274/2025, BCB 538 e 494–498/2025, PCI DSS 4.0.1, Open Finance FAPI-BR, Pix MED 2.0, LGPD/sigilo): bloqueia a partir de Low, 30 CWEs bancários em qualquer severidade e 15 regras de domínio `BK-*` (dinheiro em float, BigDecimal sem `RoundingMode`, PAN por Luhn e CPF/CNPJ por DV — redigidos —, dado sigiloso em log, BOLA, mass assignment, idempotência, gasto duplo, timing, sessão > 15 min, HTTP sem TLS, OAuth fora do FAPI, stack trace/Actuator). Gerais novas: JWT sem verificação, TLS 1.0/1.1, chave e IV fixos, PBKDF2/bcrypt fracos. Gate: SLA de correção pela data da Findings API (vencido bloqueia no bancário), `--release` exige Policy Scan, achados SCA e aviso de perfil divergente. Nova reference `contexto-bancario.md`; 298 casos de teste; calibrado em ~1.066 arquivos reais (4 classes de falso-positivo corrigidas, inclusive uma antiga: `GenerateSecret: false` lido como credencial).
- **Skill `trace2local`** (`skills/trace2local/`, perfis `backend-java` e `observabilidade`): instalar, configurar e usar o Trace2Local — modo embedded (plugin Maven `analyze` → `configure`), Lambda Java 21/25 + Station no LocalStack (JVM e nativo), verificação, Mock Connect (quando indicar mock/variação, sob demanda por baggage) e MCP do Trace2Local por projeto (perfil `core`, somente leitura, dados estruturais). Hub + 5 references + 7 evals; Linha de Defesa reforçada para saída de ferramenta.
- **ADR-015 (Proposto)**: avaliação do servidor MCP do Trace2Local pelos 5 critérios de admissão — skill primeiro, servidor no `.mcp.json` do repositório do app; **sem** edição no `.mcp.json` desta squad até o GATE.

### Adicionado (2026-09-22 — ciclo open source + JEV + qualidade)
- **Skill nova `batman` (modo noturno autônomo):** turno de melhoria contínua (janela-padrão 19h00→08h00, ajustável "Ative o modo batman até 9h00"), conectado ao cérebro cognitivo, runner determinístico `scripts/batman/shift.py`, protocolo em `references/protocolo-noturno.md`, catálogo de capacidades (SO/terminal/jobs/GUI/browser/DSH) em `references/capacidades-guardioes.md` e motor multi-provider (DeepSeek/Bedrock) + fluxo de criação de JEV em `references/motor-llm-jev.md`. Autônomo na execução (N2, allow-list), gated nos marcos N3.
- **Camada JEV incorporada às skills canônicas** (10 estratégias aprovadas por benchmark): seção "Camada JEV" em 11 SKILL.md + references novas (`tech-lead-review/references/review-jev.md`, `auditoria-skill-externa/references/scanner-deterministico.md`).
- **Evals para as 28 skills que faltavam** (formato canônico, 3 cenários/skill) — auditoria estrutural **78/78 limpas, 0 achados**; validador novo `tools/validate_evals.py` (schemas A/B) + testes.
- **Instalador `.claude` com porta de segurança fail-closed** (`install-squad-ai.py`): bloco de defesa obrigatório, frontmatter `name` == pasta, pré-screen estático (HIGH/CRITICAL bloqueia), conteúdo de terceiros preservado sem `--force`, `--perfil` (manifest.json), backup/rollback/verify.
- **Prontidão open source:** `docs/open-source/00–08` (varredura, sanitização, pesquisa, benchmark cognitivo, arquitetura, relatório de limpeza, veredito NOT PUBLIC READY com caminho de remediação) · `CODE_OF_CONDUCT.md` · `ROADMAP.md` · templates de issue (bug/feature).
- **Pré-registro da célula V3 "COM+JEV"** (`docs/relatorios/benchmarks/v3/PRE-REGISTRO-CELULA-JEV.md`) — aguardando aprovação de orçamento + selagem.

### Alterado (2026-09-22)
- 8 skills com `origin: community` corrigidas para `squad-ai` com evidência de autoria interna; `docs/ATTRIBUTIONS.md` §24 consolidado.
- `auditoria_skills.py`: evals em `*.py` contam; snapshots de benchmark excluídos da varredura (novo `T-AUD4`).
- README sincronizado: badges (agentes 30, MCPs 3), destaques medidos, novidades 2026-09, quick-start do instalador.

### Removido (2026-09-22)
- ~90 MB de binários da árvore pública movidos para `_local-artifacts/` (grafo 23 MB regenerável, zips/papers/PNGs pessoais, PPTX) — reversível; logo re-comprimida (6,3 MB → 621 KB), grafo do cérebro (1,4 MB → 714 KB).
- Ferramentas one-shot da sanitização (com nomes corporativos) movidas para `_local-artifacts/tools/`.

### Segurança (2026-09-22)
- Pré-screen estático do catálogo: **8 achados, 0 em código, 0 review, 0 DO NOT INSTALL** (os 8 são citações de padrões de ataque em docs — falso positivo documentado).
- Zero-width real removido de `auditoria-skill-externa`; `__import__` refatorado em teste do `chatbot-comercial`.
- `results/diagnostico.json` removido do índice git; `.gitignore` endurecido (`.fuse_hidden*`, `*.db.bak*`, `.env.pronto`, scratch de testes).

### Adicionado
- Identidade **SquadAI Harness** e arquitetura de cinco módulos (Core, Skills, Squad, Loops, Lab).
- Documentação fundacional: filosofia, arquitetura, ciclo de vida da skill.
- Quality gates explícitos (G0–G4) no Core.
- Template de contrato de skill.
- Meta north-star **7×** definida com métricas DORA (falsificável).

### Alterado
- Reposicionamento de "coleção de skills" para **protocolo de engenharia** com ciclo de vida explícito.

### Corrigido
- **Gate `auditoria_skills.py`:** reparado (truncado na linha 162) — relatório da rubrica §0.4 volta a rodar (`test_auditoria_skills` 3/3).
- **Débito do corpus:** `description` ausente em `arquiteto-dados-streaming` (erro do gate) + `origin`/`Linha de Defesa de Prompt` ausentes em 11 skills harvested → resolvidos. Gate do corpus **BLOQUEADO → PRONTO** (0 erros).
- **`aws-lambda-java25-aot` (v1.0→v1.1):** `ApiGatewayHandler` passa a serializar todo corpo via Jackson (fim da concatenação de String) e `notFound` não reflete mais `method`/`path` no corpo (evita injeção/vazamento). Novos helpers padronizados `created()` (201 + `Location`) e `badRequest()` (400), alinhados ao contrato `app/openapi/openapi.yaml`.
- **Gate de skills:** reparado `scripts/validate_skills.py`, truncado na linha 184 (f-string não terminada) — derrubava todo o `test_validate_skills`. Sumário/saída restaurados (`RESULTADO: PRONTO|BLOQUEADO`, exit 0/1). 8/8 testes verdes.

### Segurança
- Pré-flight obrigatório (Fase 0): rotação de token vazado e reparo do `.git` antes de qualquer rename.

---

> **Migração a partir de "Squad AI Skills":** este changelog inicia na transição de marca. O histórico técnico anterior está preservado em `Notas.md` e no histórico Git. A correspondência de termos antigos→novos está em `PLANO-REBRANDING.md` (§7).
