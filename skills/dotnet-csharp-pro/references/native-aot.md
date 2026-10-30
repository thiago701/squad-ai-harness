# Native AOT em .NET (9 e 10) — fatos e guia (verificado jul/2026)

> Fonte: learn.microsoft.com/dotnet/core/deploying/native-aot · learn.microsoft.com/aspnet/core/fundamentals/native-aot
> · whats-new/dotnet-9 · devblogs (.NET 8/9 EOS). Absorvido pelo Skill Harvester em 2026-07-15.

## O que é
Native AOT (**Ahead-Of-Time**) compila o app para **código nativo autocontido**, sem JIT nem IL em runtime.
Ganho: **cold-start em ms**, **RSS menor**, binário único, sem dependência de runtime instalado. Ideal para
serverless/Lambda, escala-a-zero, contêineres densos e CLIs. Ativa com `<PublishAot>true</PublishAot>` +
`dotnet publish -r <rid> -c Release`.

## O custo (por que exige disciplina)
No publish AOT, **todo código não alcançável é removido (trimming)** e **não há reflection irrestrita em
runtime**. O analisador estático não prevê reflexão dinâmica → o trimmer remove tipos que você esperava
refletir, e o app quebra em runtime. Logo: **AOT-first é uma decisão de design**, não um flag no fim.

## Regras inegociáveis
1. **Minimal APIs, não MVC.** MVC **não** é AOT-compatível. Blazor/MAUI têm suporte parcial; valide.
2. **`System.Text.Json` source generator obrigatório.** Todo tipo em corpo HTTP / retorno de delegate em
   Minimal API deve estar num `JsonSerializerContext` (`[JsonSerializable(typeof(T))]`). Newtonsoft.Json
   **não** é AOT-friendly.
3. **Anote reflexão restante** com `[DynamicallyAccessedMembers(...)]` e prefira **source generators**
   (`LoggerMessage`, `RegexGenerator`, `GeneratedComInterface`) a reflexão.
4. **Trate os IL warnings como erros** (`<TreatWarningsAsErrors>` + `<IsAotCompatible>true</IsAotCompatible>`
   nas libs) — eles são a única sinalização de que algo quebrará em runtime.

## Tabela de IL warnings (os que você mais verá)
| Warning | Significado | Ação |
|---|---|---|
| **IL2026** (`RequiresUnreferencedCode`) | membro marcado como incompatível com trimming | isolar/anotar o chamador ou remover a dependência de reflexão |
| **IL2070 / IL2067 / IL2072** | fluxo de `Type`/parâmetro sem `DynamicallyAccessedMembers` | anotar o parâmetro/campo com o `DynamicallyAccessedMemberTypes` correto |
| **IL3050** (`RequiresDynamicCode`) | API precisa de geração de código em runtime (não existe sob AOT) | trocar por alternativa source-gen; não há atalho |

## .NET 9 vs .NET 10 (deltas de AOT)
- **.NET 9 (STS, EOS 10/nov/2026):** amplia AOT sobre a base do 8 — **SignalR passa a suportar trimming/AOT**
  (mas **hubs fortemente tipados NÃO** sob `PublishAot`; parâmetros `IAsyncEnumerable<T>`/`ChannelReader<T>`
  com `T` struct lançam exceção em startup). Compilador **inlina thread-local statics** (menos instruções);
  `UnsafeAccessorAttribute` ganha parâmetros genéricos (CoreCLR/AOT). Binário menor por remoção de features.
- **.NET 10 (LTS, até nov/2028):** cobertura AOT mais ampla, menos trimming warnings, Native AOT como caminho
  de primeira classe para cloud-native. **Alvo recomendado** para AOT em código novo de longa vida.

## Fluxo de trabalho
1. Desde o início: `PublishAot` ligado, Minimal API, STJ source-gen, `IsAotCompatible` nas libs próprias.
2. Build com warnings-as-errors; **zere IL2026/IL207x/IL3050** antes de seguir.
3. Teste o **binário publicado** (não só o build JVM/JIT) — comportamento de trimming só aparece no publish.
4. Meça cold-start/RSS antes/depois (P2/P3 exigem número). Contêiner: imagem distroless/UBI-micro.

## Reuso no ecossistema (busca de skills)
- **Oficial — `dotnet/skills` › `dotnet-aot-compat`** (time .NET): torna projeto **existente** AOT-compatível,
  resolvendo IL warnings, adicionando `DynamicallyAccessedMembers` e ligando `IsAotCompatible`. Melhor
  ferramenta para **migração**; este skill cobre **design AOT-first** de código novo.
- Catálogos comunitários: `managedcode/dotnet-skills`, `Aaronontheweb/dotnet-skills`, `wshaddix/dotnet-skills`
  (verificar install count/estrelas antes de adotar — política do `find-skills`).
- **Lambda Java** AOT (GraalVM) → `aws-lambda-java25-aot`; **Quarkus** native → `quarkus-java-aot`.
