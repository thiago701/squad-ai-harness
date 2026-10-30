# {{project_name}}

Aplicacao Python modular gerada pelo **MITR** (Squad AI). Arquitetura: monolito modular
`dominio/ → aplicacao/ → adaptadores/` (dependencias apontam para dentro).

## Comandos
```bash
make install   # dev-deps (pytest, ruff, mypy)
make check     # lint + tipos + testes com cobertura >=90% (gate)
make run       # CLI: listar pendencias
```

## Regras que este projeto ja cumpre
Object Calisthenics (9 regras — VOs, colecao de primeira classe, sem getters);
erros de dominio tipados com handler central na borda; logging estruturado JSON;
container multi-stage non-root; CI minima em `ci.yml`.
