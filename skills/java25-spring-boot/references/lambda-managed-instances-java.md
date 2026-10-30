# Referência — Java em Lambda Managed Instances (multi-concorrência e thread-safety)

> Parte da skill `java25-spring-boot`. Carregue quando uma função Lambda em Java for avaliada ou migrada para **Lambda Managed Instances (LMI)**: Lambda rodando em instâncias EC2 da sua conta, geridas pela AWS, com **várias invocações simultâneas no mesmo ambiente de execução**. A decisão de estratégia de partida (SnapStart, Native, CRaC) está em `../../lambda-java-cold-start/SKILL.md`; o empacotamento AOT, em `../../aws-lambda-java25-aot/SKILL.md`.
>
> Procedência e licença: ver `docs/ATTRIBUTIONS.md` (colheita de 16/10/2026). Texto reescrito; limites, famílias de instância e preços mudam — confirme na documentação oficial e na calculadora de preços da AWS antes de fixar números.

## 1. A mudança de modelo mental

Na Lambda padrão, um ambiente de execução atende **uma invocação por vez**. Na LMI, o runtime Java carrega a classe do handler **uma vez** e chama o método de tratamento a partir de **várias threads do sistema operacional ao mesmo tempo** — o mesmo contrato de um servidor de aplicação. Tudo que era "seguro por acidente" (campo estático mutável, cache em `HashMap`, buffer reutilizado) passa a ser condição de corrida.

Consequência: migrar para LMI é uma **revisão de concorrência do código**, não só uma troca de configuração. Se a revisão custar mais que a economia esperada, fique na Lambda padrão.

## 2. Quando LMI faz sentido (e quando não)

| Sinal | LMI tende a ganhar | Lambda padrão tende a ganhar |
|---|---|---|
| Tráfego | Contínuo e previsível, volume alto | Em rajadas, imprevisível, longos períodos ociosos |
| Custo | Gasto dominado por duração em escala | Uso baixo ou esporádico (o piso de ambientes sempre ligados pesa) |
| Cold start | Inaceitável e não resolvido por SnapStart/Native | Tolerável ou já mitigado |
| Hardware | Precisa de família/CPU/rede específicas, ou de descontos de EC2 (Savings Plans, Reservadas) | Memória/CPU padrão bastam |
| Escala a zero | Desnecessária | Necessária |
| Código | Já thread-safe, ou barato de ajustar | Cheio de estado estático mutável e caro de mexer |

Regra prática: não recomende LMI sem uma **comparação de custo feita com a calculadora oficial** (região, arquitetura, requisições/mês, duração média, memória). Funções muito curtas e gasto mensal baixo quase sempre saem mais baratos na Lambda padrão. Trate qualquer limiar numérico que ouvir como ordem de grandeza, não como regra.

## 3. Checklist de thread-safety para Java

- [ ] **Sem campo `static` mutável** (contadores, caches em `HashMap`, "último resultado"). Use imutáveis, `ConcurrentHashMap` (com `computeIfAbsent`), `LongAdder`/`AtomicLong` ou estado local ao método.
- [ ] **Clientes do AWS SDK v2, HTTP client e pools** criados **uma vez** (construtor ou bloco estático) e reutilizados — são thread-safe. Conexão de banco **nunca por invocação**: use pool (HikariCP) dimensionado pela concorrência total esperada.
- [ ] **Estado por requisição** em parâmetros ou em `ScopedValue` (preferível no Java 25, ver `virtual-threads-deep-dive.md`); `ThreadLocal` só se herdado de biblioteca, e sempre com limpeza ao fim da invocação — thread reaproveitada vaza contexto do pedido anterior.
- [ ] **`/tmp` é compartilhado** por todas as invocações do ambiente: nome de arquivo com o id da requisição, apagar no `finally`, e estimar o uso total (requisições simultâneas × tamanho por requisição) contra o limite de disco.
- [ ] **Variáveis de ambiente e propriedades do sistema só leitura** durante requisições; mutar `System.setProperty` por pedido contamina os demais.
- [ ] **Bibliotecas auditadas**: drivers, formatadores (`SimpleDateFormat` não é thread-safe; use `java.time`), parsers e caches de terceiros precisam declarar thread-safety.
- [ ] **Logs com o id da requisição** em cada linha (MDC não atravessa threads sozinho); sem isso, o log de invocações concorrentes fica ilegível.
- [ ] **Instrumentação compatível**: observabilidade (Powertools para Java, tracing, SDK) em versões que suportam multi-concorrência — confira a matriz de versões mínimas na documentação oficial antes de migrar.

### Spring Boot em LMI

- Beans singleton **devem ser stateless**; qualquer campo mutável em `@Service`/`@Component` é compartilhado entre todas as invocações. Escopo `request` não existe no handler de Lambda — passe o contexto explicitamente.
- `@Async`, filas internas e caches locais (Caffeine) são seguros se a própria estrutura for thread-safe, mas o cache é **por ambiente** e não compartilhado entre ambientes: não presuma consistência global.
- Se o handler usar virtual threads, o gargalo desloca-se para o pool de conexões e para semáforos, não para threads de plataforma; dimensione o pool pelo teto de concorrência configurado.
- Teste de concorrência obrigatório: dispare N invocações simultâneas contra o handler (JUnit com `ExecutorService`/`CountDownLatch`, ou ferramenta de carga) e compare as saídas com a execução sequencial. Ver `testing-patterns.md` e `../../especialista-qualidade/SKILL.md`.

