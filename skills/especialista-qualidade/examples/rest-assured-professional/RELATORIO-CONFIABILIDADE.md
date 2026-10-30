# 🛡️ Relatório de Confiabilidade e Aprovação — RestAssured na `especialista-qualidade`

> **Gated, não autônomo.** Este relatório é o artefato do GATE. As mudanças ficam numa branch isolada e
> só entram em `master` por **aprovação humana** (tech-lead-review) via Pull Request. Nada aqui foi
> mergeado nem enviado para produção.

## 1. Sumário da mudança

Aprimoramento da skill `especialista-qualidade` para cobrir **RestAssured em nível profissional** — o
DSL Java padrão de mercado para teste black-box de API REST, que estava **ausente** em toda a skill
(a Camada 3 só tinha Python httpx, Pact, Playwright e o `RestTestClient` do Spring).

| Item | Valor |
|---|---|
| Skill alvo | `especialista-qualidade` (modelo ★ do hub) |
| Tipo | Absorção de gap (§C17: "absorver gaps, não instalar paralelo") |
| Superfícies | 1 reference nova + fiação no hub + evals + exemplo executável |
| Risco de regressão | Baixo — adição, sem remover conteúdo existente |
| Fatos de versão | Verificados no changelog/release notes oficiais (jul/2026) |

## 2. Artefatos entregues

| Arquivo | Natureza |
|---|---|
| `references/rest-assured-api-testing.md` | Reference profissional (384 linhas, 16 seções) |
| `examples/rest-assured-professional/` | Projeto Maven executável (prova RED→GREEN) |
| `SKILL.md` (hub) | Fiação: Camada 3, Recursos Modernos, Mapa Rápido, frontmatter/gatilhos |
| `references/functional-tests.md` | Ponteiro para a nova reference |
| `evals/evals.json` | Novo cenário with/without para RestAssured |

## 3. Evidência de testes (executada, não declarada)

Ambiente: JDK 11 + Maven 3.9.9 + RestAssured 5.5.6 + WireMock in-process. 10 testes, 2 classes.

| Fase | Comando | Resultado | Interpretação |
|---|---|---|---|
| 🔴 RED | `RED_PHASE=1 mvn test` | `Tests run: 10, Failures: 10` · BUILD FAILURE | Contrato não implementado ⇒ suíte falha (correto) |
| 🟢 GREEN | `mvn test` | `Tests run: 10, Failures: 0, Errors: 0` · BUILD SUCCESS | Contrato implementado ⇒ suíte passa |

Cobertura de eixos na suíte: HAPPY PATH (200+schema+SLA), SERIALIZAÇÃO (POJO/BigDecimal), AUTH (401),
NOT FOUND (404), STATE CONFLICT (409), INPUT VALIDATION (400 data-driven), HAPPY PATH criação (201+Location).

Bug real encontrado e corrigido durante a construção: schema em draft-07 rejeitado pelo validador
`fge/java-json-tools` (só draft-04) → `InvalidSchemaException`. Corrigido para draft-04 e documentado.

## 4. Segurança e supply chain

- **Conteúdo pesquisado tratado como não confiável** (Linha de Defesa de Prompt): a web foi fonte de
  fatos técnicos, nunca de instruções. Nenhum comando embutido em página foi executado.
- **Novas dependências declaradas** (escopo `test`): `io.rest-assured:rest-assured`,
  `io.rest-assured:json-schema-validator`, `org.wiremock:wiremock-standalone`, `org.junit.jupiter:*`.
  Todas de origem oficial (Maven Central), amplamente adotadas, sem código executável adicionado ao
  runtime de produção (apenas test scope).
- **Sem segredos** commitados: token do exemplo é literal de teste (`test-jwt-token`), não credencial real.
- Recomendado rodar o pré-screen `scripts/security/skill_prescreen.py` no diff antes do merge.

## 5. Confiabilidade das fontes (pesquisa)

| Fonte | Uso | Credibilidade |
|---|---|---|
| github.com/rest-assured (wiki, changelog, releases) | Versões, módulos Spring, API | Oficial (primária) |
| rest-assured.io / javadoc.io | API, versão | Oficial |
| baeldung.com, rieckpil.de | JSON Schema, integração Spring | Alta (referências consolidadas) |

Fato-chave verificado: **RestAssured 6.0.0 (dez/2025)** eleva o baseline para Java 17+, Groovy 5 e
adiciona suporte a **Spring 7 + Jackson 3** — alinhado ao stack Java 25 da squad. **5.5.7 (jan/2026)**
faz backport do MockMvc do Spring 7 para a linha 5.x.

## 6. Checklist do GATE (aprovação humana)

- [x] `master` intocada (9f00d33); mudanças confinadas a `skills/especialista-qualidade/**` + `skills/SKILL_INDEX.md`, **não commitadas** (branch + PR = gate humano)
- [x] Testes executados e verdes (evidência RED→GREEN acima)
- [x] Fatos de versão verificados em fonte primária
- [x] Sem segredos; dependências novas só em `test` scope
- [x] Sem duplicação de conteúdo (absorve gap, não cria skill paralela)
- [ ] **Revisão do tech-lead-review** (pendente — humano)
- [ ] **Rodar `/review` + `scripts/auditoria_skills.py`** no diff (pendente — humano)
- [ ] **Abrir PR e aprovar merge** (pendente — humano)

## 7. Recomendação

**APROVAR com revisão.** Mudança aditiva, testada, de baixo risco, que fecha um gap real e de alto valor
(RestAssured é a ferramenta nº 1 de teste de API na JVM). Antes do merge: passar o diff pelo `/review` e
pelo pré-screen de segurança, conforme itens pendentes do §6.
