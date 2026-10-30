# java-modernizer · Padrões GoF vs. o `if` (quando o ramo carrega comportamento)

> Reference da skill `java-modernizer` (movida da SKILL.md em 11/10/2026 — hub + references, I3). Carregue só quando a tarefa pedir este tema.

## Padrões GoF vs. o `if` (quando o ramo carrega comportamento)

A pergunta-chave que roteia a decisão: **o `switch`/`if` está escolhendo um VALOR ou um COMPORTAMENTO?**
- Escolhe **valor** (um número, uma string, um enum) → muitas vezes um `switch` expression ou um `Map` resolve, sem padrão GoF.
- Escolhe **comportamento** (qual cálculo rodar, qual regra aplicar) → é território de polimorfismo.

### Strategy — dispatch por tipo de regra
Em vez de um `switch` gigante decidindo qual imposto aplicar (`ICMS`, `ISS`, ...), crie uma interface `Imposto` e implementações `ImpostoIcms`, `ImpostoIss`. O Java despacha por polimorfismo. Adicionar um imposto novo = nova classe, zero modificação no motor (OCP respeitado). Para famílias pequenas e fixas, um `enum` que implementa a interface é a forma mais enxuta (P1) — veja o exemplo de fretes em `references/transformation-catalog.md`.

### State — comportamento que muda com o status do objeto
Se o comportamento muda conforme o estado (`Pedido` em `Rascunho`, `Pago`, `Enviado`) e você acaba com `if (status == ...)` espalhado por vários métodos, o State Pattern transforma cada estado numa classe que sabe se comportar e sabe para qual estado transicionar. Mata a duplicação dos `if (status)` espalhados. **Trade-off (P1):** para uma máquina de 2-3 estados com uma transição cada, um `switch` expression sobre um `enum` é mais simples — só vá para State quando os estados têm *múltiplos* comportamentos divergentes.

### Factory — criação condicional
`if (tipo == X) return new A()` repetido vira uma factory (ou `Map<Tipo, Supplier<T>>`). Centraliza a decisão de criação em um lugar.

> No JDK 21+, **Sealed + Pattern Matching de `switch`** é frequentemente a alternativa mais simples (P1) ao Strategy clássico para dispatch fechado: o compilador garante exaustividade e o código fica num único ponto legível. Use Strategy quando o conjunto é *aberto/extensível por terceiros*; use sealed+switch quando é *fechado e conhecido*.

---
