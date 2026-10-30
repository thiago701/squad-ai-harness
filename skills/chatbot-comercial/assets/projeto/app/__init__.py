"""Chatbot comercial multi-tenant — monólito modular.

M1 `agente` + `ferramentas` + `vertical`   agente especializado
M2 `conhecimento`                          RAG com citação obrigatória
M3 `leads`                                 captura, qualificação, exportação
M4 `curadoria`                             retreinamento com gate humano
M5 `auditoria` + `dashboard`               trilha, custo, LGPD, métricas

`servico.Servico` costura tudo. Canais entram por `canais`.
"""

__all__ = ["__version__"]
__version__ = "0.1.0"
