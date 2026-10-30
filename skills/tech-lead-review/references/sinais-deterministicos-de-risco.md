# Sinais determinísticos de risco — régua de code review sem LLM

> **Origin:** `community` — conhecimento destilado de **repowise** (`repowise-dev/repowise`, AGPL-3.0),
> auditado em 2026-07-29 (veredito ✅ APROVAR-COMO-CONHECIMENTO). **Nenhum código, nenhuma
> dependência, nenhum servidor MCP foi importado** — só conceitos, métricas e limiares, que não são
> protegidos por copyright. Ver `docs/ATTRIBUTIONS.md` §22 e o relatório em
> `docs/harvest/2026-07-29-repowise/relatorio-confiabilidade.md`.
>
> **Para que serve:** dar ao `tech-lead-review` (e ao `review`, `clean-code-craftsman`,
> `especialista-qualidade`) uma régua **verificável e barata** para responder "este arquivo é
> perigoso?" e "esta mudança é arriscada?" **antes** de gastar contexto de LLM lendo o diff inteiro.
> Tudo aqui roda com `git`, contagem de linhas e AST — **zero chamada de modelo**.

---

## Por que isto existe (P1 · P3)

Review por leitura pura é caro e não escala: o custo cresce com o tamanho do diff, e o julgamento
varia entre rodadas. Os sinais abaixo são **determinísticos** — mesma entrada, mesma saída — e
servem para **priorizar onde o julgamento caro deve ser gasto**. Eles não substituem o Tech Lead;
eles dizem em que arquivo o Tech Lead deve olhar primeiro.

**Regra de uso:** sinal determinístico **ordena**, humano **decide**. Nenhum número abaixo é
bloqueante por si só — a severidade (🔴/🟡/🔵) continua vindo do `RULES.md` §4 e do Pre-Report Gate
(>80% de confiança).

---

## 1. Os sinais comportamentais (git) — os mais preditivos

Estes vêm do histórico, não do código. A literatura (e a calibração do repowise contra corpus de
defeitos) coloca-os **acima** dos sinais estruturais clássicos.

| Sinal | Definição operacional | Limiar de disparo |
|---|---|---|
| **Co-change scatter** (*shotgun surgery*) | Arquivo acoplado a muitos parceiros que mudam junto | ≥ 3 commits recentes **e** ≥ 8 parceiros distintos |
| **Change entropy** (Hassan) | Difusão da mudança: cada commit que toca `F` arquivos distribui `log2(F)` de entropia entre eles, com decaimento temporal | ≥ 3 commits recentes **e** top 20% de entropia do repo |
| **Ownership risk** (Bird et al.) | *Minor contributor* = autor com < 5% dos commits do arquivo | ≥ 5 commits **e** (≥ 3 minor contributors **ou** nenhum dono com 40%) |
| **Churn risk** (Nagappan-Ball) | Fração de linhas reescritas em 90 dias, normalizada pelo NLOC | ≥ 5 commits recentes, top quartil de churn, churn relativo ≥ 1.0 |
| **Code age volatility** | Código antigo sendo mexido agora (idade mediana das linhas por blame) | mediana ≥ 1 ano **e** modificações recentes; crítico com ≥ 2 anos + ≥ 5 commits em 30 dias |
| **Hidden coupling** | Arquivos que co-mudam consistentemente **sem** aresta de import entre eles | par com co-change persistente e zero dependência declarada |
| **Bus factor** | Nº de contribuidores necessários para somar 80% dos commits | `1` = ponto único de conhecimento |

**Como o Tech Lead usa:** um PR que toca arquivo com *co-change scatter* alto quase sempre está
**incompleto** — pergunte pelos parceiros que não vieram no diff. *Ownership risk* alto significa
que o autor do PR provavelmente **não é o dono** — exija revisor adicional.

**Filtro de ruído importante:** ao computar co-change/entropia, descarte commits que tocam mais de
~30 arquivos (merges, formatação em massa, renomeações) — eles poluem todo o sinal.

---

## 2. Histórico de bugs — o sinal isolado mais forte

**O que conta como bug fix.** Palavra-chave no subject é só o *candidato*. Classifique o diff e
conte **apenas** `code_fix`; descarte `test_only`, `doc_only`, `config_other`, `comment_only`,
`empty` (merges). A distinção comentário-vs-código é **por linha**, não por extensão de arquivo.

