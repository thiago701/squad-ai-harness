# validacao-veracode · reference — Remediação reconhecida pelo Veracode e mitigação gated

> Parte da skill `validacao-veracode`. Carregue sob demanda. Hub: `../SKILL.md`.
> Fontes: docs.veracode.com — `/r/review_cleansers`, `/r/Supported_Java_Cleansing_Functions`,
> `/r/customcleansers`, `/r/t_annotate_java`, `/r/About_Veracode_Fix` (consultadas em 2026-10).
> **A lista oficial de cleansers muda por versão do engine** — confira a página antes de depender
> de uma função específica.

## 1. Cleansers que o Veracode reconhece (Java — amostra verificada)

O Static Analysis rastreia o fluxo do dado; quando ele passa por uma função de limpeza **suportada**
para aquela classe de CWE, o flaw não é aberto. Exemplos documentados:

| CWE | Funções suportadas (exemplos) |
|---|---|
| 80 (XSS) | `org.owasp.encoder.Encode.forHtml` (e variantes de contexto), `org.springframework.web.util.HtmlUtils.htmlEscape`, `org.owasp.esapi.Encoder.encodeForHTML`, `com.google.gwt.safehtml.shared.SafeHtmlUtils.htmlEscape` |
| 93 · 113 · 117 (CRLF / response splitting / log) | `java.net.URLEncoder.encode`, `org.apache.commons.codec.net.URLCodec.encode` e outras da página oficial |
| 90 (LDAP) | `org.owasp.esapi.Encoder.encodeForLDAP`, `encodeForDN` |
| 73 (caminho) | **padrão** de file-path cleanser: valida o caminho contra um diretório-base permitido e devolve `java.io.File`/`java.nio.file.Path` validado |

Regra prática: **encoding certo para o contexto de saída**. `encodeForHTML` num valor que vai para
SQL não fecha nada — e o Veracode sabe disso.

## 2. Cleansers customizados — anotações `VeracodeAnnotations`

Quando a validação é do próprio time, anote o método para o scanner reconhecê-lo:

```xml
<dependency>
  <groupId>com.veracode.annotation</groupId>
  <artifactId>VeracodeAnnotations</artifactId>
  <version>1.0.4</version> <!-- doc: [1.0.4,) — fixe a versão (build reprodutível) -->
</dependency>
```

| Anotação | Mitiga |
|---|---|
| `@CRLFCleanser` | CWE-93, 113, 117 |
| `@FilePathCleanser` | CWE-73 |
| `@RedirectURLCleanser` | CWE-601 |
| `@SQLQueryCleanser` | CWE-89 |
| `@XSSCleanser` | CWE-80 |

.NET tem o equivalente em atributos (`veracode-attributes`). Python/JS/TS: não há anotação —
corrija no código ou mitigue por design com evidência.

```java
import com.veracode.annotation.CRLFCleanser;
import com.veracode.annotation.FilePathCleanser;

public final class Saneamento {
    private Saneamento() {}

    @CRLFCleanser(userComment = "Substitui todo caractere de controle (inclui CR/LF/TAB) antes de logar — CWE-117")
    public static String paraLog(String valor) {
        return valor == null ? null : valor.replaceAll("\\p{Cntrl}", "_");
    }

    @FilePathCleanser(userComment = "Resolve contra a base, normaliza e exige permanecer dentro dela — CWE-73")
    public static Path dentroDe(Path base, String nome) {
        Path raiz = base.toAbsolutePath().normalize();
        Path alvo = raiz.resolve(nome).normalize();
        if (!alvo.startsWith(raiz)) throw new SecurityException("caminho fora da base");
        return alvo;
    }
}
```

**Como o Veracode trata:** o Security Lead define o *estado padrão de mitigação* para achados cujo
dado passou por cleanser customizado; se **qualquer** entrada não tratada chegar ao ponto do flaw,
ele continua reportado.

### Uso honesto (inegociável)

1. O método **neutraliza de verdade** a classe de CWE da anotação — `trim()`, `toLowerCase()` ou
   "valida tamanho" **não** neutralizam CRLF/SQL/XSS.
2. Tem **teste unitário** provando a neutralização (inclui `\r\n`, `../`, `<script>`, `' OR 1=1`).
3. `userComment` diz **o que** é neutralizado e **por quê** — vira evidência de auditoria.
4. Toda anotação nova ou alterada é **mudança sensível de segurança** no review: o `tech-lead-review`
   trata cleanser de fachada como 🔴 (evidência falsa de mitigação).

## 3. Veracode Fix — sugestão, nunca auto-merge

- Gera até 5 patches por flaw, a partir de resultados do **Pipeline Scan** (não do Upload & Scan).
- É IA: o patch pode compilar e não corrigir, ou corrigir e quebrar comportamento.
- Fluxo gated: humano revisa o diff → testes verdes → re-roda V3–V5 → merge só com o gate verde.

## 4. Mitigação — quando corrigir não é possível agora

| Tipo (Veracode) | Use quando | Evidência mínima |
|---|---|---|
| Mitigate by Design | controle no código/arquitetura impede o ataque (ex.: CSRF off em API só-Bearer) | trecho do controle + teste que prova |
| Mitigate by Network Environment | controle de rede impede o vetor (ex.: endpoint só em VPC privada) | diagrama/regra de SG/WAF + dono da regra |
| Mitigate by OS Environment | controle do SO/runtime impede o vetor | configuração versionada + verificação |
| Potential False Positive | o scanner errou o fluxo | caminho do dado mostrando que não é externo |
| Reported to Library Maintainer | flaw em dependência sem correção disponível | issue/CVE + plano de troca/upgrade |
| Accept the Risk | negócio aceita o risco residual | **decisão humana** do dono do risco (`quality/quality-gates.md` §7.3) |

**Regras do gate:** só mitigação **APPROVED** remove o flaw do veredito; `PROPOSED`/`REJECTED`
continuam abertos. **Aprovador ≠ autor.** Mitigação expira com a mudança do código afetado.

### Template de evidência (cole na proposta de mitigação)

```markdown
**Flaw:** CWE-<id> <nome> — <arquivo>:<linha> (issue_id <n>)
**Tipo:** Mitigate by Design | Network | OS | Potential False Positive | Library Maintainer
**Por que não é explorável:** <fluxo do dado, da origem ao ponto do flaw>
**Controle compensatório:** <onde está, link do código/config>
**Prova:** <teste automatizado / evidência reproduzível>
**Revisor (≠ autor):** <nome> · **Revalidar em:** <data ou gatilho de mudança>
```

## 5. Supressão do pré-scan (auditável)

Para falso-positivo **do pré-scan** (heurística), não do Veracode:

```java
// veracode-precheck: ignorar J-RAND-01 motivo=jitter de retry; sem uso criptográfico
long atraso = base + new Random().nextInt(250);
```

- Sem `motivo=` a supressão é ignorada e o achado continua (marcado no título).
- Toda supressão aparece na seção "Supressões" do relatório — o revisor vê e pode recusar.
- Supressão do pré-scan **não** mitiga nada no Veracode: se o scan real abrir o flaw, vale o §4.
