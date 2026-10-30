# Lições de campo — A.I. PHOTOBOOTH, Fase 0 (ago/2026)

> Referência da skill `ai-evaluation`. Três lições que só apareceram ao medir de verdade.

## 1. Métrica errada é pior que código errado

**O defeito.** O teste de resistência contava sucesso pelo status do **job**, não da
**sessão**. Como o grafo roda até o fim mesmo quando a validação reprova a foto, o job
termina `COMPLETED` — então o script reportaria **"100% de sucesso" com todas as fotos
rejeitadas**.

**Por que é o pior tipo de defeito.** Código errado quebra e alguém investiga. Métrica
errada não quebra nada: produz um relatório confiante e falso, que vira decisão de negócio.

**A correção.** Separar três coisas que somadas viram mentira:

| | O que significa |
|---|---|
| **Entregue** | O sistema fez o trabalho |
| **Rejeitada na entrada** | O sistema **funcionando** — rejeitar foto ruim é a feature |
| **Erro** | O sistema **quebrando** |

Medição real depois da correção: 65,6% entregues · 34,4% rejeitadas · **0,0% de erro**.
O primeiro número parece ruim e não é; o terceiro é o que importa. Somá-los teria dado
"65,6% de sucesso" — um número que não responde pergunta nenhuma.

**A regra geral.** Antes de agregar dois contadores, pergunte se eles significam a mesma
coisa para quem vai decidir. Sucesso técnico ≠ sucesso do produto ≠ ausência de falha.

## 2. Só compare braços que fazem o mesmo trabalho

A primeira comparação pareada rodou filtro determinístico × troca de fundo e devolveu
"🔴 regressão crítica de latência: +1.104 ms". **Aritmeticamente correto, decisoriamente
sem sentido** — os dois não são alternativas para o mesmo tema.

O `compare.py` não tem como saber se dois provedores são substitutos, então o relatório
carrega o aviso por padrão. Use a comparação pareada para escolher entre **candidatos ao
mesmo papel**; para escolher entre **técnicas**, a régua é a nota humana por tema.

## 3. Conjunto sintético valida a mecânica, nunca o limiar

O eval-set v1 usa rostos sintéticos. Ele exercita detecção, alinhamento, embedding, cosseno,
agregação e comparação pareada — tudo funciona. Mas as faces são a mesma ilustração com
parâmetros diferentes, então **"outra pessoa" mede 0,92 de similaridade**, contra ~1,00 da
mesma pessoa. Separação de 0,08 onde um conjunto real daria ordens de grandeza.

**Consequência:** nenhum número de identidade daquele conjunto sustenta decisão. Isso foi
codificado num teste que **falha se alguém melhorar as fixtures sem revisar o texto do
relatório**:

```python
def test_fixtures_sinteticas_nao_calibram_o_limiar_de_identidade(...):
    separacao = mesma - outra
    assert separacao < 0.30, (
        "Se ficou grande, as fixtures melhoraram — reveja esta limitacao e o relatorio."
    )
```

**A regra geral.** Quando uma suíte verde pode ser lida como uma garantia que ela não dá,
**escreva um teste cuja função é impedir essa leitura**. É a forma executável de um
disclaimer — e a única que não apodrece.

## 4. Limiar não calibrado precisa aparecer no dado, não no rodapé

Todo limiar do projeto carrega um campo `origem` (`nao-calibrado` | `eval-set@vN`) que entra
em **cada linha de telemetria**. Não é decoração: decisão automática tomada por um limiar que
ninguém validou é risco, e enterrar isso num parágrafo de rodapé garante que alguém vai
esquecer. No dado, não dá para esquecer.
