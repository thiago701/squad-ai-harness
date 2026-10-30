# Testes always-on (disciplina)

> **Pack:** comum (always-on) · **Origin:** `squad-ai` · **Dono:** `especialista-qualidade`
> Invariantes. O método profundo vive na skill `especialista-qualidade` e em `skills/verificacao-loop`. Não duplicar.

Test-Driven é o método. Mudança de comportamento **sem teste não passa no gate**.

## Invariantes

- **Rodar testes ao mudar código.** Todo `Edit`/`Write` em código de produção dispara o `verificacao-loop`
  da stack. Sem teste verde, não avança.
- **TDD red → green.** Teste falhando **primeiro**, depois o código que o faz passar — não o contrário.
  Testes precedem ou acompanham a mudança; nunca um "depois eu testo".
- **Reportar a saída real.** Nunca afirmar "passou" sem evidência: colar a saída do runner (contagem, verde/vermelho).
  Afirmar sucesso sem prova é *invisible work* — e proibido.
- **Cobertura é gate.** Baixar cobertura ou desabilitar lint "para passar" é **proibido** (regra Must Never).
  GATE 2 exige relatório `PRONTO` do `verificacao-loop` com cobertura dentro do limite.
- **Execução incremental.** Entregar em fatias testáveis com checkpoints; nunca big-bang sem verificação no meio.

> Resumo: red → green → evidência → gate. Sem evidência real da saída, o trabalho não conta como pronto.
