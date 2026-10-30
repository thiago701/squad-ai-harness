# Referência — IaC serverless: SAM, CDK e convivência dos dois

> Parte da skill `engenheiro-devops`. Carregue quando a pergunta for **qual IaC usar para Lambda**, como organizar stacks, como testar a infraestrutura ou como migrar de SAM para CDK. O fluxo de pipeline e o canary por alias estão em `lambda-deploy.md`. Hub: `../SKILL.md`.

Procedência e licença: ver `docs/ATTRIBUTIONS.md` (colheita de 13/10/2026). Texto reescrito; valores de cota e flags mudam — confira na documentação oficial da AWS antes de fixar.

## 1. SAM ou CDK: critério de escolha

Os dois geram CloudFormation; a diferença é ergonomia e escala do time, não capacidade.

| Situação | Escolha |
|---|---|
| Projeto novo centrado em Lambda, time pequeno ou novo em IaC | SAM: template curto, próximo do CloudFormation, `sam local` nativo |
| Infra complexa (VPC, vários serviços), laços/condições, bibliotecas internas reutilizáveis | CDK: linguagem de programação, constructs L2, métodos `grant*` |
| Projeto SAM que funciona e não tem dor | Manter SAM; migração sem dor a resolver é custo puro |
| Projeto SAM batendo em limites (sem laço, difícil compartilhar padrão) | Migrar de forma incremental para CDK (seção 3) |

Na dúvida: se o usuário não escolheu, pergunte ou siga o que o projeto já usa. Não imponha o padrão da fonte (que defaulta para CDK) sobre um projeto SAM existente.

## 2. Boas práticas por ferramenta

**SAM**
- Defaults de `Timeout`, `MemorySize`, `Runtime`, `Architectures` e `Tracing` em `Globals`, não repetidos por função.
- Um bloco por ambiente em `samconfig.toml` (`dev`, `prod`) com `parameter_overrides`; nada de ARN ou ID de conta fixo — use `!Ref`, `!GetAtt`, `!Sub`.
- `sam build --use-container` quando houver dependência nativa, para compilar no mesmo ambiente do runtime.
- Prefira `arm64` (Graviton) salvo dependência x86 comprovada.
- Lógica de negócio em funções puras sem SDK da AWS: testa-se sem mock; mocks ficam só no nível do handler.

**CDK**
- Prefira constructs L2 e `grant*` a `PolicyStatement` manual: o menor privilégio sai de graça. L1 só quando o L2 não expõe o recurso.
- Separe **stacks com estado** (tabelas, filas, buckets, barramentos) das **sem estado** (funções, rotas). A stack com estado leva `terminationProtection` e `RemovalPolicy.RETAIN`; a sem estado recebe as referências por propriedade. Assim um deploy de código nunca coloca dados em risco.
- Versione `cdk.context.json` (cache de buscas de VPC/AZ): síntese determinística entre máquinas e CI.
- Nunca fixe conta/região em string; use `this.account` e `this.region` (ou `env` explícito por ambiente).
- `cdk bootstrap` uma vez por conta/região; sem ele o deploy falha.
- Em produção, `cdk deploy` só via pipeline, com `cdk diff` no PR para revisar o que muda antes de aplicar.

## 3. Convivência e migração incremental

SAM CLI aceita qualquer template CloudFormation, inclusive o sintetizado pelo CDK. Caminho de menor risco:

1. Comece com **um recurso de apoio novo em CDK** (tabela, fila, barramento) que as funções SAM consomem.
2. Deixe as stacks SAM existentes intactas, no mesmo `sam build && sam deploy`.
3. Mova stacks de função para CDK uma de cada vez, só quando houver confiança.

Ponte entre as duas pilhas: exportação de saída + importação (`Fn::ImportValue` no lado SAM, `Fn::importValue` no CDK) ou, preferível por desacoplar o ciclo de vida, **parâmetros no SSM Parameter Store** lidos dos dois lados. Cuidado: uma exportação em uso trava alterações no valor exportado.

Teste local de função definida em CDK: `cdk synth`, depois `sam build` e `sam local invoke` apontando para o template em `cdk.out/`. Dá o modelo de constructs do CDK com o teste local do SAM.

## 4. Testar a infraestrutura (CDK)

- Teste de asserção (`aws-cdk-lib/assertions`) roda na síntese, sem tocar na AWS: arquitetura da função, runtime, política IAM esperada, contagem de recursos, `DeletionPolicy: Retain` nos recursos com estado.
- **Teste de ID lógico estável** para recurso com estado: renomear o ID de um construct faz o CloudFormation apagar e recriar o recurso. Uma asserção sobre o ID lógico transforma um incidente de perda de dados em falha de teste. Atualize o ID esperado só em renomeação deliberada, com plano de migração.
- Pirâmide de testes serverless: muito teste unitário (rápido, sem AWS); integração local para formato de evento (`sam local`, precisa de Docker); poucos testes em nuvem, reservados a IAM, rede e integrações reais; E2E mínimo.

## 5. Empacotamento: zip, camadas e imagem de contêiner

- **Camadas**: úteis para código compartilhado e dependências grandes (ex.: biblioteca de observabilidade). Há limite de camadas por função e o tamanho descompactado soma função + camadas; confira os limites vigentes.
- **Imagem de contêiner** quando o pacote estoura o limite do zip, há dependência de SO não disponível no runtime, ou o time já tem pipeline Docker. Contrapartida: cold start-base maior; para imagens grandes, índice SOCI (carregamento sob demanda) reduz o custo.
- Em imagem: multi-stage, imagem-base oficial da AWS para Lambda (já traz o cliente de runtime), tag fixada por versão em produção, `arm64`.
- No SAM a imagem é construída no `sam build` e publicada no ECR no `sam deploy`; sem `docker push` manual.

## 6. Checklist de revisão de IaC serverless

- [ ] Escolha SAM/CDK justificada pelo critério da seção 1 (ou herdada do projeto).
- [ ] Sem conta, região ou ARN fixos; ambientes separados por config, não por cópia de template.
- [ ] Recursos com estado isolados, protegidos e com teste de ID lógico estável (CDK).
- [ ] IAM por `grant*` ou política escopada; nada de `*` em ação e recurso juntos.
- [ ] `diff`/change set revisado no PR antes do deploy; deploy de produção só por pipeline.
- [ ] Rollback definido (alarme + preferência de deploy; ver `lambda-deploy.md`).
- [ ] Segredos em Secrets Manager/SSM, nunca em variável de template.
- [ ] Teste local de evento rodado; teste de asserção da infra no CI.
