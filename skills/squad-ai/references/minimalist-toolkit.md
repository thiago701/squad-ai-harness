# Toolkit Minimalista — Heurísticas, Advogado do Diabo, Antipadrões Nomeados

> Toolkit de bolso absorvido da skill `arquiteto-minimalista`. A squad-ai já consagra **P1 Simplicidade > P2 Performance > P3 Custo** como regra imutável; este guia entrega o **instrumental prático** para aplicá-la em design reviews e debates arquiteturais.

## Quando consultar este guia

- Revisão de ADR — antes de aceitar, passe pelo **Advogado do Diabo** (abaixo).
- Debate sobre introduzir tecnologia nova (Kafka, Kubernetes, Redis, event sourcing...).
- Refactor grande proposto — "vamos reescrever em microsserviços".
- Design de novo bounded context — antes de C4 e DBML.
- Sempre que alguém disser "precisamos escalar" sem apresentar número observado.

Este guia **complementa** e **acelera** o trabalho do Arquiteto Minimalista. Não substitui sua skill — dá a ele (e aos outros agentes) um kit de ferramentas compartilhado.

## A bússola

Antes de qualquer resposta arquitetural, pergunte:

> "Existe uma solução mais simples que resolve 95% do problema com 20% do custo operacional?"

Se sim: proponha-a primeiro. Se não: explicite por que não.

## Dicotomia da Complexidade

Toda complexidade é de um dos dois tipos. Nomeie-o antes de discutir solução:

| Tipo | Origem | Ação |
|---|---|---|
| **Essencial** | Regras intrínsecas do domínio | Respeitar, modelar bem (DDD forte) |
| **Acidental** | Ferramentas ruins, abstrações vazadas, modismo | Combater impiedosamente |

**Exemplo:** "Temos 40 regras de cálculo tributário" é complexidade essencial — aceite, modele com clareza. "Temos 7 camadas de abstração para esconder JPA" é acidental — delete camadas.

Regra de bolso: se você consegue explicar a complexidade em 3 frases para quem não conhece o domínio, é essencial. Se precisa desenhar um slide de 20 caixas, é acidental.

## Heurísticas Rápidas de Decisão

| Situação | Default | Só evolua se... |
|---|---|---|
| Produto novo / startup | Monólito modular com pacotes bem definidos | Pressão real de deploy independente por time |
| Time < 8 engenheiros | Um serviço, no máximo 2-3 | Você tem um gargalo **observado** por domínio |
| Cache | `Caffeine` (em processo) | Estado precisa ser compartilhado entre instâncias |
| Fila de tarefas | Tabela Postgres + worker com `@Scheduled` | Throughput > 5k msgs/s sustentado |
| Orquestração | `docker compose` | Você tem multi-cluster, multi-região, ou > 20 serviços |
| Observabilidade | Logs JSON + OpenTelemetry traces | Precisa de SLO formal com error budget |
| Autenticação | JWT em Authorization header + Spring Security | Precisa de SSO corporativo, mTLS ou Passkeys |
| Mensageria externa | SQS | Você tem streaming stateful (windowing, join) — aí Kafka |
| CQRS | In-process (Command/Query handlers separados) | Leituras competem em hardware com escritas em volume medido |
| Event Sourcing | **NÃO** | Você precisa de auditoria regulatória imutável + reconstrução temporal (fintech/saúde) |
| DDD tático completo | Só em domínios genuinamente ricos | Domínio simples = camadas claras bastam |
| Microsserviços | NÃO | Times autônomos em escala + deploy independente exigido + hotspots escalam diferente |
| Kubernetes | ECS / App Runner / Lambda primeiro | Multi-cloud, operadores customizados, ou > 50 serviços |
| Redis | Postgres + índice + cache local primeiro | Pattern de acesso exige TTL fino, pub/sub, ou lua scripting |

**Leitura correta da tabela:** a coluna "Default" é ponto de partida, não ponto de chegada. "Só evolua se..." lista os **gatilhos legítimos** para evoluir. Ausência de gatilho observado = mantenha o default.

## Advogado do Diabo — 4 perguntas obrigatórias

Quando alguém propuser arquitetura complexa (microsserviços, event sourcing, CQRS distribuído, Kafka, Kubernetes), o Arquiteto Minimalista (e o Tech Lead no review) **fazem estas 4 perguntas, sempre, por escrito**:

1. **Qual problema específico e atual isso resolve que a alternativa simples não resolve?**
   - "Escalabilidade" não é resposta. "RPS observado de 2k com p95 de 800ms no módulo X" é resposta.

2. **O time está preparado para o custo operacional?**
   - Observabilidade distribuída (traces cruzando serviços).
   - Debugging de falhas assíncronas e parciais.
   - Deploy coordenado de contratos.
   - Schema registry, compatibilidade, evolução de eventos.

3. **Você já tem esse problema hoje, ou está antecipando um cenário que pode nunca ocorrer?**
   - Use YAGNI — "You Aren't Gonna Need It". Arquitetura para escala que não veio custa hoje e provavelmente será jogada fora se vier (os padrões de carga raramente batem com a previsão).

4. **Qual é o caminho de volta se essa escolha estiver errada?**
   - Se a resposta for "meses", exija evidência muito forte.
   - Se a resposta for "horas-dias", é aposta aceitável.

Se qualquer uma destas 4 perguntas não tem resposta satisfatória: a proposta **volta para o autor** com essas perguntas como lição de casa. Nenhum ADR passa sem as 4 respondidas.

## Antipadrões Nomeados (chame pelo nome)

Quando identificar, **nomeie explicitamente**. Chamar pelo nome acelera o consenso e descolou o debate do ego do autor.

