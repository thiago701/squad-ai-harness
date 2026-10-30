# E2E com oráculo e nuvem simulada — reference de `especialista-qualidade`

> **Origem:** caso-modelo RadarIAOps (13–14/10/2026; Python 3.13, boto3, moto 5.2, Terraform 1.16). Lições
> `LL-0017` e `LL-0020`. Vale para qualquer stack: o princípio é **testar a resposta de negócio pelo mesmo comando
> que o usuário digita, contra uma nuvem simulada, conferida por um oráculo que não sabe como o código funciona**.

## 1. As quatro peças

| Peça | O que é | Regra que não pode quebrar |
|---|---|---|
| **Fixtures** | o "mundo": repos simulados (Terraform real, tfvars, código) com casos plantados (fila sem DLQ, ARN inexistente, Lambda sem `architectures`) | cada caso plantado existe para uma regra/pergunta nomeada |
| **Gabarito** | o inventário esperado, escrito **à mão** a partir das fixtures (JSON) | nunca gerado pelo código sob teste — senão "100 %" mede o código contra ele mesmo |
| **Oráculo** | função que recebe a **saída** (texto/JSON da CLI) e o gabarito e diz passa/falha com motivo | não importa nada do pacote sob teste; compartilhado entre e2e local e e2e real |
| **Cenário** | `dado / quando (comando real) / então` em YAML, aprovado pelo dono | é o critério de aceite da onda; mudar exige decisão registrada |

Métrica do parser contra o gabarito: **recall e precision** por vínculo (repo, ambiente, ARN, tipo). Meta do caso:
≥ 85 % só o parser; obtido 100 %/100 % — e o número só vale porque o gabarito é independente.

## 2. Nuvem simulada no nível do processo (não só do teste unitário)

Unitário com `@mock_aws` não pega o que o usuário vê. Suba um **servidor** e rode a CLI como subprocesso:

```python
from moto.server import ThreadedMotoServer
srv = ThreadedMotoServer(ip_address="127.0.0.1", port=porta_livre); srv.start()
env = {**os.environ, "AWS_ENDPOINT_URL": f"http://127.0.0.1:{porta_livre}",
       "AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing", "AWS_DEFAULT_REGION": "us-east-1"}
env.pop("AWS_PROFILE", None)              # nunca deixar o profile real vazar para o teste
subprocess.run([sys.executable, "-m", "app.cli", "achados", "--json"], env=env, capture_output=True, check=False)
```

- `AWS_ENDPOINT_URL` (SDKs atuais) redireciona **todos** os serviços sem mudar o código de produção.
- Crie as tabelas com **o mesmo esquema do IaC** (ex.: projeções de GSI lidas do módulo Terraform), senão o teste
  passa com um índice que a produção não tem.
- O que o moto não implementa (ex.: `appconfig:ListApplications`) → stub explícito e comentado; anote o gap.
- O que esse nível achou no caso-modelo e o unitário não: **traceback** quando o serviço de config não existe
  (antes do `apply`) → virou mensagem amigável + exit 1 e um teste "sem Traceback no stderr".

## 3. Fakes gravados para APIs externas (GitHub e afins)

Em vez de mock por chamada, um **servidor fake que responde as mesmas rotas** a partir das fixtures:
listagem paginada com header `Link` (por página pequena, para exercitar a paginação), árvore recursiva, blobs em
base64, e os casos que o filtro precisa barrar (arquivado, fork, outro dono, repo fora do escopo).
Teste também o **hostil**: `Link` apontando para fora da API → recusado; owner com `../` → recusado; token nunca em
`repr`/erro. Para serviços de descoberta (Resource Explorer), um fake com `existe(arn, regiao)` e
`por_tag(chave, valor)` alimentado pelo gabarito.

## 4. Contrato de feature planejada (skip, não fail)

Enquanto a feature não existe, o comando responde **código e texto estáveis** (ex.: exit 2 + "chega na Onda 2").
- o e2e **local** afirma o contrato (garante que ninguém quebrou a superfície);
- o e2e **real** (contra a conta) detecta o contrato e faz `pytest.skip` com o motivo — vermelho só quando a
  feature existe e responde errado.
Quando a onda entra, o teste do contrato é **substituído** pelo teste do oráculo — não apagado em silêncio.

## 5. Infra como código também tem e2e barato

- `terraform test` com `mock_provider` para contratos do plan (tags obrigatórias, nomes, políticas IAM).
  Valores *unknown* no plan (ex.: `jsonencode` de policy com ARN computado) → asserte sobre o `local`/variável
  conhecida, não sobre o atributo computado.
- Teste da **limpeza** com a nuvem simulada: crie recursos com e sem tag, rode a varredura, confira que só os do
  projeto aparecem e que nada de outro projeto é tocado (colisão de nomes entre serviços é bug real).

## 6. Pirâmide do caso-modelo (referência de proporção)

| Nível | Qtde | Custo | Pega |
|---|---|---|---|
| unitário (parser, chaves, validador, limpeza) | ~180 | ms | lógica, bordas, segurança do validador |
| cadeia sem AWS (fake GitHub → parser → gabarito) | 7 | s | integração real dos módulos |
| e2e CLI processo + moto server | 12 | s | UX, códigos de saída, mensagens, contrato |
| `terraform test` (mock provider) | 5 | s | tags, IAM, nomes |
| e2e real (conta do dono, via runbook) | 3 cenários | min, centavos | o que nenhuma simulação vê (IAM real, cotas, latência) |

## 7. Anti-padrões

- **"Gabarito espelho"** — gabarito gerado pela implementação.
- **"Mock que mente o esquema"** — tabela/índice do teste diferente do IaC.
- **"E2E vermelho permanente"** — teste de feature futura falhando e todos aprendendo a ignorar o vermelho.
- **"Profile real no teste"** — `AWS_PROFILE` herdado do terminal apontando para a conta de verdade.
- **"Oráculo que importa o código"** — o verificador usa as funções que deveria verificar.
