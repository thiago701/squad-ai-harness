import { TestBed } from '@angular/core/testing';
import { TarefasArmazem } from './tarefas.armazem';

describe('TarefasArmazem', () => {
  let armazem: TarefasArmazem;

  beforeEach(() => {
    armazem = TestBed.inject(TarefasArmazem);
  });

  it('cria tarefa valida e deriva pendentes por computed', () => {
    armazem.criar('estudar signals');
    expect(armazem.totalPendentes()).toBe(1);
    expect(armazem.erro()).toBeNull();
  });

  it('rejeita titulo invalido com erro visivel', () => {
    armazem.criar('ab');
    expect(armazem.totalPendentes()).toBe(0);
    expect(armazem.erro()).toContain('titulo');
  });

  it('concluir remove das pendentes sem mutar itens', () => {
    armazem.criar('revisar pr');
    const tarefa = armazem.pendentes()[0];
    armazem.concluir(tarefa.identificador);
    expect(armazem.totalPendentes()).toBe(0);
  });
});
