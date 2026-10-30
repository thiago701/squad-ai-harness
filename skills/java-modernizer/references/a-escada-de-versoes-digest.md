# java-modernizer · A Escada de Versões (digest)

> Reference da skill `java-modernizer` (movida da SKILL.md em 11/10/2026 — hub + references, I3). Carregue só quando a tarefa pedir este tema.

## A Escada de Versões (digest)

A ordem de prioridade pedida — Java 25 → 21 → 17 → 14/11/8. Para cada recurso, **o condicional que ele mata**. O catálogo completo, com antes/depois de código para cada item, está em `references/jdk-version-ladder.md` — **leia esse arquivo sempre que a tarefa envolver escolher o recurso certo para uma versão específica.**

| Versão | Recurso (status) | Condicional que elimina |
|---|---|---|
| **25 ⭐** | Flexible Constructor Bodies (final) | Validação tortuosa em construtor — guard clause agora vem antes de `super()`/`this()` |
| **25** | Module Import Declarations (final) | Muro de `import` (cerimônia, P1) |
| **25** | Scoped Values (final) | `ThreadLocal` + lógica defensiva de `remove()`/null em concorrência |
| **25 ⚠️** | Primitive Type Patterns (**preview**) | Cadeias de range-check (`if i>=400 && i<500`) — requer `--enable-preview` |
| **25 ⚠️** | Stable Values (**preview**) | Lazy-init `if (x == null) x = ...` e double-checked locking |
| **21 ⭐⭐** | Pattern Matching for switch + `when` (final) | Cadeias `if/else-if/instanceof` de dispatch por tipo |
| **21** | Record Patterns (final) | Getters aninhados + null checks (`a.getB().getC()`) |
| **21** | Sealed + switch exaustivo (final) | `default` defensivo e o bug do "esqueci um caso" |
| **21** | Sequenced Collections (final) | `list.get(list.size()-1)` e checagens de borda |
| **17** | Sealed Classes (final) | Hierarquia aberta que força ramo `default` defensivo |
| **17** | Pattern Matching for instanceof (final) | `instanceof` seguido de cast manual verboso |
| **17** | Records (final) | Boilerplate de DTO (getters/equals/hashCode) e dados mutáveis |
| **17** | Switch Expressions (final) | `switch`-statement com `break` e fall-through acidental |
| **14** | Helpful NPE messages | Tempo perdido depurando qual variável era null |
| **11** | String API (isBlank/strip/lines/repeat) | Checagens manuais de whitespace e loops de StringBuilder |
| **8 ⭐** | Optional | `if (x != null)` — o antipadrão que mais aparece |
| **8 ⭐** | Streams | `for` + `if` para filtrar/mapear/reduzir listas |
| **8** | Lambdas + method refs | Anonymous-class boilerplate; viabiliza Strategy enxuto |

> **Correção crítica que protege a squad:** o material de origem dizia "Pattern Matching para switch (Java 17+)". Em produção isso é **enganoso** — no JDK 17 o recurso era *preview* (JEP 406) e exigia `--enable-preview`. Ele só virou **final no JDK 21** (JEP 441), junto com Record Patterns (JEP 440). Se a squad mira exaustividade real de `switch` sobre `sealed`, a **versão-alvo de produção é 21**, não 17.

---
