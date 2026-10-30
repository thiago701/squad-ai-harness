import assert from "node:assert/strict";
import { test } from "node:test";
import { Tarefas } from "../src/dominio/colecao.js";
import { ServicoDeTarefas } from "../src/aplicacao/servico.js";

test("fluxo completo com propagacao de Resultado", () => {
  const servico = new ServicoDeTarefas(new Tarefas());
  const criada = servico.criar("escrever adr");
  assert.equal(criada.tipo, "sucesso");
  if (criada.tipo !== "sucesso") return;
  assert.deepEqual([...servico.pendentes()], ["[ ] escrever adr"]);
  assert.equal(servico.concluir(criada.valor).tipo, "sucesso");
  assert.equal(servico.criar(99).tipo, "falha");
  assert.equal(servico.concluir("fantasma").tipo, "falha");
});
