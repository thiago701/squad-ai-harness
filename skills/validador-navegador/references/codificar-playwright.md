# Roteiro de Handoff para Playwright + Ressalva de CI

> **Quando ler:** depois de confirmar um fluxo PRONTO ao vivo, para montar o **roteiro de handoff** que o `especialista-qualidade` vai codificar como teste durável — e para entender por que a validação ao vivo **não substitui** a suíte de CI.
> **Propriedade:** esta skill **não autora nem mantém** a suíte Playwright — ela **entrega o roteiro** (e, no máximo, um **rascunho**). A autoria, o POM definitivo, o mutation testing e o CI são do `especialista-qualidade`. O material abaixo é **insumo de handoff**, não tarefa desta skill.
> **Princípio:** validação ao vivo é **volátil** (prova o agora); o teste Playwright é **permanente** (prova para sempre, no CI). O ganho real é o loop **explorar → confirmar → entregar roteiro** (a codificação acontece do outro lado da ponte).

---

## 1. Por que codificar

A sessão de navegador que você acabou de rodar morre com o contexto. Se a jornada é **crítica** (login, checkout, criação de recurso, um bug que você acabou de reproduzir), ela precisa virar um teste que roda em toda PR. Assim a validação exploratória **compõe**: o achado de hoje é a regressão barrada amanhã.

**O que codificar:** jornadas críticas confirmadas; todo bug reproduzido (vira teste de regressão permanente — 8º eixo do `especialista-qualidade`); fluxos de formulário com validação.
**O que NÃO codificar:** checagem pontual/descartável; exploração que não representa contrato de negócio; algo já coberto pela suíte.

> A **autoria** do teste é do `especialista-qualidade` (dono da suíte, POM, mutation, CI). Esta skill **entrega o roteiro confirmado** (passos + seletores + asserções observadas) para ele codificar — ou gera o rascunho e passa para revisão.

---

## 2. Mapeamento — ação ao vivo → código Playwright

| Ação exploratória | Playwright durável |
|---|---|
| `preview_start("web")` | `page.goto(baseURL)` (webServer no config) |
| `preview_snapshot` → achou role/name | `page.getByRole('button', { name: 'Entrar' })` |
| `preview_fill("#email", "x")` | `page.getByLabel('E-mail').fill('x')` |
| `preview_click("[data-testid=salvar]")` | `page.getByTestId('salvar').click()` |
| asserção de estado via novo snapshot | `await expect(page.getByText('Comprar café')).toBeVisible()` |
| `preview_console_logs level:error` = 0 | listener `page.on('console', ...)` falha em erro |
| `preview_network filter:failed` = 0 | `page.on('response', r => expect(r.status()).toBeLessThan(400))` |

Prefira **seletores semânticos/`data-testid`** aos seletores frágeis de CSS/estrutura. Se a UI não tem `data-testid` nos pontos-chave, **recomende adicioná-los ao fonte** (dívida barata que estabiliza todo E2E) — tarefa do `especialista-frontend`.

---

## 3. Padrão canônico — Page Object Model

```ts
// tests/e2e/pages/TarefasPage.ts
import { Page, expect } from '@playwright/test';

export class TarefasPage {
  constructor(private page: Page) {}
  async login(email: string, senha: string) {
    await this.page.getByLabel('E-mail').fill(email);
    await this.page.getByLabel('Senha').fill(senha);
    await this.page.getByRole('button', { name: 'Entrar' }).click();
    await expect(this.page.getByRole('heading', { name: 'Minhas Tarefas' })).toBeVisible();
  }
  async criarTarefa(titulo: string) {
    await this.page.getByTestId('nova-tarefa').click();
    await this.page.getByLabel('Título').fill(titulo);
    await this.page.getByTestId('salvar').click();
    await expect(this.page.getByText(titulo)).toBeVisible();
  }
}
```

```ts
// tests/e2e/tarefas.spec.ts
import { test, expect } from '@playwright/test';
import { TarefasPage } from './pages/TarefasPage';

test('jornada: login → criar → concluir', async ({ page }) => {
  const erros: string[] = [];
  page.on('console', m => { if (m.type() === 'error') erros.push(m.text()); });   // Eixo 4
  page.on('response', r => { if (r.status() >= 400) erros.push(`${r.status()} ${r.url()}`); }); // Eixo 5

  const app = new TarefasPage(page);
  await page.goto('/');
  await app.login('teste@exemplo.dev', 'senha-de-teste-123');   // dados de TESTE
  await app.criarTarefa('Comprar café');
  await page.getByTestId('concluir-0').click();
  await expect(page.getByTestId('concluir-0')).toHaveAttribute('aria-checked', 'true');

  expect(erros, `console/rede limpos: ${erros.join(' | ')}`).toHaveLength(0);
});
```

Config essencial (`playwright.config.ts`): `trace: 'on-first-retry'`, `screenshot: 'only-on-failure'`, `video: 'retain-on-failure'`, e `webServer` subindo o app — para o CI reproduzir o mesmo alvo que você validou ao vivo. Os **traces** dão o replay time-travel de uma falha (equivalente durável do seu `gif_creator`).

---

## 4. Handoff ao `especialista-qualidade`

1. Entregue o **roteiro confirmado**: passos, seletores usados, asserções observadas (DOM/console/rede), viewport.
2. Local canônico: `tests/e2e/` (POM em `tests/e2e/pages/`).
3. O teste entra na **camada E2E** (5% do topo da pirâmide — só jornadas críticas; não infle).
4. Roda no CI headless: `npx playwright test` (ver ressalva abaixo).
5. Todo **bug reproduzido** vira um `test(...)` de regressão antes do fix ser considerado completo.

---

## §CI — a validação ao vivo NÃO é o oráculo de CI (fail-closed)

Distinção que não pode ser confundida:

| | Validação ao vivo (esta skill) | Suíte Playwright (CI) |
|---|---|---|
| Executor | agente dirigindo browser (`preview_*` / `claude-in-chrome`) | `npx playwright test` headless |
| Quando | dev-time, GATE 2, reproduzir bug | toda PR, automático |
| Depende de | **um browser conectado ao harness** | runner com Chromium instalado (`npx playwright install`) |
| Prova | "funciona agora, para mim" | "funciona sempre, para todos" |

- **Fail-closed:** se o instrumento de navegador não está disponível (sem browser conectado no `claude-in-chrome`; sem dev server que suba), **reporte INDISPONÍVEL — não PRONTO**. Ausência de validação nunca vira aprovação.
- A validação ao vivo **complementa**, não substitui, a suíte durável. O GATE 2 quer as duas: `verificacao-loop` (que roda a suíte headless) **e**, para mudança de navegador, o veredito ao vivo desta skill.
- Em CI headless puro (sem browser interativo), a validação ao vivo pode ser pulada com nota explícita; a cobertura E2E fica com a suíte Playwright. **Registre o que foi pulado** — silêncio lê como "validei tudo".

> Ressalva de ambiente: o toolset `claude-in-chrome` pode não existir em execução headless/cron. Se a tarefa exige validação ao vivo e o instrumento falta, pare e diga — não simule um veredito.
