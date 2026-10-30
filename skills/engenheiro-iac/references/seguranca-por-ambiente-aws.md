# Referência — Segurança por ambiente (dev × prod) na infra AWS

> Quando ler: ao escrever ou revisar Terraform que cria rede, armazenamento, banco, balanceador ou
> papéis IAM na AWS, e ao decidir o que o pipeline precisa barrar antes do `apply`.
> Postura: **seguro por padrão, dimensionado por ambiente**. Dev pode ser mais enxuto para depurar e
> custar menos; produção aplica as fronteiras todas. Qualquer afrouxamento é decisão explícita, nunca omissão.

## 1. Criptografia em repouso e em trânsito

| Componente | Dev | Prod |
|---|---|---|
| Bucket S3 | SSE-S3 (custo e atrito zero) | SSE-KMS com chave gerenciada pelo cliente (trilha de auditoria, controle de rotação, acesso entre contas) |
| RDS/Aurora, DocumentDB, EBS | cifrado, chave gerenciada pela AWS | cifrado, chave do cliente |
| Secrets Manager | chave gerenciada pela AWS | chave do cliente |
| Balanceador e CDN | somente TLS 1.2+ | somente TLS 1.2+, com redirecionamento HTTP→HTTPS |

Em Terraform, cifrar é atributo explícito no recurso (ex.: `storage_encrypted`, bloco de configuração de
SSE do bucket). Deixar o default do provider e "supor" que cifra é a falha que o scanner mais encontra.

## 2. Armazenamento S3

- Bloqueio de acesso público **ligado nas 4 opções**, a menos que o bucket sirva site estático de propósito.
- Política de bucket nega por padrão; propriedade de objetos "dono do bucket aplicado" (sem ACL).
- Conteúdo estático atrás de CDN: o bucket continua **privado** e a CDN o lê por *Origin Access Control*.
  O mecanismo antigo (*Origin Access Identity*) é legado — não use em recurso novo.
- Prod: versionamento e log de acesso ligados (versionamento também salva o bucket de state remoto).

## 3. Rede

- Computação (contêineres, instâncias de aplicação) em sub-rede **privada**; só o balanceador fica em sub-rede pública.
- Banco sem IP público, sempre. Função Lambda só entra na VPC se precisar alcançar recurso privado.
- Saída da sub-rede privada passa por NAT ou por *VPC endpoints*. NAT cobra por hora **e** por GB processado:
  em dev uma única AZ basta (1 pública + 1 privada); em prod use várias AZs e avalie endpoints para S3/DynamoDB
  e para os serviços que mais trafegam, que costumam sair mais baratos do que NAT.

## 4. Grupos de segurança — regra por referência, não por CIDR

| Componente | Entrada | Saída |
|---|---|---|
| Balanceador | 443 da internet | só o SG da aplicação |
| Aplicação | só o SG do balanceador, na porta da app | 443 e o SG do banco |
| Banco | só o SG da aplicação, na porta do banco | nenhuma |

Negar por padrão e abrir o mínimo. `0.0.0.0/0` só no 443 do balanceador público. Referenciar SG por SG
(em vez de faixa de IP) mantém a regra correta quando a infraestrutura escala.

## 5. IAM

- Papéis de tarefa/função com **privilégio mínimo**: ARNs enumerados, condições quando possível, sem `*` em
  recurso nem em ação, salvo o inevitável (ex.: objetos de um bucket exigem o sufixo `/*` no ARN do bucket).
- Acesso entre serviços por papel, nunca por chave de acesso estática.
- O Terraform não cria usuário administrador; administração humana é gerida à parte.

## 6. Segredos

- Credenciais e chaves de API em Secrets Manager (rotação automática, auditoria, compartilhamento entre contas);
  configuração não sensível em Parameter Store. Convenção de nome por ambiente: `/app/{env}/nome`.
- Segredo entra na aplicação **em tempo de execução**; nunca embutido na imagem nem em `.tfvars`.
- Cuidado específico de Terraform: um segredo lido por *data source* ou gerado por recurso **vai para o state**.
  Prefira que a aplicação leia o segredo direto pelo papel IAM e que o Terraform só crie o contêiner do segredo.

## 7. Portões antes do apply (ordem sugerida, falha fecha o pipeline)

1. Testes unitários, se existirem.
2. Análise estática/lint (`terraform fmt -check`, `validate`, linters).
3. Scan de IaC no código **e** no plan em JSON (Checkov ou Trivy; para CDK, regras via Aspects).
4. Detecção de segredos no repositório (git-secrets, truffleHog ou detect-secrets); achado = bloqueia.
5. Plan revisado por humano em produção (princípio "plan é contrato").

Silenciar uma regra do scanner exige comentário com justificativa e dono — nunca supressão global.

## 8. Logs e observabilidade por ambiente (custo versus valor)

| Item | Dev | Prod |
|---|---|---|
| Logs de contêiner | CloudWatch Logs | CloudWatch Logs |
| VPC Flow Logs, logs de acesso do balanceador e do S3 | desligados | ligados (destino S3) |
| Log do banco | só erro | erro + consultas lentas + auditoria |

Log custa. Em qualquer ambiente, **defina retenção nos grupos de log** — grupos sem retenção acumulam para
sempre e viram custo silencioso (em Terraform, `retention_in_days` no recurso do grupo).

## 9. Checklist adicional ao pedir "produção"

- [ ] Multi-AZ em todo serviço com estado
- [ ] Flow Logs, logs de acesso do balanceador e do S3
- [ ] Insights de performance do banco; auditoria exportada para o CloudWatch
- [ ] WAF no balanceador se a aplicação é pública
- [ ] GuardDuty: **recomendar**, não habilitar sozinho (decisão de conta/organização)
- [ ] Scan de IaC verde no plan final

## 10. Custo antes do código

Antes de gerar o Terraform, apresente a estimativa mensal: quebra por serviço, total, premissas (24/7? volume de
requisições? região?) e dicas de otimização. Dimensione para **dev** por padrão e só suba para prod quando o
pedido disser "produção". Preços variam por região e mudam: confira na calculadora/API oficial da AWS, não
fixe valores em código ou documentação.

## Anti-padrões

- Bucket público "só para testar" que sobe para prod junto com o módulo.
- SG com `0.0.0.0/0` em porta de banco ou de administração.
- Grupo de log sem retenção; NAT em todas as AZs de um ambiente de dev.
- Segredo em variável Terraform sem `sensitive`, ou lido para dentro do state sem necessidade.
- Scan de IaC rodando só depois do apply.
