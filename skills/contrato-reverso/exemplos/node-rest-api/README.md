# Exemplo — Node.js + REST API (v1) + Cognito + CORS

Caso de validação do **C1 Node** e do **leitor SAM REST** da skill `contrato-reverso`.

```bash
python ../../scripts/cr.py verificar --raiz . --nivel direcionado   # A + B + C1 (runner Node, Gateway simulado)
python ../../scripts/cr.py bench --raiz . --so-estatico             # ou sem --so-estatico para incluir C1
```

O que ele exercita: payload 1.0 (`event.resource`, `requestContext.authorizer.claims`), 403
"Missing Authentication Token" para rota inexistente (REST), 401 do autorizador antes do Lambda,
CORS de preflight pelo Gateway **e** `Access-Control-Allow-Origin` devolvido pelo próprio Lambda
(em REST com proxy o Gateway não acrescenta), isolamento por dono (404, nunca 403), ordenação.
