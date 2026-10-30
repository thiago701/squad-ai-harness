# Testes Unitários — Detalhamento Completo

> **Quando ler:** ao escrever testes unitários (camada base da pirâmide). Pré-requisito: ter lido a SKILL.md (filosofia + 8 eixos preditivos).

> **Princípio:** unitário testa lógica pura, isolada, em milissegundos. Sem I/O, sem rede, sem banco. Mock apenas dependências de fronteira do domínio.

## CAMADA 1 — Testes Unitários

### Estrutura de projeto completa
```
projeto/
├── src/
│   └── dominio/
│       ├── pedido.py / Pedido.java
│       └── pedido_service.py / PedidoService.java
└── tests/ (Python) / src/test/ (Java)
    ├── unit/
    │   ├── domain/          ← entidades, value objects, regras puras
    │   └── application/     ← use cases com dependências mockadas
    ├── integration/
    │   ├── repository/      ← banco real via Testcontainers (coerência com DBML)
    │   ├── persistence/     ← testes de mapper Domain↔JPA (ida e volta)
    │   ├── migration/       ← Flyway migrations executam sem erro
    │   ├── messaging/       ← fila real via Testcontainers
    │   └── adapter/         ← adapters externos com WireMock
    ├── functional/
    │   ├── api/             ← testes de API com cliente HTTP real
    │   ├── bdd/             ← cenários Gherkin
    │   └── contract/        ← Pact consumer/provider
    ├── performance/
    │   ├── load/            ← scripts k6 / Locust
    │   └── baselines/       ← resultados de referência
    ├── builders/            ← builders centralizados
    └── conftest.py / TestConfig.java
```

### Python 3.12+ — Suíte unitária completa com os 8 eixos

