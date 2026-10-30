# Referência — Diagramas de arquitetura AWS (do código ao desenho legível)

> Parte da skill `arquiteto-minimalista`. Carregue sob demanda quando o pedido for **desenhar, documentar ou
> revisar um diagrama de arquitetura** (draw.io/XML ou Mermaid). Hub: `../SKILL.md`.
> Proveniência: técnicas reescritas a partir de `awslabs/agent-plugins` (Apache-2.0), skill
> `deploy-on-aws/aws-architecture-diagram`. Nenhum trecho copiado — ver `docs/ATTRIBUTIONS.md`.

## 1. Dois pontos de partida

| Ponto de partida | Como proceder |
|---|---|
| **Já existe infraestrutura como código** (SAM/CloudFormation, CDK, Terraform) | Varra o repositório atrás de recursos `AWS::*`, constructs e `resource "aws_*"`; extraia serviços, fronteiras (VPC, sub-redes) e **direção do fluxo de dados**. Mostre a lista descoberta ao humano e **confirme antes de desenhar**. |
| **Ideia ainda no papel** | Faça poucas perguntas (3 a 5): objetivo, serviços previstos, escala, segurança, padrão de tráfego. Proponha serviços e fluxo, itere, só então desenhe. |

Se não houver IaC, procure tecnologias fora da AWS (Dockerfile, broker de mensagens, banco, framework de ML) e
represente-as com ícones genéricos rotulados — em arquitetura mista, ícone AWS só para serviço AWS.

## 2. Escopo: desenhe só o que está no fluxo (alinha com P3)

- Inclua apenas serviços que o humano citou ou que são essenciais ao caminho do dado.
- **Não** acrescente por conta própria preocupações transversais (IAM, KMS, CloudTrail, bucket de logs).
  Se pedidas, ficam num grupo tracejado "serviços auxiliares" **sem setas e sem numeração**.
- Os transversais típicos são só observabilidade e identidade (CloudWatch, CloudTrail, X-Ray, IAM). Todo
  outro serviço é primário: precisa de pelo menos uma seta e de um passo numerado.
- No máximo 1 ou 2 pontos de decisão por diagrama; seta tracejada só para falha/contingência.

## 3. Onde cada serviço mora

| Serviço | Posição no desenho |
|---|---|
| Balanceador, NAT, bastion | Sub-rede pública |
| EC2, contêineres, Lambda em VPC, banco relacional, cache | Sub-rede privada |
| Transit Gateway, gateway de VPN | Nível da VPC, fora das sub-redes |
| DNS, CDN, objeto, identidade, métricas | Fora da VPC |
| Usuários e on-premises | Fora da fronteira da nuvem, com folga visível |

Prefira layout plano; aninhe só em fronteiras reais (região, VPC, AZ, sub-rede).

## 4. Legibilidade

- **Fluxo**: vertical em camadas para usuário→balanceador→computação→dados; horizontal para pipelines (dados, CI/CD).
- **Espaçamento**: folga generosa entre grupos; acima de ~13 serviços, aumente espaços e a página.
- **Setas**: ortogonais, saindo perpendicular à face e se afastando dela; com 2+ saídas do mesmo serviço, use
  pontos de saída distintos; com 2+ entradas no mesmo destino, espalhe os pontos de entrada.
  Para ligar serviços não adjacentes, force pontos intermediários e contorne os blocos — seta nunca atravessa serviço.
- **Passos numerados**: acima de ~7 serviços ou ramificações, marque o início de cada seta com um selo numerado e
  explique cada passo numa legenda lateral com a altura do diagrama.
- **Rótulos**: serviço no ícone (com subtítulo em itálico dizendo o papel); categoria no contêiner, nunca o nome do serviço.
- **Título** sempre presente; entregue também um **texto alternativo** curto (< 100 caracteres) que diga o propósito
  do diagrama, não "diagrama de…".

## 5. Tema claro/escuro

Não fixe cor de fundo no diagrama nem cor branca no rótulo de seta: use cores que se adaptem ao tema, senão o
contraste quebra no modo escuro. Cor do texto de um grupo deve acompanhar a cor de sua borda.

## 6. Validação antes de entregar

1. Arquivo bem-formado (sem `--` dentro de comentário XML; caracteres especiais escapados).
2. Identificadores únicos e descritivos (`lambda-pedidos`, não `cell-47`).
3. Toda origem/destino de seta aponta para um elemento existente.
4. Só formas de biblioteca oficial de ícones — **nunca invente nome de forma**; se não achar, use o genérico rotulado.
5. Sem compressão/base64 no arquivo-fonte (precisa ser diffável em PR).
6. Exportação PNG/SVG/PDF só se o humano pedir e a ferramenta existir; sem ela, entregue o arquivo-fonte e avise.

## 7. Checklist P3 do diagrama

- [ ] Fluxo de dados legível de ponta a ponta sem a legenda?
- [ ] Algum serviço desenhado que ninguém pediu e não está no caminho do dado?
- [ ] Fronteiras (VPC/sub-rede/região) correspondem ao IaC real?
- [ ] Texto alternativo e título presentes?
