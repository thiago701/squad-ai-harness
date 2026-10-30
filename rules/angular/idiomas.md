# rules/angular/idiomas.md — Idiomas always-on de Angular 21+ + TypeScript

> **Natureza:** conhecimento **always-on** — curto, barato, sempre verdadeiro. Aqui ficam só os
> **invariantes** (o que é *sempre* preferível). O detalhe operável (código completo, microfrontends,
> NgRx Signals, design system, a11y profunda) vive na skill **`especialista-frontend`** — invoque-a
> para gerar/avaliar código. Não duplique a skill; destile.
> **Arbitragem:** P1‑Simplicidade > P2‑Performance > P3‑CustoBaixo · segurança nunca negociável.

---

## 1. Componentes e estrutura (sempre)

- **Standalone por padrão.** Componentes/diretivas/pipes `standalone: true`; **sem `NgModule`**. NgModule
  só em legado em migração — e a direção é sempre *remover* módulo, nunca criar.
- **`inject()` em vez de DI por construtor** quando aplicável (funções, guards, resolvers, herança). Construtor
  fica para o que exige ordem de inicialização explícita.
- **Um componente, uma responsabilidade.** Lógica de domínio em serviços/stores, não no componente (P1).
- **Arquivos pequenos e coesos.** Template/estilo inline só quando triviais; senão arquivos separados.

## 2. Reatividade e estado (sempre)

- **Signals como fonte de estado reativo.** `signal` / `computed` / `effect` para estado local e derivado.
  `effect` só para *sincronizar com o mundo externo*, nunca para derivar estado (use `computed`).
- **`input()` / `output()` / `model()` de função** em vez de `@Input()/@Output()` decorator.
- **RxJS só onde agrega** — fluxos assíncronos genuínos (eventos, streams, debounce, cancelamento). Estado
  síncrono simples não vira `Observable`. Converta na borda com `toSignal()/toObservable()`.
- **`async` pipe** no template em vez de `subscribe()` manual; sem subscription órfã (memory leak).

## 3. Templates — novo control flow (sempre)

- **`@if` / `@for` / `@switch`** em vez de `*ngIf` / `*ngFor` / `[ngSwitch]`. Diretivas estruturais legadas
  são proibidas em código novo.
- **`@for` exige `track`** (chave estável; nunca `$index` se houver id). Sem `track` adequado = 🟡.
- **`@defer`** para conteúdo pesado/abaixo da dobra (detalhe em `performance.md`).

## 4. Detecção de mudança e renderização (sempre)

- **`ChangeDetectionStrategy.OnPush` por padrão** em todo componente.
- **Mire zoneless** (`provideZonelessChangeDetection()` / sem `zone.js`); Signals + OnPush tornam isso natural.
- **SSR/hydration** quando houver SEO/TTI relevante — *non-destructive hydration*, sem flicker.

## 5. Roteamento (sempre)

- **Lazy loading de rotas** via `loadComponent` / `loadChildren` — nunca import estático de feature pesada.
- **Functional guards/resolvers** (`CanActivateFn` etc.) com `inject()`, não classes.

## 6. TypeScript (sempre)

- **`strict: true`** (e `strictTemplates` no Angular). Não relaxar flags para "passar".
- **Proibido `any`.** Use `unknown` + narrowing, generics ou tipos próprios. `any` em código novo = 🟡.
- **Tipos explícitos em fronteiras públicas** (assinaturas de serviço, contratos de API/DTO). Inferência
  interna é bem-vinda; contrato exposto é declarado.
- **`readonly` e imutabilidade** por padrão; evite mutação de estado compartilhado.
- **Sem `non-null assertion` (`!`) gratuito** mascarando modelo de dados frágil.

## 7. Acessibilidade (a11y) — requisito, não enfeite

- **a11y é critério de aceite**, não polimento opcional. HTML semântico primeiro; ARIA só quando o semântico
  não cobre. Foco visível, navegação por teclado, `alt`/labels, contraste mínimo (WCAG AA).
- Acessibilidade quebrada em fluxo principal = 🟡 (bloqueia merge ou exige exceção registrada).

## 8. Segurança (sempre — nunca negociável)

- **Nunca usar `bypassSecurityTrust*`** sem justificativa auditada; HTML externo é não confiável.
- **Sem segredos no bundle** (chaves/tokens). Config sensível vem do backend, não de `environment.ts` versionado.

---

> **Para gerar/avaliar código frontend de verdade, use a skill `especialista-frontend`.**
> Performance frontend tem arquivo próprio: [`performance.md`](performance.md).
