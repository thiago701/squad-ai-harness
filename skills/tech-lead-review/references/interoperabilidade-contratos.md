# Predictive Interoperability & Contract Impact Review

> **Princípio:** uma alteração localmente válida não significa uma alteração sistemicamente segura. O código
> pode estar 100% correto isoladamente e ainda assim produzir uma falha sistêmica.
> Executor: `interoperability-contract-gate` (`scripts/gates/interop/`, núcleo `scripts/compat/`).

## 1. Duas direções, sempre

| Direção | Pergunta | Fontes |
|---|---|---|
| **DOWNSTREAM** (filhos) | quem pode quebrar se alterarmos nosso contrato? | catálogo (`consumesApis`), código dos repositórios disponíveis, IaC que assina nossos tópicos/filas/bus, runtime |
| **UPSTREAM** (pais) | com quem podemos ficar incompatíveis? | nosso `consumesApis`, código cliente (URLs/versões/escopos), contratos OpenAPI dos provedores disponíveis |

## 2. Contract Dependency Graph

Montado a cada review a partir de: catálogo Backstage (`catalog-info.yaml` deste repositório, de
`interoperabilityContractGate.catalogos` e dos repositórios declarados), código e IaC dos repositórios em
`interoperabilityContractGate.repositorios` (clones locais), runtime (`squad/runtime-evidencia/v1`, ex.:
exportado do Trace2Local), validações de consumidores e histórico git. Transitivos até 3 níveis / 50 nós.

Classe do consumidor — inferência nunca vira fato: `KNOWN` (catálogo com vínculo exato à API, ou código que
referencia o contrato/esquema) · `INFERRED` (IaC/runtime) · `POSSIBLE` (só catálogo do componente, sem
`spec.definition` ligando a API ao arquivo) · `UNKNOWN`.

## 3. Contratos reconhecidos

OpenAPI 3.x (operação, parâmetros, corpo, respostas por status, escopos, mídias, servidores) · AsyncAPI 2.x/3.x ·
Avro `.avsc` · Protobuf `.proto` (primeiro nível, números de campo) · JSON Schema · DTOs Java de borda
(`*Event/*Message/*Request/*Response/*Command/*Dto`). Implícitos no código (base × revisão dos arquivos
alterados): status HTTP por endpoint, paginação, `@JsonInclude`, `@JsonFormat`, `setScale`, `ZoneId`,
`Sort.by`, `@Async`, idempotência, timeouts/retries, `produces/consumes`, `eventType/detail-type`, destino de
publicação, `MessageGroupId`, deduplicação, chave de partição Kafka, atributos de mensagem, rotas/tipos de
WebSocket, heartbeat. **Não cobertos (lacuna declarada):** GraphQL SDL, SOAP/XSD, gRPC além do `.proto`,
Kotlin DTO.

## 4. Semantic Contract Diff

A classificação depende da direção (`scripts/compat/diff.py`): `SAFE · LIKELY_SAFE · UNKNOWN · RISKY · BREAKING`.

| Mudança | Saída (nós produzimos) | Entrada (nós lemos) |
|---|---|---|
| campo removido | BREAKING (obrigatório) / RISKY (opcional) | LIKELY_SAFE (BREAKING se esquema fechado) |
| campo opcional adicionado | SAFE | SAFE |
| campo obrigatório adicionado | LIKELY_SAFE (BREAKING p/ leitor fechado) | BREAKING |
| campo renomeado/movido (`customerId → customer.id`) | BREAKING | RISKY/BREAKING |
| `String → Optional<String>` (passa a aceitar nulo) | RISKY | SAFE |
| `Long → String` / estrutura `STRING → RECORD` | BREAKING | BREAKING |
| alargamento `int → long` | RISKY | SAFE |
| símbolo de enum adicionado / removido | RISKY / LIKELY_SAFE | SAFE / BREAKING |
| formato/fuso/precisão | RISKY | RISKY |

Semantic Versioning não é evidência: `1.4.1 → 1.4.2` pode ser BREAKING — vale o diff real.

## 5. Kafka / Avro

Resolução leitor × escritor da especificação Avro e modos do Schema Registry (padrão `BACKWARD`):
`BACKWARD` (leitor novo lê dado antigo — atualizar consumidores antes), `FORWARD` (leitor antigo lê dado novo —
produtores antes), `FULL` (ordem livre) e `*_TRANSITIVE` (contra todas as versões do histórico git). Modo
declarado violado = fato (o registry recusaria) → `BLOCKER`. Esquema `.avsc` de consumidor disponível é
verificado como LEITOR contra o novo escritor ("2 consumidores esperam STRING").

## 6. Consumer & Provider Impact

