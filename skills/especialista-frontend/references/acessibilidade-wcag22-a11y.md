# Acessibilidade Digital Universal (WCAG 2.2 AA / AAA) e Engenharia Inclusiva

> **Quando ler:** durante o design, implementação e auditoria de qualquer componente, tela ou jornada no frontend.
> **Princípio imutável:** acessibilidade não é recurso opcional, checklist de última hora ou polimento tardio. É um requisito funcional primário e inegociável. Componente inacessível é defeito bloqueante (🔴).

---

## 1. O Padrão WCAG 2.2 (Atualizado e Vigente)

O **Web Content Accessibility Guidelines (WCAG) 2.2** expande a acessibilidade para cobrir com profundidade usuários com baixa visão, deficiências motoras e déficits cognitivos. Todo código produzido pela Squad deve atingir conformidade estrita no nível **AA** (com aspiração a **AAA** em áreas críticas).

### Novos Critérios Chave do WCAG 2.2:

| Critério | Nível | Nome | Requisito Técnico Obrigatório |
|---|---|---|---|
| **2.4.11** | AA | **Focus Not Obscured (Minimum)** | O componente em foco de teclado NUNCA deve ficar totalmente oculto por elementos fixos (headers, banners flutuantes, modais ou toasts). Use `scroll-padding-top` e `scroll-margin-top`. |
| **2.4.12** | AAA | **Focus Not Obscured (Enhanced)** | Nenhuma parte do elemento em foco pode ficar oculta por outro conteúdo. |
| **2.4.13** | AA | **Focus Appearance** | O indicador de foco deve ter área mínima definida, contraste de pelo menos **3:1** entre o estado de foco e desfoco, e contraste de pelo menos **3:1** contra o fundo adjacente. |
| **2.5.7** | AA | **Dragging Movements** | Toda funcionalidade operada por arrasto (drag and drop, sliders, reordenação de listas) deve fornecer uma alternativa acessível operada por clique único ou teclado (ex: botões "Mover para cima" / "Mover para baixo"). |
| **2.5.8** | AA | **Target Size (Minimum)** | O tamanho mínimo do alvo de toque/clique deve ser de pelo menos **$24 \times 24\text{px}$**, exceto se houver espaçamento compensatório suficiente ou se estiver em linha de texto. (Recomendação ergonômica: adotar **$44 \times 44\text{px}$** para mobile). |
| **3.3.7** | A | **Redundant Entry** | Informações já inseridas pelo usuário na mesma sessão ou fluxo não devem ser solicitadas novamente (reuso automático de dados de faturamento/entrega, ou opção clara de "Usar os mesmos dados"). |
| **3.3.8** | AA | **Accessible Authentication (Minimum)** | Não exigir testes cognitivos (memorização de senhas complexas arbitrárias sem suporte a gerenciadores de senha, resolução de cálculos ou quebra-cabeças). Permitir colagem de senhas (`paste`) e suportar Passkeys/WebAuthn. |

---

## 2. Matriz de Contraste e Uso Inclusivo da Cor

### 2.1. Limiares de Razão de Contraste (Contrast Ratio)
- **Texto Normal (< 18pt ou < 14pt bold):**
  - Nível AA: Mínimo de **4.5:1** contra o fundo.
  - Nível AAA: Mínimo de **7.0:1** contra o fundo.
- **Texto Grande ($\ge$ 18pt / 24px normal, ou $\ge$ 14pt / 18.66px bold):**
  - Nível AA: Mínimo de **3.0:1** contra o fundo.
  - Nível AAA: Mínimo de **4.5:1** contra o fundo.
- **Componentes de UI e Gráficos Essenciais (Critério 1.4.11):**
  - Bordas de inputs interativos, ícones com significado e anéis de foco: Mínimo de **3.0:1** contra superfícies adjacentes.

### 2.2. A Regra do Canal Duplo (Não Depender Apenas da Cor - Critério 1.4.1)
- Jamais use apenas cor para sinalizar status, erro ou sucesso. Usuários com discromatopsia (daltonismo) não distinguem vermelho e verde puros.
- **Solução Obrigatória:** Combine sempre **Cor + Ícone + Texto Semântico**.
  ```html
  <!-- Incorreto: Apenas borda vermelha -->
  <input class="border-red" />

  <!-- Correto: Borda + Ícone de Erro + Mensagem com aria-describedby -->
  <div class="form-field">
    <label for="cpf-input">CPF</label>
    <div class="input-wrapper">
      <input id="cpf-input" aria-invalid="true" aria-describedby="cpf-error" />
      <span class="icon-error" aria-hidden="true">⚠️</span>
    </div>
    <span id="cpf-error" class="error-message" role="alert">
      CPF incompleto. Digite os 11 dígitos.
    </span>
  </div>
  ```

