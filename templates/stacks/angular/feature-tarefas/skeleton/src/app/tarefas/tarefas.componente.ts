// Componente standalone atual: OnPush + signals + control flow novo.
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { TarefasArmazem } from './tarefas.armazem';

@Component({
  selector: 'app-tarefas',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section aria-label="tarefas pendentes">
      <h2>Pendentes: {{ armazem.totalPendentes() }}</h2>
      <form (submit)="criar($event, campo.value); campo.value = ''">
        <label>
          Nova tarefa
          <input #campo name="titulo" required minlength="3" maxlength="120" />
        </label>
        <button type="submit">Criar</button>
      </form>
      @if (armazem.erro(); as mensagem) {
        <p role="alert">{{ mensagem }}</p>
      }
      <ul>
        @for (tarefa of armazem.pendentes(); track tarefa.identificador) {
          <li>
            {{ tarefa.titulo }}
            <button type="button" (click)="armazem.concluir(tarefa.identificador)">
              concluir
            </button>
          </li>
        } @empty {
          <li>(sem pendencias)</li>
        }
      </ul>
    </section>
  `,
})
export class TarefasComponente {
  protected readonly armazem = inject(TarefasArmazem);

  protected criar(evento: Event, titulo: string): void {
    evento.preventDefault();
    this.armazem.criar(titulo);
  }
}
