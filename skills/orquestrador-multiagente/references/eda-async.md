# Coordenação Assíncrona & Arquitetura Orientada a Eventos (EDA)

## Porquê EDA
Acoplamento síncrono (HTTP/gRPC) cria bloqueio de latência e dependência mútua de disponibilidade.
Um **barramento de mensagens** central reduz a topologia de conexões de **O(N²) → O(N)**.
Migrar de **polling** para fluxos reativos corta latência **70–90%**: agentes ficam **adormecidos** (sem
consumir CPU) até um evento correspondente ser publicado.

```
Ponto-a-ponto O(N²)          EDA O(N)
A ─ B                        A   B   C   D
│ ╳ │              →          \  |   |  /
C ─ D                        [ Barramento (Kafka/RabbitMQ) ]
```

## Padrões de coordenação
- **Cadeias de eventos (pipelines)** — evento de conclusão (`pesquisa.concluida`) dispara o próximo agente.
- **Fan-out** — um evento (`documento.carregado`) ativa em paralelo vários subscritores (qualidade,
  extração de entidades, indexação) → reduz o tempo total do pipeline.
- **Event Sourcing** — log imutável e ordenado de todas as mudanças de estado/decisões; reconstrói
  qualquer estado histórico → trilho de auditoria incontestável (governança, forense).
- **Saga** — transações distribuídas **sem locks**: cada agente faz uma transação local e emite evento;
  se um passo falha (ex.: pagamento após reserva de voo), a saga executa **transações compensatórias**
  em sentido inverso para desfazer efeitos e restaurar consistência global.

## Kafka em alto rendimento
Partição por **chave = `thread_id`** garante que eventos da mesma sessão vão para a **mesma partição** →
processamento **estritamente ordenado** pelo grupo de consumidores. Recuperação por **replay** do log a
partir do último **offset** confirmado.

> Ponte com a Squad: o **padrão Saga** aqui é o mesmo do módulo **Conductor** (ADR-005/ADR-006, memória
> `saga-sec-fase1`). Implementação de streaming/infra → `arquiteto-dados-streaming` / `engenheiro-iac`.
