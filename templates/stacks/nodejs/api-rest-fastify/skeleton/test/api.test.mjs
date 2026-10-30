import assert from "node:assert/strict";
import { test } from "node:test";
import { criarAplicacao } from "../src/adaptadores/api.mjs";

test("fluxo completo via inject (sem porta real)", async () => {
  const aplicacao = criarAplicacao();
  const saude = await aplicacao.inject({ method: "GET", url: "/health" });
  assert.equal(saude.statusCode, 200);
  const criada = await aplicacao.inject({
    method: "POST", url: "/tarefas", payload: { titulo: "integrar fastify" },
  });
  assert.equal(criada.statusCode, 201);
  const { identificador } = criada.json();
  const lista = await aplicacao.inject({ method: "GET", url: "/tarefas" });
  assert.deepEqual(lista.json(), ["[ ] integrar fastify"]);
  const conclusao = await aplicacao.inject({ method: "POST", url: `/tarefas/${identificador}/concluir` });
  assert.equal(conclusao.statusCode, 200);
});

test("handler central + json schema traduzem erros", async () => {
  const aplicacao = criarAplicacao();
  const dominio = await aplicacao.inject({ method: "POST", url: "/tarefas", payload: { titulo: "ab" } });
  assert.equal(dominio.statusCode, 422);
  const schema = await aplicacao.inject({ method: "POST", url: "/tarefas", payload: {} });
  assert.equal(schema.statusCode, 400);
  const fantasma = await aplicacao.inject({ method: "POST", url: "/tarefas/x/concluir" });
  assert.equal(fantasma.statusCode, 404);
});