Por consumidor: `VALIDADO` (evidência `squad/interop-validacao/v1` aprovada **para este commit**, sem nada que a
contradiga) · `COMPATIVEL_ESTATICO` (código disponível sem uso do que mudou) · `INCOMPATIVEL` (usa o que mudou,
leitor Avro incompatível, runtime acessa ou validação falhou) · `CONFLITO` (validação aprovada × uso detectado →
confirmação humana) · `DESCONHECIDO` · `POSSIBLY_INACTIVE` (sem atividade na janela de runtime, com janela de no
máximo 30 dias — nunca remover compatibilidade sem validação). A evidência de validação só vale para consumidor
declarado na política revisada com o **mesmo comando** (hash do argv), dentro da validade do checkpoint e com o
consumidor no commit validado; é arquivo local, sem proveniência criptográfica, e sozinha nunca desmente quebra. Upstream: cliente passou a chamar caminho/
versão que o provedor disponível não expõe → `PROVIDER_CONTRACT_MISMATCH`.

Validação automática de consumidores (§19 do pedido) roda **por comando explícito**, nunca dentro do gate:
`python -m scripts.gates interop-validar-consumidores` executa o `testeCompatibilidade` (argv, sem shell,
com `timeoutS`) declarado na política revisada e grava a evidência vinculada ao commit do produtor.

## 7. Predictive Contract Risk Engine e bloqueio proporcional

`score` = probabilidade de quebra × consumidores × criticidade × exposição em runtime × confiança × novidade ×
lacuna de validação (fatores expostos no resultado). Severidade pela evidência (`scripts/compat/risco.py`):

| Severidade | Quando |
|---|---|
| `BLOCKER` | quebra comprovada (consumidor/ambiente demonstradamente incompatível, confiança ≥ 90; modo Avro violado) ou risco CRÍTICO sem a validação exigida |
| `HIGH` | forte evidência de impacto (consumidor incompatível, confiança ≥ 80) |
| `NEEDS_CONFIRMATION` | consumidor conhecido sem como provar compatibilidade; quebra estrutural sem público identificado |
| `WARNING` | consumidores sem uso do que mudou; mudança pequena sem consumidor conhecido |
| `INFO` | comprovadamente compatível (NO SILENT CONTRACT CHANGES: aparece mesmo assim) |

Escalonamento: LOW → validação estática · MEDIUM → testes automatizados de compatibilidade · HIGH → contrato +
integração · CRITICAL → validação entre sistemas + confirmação explícita. Testes unitários do repositório não
aprovam mudança crítica. Ferramentas sugeridas por stack: Pact JVM / Spring Cloud Contract,
`kafka-schema-registry-maven-plugin test-compatibility`, `oasdiff breaking`, `buf breaking`.

`NEEDS_CONFIRMATION`/`HIGH` não bloqueiam review/push/merge (a aprovação humana do PR é a confirmação);
bloqueiam o **deploy** até confirmação em `interoperabilityContractGate.confirmacoes` (aprovador humano listado,
referência, validade). O agente nunca confirma. No deploy a base é a revisão em execução no ambiente
(`--implantado <sha>`, informada pelo pipeline e registrada no resultado); sem ela o gate fica `INCONCLUSIVE`.
Com confirmação pendente, o status remoto ganha o contexto `…/confirmacao` em `pending` — exija-o no deploy.

## 8. Human-in-the-loop como ÚLTIMO gate

Detect → Analyze → Infer → Test automatically → Search evidence → Cross-repo → Runtime → ainda incerto? →
pergunta ao dono. Modelo de pergunta: "**EXTERNAL CONSUMER VALIDATION REQUIRED** — `PaymentCompleted v3`
remove `authorizationCode`. `Fraud Engine` (dono: Fraud Platform Team) está identificado como consumidor.
Confirmem se a versão implantada deixou de depender desse campo antes da promoção". Dono só com evidência
(catálogo `spec.owner`, CODEOWNERS) — sem evidência, "dono não identificado".

## 9. Saída

**CONTRACT IMPACT REVIEW** por contrato (mudança, direção, classificação, consumidores conhecidos/validados/
incompatíveis/desconhecidos, blast radius direto/transitivo/crítico/desconhecido, risco, confiança,
validações automáticas, pendências, decisão), **Change Intelligence** (contrato × DTO × IaC × comportamento ×
testes de contrato) e o export para o Trace2Local (`.cache/gates/compat/insights-interoperabilidade.json`).

## 10. Controle de falso positivo e aprendizado com incidentes

`python -m scripts.gates compat-desfecho` registra VP/FP/FN/override no ledger versionado;
`compat-calibracao` mostra precisão, recall, FP entre alertas e marca `RECALIBRAR` (≥ 5 desfechos e precisão <
0,70) — sem rebaixar severidade sozinho. `compat-incidente` transforma incidente em proposta de detector +
teste de regressão (`docs/compat/incidentes/`).
