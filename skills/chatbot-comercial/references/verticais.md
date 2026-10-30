# Vertical-packs

Um vertical é um **arquivo de dados**, não código. Adicionar um vertical não toca em `app/`.

## Como adicionar um vertical

1. `assets/projeto/verticais/<nome>.json` — o pack.
2. `assets/projeto/dados/<nome>/` — documentos da base (md, txt, csv, json, html, pdf).
3. `assets/projeto/golden/<nome>.json` — ≥30 perguntas reais + negativos.
4. Uma seção neste arquivo, no formato das seções abaixo.

Depois: `CHATBOT_VERTICAL=<nome> make up && make eval`.

## Anatomia do pack

```jsonc
{
  "vertical": "pousada",
  "rotulo": "Pousada / Hotel",
  "persona": { "tom": "...", "instrucao": "... {{ESTABELECIMENTO}} ..." },

  "intencoes": [ { "nome": "...", "palavras": ["..."] } ],   // ORDEM = PRECEDÊNCIA
  "sinonimos": { "cachorro": ["animais", "estimacao", "pet"] },
  "termos_ignorados": ["pousada", "servico", "local"],       // não ancoram resposta

  "ferramentas": [
    { "nome": "consultar_disponibilidade", "efeito": "leitura",
      "intencao": "disponibilidade",                          // QUANDO chamar
      "slots_obrigatorios": ["data_entrada"],
      "slots_padrao": { "hospedes": 2 },
      "slots_por_palavra": { "tipo": { "chale": "Chalé Standard" } } },

    { "nome": "consultar_cardapio", "efeito": "leitura",      // sem código novo
      "intencao": "cardapio", "adapter": "tabela",
      "slots_obrigatorios": ["consulta"],
      "config": { "arquivo": "cardapio.json", "campo_busca": "item",
                  "campos_saida": ["item", "preco"] } }
  ],

  "escalonar_intencoes": ["reclamacao"],
  "escalonar_sem_fonte": true,
  "recusas":        ["frase que entra no prompt de sistema"],
  "padroes_recusa": [ { "regex": "...", "motivo": "..." } ],  // determinístico
  "captura_lead": {
    "intencoes_que_geram_lead": ["..."],
    "qualificacao": { "quente": ["data_entrada", "hospedes"],
                      "morno":  ["data_entrada"], "padrao": "frio" }
  },
  "kpis": ["..."],
  "mensagens": { "sem_fonte": "...", "escalonamento": "...", "recusa": "..." }
}
```

### O que é declarativo (e por que isso importa)

`intencao` + `slots_obrigatorios` no pack fazem o **binding** intenção→ferramenta. Sem isso,
`app/agente.py` precisaria de um `if intencao == "disponibilidade"` por vertical, e a
promessa de "vertical novo sem tocar no núcleo" seria falsa — como de fato era, até uma
auditoria apontar.

`adapter: "tabela"` cobre ferramenta de consulta sobre arquivo (`cardapio.json`,
`planos.csv`, `servicos.json`) **sem código novo**. Só precisa de `_f_<nome>` no núcleo quem
integra com o sistema do cliente — PMS, agenda, ERP —, e aí o código é a fronteira, não o
núcleo.

`qualificacao` lista os campos que cada nível exige. Antes era prosa que o código ignorava;
configuração morta é pior que configuração ausente, porque mente.

### Seis regras que valem para todo vertical

1. **Ordem das intenções é precedência.** Empate de acertos vai para quem vem primeiro.
   Da mais específica (`reclamacao`, `grupo_evento`) para a mais genérica (`disponibilidade`).
2. **Casamento é por prefixo com fronteira de palavra.** `quarto` casa `quartos`; `cao` não
   casa `recep`**ção**. Inclua plurais irregulares de `-ão` à mão: `acomodação` **e**
   `acomodações`, `cão` **e** `cães`.
3. **`recusas` é para o prompt; `padroes_recusa` é para o código.** Prompt convence, regex
   garante. O que não pode escapar vai nos dois.
