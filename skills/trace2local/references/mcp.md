# MCP do Trace2Local — agentes lendo a execução real

> Fonte: `docs/MCP.md` e ADR-017 do repositório `trace2local`. E2E na stack alvo: 14/14.

Cliente fino da API local (stdio ou Streamable HTTP em `127.0.0.1`), JRE 21+, ~2,4 MB.

```bash
mvn -pl trace2local-mcp -am package -DskipTests   # → trace2local-mcp/target/trace2local-mcp-<v>-all.jar
java -jar trace2local-mcp-<v>-all.jar --help
```

## Registro no harness (repositório do APP)

| harness | arquivo | chave |
|---|---|---|
| Claude Code | `.mcp.json` (ou `claude mcp add trace2local -e TRACE2LOCAL_URL=… -- java -jar …`) | `mcpServers` |
| Cursor | `.cursor/mcp.json` | `mcpServers` |
| VS Code / Copilot | `.vscode/mcp.json` | `servers` |
| Windsurf / Devin / Codex | `mcp.json` / `config.toml` da ferramenta | equivalente |
| harness por URL | `java -jar … --http 7341` → `http://127.0.0.1:7341/mcp` (+ `TRACE2LOCAL_MCP_HTTP_TOKEN`) | — |

```json
{ "mcpServers": { "trace2local": { "command": "java",
  "args": ["-jar", "/caminho/trace2local-mcp-0.1.0-SNAPSHOT-all.jar"],
  "env": { "TRACE2LOCAL_URL": "http://127.0.0.1:19877/trace2local", "TRACE2LOCAL_MCP_TOOLS": "core" } } } }
```

## Configuração

| variável | padrão | efeito |
|---|---|---|
| `TRACE2LOCAL_URL` | `http://127.0.0.1:9876/trace2local` | embedded `:9876`; Station do compose `:19877` |
| `TRACE2LOCAL_MCP_TOOLS` | `all` | `core` = 7 ferramentas (~1,3 k tokens residentes × ~3 k do `all`) |
| `TRACE2LOCAL_MCP_ALLOW_MUTATIONS` | `false` | expõe `dispatch_endpoint`, `apply_mock_suggestion`, `put_mock_binding`, `control_mock_binding` |
| `TRACE2LOCAL_MCP_DATA` | `structural` | `full` inclui corpos de payload e valores de dados (já redigidos na origem) |
| `TRACE2LOCAL_MCP_ALLOW_REMOTE` | `false` | base fora do loopback |
| `TRACE2LOCAL_UI_TOKEN` | — | perfil corporate do Trace2Local |

## Ferramentas

Leitura: `status` · `list_executions` · `get_execution` (outline com `[nodeId]`, ✕ Δ SIM ↪ ⧗) · `get_step` ·
`get_logs` · `diagnose_failure` · `explain_execution` · `list_insights` · `get_topology` · `compare_executions` ·
`list_endpoints` · `wait_for_execution` · `list_mock_suggestions` · `list_mock_bindings` · `get_mock_journal` ·
`list_mock_plugins` · `validate_mock_binding`.
Mutação (opt-in): `dispatch_endpoint` · `apply_mock_suggestion` · `put_mock_binding` · `control_mock_binding`.
Prompts: `investigar-falha` · `validar-variacoes-de-parceiro` · `homologar-execucao`.

## Exemplo real (resumido)

```text
> diagnose_failure
Execução 77cf7f2f… · FAILED · 26.64 s · raiz: pix-api · POST /pix/transfers
CAUSA(S) RAIZ — FATO OBSERVADO
- [3c5fe631cddb7829] HTTP_CLIENT POST SPI (BACEN) /spi/v1/settlements
  caminho: pix-api › Aceitar e enviar para liquidação › SQS: pix-settlement › pix-settlement · SQS … › Liquidar no SPI
  erro: status do span: HTTP 503 · resposta do Mock Connect: [SIM …; variation=v-falha-transitoria]
LAUDO  desfecho: Falha técnica (93%, jev-deterministic)
PRÓXIMOS PASSOS  get_step(…) · compare_executions … · list_mock_suggestions host=spi.bacen.local
```

## Segurança (resumo para o threat model)

- Lê **apenas** a API local do Trace2Local; nenhuma rede externa; base só loopback por padrão.
- Somente leitura por padrão; anotações `readOnlyHint`/`destructiveHint`; mutação bloqueada responde `isError` com a
  instrução para o humano.
- O que vai ao modelo do agente: estrutura, tempos, erros e logs (redigidos na origem); payload/valores só em `full`.
- HTTP: bind `127.0.0.1`, validação de `Origin` (anti DNS rebinding), Bearer opcional, corpo ≤ 1 MiB.
- Saída limitada a 60 000 caracteres com aviso; sem estado próprio (nada persistido).
