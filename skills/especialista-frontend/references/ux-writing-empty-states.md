# UX Writing, Microcópia Assistiva, Gestão de Erros e Empty States

> **Quando ler:** ao redigir textos de interface, labels de botões, mensagens de erro/sucesso, estados vazios (empty states) ou definir estratégias de feedback de carregamento.
> **Princípios governantes:** P1-Simplicidade. Cada palavra na tela deve reduzir a incerteza do usuário. Evitar jargões técnicos herméticos.

---

## 1. Os Quatro Pilares da Microcópia de Excelência

Microcópia é o conjunto de palavras curtas que guiam as pessoas através de uma interface digital (rótulos de botões, tooltips, placeholders, mensagens de confirmação). Ela deve sustentar quatro atributos universais:

| Pilar | Regra Prática | Exemplo Ruim | Exemplo Excelente |
|---|---|---|---|
| **1. Claro** | Sem jargões técnicos internos ou acrônimos misteriosos. O usuário deve entender sem hesitar. | "Falha de parse no payload JSON." | "Não conseguimos ler os dados do arquivo enviado." |
| **2. Conciso** | Diga o necessário com o menor número de palavras possível, sem perder precisão. | "Para poder continuar para a próxima tela, por favor clique no botão abaixo." | "Continuar" |
| **3. Útil** | Sempre aponte a ação seguinte. Uma mensagem sem rota de fuga gera paralisia. | "Sessão expirada." | "Sua sessão expirou por segurança. **Fazer login novamente**" |
| **4. Humano** | Empático, calmo e respeitoso. Jamais culpe o usuário pelo erro. | "Você digitou um CEP inválido!" | "CEP não encontrado. Verifique os 8 números e tente de novo." |

### Rótulos de Botão Baseados em Verbo de Ação
Botões devem expressar claramente o resultado imediato da ação.
- Evite: "Sim", "OK", "Enviar", "Submeter".
- Prefira: "Salvar alterações", "Transferir R$ 250,00", "Excluir conta permanentemente", "Voltar para o início".

---

## 2. Anatomia de Mensagens de Erro Construtivas

Erros são os momentos de maior fricção e ansiedade em um fluxo digital (Pico da Peak-End Rule). Toda mensagem de erro deve seguir rigorosamente a **Tríade Construtiva**:

```
[ 1. O QUE ACONTECEU ]  ->  Fato objetivo, sem culpar o usuário
[ 2. POR QUE ACONTECEU ] ->  Razão compreensível (sem stack trace ou código HTTP)
[ 3. COMO RESOLVER ]    ->  Instrução acionável e imediata
```

### Casos Práticos Corporativos / Bancários:

#### Cenário A: Falha na Transferência de Saldo
- ❌ **Ruim:** "Erro 403: Saldo insatisfatório para a operação financeira."
- ✅ **Correto:**
  - *O que:* Não foi possível realizar a transferência de R$ 500,00.
  - *Por que:* O valor excede o saldo disponível na sua Conta Corrente (Saldo atual: R$ 320,00).
  - *Como resolver:* Transfira um valor de até R$ 320,00 ou adicione fundos antes de tentar novamente.

#### Cenário B: Arquivo Anexado Inválido
- ❌ **Ruim:** "MIME-Type não suportado."
- ✅ **Correto:**
  - *O que:* Não foi possível carregar o arquivo "documento.bmp".
  - *Por que:* Aceitamos apenas arquivos nos formatos PDF, PNG ou JPG de até 5 MB.
  - *Como resolver:* Salve seu arquivo como PDF ou PNG e tente enviar novamente.

---

## 3. Empty States: Transformando Telas Vazias em Oportunidades

Uma tela vazia sem orientação é uma das maiores causas de abandono precoce de produtos digitais. Existem quatro tipos fundamentais de Empty States:

```
+-------------------------------------------------------+
|                       [ ÍCONE ]                       |
|                                                       |
|             Você ainda não cadastrou clientes         |
|   Cadastre seu primeiro cliente para começar a emitir |
|       cobranças e gerar notas fiscais em segundos.    |
|                                                       |
|                [ + Cadastrar Cliente ]                |
+-------------------------------------------------------+
```

### Os 4 Tipos Canônicos de Empty State:

1. **Primeiro Uso (Onboarding):**
   - Situação: O usuário acabou de criar a conta e não tem dados cadastrados.
   - Resposta: Apresente o benefício central e forneça um botão de ação primária (CTA) em destaque para criar o primeiro registro.
2. **Zero Inbox / Limpeza Concluída:**
   - Situação: Todas as pendências, aprovações ou mensagens foram processadas.
   - Resposta: Mensagem de celebração sutil ("Tudo limpo por aqui! Você revisou todas as pendências de hoje.") para proporcionar sensação de alívio e conclusão.
3. **Filtro ou Busca Sem Resultados:**
   - Situação: A busca do usuário não retornou registros.
   - Resposta: "Nenhum cliente encontrado para 'Silva'. Tente buscar por CPF ou limpe os filtros aplicados." com botão "Limpar filtros".
4. **Falha Temporária de Conexão:**
   - Situação: O servidor falhou ao responder a requisição.
   - Resposta: "Não conseguimos carregar seus relatórios agora. Nossa equipe já está verificando." com botão "Tentar novamente".

---

## 4. Loading States: Skeletons vs Spinners na Redução da Latência Percebida

Estudos empíricos de percepção visual demonstram que **Skeleton Screens reduzem o tempo de espera percebido em até 20%** quando comparados a spinners genéricos:

| Padrão | Quando Usar | Por que Funciona |
|---|---|---|
| **Skeleton Screen com Shimmer** | Carregamento inicial de páginas, cartões de feed, tabelas e dashboards. | O usuário percebe a estrutura física da página imediatamente; o cérebro antecipa o conteúdo final antes mesmo dos dados chegarem. |
| **Progress Bar Linear Determinística** | Uploads de arquivos, processamento de lotes com tempo mensurável (0% a 100%). | Comunica progresso constante; elimina a ansiedade de travamento. |
| **Spinner Pequeno Inline** | Ações rápidas dentro de um botão (< 1s, ex: salvando campo único). | Mantém o botão no lugar e sinaliza que o clique foi registrado. |
| **Spinner de Tela Cheia (Anti-padrão)** | **EVITAR SEMPRE.** | Gera sensação de bloqueio total do sistema e impotência operacional. |

### Implementação de Skeleton Shimmer Acessível em CSS:
```css
.skeleton {
  background: linear-gradient(
    90deg,
    var(--color-surface-subtle) 0%,
    var(--color-border-subtle) 50%,
    var(--color-surface-subtle) 100%
  );
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s infinite linear;
  border-radius: var(--radius-sm);
}

@keyframes skeleton-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Respeito à sensibilidade visual */
@media (prefers-reduced-motion: reduce) {
  .skeleton {
    animation: none;
    opacity: 0.7;
  }
}
```
Adicione sempre `aria-busy="true"` no container pai enquanto o skeleton estiver ativo, removendo-o assim que os dados forem renderizados.
