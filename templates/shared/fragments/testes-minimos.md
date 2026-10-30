## Testes mínimos (qualquer stack)
TDD como padrão: teste primeiro, RED→GREEN. Unit + integração no mínimo; contrato/E2E quando houver borda de rede. Cobertura ≥90% de linhas verificada no build (gate, não sugestão). Teste falhando = entrega bloqueada. Testes determinísticos: sem sleep arbitrário, sem rede externa, sem ordem implícita.
