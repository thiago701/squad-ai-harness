// Borda CLI: traduz Resultado em codigo de saida + log JSON (handler central).
import { Tarefas } from "../dominio/colecao.js";
import { ServicoDeTarefas } from "../aplicacao/servico.js";
import type { Resultado } from "../dominio/tarefa.js";

function registrar(nivel: "info" | "erro", mensagem: string): void {
  console.log(JSON.stringify({ nivel, quando: new Date().toISOString(), mensagem }));
}

function apresentar(resultado: Resultado<string>): number {
  if (resultado.tipo === "falha") {
    registrar("erro", resultado.erro.message);
    return 2;
  }
  registrar("info", resultado.valor);
  return 0;
}

export function executar(argumentos: readonly string[]): number {
  const servico = new ServicoDeTarefas(new Tarefas());
  const [comando, ...resto] = argumentos;
  if (comando === "criar") {
    return apresentar(servico.criar(resto.join(" ")));
  }
  if (comando === "concluir" && resto[0] !== undefined) {
    return apresentar(servico.concluir(resto[0]));
  }
  registrar("info", servico.pendentes().join("\n") || "(sem pendencias)");
  return 0;
}
