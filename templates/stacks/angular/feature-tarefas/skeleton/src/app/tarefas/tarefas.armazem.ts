// Store de feature com signals: estado imutavel, derivacoes via computed.
import { Injectable, computed, signal } from '@angular/core';
import { Tarefa, novaTarefa, validarTitulo } from './tarefas.modelo';

@Injectable({ providedIn: 'root' })
export class TarefasArmazem {
  private readonly itens = signal<readonly Tarefa[]>([]);
  readonly erro = signal<string | null>(null);

  readonly pendentes = computed(() => this.itens().filter((tarefa) => !tarefa.concluida));
  readonly totalPendentes = computed(() => this.pendentes().length);

  criar(tituloBruto: string): void {
    const resultado = validarTitulo(tituloBruto);
    if (resultado.tipo === 'falha') {
      this.erro.set(resultado.erro);
      return;
    }
    this.erro.set(null);
    this.itens.update((atuais) => [...atuais, novaTarefa(resultado.valor)]);
  }

  concluir(identificador: string): void {
    this.itens.update((atuais) =>
      atuais.map((tarefa) =>
        tarefa.identificador === identificador ? { ...tarefa, concluida: true } : tarefa,
      ),
    );
  }
}
