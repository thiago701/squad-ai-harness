# Referência — Lambda Managed Instances (LMI)

> Parte da skill `arquiteto-cloud-aws`. Carregue sob demanda quando a pergunta for "Lambda ou EC2 para
> tráfego estável", "como eliminar cold start sem Provisioned Concurrency", "multi-concorrência na
> Lambda" ou "dimensionar capacity provider". Hub: `../SKILL.md`.
> Proveniência: técnica reescrita a partir de `awslabs/agent-plugins` (Apache-2.0), skill
> `aws-lambda-managed-instances`. Nenhum trecho copiado — ver `docs/ATTRIBUTIONS.md`.

## O que é

A função continua sendo Lambda (mesmo handler, mesmo deploy), mas executa em **instâncias EC2 da sua
própria conta**, que a AWS provisiona, atualiza e escala. Você ganha famílias de CPU novas, rede mais
larga e preço de EC2 (inclusive Savings Plans/RI); em troca, perde o scale-to-zero e passa a **rodar
várias invocações ao mesmo tempo no mesmo ambiente de execução**.

## Quando usar (e quando não)

| Sinal | LMI | Lambda padrão |
|---|---|---|
| Tráfego | contínuo e previsível, dezenas de milhões de requisições/mês | em rajadas, com longos períodos ociosos |
| Custo | gasto dominado por duração em volume alto | volume baixo ou esporádico |
| Cold start | inaceitável (capacidade provisionada fica quente; escalar além dela ainda pode atrasar um pouco) | tolerável, ou resolvido por SnapStart/Native |
| Hardware | quer CPU específica, família C/M/R, banda alta | memória/CPU padrão bastam |
| Escala a zero | não precisa | exige |
| Código | thread-safe (Java/.NET/Node) ou Python | não thread-safe e caro de corrigir |

Regra de bolso: só vale olhar LMI quando o gasto mensal com Lambda passa de ~US$ 1.000 **com tráfego
estável**. Abaixo disso, o piso fixo de ambientes mínimos costuma custar mais que a Lambda. Funções
muito curtas (< 100 ms) e carga imprevisível também não ganham. **Sempre apresente a comparação de
custo antes de recomendar** — use a calculadora oficial da AWS com região, runtime, requisições/mês,
duração média, memória e arquitetura; não use estimativas decoradas.

## Posição frente às outras estratégias de cold start

LMI não substitui a matriz da skill `lambda-java-cold-start`; ela entra como mais uma linha:

1. Tráfego em rajadas, SLA tolerante → SnapStart ou GraalVM Native (pagam só o que usam).
2. Tráfego estável + SLA de latência rígido + volume alto → LMI (sem cold start na capacidade mínima).
3. Quer manter escala a zero **e** latência previsível em poucos horários → Provisioned Concurrency
   ou escalonamento agendado de LMI (ver abaixo).

## Dimensionamento inicial (a partir de métricas reais)

Com o Lambda Insights ligado na função atual (peça confirmação antes de anexar a layer — ela pode
mexer em cold start), derive o ponto de partida:

- **Concorrência por ambiente** ≈ metade da duração dividida pelo tempo de CPU por invocação (arredonde
  para baixo). Isso mira ~50% de uso de CPU na concorrência máxima e deixa folga.
- **Memória** ≈ concorrência × (% de memória usada) × memória hoje, limitada ao intervalo 2–32 GB.
  Superestima de propósito (ignora memória-base compartilhada); refine depois.
- **Ambientes mínimos** ≈ concorrência média atual × 2 ÷ concorrência por ambiente, nunca abaixo de 3.

Sem Insights: runtime com a concorrência padrão, 2 GB, 3 ambientes mínimos — e ajuste no teste.

## Escolhas de configuração

- **Família/arquitetura:** Graviton (arm64) por padrão; x86 só se houver dependência nativa. Deixe a
  Lambda escolher o tipo da instância; restringir demais derruba disponibilidade. Em dev/teste, exclua
  famílias caras.
- **Razão memória:vCPU:** 2:1 para CPU-bound; 4:1 para uso geral; 8:1 para memória pesada ou Python.
  Mínimo 2 GB/1 vCPU, máximo 32 GB; a memória precisa ser múltipla da razão.
- **Concorrência por vCPU (padrão):** Node 64, Java 32, .NET 32, Python 16. Para I/O-bound mantenha;
  para CPU-bound use 1 por vCPU.
- **Escala:** ambientes mínimos (padrão 3; em produção não desça disso, pois reduz cobertura
  multi-AZ — em não-prod pode ser 1), teto de vCPUs (controla o limite de custo) e utilização-alvo
  (subir economiza, mas reduz tolerância a picos). A escala dobra em ~5 minutos sem throttle; tráfego
  que mais que dobra nesse intervalo ainda gera 429.
- **Ciclo de vida:** instâncias vivem ~12 h e ambientes ~4 h, depois são trocados pela própria Lambda —
  o código não pode assumir estado de longa duração no ambiente.

## Escalonamento agendado

