# Lições de campo — A.I. PHOTOBOOTH, Fase 0 (ago/2026)

> Referência da skill `integracao-hardware-periferico`. **Escrita a partir de defeitos
> reais encontrados por teste**, não de teoria. Cada um passaria numa demonstração e
> apareceria num evento.

## 1. `QUEUED` não é "já tratado" — a armadilha da idempotência larga demais

**O defeito.** A guarda de idempotência tratava qualquer estado ativo como "já cuidamos
disso":

```python
ATIVOS = {QUEUED, SPOOLING, PRINTING, DONE}
if existente and status in ATIVOS:
    return existente["job_id"]        # ← e nunca imprime
```

Com a impressora offline, o job entrava em `QUEUED`. Quando ela voltava, qualquer reenvio
batia nessa guarda e devolvia o `job_id` **sem imprimir**. O job morria na fila em silêncio.

**A correção.** Separar "entregue ao spooler" de "ainda na fila":

```python
JA_TRATADOS = {SPOOLING, PRINTING, DONE}     # idempotência vale só para estes
ATIVOS = JA_TRATADOS | {QUEUED}
```

…e adicionar um `drenar()` acionado pelo health check, que reenvia o que ficou parado
quando a impressora volta.

**A regra geral.** Idempotência protege contra *repetir trabalho feito*. Um item que ainda
não foi feito não é protegido por ela — é abandonado por ela. Sempre que escrever uma guarda
de idempotência, pergunte: **este estado significa "já aconteceu" ou "ainda vai acontecer"?**

## 2. Sumir da fila é ambíguo — imprimiu ou morreu?

**O defeito.** `Get-PrintJob` do Windows remove o job da fila quando ele **termina** e
quando ele **falha**. Tratar "sumiu" como sucesso perde fotos em silêncio; o operador só
descobre pela reclamação.

**A correção.** Usar o **tempo de ciclo** do equipamento como árbitro:

```python
if desde is None or (time.monotonic() - desde) >= self._ciclo:
    return DONE
return FAILED     # sumiu rápido demais para ter impresso
```

Na Fujifilm ASK-300 o ciclo de 10×15 cm é **12,3 a 26,4 s** — número da especificação do
fabricante, não estimativa. Um job que some em 1 s não imprimiu.

**A regra geral.** Quando a API do periférico é ambígua, **procure um invariante físico**
para desempatar: tempo de ciclo, consumo de mídia, contador de páginas. O relógio sabe
coisas que a API não conta.

## 3. Faça o adapter testável sem o sistema operacional alvo

O adapter do spooler roda no Windows, mas o time desenvolve e o CI roda em Linux. Sem um
`ShellRunner` injetável, esse código só seria exercitado **no dia do evento** — que é
exatamente quando não se quer descobrir um bug de integração.

```python
class ShellRunner(Protocol):
    def rodar(self, comando: str, *, timeout_s: float = 20.0) -> tuple[int, str, str]: ...
```

Uma classe de 20 linhas fala com o SO. Todo o resto — tradução de estado, idempotência,
tempo de ciclo, drenagem — é testado com um runner de mentira que devolve exatamente o que
o PowerShell devolveria. **11 testes, zero Windows.**

## 4. O que o teste virtual continua não provando

Reconfirmado na prática, e precisa estar em todo relatório: cor real, corte e sangria
físicos, tempo de ciclo real, fim de ribbon, atolamento e comportamento do driver sob horas
de carga. **Reserve um dia de bancada com o equipamento antes do primeiro evento pago.**

Some a isso o risco de driver: o suporte oficial de impressoras fotográficas costuma parar
em versões antigas do Windows. Valide **na máquina do totem, cedo** — não na véspera.
