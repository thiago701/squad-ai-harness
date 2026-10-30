# Subsistemas de Memória & Ciclo de Vida Cognitivo

## Cinco tipologias de memória operacional
1. **Trabalho (curto prazo)** — contexto ativo na janela de atenção; buffers rotativos/compactação;
   some ao fim do ciclo da tarefa.
2. **Episódica** — arquivo cronológico de experiências específicas (o quê, quando, sob que condições);
   permite usar sucessos/falhas passados para orientar decisões.
3. **Semântica** — conhecimento factual do domínio, regras de negócio, políticas; via **embeddings
   vetoriais** ou **grafos (GraphRAG)**.
4. **Procedimental** — competências de fluxo: sequência de ferramentas a invocar e regras de transição.
5. **Meta-memória** — auto-avaliação dos limites do próprio conhecimento; decide quando pedir mais
   contexto ou redefinir estratégia.

## Ciclo Escrever-Gerir-Ler (Write-Manage-Read)
- **Escrever** — preserve o episódio em **alta resolução**: prompt original, traço de raciocínio,
  chamadas de ferramenta e consequências observadas. **Sumarizar cedo corrompe irreparavelmente** a
  utilidade posterior da memória episódica.
- **Gerir** — consolidação e **despejo (eviction)**, inspirado em consolidação sináptica: tarefas
  assíncronas de reflexão (LLM de alta capacidade) traduzem experiência bruta em conhecimento semântico
  duradouro — eliminam contradições, atualizam preferências por **deduplicação adaptativa**, removem ruído.
- **Ler** — recuperação para o contexto ativo (qualidade da busca vetorial é crítica — ver falhas).

## Três falhas sem curadoria ativa
- **Deriva de sumarização** — recapitulações sucessivas eliminam detalhes; sobra memória imprecisa.
- **Diluição de atenção** — excesso de lixo contextual recuperado degrada a precisão de raciocínio da LLM.
- **Cegueira de memória** — factos cruciais gravados mas **nunca recuperados** por falha na busca vetorial.

> Ponte com a Squad: casa com `memoria-sessao` (memória de trabalho/sessão) e `aprendizado-continuo`
> (consolidação → conhecimento semântico). O ciclo aqui é o "porquê" teórico daqueles mecanismos.
