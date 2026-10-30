# Concorrência, lease por módulo e RecursionGuard (Onda 4 / I11)

Código: `contracts/concorrencia.py` · contrato canônico: `contracts/concorrencia.json` (`concorrencia-v1`).
Doutrina do `validator.py`: o modelo sugere o despacho, o código decide se é PERMITIDO.

## O que o contrato garante

| Campo | Efeito (valor no contrato) |
|---|---|
| `concorrencia_max` (3) | `validar_concorrencia(ativos)`: `ativos < max` => PERMITIDO; senão AGUARDAR |
| `profundidade_max_delegacao` (3) | `RecursionGuard.entrar`: orquestrador = 0; acima do limite => BLOQUEADO |
| (sem campo) | ciclo de delegação (run já na cadeia) => BLOQUEADO, regra `ciclo_de_delegacao` |
| `lease_ttl_s` (900) | validade do lease; vencido pode ser tomado por outro dono (grava `tomado_de`) |
| `modulos_exclusivos` | `memory/`, `governance/registry/`, `.claude/pipeline/`: um escritor por vez |
| `sem_progresso_apos_s` (600) | a cada janela inteira sem novo marco, +1 ocorrência de `sem_progresso` |
| `escalonar_apos_sem_progresso` (2) | com essas ocorrências seguidas o status vira `escalonar` |

Sem o arquivo (ou com valor inválido) valem as constantes do módulo; `carregar_contrato()` marca `origem`.

## Como o motor do `squad-pipeline` usa

1. **Antes de despachar**: `validar_concorrencia(ativos)`; em AGUARDAR, espere um retorno e reavalie.
2. **A cada despacho**: `RecursionGuard.entrar(run_id, pai_run_id)`; em BLOQUEADO não despache, devolva
   `status=escalar` com o `motivo`. Ao receber o retorno do subagente, `sair(run_id)`. Sem processo Python
   persistente, passe `profundidade=` explícita (a detecção de ciclo exige a pilha em memória).
3. **Escrita em módulo exclusivo**: `modulo_exclusivo(caminho)` devolve a raiz exclusiva; adquira o lease
   da RAIZ (`adquirir_lease` / `lease adquirir`) antes de delegar a escrita e libere ao fim. NEGADO =>
   não delegue essa escrita agora. Quem renova antes do TTL adquire de novo com o mesmo dono.
4. **A cada retorno de subagente**: `registrar(run_id, marco)` (CLI: `progresso registrar`). Registre um
   marco `despacho` ao despachar, para o relógio ter ponto de partida.
5. **Ao avaliar** (`progresso avaliar`): `sem_progresso` é aviso; `escalonar` (exit 1) => PARAR o run e
   enfileirar decisão humana (gate), sem novo despacho para ele.

## SLI

`evento_sli` monta a linha `sli-v1` completa (13 campos) e `anexar_sli` a acrescenta ao fim de
`memory/sli.jsonl`. Eventos: `sem_progresso`, `escalonamento`, `lease_negado`, `recursao_bloqueada`;
`tool=camada-0/contracts.concorrencia`, `fonte=script:camada-0/concorrencia`, campos desconhecidos `null`.
Pela CLI, `--sli` grava `lease_negado` (lease adquirir) e `sem_progresso`/`escalonamento` (progresso
avaliar); cada ocorrência vira um evento só, mesmo que o motor chame `avaliar` várias vezes.

## CLI

```
python -m contracts.concorrencia lease adquirir|liberar|listar --raiz . --slug <slug> [--modulo M --dono D]
python -m contracts.concorrencia progresso registrar|avaliar --raiz . --slug <slug> --run-id R [--marco T]
python -m contracts.concorrencia validar --ativos N        # concorrencia_max
python -m contracts.concorrencia contrato [--json]
```
Uma linha por chamada (`--json` para máquina). Exit 0 = ok; 1 = NEGADO/AGUARDAR/escalonar; 2 = erro de uso.

## O que NÃO faz

- Não é lock de SO e não vale entre máquinas: o lease é um arquivo cooperativo na raiz do repositório.
- A gravação é atômica (temporário + `os.replace`), mas ler-e-gravar não é: duas aquisições simultâneas
  do mesmo módulo podem ambas "vencer". O motor deve despachar escritas em série por módulo.
- Não impede escrita de quem ignora o protocolo, e não detecta conflito entre pai e filho
  (`memory/` x `memory/sli.jsonl`): por isso o lease é sempre da raiz exclusiva.
- O `RecursionGuard` e o `MonitorProgresso` em memória não sobrevivem ao processo (o monitor persiste
  só com `caminho`, como a CLI faz em `.claude/pipeline/<slug>/progresso.json`).
