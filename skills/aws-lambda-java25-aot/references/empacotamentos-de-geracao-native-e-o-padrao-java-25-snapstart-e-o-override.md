# aws-lambda-java25-aot · Empacotamentos de geração: Native é o PADRÃO (Java 25); SnapStart é o override

> Reference da skill `aws-lambda-java25-aot` (movida da SKILL.md em 11/10/2026 — hub + references, I3). Carregue só quando a tarefa pedir este tema.

## Empacotamentos de geração: Native é o PADRÃO (Java 25); SnapStart é o override

Esta skill suporta **dois empacotamentos** sobre a **mesma base de código vanilla
hexagonal e testável** (provada pela entrega Task Manager: 100% cobertura de linha,
220 testes, `./mvnw verify` ~25–31 s verde, gates travados). **Desde 2026-07-05, para
Java 25 novo o padrão é GraalVM Native (AOT)**; o SnapStart (em `java21`) é o override
documentado. A referência viva dos dois lados sobre **código idêntico** é
`lambda-aot-benchmark/` (`graalvm-native/` vs `snapstart/`) — use-a como blueprint.

O ponto-chave: o **código de negócio é o mesmo vanilla testável na JVM**; só o
empacotamento/runtime muda. Native NÃO obriga Spring Boot — o default recomendado é
**vanilla hexagonal + GraalVM Native** (testável na JVM E cold start ~4× menor que a JVM),
preservando P1-Simplicidade. O caminho Spring Boot 4 + GraalVM continua disponível para
quem já é Spring-first.

| Critério | **GraalVM Native — PADRÃO Java 25** | SnapStart — override (`java21`) |
|---|---|---|
| Cold start | **~30–150 ms** | 200–500 ms (P99 −90%) |
| Código de negócio | vanilla hexagonal, testável na JVM (ms) | **idêntico** |
| Custo de build | alto (reflect-config, +min, JVM↔nativo) | baixo (JVM pura) |
| Papel | **default para Java 25 greenfield** | override: deploy contínuo, time pequeno, reflexão pesada, SLA ≥ 200 ms |
| Templates | `template-native.yaml` + reflect-config (`*.tmpl` Spring opcional) | `*-vanilla-jvm.*.tmpl` (runtime `java21` + SnapStart) |

**Gerar (default Java 25):** parta da base vanilla testável (`scripts/generate_vanilla_lambda.py`,
ou clone `lambda-aot-benchmark/graalvm-native/`) e mantenha o empacotamento Native — pom com
profile `native` **opt-in** (`-Pnative`, para `mvn verify` rodar os testes na JVM sem exigir
GraalVM), `reflect-config.json`, e `template.yaml` com `provided.al2023` + `BuildMethod: makefile`.
**Override para SnapStart** (leia `references/vanilla-jvm-snapstart.md`): mesma base, runtime
`java21` + `SnapStart: ApplyOn: PublishedVersions`, sem reflect-config. Os templates vanilla nascem
com **auth por padrão** (Cognito JWT + ownership → fecha BOLA/IDOR) e **Maven wrapper sempre**.

**Gerar (provado VERDE):** `scripts/generate_vanilla_lambda.py` faz cópia verbatim do
blueprint provado (`<repo>/app`) + rename uniforme de identificadores → projeto que passa
`./mvnw verify` verde de primeira (220 testes, 100% cobertura, gates):

```bash
python aws-lambda-java25-aot/scripts/generate_vanilla_lambda.py \
  --blueprint <repo>/app --entity Widget --package com.acme.widget \
  --table WidgetSingleTable --app-dir ./widget-lambda
cd widget-lambda && ./mvnw verify    # BUILD SUCCESS (provado: Widget, 220 testes, gate MET)
```

O projeto nasce com os campos de exemplo do blueprint sob o seu nome de entidade —
substitua-os pelo seu DBML e mantenha o cross-cutting. Detalhes em
`references/vanilla-jvm-snapstart.md`.

### Parametrizar o domínio: value objects a partir de uma spec (fecha o débito manual)

O `generate_vanilla_lambda.py` deixa os **campos de exemplo do blueprint** sob o seu
nome — trocá-los pelos **value objects validados do domínio real** (Pais, Escopo,
DataEvento, Horario, Descricao…) era manual (~7 min, medido no `calendario-lambda`).

`scripts/value_objects.py` aceita uma **domain-spec** (JSON) e emite esses VOs — records
com validação no compact constructor + fábricas — mais a exceção base, em **~2-3 min**,
de forma determinística e regenerável:

```bash
python scripts/value_objects.py examples/calendario-domain.json \
  -o ./calendario-lambda/src/main/java --aggregate
```

Arquétipos (`kind`): `string_pattern`, `bounded_string`, `enum`, `identifier`,
`local_date`, `local_time`, `time_range`, `integer_range`, `decimal`, `instant`. Cada um
nasce compatível com o gate Checkstyle estrutural e com `DomainException.code()` → RFC
9457; `--aggregate` também compõe o agregado rico (criar/rehydrate/copyWith/mutadores).

O **segundo** pedaço mecânico — o `@DynamoDbBean` (Item) + o mapper de chaves +
`toItem`/`toDomain` — sai de `scripts/single_table_mapper.py` a partir dos blocos
`aggregate` + `single_table` da mesma spec. E `generate_vanilla_lambda.py --domain-spec
<spec>` faz **tudo num comando**: rename do blueprint + VOs + Item/Mapper. O repositório
(access patterns) segue confirmado com o usuário, não gerado.

**Leia `references/domain-spec.md`** para o catálogo + schema + o fluxo de 1 comando.
Exemplos em `examples/` (dogfood: `calendario-domain.json` reproduz VOs **e** Item/Mapper
do `calendario-lambda`). Testes: `scripts/test_value_objects.py` +
`scripts/test_single_table_mapper.py` (stdlib `unittest`, zero-dep).
