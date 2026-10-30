# logs-observabilidade · reference — Mascaramento de dados sensíveis (antes → depois)

> Hub: `../SKILL.md`. Regras: LOG-02, LOG-05, LOG-25. Oráculo executável: `scripts/logs_obs/mascara.py`
> (`python lint_logs.py mascarar --texto "..."` mostra antes → depois). Base legal/normativa: LGPD art. 6º III
> (minimização) e 46 (segurança desde a concepção), PCI DSS v4.0.1 req. 3.4.1 (PAN mascarado: no máximo BIN + 4).

## 1. Estratégia em três camadas (todas, não uma)

| Camada | Onde | Ferramenta | Pega o quê |
|---|---|---|---|
| **1. Origem** (obrigatória) | serializer / `toString` / tipo | Jackson serializer, `record` com `toString` seguro, Lombok `@ToString.Exclude`, Pydantic `SecretStr`, classe `Mascara` | tudo que o dev **sabe** que é sensível |
| **2. Encoder/filtro** (rede) | appender | `MaskingJsonGeneratorDecorator` (logstash), `%replace`/`%maskedKvp`, `TurboFilter`, `logging.Filter`/structlog processor com `mascara.py` | o que escapou por engano (campo novo, `toString` de terceiro) |
| **3. Plataforma** (última linha) | destino | CloudWatch data protection policy, Datadog Sensitive Data Scanner | o que passou por 1 e 2 — e **cobra por GB** |

Só a camada 3 = incidente adiado: o dado já saiu do processo, já está no stdout, no agent, no buffer.

## 2. Formatos canônicos da Squad (contrato — `tests/test_logs_observabilidade.py` trava)

| Dado | Antes (sintético) | Depois | Regra |
|---|---|---|---|
| CPF | `529.982.247-25` | `***.982.247-**` | 6 dígitos centrais (padrão Receita); só mascara se o DV é válido |
| CNPJ | `11.222.333/0001-81` | `**.222.333/0001-**` | raiz oculta, filial visível |
| Cartão (PAN) | `4111 1111 1111 1111` | `**** **** **** 1111` | só 4 finais; `manter_bin=True` → `411111******1111` (PCI 3.4.1 máximo) só com necessidade de negócio documentada; só mascara se Luhn válido |
| E-mail | `thiago.silva@exemplo.com` | `t***********@exemplo.com` | 1º caractere + domínio (suporte reconhece, ninguém reconstrói) |
| Telefone | `+55 (83) 99999-1234` | `+55 (83) *****-1234` | DDD + 4 finais |
| Senha/segredo `k=v` | `senha=hunter2` | `senha=****` | some inteiro |
| Authorization | `Authorization: Bearer eyJ…` | `Authorization: Bearer [TOKEN:****6789]` | 4 finais para correlacionar com o IdP |
| JWT solto | `eyJhbGci….eyJzdWI….c2lu…` | `[JWT:****FrZQ]` | idem |
| AWS access key | `AKIAIOSFODNN7EXAMPLE` | `AKIA************MPLE` | prefixo + 4 finais (identifica a chave para rotação) |
| Credencial em URL | `postgres://app:S3nha@db:5432/x` | `postgres://app:****@db:5432/x` | |
| Chave privada PEM | `-----BEGIN RSA PRIVATE KEY-----…` | `[CHAVE_PRIVADA_REDIGIDA]` | bloco inteiro |

Princípios: **reconhecível** (o operador sabe que algo foi mascarado e de que tipo), **irreversível**, **validado**
(CPF/CNPJ por dígito verificador, PAN por Luhn + prefixo de bandeira — nunca corromper números de pedido,
timestamps ou UUIDs), **estável** (mesmo formato na origem, no encoder e na plataforma).

## 3. Java — implementação

### 3.1 Origem: tipo sabe se mascarar

```java
public record Cliente(String id, @Sensivel(Tipo.CPF) String cpf, @Sensivel(Tipo.EMAIL) String email) {
    @Override public String toString() {                       // record expõe TODOS os componentes por padrão
        return "Cliente[id=%s, cpf=%s, email=%s]".formatted(id, Mascara.cpf(cpf), Mascara.email(email));
    }
}
// Jackson (logs JSON e respostas): serializer por anotação
@JsonSerialize(using = MascaraSerializer.class) private String cpf;
// Lombok: @ToString(onlyExplicitlyIncluded = true) + @ToString.Include nos campos seguros
```
`Mascara` (utilitário de domínio, sem dependência): `cpf`, `cnpj`, `pan`, `email`, `telefone`, `token`/`ultimos4` —
mesmo formato da §2. Template: `templates/java/Mascara.java`.

### 3.2 Rede no encoder (logstash-logback-encoder)

```xml
<encoder class="net.logstash.logback.encoder.LogstashEncoder">
  <jsonGeneratorDecorator class="net.logstash.logback.mask.MaskingJsonGeneratorDecorator">
    <defaultMask>****</defaultMask>
    <path>password</path><path>senha</path><path>token</path><path>authorization</path>
    <path>*/cpf</path><path>*/cartao</path>                  <!-- por caminho: barato -->
    <valueMask><value>(\d{3})\.?\d{3}\.?\d{3}-?(\d{2})</value><mask>***.$1.***-**</mask></valueMask>
    <valueMasker class="exemplo.observabilidade.MascaraValueMasker"/>  <!-- delega ao Mascara (CPF/PAN validados) -->
  </jsonGeneratorDecorator>
</encoder>
```
"Prefer identifying data to mask by path" — regex por valor custa CPU em todo log; use para a rede, não como
estratégia principal. Template completo: `templates/java/logback-spring.xml` + `MascaraJsonDecorator.java`.

