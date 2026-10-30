# Integração JEV e Arquitetura Multiagente Sonar-First

> **Implementação canônica:** `scripts/sonar/jev_sonar.py` + `cognitivo/harness/adapters.py` (`SONAR_PREP`, `SONAR_GATE`).

---

## 1. Os 8 Papéis Lógicos na Camada JEV (Camada 0 Determinística)

Para evitar a multiplicação desnecessária de chamadas de LLM (*agent soup*, `AGENTS.md` §4.1), os 8 papéis
solicitados pela arquitetura Sonar-First operam como funções determinísticas tipadas na Camada 0
(`JevSim`, `< 2 ms`, US$ 0) e só escalam para especialistas LLM (`sonnet`/`opus`) quando há necessidade
comprovada de refatoração semântica ou arquitetural:

| # | Papel Lógico | Função em `scripts/sonar/jev_sonar.py` | Responsabilidade | Quando escala ao LLM |
|---|---|---|---|---|
| 1 | **Sonar Rule Interpreter** | `interpretar_regras_aplicaveis` | Cruza linguagens/frameworks do projeto com o catálogo MQR e destaca regras prioritárias. | Nunca (100% determinístico). |
| 2 | **Preventive Coding Agent** | `gerar_restricoes_preventivas` | Traduz regras `BLOCKER`/`HIGH`/`MEDIUM` em restrições imperativas injetadas na Fase A/B. | Na geração do código pelo especialista da linguagem. |
| 3 | **JEV Risk Classifier** | `classificar_risco_jev` | Calcula `tier_risco` (`trivial`, `baixo`, `medio`, `alto`, `critico`), `score_risco` `[0..1]` e orçamento em ms. | Quando `tier == "critico"` (toca auth/cripto/SQL/concorrência em múltiplos arquivos). |
| 4 | **Static Analysis Agent** | `avaliar_validacao_incremental` | Executa a análise AST + regex incremental com cache SHA-256 (`.cache/sonar-cache.json`). | Nunca (100% determinístico). |
| 5 | **Secure Coding Agent** | `prevenir_falhas_seguranca` | Audita achados MQR `SECURITY` (CWE-78, CWE-79, CWE-89, CWE-117, CWE-209, CWE-319, CWE-328, CWE-330, CWE-798). | Sempre que houver achado `SECURITY` (`engenheiro-seguranca`). |
| 6 | **Auto-Fix Agent** | `classificar_elegibilidade_autofix` | Decide se a violação tem transformação local determinística segura ou se exige refatoração estrutural. | Quando a regra exige redesign (`S3776`, `S1541`, `S6881`, `S3655`, `S2095`). |
| 7 | **QA Validation Agent** | `planejar_verificacao_qa` | Verifica se os testes impactados rodaram e passaram após qualquer código gerado ou autocorrigido. | Se um teste quebrar após refatoração (`especialista-qualidade`). |
| 8 | **Quality Gate Auditor** | `auditar_quality_gate_final` | Emite veredito `PASS` / `BLOCKED`, ratings `A`–`E` estimados e selo `V2` vs `V3`/`V4`. | Quando o gate bloqueia sem autofix aplicável (`tech-lead-review`). |

---

## 2. Integração Nativa com as Skills da Squad AI

O motor Sonar-First não depende de invocação manual isolada; ele está conectado aos pontos vitais do
ecossistema:

1. **Preflight e Planejamento (`scripts/preflight.py` + `squad-pipeline`):**
   - `00-preflight.md` inclui automaticamente a seção `## Restricoes preventivas Sonar-First (Fase A/B)`.
2. **Geração e Refatoração de Código (`java25-spring-boot`, `java-modernizer`, `python-pro`, `especialista-frontend`, `clean-code-craftsman`):**
   - Aplicam as restrições preventivas da Fase B durante a escrita e rodam `python -m scripts.sonar validar <arquivos>` (Fase C) e `autocorrigir` (Fase D) antes de concluir a tarefa.
3. **TDD e Qualidade (`especialista-qualidade` + `verificacao-loop`):**
   - Validam que os testes não introduzem smells ou credenciais hardcoded e executam `python -m scripts.sonar gate` na Fase E pré-entrega.
4. **Segurança e Code Review Independente (`engenheiro-seguranca` + `tech-lead-review`):**
   - O `tech-lead-review` consome o relatório da Fase E como evidência de entrada, mantendo sua auditoria independente sobre design, contratos, segurança de negócio e aderência arquitetural.
