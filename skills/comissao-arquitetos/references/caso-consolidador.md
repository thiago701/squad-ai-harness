# Caso de referência — Consolidador de Treinamentos (Enterprise, 13–14/10/2026)

Repositório do caso: `<workspaces>/consolidador-treinamentos/` — `docs/spec/` (SPEC, PLANO, ADRs, ata, GATE 1, fluxo) e `docs/spec/comissao/` (brief, memos, votos, revisão independente).

## Pedido
Dashboard de treinamentos (CloudFront) com autocomplete de colaboradores, backend "basicamente Step Functions", DynamoDB free tier, API POST + Bruno com apiKey no Secrets Manager, seed a partir de arquivos de contexto, conta/região fixas, UX minimalista. "Refine em várias rodadas até não restar dúvidas. Plano + spec, sem código."

## Linha do tempo
| Etapa | Resultado |
|---|---|
| Staging | 5 arquivos de contexto + referência de UX lidos; CSVs perfilados por script |
| Brief | pedido verbatim, 10 tensões (síncrono × scan de pastas; 0 Lambda × fuzzy; HTTP × REST; LGPD; fonte das evidências…) |
| Ajustes em voo | 3 (Secrets Manager; valor completo do "grupo NTT"; avaliar JEV) → 2 relançamentos da R1 |
| R1 | 6 memos (A–F); B com 38 fontes oficiais |
| R2 | 10 ADRs; 57 APROVO / 3 OBJEÇÃO (todas com alternativa) |
| R3 | 6/6 "sem dúvidas" + 4 correções (REVISAO# órfã, lote em vários POSTs, `hash8`, invariantes 7–8) |
| Revisão independente | "pronto com ajustes": 🔴 timeout 30 s, 🔴 desvio de requisito oculto, 🔴 chave com data nula, 🔴 campo sem fonte; 15 inconsistências |
| GATE 1 | aprovado com 11 defaults |
| Pós-GATE 1 | repo preparado para multiagente (skill `repo-ai-first-multiagente`) |
| Ondas 1–9 (Implementação & Deploy) | 18 tarefas (`T-101` a `T-504`) entregues em ondas + deploy completo em SANDBOX e PRODUÇÃO (`ap-northeast-1`) com seed real dos 58 colaboradores |
| Onda 10 (Hardening, Cache S3, Relatório do Gestor & Catraca de Qualidade) | Auth individual por funcional no CloudFront KVS + sessão HMAC `__Host-` + troca de senha self-service; CSP A+ (`0 innerHTML`, classes `.w-pct-*`); Cache Espelho de Certificados no S3 (`324` arqs filtrados = `15,8 MB`, `-98,4%` de ruído); tela **Relatório do Gestor** (matriz `58×21` em Read Model S3 `0 RCU` + delta no cliente + RBAC duplo); Catraca de Qualidade Contínua (`Inv.1..12` + Baterias `Q1..Q5` + Corpus S3 `test_continuous_s3.py`) |

## Conflitos e como foram arbitrados
| Conflito | Decisão | Critério |
|---|---|---|
| HTTP API + Choice na SF × REST + API key espelhada | HTTP API com mitigações de Segurança nomeadas | P1; Segurança aceitou |
| 0 Lambda × Lambda de matching × JEV | JSONata determinístico + fila de revisão + extração PDF stdlib (`BT..ET`) no scanner; difflib/JEV só por gatilho medido + benchmark | P1 + invariante 60 linhas + doutrina JEV |
| Status materializado × derivado | derivado na leitura individual (`SF consulta`); Read Model JSON no S3 (`relatorio-gestor.json`) **exclusivo** para a matriz global 58×21 do Gestor (`0 RCU`) com reconciliação de delta no cliente | P1 + P3 (evita 58 Queries ou Scan no DynamoDB) |
| Espelho integral do OneDrive (967 MB, 85,8% de outras equipes) × Espelho filtrado da equipe | Espelho S3 **filtrado pelo roster da equipe** (`324` arqs = `15,8 MB`) + bloqueio duplo (`403` CF Function + Bucket Policy `Deny`) | Segurança/LGPD (veto a dados de terceiros) + P3 |
| URLs internas do cliente (banco) | não guardar | política de confidencialidade do usuário |

## Lições (viraram regras das skills; registradas como LL-0023…LL-0031)
1. Brief antes de convocar (`LL-0023`). 2. Papéis ortogonais (`LL-0023`). 3. Rejeitados explícitos (`LL-0023`). 4. Objeção exige alternativa (`LL-0023`). 5. R3 curta acha bugs (`LL-0023`). 6. Revisão independente obrigatória (`LL-0023`). 7. Desvio vira pergunta (`LL-0023`). 8. Fatos com fonte (`LL-0023`). 9. Contratos JSON Schema congelados + posse por onda + fixture `norm` N-way (`LL-0024`). 10. Step Functions JSONata `$now()` exige timezone `-0300` e `Map` inline exige `Output` enxuto `< 256 KiB` (`LL-0025`). 11. Ingestão corporativa exige filtro de escopo da equipe (`-98%` S3), extração PDF stdlib (`BT..ET`) e anti-Mojibake (`LL-0026`). 12. CloudFront Function + KVS exige LF `< 10.240 B`, rotas virtuais `GET` e sincronia tripla `DynamoDB ↔ S3 ↔ KVS` (`LL-0027`). 13. SPA com CSP A+ exige `domEl` (`0 innerHTML`), classes `.w-pct-*`, magic bytes e scanner git por digest SHA-256 (`LL-0028`). 14. Guarda de `AbortController` na UI e reconciliação por chave dupla `cursoId`/`ARQ:` (`LL-0029`). 15. Read Model S3 `0 RCU` com RBAC duplo e `--exclude` obrigatório no `aws s3 sync --delete` (`LL-0030`). 16. Catraca de Qualidade Contínua: todo incidente vira Invariante Estático + Bateria Comportamental (`LL-0031`).

## Custo aproximado
R1: 6 × 140–220k tokens; R2: 6 × ~30k; R3: 6 × ~10k; revisão: ~200k. Total ≈ 1,5M tokens (subagentes) — justificável em large; em standard, 3 papéis.
Estudo de caso completo ponta a ponta em `docs/evolucao-caso-consolidador-2026-10/README.md`.