### 3.3 Layout de texto (local) e Log4j2

Logback: `%replace(%msg){'\d{3}\.?\d{3}\.?\d{3}-?\d{2}', '***.***.***-**'}`, `%maskedKvp{cpf,token}` (mascara
valores de KV pairs). Log4j2: `%replace{%msg}{regex}{subst}`. `MaskingPatternLayout` (classe custom estendendo
`PatternLayout` com `addMaskPattern`) é padrão comunitário (Baeldung) — "last line of defense".

### 3.4 Teste obrigatório

```java
@Test void log_nao_vaza_cpf() {
    var appender = new ListAppender<ILoggingEvent>(); appender.start();
    ((Logger) LoggerFactory.getLogger(PedidoService.class)).addAppender(appender);
    service.criar(new Cliente("u-1", "529.982.247-25", "ana@exemplo.com"), pagamento);
    assertThat(appender.list).allSatisfy(e -> assertThat(e.getFormattedMessage())
        .doesNotContain("529.982.247-25").doesNotContain("ana@exemplo.com").contains("***.982.247-**"));
}
```
Para o JSON final: `OutputCaptureExtension` (Spring) e asserção sobre o stdout serializado.

## 4. Python — implementação

```python
from logs_obs.mascara import mascarar_texto, sanitizar_para_log   # a mesma biblioteca do linter

class MascaraFilter(logging.Filter):                 # rede de segurança: mensagem, args e extras
    def filter(self, record):
        record.msg = mascarar_texto(str(record.msg))
        if record.args: record.args = tuple(mascarar_texto(str(a)) for a in record.args)
        for k, v in list(record.__dict__.items()):
            if isinstance(v, str) and k not in ("name", "levelname", "pathname", "filename", "module", "funcName"):
                record.__dict__[k] = mascarar_texto(v)
        return True
```
- Origem: `pydantic.SecretStr` (`repr` → `'**********'`, JSON `"**********"`, `get_secret_value()` explícito),
  `dataclass(repr=False)` + `__repr__` seguro.
- structlog: processor `(logger, method, event_dict)` que percorre `event_dict` e aplica `mascarar_texto`, antes do
  `JSONRenderer`.
- Template: `templates/python/logging_json.py` (JSON formatter + `MascaraFilter` + `correlation_id` por contextvar).

## 5. O que NUNCA mascarar "mais ou menos"

- Hash **não** é máscara para dado de baixa entropia (CPF tem 10⁹ valores: tabela arco-íris trivial) — use hash só
  com **salt secreto** (HMAC) e só se precisar correlacionar.
- Truncar o início do JWT (`eyJ***`) ainda expõe o header; mascare o token inteiro e guarde 4 finais.
- Não logue "o cliente X tem CPF iniciado por 529" — é inferência, ainda é dado pessoal.
- Dado anonimizado de verdade (LGPD art. 5º III/XI) não é reidentificável; mascarado **é** dado pessoal — retenção e
  acesso continuam valendo.

## 6. Checklist de mascaramento (review)

- [ ] Toda classe/record com campo sensível tem `toString`/serializer seguro ou `@ToString.Exclude` (camada 1).
- [ ] Log não recebe o objeto inteiro; recebe id + campo já mascarado (LOG-02).
- [ ] Encoder tem decorator/filtro de rede com os formatos da §2 (camada 2).
- [ ] Plataforma com policy/scanner ativos (camada 3, LOG-25) — e monitor "PII escapou".
- [ ] Teste automatizado prova "antes → depois" nos pontos que tocam PII (§3.4).
- [ ] Artefatos de log versionados (fixtures, snapshots) usam dados **sintéticos inválidos** (CPF `000.000.000-00`,
  PAN Luhn-inválido) — o gate LOG-04/05 varre `.log/.jsonl`.

## Fontes

- PCI DSS v4.0.1 req. 3.4.1 (masking PAN): https://www.pcisecuritystandards.org/document_library/ · LGPD: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm
- logstash-logback-encoder — Masking: https://github.com/logfellow/logstash-logback-encoder/blob/main/README.md#masking
- Logback layouts (`%replace`, `%maskedKvp`): https://logback.qos.ch/manual/layouts.html · Log4j2 pattern layout: https://logging.apache.org/log4j/2.x/manual/pattern-layout.html · Baeldung MaskingPatternLayout: https://www.baeldung.com/logback-mask-sensitive-data
- Jackson `@JsonSerialize`: https://javadoc.io/doc/com.fasterxml.jackson.core/jackson-databind/latest/com/fasterxml/jackson/databind/annotation/JsonSerialize.html · Lombok `@ToString`: https://projectlombok.org/features/ToString · `Record.toString()`: https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/lang/Record.html#toString()
- Python logging cookbook (Filter muta LogRecord): https://docs.python.org/3/howto/logging-cookbook.html · structlog processors: https://www.structlog.org/en/stable/processors.html · Pydantic `SecretStr`: https://pydantic.dev/docs/validation/latest/api/pydantic/types/
- CloudWatch data protection / Datadog SDS: ver `cloudwatch.md` §5 e `datadog.md` §4
