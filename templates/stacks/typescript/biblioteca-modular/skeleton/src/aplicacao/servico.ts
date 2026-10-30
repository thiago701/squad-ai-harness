// Caso de uso com contratos explicitos e propagacao de Resultado.
import { Tarefas } from "../dominio/colecao.js";
import { type Resultado, criarTitulo, descrever, novaTarefa } from "../dominio/tarefa.js";

export class ServicoDeTarefas {
  readonly #tarefas: Tarefas;

  constructor(tarefas: Tarefas) {
    this.#tarefas = tarefas;
  }

  criar(tituloBruto: unknown): Resultado<string> {
    const titulo = criarTitulo(tituloBruto);
    if (titulo.tipo === "falha") {
      return titulo;
    }
    const tarefa = novaTarefa(titulo.valor);
    this.#tarefas.adicionar(tarefa);
    return { tipo: "sucesso", valor: tarefa.identificador };
  }

  concluir(identificador: string): Resultado<string> {
    const resultado = this.#tarefas.concluir(identificador);
    if (resultado.tipo === "falha") {
      return resultado;
    }
    return { tipo: "sucesso", valor: descrever(resultado.valor) };
  }

  pendentes(): readonly string[] {
    return this.#tarefas.pendentes().map(descrever);
  }
}
