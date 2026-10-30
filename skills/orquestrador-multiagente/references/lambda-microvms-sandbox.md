# Sandbox de agente em AWS Lambda MicroVMs

> **Procedência:** técnicas absorvidas (e reescritas) da skill `aws-lambda-microvms` de
> `awslabs/agent-plugins` (Apache-2.0, commit `fbefb37`). Serviço novo: **confira regiões, cotas e
> nomes de API na documentação oficial da AWS antes de citar números** — os valores abaixo são os
> padrões descritos na fonte, não garantias.

## Quando considerar

Complementa `seguranca-sandbox.md`: aquela decide *qual tecnologia de isolamento*; este arquivo é o
caminho concreto quando a nuvem é AWS e o agente precisa de **sessão longa com estado em memória**.

| Situação | Escolha |
|---|---|
| Sessão de agente/notebook/REPL que dura de minutos a horas e precisa reter estado entre turnos | MicroVM (suspende e retoma com RAM e disco preservados) |
| Executar código não confiável de LLM por tenant, com fronteira de hardware (Firecracker) | MicroVM |
| Servidor que escuta porta (WebSocket, gRPC, TCP) ou precisa de FUSE/eBPF | MicroVM |
| Tarefa curta (< 15 min), acionada por evento, sem estado em memória | Lambda comum |
| Computação contínua além do teto de ~8 h ou kernel/SO customizado | ECS/EKS/EC2 |

Dois recursos: a **imagem** (artefato versionado, gerado de um zip com `Dockerfile` + imagem base
gerenciada) e a **instância** (MicroVM criada a partir de uma versão da imagem). Dois papéis IAM
**separados**: o de build (lê o artefato, grava log) e o de execução (o que o código do agente enxerga
em runtime). Nunca reutilize um pelo outro: o de build costuma ter permissões que o código não
confiável não deve herdar.

## Ciclo de vida e idle

- Estados: `PENDING → RUNNING ⇄ SUSPENDING/SUSPENDED → TERMINATING → TERMINATED`.
- **Ociosidade é medida por tráfego de entrada no proxy.** Um agente que trabalha em segundo plano sem
  receber requisições é contado como ocioso e será suspenso. Para workers, suba o limite de ociosidade
  ou omita a política de idle (o bloco, se existir, exige os três campos).
- Há um teto absoluto de vida por instância, separado da política de idle.
- Não há auto-suspensão de dentro da MicroVM: quem suspende é o plano de controle, por API.
- Ganchos HTTP opcionais (build: `ready`, `validate`; runtime: `run`, `resume`, `suspend`, `terminate`):
  1. Se usar qualquer gancho de runtime, implemente também o `ready`.
  2. Responda 503 rápido quando ainda não está pronto — bloquear a chamada gasta o timeout inteiro.
  3. Sirva os ganchos em `0.0.0.0` e em thread/loop separado do servidor principal, para o `suspend`
     responder mesmo com os workers ocupados.
  4. Ganchos devem ser idempotentes (`suspend` e `terminate` podem ser repetidos).
  5. `run`/`resume` são notificações rápidas; trabalho longo vai para assíncrono.
  6. Defina timeouts explícitos; o padrão é curto.

## Snapshot: tudo que está na memória é compartilhado

Toda instância nasce do **mesmo snapshot** (memória + disco). Efeito para agentes:

- **Unicidade:** UUIDs, sementes de PRNG, tokens e segredos gerados no build viram idênticos em todas
  as instâncias. Gere no primeiro uso ou no gancho `run`; entregue dados por-instância via payload do
  `RunMicrovm` (tenant, sessão, referências a segredos — não o segredo em si).
- **Aleatoriedade:** use CSPRNG do SO (`SecureRandom`, `secrets`, `crypto.randomBytes`, `crypto/rand`,
  `getrandom`) e evite gerador semeado uma vez antes do snapshot. Imagem base própria pode não
  reressemear o OpenSSL na retomada: prefira a imagem base gerenciada.
