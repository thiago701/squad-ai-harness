import assert from "node:assert/strict";
import { test } from "node:test";
import { Tarefas } from "../src/dominio/colecao.mjs";
import { TarefaInexistente, TituloInvalido, concluirTarefa, criarTitulo, descrever, novaTarefa } from "../src/dominio/tarefa.mjs";

test("titulo valida e normaliza na construcao", () => {
  assert.equal(criarTitulo("  comprar cafe  ").valor, "comprar cafe");
  assert.throws(() => criarTitulo("ab"), TituloInvalido);
  assert.throws(() => criarTitulo("x".repeat(121)), TituloInvalido);
});

test("tarefa imutavel: concluir devolve nova versao", () => {
  const original = novaTarefa("estudar node");
  const concluida = concluirTarefa(original);
  assert.equal(original.concluida, false);
  assert.equal(concluida.concluida, true);
  assert.ok(descrever(concluida).startsWith("[x]"));
  assert.throws(() => { original.concluida = true; }, TypeError);
});

test("colecao de primeira classe controla o conjunto", () => {
  const tarefas = new Tarefas();
  const tarefa = novaTarefa("revisar pr");
  tarefas.adicionar(tarefa);
  assert.equal(tarefas.total(), 1);
  tarefas.concluir(tarefa.identificador);
  assert.deepEqual(tarefas.pendentes(), []);
  assert.throws(() => tarefas.concluir("fantasma"), TarefaInexistente);
});
