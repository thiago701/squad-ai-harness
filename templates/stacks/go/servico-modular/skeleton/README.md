# {{project_name}} (Go)

Servico Go idiomatico gerado pelo **MITR**: dominio puro com erros sentinela,
colecao de primeira classe, porta definida no consumidor, repositorio com mutex
e CLI com handler central + slog JSON.

```bash
make check   # go vet + testes table-driven + cobertura >=90% (gate)
make build   # binario estatico minimo (CGO off, trimpath)
```