```python
# tests/unit/application/test_confirmar_pedido.py
import pytest
from decimal import Decimal
from unittest.mock import Mock, call
from dominio.use_cases import ConfirmarPedidoUseCase
from dominio.entidades import StatusPedido
from dominio.excecoes import (
    PedidoNaoEncontradoException,
    ValorMinimoPedidoException,
    TransicaoEstadoInvalidaException,
)
from tests.builders import PedidoBuilder


class TestConfirmarPedido:
    """
    Contrato: pedido pendente com valor >= R$10,00 deve ser confirmado e cliente notificado.
    Invariante: notificador e salvar NUNCA chamados se qualquer validação falhar.
    """

    def setup_method(self):
        self.repo       = Mock()
        self.notificador = Mock()
        self.usecase    = ConfirmarPedidoUseCase(
            repositorio=self.repo, notificador=self.notificador
        )

    # ── HAPPY PATH ────────────────────────────────────────────────────────────

    def test_confirma_pedido_pendente_com_valor_valido(self):
        pedido = PedidoBuilder.pendente().com_valor(Decimal("150.00")).build()
        self.repo.buscar_por_id.return_value = pedido

        resultado = self.usecase.executar(pedido_id=pedido.id)

        assert resultado.status == StatusPedido.CONFIRMADO
        self.repo.salvar.assert_called_once_with(pedido)
        self.notificador.pedido_confirmado.assert_called_once_with(pedido)

    # ── BOUNDARY VALUES ───────────────────────────────────────────────────────

    def test_confirma_valor_exatamente_no_limite_minimo(self):
        pedido = PedidoBuilder.pendente().com_valor(Decimal("10.00")).build()
        self.repo.buscar_por_id.return_value = pedido

        resultado = self.usecase.executar(pedido_id=pedido.id)

        assert resultado.status == StatusPedido.CONFIRMADO

    def test_rejeita_valor_um_centavo_abaixo_do_minimo(self):
        pedido = PedidoBuilder.pendente().com_valor(Decimal("9.99")).build()
        self.repo.buscar_por_id.return_value = pedido

        with pytest.raises(ValorMinimoPedidoException) as exc:
            self.usecase.executar(pedido_id=pedido.id)

        assert "9.99" in str(exc.value)

    @pytest.mark.parametrize("valor_invalido", [
        Decimal("0.00"), Decimal("-0.01"), Decimal("-999.99")
    ])
    def test_rejeita_valores_zero_e_negativos(self, valor_invalido):
        pedido = PedidoBuilder.pendente().com_valor(valor_invalido).build()
        self.repo.buscar_por_id.return_value = pedido

        with pytest.raises(ValorMinimoPedidoException):
            self.usecase.executar(pedido_id=pedido.id)

    # ── INVALID INPUT ─────────────────────────────────────────────────────────

    def test_rejeita_pedido_id_nulo_sem_acessar_repositorio(self):
        with pytest.raises((ValueError, TypeError)):
            self.usecase.executar(pedido_id=None)
        self.repo.buscar_por_id.assert_not_called()

    def test_rejeita_pedido_id_negativo_sem_acessar_repositorio(self):
        with pytest.raises(ValueError):
            self.usecase.executar(pedido_id=-1)
        self.repo.buscar_por_id.assert_not_called()

    def test_lanca_excecao_descritiva_quando_pedido_nao_encontrado(self):
        self.repo.buscar_por_id.return_value = None

        with pytest.raises(PedidoNaoEncontradoException) as exc:
            self.usecase.executar(pedido_id=999)

        assert "999" in str(exc.value)

    # ── STATE TRANSITIONS ─────────────────────────────────────────────────────

    @pytest.mark.parametrize("status_invalido", [
        StatusPedido.CONFIRMADO,
        StatusPedido.CANCELADO,
        StatusPedido.ENVIADO,
        StatusPedido.DEVOLVIDO,
    ])
    def test_rejeita_transicao_de_qualquer_status_invalido(self, status_invalido):
        pedido = PedidoBuilder.com_status(status_invalido).build()
        self.repo.buscar_por_id.return_value = pedido

        with pytest.raises(TransicaoEstadoInvalidaException) as exc:
            self.usecase.executar(pedido_id=pedido.id)

        assert status_invalido.value in str(exc.value)

    # ── EXTERNAL FAILURE ──────────────────────────────────────────────────────

    def test_propaga_excecao_quando_repositorio_falha_na_busca(self):
        self.repo.buscar_por_id.side_effect = RuntimeError("DB connection lost")

        with pytest.raises(RuntimeError, match="DB connection lost"):
            self.usecase.executar(pedido_id=1)

    def test_atomicidade_nao_salva_quando_notificador_falha(self):
        pedido = PedidoBuilder.pendente().com_valor(Decimal("100.00")).build()
        self.repo.buscar_por_id.return_value = pedido
        self.notificador.pedido_confirmado.side_effect = RuntimeError("SMTP unavailable")

        with pytest.raises(RuntimeError):
            self.usecase.executar(pedido_id=pedido.id)

        self.repo.salvar.assert_not_called()  # atomicidade: não persiste sem notificação

    def test_repositorio_salvar_falha_nao_chama_notificador(self):
        pedido = PedidoBuilder.pendente().com_valor(Decimal("100.00")).build()
        self.repo.buscar_por_id.return_value = pedido
        self.repo.salvar.side_effect = RuntimeError("DB write failed")

        with pytest.raises(RuntimeError):
            self.usecase.executar(pedido_id=pedido.id)

        self.notificador.pedido_confirmado.assert_not_called()

    # ── INVARIANTES ───────────────────────────────────────────────────────────

    def test_invariante_notificador_nunca_chamado_quando_valor_invalido(self):
        pedido = PedidoBuilder.pendente().com_valor(Decimal("5.00")).build()
        self.repo.buscar_por_id.return_value = pedido

        with pytest.raises(ValorMinimoPedidoException):
            self.usecase.executar(pedido_id=pedido.id)

        self.notificador.pedido_confirmado.assert_not_called()

    def test_invariante_salvar_nunca_chamado_quando_estado_invalido(self):
        pedido = PedidoBuilder.com_status(StatusPedido.CANCELADO).build()
        self.repo.buscar_por_id.return_value = pedido

        with pytest.raises(TransicaoEstadoInvalidaException):
            self.usecase.executar(pedido_id=pedido.id)

        self.repo.salvar.assert_not_called()
```

