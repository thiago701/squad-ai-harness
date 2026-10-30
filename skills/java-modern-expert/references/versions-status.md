# Versões e suporte do JDK — status detalhado

> **Verificado em 2026-09-27** (openjdk.org, oracle.com, adoptium.net, docs.aws.amazon.com,
> endoflife.ai cross-check). **Revalidar a cada release (mar/set).** Roadmap Oracle de 15/09/2026.

## 1. Matriz principal

| Versão | Tipo | GA | Oracle premier/extended | Temurin (Adoptium) | Corretto | Observação-chave |
|---|---|---|---|---|---|---|
| Java 21 | LTS | 2023-09-19 | 2028-09 / 2031-09 | ≥ 2029-12 | 2030-10-31 | ⚠️ Oracle JDK 21 sai do NFTC (licença permissiva) no CPU de **out/2026** → OTN. |
| Java 22–24 | non-LTS | 2024-03 … 2025-03 | encerrado | EOSL | EOL | 24: VT sync (JEP 491), Security Manager desativado (486), Class-File API final (484). |
| **Java 25** | **LTS** | **2025-09-16** | 2030-09 / **2033-09** | **≥ 2031-09** | **2032-10-31** | **LTS vigente e recomendada da Squad.** |
| Java 26 | non-LTS | 2026-03-17 | até 2026-09 | EOSL 2026-09 | 2026-10-31 | HTTP/3 (517), Applet removido (504), G1 throughput (522). |
| **Java 27** | **non-LTS** ⚠️ | **2026-09-15** | até 2027-03 (preliminar) | 2027-03 | 2027-04-30 | G1 universal, PQC TLS, **COH por default** (534). |
| Java 28 | non-LTS (prev.) | ~2027-03 | — | — | — | **Valhalla Value Objects Preview** (401/539), Shenandoah geracional default (535). |
| **Java 29** | **LTS (planejada)** | ~2027-09 | 2032-09 / 2035-09 (prev.) | — | — | **Próxima LTS** — cadência 21 → 25 → 29. |

> ⚠️ **Correção crítica:** Java 27 **não é LTS**. Roadmap Oracle (15/09/2026) marca 27/28 como
> non-LTS e **29 como próxima LTS**. Adoptium/Corretto já tratam 27 como non-LTS. O roadmap anota
> "designações sujeitas a mudança (***)" — postura segura: tratar 27 como non-LTS.

## 2. Temurin (Adoptium) — builds atuais (set/2026)

| Versão | Última build | Próximo update | Disponibilidade |
|---|---|---|---|
| 27 | 27+35 | 27.0.1 (out/2026) | mar/2027 |
| 26 | 26.0.2.1 | EOSL | encerrado set/2026 |
| **25 (LTS)** | 25.0.4.1 | 25.0.5 (out/2026) | ≥ set/2031 |
| 21 (LTS) | 21.0.12.1 | 21.0.13 (out/2026) | ≥ dez/2029 |
| 17 (LTS) | 17.0.20.1 | 17.0.21 | ≥ out/2027 |
| 11 (LTS) | 11.0.32.1 | 11.0.33 | ≥ out/2027 |
| 8 (LTS) | 8u504 | 8u511 | ≥ dez/2030 |

Política Adoptium: LTS com ≥ 4 anos de updates gratuitos; CSPUs acompanham o OpenJDK.

## 3. Corretto — EOL (FAQ AWS + endoflife.ai, 24/09/2026)

| Versão | EOL |
|---|---|
| 25 (LTS) | 2032-10-31 |
| 21 (LTS) | 2030-10-31 |
| 17 (LTS) | 2029-10-31 |
| 11 (LTS) | 2032-01-31 |
| 8 (LTS) | 2030-12-31 |
| 27 (non-LTS) | 2027-04-30 |
| 26 (non-LTS) | 2026-10-31 |

## 4. Licenciamento Oracle (resumo atual)

- **Oracle JDK 25+** — **NFTC: gratuito para TODOS os usos, inclusive produção**; updates
  pós-set/2028 passam a OTN.
- **Oracle JDK 21** — NFTC só até o CPU de **out/2026**; depois OTN (produção exige assinatura).
- **Oracle JDK 17/11/8** — OTN (gratuito apenas uso pessoal/desenvolvimento).
- **OpenJDK (GPLv2+CE)** — sempre gratuito; builds Oracle em jdk.java.net.
- **Temurin e Corretto** — gratuitos e patrocinados; padrão de produção sem contrato Oracle.
- GraalVM deixou de ser parte dos produtos Java SE (último: GraalVM for JDK 24).

## 5. Fontes

| Fonte | URL |
|---|---|
| Oracle Java SE Support Roadmap (15/09/2026) | https://www.oracle.com/java/technologies/java-se-support-roadmap.html |
| JDK 25 / 26 / 27 / 28 (JEPs, schedule) | https://openjdk.org/projects/jdk/25/ · /26/ · /27/ · /28/ |
| Release notes JDK 27 | https://jdk.java.net/27/release-notes |
| Adoptium support | https://adoptium.net/support/ |
| Corretto docs | https://docs.aws.amazon.com/corretto/latest/corretto-25-ug/ |
| endoflife.ai (cross-check) | https://endoflife.ai/amazon-corretto |
