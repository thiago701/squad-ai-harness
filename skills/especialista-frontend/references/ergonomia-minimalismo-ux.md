# Ergonomia e Minimalismo no UX — Guia de Engenharia Centrada no Humano

> **Quando ler:** ao desenhar arquiteturas de informação, layouts, fluxos de navegação e componentes visuais.
> **Princípios governantes:** P1-Simplicidade na experiência humana. O design existe para remover atrito, não para chamar atenção para si mesmo ("Menos, porém melhor" — Dieter Rams).

---

## 1. Ergonomia Cognitiva: A Teoria da Carga Cognitiva aplicada a Software

A mente humana possui capacidade limitada de processamento na memória de trabalho. Segundo a Teoria da Carga Cognitiva de John Sweller, a carga mental total é composta por três frações:

```
Carga Total = Carga Intrínseca + Carga Extrínseca + Carga Germânica
```

| Tipo de Carga | O que representa | Papel do Engenheiro Frontend | Exemplo de Decisão de UX |
|---|---|---|---|
| **Intrínseca** | Complexidade inerente à tarefa de negócio (ex: conciliar balancete bancário ou configurar roteamento de rede). | Inevitável pelo domínio, mas deve ser decomposta em passos compreensíveis. | Dividir a tarefa em um Wizard multi-etapas com indicador claro de progresso. |
| **Extrínseca** | Esforço mental desperdiçado decifrando a interface (ruído visual, botões confusos, menus escondidos, terminologia técnica). | **Eliminar impiedosamente.** Toda carga extrínseca é defeito de design (violação P1). | Remover bordas redundantes, unificar botões discrepantes e usar rótulos descritivos. |
| **Germânica** | Esforço dedicado à construção de modelos mentais sólidos e aprendizado do sistema. | **Facilitar e incentivar.** A interface deve reforçar padrões duradouros. | Usar metáforas consistentes e feedback visual imediato para consolidar a ação do usuário. |

### Regra do Data-Ink Ratio de Edward Tufte
$${\text{Data-Ink Ratio}} = \frac{\text{Tinta/Pixels dedicados aos Dados Reais}}{\text{Total de Tinta/Pixels na Tela}}$$
- **Diretriz:** Todo pixel ou elemento visual que não represente dado útil, estado acionável ou suporte estrutural deve ser removido.
- **O que cortar:**
  - Linhas de grade (gridlines) pesadas e escuras em tabelas corporativas (substituir por linhas sutis de 1px com baixa opacidade ou espaçamento inteligente).
  - Sombras pesadas e gradientes excessivos que poluem o plano de fundo.
  - Ícones puramente decorativos ao lado de rótulos que já são autoexplicativos.
  - Caixas dentro de caixas (efeito "matrioska" de cartões aninhados sem necessidade semântica).

---

## 2. Princípios da Gestalt na Organização Visual da Interface

A psicologia da Gestalt descreve como o cérebro humano agrupa automaticamente estímulos visuais para interpretar o ambiente:

### 2.1. Lei da Proximidade
- Elementos espacialmente próximos são percebidos como pertencentes ao mesmo grupo funcional.
- **Aplicação Prática:**
  - O espaçamento entre um rótulo (`<label>`) e seu campo (`<input>`) deve ser estritamente menor (ex: `4px` a `8px`) do que o espaçamento até o próximo campo do formulário (ex: `24px` a `32px`).
  - Botões de ações mutuamente excludentes ("Salvar" vs "Cancelar") devem ter respiro equilibrado, mantendo a ação destrutiva ("Excluir") claramente isolada.

### 2.2. Lei da Similaridade
- Elementos que compartilham características visuais (cor, forma, peso tipográfico, tamanho) são percebidos como tendo a mesma função ou hierarquia.
- **Aplicação Prática:**
  - Se um link de navegação é estilizado em azul com sublinhado sutil, textos não clicáveis jamais devem usar essa combinação.
  - Todos os botões de ação primária da aplicação inteira devem compartilhar exatamente a mesma tonalidade, altura e raio de curvatura.

### 2.3. Lei da Região Comum (Container e Card Layout)
- Elementos delimitados dentro do mesmo contorno visual ou plano de fundo são percebidos como um conjunto unificado.
- **Aplicação Prática:**
  - Agrupe seções relacionadas (ex: "Dados de Cobrança", "Forma de Pagamento") em cartões com elevação sutil ou plano de fundo diferenciado (`--surface-subtle`), evitando divisores rígidos.

### 2.4. Lei do Fechamento e Figura-Fundo
- O cérebro completa figuras incompletas e separa o elemento principal (figura) do contexto (fundo).
- **Aplicação Prática:**
  - Modais, Drawers e Popovers devem usar um backdrop sutil com blur ou escurecimento suave (`backdrop-filter: blur(4px); background-color: rgba(0, 0, 0, 0.4)`), estabelecendo inequivocamente a hierarquia figura-fundo sem causar ofuscamento visual.

---

## 3. Ergonomia Motora e Física: A Zona do Polegar (Thumb Zone)

Nas interfaces móveis e tablets, a ergonomia física dita o conforto de uso prolongado e previne lesões por esforço repetitivo e toques acidentais:

