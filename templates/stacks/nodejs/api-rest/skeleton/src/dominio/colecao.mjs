// Colecao de primeira classe: o comportamento do conjunto mora aqui.
import { TarefaInexistente, concluirTarefa } from "./tarefa.mjs";

export class Tarefas {
  #itens = new Map();

  adicionar(tarefa) {
    this.#itens.set(tarefa.identificador, tarefa);
  }

  concluir(identificador) {
    const existente = this.#itens.get(identificador);
    if (!existente) {
      throw new TarefaInexistente(`tarefa ${identificador} nao encontrada`);
    }
    const concluida = concluirTarefa(existente);
    this.#itens.set(identificador, concluida);
    return concluida;
  }

  pendentes() {
    return [...this.#itens.values()].filter((tarefa) => !tarefa.concluida);
  }

  total() {
    return this.#itens.size;
  }
}
