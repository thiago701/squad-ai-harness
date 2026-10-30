# Rules — conhecimento always-on da Squad AI

> **Origin:** `squad-ai` · **Status:** Ciclo 2 · **Dono:** `tech-lead-review` + `engenheiro-seguranca` (veto)
> **Relação:** os `rules/` são a destilação enxuta de [`AGENTS.md`](../AGENTS.md) e [`RULES.md`](../RULES.md)
> em **packs** que um projeto liga por stack. Em divergência, vale o documento **mais específico**.

## Rules vs. Skills — barato sempre vs. caro sob demanda

São os dois eixos do conhecimento do ecossistema. **Não se sobrepõem.**

| | **Rules** (este diretório) | **Skills** (`skills/`, `SKILL.md`) |
|---|---|---|
| Natureza | **Always-on** — sempre no contexto | **On-demand** — carregada quando o gatilho dispara |
| Custo | **Barato** (poucas linhas, sempre presente) | **Caro** (centenas de linhas, hub + `references/`) |
| Conteúdo | **Invariantes** — o que é *sempre* verdade num eixo | **Procedimento profundo** — como fazer X bem |
| Tamanho | Cada arquivo **≤ 80 linhas** | Hub ≤ 400 linhas + referências |
| Exemplo | "P1 > P2 > P3; segurança é veto" | `arquiteto-performance` resolvendo um gargalo p99 |

**Regra de não-duplicação:** um rule **destila o invariante**, nunca copia o conteúdo da skill. Se algo muda de
versão para versão ou depende de contexto, é skill. Se é sempre verdade e cabe em uma linha, é rule.

## Como os packs se relacionam com AGENTS.md / RULES.md

- [`AGENTS.md`](../AGENTS.md) e [`RULES.md`](../RULES.md) são o **ponto único de verdade** (identidade + regras).
- Os `rules/` **não inventam regra nova** — recortam o sempre-verdadeiro desses dois em arquivos pequenos e
  carregáveis seletivamente por **pack**. Cada arquivo aponta de volta à fonte canônica.
- Assim um projeto liga só os packs da sua stack, sem carregar todo o `AGENTS.md` em todo turno (economia P3).

## Packs

| Pack | Carregamento | Conteúdo | Status |
|---|---|---|---|
| **comum** | Sempre (cross-cutting) | Prioridades, segurança, git, testes, skills-e-código, logs | ✅ disponível |
| **java** | Stack Java/Spring | Idiomas Java 25 + Spring Boot 4; segurança da stack | ✅ disponível |
| **python** | Stack Python | Idiomas Python 3.13 + FastAPI; segurança da stack; memória RAM (`python/memoria.md`) | ✅ disponível |
| **angular** | Stack Angular | Idiomas Angular 21+; performance de frontend | ✅ disponível |

### Pack comum (este, sempre carregado)

| Arquivo | Eixo invariante |
|---|---|
| [`comum/prioridades.md`](comum/prioridades.md) | P1 > P2 > P3, desempate e veto de segurança |
| [`comum/seguranca.md`](comum/seguranca.md) | Secrets, Linha de Defesa, deny-list, supply chain |
| [`comum/git.md`](comum/git.md) | Conventional Commits PT-BR, branch antes da default, coautoria |
| [`comum/testes.md`](comum/testes.md) | TDD red→green, evidência real, cobertura como gate |
| [`comum/skills-e-codigo.md`](comum/skills-e-codigo.md) | Skills-first, fachada fina, least agency, blast radius |
| [`comum/logs.md`](comum/logs.md) | Logs por evento, correlação, segredo barrado, PII mascarada na origem — escritos certos na 1ª vez |

## Como um projeto seleciona packs por stack

A seleção segue a mesma lógica da **instalação seletiva de skills** (Fase 5): um perfil liga só o que a stack usa.

- Fonte da verdade dos perfis: [`manifest.json`](../manifest.json).
- Instalador: [`scripts/instalar.ps1`](../scripts/instalar.ps1) — ex.: `.\scripts\instalar.ps1 -Perfil backend-java`.

| Perfil (`manifest.json`) | Pack `comum` | Pack(s) de stack |
|---|---|---|
| `minimo` | ✅ sempre | — |
| `completo` | ✅ sempre | `java` + `python` + `angular` |
| `backend-java` | ✅ sempre | `java` (+ `angular` no frontend) |
| `dados` | ✅ sempre | conforme a linguagem do projeto |
| `ia` | ✅ sempre | conforme a linguagem do projeto |
| `seguranca` | ✅ sempre | — |

> O pack **comum** é a base de todos os perfis (espelha o `minimo` herdado por todos). Os packs de stack
> seguem o mesmo critério das skills do perfil: liga-se o pack da linguagem/cloud que o perfil declara usar.