```
+---------------------------+
|      ZONA DIFÍCIL         |  <- Evite ações frequentes aqui
|   (Exige esticar o dedo)  |     (Bom para: título de tela, logo)
+---------------------------+
|       ZONA NATURAL        |  <- Alcance moderado confortável
|   (Navegação de conteúdo) |     (Bom para: cards, feeds, leitura)
+---------------------------+
|       ZONA FÁCIL          |  <- Alcance imediato do polegar
|  (Ações Críticas / CTAs)  |     (Bom para: Bottom Bar, CTAs primários)
+---------------------------+
```

### Regras de Ergonomia Física:
1. **CTAs Fixos na Base (Sticky Bottom Bar):** Em fluxos transacionais no mobile (ex: checkout, confirmação de Pix), o botão de confirmação deve residir na zona inferior acessível pelo polegar, com `safe-area-inset-bottom` respeitado.
2. **Tamanho Mínimo de Alvo (Touch Target):** Mínimo absoluto de **$44 \times 44\text{px}$** para áreas clicáveis móveis, com folga de pelo menos `8px` entre alvos adjacentes para impedir toques incorretos.
3. **Prevenção de Fadiga Visual:**
   - Evitar contraste extremo de branco puro (`#FFFFFF`) sobre preto puro (`#000000`). Utilizar pretos ricos com matiz suave (ex: `hsl(220, 15%, 10%)`) e textos em cinza-claro de alto contraste (ex: `hsl(220, 15%, 95%)`).
   - Respeitar a escala tipográfica para manter legibilidade sem zoom em distâncias de leitura normais (mínimo de `16px` para texto de corpo em mobile para evitar auto-zoom indesejado no iOS).

---

## 4. Os 10 Princípios do Bom Design de Dieter Rams Aplicados ao Frontend

Dieter Rams definiu os mandamentos universais do design funcional ("Weniger, aber besser"):

1. **O bom design é inovador:** A tecnologia serve ao propósito do usuário, não o oposto.
2. **O bom design torna o produto útil:** A interface deve focar na utilidade primordial do software; floreios estéticos que atrapalham a tarefa devem ser eliminados.
3. **O bom design é estético:** A beleza sensorial do software gera calma mental e precisão operacional.
4. **O bom design torna o produto compreensível:** A estrutura da página deve ser autoexplicativa; o usuário deduz a função pelo aspecto do componente (Affordance clara).
5. **O bom design é discreto:** Software para trabalho é ferramenta; a interface não deve competir com a atenção do operador.
6. **O bom design é honesto:** Não prometa instantaneidade se a operação é assíncrona; mostre o status real sem simulações falsas.
7. **O bom design é duradouro:** Evite modismos gráficos passageiros (neomorfismo desgovernado, skeuomorfismo excessivo); priorize clareza tipográfica que perdura por décadas.
8. **O bom design é minucioso até o último detalhe:** Alinhamentos pixel-perfect, estados de foco impecáveis, microinterações calibradas e zero quebra em qualquer resolução.
9. **O bom design é sustentável e respeitoso:** Respeite o consumo de bateria, memória do dispositivo do usuário e uso de dados com bundles enxutos e renders eficientes.
10. **O bom design é o mínimo de design possível:** Concentre-se nos aspectos essenciais. Elimine tudo que for supérfluo. Volte à pureza e simplicidade funcional.

---

## 5. Craft-First Interface Design para SaaS Denso e Dashboards (`Dammyjay93/interface-design`)

Interfaces de ferramentas profissionais, painéis operacionais e plataformas financeiras exigem alta densidade informacional sem fadiga ocular:

1. **Elevação Silenciosa (*Whisper-Quiet Elevation*):**
   - Em vez de sombras pesadas (`box-shadow` difuso) ou bordas grossas, separe planos hierárquicos por **saltos sutis de luminância perceptual em `OKLCH`** ($\Delta L = 0.02\text{ a }0.04$) combinados com bordas *hairline* de `1px solid` derivadas via `color-mix(in oklch, var(--color-text-primary) 10%, transparent)`.
2. **Alinhamento Óptico vs. Alinhamento Matemático:**
   - Um ícone triangular ("Play") ou seta dentro de um botão circular parece deslocado se centralizado apenas pela bounding box geométrica; aplique compensação óptica (`padding-inline-start: 2px`).
   - Em botões com ícone + texto, reduza o `padding` do lado do ícone em `2px–4px` para equilibrar o peso visual.
3. **Orçamento de Densidade e Ritmo Espacial (4px / 8px Grid):**
   - **Marketing / Onboarding (`--density 2–4`):** respiro amplo (`24px–64px`), foco em narrativa única por dobra.
   - **Aplicação SaaS / CRUD (`--density 5–7`):** equilíbrio padrão (`16px–32px`), agrupamento claro por região comum.
   - **Console Operacional / Trading / Observabilidade (`--density 8–9`):** compacto (`8px–16px`), `tabular-nums` obrigatório, navegação por teclado (`Roving Tabindex` + `Ctrl+K`) e contraste perceptual **APCA $|L_c| \ge 75$**.
