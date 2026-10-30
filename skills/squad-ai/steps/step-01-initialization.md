# Step 1 — Inicialização e Planejamento

## Objetivo

Montar a infraestrutura de comunicação da squad, coletar contexto mínimo do projeto, validar disponibilidade dos agentes e produzir o plano de trabalho por fases.

---

## 1. Montar a Infraestrutura

```bash
python .agent/skills/squad-ai/scripts/squad_manager.py iniciar
```

Cria/limpa: `registro_atividades.json`, `caixa_entrada/`, `travas/`, `aviso_geral.msg`, `artefatos/`, `metricas/`. **Preserva** `decisoes/`.

---

## 2. Coletar Contexto do Projeto

Se o usuário não forneceu, pergunte (uma única rodada):

```
CONTEXTO OBRIGATÓRIO
  1. Nome do projeto (kebab-case) e groupId Maven
  2. Problema de negócio em 1 parágrafo (não a solução)
  3. Bounded contexts candidatos (ex: "pedidos, pagamentos, catalogo")
  4. Escopo: MVP (1-2 contextos, 3-5 stories) ou completo?
  5. Envolve IA/agentes/LLM?
  6. Modo de execução: sequencial (padrão) ou paralelo
  7. Arquivo .dbml ou DER existente? (se sim, localização)

STACK É FIXA (não perguntar, apenas confirmar):
  Java 25 + Spring Boot 4 + Spring 7 + Aurora PostgreSQL + Flyway +
  Maven 4 multi-module + Testcontainers. Desvios exigem ADR explícito.
```

### 2.1 Contexto de Banco (se .dbml/DER existir)

```
PROTOCOLO DE CONTEXTUALIZAÇÃO
  □ Localizar .dbml em raiz ou docs/
  □ Parsear tabelas, colunas, tipos, FKs, indexes, enums
  □ Mapear relacionamentos: > (1:N), < (N:1), - (1:1), <> (N:N)
  □ Registrar DER como artefato de referência para TODAS as fases
  □ Entities JPA e migrations Flyway DEVEM ser coerentes com o DBML
  □ Domain Entities ≠ JPA Entities — mapper obrigatório
  □ Regra: .dbml é a fonte de verdade do esquema. Mudança começa lá.
```

---

## 3. Selecionar Agentes

```
NÚCLEO (sempre):
  ✓ engenheiro-especificacao
  ✓ arquiteto-minimalista
  ✓ especialista-banco
  ✓ engenheiro-clean-architect
  ✓ java25-spring-boot
  ✓ engenheiro-devops
  ✓ especialista-qualidade
  ✓ tech-lead-review

CONFORME CONTEXTO:
  △ arquiteto-cloud-aws       — se deploy em AWS (Aurora PG → quase sempre)
  △ arquiteto-performance     — se SLAs p99 rigorosos
  △ engenheiro-seguranca      — se dados sensíveis ou autenticação
  △ localstack-dev            — se dev local precisa simular AWS
  △ arquiteto-ia              — se há LLMs/RAG/agentes de IA
```

Validar disponibilidade:

```bash
python .agent/skills/squad-ai/scripts/squad_manager.py validar_skills \
  "engenheiro-especificacao,arquiteto-minimalista,especialista-banco,\
engenheiro-clean-architect,java25-spring-boot,engenheiro-devops,\
especialista-qualidade,tech-lead-review"
```

Se alguma skill não estiver disponível, notifique e sugira alternativa.

---

## 4. Criar Plano de Trabalho

Registre as atividades-semente de cada fase:

```bash
python .agent/skills/squad-ai/scripts/squad_manager.py criar_atividade \
  "Levantamento DDD e user stories BDD" "engenheiro-especificacao" "" "discovery"

python .agent/skills/squad-ai/scripts/squad_manager.py criar_atividade \
  "Design C4 + ADRs + estratégia CQRS/Outbox" "arquiteto-minimalista" "" "design"

python .agent/skills/squad-ai/scripts/squad_manager.py criar_atividade \
  "Scaffold Java 25 + domínio rico via TDD" "engenheiro-clean-architect" "" "build"

# ... idem para test, review, deliver
```

---

## 5. Confirmar Stack com o Usuário

Apresente (curto):

```
PLANO DE PROJETO: <nome>
━━━━━━━━━━━━━━━━━━━━━━━━

Stack confirmada (padrão da squad, fixa):
  • Java 25 + Spring Boot 4 / Spring 7
  • Aurora PostgreSQL + Flyway
  • Maven 4 multi-module (domain/application/infrastructure/bootstrap)
  • CQRS in-process + Outbox, DDD forte
  • Testes: JUnit 5 + AssertJ + Testcontainers + ArchUnit
  • Docker multi-stage + docker-compose dev

Squad: <N> agentes
Modo: sequencial

FASES:
  1. Discovery  → <agentes>
  2. Design     → <agentes>
  3. Build      → <agentes> (usa scaffold automatizado)
  4. Test       → <agentes>
  5. Review     → <agentes>
  6. Deliver    → <agentes>

Próximo passo: Discovery (DDD + BDD).
```

Se o usuário pedir desvio da stack, gere ADR e aprove via Tech Lead **antes** de prosseguir.

---

## 6. Próximo Step

`./step-02-discovery-design.md`