- **Conexões:** conexões de saída não sobrevivem a `run`/`resume`; todo cliente precisa de timeout e
  reconexão automática. Pool de banco criado no build chega morto.
- **Configuração:** variável de ambiente de build = estática e visível a todos; payload de run =
  por-instância; segredo de verdade = buscar em runtime com o papel de execução (credenciais via IMDSv2).
- **Tamanho:** a memória é restaurada de forma ansiosa e o disco sob demanda; o tempo de retomada
  cresce com o snapshot (a fonte cita ~1 s por 500 MB como ordem de grandeza). Não pré-carregue
  modelos nem buffers enormes no build; use build multi-estágio e limpe caches.
- Snapshots **não são atualizados pelo serviço**: reconstrua a imagem quando a base for atualizada.

## Postura de segurança para código de agente

1. **Papel de execução mínimo.** Sem ele, nem o stdout vai para o log; com ele, escope só o que a
   tarefa precisa (nada de `*`). Trust policy com `aws:SourceAccount` e `aws:SourceArn` contra
   *confused deputy*.
2. **Token de entrada efêmero e restrito por porta.** Validade curta (teto de 60 min; use o mínimo),
   `allowedPorts` explícito, nunca `allPorts` por conveniência. Trate o token como segredo: sem log,
   sem arquivo, sem histórico de shell (argumento de linha de comando aparece em `ps`).
3. **Shell de depuração é exceção, não padrão.** O conector de shell abre PTY dentro do mesmo
   contêiner da aplicação; só anexe quando um humano ou agente de confiança precisar, com token de
   shell separado e curto. Em produção, não anexe.
4. **Capacidades extras do SO** (`ALL`: FUSE, contêineres aninhados, eBPF) ampliam a superfície;
   habilite só com requisito concreto.
5. **Egress.** Por padrão há saída para a internet; para agente que executa código de terceiros,
   restrinja por conector de rede/VPC e allowlist — é o controle contra exfiltração.
6. **Quem chama `RunMicrovm` precisa de permissão para passar conectores de rede**, mesmo no padrão;
   escope o recurso aos conectores realmente usados.
7. **Efemeridade:** uma instância por sessão/tenant e terminar ao fim; versões de imagem antigas
   custam armazenamento, apague as não usadas.
8. PrivateLink existe para o domínio dos endpoints: use quando os clientes estão numa VPC.

## Padrão recomendado (sessão de agente com execução de código)

1. Imagem com gancho `ready` (aquece interpretador/dependências) e `validate` (roda carga de exemplo,
   o que também ajuda a plataforma a pré-buscar as partes quentes do snapshot).
2. Plano de controle cria a instância por sessão, passa `tenant_id`/`session_id` no payload de run e
   mantém o `microvmId` em tabela com TTL.
3. Cada turno: emitir token curto restrito à porta da aplicação → chamar o endpoint → descartar token.
4. Ocioso entre turnos: deixar a plataforma suspender (auto-resume ligado); persistir no gancho
   `suspend` só o que não pode ser perdido.
5. Fim da sessão ou do orçamento: terminar explicitamente; teto de vida como rede de segurança.

## Checklist de revisão

- [ ] Nada único (ID, semente, segredo, token) é criado antes do snapshot.
- [ ] Clientes de rede reconectam sozinhos após `run`/`resume`.
- [ ] Papéis de build e de execução são distintos; execução com privilégio mínimo.
- [ ] Tokens: TTL curto, portas explícitas, nunca logados.
- [ ] Shell e capacidades extras desligados em produção.
- [ ] Egress restrito para código não confiável.
- [ ] Ociosidade medida corretamente para workers sem tráfego de entrada.
- [ ] Teto de vida e limpeza de versões de imagem definidos.
- [ ] Números de cota/região conferidos na documentação oficial.