---

## 3. Navegação por Teclado e Engenharia de Foco

Uma aplicação plenamente acessível deve ser 100% operável sem o uso do mouse.

### 3.1. Indicador de Foco Visível e Inviolável
```css
/* REGRA INEGOCIÁVEL: NUNCA faça isto */
*:focus {
  outline: none; /* PROIBIDO sem anel alternativo de alto contraste */
}

/* FORMA CANÔNICA: Anel de Foco Ergonômico de 2 camadas */
:focus-visible {
  outline: 2px solid var(--color-interactive-focus-ring, #0284c7);
  outline-offset: 2px;
  box-shadow: 0 0 0 4px rgba(2, 132, 199, 0.25);
  transition: outline-offset 150ms ease;
}
```

### 3.2. Link para Pular Conteúdo (Skip Link)
Todo layout de aplicação deve conter um skip link oculto no topo, visível imediatamente no primeiro `Tab`:
```html
<a href="#conteudo-principal" class="skip-link">
  Pular para o conteúdo principal
</a>

<style>
.skip-link {
  position: absolute;
  top: -100px;
  left: 16px;
  padding: 12px 24px;
  background: var(--color-surface-card, #ffffff);
  color: var(--color-text-primary, #0f172a);
  border: 2px solid var(--color-interactive-primary-default, #2563eb);
  border-radius: 8px;
  z-index: 99999;
  font-weight: 600;
  transition: top 200ms ease;
}
.skip-link:focus {
  top: 16px;
}
</style>
```

### 3.3. Focus Trap em Diálogos Modais
Quando um modal abre:
1. O foco é transferido para o primeiro elemento interativo interno (ou para o container do diálogo).
2. O foco não deve escapar do modal ao pressionar `Tab` ou `Shift+Tab`.
3. Pressionar a tecla `Escape` deve fechar o modal.
4. Ao fechar, o foco DEVE retornar exatamente para o elemento que acionou a abertura.

---

## 4. Semântica HTML e Padrões ARIA

### 4.1. Landmarks Semânticos Obrigatórios
Use tags nativas do HTML5 em vez de `<div>` anônimas:
- `<header>`: Cabeçalho global do produto.
- `<nav aria-label="Navegação Principal">`: Menus de rotas.
- `<main id="conteudo-principal">`: O conteúdo único e dinâmico da página.
- `<aside>`: Barra lateral contextual ou filtros secundários.
- `<footer>`: Rodapé de metadados, links institucionais e direitos.

### 4.2. Notificações Dinâmicas com Live Regions
Quando dados são carregados ou atualizados via WebSocket / HTTP sem recarregar a página, informe leitores de tela:
- **`aria-live="polite"` (Padrão para Toasts e Mensagens de Sucesso):** O leitor de tela aguarda a fala atual antes de anunciar a mensagem.
- **`aria-live="assertive"` (Reservado para Alertas Críticos de Erro ou Perda de Sessão):** Interrompe a fala imediatamente para comunicar o alerta crítico.

```html
<div aria-live="polite" aria-atomic="true" class="toast-container">
  @if (mensagemSucesso(); as msg) {
    <div class="toast-success" role="status">
      {{ msg }}
    </div>
  }
</div>
```

---

## 5. Testes Automatizados de Acessibilidade com `@axe-core/playwright`

A auditoria de acessibilidade deve rodar automaticamente na suíte de testes E2E/componente gerenciada pelo `especialista-qualidade`:

```typescript
// tests/e2e/a11y.spec.ts
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Auditoria de Acessibilidade WCAG 2.2 AA', () => {
  test('A página principal não deve conter violações de acessibilidade', async ({ page }) => {
    await page.goto('/');

    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
      .analyze();

    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('O modal de confirmação de transferência deve manter o foco preso e ser acessível', async ({ page }) => {
    await page.goto('/transferencias');
    await page.getByRole('button', { name: 'Confirmar Pix' }).click();

    // Valida a11y do modal aberto
    const modalScan = await new AxeBuilder({ page })
      .include('[role="dialog"]')
      .analyze();

    expect(modalScan.violations).toEqual([]);

    // Valida fechamento por Escape
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).toBeHidden();
  });
});
```
