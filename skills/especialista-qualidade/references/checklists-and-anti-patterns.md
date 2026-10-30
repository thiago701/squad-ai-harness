# Anti-padrões, Checklists e Métricas Globais

> **Quando ler:** durante revisão de uma suíte de testes existente, ou para sustentação contínua da qualidade.

## Testes de Caracterização — Rede de Segurança para Código Legado

```
PROTOCOLO OBRIGATÓRIO antes de refatorar código legado sem testes:
  Passo 1: Execute o código legado com entradas reais — capture saídas
  Passo 2: Escreva testes que PASSAM com o código atual (caracterização)
  Passo 3: Confirme que a suíte é 100% verde ANTES de qualquer mudança
  Passo 4: Refatore em passos mínimos (1 mudança por vez)
  Passo 5: Qualquer teste vermelho = rollback imediato, analise a diferença
  Passo 6: Após refatoração completa, substitua por testes de especificação corretos
```

```python
@pytest.mark.legado  # identificação clara — não é especificação, é caracterização
class TestCaracterizacaoCalculadorLegado:
    """
    Documenta o comportamento ATUAL do código legado.
    Âncora de segurança para refatoração — não representa o comportamento CORRETO.
    """
    def test_desconto_vip_comportamento_atual(self):
        resultado = calculador_legado.calcular(tipo="VIP", valor=Decimal("100.00"))
        assert resultado == Decimal("80.00")
        # NOTA: após refatoração, substituir por: test_desconto_vip_aplica_20_porcento

    def test_tipo_nulo_comportamento_atual(self):
        resultado = calculador_legado.calcular(tipo=None, valor=Decimal("100.00"))
        assert resultado == Decimal("100.00")
        # NOTA: após refatoração, este caso deve lançar ValueError
```

---

## Checklist de Qualidade por Camada

```
UNITÁRIOS:
□ Protocolo dos 8 eixos aplicado e documentado?
□ Builders centralizados — zero new Entidade() inline nos testes?
□ Testa comportamento observável, não implementação interna?
□ Invariantes explicitamente verificadas (assert_not_called, etc.)?
□ Mutation score > 80% no domínio crítico?
□ Falha de teste explica claramente o que quebrou e com qual valor?

INTEGRAÇÃO:
□ Testcontainers — zero H2, zero mocks de repositório?
□ Isolamento por teste — rollback ou truncate entre cada teste?
□ Testa rollback em caso de exceção?
□ Testa cenário de concorrência para recursos compartilhados?
□ Serviços externos mockados com WireMock (timeout, erro, retry)?

FUNCIONAIS:
□ Cobre todos os status HTTP esperados (200, 400, 401, 403, 404, 409, 503)?
□ Valida schema completo da resposta, não apenas status code?
□ Testa idempotência nas operações que devem ser idempotentes?
□ Cenários BDD escritos na linguagem do negócio, não da implementação?
□ Contract tests definidos para todas as integrações externas?

PERFORMANCE:
□ SLA definido como código no script (thresholds)?
□ Baseline registrado antes de qualquer mudança de performance?
□ Todos os 4 tipos executados: load, stress, spike, soak?
□ Testes de performance no pipeline de CI com gate de qualidade?
□ Comparação automática com baseline anterior para detectar regressão?
```

---

## Métricas de Qualidade por Camada

| Métrica | Aceitável | Saudável | Ferramenta |
|---|---|---|---|
| Cobertura de linhas | > 75% | > 90% | pytest-cov / JaCoCo |
| Cobertura de branches | > 65% | > 85% | pytest-cov / JaCoCo |
| **Mutation score** | > 65% | > 80% | mutmut / PIT |
| Tempo suite unitária | < 60s | < 15s | CI pipeline |
| Tempo suite integração | < 5min | < 2min | CI pipeline |
| Tempo suite funcional | < 10min | < 5min | CI pipeline |
| Testes flaky | < 1% | 0% | histórico CI |
| p95 endpoint crítico | < 300ms | < 150ms | k6 / Gatling |
| Error rate sob carga | < 1% | < 0.1% | k6 / Locust |
| Regressão de performance | < 10% | < 5% | comparação de baseline |

---

## Anti-padrões para Nomear Explicitamente

- **"Happy path only"**: apenas caminho feliz — os bugs vivem nos limites e falhas.
- **"Cobertura cosmética"**: 90% de cobertura com mutation score de 30%.
- **"Teste frágil"**: verifica sequência de chamadas internas, explode em refatoração.
- **"Mock de infraestrutura em integração"**: usar H2 ou mock de repositório em testes de integração — não detecta problemas reais de banco.
- **"Performance como afterthought"**: testes de carga apenas antes do go-live — tarde demais.
- **"SLA sem baseline"**: medir performance sem referência — impossível detectar regressão.
- **"Teste de performance manual"**: scripts executados manualmente fora do CI — não previnem regressão.
- **"BDD como documentação morta"**: cenários Gherkin que não são executados automaticamente.
- **"Contract testing ignorado"**: integrar com serviços externos sem contrato — quebra silenciosa em produção.
- **"Regression amnesia"**: bug corrigido sem teste de regressão — volta em 3 meses garantido.
- **"Refatoração sem rede"**: código legado refatorado sem testes de caracterização.

---

## Linguagem e Tom

- Ao receber código: execute o **Protocolo dos 8 Eixos** e apresente o mapa de cenários por camada antes de qualquer teste.
- Ao receber requisito de performance: exija SLA em percentil (p95/p99), não média. Proponha o script de baseline antes do load test.
- Nomeie o eixo e a camada de cada cenário: *"Este é um teste de EXTERNAL FAILURE na camada de integração — WireMock simulando timeout."*
- Quando a suíte for fraca: rode mentalmente o mutation testing, aponte os mutantes que sobreviveriam.
- Finalize toda suíte com o checklist de qualidade por camada.
- Termine com: *"Qual camada e quais cenários são mais críticos para o negócio — começamos por lá?"*
