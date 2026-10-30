# Vetor: Functional — testes E2E e cobertura (integra o pytest existente)

Prova **executavel** de que a wave funciona: roda os testes e checa cobertura minima.
Integra o `pytest` que ja e o gate do ecossistema (177 testes hoje) e os gates SPARC
G4.x de `squad-ai/fase-gates.yaml`.

## 1. Gate de funcionalidade (sempre)
```
python -m pytest -q                 # tudo verde = pre-condicao do GREEN
```
Qualquer teste vermelho → wave NOT-GREEN (sub_task `owner=fix`). Regressao em teste que
passava antes da wave e **bloqueante**.

## 2. Cobertura minima por tipo de skill/projeto

| Tipo | Baseline (gate) | Ideal | Como medir |
|---|---|---|---|
| Skill/doc sem codigo executavel | N/A | N/A | nao se aplica |
| Script utilitario (Python) | **30%** | 80% | `pytest --cov` |
| Dominio de negocio (Java) | **80%** | 90% | JaCoCo (G4.2) |
| Codigo de seguranca/dinheiro | 90% | 100% do caminho critico | JaCoCo + mutation (PIT) |

> Cobertura de linha != qualidade: complemente com **mutation testing** (PIT/`mutmut`)
> onde o caminho e critico — detecta teste que executa sem assertar (licao do Ciclo 5).

## 3. Smoke test rapido (< 30s) vs full suite
- **Smoke** (no loop, por sub_task): subconjunto que cobre o caminho feliz + 1 borda.
  `pytest -q tests/test_<area>.py -k "smoke or core"`. Feedback rapido durante o build.
- **Full** (no GATE 2, antes do commit): suite inteira + cobertura. So o full decide GREEN.

## 4. Escrever testes funcionais E2E
- **Java**: Testcontainers (Postgres/Localstack reais), `@SpringBootTest`, RestAssured para
  contrato HTTP. Integracao real > mock onde o risco e de integracao (G4.x).
- **Python**: mocks controlados e determinismo; **fetcher/IO injetavel** (como o `ArxivSource`
  do harvest-cognition, testado offline). Sem rede no teste: injete a fronteira.
- Teste **comportamento, nao implementacao**; um vermelho por vez (delega a `especialista-qualidade`).

## Saida (formato)
```
FUNCTIONAL @ W<n>
pytest:     177 passed (0 failed)            ✅
cobertura:  dominio 84% (gate 80%)           ✅   · util 22% (gate 30%) ❌
smoke:      4/4 caminho-critico               ✅
veredito:   NOT-GREEN (cobertura util < 30%)
```

## Severidade
- teste vermelho / regressao → 🔴 bloqueante.
- cobertura abaixo do baseline → 🔴 bloqueante (gate countable).
- cobertura entre baseline e ideal → 🟡 (divida priorizada).
