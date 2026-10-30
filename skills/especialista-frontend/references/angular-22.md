# Angular 22 — fatos de versão (verificado jul/2026)

> Fonte: angular.dev/reference/releases · blog.angular.dev · github.com/angular/angular/releases.
> Absorvido pelo Skill Harvester em 2026-07-15. Revalidar a cada major (mai/nov).

## Linha do tempo / suporte

| Versão | Situação (jul/2026) | EOL |
|---|---|---|
| Angular 22 | **Estável atual** — 22.0.6 (jul/2026) | ~mai/2027 (LTS) |
| Angular 21 | Suportada | 2027-05-19 |
| Angular 20 | Suporte terminando | 2026-11-28 |

Cadência: **2 majors/ano** (maio e novembro). v20 = mai/2025, v21 = nov/2025, v22 = mai/2026.

## Angular 22 — destaques ("Signal-First Era")

- **Signal Forms estáveis** — formulários tipados, signal-driven; substituem padrões verbosos de
  Reactive Forms com modelo de estado reativo.
- **Selectorless components (estável)** — importar componentes diretamente no template, sem seletor
  string; ganho de type-safety e refatorabilidade em larga escala.
- **OnPush por padrão** — componentes novos usam `ChangeDetectionStrategy.OnPush` por padrão.

## Base estável herdada (v20/v21 → use à vontade)

- **Signals estáveis:** `signal`, `computed`, `input`, view queries, `effect`, `linkedSignal`, `toSignal`.
- **`resource()` e `httpResource()`** para dados assíncronos reativos baseados em signal.
- **Zoneless change detection** avançando (developer preview → estável); **incremental hydration** estável.
- Standalone components como default (sem NgModules), `inject()`, control flow `@if/@for/@switch`,
  `@defer` para lazy loading de template. Integração com Chrome DevTools (relatórios Angular).

## Armadilhas / migração

- **Signal Forms ≠ Reactive Forms:** APIs diferentes; migrar por tela, não em massa.
- **OnPush por padrão** exige disciplina de imutabilidade/signals — código que mutava objeto e
  dependia de checagem default pode parar de atualizar a view.
- **Zoneless:** remover `zone.js` exige que todo estado que dispara render seja signal/async pipe.
- Use `ng update` (schematics oficiais) para subir de major; rode em branch e valide bundle budgets.

## Ferramentas do ecossistema (2026)

- CLI Angular (`ng`), esbuild/Vite como builder, SSR/hydration nativos.
- Estado: Signals nativos + **NgRx Signals** quando precisar de store. TypeScript 7 (ver `typescript-pro`).
- Teste: Vitest/Jest + Testing Library; e2e Playwright. Validar UI ao vivo no navegador (`validador-navegador`).
