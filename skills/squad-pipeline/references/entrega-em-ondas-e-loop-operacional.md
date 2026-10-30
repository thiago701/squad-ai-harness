# Entrega em ondas e loop "até ficar operacional" — reference do `squad-pipeline`

> **Origem:** caso-modelo RadarIAOps (12–14/10/2026, tier **large**). Lições `LL-0016`…`LL-0022`. Complementa
> `fluxo-e-topologia.md` (fases) e `sdd-artifacts.md` (artefatos); aqui está o que muda quando a entrega é um
> produto em **várias ondas**, numa **pasta do dono**, com **nuvem** que só o dono pode tocar.

## 1. Linha do tempo do caso-modelo (o fluxo que funcionou)

```
Research&Reuse → PRD+plano → GATE 1 (D0–D14) → refino R1–R12 + revisão independente
 → rodadas temáticas (harness/IAOps/ontologia; validação do desenho; MCPs) → decisões do dono em lote
 → spec 01–12 + DBML + drawio + backlog O0…O4 → "aprovado, implemente"
 → Onda 0: build → revisão independente NÃO PRONTO (2 🔴) → correções → GATE 2 ✅
 → cenários e2e (E2E-01..03) + decisões D-E2E → aprovados
 → limpeza/tags (E22) → Onda 1 parcial (gabarito, GitHub, parser 100 %) → e2e da CLI (moto server)
 → Onda 2 em loop até a CLI responder integrada à AWS
```

## 2. Uma onda = um mini-pipeline com GATE 2 próprio

- Pasta `docs/pipeline/onda-N/` com `01-intake`, `03-plano`, `04-decisoes-implementacao` (E-NN), `05-seguranca`,
  `06-review`, `99-relatorio` e, para ondas longas, `00-andamento.md` (tabela tarefa × status × evidência).
- Decisões de implementação (`E-NN`) são **registradas na hora**, com motivo e alternativa descartada — o review e o
  dono leem a decisão, não o diff inteiro.
- A revisão independente (contexto limpo) é **obrigatória em large** antes do GATE 2. No caso-modelo ela deu
  NÃO PRONTO com 2 bloqueantes que o implementador não via (segredo no tfstate via refresh; validador ecoando
  segredo em mensagem de erro) — reforça `LL-0013`.

## 3. Loop "até ficar operacional" — defina "operacional" antes de girar

Quando o dono pede "implemente em loop até funcionar", o motor fixa **o oráculo** e **o ambiente** do loop:

| Item | No caso-modelo |
|---|---|
| Critério de parada | os cenários e2e aprovados passam **pelo comando real** (`radar perguntar …`) |
| Ambiente do loop | nuvem simulada (moto server) + fakes gravados (GitHub, Resource Explorer) — gira sem conta e sem custo |
| Volta do loop | implementar a menor fatia → suíte (unit + e2e local) → ruff/mypy/terraform test → entregar na pasta → atualizar `00-andamento` |
| Saída do loop | relatório + **runbook de aceite** que o dono roda na conta real (o irreversível é dele) |
| Parada antecipada | decisão irreversível ou ambígua → prepara, expõe e para (gated) |

Pedido novo no meio do loop (mensagem durante a execução): confirmar recebimento, atender, **registrar onde o loop
parou** e retomar — o `00-andamento` é o ponto de retomada.

## 4. Entrega numa pasta conectada do dono

- Trabalhe numa cópia; antes de gravar, **compare hash** com o que está na pasta (o dono pode ter editado/rodado
  formatadores). Arquivo divergente: re-stage e funda, nunca sobrescreva às cegas.
- Caminhos protegidos (ex.: `.github/`, `Makefile`) podem recusar escrita: entregue em `_mover-para-<destino>/`
  com um `LEIA-ME` dizendo onde colocar.
- Lockfiles gerados na máquina do dono (hashes de outra plataforma) são **adotados**, não regenerados.
- Fixe a versão do runtime no projeto (`.python-version`) — o gerenciador do dono pode escolher outra (3.14 × 3.13).
- Mudanças em repositório de terceiros/da Squad ficam no working tree **sem commit**: o dono decide branch/PR.

## 5. O que é do dono (sempre runbook, nunca automação)

`terraform apply/destroy` na conta, `gh repo create --private`, gravar segredos, aprovar GATE 1/GATE 2,
aprovar cenários e decisões D-E2E. A Squad entrega o comando pronto e a forma de conferir o resultado.

## 6. Anti-padrões

- **"Loop sem oráculo"** — girar "até funcionar" sem dizer o que é funcionar.
- **"Onda sem GATE"** — várias ondas acumuladas num único GATE 2 gigante.
- **"Commit às cegas na pasta do dono"** — sobrescrever arquivo que divergiu.
- **"Automação do irreversível"** — rodar apply/destroy/criação de repo pelo dono.
