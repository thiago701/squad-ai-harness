# validacao-veracode · reference — Contexto bancário (perfil `bancario`)

> Parte da skill `validacao-veracode`. Carregue sob demanda. Hub: `../SKILL.md`.
> Normas consultadas em 2026-10 (fontes no fim). Números de requisito e artigo seguem os textos
> oficiais citados — **confira a redação vigente** antes de usá-los como evidência em auditoria.

## 1. Quando usar

Todo repositório que movimenta dinheiro ou dado protegido: conta, cartão, Pix, TED/boleto, crédito,
investimento, Open Finance, ou qualquer dado sob sigilo bancário (LC 105/2001). Use
`--perfil bancario` no pré-scan **e** no gate; no gate de release, acrescente `--release`.
Não rode o perfil bancário em repositório que não é financeiro: nomes como `valor` e `limite`
viram ruído fora desse domínio.

## 2. O que o perfil muda

| Aspecto | `maximo` | `bancario` |
|---|---|---|
| Bloqueia (🔴) | severidade ≥ 3 + CWEs críticos | severidade **≥ 2** + críticos + **CWEs bancários** em qualquer severidade |
| Regras de domínio | — | **15 regras `BK-*`** (dinheiro, PAN/CPF, BOLA, idempotência, gasto duplo, timing, sessão, TLS, FAPI, config) |
| 🔴 herdado do baseline | ressalva + card | **BLOQUEADO se o SLA de correção venceu** (precisa da data da Findings API) |
| Sem scan real (só pré-scan) | aprova pelo pré-scan | ressalva "compliance não atestada" |
| Release | — | `--release` exige evidência do Policy Scan (Findings API ou `--status-politica`) |
| KDF (PBKDF2/bcrypt) | ativo | ativo |

**CWEs bancários (bloqueiam em qualquer severidade):** 90, 113, 117, 200, 208, 209, 287, 312, 319,
326, 327, 329, 347, 352, 359, 362, 367, 532, 601, 613, 639, 643, 681, 682, 837, 915, 916, 943, 1321, 1339.

## 3. Mapa normativo → cobertura da skill → evidência

| Norma | Exigência relevante para código | Como a skill cobre | Evidência que fica |
|---|---|---|---|
| **Res. CMN 4.893/2021, alterada pela CMN 5.274/2025** (adequação até 01/03/2026) | 14 controles mínimos — entre eles autenticação, criptografia, prevenção de vazamento, rastreabilidade, **avaliação e correção de vulnerabilidades**, controle de acesso, hardening, certificados e **requisitos de segurança para APIs**; pentest anual independente com documentação por 5 anos; isolamento dos ambientes Pix/STR | Pré-scan + gate + SLA (vulnerabilidades); X-TLS, J-KEY-02, J-IV-01, KDF e regras de cripto (criptografia); JWT, FAPI, sessão (autenticação); BOLA, MASS, IDEMP (APIs); PAN, CPF, LOG, CFG (vazamento) | `veredito.json/.md` por PR e release, plano de ação com prazos |
| **Res. BCB 538/2025** | Estende o mesmo arcabouço a instituições de pagamento, corretoras e distribuidoras | Mesmo perfil | Idem |
| **Res. BCB 494–498/2025** (set/2025) | PSTIs e IPs no Pix/RSFN: MFA, rastreabilidade de logs, criptografia moderna; limite inicial de R$ 15 mil por TED/Pix até a verificação de controles | Limites e antifraude são regra de negócio — BK-RACE e BK-IDEMP protegem a efetivação; MFA é processo | Testes de limite + veredito |
| **PCI DSS v4.0.1** (requisitos futuros obrigatórios desde 31/03/2025) | 3.3.1 SAD/CVV não retidos; 3.4.1 PAN mascarado; 3.5.1 PAN ilegível onde armazenado; 4.2.1 criptografia forte em trânsito; **6.2.4** técnicas contra injeção, ataques a dados, uso de criptografia, lógica de negócio e controle de acesso; 6.2.3/6.2.3.1 revisão antes do release por quem não é o autor; 6.3.1/6.3.3 vulnerabilidades ranqueadas e corrigidas; 6.3.2 inventário de software próprio e de terceiros; 8.2.8 sessão ociosa ≤ 15 min | BK-PAN, BK-LOG, J-LOG-02 (3.x); X-TLS, BK-HTTP (4.2.1); catálogo inteiro (6.2.4); lente `rev-veracode` no `tech-lead-review` (6.2.3); gate + SLA (6.3.x); Veracode SCA/SBOM (6.3.2); BK-SESSAO-01 (8.2.8) | Veredito + SBOM CycloneDX + registro do review |
| **Open Finance Brasil — perfil FAPI-BR** | `private_key_jwt`, PAR, PKCE, tokens vinculados ao certificado mTLS (ICP-Brasil), assinatura PS256; sem implicit/password grant | BK-FAPI-01 (sinais de fluxo fora do perfil), J-JWT-01/02, P-JWT-01 | Veredito; a certificação de conformidade é processo à parte |
| **Pix — Regulamento e MED 2.0** (em vigor desde 02/02/2026) | Rastreamento de recursos em contas intermediárias, bloqueio cautelar até 11 dias, contestação por autoatendimento | BK-IDEMP (endToEndId/txid), BK-RACE (débito atômico), BK-LOG (chave Pix fora do log), BK-BOLA (consulta de transações) | Veredito + trilha de auditoria do bloqueio/devolução |
| **LGPD + sigilo bancário (LC 105/2001)** | Dado pessoal e bancário fora de log, código e mensagens de erro | BK-LOG-01, BK-CPF-01, J-LOG-02, BK-CFG-01 | Veredito |

