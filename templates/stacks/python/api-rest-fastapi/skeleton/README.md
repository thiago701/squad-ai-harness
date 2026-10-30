# {{project_name}} (FastAPI + Pydantic v2)

API REST Python moderna gerada pelo **MITR**: borda FastAPI fina (rota so
orquestra), dominio puro sem framework, Pydantic v2 validando o contrato,
handler central `ErroDeDominio -> HTTP`, health check e OpenAPI automatica.

```bash
make install && make check   # lint + mypy strict + testes com cobertura >=90%
make run                     # uvicorn em :8000 (docs em /docs)
```
