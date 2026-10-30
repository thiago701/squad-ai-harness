# clean-code-craftsman · Padrões consolidados em campo

> Reference da skill `clean-code-craftsman` (movida da SKILL.md em 11/10/2026 — hub + references, I3). Carregue só quando a tarefa pedir este tema.

## Padrões consolidados em campo

Estas técnicas emergiram de revisões reais e merecem reconhecimento explícito —
não são "as únicas formas certas", mas são respostas conhecidas a smells comuns.

### Lifecycle helper substitui try/finally repetido

**Smell**: o método carrega estado mutável (`int statusCode = 500; boolean ok = false;`)
para depois emitir log/métrica num `finally`. Quando o mesmo padrão aparece em 2+
métodos, há um helper esperando para nascer:

```java
// Antes — estado mutável + try/finally manual, repetido em vários métodos
private Response doHandle(Request req) {
    LOG.received(OPERATION);
    var t0 = System.nanoTime();
    int statusCode = 500;
    boolean ok = false;
    try {
        var resp = processar(req);
        statusCode = resp.status();
        ok = true;
        return resp;
    } finally {
        LOG.completed(OPERATION, statusCode, ok);
        METRICS.record(OPERATION, System.nanoTime() - t0, statusCode);
    }
}
```

```java
// Depois — o lifecycle helper encapsula log/métrica e o try/finally
private Response doHandle(Request req) {
    return lifecycle(OPERATION, () -> processar(req));
}

// helper reutilizável: nasceu do padrão repetido em 2+ métodos
private Response lifecycle(String op, Supplier<Response> acao) {
    LOG.received(op);
    var t0 = System.nanoTime();
    int statusCode = 500;
    try {
        var resp = acao.get();
        statusCode = resp.status();
        return resp;
    } finally {
        LOG.completed(op, statusCode);
        METRICS.record(op, System.nanoTime() - t0, statusCode);
    }
}
```

> **Por que vale a pena:** o `try/finally` e a emissão de log/métrica deixam de ser copiados
> em cada handler. O smell (estado mutável espalhado) some, e o ponto de observabilidade
> passa a ter um dono único — alinhado a P1-Simplicidade.
