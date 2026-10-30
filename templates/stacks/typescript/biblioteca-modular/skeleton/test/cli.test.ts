import assert from "node:assert/strict";
import { test } from "node:test";
import { executar } from "../src/adaptadores/cli.js";

test("cli traduz Resultado em codigo de saida", () => {
  assert.equal(executar([]), 0);
  assert.equal(executar(["criar", "nova tarefa valida"]), 0);
  assert.equal(executar(["criar", "ab"]), 2);
  assert.equal(executar(["concluir", "fantasma"]), 2);
});
