#!/usr/bin/env node
// Runner do verificador C1 para handlers Lambda em Node.js (ESM ou CommonJS), sem dependências.
// Roda no diretório do PROVEDOR e fala JSON por linha: {"evento":{...}} -> {"resposta":{...}} | {"erro":"..."}.
//   --fabrica caminho/arquivo.mjs#criarHandler   função (sync/async) que devolve o handler com dublês
//   --handler caminho/arquivo.mjs#handler        o handler direto (só se não tocar nuvem)
import { createInterface } from "node:readline";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
import { randomUUID } from "node:crypto";

const args = process.argv.slice(2);
const modo = args[0] === "--fabrica" ? "fabrica" : "handler";
const [arquivo, exportacao = modo === "fabrica" ? "criarHandler" : "handler"] = String(args[1] || "").split("#");
const saida = (obj) => process.stdout.write(JSON.stringify(obj) + "\n");
console.log = (...a) => process.stderr.write(a.join(" ") + "\n"); // logs do handler não sujam o protocolo
console.info = console.log;

let handler;
try {
  const mod = await import(pathToFileURL(resolve(process.cwd(), arquivo)).href);
  const alvo = mod[exportacao] ?? mod.default?.[exportacao] ?? (exportacao === "default" ? mod.default : undefined);
  if (typeof alvo !== "function") throw new Error(`exportação '${exportacao}' não é função em ${arquivo}`);
  handler = modo === "fabrica" ? await alvo() : alvo;
} catch (e) {
  saida({ erro: String(e && e.stack || e) });
  process.exit(1);
}
saida({ runner: "node", versao: process.version, modo });

const contexto = () => ({
  awsRequestId: randomUUID(), functionName: "cdc-verificador", memoryLimitInMB: "512",
  getRemainingTimeInMillis: () => 30000, callbackWaitsForEmptyEventLoop: false,
});

const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const linha of rl) {
  if (!linha.trim()) continue;
  try {
    const { evento } = JSON.parse(linha);
    const resposta = await new Promise((ok, falha) => {
      const r = handler(evento, contexto(), (err, res) => (err ? falha(err) : ok(res)));
      if (r && typeof r.then === "function") r.then(ok, falha);
      else if (r !== undefined) ok(r); // handler síncrono que devolve valor
    });
    saida({ resposta });
  } catch (e) {
    saida({ erro: String(e && e.stack || e) }); // exceção do handler vira 502 do Gateway, como na AWS
  }
}