Para horário comercial, campanha ou janela de batch, use o EventBridge Scheduler chamando a API de
configuração de escala da função para mudar mínimo/máximo de ambientes (cron ou rate, única ou
recorrente). Ele define piso e teto; entre eles a escala continua reagindo a CPU e concorrência.
Armadilha: colocar **mínimo = máximo = 0 desativa a versão**, e ela **não volta sozinha** — agende uma
ação explícita de reativação com valores diferentes de zero antes da demanda.

## Checklist de prontidão do código

Todos os runtimes:

- nada de caminho fixo em `/tmp` — inclua o id da requisição no nome e limpe depois; estime o uso total
  (requisições simultâneas × arquivo por requisição);
- conexões de banco em pool criado fora do handler, nunca por invocação (no Python, total de conexões =
  tamanho do pool × concorrência);
- log sempre com id da requisição, senão a saída intercalada vira ilegível.

Só Java/.NET/Node (o handler é compartilhado entre threads/tarefas):

- sem estado mutável global ou `static` mutável; use coleções concorrentes (`ConcurrentHashMap`);
- estado por requisição em `ThreadLocal` (Java), `AsyncLocal` (.NET) ou `AsyncLocalStorage` (Node);
- bibliotecas e drivers thread-safe; clientes do AWS SDK v2 e pools tipo HikariCP são seguros;
- não alterar variáveis de ambiente durante a requisição;
- Node 22: handlers com callback não são suportados — use `async`; .NET: o runtime não aplica timeout de
  invocação, acompanhe o tempo restante pelo contexto.

Python usa **processos** isolados: globais não são compartilhadas e o código que funciona hoje costuma
funcionar igual. O risco é **memória multiplicada** (ex.: 200 MB × 16 processos ≈ 3,2 GB) — prefira
razão 4:1 ou 8:1 e acompanhe a métrica de memória.

Versões mínimas para observabilidade transparente: Powertools Java 2.8.0, Python 3.23.0, TypeScript
2.29.0, .NET 3.1.0; AWS SDK Java 2.34.0 e X-Ray SDK Java 2.20.0.

Ordem de migração sugerida: comece pelas funções **I/O-bound** (ganham mais com multi-concorrência;
as CPU-bound disputam a mesma CPU).

## Infraestrutura e cutover

1. Duas roles IAM: a de execução (da função) e a de operador (permite ao capacity provider gerenciar as
   instâncias EC2) — privilégio mínimo em ambas.
2. VPC com sub-redes em 3+ AZs e IPs livres; egress para CloudWatch Logs (NAT ou VPC endpoint), senão
   os logs somem.
3. Capacity provider (VPC, limites de escala) → função associada a ele → **publicar uma versão** (sem
   versão publicada nada roda e é isso que dispara o provisionamento).
4. Arquitetura da função e do capacity provider precisam coincidir (arm64 ou x86_64).
5. Validar primeiro fora de produção; **alias ponderado entre função LMI e não-LMI não é suportado**,
   então planeje o desvio de tráfego pela origem da invocação. Compare custo após 1–2 semanas.
6. Nunca encerre as instâncias EC2 à mão: apague o capacity provider.

Disponibilidade: a maioria das regiões comerciais, com exceções (consulte a documentação antes de
prometer região).

## Monitoramento e ajuste

Alarmes recomendados: taxa de throttle > 1% e CPU > 80%. As métricas se dividem em duas dimensões —
**alias** (invocações, erros, throttles, duração) e **versão** (CPU, memória, concorrência por ambiente,
quantidade de ambientes); monte um painel que junte as duas.

| Sintoma | Ajuste |
|---|---|
| Duração subiu vs. Lambda atual | reduzir concorrência por ambiente; checar saturação de CPU/memória; instância maior |
| CPU < 10–20% | subir concorrência ou baixar memória (menos vCPU) |
| CPU > 80% | baixar concorrência ou aumentar vCPU |
| Throttle de CPU persistente | escala manual com utilização-alvo menor (ex.: 25%) |
| Throttle de memória | subir memória, ajustando a razão para manter o número de vCPU |
| Throttle de disco | menos `/tmp` por invocação ou menos concorrência |
| Throttle de concorrência | subir concorrência se há folga; ver se o teto de ambientes/vCPU está limitando |
| 429 ao escalar | subir ambientes mínimos ou baixar utilização-alvo |
| Versão presa em PENDING | aguardar; checar IPs das sub-redes e roles |
| Custo alto com pouco tráfego | o piso de ambientes mínimos está sempre ligado — reavalie Lambda padrão |
| Erros 500 intermitentes | estado compartilhado sem proteção — rever o checklist |

## Armadilhas

- Recomendar LMI sem comparação de custo.
- Esquecer que não há escala a zero: ambiente ocioso continua cobrando.
- Migrar código não thread-safe só porque o cold start incomoda — corrija antes ou fique no SnapStart.
- Mínimo abaixo de 3 em produção.
- Zerar mínimo e máximo esperando recuperação automática.
