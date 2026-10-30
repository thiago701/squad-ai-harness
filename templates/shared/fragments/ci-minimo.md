## CI mínima por projeto
Gate único e rápido: build limpo → lint/tipos → testes com cobertura ≥90% → análise estatica/OC → scan de dependências e secrets. Qualquer etapa vermelha bloqueia merge. Artefato só é publicado a partir de pipeline verde e reprodutível.
