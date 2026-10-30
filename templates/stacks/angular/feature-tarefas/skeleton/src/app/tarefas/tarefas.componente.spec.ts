import { TestBed } from '@angular/core/testing';
import { TarefasComponente } from './tarefas.componente';

describe('TarefasComponente', () => {
  it('renderiza, cria pela borda e exibe erro de validacao', async () => {
    await TestBed.configureTestingModule({ imports: [TarefasComponente] }).compileComponents();
    const fixture = TestBed.createComponent(TarefasComponente);
    fixture.detectChanges();
    const host: HTMLElement = fixture.nativeElement;
    const campo = host.querySelector('input') as HTMLInputElement;
    const formulario = host.querySelector('form') as HTMLFormElement;
    campo.value = 'integrar angular 22';
    formulario.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    expect(host.textContent).toContain('integrar angular 22');
    campo.value = 'ab';
    formulario.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    expect(host.querySelector('[role="alert"]')?.textContent).toContain('titulo');
  });
});
