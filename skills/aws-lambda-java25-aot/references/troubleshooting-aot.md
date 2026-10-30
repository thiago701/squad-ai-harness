# Troubleshooting AOT — investigar bugs em Java 25 + Lambda + GraalVM Native

> Reference de **investigação** (não de geração). Complementa a seção "Debugging native
> build failures" de `spring-boot-4-graalvm-lambda.md`, mas focada em **runtime** e
> **observabilidade**. Aplica o protocolo **Debug 4 Fases** (REPRODUZIR → ISOLAR →
> DIAGNOSTICAR → CORRIGIR) ao stack. Regra-mãe: **bug do nativo se reproduz no nativo** —
> nunca diagnostique no JIT um bug que só existe no binário AOT.

## 0. Mapa de sintomas → seção

| Sintoma | Provável causa | Vá para |
|---|---|---|
| Roda na JVM, falha no binário nativo | metadado de reachability faltando | §2 |
| `MissingReflectionRegistrationError` / `ClassNotFoundException` no runtime | reflection não registrada | §2 |
| Jackson/DynamoDB Enhanced Client falha ao (de)serializar | reflect-config incompleto | §2 |
| `application.properties`/`.json` "não encontrado" só no nativo | resource-config faltando | §2 |
| `native:compile` falha | análise estática + `--no-fallback` | §2 |
| Cold start alto / `Init Duration` grande / INIT timeout | inicialização pesada | §3 |
| `Runtime.ExitError` / bootstrap não executa | custom runtime al2023 | §3 |
| Handler retorna 500 sem causa clara | falta observabilidade | §4 |
| Erro só em produção, não local | ambiente/permissão/dados | §1 + §4 |

## 1. REPRODUZIR (fase 1 — sem reprodução não há fix, há aposta)

- **Modo nativo local:** `mvn -Pnative native:compile && mvn -Pnative test`. Bug AOT é invisível na JVM.
- **Evento real:** `sam local invoke <Fn> --event events/<caso>.json` no container al2023; capture o evento EXATO (API GW v2 ou DDB Streams record) que falha.
- **Dependências locais:** LocalStack/Testcontainers para o DynamoDB (a skill já gera os testes).
- **Diferencial JVM × nativo:** se passa na JVM e falha no nativo, o bug é quase sempre **metadado de reachability** (§2), não lógica.

## 2. GraalVM Native — o caso nº 1 ("roda na JVM, falha no nativo")

A análise estática do `native-image` não enxerga features dinâmicas (reflection, recursos, proxies, serialization). O que ela não alcança precisa de **reachability metadata** declarado.

- **Mantenha `--no-fallback`.** Ele faz o build **falhar** quando falta config, em vez de gerar um fallback JVM lento. Build vermelho aqui > runtime quebrado em prod.
- **Colete metadados com o Tracing Agent** rodando a app na JVM e exercitando os caminhos reais (testes/eventos):

```bash
java -agentlib:native-image-agent=config-merge-dir=src/main/resources/META-INF/native-image/<group>/<artifact> \
     -jar target/app.jar    # exercite TODOS os caminhos; o agente faz MERGE (não overwrite)
```

  Ele gera/atualiza `reachability-metadata.json` (seções `reflection`, `jni`, `resources`, `serialization`). Commite o resultado.

- **Onde declarar:** `RuntimeHints` em `NativeHints.java` (`@RegisterReflectionForBinding`) para legibilidade **e/ou** `reflect-config.json` / `resource-config.json` em `META-INF/native-image/<group>/<artifact>/`. A skill gera ambos — **não delete**.
- **Build com diagnóstico:** `native:compile` com `-H:+PrintClassInitialization` e `--diagnostics-mode` mostra o que a análise inicializa/alcança; útil para achar a classe que falta registrar.
- **Init build-time × run-time:** classe inicializada em build-time que lê env/arquivo em runtime → mova para `--initialize-at-run-time=<classe>`. Segredo lido no init de build-time vaza no binário (N3).
- **Lambda/method handles:** classes-proxy de lambda têm suporte limitado (melhorando no GraalVM) — pode exigir registro explícito de reflection/serialization.

## 3. Runtime da Lambda — init, cold start, al2023

- **Leia o `REPORT`/`INIT_REPORT` no CloudWatch:** separe `Init Duration` (cold start) de `Duration` (invoke). Init alto = bean pesado, leitura de SSM/Secrets no init, classpath grande.
- **`Runtime.ExitError` / bootstrap:** no custom runtime al2023 o `bootstrap` deve ser o **binário nativo** executável (`chmod +x`), e o handler precisa casar. Cheque o empacotamento do SAM.
- **Timeout / OOM:** compare `Max Memory Used` × `Memory Size` no REPORT; OOM no nativo costuma ser heap pequeno para o pico (ajuste memória da função).
- **Cold start regrediu:** algo voltou a cair em fallback JVM ou reflexão não registrada — confira `--no-fallback` e o tamanho do binário.

## 4. RCA por observabilidade (Powertools + CloudWatch + X-Ray)

- **Log estruturado (`@Logging`):** JSON com `coldStart`, `functionName` e correlação; use **log sampling** para uma % de DEBUG em prod. **Nunca `System.out.println`** — o Logs Insights não consulta texto solto.
- **CloudWatch Logs Insights** — exemplos:

```sql
fields @timestamp, level, message, error.type
| filter level = "ERROR"
| stats count(*) as erros by error.type
| sort erros desc
```

- **X-Ray (`@Tracing`):** subsegmentos por chamada (DynamoDB, downstream) revelam ONDE a latência/erro nasce — essencial em cold start.
- **Métricas EMF (`@Metrics`):** métrica de erro/negócio + detecção de cold start, sem custo de chamada extra.
- **Correlation ID:** propague do API Gateway (`HttpRequests.extractTraceId(event)`) para todo log e trace — liga o sintoma à invocação.

## 5. CORRIGIR + prevenir regressão (fase 4)

1. Adicione o metadado faltante (reflect/resource/serialization) **no menor escopo** que resolve.
2. **Reproduza o verde no nativo:** `mvn -Pnative test` (não só `mvn test`).
3. **Cubra com teste** (Testcontainers/LocalStack) — bug sem teste volta (Debug 4 Fases).
4. Commite o `reflect-config`/`reachability-metadata.json`; `--no-fallback` no CI barra a regressão.

## Checklist de investigação

- [ ] Reproduzido no **modo nativo** (não só na JVM)?
- [ ] `--no-fallback` ativo e build nativo verde?
- [ ] Tracing Agent rodado nos caminhos reais e metadados versionados?
- [ ] Logs estruturados (Powertools) com `coldStart` + correlação?
- [ ] X-Ray mostra onde nasce o erro/latência?
- [ ] Fix coberto por teste **em modo nativo** antes do merge?
