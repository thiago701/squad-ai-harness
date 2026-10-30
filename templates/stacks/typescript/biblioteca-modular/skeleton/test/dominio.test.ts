import assert from "node:assert/strict";
import { test } from "node:test";
import { Tarefas } from "../src/dominio/colecao.js";
import { TituloInvalido, concluirTarefa, criarTitulo, descrever, novaTarefa } from "../src/dominio/tarefa.js";

test("criarTitulo devolve union discriminada", () => {
  const valido = criarTitulo("  estudar ts  ");
  assert.equal(valido.tipo, "sucesso");
  const curto = criarTitulo("ab");
  assert.equal(curto.tipo, "falha");
  if (curto.tipo === "falha") assert.ok(curto.erro instanceof TituloInvalido);
  assert.equal(criarTitulo(42).tipo, "falha");
  assert.equal(criarTitulo("x".repeat(121)).tipo, "falha");
});

test("tarefa imutavel e descricao", () => {
  const titulo = criarTitulo("revisar contrato");
  assert.equal(titulo.tipo, "sucesso");
  if (titulo.tipo !== "sucesso") return;
  const original = novaTarefa(titulo.valor);
  const concluida = concluirTarefa(original);
  assert.equal(original.concluida, false);
  assert.ok(descrever(concluida).startsWith("[x]"));
});

test("colecao de primeira classe com Resultado", () => {
  const tarefas = new Tarefas();
  const titulo = criarTitulo("planejar sprint");
  if (titulo.tipo !== "sucesso") assert.fail("titulo deveria ser valido");
  const tarefa = novaTarefa(titulo.valor);
  tarefas.adicionar(tarefa);
  assert.equal(tarefas.total(), 1);
  assert.equal(tarefas.concluir(tarefa.identificador).tipo, "sucesso");
  assert.deepEqual([...tarefas.pendentes()], []);
  assert.equal(tarefas.concluir("fantasma").tipo, "falha");
});
