## Observabilidade mínima
Logging estruturado (JSON) com nível, timestamp e correlação; sem dados sensíveis. Health check exposto (liveness/readiness quando aplicável). Métricas de negócio nomeadas quando o serviço for de longa vida; tracing distribuído apenas quando houver mais de um serviço na cadeia.