### Property-Based Testing — Hypothesis para invariantes e fronteiras
```python
# tests/unit/domain/test_pedido_properties.py
from hypothesis import given, assume, settings, strategies as st
from decimal import Decimal

# Propriedade 1: invariante de negócio — desconto nunca resulta em valor negativo
@given(
    valor=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("9999.99"),
                      places=2, allow_nan=False, allow_infinity=False),
    percentual=st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
)
def test_desconto_nunca_resulta_em_valor_negativo(valor, percentual):
    pedido = PedidoBuilder.pendente().com_valor(valor).build()
    assert pedido.aplicar_desconto(percentual) >= Decimal("0.00")

# Propriedade 2: comutatividade — ordem dos itens não afeta o total
@given(st.lists(
    st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999.99"), places=2),
    min_size=1, max_size=20
))
def test_total_independe_da_ordem_dos_itens(precos):
    itens = [Item(produto_id=i, quantidade=1, preco=p) for i, p in enumerate(precos)]
    pedido_a = PedidoBuilder.pendente().com_itens(itens).build()
    pedido_b = PedidoBuilder.pendente().com_itens(list(reversed(itens))).build()
    assert pedido_a.total == pedido_b.total

# Propriedade 3: idempotência de serialização
@given(st.from_type(Pedido))
def test_serializacao_roundtrip_preserva_igualdade(pedido):
    assert Pedido.from_dict(pedido.to_dict()) == pedido

# Propriedade 4: validação nunca lança exceção inesperada
@given(st.text(max_size=50))
def test_validacao_cpf_nunca_lanca_excecao_inesperada(cpf_qualquer):
    try:
        validar_cpf(cpf_qualquer)
    except CpfInvalidoException:
        pass  # única exceção esperada
    except Exception as e:
        pytest.fail(f"Exceção inesperada '{type(e).__name__}' para CPF='{cpf_qualquer}'")
```

### Builder centralizado — Python
```python
# tests/builders/pedido_builder.py
from dataclasses import dataclass, field
from decimal import Decimal
from dominio.entidades import Pedido, Cliente, StatusPedido, Item

class PedidoBuilder:
    def __init__(self):
        self._id      = 1
        self._valor   = Decimal("100.00")
        self._status  = StatusPedido.PENDENTE
        self._cliente = ClienteBuilder.padrao().build()
        self._itens   = [Item(produto_id=1, quantidade=1, preco=Decimal("100.00"))]

    def com_valor(self, v: Decimal)         -> "PedidoBuilder": self._valor  = v;      return self
    def com_status(self, s: StatusPedido)   -> "PedidoBuilder": self._status = s;      return self
    def com_id(self, i: int)                -> "PedidoBuilder": self._id     = i;      return self
    def com_itens(self, itens: list[Item])  -> "PedidoBuilder": self._itens  = itens;  return self
    def sem_itens(self)                     -> "PedidoBuilder": self._itens  = [];     return self

    def build(self) -> Pedido:
        return Pedido(id=self._id, valor=self._valor,
                      status=self._status, cliente=self._cliente, itens=self._itens)

    @classmethod def pendente(cls)                      -> "PedidoBuilder": return cls()
    @classmethod def confirmado(cls)                    -> "PedidoBuilder": return cls().com_status(StatusPedido.CONFIRMADO)
    @classmethod def cancelado(cls)                     -> "PedidoBuilder": return cls().com_status(StatusPedido.CANCELADO)
    @classmethod def com_status(cls, s: StatusPedido)   -> "PedidoBuilder": return cls().com_status(s)
```

### Mutation Testing — Python
```bash
pip install mutmut

# Executar apenas no domínio crítico
mutmut run --paths-to-mutate src/dominio/ --tests-dir tests/unit/

# Diagnosticar sobreviventes
mutmut results          # lista todos os mutantes
mutmut show <id>        # ver o mutante exato que sobreviveu

# Mutantes sobreviventes mais reveladores:
# if valor >= MINIMO  →  if valor > MINIMO      → falta teste de boundary exato
# return CONFIRMADO   →  return None             → falta assert no retorno
# notificador.enviar()→  [linha removida]        → falta verify da chamada
# raise ValueError    →  [linha removido]        → falta teste do caminho de erro
```

### Classificação de Mutantes — Aceitáveis vs Necessários

Nem todo mutante sobrevivente é sinal de teste fraco. Alguns são **aceitáveis por regra de negócio**, outros são **gaps verdadeiros**. A classificação sistematiza a decisão.

