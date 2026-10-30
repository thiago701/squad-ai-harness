# Camera HAL — contratos, preview × captura e falhas reais

> Referência da skill `integracao-hardware-periferico`.

## 1. Preview e captura são operações distintas

| | Preview | Captura |
|---|---|---|
| Frequência | contínua (15–30 fps) | evento único |
| Resolução | baixa (640×480 basta) | máxima útil |
| Latência aceitável | < 60 ms/frame | 0,2–2 s |
| Consumidor | UI, detecção de rosto para enquadrar | pipeline de geração |
| Falha aceitável | pular frame | **nunca** — precisa de retry e feedback |

Modelar as duas como a mesma chamada gera preview travado ou captura de baixa qualidade. Em DSLR
a diferença é ainda mais forte: preview vem do live view, captura dispara o obturador.

## 2. Contagem regressiva e o momento do disparo

O usuário precisa saber **exatamente** quando a foto sai.

```text
toque → 3 → 2 → 1 → flash visual (tela branca) → captura → congela o preview 1,5 s
```

- O congelamento pós-captura confirma o que foi registrado. Sem ele, o usuário não sabe se deu certo.
- Se a captura demorar mais de ~300 ms, dispare **durante** o "1", não depois — a percepção de
  atraso vem do descompasso entre a contagem e o clique.
- Ofereça "repetir" antes de gastar inferência. Uma retomada custa 0; uma geração descartada custa
  10 s e dinheiro.

## 3. Falhas reais e tratamento

| Falha | Sintoma | Tratamento no adapter |
|---|---|---|
| Dispositivo ocupado | `open()` falha | Detectar no boot; mensagem ao operador, não ao público |
| Desconexão USB no preview | Frames param ou repetem | Detectar frame idêntico N vezes → marcar OFFLINE e reconectar |
| Frame congelado | Buffer devolve o mesmo conteúdo | Comparar hash dos últimos 3 frames |
| Autofoco não converge | Fotos borradas em sequência | Timeout de foco; capturar mesmo assim e deixar a validação decidir |
| Resolução negociada diferente | Imagem menor que a pedida | Validar o que voltou; nunca assumir |
| Suspensão do SO | Câmera some | Desabilitar suspensão no totem + reabrir no health check |
| Luz do ambiente muda | Exposição oscila | Travar exposição/balanço após o enquadramento, se o driver permitir |

## 4. MockCamera — a implementação mais importante

```python
class MockCamera:
    """Fotos de um diretório de fixtures. Roda em CI, em dev e na demo sem hardware."""
    name = "mock"

    def __init__(self, fixtures_dir: Path, *, atraso_s: float = 0.4,
                 falhar_a_cada: int | None = None):
        self._fotos = sorted(fixtures_dir.glob("*.jpg"))
        self._i = 0
        self._atraso = atraso_s
        self._falhar_a_cada = falhar_a_cada     # injeção de falha determinística

    async def capture(self, *, timeout_s: float) -> Frame:
        self._i += 1
        if self._falhar_a_cada and self._i % self._falhar_a_cada == 0:
            raise CameraTimeout("mock: falha programada")
        await asyncio.sleep(self._atraso)       # simula latência real
        return Frame(ref=str(self._fotos[self._i % len(self._fotos)]), ...)
```

Três detalhes que fazem o mock valer: **latência simulada** (senão o frontend é escrito assumindo
captura instantânea), **falha programada** (senão o caminho de erro nunca é exercitado) e
**fixtures diversas** (tom de pele, luz, óculos, sem rosto).

## 5. Caminho de evolução para DSLR

Mantenha o SDK do fabricante inteiramente dentro do adapter, com um processo separado se o SDK for
instável — assim um crash do SDK não derruba a aplicação.

```text
Aplicação ──▶ CameraProvider ──▶ DslrAdapter ──(IPC)──▶ processo do SDK ──▶ câmera
```

Checklist antes de adotar DSLR na V1: alimentação contínua (bateria não aguenta evento), cabo USB
com trava, tethering estável por horas, tempo de ciclo entre disparos, aquecimento do sensor,
e o que acontece quando o cartão de memória enche.
