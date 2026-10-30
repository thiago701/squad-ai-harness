---
description: Roda UMA volta do loop de evolução da Squad AI definido em loops/evolucao-squad-loop.md — ataca até 2 gaps executáveis do mapa, valida com a bateria da casa (pytest + selos + calistenia + gate-ia + sombra TIA) e grava relatório + handoff na árvore (commit é humano)
argument-hint: "[foco opcional, ex.: 'G2 roteador' — vazio = topo do mapa; pode incluir resultado de host colado]"
---

Execute o loop especificado em `loops/evolucao-squad-loop.md` (raiz deste repositório). Leia esse
documento primeiro e siga os passos da volta exatamente.

Resumo do contrato: fixe as entradas (foco e/ou resultado de host em $ARGUMENTS; sem argumento,
use o topo do mapa em `docs/propostas/plano-loop-evolucao-2026-07-30.md` §2 e avise). Fotografe a
linha de base (handoff mais recente + selos `PRE-REGISTRO.txt` vigentes + ledgers). Apure
resultado de host ANTES de abrir item novo. Ataque até 2 itens executáveis no sandbox (TDD
aditivo, observe-only antes de fiação, memória negativa consultada). RODE o check e COLE a saída:
pytest verde, `sha256sum -c` de todos os selos, calistenia com canário (0 novas), gate de
artefatos de IA, CRLF, sombra do TIA sobre o diff da volta. Grave relatório ciclo<N> + handoff
atualizado + memória. Pare ao fechar a volta, em bloqueio humano, ou se só restarem itens de
host — e emita a fila HO com comandos prontos. Arquivo selado por pré-registro é intocável.
Erro, guard-rail de mutação ou teto estourado NUNCA é sucesso. Commit/push é sempre do humano.

Inputs inline (se houver): $ARGUMENTS
