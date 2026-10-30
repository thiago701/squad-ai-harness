# Matriz de versões e compatibilidade do ecossistema Spring

> **Verificado 2026-09-27** (spring.io, GitHub spring-projects, Maven Central, endoflife.date).
> Revalidar a cada release (mai/nov). Fonte completa: `docs/research/notes/spring-notes.md`.

## 1. Versões por projeto

| Projeto | Linha | Última | Data | Status | Fim OSS |
|---|---|---|---|---|---|
| Spring Boot | 4.1.x | **4.1.1** | 20/08/2026 | **GA atual** | 31/07/2027 (comercial 31/07/2028) |
| Spring Boot | 4.0.x | **4.0.8** | 20/08/2026 | GA | 31/12/2026 (comercial 31/12/2027) |
| Spring Boot | 4.2.x | 4.2.0-M2 | 24/09/2026 | Milestone (GA ~nov/2026) | — |
| Spring Boot | 3.5.x | 3.5.16 | 25/06/2026 | **OSS encerrado** | 30/06/2026 |
| Spring Framework | 7.0.x | **7.0.9** | 21/08/2026 | GA | ~31/12/2026 |
| Spring Framework | 7.1.x | 7.1.0-M2 | 24/09/2026 | Milestone (GA nov/2026) | — |
| Spring Cloud | 2025.1 Oakwood | **2025.1.3** | 20/08/2026 | GA (Boot 4.0.x) | 31/07/2027 |
| Spring Cloud | 2026.0 Paddington | 2026.0.0-M1 | 24/09/2026 | Milestone (Boot 4.2) | — |
| Spring Data | 2026.0 | **2026.0.1** | 20/08/2026 | GA (Boot 4.1) | — |
| Spring Data | 2025.1 | 2025.1.7 | 20/08/2026 | GA (Boot 4.0) | — |
| Spring Security | 7.1.x | **7.1.1** | 20/08/2026 | GA | 31/07/2027 |
| Spring Security | 7.0.x | **7.0.7** | 20/08/2026 | GA | 31/12/2026 |
| Spring Authorization Server | 1.5.x | 1.5.8 | 09/06/2026 | **ARQUIVADO** (spring-attic) → Security 7 | — |
| Spring AI | 2.0.x | **2.0.1** | 21/08/2026 | GA (2.0.0 GA 12/06/2026) | — |
| Spring AI | 2.1.x | 2.1.0-M1 | 25/09/2026 | Milestone (Boot 4.2) | — |

## 2. Matriz de compatibilidade (geração atual)

| Boot | Framework | Data | Security | Cloud | Hibernate | Micrometer | Jackson |
|---|---|---|---|---|---|---|---|
| 4.2 (M2) | 7.1.0-M2 | 2026.1.0-M2 | 7.2.0-M2 | 2026.0.0-M1 | 7.4.9 | 1.18.0-M2 | 3.1.6 |
| **4.1.x** | 7.0.8/7.0.9 | **2026.0.x** | **7.1.x** | 2025.1.x* | 7.4.x | 1.17.0 | 3.1.4 |
| **4.0.x** | 7.0.x | 2025.1.x | 7.0.x | **2025.1.x** | 7.2.24 | 1.16.x | 3.1.x |
| 3.5.x | 6.2.x | 2025.0.x | 6.5.x | 2025.0.x | 6.6.53 | 1.15.x | 2.19.x |

\* Não há train Cloud oficial para Boot 4.1 — usa-se 2025.1.x até o 2026.0 GA.

## 3. Baselines e destaques de segurança (razões para não ficar para trás)

- **Baseline Java 17** em Boot 4/Framework 7 (recomendação: **JDK 25 LTS**). Boot 4.2-M2 documenta Java 27.
- **Framework 7.0.8** corrigiu **16 CVEs** (SpEL, multipart smuggling, path traversal, SSRF via UriComponentsBuilder…).
- **Cloud 2025.1.3** corrigiu **17 CVEs** (Config Server TOCTOU, Gateway SSRF, Stream desserialização…).
- **Security 7.1.1** corrigiu **7 CVEs**.
- Boot 4.0 OSS morre em **31/12/2026** — planejar 4.0 → 4.1 antes disso (ou ir direto p/ 4.1).

## 4. Ecossistema adjacente (mesma data)

- Spring Cloud AWS (`io.awspring.cloud`): **4.1.1**, AWS SDK v2 2.54.3.
- Resilience4j via Circuit Breaker: **2.3.0** (Cloud 2025.1); 2.4.0 no 2026 M1.
- OpenRewrite receitas oficiais Boot 4: docs.openrewrite.org/recipes/java/spring/boot4.
- Native Build Tools: 1.1.x (1.1.14 no Boot 4.2-M2); GraalVM 25 baseline do Framework 7.

## 5. Fontes principais

- Releases Boot: https://github.com/spring-projects/spring-boot/releases
- Framework 7.0 Release Notes: https://github.com/spring-projects/spring-framework/wiki/Spring-Framework-7.0-Release-Notes
- Cloud releases: https://github.com/spring-cloud/spring-cloud-release/releases
- Data BOM: https://github.com/spring-projects/spring-data-bom/releases
- Security releases: https://github.com/spring-projects/spring-security/releases
- EOL: https://endoflife.date/spring-boot · /spring-cloud · /spring-security
- Authorization Server arquivado: https://github.com/spring-attic/spring-authorization-server