> Medida do upstream: **58,7%** dos commits que casam palavra-chave num projeto grande eram ruído.
> Filtrar não muda o poder preditivo, mas muda **a conversa** — "3 fixes reais" convence, "3 commits
> com a palavra fix" não.

**Bug magnet — massa com decaimento (meia-vida 90 dias):**

```
massa = Σ 0.5 ^ (idade_do_fix_em_dias / 90)
bug_magnet = massa >= 3.0
```

Na prática: **4 fixes recentes, ou 3 muito recentes**. Três fixes espalhados por duas semanas somam
~2,9 e **não** disparam — é intencional.

**Contrato de recência (inegociável):** quem exibe `bug_magnet` **tem que exibir a data do último
fix**. Sem âncora temporal, a flag é descartada, não exibida. E o alerta **silencia** quando o
último fix tem mais de 180 dias — um arquivo consertado muito no passado não é notícia hoje.

**Como o Tech Lead usa:** "este arquivo foi corrigido 4 vezes nos últimos 3 meses, a última há 9
dias" é o argumento mais forte que existe para exigir teste de regressão específico no PR.

---

## 3. Risco da mudança (nível de diff, não de arquivo)

Features do modelo JIT (Kamei et al.) — todas obteníveis de `git diff --numstat`:

| Feature | O que é |
|---|---|
| `la` / `ld` | linhas adicionadas / deletadas |
| `nf` | arquivos tocados |
| `nd` / `ns` | diretórios distintos / subsistemas top-level tocados |
| `entropy` | entropia de Shannon da distribuição de churn entre os arquivos do diff |
| `exp` | commits prévios do autor (experiência) — desconhecido pontua neutro |

**Duas leituras que o upstream aprendeu na marra e valem copiar:**

1. **Rankeie, não classifique.** A banda absoluta ("high risk") **não é portável** entre repos: em
   repo de commits grandes, o termo de tamanho domina e dois terços dos commits leem "alto". Use
   **percentil dentro do próprio repo** ("mais arriscado que N% dos commits deste repo") e reporte
   em **tercis**: *abaixo do típico · típico · elevado*.
2. **Direção dos sinais:** tamanho do diff domina; **entropia é risco**; **experiência do autor é
   protetora**. Ganho sobre um baseline só-churn é real mas **pequeno** (AUC 0,772 vs 0,766 no
   estudo do upstream) — trate como ordenador de fila, não como oráculo.

**Sinais de PR cross-módulo** que valem checar explicitamente: quebra de contrato (rota/campo
removido, mudança de tipo, campo novo obrigatório) pesa **mais** que co-change histórico; o primeiro
é "vai quebrar", o segundo é só "pode derivar".

---

## 4. Estrutura de código — limiares concretos

Use como **piso objetivo** do review; nomes e prosa continuam sendo julgamento do `clean-code-craftsman`.

| Marcador | Disparo |
|---|---|
| Complexidade ciclomática alta | CCN ≥ 9 |
| Aninhamento profundo | ≥ 4 níveis de controle |
| Condicional complexa | ≥ 3 operadores booleanos no guard (4 = médio, 5 = alto, 6+ = crítico) |
| Baixa coesão | **LCOM4 ≥ 2** (componentes conexos do grafo método↔campo) |
| God class | ≥ 200 linhas **e** ≥ 15 métodos **e** contém um método-cérebro — tamanho sozinho **não** dispara |
| Método longo | comprimento alto **com CCN ≥ 2** (o piso de CCN exclui literal de dados / tabela) |
| Duplicação | clones cross-file por hash rolling sobre tokens **com identificadores e literais normalizados** — renomear variável não esconde o clone |
| Erro engolido | `catch` vazio, `except:`/`except Exception:` nu, `.unwrap()`/`panic!`, `if err != nil {}` vazio |
| Teste com bloco de asserts gigante | ≥ 15 asserts em corrida ininterrupta |

**Duas válvulas de segurança que evitam falso positivo (copie-as):**

- Classe em que **nenhuma referência a membro** foi detectada reporta **LCOM4 = 1** ("sem sinal"),
  nunca `nº de métodos` — parser fraco não pode virar acusação.