4. **`efeito` da ferramenta é contrato de segurança.** `escrita_irreversivel` nunca é
   executada pelo agente — vai para humano. Confirmar reserva, cobrar, cancelar, dar alta:
   nada disso é do bot.
5. **`sinonimos` mapeia o vocabulário do cliente para o da base.** O hóspede diz "cachorro",
   o regulamento diz "animais de estimação". Sem esse mapa o RAG erra por léxico, não por
   falta de conteúdo.
6. **`termos_ignorados` não é opcional.** O nome do estabelecimento, "pousada", "clínica",
   "serviço" aparecem em todo documento. Se ancorarem, "tem serviço de babá?" casa com
   qualquer coisa e o agente responde sobre traslado — aconteceu.

---

## Estado dos packs

| Vertical | Pack executável | Documentado |
|---|---|---|
| `pousada` | ✅ `verticais/pousada.json` + 7 documentos + golden de 40 perguntas | ✅ |
| `restaurante` `clinica` `academia` `imobiliaria` `oficina` `salao` | — | ✅ abaixo |

Os seis estão especificados aqui com persona, intenções, ferramentas, recusas, lead e KPIs —
o suficiente para virar JSON numa sessão. Não vêm prontos de propósito: **golden set precisa
de pergunta de cliente real.** Trinta perguntas inventadas por vertical dariam cinco métricas
excelentes e sem significado — exatamente o que a `disciplina` existe para impedir.

---

## pousada — Pousada / Hotel ✅ implementado

Pack: `verticais/pousada.json` · Dados: 7 documentos · Golden: 40 perguntas + 8 negativos.

**Persona.** Recepção virtual. Cordial, objetiva, hospitaleira, frases curtas, trata por você.
Responde só com os trechos; cita a fonte; nunca inventa tarifa, disponibilidade, política de
cancelamento ou condição de pagamento.

**Intenções** (na ordem): `reclamacao`, `grupo_evento`, `pet`, `cancelamento`, `pagamento`,
`checkin`, `cafe`, `localizacao`, `estrutura`, `acomodacao`, `tarifa`, `disponibilidade`.

**Ferramentas.** `consultar_disponibilidade` (leitura), `consultar_tarifa` (leitura),
`criar_pre_reserva` (escrita reversível — gera lead, **não** confirma reserva),
`status_reserva` (transfere para a recepção).

**Recusas.** Desconto/upgrade fora da tabela · confirmar reserva · dado de outro hóspede ·
saúde/medicação · alterar ou cancelar reserva já confirmada.

**Escala.** `reclamacao`, `grupo_evento`, e qualquer pergunta sem fonte.

**Lead.** Gera em `disponibilidade`, `tarifa`, `acomodacao`, `grupo_evento`.
Quente = datas **e** número de hóspedes; morno = um dos dois; frio = preço sem datas.

**KPIs.** contenção · pré-reservas geradas · custo por conversa · perguntas sem fonte ·
tempo até escalonamento.

**Documentos que a base precisa ter.** tarifas · acomodações · políticas (check-in,
cancelamento, pagamento) · estrutura e serviços · localização e como chegar · reservas e
ocupação · `ocupacao.json` (calendário real das ferramentas).

**Armadilha do vertical.** Alta temporada e feriado mudam preço. Se o documento diz "acréscimo
de 40%", o agente **não** deve fazer a conta — ele cita a regra e a recepção fecha o valor.
Cálculo de preço final é `consultar_tarifa`, com dado do PMS, não aritmética do modelo.

---

## restaurante — Restaurante / Delivery

**Persona.** Atendente do salão. Rápida, direta, apetitosa sem exagero. Nunca promete tempo
de entrega que não veio do sistema.

**Intenções.** `reclamacao`, `alergia_restricao`, `status_pedido`, `reserva_mesa`, `cardapio`,
`promocao`, `pagamento`, `delivery_taxa`, `horario`, `localizacao`.

