# rules/angular/performance.md — Invariantes de performance Angular 21+

> **Always-on:** só o que é *sempre* preferível para performance frontend. Profiling, budgets finos,
> Web Vitals e otimização caso a caso vivem na skill **`especialista-frontend`**.
> **Arbitragem:** P1‑Simplicidade > P2‑Performance > P3. Otimize quando há meta/medida — não no escuro.
> Idiomas gerais (Signals, control flow, strict): [`idiomas.md`](idiomas.md).

---

## Sempre

- **Lazy loading de rotas** (`loadComponent` / `loadChildren`). Nenhuma feature pesada no bundle inicial.
- **`@defer`** para o que é caro ou está abaixo da dobra (gráficos, editores, mapas, listas longas) —
  com `on viewport` / `on idle` / `on interaction` e *placeholder*/*loading*. Reduz o JS do caminho crítico.
- **`@for` com `track`** por chave estável (id), nunca `$index` quando há identidade. Evita re-render total.
- **`OnPush` + mire zoneless.** Signals + OnPush = detecção mínima; sem CD global desnecessária.
  Evite trabalho pesado em `computed`/getters de template (rodam a cada CD).
- **Bundle budget no `angular.json`** configurado e tratado como gate: estouro = build falha (🟡→🔴 em CI).
  Cheque com `source-map-explorer`; corte dependência pesada antes de aceitá-la (P3).
- **Imagens otimizadas:** diretiva **`NgOptimizedImage`** (`ngSrc`), dimensões explícitas, `priority` no LCP,
  formatos modernos (AVIF/WebP), *lazy* por padrão. Imagem é causa nº 1 de LCP ruim.
- **SSR + hydration** (incl. *incremental hydration* com `@defer (hydrate …)`) quando TTI/SEO importam.
- **Não bloqueie a thread principal:** debounce/throttle em input/scroll; trabalho pesado fora do render
  (Web Worker quando justificar). `async` pipe em vez de subscribe manual (sem leak).
- **Pré-carregue com critério:** `PreloadAllModules` só se o ganho compensar o tráfego (P3), senão seletivo.

---

> **Otimização guiada por medida.** Sem número (Web Vital/budget), prefira a versão mais simples (P1).
> Para profiling e tuning real, use a skill **`especialista-frontend`**.
