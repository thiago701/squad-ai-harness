# Referência — Amazon Location Service: entrada, resolução e validação de endereço

> Parte da skill `arquiteto-cloud-aws`. Carregue sob demanda quando a tarefa pedir mapa, geocodificação,
> formulário de endereço, limpeza de base de endereços ou rota em uma aplicação AWS. Hub: `../SKILL.md`.
> Proveniência: técnica reescrita a partir de `awslabs/agent-plugins` (Apache-2.0), skill
> `amazon-location-service` (referências de entrada e verificação de endereço). Nenhum trecho copiado —
> ver `docs/ATTRIBUTIONS.md`.

## Qual API para qual pergunta

O erro mais comum é usar a API errada para o problema de endereço. São três perguntas diferentes:

| Pergunta | API | Natureza | Devolve |
|---|---|---|---|
| "O usuário está digitando — o que sugerir?" | Autocomplete → GetPlace | síncrona, por tecla | sugestões; depois o lugar completo pelo `PlaceId` |
| "Este endereço digitado resolve? Com que qualidade?" | Geocode | síncrona, 1 endereço | coordenadas, rótulo casado, `MatchScores` (geral e por componente), flag de número corrigido |
| "Este endereço é entregável e está no padrão postal?" | Jobs API (`StartJob`, ação `ValidateAddress`) | **assíncrona, em lote** | veredito postal, granularidade, `Mailable`/`Locatable`, status por componente, endereço padronizado |

Regras que decidem:

- Formulário ao vivo: Autocomplete + GetPlace. Se o usuário envia sem escolher sugestão, Geocode no envio.
  **Nunca** dispare um job por tecla ou por submit — job é para volume.
- Checagem pontual ("resolveu? quão bem?"): Geocode basta; o `MatchScores` já responde sem opt-in.
- Veredito postal, padronização oficial ou limpeza de base inteira: Jobs API. Cobertura **somente EUA, Canadá,
  Reino Unido e Austrália**; para qualquer outro país (inclusive Brasil) a opção é Geocode — registre isso no
  plano antes de prometer "validação postal".
- Busca de estabelecimento/POI (SearchText, SearchNearby, Suggest) **não** substitui validação de endereço:
  devolve lugares, não veredito.

## Armadilhas de entrada (formulário)

1. **Exiba sempre o rótulo do endereço, nunca o título.** O título pode vir com os componentes em ordem
   invertida e não serve para o usuário ler.
2. **O endereço é objeto aninhado**: região, país e demais partes têm campos internos (código e nome). Tratar
   como string plana gera `undefined` silencioso.
3. **Coordenada é `[longitude, latitude]`** (ordem GeoJSON). Inverter coloca o ponto no oceano sem erro.
4. Só dispare Autocomplete a partir de ~3 caracteres, com debounce, e limite o número de resultados.
5. Guarde o `PlaceId` escolhido junto do endereço: evita re-geocodificar e deixa a escolha auditável.

## Jobs API de validação: o que não falha na chamada, falha depois

`StartJob` responde `Pending` mesmo com configuração errada; o job vira `Failed` minutos depois. Checklist
antes de submeter:

- **Papel de execução** na mesma conta, com *trust policy* permitindo o serviço de geolocalização assumir o
  papel (restrinja por conta de origem com condição `aws:SourceAccount`). Só a política de permissões não basta.
- **Versionamento habilitado** nos buckets de entrada e de saída — por isso a leitura exige permissão de
  versão do objeto. Entrada: leitura, listagem e consulta do versionamento. Saída: escrita e aborto de upload
  multipart.
- Entrada em **Parquet** no S3 (limite de 10 GB por arquivo e 1 GB por row-group); divida bases maiores.
- Mantenha um `Id` por registro: volta como `Input_Id` e é a única forma segura de correlacionar saída e entrada.
- Dê `Name` significativo ao job; peça `Position` (coordenadas, só EUA/Canadá/Austrália) ou atributos
  específicos do país apenas se for usar — têm custo adicional.
- Acompanhe por evento (EventBridge) em vez de polling; se precisar de polling, espaçamento de dezenas de
  segundos. Falha de job traz código e mensagens na consulta do job.
- Chamadas da Jobs API usam credencial IAM no servidor — não são chamadas de chave de API no navegador.

## Triagem do resultado (aceitar × revisar × rejeitar)

A saída preserva os campos de entrada com prefixo `Input_` e acrescenta os de resultado com prefixo `Output_`;
registros que não processaram trazem tipo e mensagem de erro **no arquivo**, enquanto o job conclui — varra a
saída por eles. O status por componente usa nome de coluna longo, com a parte `Components_Address_` no meio;
a coluna "curta" que a intuição sugere não existe.

| Decisão | Condição típica |
|---|---|
| **Aceitar** | confiança alta (ou média-alta), granularidade até o número do imóvel, `Mailable`, componentes validados (exato, corrigido, alias ou complementado). Grave o endereço padronizado, não o bruto |
| **Revisar** | confiança média; componente-chave não confirmado (ex.: rua válida, número fora da faixa conhecida). Fila humana ou reenvio corrigido |
| **Rejeitar / recoletar** | confiança baixa; só localidade validada; número ou rua não encontrados; não entregável |

Guarde confiança e granularidade ao lado do endereço aceito — é o que torna a decisão auditável depois.

## Autenticação: chave de API × IAM × Cognito

- **Mapas, Places e Routes sem recurso pré-criado** ("resourceless"): preferíveis — menos infraestrutura e
  permissão mais simples. Geofences e Trackers sempre exigem recurso criado antes.
- **Chave de API** para clientes públicos (navegador/mobile) em Mapas/Places/Routes: lista de ações permitidas
  e recurso do provedor padrão da região. Os nomes de ação têm convenção própria (prefixos `geo-maps:`,
  `geo-places:`, `geo-routes:`); nomes de cliente SDK ou ações IAM legadas com prefixo `geo:` são rejeitados.
  Restrinja por ação e, quando possível, por origem (referer).
- **IAM** para back-end e para a Jobs API; **Cognito** (identity pool) para Geofencing/Tracking no cliente.
- Ao revisar um plano, sempre apresente as duas formas de permissão (IAM e chave de API) e diga qual se aplica.

## Mapa no navegador (MapLibre)

Passe a URL do descritor de estilo diretamente ao construtor do mapa, com a chave na query, em vez de chamar a
API de descritor por código; desligue a validação de estilo para carregar mais rápido. Prefira o cliente
JavaScript empacotado para páginas sem build e os pacotes modulares do SDK para apps com bundler.

## Custo e riscos para o checklist de revisão

- Jobs cobram por registro processado; estime volume antes (P3-CustoBaixo) e deduplique a base antes de enviar.
- Chave de API pública vazada = custo de terceiros na sua conta: restrinja ações, origem e monitore uso.
- Cobertura de validação postal limitada a quatro países: contrato com o produto deve dizer o que acontece
  fora deles.

## Checklist de revisão

- [ ] A pergunta de endereço está mapeada à API certa (digitação, resolução ou validação postal)?
- [ ] Nenhum job é disparado por interação de usuário?
- [ ] País-alvo coberto pela Jobs API, ou plano explícito de usar Geocode?
- [ ] Papel de execução com trust policy e buckets versionados?
- [ ] Triagem aceitar/revisar/rejeitar gravando confiança e granularidade?
- [ ] Rótulo (não título) exibido; coordenadas em `[lon, lat]`?
- [ ] Chave de API restrita por ação/origem; IAM no servidor?