**Fora do alcance do pré-scan (cubra por processo):** WAF de apps públicas (PCI 6.4.2), integridade
de scripts da página de pagamento (6.4.3/11.6.1), MFA administrativo, segregação física/lógica do
ambiente Pix/STR, pentest anual independente.

## 4. Regras `BK-*` — por que importam e como corrigir

### Dinheiro (BK-DINHEIRO-01/02 · CWE-1339/682)
`0.1 + 0.2 != 0.3` em `double`. Em saldo, tarifa e juros o erro de centavo vira divergência contábil.

```java
BigDecimal taxa = new BigDecimal("0.0199");                    // nunca new BigDecimal(0.0199)
BigDecimal juros = saldo.multiply(taxa).setScale(2, RoundingMode.HALF_EVEN);
BigDecimal parcela = total.divide(BigDecimal.valueOf(prazo), 2, RoundingMode.HALF_EVEN);
```
Python: `decimal.Decimal("0.0199")` com `quantize(Decimal("0.01"), ROUND_HALF_EVEN)`. JS/TS: inteiro
em centavos (ou `bigint`) e formatação só na borda.

### PAN, CPF/CNPJ e log (BK-PAN-01 · BK-CPF-01 · BK-LOG-01)
PAN válido por Luhn ou CPF/CNPJ com DV válido no código é massa real (ou parecida com real) indo para
o artefato. O valor é redigido no relatório.

```java
static String mascararPan(String pan) {               // PCI DSS 3.4.1: no máximo BIN + 4 últimos
    return pan.substring(0, 6) + "*".repeat(pan.length() - 10) + pan.substring(pan.length() - 4);
}
```
Armazenamento: token do cofre/PSP ou cifra com chave no KMS/HSM. CVV nunca é armazenado.

### BOLA / IDOR (BK-BOLA-01 · CWE-639 · OWASP API1)
O papel `CLIENTE` autoriza a rota; só a checagem de titularidade autoriza **aquela** conta.

```java
@GetMapping("/contas/{contaId}/saldo")
@PreAuthorize("@titularidade.pertence(#contaId, authentication)")
public SaldoDto saldo(@PathVariable UUID contaId) { ... }
```
Melhor ainda: a consulta filtra pelo titular do token (`findByIdAndTitular(contaId, sub)`), para que
um id alheio simplesmente não exista. Teste com dois titulares em todo endpoint.

### Mass assignment (BK-MASS-01 · CWE-915)
`@RequestBody Conta` deixa o cliente mandar `saldo`, `limite`, `status`. Entrada é um `record`
com só os campos permitidos, mapeado explicitamente para a entidade.

### Idempotência (BK-IDEMP-01 · CWE-837)
Timeout + retry do cliente = débito em dobro. Registre a chave antes de efetivar, de forma condicional:

```java
dynamo.putItem(PutItemRequest.builder()
    .tableName(tabela)
    .item(Map.of("pk", s("IDEMP#" + chave), "status", s("EM_PROCESSAMENTO")))
    .conditionExpression("attribute_not_exists(pk)")   // 2ª tentativa falha aqui, não no débito
    .build());
```
No Pix, o `endToEndId`/`txid` é a chave natural. Na Lambda Java, o `@Idempotent` do Powertools
resolve o mesmo problema.

### Gasto duplo / TOCTOU (BK-RACE-01 · CWE-367)
`if (saldo >= valor) debitar(valor)` em duas requisições simultâneas aprova as duas.

```java
dynamo.updateItem(UpdateItemRequest.builder()
    .tableName(tabela).key(chaveConta)
    .updateExpression("SET saldo = saldo - :v")
    .conditionExpression("saldo >= :v")                // atômico: ou debita, ou falha
    .expressionAttributeValues(Map.of(":v", n(valor)))
    .build());
```
SQL: `UPDATE conta SET saldo = saldo - ? WHERE id = ? AND saldo >= ?` e conferir linhas afetadas;
ou `SELECT ... FOR UPDATE` / `@Version`.

### Comparação de segredo (BK-TIMING-01 · CWE-208)
`assinatura.equals(esperada)` vaza, pelo tempo, quantos bytes batem. Use
`MessageDigest.isEqual(a, b)` / `hmac.compare_digest` / `crypto.timingSafeEqual`.

