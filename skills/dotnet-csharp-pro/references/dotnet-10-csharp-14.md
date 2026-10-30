# .NET 10 (LTS) + C# 14 — fatos de versão (verificado jul/2026)

> Fonte: learn.microsoft.com/dotnet (What's new in C# 14 / .NET 10) · devblogs.microsoft.com/dotnet.
> Absorvido pelo Skill Harvester em 2026-07-15. Revalidar a cada servicing release.

## Linha do tempo / suporte

| Release | Tipo | Situação (jul/2026) |
|---|---|---|
| .NET 10 | **LTS** | Recomendada p/ produção. Último patch **10.0.10** (2026-07-14), SDK 10.0.302 / 10.0.110. Suporte até **2028-11-10** |
| .NET 9 | STS | **EOS 10/nov/2026** (mesmo dia do .NET 8); patch 9.0.18 (jul/2026). STS agora 24 meses. AOT: SignalR trimming/AOT, inlining de thread-local statics |
| .NET 8 | LTS | Ainda suportada; patch 8.0.29 (jul/2026) |
| .NET 11 | Preview | Preview 6 (jul/2026), GA prevista nov/2026. Traz C# unions. **Não usar em prod** |

## C# 14 — recursos

- **Extension members:** blocos `extension` habilitam propriedades de extensão, operadores de extensão
  e membros estáticos de extensão (antes só métodos de extensão). Maior mudança visível da versão.
- **Field-backed properties:** palavra `field` dá acesso ao backing field gerado pelo compilador dentro
  de um accessor custom — transição suave de auto-property para lógica no get/set.
- **`nameof` com tipos genéricos não fechados:** `nameof(List<>)` → `"List"`.
- **Modificadores de parâmetro em lambdas** (`ref`/`in`/`out`) sem anotar o tipo.
- **`partial` para construtores de instância e eventos** (complementa métodos/propriedades partial do C# 13).
- **Null-conditional assignment `?.=`** e **conversões implícitas de `Span<T>`/`ReadOnlySpan<T>`**.

## .NET 10 runtime / libs

- GC geracional com pausas menores; write barriers melhorados.
- Suporte a **Intel AVX10.2** e **ARM SVE** via intrínsecos de hardware.
- **Native AOT** com cobertura ampliada e menos trimming warnings.
- Throughput ~6–9% maior processando muitos JSON pequenos após recompilar; menos boxing em genéricos comuns.
- Melhorias de PQC (criptografia pós-quântica) na BCL.
- ASP.NET Core 10: Minimal APIs mais capazes, validação, OpenAPI embutida; Blazor com melhorias de render.

## Armadilhas / migração

- **Native AOT ≠ grátis:** reflection livre, `dynamic` e serialização por reflexão quebram. Use source
  generators (`System.Text.Json` context, `LoggerMessage`) e trate todos os trimming/AOT warnings.
- **Newtonsoft.Json** ainda funciona, mas não é AOT-friendly — prefira `System.Text.Json` em código novo.
- `async void` continua sendo bug fora de event handlers — engole exceção.
- Ao subir de .NET 8, revise breaking changes de bibliotecas e `TargetFramework` `net10.0`.

## Ferramentas do ecossistema (2026)

- SDK: `dotnet` CLI, `global.json` para fixar versão. Build determinístico.
- Teste: **xUnit** (padrão da casa), NUnit/MSTest alternativos; coverlet; `WebApplicationFactory`; Testcontainers.
- Perf: **BenchmarkDotNet**, `dotnet-trace`, `dotnet-counters`, `dotnet-gcdump`.
- Qualidade: analyzers Roslyn, `dotnet format`, `TreatWarningsAsErrors`, EditorConfig.
- Segurança: `dotnet list package --vulnerable`, assinatura de pacotes, NuGet lock files.
