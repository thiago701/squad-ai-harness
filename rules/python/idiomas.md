# Rule — Idiomas always-on de Python 3.13 + FastAPI

> **Natureza:** regra **always-on**, curta e categórica. Aqui ficam só os
> **invariantes** (o que é *sempre* preferível). O **como** profundo vive nas
> skills — não duplicar aqui.
> **Aplica-se a:** todo código Python (`*.py`) do ecossistema, com foco no
> backend FastAPI da stack de referência.
> **Arbitragem:** **P1-Simplicidade > P2-Performance > P3-CustoBaixo**.
> Na dúvida entre duas formas, escolha a mais simples e legível.

---

## 1. Tipagem e modelagem (sempre)

- **Type hints completos** em toda assinatura pública (args + retorno). Código
  sem tipos não passa no gate. `from __future__ import annotations` quando ajudar.
- **`match/case`** quando clareia ramificação sobre forma/tipo de dado — não para
  substituir um `if` simples de duas pernas.
- **`dataclasses`** para dados internos sem validação de borda; **`Protocol`**
  (typing) para contratos estruturais — preferir a ABCs/herança (composição > herança).
- **`enum.Enum`/`StrEnum`** em vez de constantes string soltas.
- **Imutabilidade por padrão:** `frozen=True` em dataclass de valor; `tuple`/
  `frozenset` quando a coleção não muda.

## 2. Assíncrono (sempre que houver I/O)

- **`async`/`await`** para I/O (rede, DB, arquivo). Endpoints FastAPI de I/O são
  `async def`.
- **Nunca bloquear o event loop:** chamada bloqueante (CPU pesada, lib síncrona)
  vai para `anyio.to_thread.run_sync` / `run_in_executor`. Sem `time.sleep` em
  corrotina (use `await asyncio.sleep`).
- **`asyncio.TaskGroup`** (3.11+) para fan-out concorrente com cancelamento
  estruturado — preferir a `gather` solto.

## 3. Validação e bordas (FastAPI)

- **Pydantic v2** é a fronteira de validação: request/response models tipados.
  Nada de `dict` cru atravessando a borda. Validação acontece **na entrada**.
- **`Annotated[...]` + `Depends`** para injeção; `response_model` explícito em
  toda rota; status codes corretos.
- Domínio **não** importa FastAPI: regra de negócio é agnóstica de framework
  (Clean Architecture — ver skill).

## 4. Armadilhas (nunca)

- **Nunca** usar **default mutável** em assinatura (`def f(x=[])`); use `None` +
  inicialização interna, ou `field(default_factory=...)`.
- **Nunca** manipular caminhos com `os.path`/strings: **`pathlib.Path`** sempre.
- **Nunca** capturar `except:` nu nem engolir exceção sem log/contexto.
- **Nunca** usar `print` para diagnóstico de produção: `logging` estruturado.

## 5. Ferramentas (sempre no projeto)

- **`ruff`** = linter **e** formatter (substitui flake8/isort/black). Lint limpo
  é pré-condição de gate.
- **`pytest`** + cobertura; TDD é o método (teste precede/acompanha o código).
  Cenários de borda e property-based quando o valor justifica.
- **`uv`** para ambiente/dependências; versões pinadas.
- Tipos checados (mypy/pyright) no CI quando o módulo é crítico.

---

## Skills (conteúdo profundo — consultar sob demanda)

- **engenheiro-clean-architect** — SOLID, camadas, Protocols, isolar domínio.
- **arquiteto-performance** — asyncio sob carga, profiling, GC, p95/p99.
- **python-memoria** — RAM: iterar vs materializar, caches com limite, dados tipados em pedaços, orçamento em teste — ver [`memoria.md`](memoria.md).
- **especialista-qualidade** — pytest, BDD, cobertura, mutation, E2E.
- **clean-code-craftsman** — naming, tamanho de função, smells.
- **engenheiro-seguranca** — ver [`seguranca.md`](seguranca.md).
