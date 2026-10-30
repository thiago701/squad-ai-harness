# Review de Java/Spring no nível micro — clean code aplicado

> **Padrões absorvidos** (não código) de três skills externas de alta reputação, recriados em PT-BR
> para a stack do Squad AI. Crédito e licenças em [`docs/ATTRIBUTIONS.md`](../../docs/ATTRIBUTIONS.md):
> `piomin/claude-ai-spring-boot` (Apache-2.0, ⭐1.2k), `awesome-skills/code-review-skill` (MIT),
> `jdubois/dr-jskill`. Conceitos/padrões de design não são protegidos por copyright; citamos por boa prática.
>
> Combina com [`smells-catalog.md`](smells-catalog.md), [`functions.md`](functions.md),
> [`classes.md`](classes.md) e a skill `java25-spring-boot` (sintaxe/recursos Java 25).

## 1. Taxonomia de severidade do review (6 rótulos)

O Squad já usa 🔴/🟡/🔵 (e a escala de objetivos no `/review`). Para review de **código** (PR), absorvemos
o modelo de 6 rótulos do `code-review-skill` — ele acrescenta dois sinais que faltavam: **aprendizado** e
**elogio**. Marque TODO achado com um deles:

| Rótulo | Quando | Bloqueia merge? |
|---|---|---|
| 🔴 `blocking` | bug, falha de segurança, quebra de contrato | Sim |
| 🟠 `important` | risco real de manutenção/performance; corrigir | Depende do contexto |
| 🟡 `nit` | estilo/preferência menor | Não |
| 🔵 `suggestion` | melhoria opcional que vale considerar | Não |
| 📚 `learning` | nota educativa para o autor (o porquê) | Não |
| 🌟 `praise` | destacar explicitamente o que ficou bom | Não |

> `blocking`/`important` mapeiam para 🔴/🟡 do RULES.md; `learning`/`praise` são a novidade absorvida —
> review que só aponta defeito corrói o time. Elogie o que merece e ensine o porquê.

## 2. Processo de review em 4 fases

Não revise linha-a-linha de cara. Suba o nível de abstração primeiro (absorvido do `code-review-skill`):

1. **Contexto** — entenda o escopo do PR, a issue ligada e a intenção. Sem isso, todo comentário vira chute.
2. **Alto nível** — arquitetura, impacto de performance, estratégia de teste. Um design errado torna o
   review linha-a-linha desperdício.
3. **Linha a linha** — lógica, segurança, manutenibilidade, casos de borda.
4. **Resumo & decisão** — feedback estruturado, status de aprovação, itens de ação claros.

**Consciência de automação:** não gaste review humano no que o linter/formatter pega (formatação, import order).
Foque no que só um humano vê: intenção, design, corretude, segurança. (Ver [`formatting.md`](formatting.md).)

**Tom colaborativo:** pergunta > comando; sugestão > mandato. "O que acha de extrair isto?" rende mais que
"extraia isto".

## 3. Checklist de clean code Java/Spring/JPA

Absorvido de `piomin/claude-ai-spring-boot` (skills `clean-code`, `java-code-review`, `jpa-patterns`) e do
guia Java do `code-review-skill`. Para sintaxe/recursos, encaminhe à skill `java25-spring-boot`.

### Java moderno (legibilidade e intenção)
- **Records** para DTOs/value objects imutáveis — elimina boilerplate de `equals`/`hashCode`/getters.
- **Sealed classes + pattern matching for switch** para hierarquias fechadas — torna o domínio explícito e o
  compilador exige exaustividade.
- **Text blocks** para SQL/JSON inline em vez de concatenação ilegível.
- **Optional** no retorno (nunca em campo/parâmetro); não chame `.get()` sem `isPresent`/`orElse`.

### Spring Boot (acoplamento e configuração)
- **Injeção por construtor** (campos `final`), nunca `@Autowired` em campo — testável e à prova de nulos.
- **`@ConfigurationProperties`** tipado em vez de `@Value` espalhado.
- **`ProblemDetail`** (RFC 7807) para erros de API; sem vazar stack trace na resposta.
- Camadas honestas: controller fino → service com a regra → repository. Regra de negócio não mora no controller.

### JPA/persistência (o que mais gera bug sutil)
- **N+1**: o defeito clássico. Use `JOIN FETCH`/`@EntityGraph`; desconfie de `LAZY` iterado em loop. (📚 explique o porquê ao autor.)
- **`equals`/`hashCode` em entidade**: baseie em **id de negócio**, nunca no `@Id` gerado (que é null antes do persist) nem em todos os campos. Records não servem como `@Entity`.
- Evite `FetchType.EAGER` por padrão; prefira projeção por **DTO** quando não precisa da entidade gerenciada.
- Transação no **service**, no menor escopo; nada de `@Transactional` no controller.

### Tratamento de erro & logging
- Não engula exceção (`catch` vazio) nem use exceção para fluxo de controle. (Ver [`error-handling.md`](error-handling.md).)
- **Logging estruturado** (chave-valor), sem PII/segredo em log (cruza com `engenheiro-seguranca`, OBJ-1).

### Testes
- Nome do teste descreve comportamento; um conceito por teste; AAA. (Ver [`tests.md`](tests.md).)
- Testcontainers para integração real de JPA quando o risco justificar.

## 4. Saída do review

Sempre termine pela Fase 4: um resumo com o **status** (aprovar / aprovar com ressalvas / bloquear), os achados
agrupados por severidade, e itens de ação acionáveis. Sem isto, o autor não sabe o que fazer.

---
> **Proveniência:** padrões absorvidos e reescritos; nenhum arquivo externo foi copiado. Antes de adotar
> qualquer conteúdo NOVO destas fontes, passe pela `auditoria-skill-externa` (supply chain, RULES.md A10).
