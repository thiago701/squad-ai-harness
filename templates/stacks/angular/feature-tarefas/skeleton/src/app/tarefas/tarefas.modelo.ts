// Dominio da feature: tipos estritos + validacao (mesma semantica multistack).
export interface Tarefa {
  readonly identificador: string;
  readonly titulo: string;
  readonly concluida: boolean;
}

export type ResultadoTitulo =
  | { readonly tipo: 'sucesso'; readonly valor: string }
  | { readonly tipo: 'falha'; readonly erro: string };

export function validarTitulo(bruto: string): ResultadoTitulo {
  const limpo = bruto.trim();
  if (limpo.length < 3 || limpo.length > 120) {
    return { tipo: 'falha', erro: 'titulo deve ter entre 3 e 120 caracteres' };
  }
  return { tipo: 'sucesso', valor: limpo };
}

export function novaTarefa(titulo: string): Tarefa {
  return Object.freeze({ identificador: crypto.randomUUID(), titulo, concluida: false });
}
