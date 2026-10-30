# Referência — Right-sizing e custo de Lambda (memória, CPU, Power Tuning, ESM)

> Parte da skill `lambda-java-cold-start`. Carregue quando a pergunta for **quanta memória dar à função**, como medir custo por invocação, como calibrar event source mappings (SQS, Kinesis, DynamoDB Streams, Kafka) ou quando usar response streaming. A escolha de estratégia de cold start (SnapStart, Native, CRaC, PC) está no `SKILL.md`.

Procedência e licença: ver `docs/ATTRIBUTIONS.md` (colheita de 13/10/2026). Texto reescrito; limites e preços mudam — confira na documentação oficial da AWS antes de fixar números.

## 1. Memória e CPU andam juntas

Na Lambda a CPU é proporcional à memória configurada: não existe botão de vCPU separado. Perto de 1.769 MB a função recebe o equivalente a uma vCPU inteira; abaixo disso, ela divide uma vCPU. Consequência prática para Java:

- JIT, GC e inicialização do Spring são CPU-bound. Uma função com 512 MB pode rodar bem mais devagar que com 1.769 MB e sair **mais cara**, porque o preço é duração × memória.
- Mais memória só compensa até o ponto em que a duração para de cair. O alvo é o mínimo de **custo por invocação** que ainda cumpra o SLA de latência, não o mínimo de memória.
- Faixas de partida (ponto de partida para medir, nunca resposta final): 512 MB para handler HTTP comum; 1.024 MB para processamento pesado; ≥ 1.769 MB quando CPU-bound ou JVM sem otimização de partida.

## 2. Medir antes de mexer: Power Tuning

O AWS Lambda Power Tuning (projeto open source) é uma máquina de estados do Step Functions que invoca a função em vários tamanhos de memória e devolve a curva custo × duração.

Como usar bem:

1. Rode **depois** de resolver o cold start: ele mede invocações aquecidas; não é teste de partida a frio.
2. Inclua o tamanho da fronteira de 1 vCPU (≈ 1.769 MB) na lista de valores, além de uma faixa abaixo e outra acima.
3. Use payload representativo e 50–100 execuções por tamanho; com poucas, o ruído de GC e de JIT domina.
4. Em função com SnapStart, meça a versão publicada, não `$LATEST` (o snapshot muda o perfil de duração).
5. Repita a cada mudança relevante de código ou de dependência e, em produção estável, a cada trimestre.

Cuidados: a ferramenta invoca de verdade (efeito colateral, custo, cota). Rode em ambiente de teste ou com payload sem efeito externo, e restrinja a função alvo por IAM. Trate o resultado como evidência, não como ordem: se a diferença de custo entre dois tamanhos for pequena, prefira o que reduz a latência p99.

## 3. Alavancas de custo, em ordem de retorno

| Alavanca | Quando vale | Armadilha |
|---|---|---|
| `arm64` (Graviton) | Quase sempre; mais barato por GB-s e normalmente igual ou mais rápido | Dependência nativa x86-only (JNI, camadas de terceiros) impede; valide no CI com a mesma arquitetura |
| Memória no ponto da curva | Toda função em produção | Reduzir memória sem medir alonga a duração e pode encarecer |
| `Timeout` realista | Sempre | Timeout de 900 s esconde laço infinito e chamada pendurada e paga por ela; use máximo esperado + folga |
| Reserved concurrency | Teto contra explosão de custo ou proteção de dependência frágil | Ela também **limita** a função: throttle antes do esperado se estiver baixa |
| Provisioned Concurrency | Tráfego base contínuo e SLA estrito | Cobra pelo tempo provisionado, com ou sem invocação; ver checklist no `SKILL.md` |
| Retenção de logs | Sempre | Log group sem retenção cresce para sempre; dev 7–30 dias, produção conforme compliance |
| Lote maior (ESM) | Processamento assíncrono/batch | Lote grande demais amplia o raio de falha por retry (ver seção 4) |

Árvore curta: tráfego imprevisível → sob demanda, sem PC. Base estável com picos → PC no piso, sob demanda nos picos. Batch → maximizar lote e calibrar memória por custo. Raramente chamada → memória mínima e aceitar cold start.

## 4. Event source mappings: o que calibrar

| Origem | Parâmetros principais | Observação |
|---|---|---|
| SQS | `BatchSize`, `MaximumBatchingWindowInSeconds`, `MaximumConcurrency` | `MaximumConcurrency` protege banco e APIs a jusante; use com `ReportBatchItemFailures` para não reprocessar o lote inteiro |
| Kinesis | `BatchSize`, `ParallelizationFactor`, `TumblingWindowInSeconds` | Paralelismo é por shard; sem partition key bem distribuída o fator não ajuda |
| DynamoDB Streams | `BatchSize`, `ParallelizationFactor` | Ordem por item é preservada dentro da partição; `IteratorAge` crescente indica consumidor atrasado |
| Kafka / MSK | `BatchSize`, `MaximumBatchingWindowInSeconds` | Janela maior economiza invocações ao custo de latência |

Regras de revisão:

- Handler **idempotente** sempre: a entrega é pelo menos uma vez, e retry de lote repete itens já processados.
- `IteratorAge` (streams) e idade da mensagem mais antiga (SQS) são os sinais de atraso; alarme em ambos.
- Falha parcial: devolva só os itens que falharam, em vez de lançar exceção e refazer tudo.
- Destino de falha (DLQ ou on-failure destination) configurado antes de produção; sem ele, evento esgotado some.
- Lote por tempo e por tamanho: com SnapStart ou Native, lote maior dilui o custo fixo da invocação, mas verifique o `Timeout` contra o pior caso do lote inteiro.

## 5. Response streaming (quando a resposta é grande ou lenta)

Streaming entrega bytes ao cliente à medida que são produzidos, em vez de bufferizar tudo. Considere quando:

- a resposta passa do limite síncrono bufferizado (da ordem de 6 MB) — o limite com streaming é bem maior (da ordem de 200 MB);
- o tempo até o primeiro byte importa (SSE, respostas de LLM, relatórios longos);
- o gateway/URL de função suporta o modo (Function URL com invoke mode de streaming; REST API precisa ser configurada para streaming; HTTP API não).

Pontos de atenção para Java: o runtime gerenciado exige a interface própria de streaming (`RequestStreamHandler` não é streaming de resposta); em Native com `provided.al2023`, o suporte depende do cliente de runtime. Valide no ambiente alvo, e confira o limite de timeout de integração vigente. Se o cliente aceita polling ou link pré-assinado do S3, essa costuma ser a opção mais simples e barata.

## 6. Checklist de revisão

- [ ] Arquitetura `arm64`, a menos que haja dependência x86 comprovada.
- [ ] Memória definida por medição (Power Tuning) com a fronteira de 1 vCPU no teste, não por palpite.
- [ ] Medição feita na versão publicada quando há SnapStart.
- [ ] `Timeout` = máximo esperado + folga; nada de 900 s por padrão.
- [ ] Retenção de log definida em todos os log groups.
- [ ] ESM com lote, janela e concorrência explícitos; falha parcial e destino de falha configurados.
- [ ] Alarmes em `IteratorAge`/idade de mensagem, erros e throttles.
- [ ] Handler idempotente para entrega pelo menos uma vez.
- [ ] Streaming só onde o gateway suporta e o ganho de latência/tamanho justifica.
