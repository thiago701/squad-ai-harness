#!/usr/bin/env python3
"""
Teste stub para OutboxPollerRelay :: publicação de eventos

DETALHE: O template OutboxPollerRelay (infraestrutura/outbox/) recupera
eventos não processados e os marca como processado, mas não os publica.

O TODO na linha 1326 documenta a decisão pendente:
  // TODO: publicar em SQS / Kafka / listener in-process

EXPECTATIVA FUTURA (débito D-20261023-001):
  - Recuperar lote de eventos não processados ✓ (implementado)
  - Publicar em ALGUM sistema (SQS, Kafka, ou listener in-process) ✗ (TODO)
  - Marcar como processado só após confirmação de entrega ✗ (exige decisão de arquitetura)

DECISION GATE: Qual sistema de publicação?
  1. SQS: integração AWS nativa, DLQ, sem setup externo
  2. Kafka: alta throughput, replay, requer cluster
  3. Listener in-process: zero deps, local, sem durabilidade entre restarts

PRÉ-REQUISITO: decisão de arquitetura com tech-lead antes de implementar.
"""

import unittest


class OutboxRelayPublishingDecision(unittest.TestCase):
    """
    Stub de teste documentando a decisão pendente: qual estratégia de publicação
    para eventos da Outbox.
    """

    def test_outbox_relay_recupera_nao_processados(self):
        """✓ Implementado: buscar eventos não processados do banco."""
        # tpl_outbox_relay(..) gera:
        #   repo.findUnprocessed(PageRequest.of(0, BATCH_SIZE))
        pass

    def test_outbox_relay_marca_processado(self):
        """✓ Implementado: marcar evento como processado."""
        # tpl_outbox_relay(..) gera:
        #   evt.markProcessed(Instant.now())
        pass

    def test_outbox_relay_publica_evento(self):
        """✗ TODO: publicar evento em algum sistema de mensageria."""
        # DECISÃO PENDENTE: qual sistema?
        # A) SQS: evt -> SqsClient.sendMessage(queueUrl, ...)
        # B) Kafka: evt -> KafkaTemplate.send(topic, ...)
        # C) Listener in-process: EventBus.publish(evt)
        self.skipTest("Aguardando decisão de arquitetura: SQS vs Kafka vs listener")


if __name__ == "__main__":
    unittest.main()
