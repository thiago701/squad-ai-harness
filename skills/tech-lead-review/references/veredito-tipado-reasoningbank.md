# tech-lead-review · reference — Veredito tipado e ReasoningBank (R5)

> Movido verbatim do hub na v1.3 (18/10/2026) para abrir espaço à Auditoria de Cobertura
> sem estourar o teto residente de 5000 tokens. Conteúdo inalterado.

O veredito READY/NOT READY decide o GATE 2. Mas, para o **aprendizado** (R2), carimbe também um
**veredito tipado da trajetória** ao fechar a tarefa — é o passo **JUDGE** do laço de 4 passos:

| Veredito tipado | Quando | Vira no banco |
|---|---|---|
| **success** | passou em tudo, sem ressalva | trajetória de sucesso em `.claude/banco-padroes/<domain>.md` |
| **partial** | funcionou, mas com 🟡 aberto ou dívida registrada | trajetória `partial` (com a ressalva explícita) |
| **failure** | abordagem abandonada/revertida | trajetória de falha em `.claude/banco-padroes/anti-padroes.md` |

O veredito + o custo de tokens (R3, do `custo.md`) alimentam o `/aprender` (DISTILL) do
`aprendizado-continuo`. **Falha catalogada vale tanto quanto sucesso:** ela vira `anti_padrao_evitado`
no próximo RETRIEVE e impede o agente de repetir o beco sem saída. Não invente trajetória sem
`evidence` real (arquivo, teste, PR) — sem evidência, descarte.
