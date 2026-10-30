// Dominio estrito: branded type + Resultado (union discriminada, sem excecao).
import { randomUUID } from "node:crypto";

export class ErroDeDominio extends Error {}
export class TituloInvalido extends ErroDeDominio {}
export class TarefaInexistente extends ErroDeDominio {}

declare const marcaTitulo: unique symbol;
export type TituloTarefa = string & { readonly [marcaTitulo]: true };

export type Resultado<T> =
  | { readonly tipo: "sucesso"; readonly valor: T }
  | { readonly tipo: "falha"; readonly erro: ErroDeDominio };

export function sucesso<T>(valor: T): Resultado<T> {
  return { tipo: "sucesso", valor };
}

export function falha<T>(erro: ErroDeDominio): Resultado<T> {
  return { tipo: "falha", erro };
}

export function criarTitulo(bruto: unknown): Resultado<TituloTarefa> {
  if (typeof bruto !== "string") {
    return falha(new TituloInvalido("titulo deve ser texto"));
  }
  const limpo = bruto.trim();
  if (limpo.length < 3 || limpo.length > 120) {
    return falha(new TituloInvalido("titulo deve ter entre 3 e 120 caracteres"));
  }
  return sucesso(limpo as TituloTarefa);
}

export interface Tarefa {
  readonly identificador: string;
  readonly titulo: TituloTarefa;
  readonly concluida: boolean;
}

export function novaTarefa(titulo: TituloTarefa): Tarefa {
  return Object.freeze({ identificador: randomUUID(), titulo, concluida: false });
}

export function concluirTarefa(tarefa: Tarefa): Tarefa {
  return Object.freeze({ ...tarefa, concluida: true });
}

export function descrever(tarefa: Tarefa): string {
  const marcador = tarefa.concluida ? "x" : " ";
  return `[${marcador}] ${tarefa.titulo}`;
}
