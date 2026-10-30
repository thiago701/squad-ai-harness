# TypeScript 7.0 — fatos de versão (verificado jul/2026)

> Fonte: github.com/microsoft/typescript-go · infoworld / theregister / visualstudiomagazine (jun–jul 2026).
> Absorvido pelo Skill Harvester em 2026-07-15. Revalidar a cada minor.

## Linha do tempo

| Marco | Data |
|---|---|
| Anúncio "Project Corsa" (port p/ Go) | 2025-03 |
| TS 7.0 RC | 2026-06-18 |
| **TS 7.0 GA** | **2026-07-08** |

"Strada" = codebase legado em JS/TS. "Corsa" = novo compilador em Go. TS 6.x foi a última linha do
compilador antigo; TS 7 é o Go-native.

## O que é (e o que NÃO é)

- **É um PORT, não uma reescrita de linguagem.** A semântica de checagem de tipos é **idêntica** ao TS 6.
  O que muda é a implementação (Go) e a **velocidade**.
- **Ganho medido:** Microsoft cita **8–12x** em build completo. Exemplo oficial: type-check do codebase do
  VS Code caiu de **125,7s (TS 6) para 10,6s (TS 7)** = **~11,9x**. Language service (editor) também reescrito.
- **Mesma config, mesmos tipos:** `tsconfig.json`, flags e tipos existentes continuam valendo.

## Migração

- Instale o novo compilador (`tsgo` / `typescript@7`). Rode o build — a maioria dos projetos "só funciona".
- **Erros novos aparecendo?** Muitas vezes são bugs reais que o compilador antigo mascarava — corrija, não suprima.
- Ferramentas que embutiam a API do compilador antigo (alguns bundlers/plugins) precisam de versão compatível
  com a nova API. Verifique ts-loader/ts-jest/eslint-parser antes de migrar CI.
- Estratégia segura: rodar TS 6 e TS 7 em paralelo no CI por um período, comparar diagnósticos.

## Boas práticas de tipagem (independem da versão)

- `strict: true` + `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes`.
- `unknown` na borda, estreitar com type guards; `any` proibido.
- Discriminated unions + exhaustiveness com `never`.
- Validação de runtime com zod/valibot; derivar tipo do schema (`z.infer`).
- `verbatimModuleSyntax` + `moduleResolution: bundler|nodenext`; project references em monorepo.

## Ecossistema (2026)

- Build/bundle: esbuild, tsup, vite, swc. Type-check no CI com `tsgo --noEmit` (agora barato).
- Runtime direto: Node type-stripping (`--experimental-strip-types`), tsx, Deno/Bun.
- Lint type-aware: `typescript-eslint`. Testes: vitest, `node:test`, tsd/expectTypeOf p/ tipos.