**Tabela de Classificação de Mutantes** (adaptada do GLOSSARIO §8):

| Tipo de Mutação | Sobrevivente é aceitável? | Quando Aceitar | Ação |
|---|---|---|---|
| **Boundary** (`>` → `>=`) | Às vezes | Se o valor exato nunca ocorre em produção (regra conhecida) | Documentar: `// PIT: >100 nunca ocorre` |
| **Null check removido** | Nunca | — | Criar teste com entrada null |
| **Return value mutation** | Nunca | — | Adicionar assertion no teste |
| **Conditional negation** | Nunca | — | Adicionar teste do caminho ausente |
| **Math operator** (`+` → `-`) | Nunca | — | Adicionar teste com valores diferenciados |
| **Void method call removed** | Nunca | — | Usar `Mockito.verify()` para side effect |

**Exemplos Práticos:**

```java
// EXEMPLO 1: Boundary mutante ACEITÁVEL
// Código: if (preco > PRECO_MINIMO) // PRECO_MINIMO = 10
public boolean podeComprar(BigDecimal preco) {
    return preco.compareTo(PRECO_MINIMO) > 0;
}

// Mutante: if (preco >= PRECO_MINIMO)
// Teste: preco = 10.01 passa
// Análise: ACEITÁVEL porque regra de negócio é "preço > 10", nunca "= 10"
// Documentação:
// Teste falta: teste com exatamente 10.00 não seria possível de forma realista
// PIT: boundary >= é aceitável, valor == MINIMO nunca ocorre em produção

@Test
void devePermitirPrecoAcimaDoMinimo() {
    assertThat(podeComprar(BigDecimal("10.01"))).isTrue();
    assertThat(podeComprar(BigDecimal("10.00"))).isFalse();  // Boundary exato
}
```

```java
// EXEMPLO 2: Return value mutante NECESSÁRIO (teste faltando)
// Código: 
public String calcularStatusPedido(Pedido pedido) {
    if (pedido.itens().isEmpty()) {
        return "VAZIO";
    }
    return "COMPLETO";
}

// Mutante: return null  (em vez de "VAZIO")
// Se mutante sobrevive: teste não valida o return "VAZIO"

// FIX:
@Test
void deveRetornarVazioQuandoSemItens() {
    var pedido = PedidoBuilder.pendente().sem_itens().build();
    
    String status = service.calcularStatusPedido(pedido);
    
    assertThat(status).isEqualTo("VAZIO");  // ← assertion era faltando
}
```

```java
// EXEMPLO 3: Void method call mutante NECESSÁRIO (verify faltando)
// Código:
public void confirmarPedido(Pedido pedido) {
    pedido.confirmar();
    notificador.enviar(pedido);  // void call
}

// Mutante: remover a linha notificador.enviar()
// Se mutante sobrevive: teste não verifica o side effect

// FIX:
@Test
void deveNotificarAoConfirmar() {
    var pedido = PedidoBuilder.pendente().build();
    
    service.confirmarPedido(pedido);
    
    verify(notificador, times(1)).enviar(pedido);  // ← verify era faltando
}
```

**Workflow: Diagnosticar e Classificar Mutantes**

```bash
# 1. Rodar PIT/mutmut
mvn org.pitest:pitest-maven:mutationCoverage

# 2. Ver relatório
open target/pit-reports/index.html

# 3. Para cada sobrevivente, classificar:
#    Aceitável → documentar no código
#    Necessário → criar teste
```

**Threshold por Categoria (recomendado):**

```yaml
# pitest config em pom.xml
<mutationThreshold>80</mutationThreshold>  # Global
# Por pacote:
# - null checks: 100% obrigatório
# - boundaries: >= 90%
# - math operators: 100%
# - void methods: 100%
```

**Checklist Mutante Scanning:**
- ✅ Rodar PIT/mutmut em CI/CD (domínio crítico >= 80%)
- ✅ Criar issue para cada mutante sobrevivente
- ✅ Classificar usando tabela acima
- ✅ Documentar mutantes aceitáveis no código (`// PIT:...`)
- ✅ Adicionar testes para mutantes necessários
- ✅ Threshold mínimo: 60% em geral, 80% em domínio

---
