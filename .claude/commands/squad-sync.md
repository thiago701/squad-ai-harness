---
description: Sincronização git/github dirigida por JEV — estado do repo, plano N0/N2/N3, commits agrupados, push gated (0 tokens nas decisões).
argument-hint: [escopo: plan | execute --push | status]
origin: squad-ai
---

Você está executando o comando **/squad-sync** — fachada fina da skill **`git-sync`**
(sincronização git dirigida por JEV). Consulte a skill para o protocolo completo e siga:

1. **Decida com o JEV (0 tokens):** rode `python scripts/git/squad_sync.py plan` e apresente
   estado → plano (N0/N2/N3) → risco → custo (0 tokens).
2. **Gate por tier:** N0/N2 fluem (reversíveis); **push/config de remote/branch padrão são
   N3** — execute somente com aprovação explícita do humano (`execute --push`).
3. **Execute** `python scripts/git/squad_sync.py execute [--push] [--mensagem "<intenção>"]`.
   Fail-closed: passo falho para o fluxo; nunca `--force`, nunca reescrever história.
4. **Escale** conflito/divergido/detached para o humano com diagnóstico; LLM só redige
   mensagem de commit narrativa sob pedido.
5. **Relate:** tabela estado inicial → ações (com hashes) → estado final → pendências N3.

**Entrega:** relatório conciso; nunca commit/push sem o gate correspondente (N3).