### Sessão, transporte e configuração (BK-SESSAO-01 · BK-HTTP-01 · BK-CFG-01/02 · X-TLS-01/02)
- Ociosidade ≤ 15 min (PCI DSS 8.2.8); token de acesso curto e refresh rotativo.
- Toda integração em HTTPS com TLS 1.2+ (preferir 1.3); mTLS com ICP-Brasil em integrações reguladas.
- `server.error.include-stacktrace=never`; Actuator só com `health`/`info`, em porta interna e autenticada.

### Open Finance (BK-FAPI-01)
Cliente com `private_key_jwt`, PAR + PKCE S256, token vinculado ao certificado mTLS, assinatura PS256.
`client_secret_*`, `response_type=token`, `grant_type=password` e `alg` `none`/`HS256` ficam fora do perfil.

## 5. Política Veracode recomendada para banco

- **Nível:** política com VL4 + SCA no mínimo, bloqueando Very High, High e Medium. VL5 exige teste
  manual além do automatizado — use quando houver esse teste (o pentest anual da 5.274 é independente
  da plataforma).
- **Grace period ≤ SLA desta skill** (seção 6); política `Did Not Pass` trava o release.
- **SCA:** bloquear componentes com CVE de CVSS ≥ 7 e licenças de alto risco; SBOM CycloneDX por
  release (PCI DSS 6.3.2).
- **DAST autenticado** em staging a partir do OpenAPI (rotas com titular A tentando recurso do titular B).
- **Mitigação:** aprovador ≠ autor, de preferência do time de segurança; *Accept the Risk* só pelo
  dono do risco, com prazo de revisão.

## 6. SLA de correção (padrão da skill)

| Severidade Veracode | Prazo desde a 1ª detecção |
|---|---|
| 5 Very High | 1 dia |
| 4 High | 7 dias |
| 3 Medium | 30 dias |
| 2 Low | 90 dias |

Alinhado ao SLA canônico de CVE da squad (`engenheiro-seguranca/references/secrets-cripto.md`).
A política da instituição prevalece: `--sla-dias "5=1,4=15,3=45,2=120"`. O cálculo usa
`finding_status.first_found_date` da Findings API; o `results.json` do Pipeline Scan não traz data,
então ali o herdado continua como ressalva.

## 7. Pacote de evidências por release

1. `veredito.json` e `veredito.md` do gate (perfil, motivos, ressalvas, achados).
2. `results.json` do Pipeline Scan e export da Findings API do Policy Scan.
3. SBOM CycloneDX (Veracode SCA).
4. Mitigações aprovadas, com evidência e aprovador.
5. Plano de ação das vulnerabilidades em aberto, com prazos.
6. Relatório do pentest anual e plano de ação (a CMN 5.274 exige guarda por 5 anos).

Guarde pelo prazo da política da instituição; na dúvida, alinhe aos 5 anos do pentest.

## 8. Limites honestos

- Regex não prova autorização correta: `BK-BOLA-01` fica quieta se o arquivo tem `@PreAuthorize`,
  mesmo que a expressão esteja errada. Teste de autorização com dois titulares é obrigatório.
- Sem análise entre arquivos: um débito sem trava espalhado em várias classes pode passar.
- Limites, antifraude e regras de MED são regra de negócio — threat modeling, testes de domínio e
  pentest cobrem; o pré-scan não.
- Calibração de 04/10/2026 em cerca de 1.066 arquivos reais do repositório: quatro classes de
  falso-positivo encontradas e corrigidas com teste de regressão; ficaram 2 residuais conhecidos
  (`valor: float` num módulo que não é financeiro).

## Fontes

- [Grant Thornton — o que muda com a Resolução CMN 5.274/2025](https://www.grantthornton.com.br/insights/artigos-e-publicacoes/seguranca-cibernetica-o-que-muda-com-a-cmn-5.2742025/)
- [Tech86 — Resolução 5.274: 14 controles obrigatórios](https://www.tech86.com.br/blog/bacen-resolucao-5274-14-controles-obrigatorios-prazo-vencido/)
- [EximiaCo — Resoluções BCB 494 a 498](https://eximia.co/insights/resolucoes-bcb-494-a-498-avancos-de-ciberseguranca/)
- [Open Finance Brasil — FAPI-BR (Área do Desenvolvedor)](https://openfinancebrasil.atlassian.net/wiki/spaces/OF/pages/346652711)
- [Agência Brasil — novas regras de segurança do Pix (fev/2026)](https://agenciabrasil.ebc.com.br/economia/noticia/2026-02/novas-regras-de-seguranca-do-pix-entram-em-vigor-veja-mudancas)
- [Qualys — PCI DSS 4.0.1 para aplicações web e APIs](https://blog.qualys.com/product-tech/2025/12/19/pci-dss-4-0-1-compliance-web-application-api-security)
- PCI SSC — *PCI DSS v4.0.1* (documento oficial, jun/2024)
