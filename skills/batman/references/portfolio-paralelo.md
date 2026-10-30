# Portfólio paralelo (v3) — vários projetos, N workers, despacho por modelos JEV

> Código: `scripts/batman/portfolio.py` (despachante) + `scripts/batman/jev_portfolio.py`
> (modelos JEV). Testes: `tests/test_batman_portfolio.py`. Config: `scheduler/batman-portfolio.json`.
> A doutrina N0–N3 de `autonomia-graduada.md` e `protocolo-noturno.md` continua valendo.

## 1. Por que

O v2 (`shift.py`) trabalha **um** workspace com **um** job por vez. Com 6 repos na rotina,
a noite rendia um repo e o resto esperava. O v3 trata o portfólio como uma única
fila multi-repo e preenche N workers em paralelo, decidindo cada vaga com JEV.

## 2. Arquitetura

```
batman-portfolio.json ──► preparar(): resolve caminho · detecta stack/unidades · git status (protegidos)
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
        Fila repo A          Fila repo B          Fila repo C      (agenda.Fila, uma por workspace)
              │  bateria/descoberta/subjobs por repo     │
              └──────────► Despachante (1 thread) ◄──────┘
                    para cada vaga livre:
                    Noul admitir → Score pontuar_job → Choice escolher_proximo → Choice rotear_modelo
                                   │
                         ThreadPool (N = Choice decidir_workers)
                    worker: bateria (subprocess) | agente headless (claude -p --model <tier>)
                                   │
                    resultado → fila.concluir · ledger JEV · feitos · journal · N3
```

- **Despachante único:** só ele lê e grava filas, ledger e journal. Os workers apenas executam
  subprocessos e devolvem `(resultado, ok, evidência)`. Não há estado compartilhado mutável entre threads.
- **Paralelo entre repos, serial dentro do repo** (`paralelo_max: 1`): sem commits, dois agentes no
  mesmo working tree misturam diffs e um quebra a bateria do outro. Aumente só para repos com
  partes independentes, e com cautela.
- **Agente headless que não chama `concluir`** conta como falha (igual ao v2) e entra no ledger.

## 3. Modelos JEV

| Modelo | Tipo | Entrada | Saída | Aprende com |
|---|---|---|---|---|
| `pontuar_job` | Score | job, prioridade do repo, histórico | valor × sucesso ÷ √custo | taxa Beta(1,1) e minutos reais por (repo, classe) |
| `escolher_proximo` | Choice | melhor job de cada repo com vaga | (repo, job) + ranking como evidência | — (fair-share e espera) |
| `admitir` | Noul | job, protegidos, repo ativo | executar · verificar · recusar · escalar | — (doutrina + `classificar_decisao`) |
| `rotear_modelo` | Choice | job + admissão | tier `small`/`medio`/`grande` → `--model` | — (P3 custo) |
| `decidir_workers` | Choice | config, demanda, CPUs | nº de workers | — |

Detalhes que importam:

- **Exploração:** bônus UCB1 `0,3·√(2·ln(N+2)/(n+1))` garante que repo/classe pouco vistos ainda
  ganhem vaga; com histórico, quem falha muito perde Score e quem entrega sobe.
- **Estimativa calibrada:** com ≥ 3 amostras, `0,7·média_real + 0,3·declarada` decide se o job
  cabe no tempo que resta (fim do "job de 30 min que leva 90").
- **Peso do repo:** `1/prioridade`. Mesma prioridade = mesmo peso (squad e neural-med intercalam).
- **Anti-inanição:** repo sem worker há 60 min tem o Score efetivo dobrado; nenhum repo fica a noite inteira sem ser atendido.
- **"verificar"** (confiança 0,5–0,8, por exemplo um alvo em `security/`): o job roda e, se terminar
  ok, a bateria do repo é **antecipada** para validar a mudança na hora.
- **Aguardando humano (BLOCKED_HUMANO):** job cujo objetivo pede ação que só o humano faz
  ("Humano instala…", "Após o humano copiar…", "requer humano", "(humano)") é **escalado na 1ª
  admissão**, sem gastar worker, e vai à fila N3 com a ação exata (`jev_portfolio.depende_de_humano`).
  Jobs `det` nunca escalam por texto. Motivo: no turno de 07/10, 186 das 251 execuções LLM do squad
  (74%) foram em jobs desse tipo, que só concluíam "estou bloqueado" e criavam subjobs iguais.
  Proveniência: técnica reescrita do protocolo de status de worker (DONE/BLOCKED — não redespachar
  sem mudar algo) de `obra/superpowers`, `skills/subagent-driven-development/SKILL.md` @8ca22db, MIT.
- **Protegidos:** caminho exato ou prefixo de diretório untracked (`src/novo/`). `*` = git
  indisponível ⇒ só a bateria (fail-safe; nunca "sem proteção").

## 4. Configuração

```json
{
  "workers": 3,
  "modelos": {"small": "haiku", "medio": "sonnet", "grande": "opus"},
  "repos": [
    {"id": "squad-ai-harness", "path": "C:\\...\\squad-ai-harness", "prioridade": 1},
    {"id": "trace2local", "path": "C:\\...\\trace2local", "prioridade": 2,
     "paralelo_max": 1, "bateria": [{"nome": "verify", "cmd": ["mvnw.cmd", "-q", "verify"]}]}
  ]
}
```

## 5. Como usar

| Situação | Comando |
|---|---|
| Ver o que o turno faria (sem executar) | `python scripts/batman/portfolio.py plano` |
| Turno noturno paralelo (Windows, agente headless) | `python scripts/batman/portfolio.py turno --until 08:00` |
| Sessão Claude sem headless | `proximo --n 3 --json` → um subagente por item → `concluir --ws` |
| Acompanhar | `python scripts/batman/portfolio.py status` |
| Reiniciar se morrer | Agendador do Windows: `portfolio.py vigia --inicio 18:00 --until 08:00` a cada 15 min |

## 6. Limites honestos

- O speedup real depende de CPU/RAM (builds Maven em paralelo pesam) e da cota do agente headless;
  `decidir_workers` limita por `CPUs − 1`, mas não mede RAM. Comece com 3 workers.
- A descoberta multi-stack é heurística (sem teste dedicado, arquivo/função longa, TODO). Ela
  **sugere** trabalho; o critério de aceite e o TDD do job é que garantem o valor.
- Em montagens lentas (VM com pasta compartilhada), `git status` e a varredura de repos grandes
  podem levar minutos. Rode o turno no Windows nativo.