## 4. Configuração: da métrica ao ponto de partida

Parâmetros que você realmente decide (nomes conforme a documentação da AWS; confirme na versão atual):

- **Concorrência por ambiente** (`PerExecutionEnvironmentMaxConcurrency`): o padrão de Java é por vCPU e funciona para carga dominada por I/O. Para trabalho **CPU-bound**, comece em **1 por vCPU** e suba medindo.
- **Razão memória:vCPU**: 2:1 para CPU-bound, 4:1 para uso geral/misto, 8:1 para memória pesada. Há mínimo e máximo de memória por ambiente; a memória deve ser múltipla da razão.
- **Ambientes mínimos/máximos e teto de vCPU**: mínimo maior que 1 em produção para cobrir mais de uma zona de disponibilidade; teto de vCPU funciona como **freio de custo**.
- **Arquitetura**: `arm64` (Graviton) por preço-desempenho, exceto dependência nativa x86 comprovada; função e provedor de capacidade devem usar a **mesma** arquitetura, senão o deploy falha.
- **Tipo de instância**: restringir só se houver necessidade real de hardware; em dev/teste, excluir famílias caras.

Cálculo de partida (se houver métricas de uso da função atual, por exemplo do Lambda Insights — habilitar a extensão altera a função, então só com confirmação humana):

1. Concorrência alvo ≈ metade da duração dividida pelo tempo de CPU por invocação (mira ~50% de CPU em plena concorrência, deixando folga).
2. Memória ≈ concorrência × uso de memória por invocação, com piso do mínimo da LMI. Superestima de propósito, pois ignora a memória base compartilhada.
3. Ambientes mínimos ≈ concorrência de base × 2 ÷ concorrência por ambiente (folga de ~50%), com piso de 3.

Sem métricas: concorrência padrão do runtime, memória mínima e 3 ambientes; ajuste no teste, nunca em produção às cegas. Para tráfego com padrão conhecido (horário comercial, campanha), ajuste mínimo/máximo **por agenda** (EventBridge Scheduler chamando a API de escala da função). Atenção: mínimo e máximo em zero **desativa** a versão e ela **não volta sozinha** — é preciso uma ação agendada de reativação.

## 5. Operação: sinais e ajustes

| Sintoma | Provável causa | Ajuste |
|---|---|---|
| Duração maior que na Lambda padrão | Concorrência alta demais para a CPU | Reduzir concorrência por ambiente; olhar CPU/memória do ambiente; considerar instância maior |
| CPU abaixo de ~10–20% | Subutilização | Subir concorrência ou baixar a memória (menos vCPU) |
| CPU acima de ~80% | Saturação | Reduzir concorrência ou aumentar vCPU |
| Throttles de CPU | Escala atrás da carga | Escala manual com alvo de utilização menor |
| Throttles de memória | Memória curta | Subir memória, mantendo a razão para preservar o vCPU |
| Throttles de disco | `/tmp` estourando | Menos disco por requisição ou menos concorrência |
| 429 na subida de carga | Tráfego dobrou mais rápido que a janela de escala | Subir ambientes mínimos ou reduzir a meta de utilização |
| Versão presa em pendente | Provisionamento em curso, sub-redes sem IP, papel incorreto | Aguardar; verificar IPs livres e permissões |
| Logs ausentes | Sem saída da VPC | NAT ou endpoint de VPC para CloudWatch Logs |
| Custo alto com pouco tráfego | Piso de ambientes sempre ligados | Reavaliar: Lambda padrão pode ser mais barata |

As métricas se dividem em duas visões (por alias: invocações, erros, throttles, duração; por versão: CPU, memória, concorrência e contagem de ambientes). Monte um painel único com as duas. As instâncias não se encerram pelo console do EC2: remover o provedor de capacidade é o que as destrói.

## 6. Rede, permissões e segurança (resumo)

- As instâncias vivem na **sua VPC**: precisam de NAT ou endpoints de VPC para falar com serviços da AWS (logs, SDK). Sub-redes em 3+ zonas melhoram resiliência. Defina egress mínimo no grupo de segurança.
- Há um papel de **operador** para o provedor de capacidade; mantenha-o com privilégio mínimo e condições, e **não conceda curingas**. Delegação de gestão de instâncias é permissão sensível: revisar com `engenheiro-seguranca`.
- IaC (SAM/CDK) para provedor de capacidade e função fica com `engenheiro-iac` e `engenheiro-devops`.

## 7. Checklist de revisão

- [ ] Comparação de custo feita na calculadora oficial; tráfego estável e gasto que justifiquem o piso de ambientes?
- [ ] Revisão de thread-safety concluída (estado estático, pools, `/tmp`, `ThreadLocal`, bibliotecas, logs)?
- [ ] Teste de concorrência automatizado no CI, comparando com execução sequencial?
- [ ] Arquitetura da função igual à do provedor de capacidade?
- [ ] Concorrência, razão memória:vCPU, mínimos/máximos e teto de vCPU definidos por medição, com plano de ajuste?
- [ ] Papel de operador com privilégio mínimo; rede com saída para logs e serviços necessários?
- [ ] Alarmes em throttles, CPU, memória e concorrência; painel combinando alias e versão?
- [ ] Plano de agenda (se houver) inclui reativação explícita e não deixa a função em zero por engano?
