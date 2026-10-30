# Arquitetura AI-Native — Padrão de Desenvolvimento da Squad AI

> **O que é este documento.** O padrão arquitetural que a Squad AI adota **por default em todo projeto**. Trata da *meta-arquitetura*: como desenhar o sistema para que agentes de IA o **especifiquem, codifiquem, testem, mantenham e validem de ponta a ponta** com o mínimo de fricção. Não é sobre o produto usar IA — é sobre IA *construir* o produto. Por isso vale para qualquer projeto, com ou sem IA no resultado final.
>
> Carregue este reference na **Fase 2 (DESIGN)** e consulte-o sempre que desenhar fronteiras, escolher onde isolar o que muda, ou definir como o agente vai se autovalidar.

## Índice
1. [A tese em uma frase](#1-a-tese-em-uma-frase)
   - ★ [Os três princípios mestres (simplicidade · performance · manutenibilidade)](#os-três-princípios-mestres--o-norte-que-os-pilares-servem)
2. [Os 7 pilares AI-native](#2-os-7-pilares-ai-native)
3. [As três camadas de contrato com a IA](#3-as-tres-camadas-de-contrato-com-a-ia)
4. [Catálogo de fronteiras executáveis (ArchUnit A1–A9)](#4-catalogo-de-fronteiras-executaveis-archunit-a1a9)
5. [Workflow canônico do agente por fatia](#5-workflow-canonico-do-agente-por-fatia)
6. [Anti-padrões a vigiar](#6-anti-padroes-a-vigiar)
7. [O que NÃO fazer (recusas explícitas)](#7-o-que-nao-fazer-recusas-explicitas)
8. [Como cada fase do pipeline aplica o padrão](#8-como-cada-fase-aplica-o-padrao)

---

## 1. A tese em uma frase

> **A melhor arquitetura para desenvolvimento dirigido por IA é a que transforma cada decisão humana em uma restrição executável** — de modo que o agente tenha liberdade máxima dentro de fronteiras que o *build* (não a boa vontade, não a memória do prompt) garante.

Um agente de IA é um colaborador rápido, incansável e **literal**: faz exatamente o que o contrato permite. A fricção do desenvolvimento com IA não está em gerar código — está em (a) **especificar** sem ambiguidade, (b) dar ao agente um **loop de feedback fechado** (ele precisa saber sozinho se acertou) e (c) **impedir estruturalmente** que ele viole uma regra que ninguém lembrou de repetir no prompt.

O inimigo continua sendo a **complexidade acidental** — e com IA ela custa mais caro: cada peça móvel a mais é mais superfície para alucinar, mais contexto para carregar, mais ambiguidade para errar. **Menos partes móveis = mais throughput de IA confiável.** Por isso AI-Native e minimalismo (P1) são o mesmo princípio visto de dois ângulos.

---

## Os três princípios mestres — o norte que os pilares servem

Os 7 pilares (§2) são **meios**. Os fins são três princípios mestres de qualidade, e **toda decisão de arquitetura é julgada por eles** — com o tie-break **P1 > P2 > P3** quando conflitarem.

### 1. Simplicidade no código (P1 — vence sempre)
Código que qualquer pessoa do time entende em **< 10 min**. Simplicidade não é "menos linhas" — é **menos coisas para entender**: menos conceitos, menos indireção, menos partes móveis. Com IA isso conta dobrado: cada peça a mais é mais superfície para o agente alucinar e mais contexto para carregar. *Servida por:* Pilar 2 (fronteiras pequenas e explícitas), Pilar 3 (o que muda fica isolado atrás de um port), e a recusa a overengineering (§6/§7). **Sintoma de violação:** o agente precisa abrir 5 arquivos para mudar 1 comportamento.

### 2. Alta performance (P2 — com evidência, nunca por palpite)
O sistema cumpre **SLAs explícitos** (p95/p99 por operação) sob carga real. A disciplina AI-native: **performance também é um oráculo determinístico** — define-se a meta na Fase 2, valida-se com teste de carga (k6/Locust) dentro da malha de feedback (Pilar 5), e **otimiza-se só onde há evidência de gargalo** (profiling antes de mexer). Sem SLA definido, "está rápido" é opinião. Cuidado com o agente que "otimiza" sem medir — quase sempre adiciona complexidade (fere P1) sem ganho provado.

### 3. Manutenibilidade e evolução (a aposta de longo prazo)
O sistema precisa ser **seguro de mudar** — porque vai mudar, e quem muda (humano ou agente) precisa fazê-lo sem quebrar invariantes que esqueceu. É aqui que o AI-native mais brilha: o **código é a arquitetura** (ArchUnit impede erosão de fronteira — Pilar 2), cada decisão tem um **ADR** que explica o porquê (o agente não re-infere), a **rastreabilidade por ID** (Pilar 1) liga requisito↔código↔teste, e as fronteiras de bounded context são **pontos de extração baratos** quando o sistema precisar crescer. Evoluir = abrir uma fatia nova pelo workflow canônico (§5), confiando nos oráculos para não regredir. **Manutenibilidade é a irmã da Simplicidade:** o que é simples de entender é seguro de mudar.

> **Como os três se relacionam.** Simplicidade e Manutenibilidade puxam na mesma direção (P1); Performance (P2) às vezes tensiona com elas — e o tie-break decide: só se paga complexidade por performance **com número que prove o gargalo**. Custo baixo (P3) é o eixo econômico, subordinado aos três. Os 7 pilares a seguir existem para entregar este norte — não são fins em si.

---

## 2. Os 7 pilares AI-native

Cada pilar é um mecanismo concreto, não um slogan. Em DESIGN, o arquiteto deve conseguir apontar **onde no repositório** cada um vai morar.

**Pilar 1 — Spec-as-source-of-truth com rastreabilidade por ID.**
Todo requisito tem um identificador estável (`RN-*` regra de negócio, `NFR-*` requisito não-funcional, `I-*` invariante, `US-*` user story, `IA-UC-*` caso de uso de IA). Código, testes e commits citam esses IDs. O resultado é uma cadeia **requisito → ADR → módulo → teste** navegável por máquina, nos dois sentidos. É o que permite detectar requisito órfão (implementado sem prova) e teste órfão (sem âncora na spec).

**Pilar 2 — Fronteiras como mecanismo de build (não como disciplina).**
1 módulo por bounded context; camadas Clean impostas por testes de arquitetura (ArchUnit/equivalente); kernel compartilhado minimalista. O agente recebe um espaço onde **o erro estrutural é impossível de cometer silenciosamente** — o build vermelho avisa antes do humano. Ver §4.

**Pilar 3 — IA atrás de ports: fornecedor é configuração.**
`LlmPort`, `AsrPort`, `EmbeddingsPort` (ou equivalentes) isolam todo SDK de IA na camada de infraestrutura de um único contexto. Trocar de provedor (Claude↔Gemini↔Nova) ou de modo (`mock`↔`real`) é variável de ambiente, **não toca o domínio nem exige re-geração de código**. Aplicação literal de "isole o que muda atrás de uma fronteira de troca barata".

**Pilar 4 — Mock-first e determinismo: o agente desenvolve sem nuvem e sem segredo.**
Mock de LLM/ASR (ex.: WireMock ou serviço mock próprio), dados 100% sintéticos, `make up` sobe o sistema inteiro local. O agente itera em segundos, sem chave de API, sem dado real, sem gate externo. **O caminho de desenvolvimento é offline e reprodutível** — condição para rodar centenas de ciclos por hora.

**Pilar 5 — Loop de feedback fechado: o agente sabe sozinho se acertou.**
O pilar mais subestimado. Um agente só é produtivo se **verifica o próprio trabalho sem humano**. Entregue isso com uma malha densa de *oráculos determinísticos*: smoke e2e binário (verde/vermelho), testes de integração transacionais, suítes de autorização negativa e "PII em logs", ArchUnit. Cada um dá um veredito sem julgamento humano. Quanto mais densa a malha, mais o agente trabalha sozinho.

**Pilar 6 — Contratos explícitos validados pós-geração.**
Eventos têm schema (`*.schema.json`) validado em teste de contrato. Saídas de LLM têm contrato (JSON schema, citação resolvível, lista proibida) validado **deterministicamente pós-geração**. O agente nunca precisa "confiar" numa saída de IA — a estrutura é checada por código. Princípio: **a IA gera, o código determinístico decide e valida.**

**Pilar 7 — Orquestração multi-agente versionada.**
O próprio processo de construção é artefato: prompts versionados (com `manifest.json`, hash, modelo-alvo), backlog executável, registro de atividades como trilha de auditoria. Mudar um prompt é um *release* com eval, não uma edição solta.

---

## 3. As três camadas de contrato com a IA

Da mais "mole" (texto) à mais "dura" (build quebra). Quanto mais para baixo, mais o agente pode operar sem revisão humana linha a linha.

1. **Contrato semântico — a especificação.** `docs/` é a fonte de verdade. O agente lê PRD, RN-*, NFR-*, I-* **antes** de escrever qualquer linha. Regra máxima: *"não comece pelo código; primeiro amadureça até o SPEC_FREEZE da fatia."*
2. **Contrato estrutural — as fronteiras.** Cada bounded context é um módulo com camadas; só a camada `api/` é visível a outros contextos; `domain/` não depende de nada externo além do kernel. Isso é o grafo de dependências do build, não uma convenção.
3. **Contrato executável — os testes de arquitetura.** ArchUnit transforma as regras acima em asserções de build. **Se o agente cruzar uma fronteira proibida, o build vermelho avisa antes do humano.** A regra dura é o que permite confiar em código gerado sem reler cada linha.

> Um prompt pode esquecer de dizer "não chame o repositório de outro contexto". Um teste ArchUnit nunca esquece.

---

## 4. Catálogo de fronteiras executáveis (ArchUnit A1–A9)

Catálogo de referência (instancie por projeto — nem toda regra existe desde a 1ª fatia; cada uma nasce quando o módulo que ela protege nasce). Cada regra é "um prompt que você nunca mais precisa escrever".

| Regra | Invariante de arquitetura | Falha se… |
|---|---|---|
| **A1** | Fronteira de BC: um contexto só enxerga o `api/` de outro | classe fora de `*.api` é importada cross-context |
| **A2** | Direção de camadas: `domain ← application ← infrastructure`; `api` não depende de `infrastructure` | dependência na direção errada |
| **A3** | `domain/` puro: depende só do runtime base + kernel compartilhado | `domain` importa framework, ORM, SDK ou outro BC |
| **A4** | SDK/fornecedor de IA só na `infrastructure` do contexto de IA | tipo de SDK de IA fora dos adapters |
| **A5** | Kernel compartilhado minimalista: depende só do runtime base | kernel ganha dependência externa |
| **A6** | Componentes "sem IA" por decisão (ex.: edge/SaMD) não importam geração de IA | componente proibido referencia LLM/geração |
| **A7** | Isolamento de integração externa: nenhum tipo de protocolo externo (FHIR/HL7, etc.) vaza do seu adapter | tipo externo exposto em `api/` ou outro BC |
| **A8** | Isolamento de dados/identidade: cada `infrastructure` só acessa o schema do próprio BC; dado sensível confinado | acesso cruzando schema/identidade de outro BC |
| **A9** | Higiene: sem segredo no repo, sem `System.out`/PII em log; logger estruturado no caminho auditado | uso proibido detectado |

**Teste do teste.** Mantenha 3 violações sintéticas (fora do classpath de produção) que **devem** quebrar o build — garante que a suíte realmente pega o que promete. Sem isso, uma suíte ArchUnit pode passar verde por não testar nada.

---

## 5. Workflow canônico do agente por fatia

Sequência para qualquer incremento (uma onda ou uma US):

```
1. LER a spec      → docs/ (RN/NFR/I/US relevantes) + ADRs + invariantes do BC alvo
2. CONGELAR escopo → SPEC_FREEZE da fatia: o que entra, hipóteses reversíveis, critérios de aceite
3. ESCREVER teste  → caso de aceite primeiro (oráculo), citando os IDs (US-005, I-023…)
4. GERAR código    → dentro de UM módulo/camada; ports para o que é externo
5. RODAR o loop    → make up + smoke e2e + ArchUnit + ITs → veredito determinístico
6. VALIDAR         → guardrails/eval offline (se toca IA) + checklist de aceite da fatia
7. REGISTRAR       → CHANGELOG + registro de atividades + commit citando os IDs
```

A regra de ouro — **"não comece pelo código"** — evita o anti-padrão nº 1 de IA: gerar muito código sobre spec ambígua e ter que refazer. **Especificar é mais barato que regenerar.**

**Onde o humano decide:** aprovação do SPEC_FREEZE, merge de PR, e gates externos (segurança, compliance, regulatório). A IA propõe e valida; o humano congela escopo e libera.

---

## 6. Anti-padrões a vigiar (especialmente com IA gerando rápido)

- **Geração sobre spec ambígua.** Sintoma: retrabalho em massa. Cura: SPEC_FREEZE antes de código.
- **Abstração prematura por IA.** Agentes adoram criar `Factory`/`Strategy`/interface para uma única implementação. Regra: a abstração nasce na 2ª variação, não na 1ª (YAGNI).
- **Erosão silenciosa de fronteira.** Import "que funciona" cruzando BCs. Cura: ArchUnit (§4) — sem isso, a arquitetura degrada na velocidade da geração.
- **Config virando código.** Valor mágico hardcodado que deveria ser parâmetro. Cura: catálogo único de configuração.
- **Saída de IA tratada como confiável.** Cura: validação pós-geração por schema/contrato (Pilar 6).
- **"Consistência sobre simplicidade".** Forçar CQRS/outbox/hexagonal pleno onde não dói. Use só onde paga o peso.

---

## 7. O que NÃO fazer (recusas explícitas)

Tudo abaixo é complexidade acidental que **reduz** o throughput de IA confiável:
- Fila/event sourcing no SDLC quando uma transação local resolve.
- Microsserviço por bounded context para time pequeno (vira *distributed monolith*).
- Framework de orquestração pesado além do mínimo versionado.
- Banco vetorial dedicado para corpus minúsculo (pgvector no banco existente basta).
- Abstrair geradores/scaffolding antes da 2ª necessidade real.

---

## 8. Como cada fase aplica o padrão

| Fase | O que o padrão AI-native exige |
|---|---|
| **Discovery** | IDs estáveis em todo requisito (RN/NFR/I/US/IA-UC) — base do Pilar 1. Critérios de aceite em Given-When-Then (viram oráculos). |
| **Design** | Decidir explicitamente: fronteiras de BC (Pilar 2), ports do que é externo/IA (Pilar 3), catálogo ArchUnit aplicável (§4), o que é mock-first (Pilar 4), e **quais oráculos determinísticos** o agente terá (Pilar 5). Registrar cada decisão como ADR citado pela pasta que justifica. |
| **Build** | Gerar dentro de UM módulo/camada; ports para o externo; prompts versionados; config nunca hardcodada. |
| **Test** | A malha de oráculos (Pilar 5): unit + integração transacional + contrato (Pilar 6) + eval offline para IA. |
| **Review** | Verificar que cada decisão humana virou restrição executável; que não há requisito/teste órfão; que fronteiras estão guardadas por ArchUnit. |
| **Deliver** | `make up` reproduz o sistema; gate de eval por release para o que toca IA generativa. |

> **Critério de "arquitetura AI-native pronta" (gate da Fase 2):** o arquiteto consegue apontar, para cada um dos 7 pilares, **o mecanismo concreto e onde ele mora** — e listar os oráculos determinísticos que permitirão ao agente se autovalidar na Fase 3. Se um pilar não tem mecanismo, ele é um gap a fechar antes do Build.
