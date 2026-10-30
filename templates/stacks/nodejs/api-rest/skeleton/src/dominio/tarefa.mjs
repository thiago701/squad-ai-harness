// Dominio puro: value objects congelados e erros tipados.
import { randomUUID } from "node:crypto";

export class ErroDeDominio extends Error {}
export class TituloInvalido extends ErroDeDominio {}
export class TarefaInexistente extends ErroDeDominio {}

export function criarTitulo(bruto) {
  const limpo = String(bruto ?? "").trim();
  if (limpo.length < 3 || limpo.length > 120) {
    throw new TituloInvalido("titulo deve ter entre 3 e 120 caracteres");
  }
  return Object.freeze({ valor: limpo });
}

export function novaTarefa(tituloBruto) {
  const titulo = criarTitulo(tituloBruto);
  return Object.freeze({ identificador: randomUUID(), titulo, concluida: false });
}

export function concluirTarefa(tarefa) {
  return Object.freeze({ ...tarefa, concluida: true });
}

export function descrever(tarefa) {
  const marcador = tarefa.concluida ? "x" : " ";
  return `[${marcador}] ${tarefa.titulo.valor}`;
}