- Marcadores de "obsessão por primitivos" ficam **mudos em módulos com menos de ~60 linhas**.

**Combinação que importa mais que qualquer marcador isolado:** `hotspot` = **alto churn × alta
complexidade**. Complexo e estável é dívida barata; simples e volátil é normal; **complexo e volátil
é onde os bugs moram**.

---

## 5. Lacuna de teste — três condições conjuntas

Não chame de "sem teste" o que é só "sem arquivo de teste com nome parecido". Separe:

- **Lacuna real** (forte): o arquivo **está** no mapa de cobertura e **nada cobre as linhas
  alteradas**.
- **Lacuna presumida** (fraca): não há arquivo de teste com nome correspondente — heurística de
  nome, rotule como palpite.

**Hotspot não testado** (o achado que vale bloquear) exige as **três** condições:

1. é hotspot (flag de churn, **ou** ≥ 8 commits em 90 dias);
2. é centralmente dependido (**≥ 4 dependentes**);
3. cobertura de linha **< 40%**.

Severidade **crítica** com cobertura ≤ 15% **e** ≥ 10 dependentes.

**Contrato "vazio ≠ desconhecido":** só se pode dizer "nada cobre esta mudança" quando o mapa de
cobertura **existe**. Sem mapa, o estado correto é `desconhecido`, e a recomendação é rodar a suíte
inteira. Confundir os dois é como um gate verde mente.

**Seleção de testes impactados:** diffar → descartar arquivos só-deleção → pegar as linhas alteradas
→ retornar os testes cuja cobertura registrada **intersecta** essas linhas. Sempre carimbe a
procedência: `via: cobertura` vs `via: palpite-por-nome`.

---

## 6. Código morto — confiança antes de deletar (N1 do RULES.md)

Deleção é marco crítico. Nunca proponha deletar por "in-degree zero"; componha a confiança:

**Escala por idade (arquivo órfão, sem commits em 90 dias):**

| Último toque | Confiança |
|---|---|
| > 1 ano | 1,00 |
| > 180 dias | 0,90 |
| > 90 dias | 0,80 |
| sem outro sinal | 0,70 |
| arquivo com < 30 dias de vida | 0,55 (provável WIP) |
| ainda recebendo commits | 0,40 |

**Depois disso, a confiança só desce.** Teto de **0,40** quando: há import dinâmico no mesmo
diretório, ou o path contém `config`, `settings`, `env`, `bootstrap`, `startup`, `entrypoint`,
`schema`, `seed`, `migration`, ou está em `scripts/`, `bin/`, `tasks/`.

**"Seguro para deletar" exige as três, juntas:**

1. confiança ≥ 0,70;
2. path sem fator de carga em runtime;
3. nome que **não** casa com dispatch dinâmico: `*Plugin`, `*Handler`, `*Adapter`, `*Middleware`,
   `*Command`, `register_*`, `on_*`, `*_route`, `*_callback`, `*_task`.

**Isento por construção** (nunca acuse): entry points (`__init__.py`, `__main__.py`, `conftest.py`,
`main.go`, `wsgi.py`), rotas de framework (Next.js `page/layout/route`, SvelteKit, Nuxt), arquivos de
teste, código gerado, migrations, símbolos com anotação de framework (`@Component`, `@Service`,
`@RestController`, `@KafkaListener`, fixtures de pytest, rotas Flask/FastAPI, comandos Click/Typer),
árvores vendorizadas.

**Falsos positivos que você vai encontrar:** reflexão e dispatch por string; `__all__` do Python
nunca é lido pelo grafo; barrel/re-export; "usado só em teste" conta como usado; interfaces e classes
abstratas.

---

## 7. Decisões arquiteturais — mineração e frescor

Como transformar "por que isto é assim?" em consulta barata, **sem LLM**:

**Fontes determinísticas, em ordem de autoridade:** ADR versionado (8) > corpo de PR (7) >
arqueologia de commit (6) > CHANGELOG, seções *Changed/Removed/Deprecated/Security* — **nunca
*Added*** (5) > marcador inline `# WHY:` / `# DECISION:` / `# TRADEOFF:` (4) > comentário de código e
README (3).