**Ferramentas.** `consultar_cardapio` (leitura) · `consultar_disponibilidade_mesa` (leitura) ·
`status_pedido` (leitura) · `criar_reserva_mesa` (escrita reversível). Fechar pedido e cobrar
**não** são do bot.

**Recusas.** Garantir tempo de entrega · afirmar ausência de alérgeno sem o documento dizer ·
prometer desconto fora da promoção vigente · alterar pedido em preparo.

**Escala.** `reclamacao`, `alergia_restricao` (sempre — risco à saúde), pedido atrasado.

**Lead.** Reserva de mesa e pedido de evento. Quente = data + número de pessoas.

**KPIs.** contenção · reservas geradas · pedidos rastreados sem humano · custo por conversa ·
top pratos perguntados e ausentes do cardápio.

**Armadilha.** Cardápio muda toda semana e é a fonte de erro número um. Reindexação
incremental por sha256 resolve; o que não resolve é cardápio em PDF escaneado — exija
CSV ou o export do sistema de PDV.

---

## clinica — Clínica / Consultório

**Persona.** Recepção da clínica. Acolhedora, precisa, sem jargão. **Nunca** interpreta
sintoma, sugere conduta, opina sobre exame ou estima gravidade.

**Intenções.** `emergencia`, `reclamacao`, `resultado_exame`, `convenio`, `agendamento`,
`preparo_exame`, `especialidades`, `valores`, `horario`, `localizacao`.

**Ferramentas.** `consultar_agenda` (leitura) · `consultar_convenio` (leitura) ·
`criar_pre_agendamento` (escrita reversível). Confirmar, remarcar e cancelar consulta são
humanos — remarcação errada custa uma vaga e um paciente.

**Recusas (as mais duras de todos os verticais).** Qualquer orientação clínica · estimar
diagnóstico · confirmar comparecimento ou dado de outro paciente · entregar resultado de
exame no chat · falar de medicação.

**Escala.** `emergencia` **imediatamente e sem retrieval** — coloque o padrão de emergência
como primeiro `padroes_recusa` do pack. Também `resultado_exame` e `reclamacao`.

**Lead.** Pré-agendamento. Quente = especialidade + convênio + janela de data.

**KPIs.** contenção · pré-agendamentos · taxa de escalonamento por emergência (deve ser
próxima do real, não zero) · perguntas de preparo sem resposta · custo por conversa.

**LGPD.** Dado de saúde é **dado sensível** (art. 11). Consentimento explícito
(`CHATBOT_EXIGIR_CONSENTIMENTO=1`), retenção curta (`CHATBOT_RETENCAO_DIAS=90`), e nada de
sintoma na trilha — `redigir()` precisa de padrões adicionais neste vertical.

---

## academia — Academia / Estúdio

**Persona.** Consultor comercial. Enérgico sem ser insistente. Foco em converter visita.

**Intenções.** `reclamacao`, `cancelamento_plano`, `planos_precos`, `aula_horario`,
`experimental`, `modalidades`, `estrutura`, `congelamento`, `localizacao`.

**Ferramentas.** `consultar_planos` (leitura) · `consultar_grade_aulas` (leitura) ·
`agendar_experimental` (escrita reversível). Cancelamento de plano nunca é do bot — é o
momento de retenção humana.

**Recusas.** Prescrever treino ou dieta · prometer resultado físico · negociar mensalidade
fora da tabela · cancelar plano.

**Escala.** `cancelamento_plano` (sempre — é retenção), `reclamacao`, lesão ou dor.

**Lead.** É o produto principal deste vertical. Quente = agendou experimental.

**KPIs.** contenção · experimentais agendados · **taxa de conversão de lead em visita** ·
custo por lead · top modalidades perguntadas e inexistentes.

**Armadilha.** Base pequena e estável (planos, grade, regras). O erro aqui não é RAG — é
deixar a conversa morrer sem CTA. Toda resposta em intenção comercial deve terminar com
convite para a experimental.

