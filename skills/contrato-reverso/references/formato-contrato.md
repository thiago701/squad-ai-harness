# Formato do contrato do consumidor (CDC) — `*.cdc.yaml`

Um arquivo `*.cdc.yaml` por consumidor, numa pasta por API (`contracts/consumidores/<api>/`).
Ele descreve **o que o consumidor precisa**, não o que o backend faz. A verificação caminha
ao contrário da implementação:

```
expectativa do consumidor → contrato publicado (OpenAPI) → configuração do Gateway → backend
```

e executa as chamadas pelo caminho real (`consumidor → API Gateway → Lambda/ECS → dependências`).

## Rodar (de qualquer projeto)

```bash
CR=<skill>/scripts/cr.py          # ~/.claude/skills/contrato-reverso/scripts/cr.py depois de instalada
python $CR iniciar   --raiz .     # projeto novo: rascunho do contrato + verificador do provedor
python $CR verificar --raiz . --nivel rapido        # A+B estáticas, < 1 s
python $CR verificar --raiz . --nivel direcionado   # + C1 (verificador do provedor lê este arquivo)
python $CR verificar --raiz . --nivel auto          # nível escolhido pelo diff (git)
python $CR verificar --raiz . --nivel ampliado --ambiente dev --alvo https://<api>.execute-api.<região>.amazonaws.com/dev
python $CR impacto   --raiz .     # só mostra o nível que o diff exige
python $CR observar  --raiz .     # modo contínuo local (debounce + cancelamento)
python $CR bench     --raiz .     # regressões controladas antes × depois
```

Saída: **0 aprovado · 1 reprovado · 2 inconclusivo** + relatório em `.contrato-reverso/relatorios/<consumidor>.md|json`
(ponha `.contrato-reverso/` no `.gitignore`). Falta de JDK, PyYAML, endpoint ou credencial é **inconclusivo** — nunca aprovado.

## Camadas de evidência (uma não substitui a outra)

| camada | o que comprova | o que NÃO comprova |
|---|---|---|
| A · consumidor ↔ OpenAPI | o contrato publicado promete tudo que o consumidor usa | que a implementação cumpre |
| B · consumidor/OpenAPI ↔ Gateway (SAM) | rotas, autorizador, CORS, formato de payload, limites | o Gateway implantado |
| C1 · provedor in-process | o handler real atende o consumidor, com o Gateway simulado a partir do SAM | Gateway implantado, banco real, ordenação feita pelo banco |
| C2 · replay HTTP | o endpoint implantado atende o consumidor | consumidores e versões não avaliados |

## Formato

