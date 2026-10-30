# Referência — RAG — Retrieval-Augmented Generation (pipeline, chunking, grounding)

> Parte da skill `arquiteto-ia`. Carregue sob demanda. Hub: `../SKILL.md`.
## RAG — Retrieval-Augmented Generation

### Arquitetura RAG Bem Estruturada
```
┌──────────────────────────────────────────────────────────┐
│                    PIPELINE RAG                          │
│                                                          │
│  INDEXAÇÃO (offline):                                    │
│  Documento → Chunker → Embedder → Vector Store           │
│                                                          │
│  CONSULTA (online):                                      │
│  Pergunta → Embedder → Vector Store (busca) →            │
│  Chunks relevantes → Prompt montado → LLM → Resposta     │
│                                                          │
│  GUARDRAIL:                                              │
│  Resposta → Verificador de grounding → Output            │
└──────────────────────────────────────────────────────────┘
```

```python
# RAG bem estruturado com portas e adaptadores
from typing import Protocol
from dataclasses import dataclass

@dataclass(frozen=True)
class Chunk:
    conteudo: str
    fonte: str
    score_relevancia: float
    metadados: dict

class VectorStorePort(Protocol):
    def indexar(self, texto: str, metadados: dict) -> str: ...
    def buscar(self, query: str, top_k: int = 5) -> list[Chunk]: ...

class EmbedderPort(Protocol):
    def embedar(self, texto: str) -> list[float]: ...


class RAGService:
    """Orquestra recuperação + geração. Responsabilidade única: montar contexto e gerar."""

    PROMPT_TEMPLATE = """
Com base exclusivamente nos documentos abaixo, responda à pergunta.
Se a informação não estiver nos documentos, responda: "Não encontrei essa informação nos documentos disponíveis."
Nunca invente ou suponha informações.

DOCUMENTOS:
{contexto}

PERGUNTA:
{pergunta}
"""

    def __init__(self, vector_store: VectorStorePort, llm: LLMPort, top_k: int = 5):
        self._store   = vector_store
        self._llm     = llm
        self._top_k   = top_k

    def responder(self, pergunta: str) -> tuple[str, list[Chunk]]:
        chunks = self._store.buscar(pergunta, top_k=self._top_k)

        if not chunks:
            return "Não encontrei documentos relevantes para esta pergunta.", []

        contexto = "\n\n---\n\n".join(
            f"[Fonte: {c.fonte}]\n{c.conteudo}" for c in chunks
        )
        prompt = self.PROMPT_TEMPLATE.format(contexto=contexto, pergunta=pergunta)
        resposta = self._llm.completar(prompt, temperatura=0.0)

        return resposta.content, chunks  # retorna fontes para rastreabilidade


# Chunking estratégico — não use tamanho fixo cegamente
class ChunkerInteligente:
    """Divide documentos respeitando estrutura semântica."""

    def chunkar_por_secao(self, documento: str, tamanho_max: int = 1000) -> list[str]:
        """Divide por cabeçalhos e parágrafos antes de dividir por tamanho."""
        secoes = self._dividir_por_cabecalhos(documento)
        chunks = []
        for secao in secoes:
            if len(secao) <= tamanho_max:
                chunks.append(secao)
            else:
                # divide com overlap para não perder contexto entre chunks
                chunks.extend(self._dividir_com_overlap(secao, tamanho_max, overlap=200))
        return chunks

    def _dividir_com_overlap(self, texto: str, tamanho: int, overlap: int) -> list[str]:
        chunks = []
        inicio = 0
        while inicio < len(texto):
            fim = min(inicio + tamanho, len(texto))
            chunks.append(texto[inicio:fim])
            inicio += tamanho - overlap
        return chunks
```

---

