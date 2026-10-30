# Referências — Técnicas de Compactação de Contexto

## Literatura Relevante

### LLM Context Management
- Sliding Window Attention (Longformer, 2020): janela deslizante de contexto
- Retrieval-Augmented Generation (Lewis et al., 2020): externalizar memória
- MemGPT (Packer et al., 2023): gerenciamento hierárquico de memória LLM

### Analogias de Engenharia de Software
- Git commit = checkpoint de estado
- Stack frame = contexto de execução atual
- Core dump = snapshot completo para debug
- Log structured storage = append-only com compactação periódica

## Estimativas de Custo de Contexto

| Tipo de Conteúdo | Tokens Típicos | Compactado |
|---|---|---|
| Output pytest 100 testes | ~300 tokens | ~15 tokens |
| Arquivo Python 200 linhas | ~600 tokens | ~40 tokens |
| Decisão arquitetural | ~50 tokens | ~50 tokens (não compactar) |
| Log bash de instalação | ~200 tokens | ~5 tokens |
| Sprint checkpoint completo | ~100 tokens | ~100 tokens |

## Quando NÃO compactar

1. Durante uma task crítica (meio de uma implementação)
2. Quando há erros não resolvidos (contexto do erro é necessário)
3. Quando o usuário está revisando ativamente o output
4. Antes de confirmar que todos os commits foram feitos
5. Quando há ação de ferramenta ainda aberta no turno atual (a fatia pararia antes dela)
6. Quando a fatia a esquecer não pesa mais que o último resumo (o resumo novo não encolhe nada)
7. Se o sumarizador falhar: siga com o histórico original (fail-open), nunca com a fatia apagada

## Ferramentas Complementares

- `memoria-sessao` skill: salva checkpoints em arquivo
- `.auto-memory/`: sistema de memória persistente entre sessões
- Git log: fonte de verdade para o que foi implementado
