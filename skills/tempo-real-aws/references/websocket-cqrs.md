# CQRS com API Gateway WebSocket — desenho detalhado

> Parte da skill `tempo-real-aws`. Hub: `../SKILL.md`. Implementação e testes de referência:
> `labs/aws-referencia-ordens/java` (`Projecao`, `Notificacao`, `Conexoes`, `CqrsWebSocketTest`).

## 1. Responsabilidades e consistência

| Componente | Faz | Não faz | Consistência |
|---|---|---|---|
| API de comando | valida, autentica, inicia o processo; responde 202 | não lê a projeção | — |
| Orquestração (Step Functions) | muda o estado de escrita com versão | não notifica cliente | forte por item |
| Eventos de domínio (CDC/outbox → EventBridge) | publica o estado novo | não garante ordem nem unicidade | at-least-once |
| Projeção de leitura | aplica a maior versão; serve consultas | não decide regra de negócio | eventual |
| Notificador | avisa conexões do dono | não é fonte de verdade | best-effort |
| Cliente | dedupe por versão; reconcilia ao reconectar | não confia só no push | — |

**CQRS ≠ WebSocket.** CQRS é a separação comando/consulta (dois modelos, duas tabelas, dois caminhos).
WebSocket é só o canal que encurta o "quando consultar".

## 2. Tabela de conexões

| Atributo | Valor |
|---|---|
| `pk` | `T:<tenant>:U:<usuário>` (dono) |
| `sk` | `C:<connectionId>` |
| `expiraEm` (TTL) | início + 7.200 s (duração máxima) + margem |

- Consulta do notificador: `Query pk = :dono AND begins_with(sk, 'C:')`, paginada.
- **TTL apaga "tipicamente em alguns dias"** e itens vencidos **continuam aparecendo** nas leituras →
  filtre `expiraEm > agora` e remova o vencido.
- `$disconnect` é **best-effort** → a limpeza garantida é `GoneException` + filtro + TTL.

## 3. Autenticação do `$connect` por ticket

1. Cliente autenticado chama `POST /conexoes/ticket` (REST + Cognito).
2. Serviço gera 32 bytes aleatórios (base64url), grava **só o SHA-256** com `expiraEm = agora + 60 s`
   e `usado = false`.
3. Cliente abre `wss://…/v1?ticket=<valor>`.
4. Lambda authorizer (REQUEST, `route.request.querystring.ticket`) faz `UpdateItem` condicional
   `usado = false AND expiraEm > :agora` → devolve política `Allow` e contexto `{tenantId, usuarioId}`.
5. A rota `$connect` grava a conexão com o contexto do autorizador.

Por quê: o navegador não envia `Authorization` no handshake; JWT na query string vai para logs e
tem validade longa. O ticket é inútil após um uso ou 60 s.

## 4. Envio e falhas

```
para cada conexão do dono:
  se expiraEm <= agora: remover; continuar
  POST @connections/{id}
    200          → entregue
    GoneException → remover a conexão
    outro erro    → falha transitória → item do lote volta à fila
```

Mensagem: `{tipo, versaoContrato, idEvento, ordemId, status, versao, atualizadoEm}` — ≤ 128 KB,
frames de 32 KB; nada interno.

## 5. Protocolo do cliente

1. Ao receber: se `versao > conhecida[ordemId]`, aplica; senão descarta (duplicata/atrasada).
2. Ao conectar/reconectar: novo ticket, abre o socket e **consulta** (`GET /ordens`) para
   reconciliar — o que chegou enquanto estava offline foi perdido por definição.
3. Ao trocar de aba/dispositivo: cada conexão é independente; o dono pode ter várias.
4. Em teste de consistência eventual: polling com **prazo** e **condição** ("versão ≥ N em até 30 s").

## 6. Testes obrigatórios (mapa para o cenário de referência)

| Falha | Teste |
|---|---|
| Duplicata | `CqrsWebSocketTest.duplicado` |
| Fora de ordem | `CqrsWebSocketTest.foraDeOrdem` |
| Cliente desconectado (`GoneException`) | `CqrsWebSocketTest.conexaoObsoleta` |
| TTL atrasado | `CqrsWebSocketTest.ttlAtrasado` |
| Falha transitória e reentrega | `CqrsWebSocketTest.falhaTransitoriaReprocessa` |
| Reconexão e consulta | `CqrsWebSocketTest.reconexaoRecuperaEstado` |
| Lote parcial | `HandlersTest.lotePacial` |
