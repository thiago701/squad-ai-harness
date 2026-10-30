---
description: Executa os quality gates da stack (verificacao-loop) e emite o relatório padronizado READY/NOT READY.
argument-hint: [stack: java | python | angular | auto]
origin: squad-ai
---

Você está executando o comando **/squad-quality-gate** — fachada fina do **Quality Gate System**.

Stack/alvo: **$ARGUMENTS** (padrão: auto-detectar pelo projeto)

Invoque a skill **`verificacao-loop`** e execute os gates executáveis apropriados à stack:

1. **Java 25:** `mvn verify` + cobertura **JaCoCo ≥ 80%** + SpotBugs + OWASP dependency-check + ArchUnit (regras de Clean Architecture).
2. **Python 3.13:** `ruff` (lint/format) + `pytest --cov` (cobertura) + checagem de tipos.
3. **Angular 21+:** `ng lint` + `ng test`.
4. **Loop de verificação:** rode, leia a saída real (não presuma), e itere até verde ou até identificar o bloqueio. Distinga **pass@k** (passou uma vez) de **pass^k** (passa de forma consistente em execuções repetidas) — fluxos críticos exigem pass^k.

**Gatilho de segurança:** se o diff toca auth/input/queries/cripto/secrets, o gate **não fecha verde** sem o aval de **`engenheiro-seguranca`** (/squad-security) — crítico é 🔴 bloqueante.

**Entrega:** **relatório padronizado READY / NOT READY** auditável, com os números reais (cobertura, lint, testes, vulnerabilidades) e a lista de bloqueios quando NOT READY. Este relatório é pré-requisito do **GATE 2** no pipeline.