**Regra de ouro:** fontes **corroboram**, não sobrescrevem. Mesma decisão em ADR + commit = um
registro com duas evidências; o cabeçalho vem da fonte de maior autoridade.

**Gate anti-alucinação (aplicável a qualquer extração assistida por modelo):** a citação tem que ser
**substring literal** da fonte (sem penalidade) ou ter **≥ 0,6 de sobreposição de tokens**
(confiança × 0,85); fora disso é `não verificado` (× 0,6). Campo não fundamentado é **limpo**, não
mantido.

**Frescor (staleness) por arquivo afetado:** arquivo não existe mais → 1,0; arquivo não mudou desde
o registro → 0,0; caso contrário cresce com commits recentes e idade. **+0,3** quando um commit
posterior contém sinal de reversão ("replace", "migrate away", "revert", "drop", "no longer") **e**
compartilha tópico com a decisão. **≥ 0,5 = obsoleta** — pare e reabra a decisão.

**Hotspot não governado** — a pergunta que o Tech Lead deveria fazer todo mês: *quais arquivos estão
no top 25% de churn, com ≥ 3 commits em 90 dias, e **não** são cobertos por nenhuma ADR ativa?*
Essa lista é a fila de ADRs faltantes.

---

## 8. Entrega de contexto no momento certo (padrão de hook)

O padrão mais reaproveitável do upstream não é uma métrica — é **quando** o aviso chega.

**Contrato invariante de hook:** sem chamada de LLM, sem rede, só leitura local; cold start
< ~500 ms; **qualquer falha sai com exit 0 em silêncio** — ambiente quebrado nunca derruba nem
bloqueia o agente.

**Anti-ruído (o que faz a diferença entre útil e ignorado):**

- **um aviso por arquivo por sessão** (ledger atômico contra disparo duplo);
- teto duro de tokens injetados (~400) por evento;
- **três portões obrigatórios** para o aviso pré-edição: ≥ 3 fixes contados **e** último fix dentro
  de 180 dias **e** ainda não avisado nesta sessão;
- no máximo **duas linhas** por arquivo (o histórico de bugs + a decisão que o governa).

Isso encaixa direto no formato de hook do `RULES.md` §3.3 (`perfil: minimal` — avisa, não bloqueia).

---

## 9. Como reportar (o que separa sinal de barulho)

1. **Toda dedução tem que ser atribuível.** Se um score cai, o relatório precisa dizer *qual*
   marcador custou *quanto*. Score opaco não muda comportamento.
2. **Agrupe por categoria com teto.** Sem teto, um arquivo com 40 ocorrências do mesmo problema
   trivial afunda um arquivo com um problema grave. Some por categoria, limite a soma e **escale as
   deduções proporcionalmente** até o teto — assim "isso te custou X" continua honesto.
3. **Percentil > banda absoluta.** Sempre ancore no próprio repo.
4. **Nunca corte silenciosamente.** Se você limitou a top-N, ou pulou arquivos, **diga**. Truncar em
   silêncio lê-se como "cobrimos tudo".
5. **Declare o que é aproximado.** Contagem por símbolo, estimativa de linhas, palpite por nome de
   arquivo — carimbe. Precisão falsa é pior que imprecisão declarada.
6. **Publique a limitação junto com o número.** O upstream publica que, dentro de faixas de tamanho
   parecido, o poder preditivo dos marcadores cai para quase nada (AUC ≈ 0,49) — parte do sinal é
   só "arquivo maior tem mais risco". Um número com limitação declarada sobrevive à auditoria; um
   número sozinho, não.

---

## Quando NÃO usar

- **Repositório novo ou com histórico raso** (`--depth 1`, migração recente): todos os sinais de git
  ficam mudos ou mentem. Use só a seção 4.
- **Como gate automático de bloqueio.** Estes números **ordenam a fila** de review; bloquear PR por
  limiar estatístico gera burla (dividir o commit em três) sem ganho de qualidade.
- **Como substituto do julgamento.** Nenhum marcador aqui lê intenção, contrato de negócio ou
  segurança. Vulnerabilidade continua sendo 🔴 do `engenheiro-seguranca`, independentemente de score.
- **Para justificar deleção sem aprovação humana.** N1 do `RULES.md` continua valendo: confiança
  alta é argumento, não autorização.
