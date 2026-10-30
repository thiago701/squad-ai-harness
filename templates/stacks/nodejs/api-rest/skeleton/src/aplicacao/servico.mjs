// Caso de uso: unica dependencia e a colecao (injetada).
import { descrever, novaTarefa } from "../dominio/tarefa.mjs";

export class ServicoDeTarefas {
  #tarefas;

  constructor(tarefas) {
    this.#tarefas = tarefas;
  }

  criar(tituloBruto) {
    const tarefa = novaTarefa(tituloBruto);
    this.#tarefas.adicionar(tarefa);
    return tarefa.identificador;
  }

  concluir(identificador) {
    return descrever(this.#tarefas.concluir(identificador));
  }

  pendentes() {
    return this.#tarefas.pendentes().map(descrever);
  }
}
