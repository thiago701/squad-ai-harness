# Vetor: Fidelity — codigo vs spec (machine-checkable)

Verifica se o codigo entregue **corresponde ao `OPENDESIGN.md`** do projeto: cada
Criterio de Aceite (AC) esta coberto, cada Regra de Negocio (RN) preservada, e nenhum
Non-Goal (NG) vazou para o codigo. **Criterio por grep/teste/ast — nao julgamento.**

## Entrada
- O `OPENDESIGN.md` do projeto (secoes 3 RN, 4 Non-Goals, 5 Criterios de Aceite).
- O diff/codigo da wave recem-construida.

## Protocolo

### 1. ACs cobertas (secao 5 do OpenDesign)
Para cada `AC-N` com sua coluna "Como verificar":
- Rode o comando/teste indicado **OU** faca o grep do simbolo que materializa o AC.
- Marque: ✅ coberta (verificacao passa) · ❌ ausente (nao existe no codigo/teste) · 🟡 parcial.

```
# exemplo: AC-1 "query parametrizada" -> procurar concatenacao proibida
grep -rnE "(SELECT|INSERT|UPDATE).*\" *\+|\+ *\"(SELECT|INSERT)" src/   # deve dar 0 hits
```

### 2. Regras de Negocio preservadas (secao 3)
Para cada `RN-N`: localize a assercao que a defende (teste, validacao no construtor,
invariante de aggregate, regra ArchUnit). RN sem assercao localizavel = 🟡 (invariante
declarada mas nao protegida).

### 3. Non-Goals nao vazaram (secao 4)
Para cada `NG-N`: grep pelo conceito proibido. Se aparecer **sem ADR** que o autorize, e
um achado 🔴 (o escopo vazou).

```
# exemplo: NG1 "sem cache distribuido" -> nao deve haver redis/memcached sem ADR
grep -rniE "redis|memcached|hazelcast" src/    # 0 hits, ou exige ADR-NNN
```

## Saida (formato)

```
FIDELITY @ W<n>
ACs:        AC-1 ✅ · AC-2 ✅ · AC-3 ❌(ausente: sem teste para o limite de volume)
RNs:        RN1 ✅ · RN2 🟡(declarada, sem assercao)
Non-Goals:  NG1 ✅ · NG2 🔴(vazou: 'redis' em src/cache/ sem ADR)
veredito:   NOT-GREEN  (1x 🔴, 1x ❌, 1x 🟡)
```

## Severidade
- ❌ AC ausente / 🔴 Non-Goal vazado → **bloqueante** (sub_task `owner=fix`).
- 🟡 RN sem assercao / AC parcial → **necessario** (proxima wave).

## Anti-padrao
"Parece que cobre" sem rodar o comando. Fidelity e **executavel**: cada veredito tem um
comando/grep citavel ao lado. Sem evidencia, o AC nao conta como coberto.
