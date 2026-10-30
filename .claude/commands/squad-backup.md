---
description: Backup seguro do ecossistema (skills, memória, config) via script de backup — antes de mudanças de risco.
argument-hint: [alvo: completo | skills | memória | config]
origin: squad-ai
---

Você está executando o comando **/squad-backup** — fachada fina do **script de backup** (guardrail de governança).

Alvo: **$ARGUMENTS** (padrão: completo)

Execute o **script de backup** do ecossistema (ex.: `scripts/backup.ps1` no Windows/PowerShell — cidadão de primeira classe deste repositório):

1. **Snapshot versionado:** copie as superfícies de verdade para um destino datado e fora do working tree ativo (skills-fonte, `memory/`, `.claude/`, registry, config), sem incluir binários pesados e outputs de rotina (respeite o `.gitignore`).
2. **Quando rodar (obrigatório):** ANTES de qualquer operação de risco — sobrescrever config crítica, refatoração em massa, evolução de skills, instalação/atualização que toque settings. "Nunca sobrescrever config crítica sem backup" é regra dura de governança.
3. **Integridade:** registre o conjunto copiado e, quando aplicável, um checksum, para permitir restauração confiável.
4. **PowerShell-first:** o script deve funcionar em PowerShell no Windows 11 antes de qualquer outro ambiente.

**Modo seguro:** o backup é **não-destrutivo** — apenas cria cópias, jamais apaga ou move o original. Confirme o destino antes de gravar grandes volumes.

**Entrega:** confirmação do snapshot (caminho datado + itens incluídos + checksum) e instrução de como restaurar.
