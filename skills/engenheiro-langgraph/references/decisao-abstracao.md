# Decisão de abstração — SDK direto × função × LangChain × LangGraph × fila

> Referência da skill `engenheiro-langgraph`. Objetivo: impedir que LangChain/LangGraph entrem
> num projeto por moda. Cada nível abaixo tem um custo real; só suba de nível quando o nível
> atual doer de verdade.

## 1. A escada de complexidade

```text
Nível 0  SDK direto            custo: ~0        ganho: nenhum além da chamada
Nível 1  função async própria  custo: ~0        ganho: composição, teste, timeout
Nível 2  Protocol + adapters   custo: ~40 LOC   ganho: troca de provedor por config
Nível 3  LangChain (peças)     custo: deps      ganho: structured output, parsers, retries prontos
Nível 4  LangGraph             custo: conceito  ganho: State, checkpoint, resume, ramificação
Nível 5  fila + worker         ortogonal        ganho: HTTP não segura inferência longa
```

**Só suba de nível com dor comprovada.** Escreva a dor no ADR: "subimos ao nível 4 porque o
processo precisa retomar após reboot no meio do evento — o nível 1 perderia a inferência já paga".

## 2. Lado a lado

### Nível 0 — SDK direto (o padrão)

```python
from google import genai
client = genai.Client()          # criado UMA vez, no lifespan

async def transformar(img_bytes: bytes, prompt: str) -> bytes:
    r = await client.aio.models.generate_content(
        model="gemini-flash-image", contents=[prompt, img_part(img_bytes)]
    )
    return first_image(r)
```

Sete linhas. Sem dependência extra. Stack trace aponta para a linha certa.
**Se o requisito é "aplique o efeito nesta foto", pare aqui.**

### Nível 2 — Protocol próprio (troca de provedor)

```python
from typing import Protocol

class ImageTransformProvider(Protocol):
    name: str
    async def transform(self, image_ref: str, prompt: str, *, timeout_s: float) -> "Result": ...

class GeminiProvider:  ...
class FalProvider:     ...
class LocalGPUProvider:...
class MockProvider:    ...        # indispensável para teste e para demo sem internet
```

Isto **não** exige LangChain. São 40 linhas e você controla a semântica de erro, de custo e de
timeout — que é exatamente o que a abstração de terceiro esconde de você.

### Nível 4 — LangGraph (quando ele se paga)

Migre quando a função do nível 1 tiver adquirido **três ou mais** destes sintomas:

- [ ] Mais de 5 `if state.status ==` para decidir o próximo passo.
- [ ] `try/except` aninhado em 3 níveis para retry por etapa distinta.
- [ ] Necessidade de retomar do meio após crash (evento real, sessão paga).
- [ ] Necessidade de pausar e esperar decisão humana.
- [ ] Duas ou mais etapas rodando em paralelo com merge de resultado.
- [ ] Você não consegue mais dizer, olhando o código, em que etapa uma sessão travou.

Menos de três sintomas = a função ainda é a resposta certa.

## 3. Quando LangChain (sem Graph) vale sozinho

Casos legítimos e estreitos:

- `with_structured_output(PydanticModel)` quando você quer o *retry de parse* pronto.
- Loaders/splitters de documento num RAG (não é o caso de um photobooth).
- Padronizar mensagens entre provedores heterogêneos num único código.

Casos ilegítimos (recusar):

- "Usar LangChain porque é o padrão do mercado."
- Envolver uma chamada única para "ficar preparado para o futuro" — YAGNI custa deps hoje.
- Usar `Chain` onde uma função async faz o mesmo com menos indireção.

## 4. Fila + worker é ortogonal — e quase sempre necessário

Inferência de imagem leva 5–30 s. Um `POST /gerar` que segura a conexão por 30 s:

- estoura timeout de proxy/navegador;
- perde o trabalho se o cliente fechar a aba;
- impede medir fila separada de inferência.

Padrão correto, independente de LangGraph:

```text
POST /sessions/{id}/generate  → enfileira PhotoJob, devolve 202 + job_id
GET  /jobs/{id}               → QUEUED | PROCESSING | COMPLETED | FAILED
                                 (ou SSE/WebSocket para push)
worker                        → consome a fila e executa o grafo
```

O grafo roda **dentro** do worker. Trocar a fila (in-memory → SQLite → Redis) não toca o grafo.

## 5. Checklist de ADR

Toda adoção de nível ≥ 3 precisa responder por escrito:

1. Qual dor concreta do nível anterior motivou a subida?
2. Que alternativa mais simples foi descartada, e por quê?
3. Qual o custo assumido (deps, cold start, curva de aprendizado, lock-in)?
4. Qual o critério objetivo para **reverter** (voltar ao nível anterior)?
5. Que métrica prova o ganho? (latência, taxa de recuperação, LOC, tempo de diagnóstico)

Sem resposta para as 5, a adoção é reprovada pelo `arquiteto-minimalista`.
