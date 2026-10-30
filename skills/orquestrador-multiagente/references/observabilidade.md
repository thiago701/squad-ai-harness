# Observabilidade & Telemetria em MAS

## OpenTelemetry GenAI (padrão)
Estende observabilidade de chamada única para **rastreios distribuídos multi-passo não-determinísticos**.
Convenções Semânticas GenAI diferenciam a natureza de cada operação:
- **Spans CLIENT** — chamadas reais às APIs de modelo; medem latência do fornecedor e **tokens** consumidos
  (`gen_ai.usage.input_tokens`/`output_tokens`, `gen_ai.request.model`, `gen_ai.response.finish_reasons`).
- **Spans INTERNAL** — atividade lógica/administrativa do ecossistema: decisões, memória local, roteamento.

> Estado real (jul/2026): convenções GenAI em *Development*; **client spans** estáveis, **agent/framework
> spans** experimentais mas estáveis na prática. **Verificado** — ver PROCEDENCIA.md.

## Atributos de tipo de span (específico AG2 — `ag2.span.type`)
`conversation` (sessão global) · `agent` (turno de um agente) · `llm` (parâmetros da chamada: temperatura,
config) · `tool` (ativação de função: args JSON + retorno) · `code_execution` (dentro de sandbox/interpretador)
· `human_input` (espera bloqueante por feedback) · `speaker_selection` (decisão de qual agente fala a seguir).
*(taxonomia do AG2/AutoGen; outros frameworks nomeiam diferente.)*

## Propagação entre agentes — W3C Trace Context (A2A)
O agente emissor injeta o header **`traceparent`** = `versão-traceId-spanIdPai-flags`, ex.:
`00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`. O recetor extrai e acopla os seus spans ao
**mesmo trace ID** → árvore de telemetria contínua num painel único. Padrão W3C — **verificado**.

## Overhead por plataforma (100 execuções idênticas)

| Plataforma | Overhead | Mecanismo | Perfil |
|---|---|---|---|
| **LangSmith** | ~0% | callbacks assíncronos em segundo plano | Mínimo; ótimo p/ produção, mas acoplado ao ecossistema LangChain |
| **Laminar** | ~5% | mínima instrumentação síncrona no caminho crítico | Produção com restrição severa de latência |
| **AgentOps** | ~12% | monitorização abrangente do ciclo de vida | Testes intensivos/validação funcional |
| **Langfuse** | ~15% | instrumentação densa passo-a-passo, serializa prompts/tokens/tabelas | Overhead alto pela serialização frequente |

*(números de overhead são user-provided/ilustrativos — não confirmados; ver PROCEDENCIA.md)*

## Diretriz
**Observabilidade assíncrona**: envio em **lote em segundo plano** (background batching) sob OTel GenAI,
para que serialização/gravação de traços **não** atrase a resposta percebida. A Squad já usa Langfuse em
alguns fluxos (plugin `langfuse`) — pesar o ~15% de overhead contra a densidade de dados desejada.
