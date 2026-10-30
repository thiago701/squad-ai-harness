# tech-lead-review · reference — Lente `rev-veracode` (skill `validacao-veracode`)

> Adicionado em 2026-10-02. Associa a validação Veracode ao code review como **lente obrigatória
> em todo PR**. Fonte da doutrina de validação: `skills/validacao-veracode/SKILL.md`.
> Doutrina de segurança e adoção da ferramenta: `skills/engenheiro-seguranca/references/veracode.md`.

## Por que em todo PR

A lente é **determinística** (regex por CWE + gate normalizado), roda em segundos, custa US$ 0 e não
precisa de credencial — o mesmo argumento do "JEV First": decisão barata e reproduzível antes do
julgamento caro. Quando existe resultado real do Veracode (Pipeline Scan no PR, Policy Scan no
release), ele entra no **mesmo** gate e prevalece sobre o pré-scan.

## Como rodar no review

```bash
S=skills/validacao-veracode/scripts            # instalada: ~/.claude/skills/validacao-veracode/scripts
python $S/veracode_precheck.py . --desde origin/main --perfil maximo --json pre.json
python $S/veracode_gate.py pre.json [results.json] [--baseline baseline.json] \
       [--status-politica "<Passed|Did Not Pass|Conditional Pass>"] \
       --perfil maximo --json veredito.json --md veredito.md
```

Anexe `veredito.md` ao `.claude/pipeline/<slug>/06-review.md` (no pipeline, o artefato da lente é
`05b-veracode.md`). O campo `review_worker` de `veredito.json` já está no schema dos workers
(`references/review-multi-dimensao.md`) — consolide sem reescrever.

## Veredito da lente → veredito do review

| `rev-veracode` | Veredito do Tech Lead | Observação |
|---|---|---|
| `BLOQUEADO` | **REQUER NOVO ROUND / NOT READY** | veto de segurança (G7) — não entra no desempate P1>P2>P3 |
| `APROVADO_COM_RESSALVAS` com 🟡 | **AGUARDANDO** | autor corrige; validação assíncrona |
| `APROVADO_COM_RESSALVAS` com 🔴 herdado | **APROVADO COM DEBT** | card de dívida com prazo (SLA: Very High 24 h · High 7 d · Medium 30 d) |
| `APROVADO` | segue as demais dimensões | lente verde não prova ausência de flaw — só ausência de achado |

## Regras do Tech Lead para esta lente

1. **Perfil:** `maximo` por padrão; **`bancario`** em todo repositório que movimenta dinheiro ou dado
   sob sigilo bancário (conta, cartão, Pix, crédito, Open Finance) — liga as regras `BK-*`, bloqueia
   🔴 herdado com SLA vencido e, no release (`--release`), exige evidência do Policy Scan.
   `padrao` só se o projeto declarar política equivalente a *Veracode Recommended High* — e isso fica
   registrado no review. Detalhe: `skills/validacao-veracode/references/contexto-bancario.md`.
2. **Pre-Report Gate:** o 🔴 do pré-scan já tem âncora (arquivo:linha + regra + CWE), mas é
   heurístico — confirme o fluxo de dados antes de devolver. Falso-positivo sai **só** por
   `veracode-precheck: ignorar <REGRA> motivo=<...>`, que fica visível no relatório.
3. **Mitigação:** só `APPROVED` tira o flaw do veredito; `PROPOSED`/`REJECTED` contam como abertos.
   Aprovador ≠ autor. *Accept the Risk* é do humano dono do risco (`quality/quality-gates.md` §7.3).
4. **Cleansers customizados** (`com.veracode.annotation.*`): anotação nova ou alterada é mudança
   sensível — o método precisa neutralizar de verdade a classe de CWE e ter teste. Cleanser de
   fachada = 🔴 (evidência falsa de mitigação).
5. **Fail-closed:** `results.json` ilegível, formato desconhecido ou `scan_status` ≠ `SUCCESS` não
   aprovam (gate sai com exit 2 ou `BLOQUEADO`).
6. **Escalação:** 🔴 que persiste após 3 voltas de correção → humano (aceite de risco não é do agente).
7. **Banco — o que a lente não prova:** `BK-BOLA-01` fica quieta quando o arquivo tem `@PreAuthorize`,
   mesmo que a expressão esteja errada. Em endpoint de conta/cartão, exija teste de autorização com
   dois titulares; em débito, teste de concorrência (duas requisições simultâneas).