---

## imobiliaria — Imobiliária

**Persona.** Corretor de plantão. Consultivo, faz uma pergunta de qualificação por vez.

**Intenções.** `reclamacao`, `visita`, `busca_imovel`, `financiamento`, `documentacao`,
`condominio_iptu`, `aluguel_regras`, `localizacao`.

**Ferramentas.** `buscar_imoveis` (leitura, catálogo dinâmico) · `consultar_imovel` (leitura) ·
`agendar_visita` (escrita reversível). Proposta, negociação e contrato são humanos.

**Recusas.** Negociar valor · garantir aprovação de crédito · opinar sobre valorização ·
informar dado do proprietário ou do inquilino atual.

**Escala.** Proposta, `reclamacao`, e qualquer conversa sobre contrato assinado.

**Lead.** É o produto. Quente = perfil (tipo, faixa, bairro) + visita agendada.

**KPIs.** contenção · visitas agendadas · leads por faixa de preço · custo por visita
agendada · imóveis perguntados e fora do catálogo.

**Armadilha.** O catálogo muda todo dia — é a única base deste conjunto que **não** deve
morar em documento. Ligue `buscar_imoveis` ao sistema da imobiliária e deixe o RAG só para
regras (documentação, financiamento, condomínio). Indexar catálogo desatualizado é pior que
não responder.

---

## oficina — Oficina mecânica / Auto center

**Persona.** Atendente da oficina. Direta, sem tecnês, transparente sobre o que só o
mecânico pode dizer.

**Intenções.** `reclamacao`, `garantia`, `orcamento`, `agendamento`, `status_servico`,
`servicos_oferecidos`, `horario`, `localizacao`.

**Ferramentas.** `consultar_servicos` (leitura) · `consultar_agenda` (leitura) ·
`status_servico` (leitura, por placa ou OS) · `agendar_avaliacao` (escrita reversível).

**Recusas.** **Diagnosticar defeito pelo relato** · estimar preço de reparo não tabelado ·
prometer prazo de peça · garantir cobertura de garantia sem laudo.

**Escala.** `orcamento` de reparo, `garantia`, `reclamacao`, e qualquer descrição de sintoma
mecânico ("está fazendo um barulho").

**Lead.** Agendamento de avaliação. Quente = veículo + sintoma + janela de data.

**KPIs.** contenção · avaliações agendadas · consultas de status sem humano · custo por
conversa · top sintomas relatados (vira insight comercial).

**Armadilha.** É o vertical com maior pressão para o bot "chutar" um diagnóstico. O padrão de
recusa por sintoma precisa ser largo e testado — coloque pelo menos cinco sintomas comuns nos
negativos do golden set.

---

## salao — Salão de beleza / Barbearia

**Persona.** Recepção do salão. Simpática, ágil, boa em encaixar horário.

**Intencoes.** `reclamacao`, `alergia_quimica`, `agendamento`, `precos`, `servicos`,
`profissional`, `desmarcar`, `horario`, `localizacao`.

**Ferramentas.** `consultar_servicos` (leitura) · `consultar_agenda_profissional` (leitura) ·
`agendar_horario` (escrita reversível) · `desmarcar` → humano (é política de no-show).

**Recusas.** Recomendar química ou coloração pelo chat · garantir resultado de cor · prometer
horário sem confirmar agenda · isentar taxa de no-show.

**Escala.** `alergia_quimica` (sempre), `reclamacao`, `desmarcar` em cima da hora.

**Lead.** Agendamento. Quente = serviço + profissional + horário.

**KPIs.** contenção · horários agendados · **taxa de no-show de agendamento feito pelo bot**
(compare com o do humano — é o número que prova o valor) · custo por agendamento.

**Armadilha.** Preço varia por comprimento de cabelo e por profissional. Publique faixa
("a partir de R$ X") e deixe o valor fechado para a avaliação presencial. Um preço errado
aqui vira reclamação na cadeira.