```yaml
versao_formato: 1
rascunho: true                        # gerado por `iniciar`: veredito no máximo inconclusivo até revisão
consumidor:
  nome: painel-tarefas-spa
  tipo: navegador | servico          # navegador liga as verificações de CORS
  origem_navegador: https://...
  hipotetico: true|false              # perfil ainda não confirmado pelo dono
  timeout_ms: 8000                    # opcional — só declare se houver evidência
  trata_genericamente: ["5xx", 429]
  leitor:
    ignora_campos_desconhecidos: true # tolerant reader
    enums_fechados: [status]          # switch exaustivo: valor novo QUEBRA
  limitacao: texto que vai para todo relatório
provedor:
  raiz: app
  openapi: app/openapi/openapi.yaml   # opcional: sem ele, a camada A registra A-SEM-CONTRATO-PUBLICADO (risco)
  gateway: {template: app/template.yaml, recurso_api: TaskHttpApi, funcao: TaskFunction}
  #   template: SAM (HTTP/REST), CFN/CDK (arquivo ou pasta cdk.out), Terraform (pasta *.tf ou plan.json)
  verificador_inprocess: {comando: [...], cwd: app, observado: app/target/contrato-reverso/observado-<nome>.json}  # Java
  # verificador_inprocess: {runner: python, fabrica: cdc_fabrica:criar_handler, pythonpath: [src, tests]}       # Python
  # verificador_inprocess: {runner: node, fabrica: "test/cdc-fabrica.mjs#criarHandler"}                         # Node
  suite_ampliada: {comando: [...], cwd: app}
  suite_existente: {comando: [...], cwd: app}   # proteção anterior, sem o verificador (coluna ANTES do bench)
  transversal: [regex, ...]           # opcional: arquivos que ampliam para a suíte completa
ambientes:                            # onde a replay C2 pode rodar (tokens: CDC_TOKEN_<IDENTIDADE>)
  dev: {hosts_permitidos: ["*.execute-api.*.amazonaws.com"], producao: false}
  prd: {hosts_permitidos: [...], producao: true}   # produção: só GET/OPTIONS/HEAD
identidades: [usuario-a, usuario-b]
interacoes:                           # em ordem — é uma jornada, com capturas
  - id: criar-tarefa
    risco: o que quebra para o usuário se isto falhar
    origem: {tipo: documentacao|codigo-cliente|teste-cliente|sdk|exemplo-aprovado|trafego-sanitizado|incidente|openapi-exemplo|hipotese, ref: arquivo/linha}
    requisicao: {metodo: POST, caminho: /tasks/{{captura}}, token: usuario-a, headers: {}, query: {}, corpo: {}}
    resposta:
      status: 201                     # ou lista
      content_type: application/json  # ou lista aceita
      headers: {Nome: valor-ou-lista}
      corpo_vazio: true
      campos:
        nome:
          tipo: string|integer|number|boolean|array|object
          presenca: obrigatoria|opcional   # padrão obrigatoria
          nulo: true|false                 # padrão false — ausência ≠ null
          enum: [...]                      # valores que o consumidor conhece
          formato: date-time
          igual: valor | "{{captura}}"
          eco: campo-da-requisicao
          padrao: regex
          igual_tamanho_de: campo-lista-irmao
          soma_de: [campos irmãos]
          itens: {campos dos elementos}    # arrays
          ordenado_por: {campo: createdAt, ordem: desc}
          todos: {campo: status, igual: TODO}
          contem_capturas: [captura]
    capturar: {captura: campo-do-corpo}
```

**Origem é obrigatória.** Não derive tudo do OpenAPI do próprio backend: ele pode ter o
mesmo erro da implementação. `openapi-exemplo` é aceito, mas o relatório marca como
"mesma fonte do provedor". Sem acesso ao consumidor, diga isso em `limitacao` e use `hipotese`.

## Divergências aceitas (processo de aceite)

Mudança intencional de contrato ou débito conhecido NÃO é silenciado pela automação.
Um humano registra em `divergencias-aceitas.yaml`, na pasta do contrato:

```yaml
aceites:
  - chave: "B:B-CORS-AUSENTE:preflight-criar"   # camada:código:interação (está no relatório)
    justificativa: consumidor real é um BFF; CORS desnecessário até a SPA existir
    responsavel: thiago
    aprovado_em: 2026-10-17
    expira_em: 2026-12-31
    migracao: como e quando o consumidor/provedor converge
```

Aceite vencido deixa de valer; aceite sem achado correspondente é sinalizado como obsoleto.
A ferramenta nunca escreve neste arquivo.

## Mutações do projeto (bench)

`mutacoes.yaml` ao lado do contrato. As de OpenAPI e Gateway são automáticas (derivadas do que o
consumidor usa); aqui entram as que dependem do código:

```yaml
mutacoes:
  - id: java-null-omitido
    tipo: quebra            # quebra | compativel
    alvo: implementacao
    arquivo: app/src/main/java/.../JsonSupport.java
    descricao: null passa a ser omitido (ausência ≠ null)
    trocas:
      - {ancora: "JsonMapper.builder()", antigo: ".addModule(new JavaTimeModule())", novo: "...NON_NULL)"}
```

## Orçamento por nível

`contracts/consumidores/orcamento.json` → `{"segundos": {"rapido": 2, "direcionado": 30, "ampliado": 300}}`.
Estourar não reprova: gera `ORCAMENTO-EXCEDIDO`, que exige justificar a proteção extra ou compensar.
