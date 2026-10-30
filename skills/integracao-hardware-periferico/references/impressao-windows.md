# Impressão no Windows — spooler, porta virtual, estados e idempotência

> Referência da skill `integracao-hardware-periferico`.

## 1. Anatomia do caminho de impressão

```text
aplicação → API de impressão do SO → driver → spooler → porta → dispositivo
                                                  │
                                       job com estados observáveis
```

O que se pode observar sem hardware: existência do job, tamanho, estado no spooler, erros do
driver, e o arquivo gerado quando a porta é um caminho de disco.

## 2. Configurar a impressora virtual (Fase 0)

1. **Instale o driver oficial do modelo alvo.** Confirme a compatibilidade com o Windows do totem
   antes de prometer a integração — drivers de impressora fotográfica costumam ter suporte oficial
   apenas até versões antigas do Windows, ainda que funcionem em versões mais novas.
2. **Adicione a impressora com uma porta local que aponta para um arquivo/diretório** em vez de
   uma porta USB física. O spooler processa o job normalmente e a saída vai para disco.
3. **Pause a fila** durante os testes de fluxo, para os jobs se acumularem e ficarem inspecionáveis.
4. **Configure o preset de mídia** exatamente como será em produção: tamanho, orientação, margens,
   qualidade. Um preset errado só aparece quando o papel sai cortado.
5. Verifique a **matemática do papel**: 10×15 cm a 300 dpi = 1200 × 1800 px. Se o driver espera
   outra dimensão, ajuste o pipeline — não deixe o driver reamostrar por você.

Inspeção pelo PowerShell (leitura, não escrita):

```powershell
Get-Printer
Get-PrintJob -PrinterName "<nome>"          # Id, JobStatus, Size, SubmittedTime
Get-PrintConfiguration -PrinterName "<nome>"
```

## 3. Mapeamento de estados

| Estado do SO | `PrintJobStatus` | Ação |
|---|---|---|
| Spooling | `SPOOLING` | Aguardar |
| Printing | `PRINTING` | Aguardar; iniciar cronômetro de ciclo |
| Printed / removido da fila sem erro | `DONE` | Concluir sessão |
| Error / PaperOut / Offline | `FAILED` | Health → DEGRADADO/OFFLINE; **não** reenviar automaticamente |
| Paused | `QUEUED` | Manter; avisar o operador |
| Deleted | `CANCELLED` | Encerrar sem retry |

**Job sumiu da fila sem erro** costuma significar sucesso — mas confirme cruzando com o tempo de
ciclo esperado. Job que desaparece em 1 s numa impressora cujo ciclo é dezenas de segundos não
imprimiu.

## 4. Idempotência — a regra que economiza mídia

```python
job_key = f"{session_id}:{n_copia}"          # determinístico

async def submit_idempotente(image_ref, job_key, store):
    existente = await store.get(job_key)
    if existente and existente.status in {DONE, PRINTING, SPOOLING}:
        return existente.job_id               # não reimprime
    job_id = await printer.submit(image_ref, job_key=job_key)
    await store.put(job_key, job_id, QUEUED)
    return job_id
```

Sem isso, um retry de rede, um restart do worker ou um duplo toque no botão produzem uma segunda
foto. Mídia de sublimação é cara e vem em quantidade fixa por kit.

## 5. Fila persistente e reconciliação

```text
tabela print_jobs: job_key (PK) | session_id | image_ref | job_id_so | status | tentativas
                  | criado_em | atualizado_em | erro

no boot do worker:
  SPOOLING/PRINTING órfãos → consultar o SO
     ainda existe?  → manter
     não existe?    → DONE se o tempo de ciclo passou; senão QUEUED (protegido pelo job_key)
```

## 6. Cadência de impressão no evento

Uma impressora fotográfica de sublimação leva, conforme o modo de acabamento, algo entre **~12 e ~26 s**
por foto 4×6 in (10×15 cm) — a Fujifilm ASK-300 é a referência usada aqui, e o número vem da especificação
do fabricante, não de estimativa. Consequências de projeto:

- A **impressora é o gargalo de vazão**, não a IA. Se a geração leva 10 s e a impressão 20 s, a
  fila física cresce ao dobro da velocidade da fila digital — teto de ~2,5 a 5 impressões por minuto.
- Torne a impressão **opcional e explícita** ("quer impressa?"), não automática. Menos mídia
  gasta, fila menor, e o QR atende quem só quer o arquivo digital.
- Mostre ao operador a **fila física** e uma estimativa de espera.
- Planeje o consumo: kits têm quantidade fixa de impressões; acabar mídia no meio do evento é
  falha operacional previsível. Alerta quando restarem 10%.

## 7. O que o teste virtual NÃO prova

Escreva isto no relatório da POC, sem suavizar:

- Cor real impressa (perfil ICC, calibração, mídia) — só com a impressora física.
- Corte, sangria e margens físicas.
- Tempo de ciclo real e comportamento térmico da impressora.
- Fim de ribbon/papel, atolamento, recuperação de erro de mídia.
- Comportamento do driver sob carga de horas.

**Consequência prática:** reserve um dia de homologação com o equipamento físico antes do primeiro
evento pago. A integração virtual reduz esse dia de "descobrir tudo" para "confirmar o que já
funciona" — mas não o elimina.
