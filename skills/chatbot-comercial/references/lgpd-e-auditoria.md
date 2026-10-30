# LGPD e auditoria

Leia antes de ligar o bot para o público, e sempre que o cliente for de saúde, educação ou
financeiro.

> Isto é orientação técnica de implementação, não parecer jurídico. Base legal, política de
> privacidade e contrato de operador precisam de advogado. O que está aqui é o que o código
> precisa fazer para que o parecer jurídico seja implementável.

## Papéis

O estabelecimento é **controlador** — ele decide por que trata o dado do cliente dele.
A Neural7 é **operadora** — trata em nome do controlador. Isso implica contrato de operador
(art. 39), e implica que decisões de retenção e base legal são do cliente, não suas. O código
só precisa tornar as duas configuráveis.

## Restrição 5 — nenhum dado sensível em log

Uma função, um ponto de passagem: `app/privacidade.py`.

| Função | O que faz | Onde é obrigatória |
|---|---|---|
| `redigir()` | telefone, e-mail, CPF, cartão, chave PIX → marcador | antes de gravar na trilha, no lead e em qualquer `logger` |
| `hash_contato()` | SHA-256 com sal por tenant, 32 chars | dedupe de lead, consentimento, direito ao esquecimento |
| `mascarar_contato()` | `1199***8888`, `jo***@exemplo.com` | o que o atendente vê no painel |

Regras:

- **O contato nunca é gravado em claro.** Hash para reconciliar, máscara para reconhecer.
- `CHATBOT_SAL_HASH` é **por tenant** e é segredo. Sal compartilhado permite cruzar bases de
  clientes diferentes — troque o valor do `.env.example` antes de subir.
- `redigir()` é idempotente: rodar duas vezes não corrompe.
- Log estruturado carrega `tenant`, `sessao`, `intencao`, `modelo`, `custo` e **contagem** de
  fontes. Nunca o texto da mensagem.

Verificação que vale mais que a intenção — está no smoke do projeto gerado:

```bash
grep -c "<telefone de teste>" servidor.log   # tem que dar 0
```

E no teste: `test_trilha_nao_grava_dado_pessoal`.

## Consentimento e base legal

```bash
CHATBOT_EXIGIR_CONSENTIMENTO=0   # atendimento comum: legítimo interesse / execução de contrato
CHATBOT_EXIGIR_CONSENTIMENTO=1   # dado sensível, marketing posterior, menor de idade
```

Com `=1`, `Servico.responder` só grava lead se houver consentimento registrado. **A conversa
continua sendo atendida** — o que não acontece é a captura comercial. Recusar atendimento por
falta de consentimento é criar um problema onde não havia.

`consentimentos` guarda `(tenant, contato_hash, consentido, base_legal, ts)`. `base_legal`
é texto porque quem preenche é o jurídico do cliente, não o código.

**Dado sensível (art. 11)** — saúde, biometria, origem racial, religião, opinião política,
vida sexual — exige consentimento **específico e destacado**. Na prática, para o vertical
`clinica`: `EXIGIR_CONSENTIMENTO=1`, `RETENCAO_DIAS=90`, e padrões extras em `redigir()` para
sintoma e nome de medicamento.

## Retenção e eliminação

| Operação | Onde | Quando roda |
|---|---|---|
| Expurgo por prazo | `Lgpd.expurgar()` · `POST /api/lgpd/expurgo` | cron diário no host |
| Direito à eliminação (art. 18, VI) | `Lgpd.esquecer(hash)` | pedido do titular |

```cron
0 3 * * * curl -fsS -X POST -H "X-Painel-Token: $TOKEN" http://127.0.0.1:8080/api/lgpd/expurgo
```

`RETENCAO_DIAS=180` é o default. Menos que isso quebra o M4 (a curadoria precisa de histórico
para descobrir o que o bot erra); mais que isso vira passivo. Para saúde, 90.

Nota honesta: `esquecer()` remove lead e consentimento. A trilha de interações é **anonimizada
por construção** (texto redigido, sem identificador direto), o que é o que sustenta mantê-la
para auditoria depois da eliminação do lead. Se o cliente exigir remoção total, some
`DELETE FROM interacoes WHERE sessao = ?` — e documente a decisão, porque ela apaga evidência.

## Trilha de auditoria — o que fica de cada interação

| Campo | Por quê |
|---|---|
| `ts`, `tenant`, `sessao`, `correlacao`, `canal` | rastrear e correlacionar com o log do canal |
| `intencao` | entender a distribuição real da demanda |
| `pergunta` (redigida) | reproduzir o caso |
| `contexto` (ids dos chunks) | **saber exatamente o que o modelo viu** |
| `resposta` (redigida) | o que o cliente recebeu |
| `fontes` | procedência — o coração da restrição 4 |
| `modelo`, `tokens_entrada`, `tokens_saida`, `custo_brl` | custo e escolha de roteamento |
| `latencia_ms` | latência do **turno**, que é o que o cliente sente |
| `escalonado`, `sem_fonte`, `recusado` | qualidade e segurança |

`contexto` é o campo que a maioria dos projetos esquece e é o que responde a pergunta que o
auditor faz: *"com base em quê o sistema disse isso?"*. Sem ele, a trilha é anedota.

Exportação para auditor externo: `exportar_trilha(conexao, tenant, destino)` → JSONL.

## Decisão automatizada (art. 20)

O bot **não** decide nada sobre o titular: não aprova crédito, não confirma reserva, não
cancela plano, não nega garantia. Toda ação irreversível é `escrita_irreversivel` e vai para
humano. Isso não é só boa prática — é o que evita o direito à revisão do art. 20 virar
processo operacional.

O M4 tem o mesmo desenho: **nenhuma mudança na base de conhecimento acontece sem aprovação
humana identificada**. `aplicar()` levanta `AprovacaoAusente`, `aprovar()` exige
`aprovado_por`, e o nome fica na trilha e na versão. Rollback é `POST /api/versoes/<id>/rollback`.

## Segurança operacional

| Item | Mínimo aceitável |
|---|---|
| `PAINEL_TOKEN` | definido em produção. **Todo `/api/*` exige o token** — inclusive `/api/sessao/<id>`, que devolve a conversa inteira, e `/api/versoes`. Só `/saude` e `/chat` são públicos |
| Ingestão de site (`seed_rag.py --url`) | conteúdo baixado é **dado não confiável**: entra na base como informação, jamais como instrução ao agente |
| Porta | publicada em `127.0.0.1` pelo compose; proxy com TLS na frente |
| CORS do widget | restrito ao domínio do cliente antes de ir a público |
| `WHATSAPP_VERIFICAR_ASSINATURA` | `1` — sempre |
| `CHATBOT_SAL_HASH` | único por tenant, fora do repositório |
| Backup | volume `var/` no rotativo; teste a restauração uma vez |
| Prompt injection | `conversation_core.InputGuard` no envelope + conteúdo de cliente tratado como dado, nunca instrução |

## Checklist antes do primeiro cliente real

- [ ] `.env` com sal próprio, `PAINEL_TOKEN` e tetos de custo definidos.
- [ ] `CHATBOT_RETENCAO_DIAS` combinado com o cliente e escrito no contrato.
- [ ] Cron de expurgo instalado e testado uma vez.
- [ ] `grep` no log de produção por telefone e e-mail de teste → zero.
- [ ] `make verificar` verde, com a tabela do eval publicada no README.
- [ ] Contrato de operador assinado e política de privacidade do cliente mencionando o
      atendimento automatizado.
- [ ] Alguém nomeado para olhar a fila de curadoria toda semana. Sem dono, o M4 não acontece.
