import assert from "node:assert/strict";
import { test } from "node:test";
import { Tarefas } from "../src/dominio/colecao.mjs";
import { ServicoDeTarefas } from "../src/aplicacao/servico.mjs";

test("fluxo criar -> listar -> concluir", () => {
  const servico = new ServicoDeTarefas(new Tarefas());
  const identificador = servico.criar("escrever adr");
  assert.deepEqual(servico.pendentes(), ["[ ] escrever adr"]);
  assert.equal(servico.concluir(identificador), "[x] escrever adr");
  assert.deepEqual(servico.pendentes(), []);
});
