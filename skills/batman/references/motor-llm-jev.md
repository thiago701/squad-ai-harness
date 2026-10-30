# Motor do Batman — providers de LLM e criação de modelos JEV

## 1. Providers

O motor do turno é o LLM da sessão; o usuário pode especificar o provider ao ativar:

| Provider | Como ativar | Credencial |
|---|---|---|
| **DeepSeek** (padrão) | sem parâmetro extra | chave do ambiente da sessão (`.env` local, gitignored) |
| **Amazon Bedrock** (corporativo) | "Ative o modo batman com bedrock" ou `SQUAD_LLM_PROVIDER=bedrock` | cadeia default da AWS (env/profile/**IAM role corporativo**) — **nunca no código nem em arquivo commitado** |

**Config única:** `governance/llm-provider.json` (provider/region/modelos por tier
small/pro + pricing) com env vencendo sempre (`SQUAD_LLM_PROVIDER`, `SQUAD_LLM_REGION`,
`SQUAD_LLM_MODEL_SMALL/PRO`). Guia completo de ambiente corporativo:
`docs/bedrock-corporativo.md`.

**Regras de provider:**
- Credenciais só via ambiente/secret store; qualquer credencial vista em arquivo é
  achado 🔴 (registra e escala, nunca usa).
- Roteamento de custo (P3): tarefa barata usa modelo barato; o motor documenta o
  provider/modelo por tarefa no journal.
- Bedrock exige que a região/modelo estejam habilitados na conta — verificação de
  disponibilidade **antes** de assumir; sem assumir nomes de modelo inexistentes.

## 2. Criação de novos modelos JEV (o Batman se aperfeiçoa)

Decisões que o turno repete muitas vezes são candidatas a virar **modelo JEV**
(decisão tipada `Choice`/`Score`/`Noul` + probabilidade + confiança + evidência).
Fluxo obrigatório (mesmo do programa `labs/jev-ecosystem`):

1. **Hipótese:** que decisão repetitiva merece ser tipada? (ex.: "este log de CI é
   flaky ou regressão real?").
2. **Baseline:** medir como o turno decide hoje (LLM) — custo, tempo, acerto contra
   gold set anotado.
3. **Benchmark:** implementar o modelo no padrão JevSim e rodar contra o gold set
   (N≥3) com o **Quality Gate anti-regressão** (P1–P6).
4. **Decisão:** adotar **somente se** o gate provar ganho real (regra absoluta:
   mais rápido porém menos correto é rejeitado). Se não provar, registrar o negativo.
5. **Registro:** modelo novo documentado em `labs/jev-ecosystem/docs/` e citado no
   relatório matinal com a evidência.

## 3. Evidência e racionalidade científica do turno

- **Cada afirmação de melhoria carrega medição:** teste verde, benchmark, métrica
  antes/depois, arquivo:linha. "Deve ter ficado melhor" não entra no relatório.
- **Hipótese explícita:** toda mudança começa com "se eu fizer X, espero Y medido por Z".
- **Falsificação ativa:** o turno tenta derrubar a própria melhoria (roda o cenário
  contrário, aumenta o rigor) antes de reivindicá-la.
- **Amostra e variância:** N≥3 para benchmark; variância registrada; resultado
  inconclusivo é declarado inconclusivo.