### 1. "Arquitetura por Currículo"
**Sinal:** escolha técnica motivada por aparecer bem no LinkedIn / artigo de blog, não pelo problema.
**Exemplo:** "Vamos usar Kafka + Axon + Kubernetes porque é o que a Netflix usa."
**Resposta:** "Você é a Netflix? Qual é a sua escala? Qual é a sua equipe?"

### 2. "Distributed Monolith"
**Sinal:** múltiplos serviços com acoplamento síncrono forte — o pior dos dois mundos.
**Exemplo:** 5 microsserviços que **todos** precisam subir juntos ou nada funciona.
**Resposta:** "Se não dá para fazer deploy de um sem os outros, por que separou?"

### 3. "Integração por Banco de Dados"
**Sinal:** dois serviços compartilhando tabelas diretamente.
**Exemplo:** Serviço A consulta `clientes` do banco do Serviço B via SELECT cruzado.
**Resposta:** "Isso cria acoplamento invisível. Use API ou evento via Outbox."

### 4. "Abstração Prematura"
**Sinal:** interface criada sem necessidade real de variação.
**Exemplo:** `interface PedidoService` com uma única implementação `PedidoServiceImpl`.
**Resposta:** "Qual é a segunda implementação que justifica a interface? Se não existe e não está no horizonte de 6 meses, delete."

### 5. "Consistency over Simplicity"
**Sinal:** padrão uniforme forçado em todo o sistema, mesmo onde partes têm necessidades radicalmente diferentes.
**Exemplo:** "Todos os módulos devem ter Kafka, mesmo os que só processam 1 mensagem/dia."
**Resposta:** "Consistência é útil onde reduz custo cognitivo. Onde obriga overengineering local, vira anti-padrão."

### 6. "Escalar agora para 1M RPS"
**Sinal:** arquitetar hoje para tráfego hipotético 100x maior.
**Resposta:** "Quando você tiver 10x o tráfego atual, você ainda estará dentro do default. E terá dados reais para projetar os próximos 10x."

### 7. "Reescrever do zero"
**Sinal:** "o código está ruim, vamos reescrever."
**Resposta:** "Reescritas grandes levam 3x o prazo estimado e reintroduzem bugs que a versão atual já resolveu. Proponha refactor incremental com Expand-Contract."

### 8. "Framework de Configuração"
**Sinal:** "vamos criar um framework interno que outros times usam".
**Resposta:** "Qual é o segundo usuário? Se não existe, é só uma lib da sua squad. Frameworks internos são o caminho mais caro para viralizar bugs."

### 9. "Microservice Too Small"
**Sinal:** serviço com 2 endpoints, 1 tabela, 1 deploy independente mas acoplado a 4 outros.
**Resposta:** "Monte como módulo no monólito com fronteira clara. Extrair quando o custo de acoplamento superar o custo operacional."

### 10. "Plataforma sem Cliente"
**Sinal:** squad de "platform engineering" construindo plataforma sem produto real consumindo.
**Resposta:** "Plataforma valida-se com uso, não com roadmap. Qual squad vai usar isso nos próximos 30 dias?"

## Avaliação de Manutenibilidade Humana

Todo design proposto passa por 3 perguntas (além de performance e custo):

1. **Legibilidade** — um engenheiro novo entende o fluxo principal em ≤ 30 minutos?
2. **Testabilidade** — as unidades de negócio são testáveis sem infraestrutura externa?
3. **Evolutibilidade** — adicionar uma feature nova toca quantos lugares? Se > 5, alerta.

Se qualquer uma falha: provavelmente temos complexidade acidental para combater.

## Tom e Linguagem

- **Direto** — não elogie escolha ruim para não constranger. Clareza respeitosa > cortesia vazia.
- **Trade-off explícito** — "Esta escolha otimiza X ao custo de Y" em vez de "Isso é ruim".
- **Analogia concreta** — quando a abstração embacia, traga analogia do mundo físico.
- **Pergunta que avança** — termine com "Qual destas alternativas faz sentido dado o time e o prazo?".
- **Argumento técnico > pressão social** — se você discorda, apresente o argumento com clareza; não recue sem contrapartida técnica real.

## Sinais de saúde de uma arquitetura minimalista

- ✅ Novo engenheiro produtivo em ≤ 2 dias.
- ✅ `docker compose up` sobe tudo que precisa para rodar o sistema localmente.
- ✅ Testes de integração rodam sem infra AWS real (Testcontainers + LocalStack).
- ✅ ADRs explicam **por que não escolhemos X**, não só por que escolhemos Y.
- ✅ Linguagem ubíqua entre glossário e código é idêntica.
- ❌ Diagrama da arquitetura não cabe em uma tela.
- ❌ "Precisa de 3 janelas abertas para debugar 1 request".
- ❌ Time gasta mais tempo em infra do que em feature de negócio.

## Checklist — Design Review Express (5 min)

Antes de aprovar um C4 ou um ADR, passe por:

- [ ] Complexidade essencial vs acidental nomeada?
- [ ] Solução mais simples que resolve 95% foi considerada e descartada com justificativa?
- [ ] As 4 perguntas do Advogado do Diabo estão respondidas (se a proposta é complexa)?
- [ ] Antipadrão da lista acima se aplica? (Se sim, nomeado?)
- [ ] Manutenibilidade humana: legibilidade, testabilidade, evolutibilidade validadas?
- [ ] Caminho de volta existe (reversibilidade)?

Aprovação sem esse checklist = risco de colecionar complexidade acidental.

## Relacionadas

- [[Skill - Arquiteto Minimalista]]
- [[Tres Prioridades Imutaveis]]
- `references/adr-guide.md` — template para formalizar decisões
- `references/code-review-guide.md` — 4 lentes para PR
- `references/documentation-guide.md` — documentar decisões sobreviventes
