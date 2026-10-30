# {{project_name}} — feature Angular 22 (overlay MITR)

Feature standalone atual: OnPush, **signals** (store), `computed`, control flow
`@for/@if/@empty` com `track`, acessibilidade (`role="alert"`, labels) e specs.

## Composicao sobre um workspace
```bash
ng new meu-app --defaults   # workspace base
cp -r src/app/tarefas <workspace>/src/app/
# adicionar TarefasComponente ao roteamento/app raiz
ng test --watch=false && ng build
```
