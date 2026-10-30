import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { criarAplicacao } from "../src/adaptadores/http.mjs";

let servidor;
let base;

before(async () => {
  servidor = criarAplicacao();
  await new Promise((pronto) => servidor.listen(0, pronto));
  base = `http://127.0.0.1:${servidor.address().port}`;
});

after(() => servidor.close());

test("health e fluxo completo pela borda HTTP", async () => {
  const saude = await fetch(`${base}/health`);
  assert.equal(saude.status, 200);
  const criada = await fetch(`${base}/tarefas`, {
    method: "POST", body: JSON.stringify({ titulo: "integrar http" }),
  });
  assert.equal(criada.status, 201);
  const { identificador } = await criada.json();
  const lista = await (await fetch(`${base}/tarefas`)).json();
  assert.deepEqual(lista, ["[ ] integrar http"]);
  const conclusao = await fetch(`${base}/tarefas/${identificador}/concluir`, { method: "POST" });
  assert.equal(conclusao.status, 200);
});

test("handler central traduz erros de dominio", async () => {
  const invalida = await fetch(`${base}/tarefas`, { method: "POST", body: JSON.stringify({ titulo: "ab" }) });
  assert.equal(invalida.status, 422);
  const fantasma = await fetch(`${base}/tarefas/nao-existe/concluir`, { method: "POST" });
  assert.equal(fantasma.status, 404);
  const jsonQuebrado = await fetch(`${base}/tarefas`, { method: "POST", body: "{" });
  assert.equal(jsonQuebrado.status, 422);
  const rotaErrada = await fetch(`${base}/nada`);
  assert.equal(rotaErrada.status, 404);
});
