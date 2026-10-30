# Padrões de Raciocínio & Recuperação

## Raciocínio: de ReAct a Plan-then-Execute
- **ReAct** (clássico) — versátil para exploração aberta, mas **desvia para loops** com dados ruidosos
  ou parâmetros de ferramenta imprecisos.
- **Plan-then-Execute** (produção) — **isola a fase de planeamento** do ciclo físico de execução. O plano
  é um **contrato imutável**, sujeito a **aprovação** (humano ou guarda de política determinística) antes
  de ativar os nós de execução. Reduz derrapagem e dá ponto de controlo/custo.

## RAG dinâmico guiado por modelos especializados
- **RAG Adaptativo** — classificador de entrada decide: busca semântica simples vs decomposição lógica
  multi-passo em bases distribuídas. Ajusta o investimento computacional à complexidade do pedido.
- **Self-RAG (Auto-RAG)** — o LLM emite **tokens de crítica interna**: avalia se o conteúdo recuperado é
  factual e se a resposta responde de facto; **reinicia a busca** se detetar incoerência.
- **CRAG (RAG Corretivo)** — camada que avalia a **relevância dos documentos antes** do gerador; se a
  informação é ambígua/insuficiente, descarta fontes fracas e faz **busca corretiva na web** para
  preencher lacunas.

### Heurística
Comece simples (busca semântica direta). Suba para Adaptativo quando o domínio tem perguntas de
complexidade heterogénea; adicione Self/CRAG quando o custo de uma resposta factualmente errada é alto.
Cada camada de crítica/correção **gasta tokens e latência** (P2/P3) — justifique com o requisito.

> Ponte com a Squad: RAG/vetorial de baixo nível → `arquiteto-ia`. Plano-como-contrato casa com o GATE
> humano da Squad ("gated, not autonomous").
