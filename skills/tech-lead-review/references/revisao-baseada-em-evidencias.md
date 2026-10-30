# Revisão baseada em evidências — 4 fontes, marcas e lente AWS

> Parte da skill `tech-lead-review`. Hub: `../SKILL.md`. **Marcas, níveis V0–V5 e formato de achado
> são definidos uma vez** em `governance/politica-evidencias-sigilo-qualidade.md` — este arquivo só
> diz como o review os usa. Adicionado em 2026-10-08.

## 1. Confronto obrigatório das 4 fontes

| # | Fonte | Pergunta |
|---|---|---|
| 1 | Descrição e critérios de aceite | o que foi prometido? |
| 2 | Diff e contexto do código | o que de fato mudou (e o que ficou de fora)? |
| 3 | Testes e resultados | o que foi **executado** e passou — e em que nível (V1–V5)? |
| 4 | Convenções e contratos do repositório | AGENTS.md, contratos, gates, padrões da skill |

Divergência entre quaisquer duas é `[DIV]`. Critério de aceite sem teste executado é `[GAP]`, nunca
"aprovado". Teste com mock não vira "validado na AWS".

## 2. Dimensões avaliadas

Corretude · segurança · performance · design · contratos · dados · concorrência · supply chain · IaC ·
testes · observabilidade · **usabilidade** (mensagem diz o que houve e o próximo passo, com
correlação, sem detalhe interno e sem inventar canal de atendimento).

## 3. Formato do achado

O da política §3: `[ID] <marcas> <severidade> — título`, evidência **sanitizada** (local, nunca o
segredo), impacto, recomendação, validação (teste/comando + nível). O Pre-Report Gate do hub
continua: sem âncora concreta, não reporta.

## 4. Lente AWS (quando o diff toca ASL, VTL, IaC ou integração AWS)

| Sinal no diff | Comando determinístico | Especialista |
|---|---|---|
| `*.asl.json` | `python scripts/aws/asl_lint.py <arq> --tipo STANDARD|EXPRESS` | `orquestracao-step-functions` |
| `*.vtl` ou `requestTemplates` | `python scripts/aws/vtl_lint.py <arq>` | `api-gateway-integracoes` |
| diagrama + ASL + IaC do mesmo fluxo | `python scripts/aws/coerencia.py <cenário>` | `arquiteto-cloud-aws` |
| template SAM/CFN | `cfn-lint <template>` (se instalado) | `engenheiro-iac` |
| WebSocket/IoT/projeção | testes de duplicidade, desordem, reconexão | `tempo-real-aws` |
| plano de investigação em produção | `python scripts/aws/guarda_somente_leitura.py <plano>` | `analise-producao-aws` |

Achado de lint `ERRO` com marca `[SEC]` é 🔴 (segurança fora da arbitragem). Achado `AVISO` vira 🔵
ou 🟡 conforme impacto demonstrado.

## 5. Laudo

Começa por **APROVAR · APROVAR COM RESSALVAS · SOLICITAR MUDANÇAS · BLOQUEAR** e segue com: escopo
revisado, níveis de validação por funcionalidade, achados por severidade, lacunas (`[GAP]`) e o que
falta para subir de nível. "Não declarar ganho sem medição, teste não executado como aprovado nem
integração simulada como validada em produção."
