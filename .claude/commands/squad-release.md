---
description: Empacotamento e release versionado (SemVer + changelog + checksum) com engenheiro-devops, após gates verdes.
argument-hint: [tipo: patch | minor | major] [alvo: app | pacote .skill]
origin: squad-ai
---

Você está executando o comando **/squad-release** — fachada fina do papel Release Manager (par com `engenheiro-devops`).

Tipo/alvo do release: **$ARGUMENTS**

Invoque a skill **`engenheiro-devops`** (modelo sonnet) e conduza o release de forma controlada:

1. **Pré-condição inegociável:** o release só procede com **quality gate verde** (rode /squad-quality-gate antes) e **/squad-review** aprovado (READY). Nunca publique com gate vermelho.
2. **Versionamento semântico (SemVer):** determine patch/minor/major pelo impacto das mudanças. Gere o **changelog** (padrão release-please/Conventional Commits) a partir do histórico.
3. **Empacotamento:** para artefatos `.skill`/pacotes, gere o pacote por tag, calcule **checksum** e registre a procedência (`origin:`). Não misture pacotes de distribuição às fontes — use `dist/`.
4. **Tag + publicação:** crie a tag git e publique conforme o pipeline (GitHub Release/registry). Confirme cada passo destrutivo com o usuário.

**Modo seguro (gated):** não faça `push --force`, não pule gates, não publique sem checksum e aprovação humana. Backup recomendado antes (/squad-backup).

**Entrega:** release versionado (tag + changelog + checksum) com confirmação de gates verdes e instrução de rollback.
