// Colecao de primeira classe com Resultado (fluxo esperado sem excecao).
import { type Resultado, type Tarefa, TarefaInexistente, concluirTarefa, falha, sucesso } from "./tarefa.js";

export class Tarefas {
  readonly #itens = new Map<string, Tarefa>();

  adicionar(tarefa: Tarefa): void {
    this.#itens.set(tarefa.identificador, tarefa);
  }

  concluir(identificador: string): Resultado<Tarefa> {
    const existente = this.#itens.get(identificador);
    if (existente === undefined) {
      return falha(new TarefaInexistente(`tarefa ${identificador} nao encontrada`));
    }
    const concluida = concluirTarefa(existente);
    this.#itens.set(identificador, concluida);
    return sucesso(concluida);
  }

  pendentes(): readonly Tarefa[] {
    return [...this.#itens.values()].filter((tarefa) => !tarefa.concluida);
  }

  total(): number {
    return this.#itens.size;
  }
}
