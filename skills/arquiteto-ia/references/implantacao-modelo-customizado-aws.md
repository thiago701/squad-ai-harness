# Implantação de modelo customizado (fine-tuned) na AWS — Bedrock × SageMaker

> Reference do `arquiteto-ia`. Procedência: técnicas absorvidas e reescritas da skill
> `model-deployment` (SageMaker AI) de `awslabs/agent-plugins` (Apache-2.0); ver `docs/ATTRIBUTIONS.md`.
> Trechos marcados **(Squad)** são adaptação nossa, não vêm da fonte.
> Os limites regionais, tamanhos e instâncias abaixo são o retrato da época da leitura (17/10/2026):
> confirme na documentação vigente antes de decidir.

## Quando usar

Você já tem um modelo ajustado com **LoRA** (treinado no SageMaker, via customização serverless) e precisa
colocá-lo em produção. A pergunta não é "como treinar", e sim **onde servir** e **o que checar antes**.
Para avaliar o modelo antes de implantar, ver a skill `ai-evaluation`.

## Passo 0 — Identificar o que foi treinado

Antes de qualquer decisão, levante três fatos a partir do job de treinamento: o **local dos artefatos**
(S3), o **papel IAM** usado e a **região**. O identificador do modelo-base costuma estar numa **tag** do job.
Com ele, classifique a família:

- **Família Nova** (modelos proprietários da AWS): só roda em infraestrutura gerenciada pela AWS.
- **Pesos abertos** (Llama, Qwen, Mistral, DeepSeek, GPT-OSS...): você tem os pesos e pode servir de mais de um jeito.

Armadilha: fine-tuning **completo** (FFT) não segue estes caminhos — o fluxo descrito aqui vale para **LoRA**.
Se a implantação falhar sem motivo claro, confirme o método: a configuração do job (`peft_config` preenchido
= LoRA; nulo = FFT) responde na hora.

## Decisão de alvo

| Critério | Bedrock (importação / modelo custom) | Endpoint SageMaker |
|---|---|---|
| Modelo de cobrança | Por requisição; custo ~zero ocioso | **Por hora de instância**, mesmo ocioso |
| Capacidade | Escala sem planejamento | Você escolhe instância e escala |
| Latência | Boa para demanda variável | Previsível, para carga constante com requisito de latência |
| Controle | Menor | Maior (instância, contêiner, adaptadores) |

Regra prática **(Squad)**: tráfego irregular, time pequeno e sem SLO de latência rígido → Bedrock.
Carga estável e alta, ou necessidade de vários adaptadores no mesmo hardware → SageMaker.
A fonte manda **não recomendar** e deixar a pessoa escolher; na Squad, apresente a matriz com o
custo ocioso explícito e deixe a decisão no **GATE** humano.

## Os quatro caminhos

1. **Pesos abertos → Bedrock (Custom Model Import).** Exige os pesos **já fundidos** (merge do LoRA no base)
   em formato safetensors, com configuração e tokenizador na mesma pasta. Há **teto de tamanho**
   (da ordem de centenas de GB para texto, menos para multimodal) — some os objetos no S3 *antes* de
   começar. Disponível só em algumas regiões. O papel precisa de **relação de confiança com o Bedrock**
   e leitura do bucket do modelo. Gotcha: o construtor do SDK pode assumir a região padrão em vez da do job —
   fixe a região explicitamente.
2. **Pesos abertos → SageMaker, endpoint multi-adaptador.** Pesos **não fundidos**: um componente de
   inferência carrega o modelo-base e outros carregam cada adaptador LoRA. Benefício: vários
   adaptadores compartilham a mesma GPU. Gotchas: na invocação é obrigatório informar **qual componente de
   inferência** chamar; a config do endpoint com papel de execução liga o modo "componentes" e **não**
   deve nomear o modelo nas variantes; versões antigas do contêiner de serving não têm certo ponto de
   entrada assíncrono (use o modo de batching alternativo); modelos com acesso restrito podem ser lidos
   do cache do catálogo do JumpStart, evitando token de hub externo.
3. **Nova → Bedrock (modelo custom).** Caminho gerenciado, hoje restrito a **uma região**.
4. **Nova → SageMaker (endpoint de modelo único).** Sem componentes de inferência: invoca-se o endpoint
   direto. A lista de instâncias aceitas varia por variante (menores aceitam mais opções; as maiores
   exigem as instâncias mais caras), e **instância maior = contexto maior**.

Dimensionamento de partida para pesos abertos no SageMaker, por porte do modelo: pequeno (<3B) numa GPU de
~24 GB; médio (<10B) em 4 GPUs; grande (>10B) em 8 GPUs de memória alta. Ajuste por memória real do
modelo + KV cache; se o componente-base falhar no health check, revise a memória mínima declarada.

## Licença não é detalhe — é um portão

Cada modelo-base traz uma licença própria (Apache-2.0, MIT, licenças comunitárias com cláusulas de uso,
termos de serviço da AWS). Antes de implantar:

1. Descubra a licença do **modelo-base** (não do seu adaptador).
2. Mostre o nome e o link à pessoa e **obtenha aceite explícito**.
3. Só então marque o aceite de EULA no código gerado — e diga em voz alta que foi marcado por causa do aceite.
4. Modelo sem licença conhecida: avise e peça verificação independente; **não prossiga por inércia**.

**(Squad)** Licenças comunitárias (Llama, Gemma, Qwen "agreement") costumam ter limites de uso comercial
ou de escala; registre a decisão no ADR do projeto. Isto conversa com o filtro de licença da skill
`auditoria-skill-externa`.

## Pós-implantação — o que entregar

- **O quê foi criado:** nome, ARN, status.
- **Como invocar:** exemplo mínimo para o alvo escolhido (lembrando o nome do componente de inferência no multi-adaptador).
- **Custo:** instância-hora (SageMaker) × por requisição (Bedrock).
- **Limpeza:** ordem importa no multi-adaptador — apague o componente do **adaptador**, depois o do
  **base**, depois o **endpoint**, esperando cada exclusão terminar. No Bedrock, exclua o modelo importado.

## Problemas comuns (diagnóstico rápido)

| Sintoma | Causa provável |
|---|---|
| "Pesos maiores que o limite" | Modelo excede o teto do Bedrock → use SageMaker |
| Papel não pôde ser assumido | Falta confiança do papel com o serviço Bedrock |
| Acesso negado ao S3 | Papel sem leitura no bucket dos pesos |
| Importação sobe na região errada | Padrão do SDK; fixe a região |
| Erro de módulo do SDK | SDK desatualizado — atualize para a versão mínima exigida |
| Console reclama de campo de modelo ausente | Falha só visual do console; o endpoint funciona |

## Checklist (Squad)

- [ ] Método confirmado como LoRA; modelo avaliado (`ai-evaluation`) antes de subir.
- [ ] Alvo escolhido com custo ocioso explicitado e aprovado no gate.
- [ ] Região, tamanho dos pesos e papel IAM (mínimo necessário) verificados.
- [ ] Licença do modelo-base exibida e aceita por humano; registrada.
- [ ] Plano de limpeza e alarme de custo para endpoint de teste esquecido ligado.
- [ ] Credenciais e ARNs fora do repositório (nunca em notebook versionado).
