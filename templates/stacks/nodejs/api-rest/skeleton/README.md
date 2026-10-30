# {{project_name}} (Node.js 22)

API REST sem dependencias gerada pelo **MITR**: `node:http`, dominio congelado,
colecao de primeira classe, handler central de erros (dominio -> status) e
health check. Testes com `node:test` e gate de cobertura >=90%.

```bash
npm test    # unit + integracao HTTP real (porta efemera) + cobertura
npm start   # sobe em :3000
```
