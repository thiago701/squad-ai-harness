# Node.js 26 (Current) / 24 (LTS) — fatos de versão (verificado jul/2026)

> Fonte: nodejs.org/en/blog/release/v26.0.0 · nodejs.org/en/about/previous-releases · nodejs/Release.
> Absorvido pelo Skill Harvester em 2026-07-15. Revalidar a cada minor.

## Linha do tempo / suporte

| Versão | Papel (jul/2026) | Notas |
|---|---|---|
| Node 26 | **Current** (desde 2026-05-05) | Vira LTS em out/2026. Temporal default, V8 14.6 |
| Node 24 | **Active LTS** | Alvo recomendado para produção |
| Node 22 | Maintenance LTS | Migrar quando possível |

Mudança de processo: **1 major/ano a partir do Node 27** (anunciado em jun/2026) — antes eram 2/ano.
Majors pares entram em LTS; ímpares não. Prod deve mirar a Active LTS mais recente.

## Node 26 — destaques

- **Temporal habilitado por padrão.** API imutável e time-zone-aware que substitui `Date`.
  `Temporal.Now.instant()`, `Temporal.PlainDate`, `Temporal.ZonedDateTime`, aritmética de duração sem bugs de fuso.
- **V8 14.6** (Chromium 146). Novos métodos de coleção: `Map`/`WeakMap` `getOrInsert` (upsert) no JS.
- **Undici 8** sob `fetch` — correção, conformidade e confiabilidade na camada HTTP.

## Recursos estáveis que definem "Node moderno" (24/26)

- **fetch/Request/Response/Headers globais** — sem `node-fetch`/axios para o caso comum.
- **Test runner nativo** `node:test` + `node:assert`; `node --watch`; coverage nativo.
- **Permission model:** `--permission --allow-fs-read`/`--allow-fs-write`/`--allow-child-process` etc.
- **`--env-file=.env`** nativo (sem dotenv); **`node --run`** roda scripts do package.json.
- Suporte a rodar **TypeScript** direto via type-stripping (`--experimental-strip-types`) — ver `typescript-pro`.
- `WebSocket` cliente global; Web Streams; `structuredClone`; `AbortSignal.timeout()`.

## Armadilhas / migração

- **ESM vs CJS:** projeto novo em ESM (`"type":"module"`). Interop com CJS legado exige cuidado com `require`/`__dirname`.
- **Temporal** substitui `Date`, mas libs de terceiros ainda usam `Date` — cuidado na fronteira.
- **Bloqueio de event loop** continua sendo a causa nº 1 de latência — mover CPU pesado para `worker_threads`.
- Ao subir de 22→24/26, revise depreciações (`util._extend`, APIs de crypto legadas).

## Ferramentas do ecossistema (2026)

- Gerenciadores: **npm**, **pnpm** (rápido, disk-efficient), Yarn. Lockfile sempre commitado.
- Lint/format: **ESLint** (flat config) + **Prettier**, ou **Biome** (lint+format num binário).
- Teste: `node:test` nativo; **vitest** para suites grandes. HTTP: Fastify (`inject`), supertest.
- Perf: `node --prof`, `clinic.js`, `0x`. Segurança: `npm audit`, `osv-scanner`, permission model.
