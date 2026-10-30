# DevOps Guidance — Quality Assurance (QA.*): indicadores, antipadrões e métricas

> Reference de `estrategia-testes-aws`. Saga **Quality Assurance** do AWS Well-Architected DevOps
> Guidance: 5 capacidades, 31 indicadores. Categoria: **F** = FOUNDATIONAL, **R** = RECOMMENDED,
> **O** = OPTIONAL. Use como checklist de maturidade do plano de testes.

## QA.TEM — Test environment management

| ID | indicador | cat. | o que pede |
|---|---|---|---|
| TEM.1 | ambientes de teste dedicados | F | parecidos com produção; staging monitorado no mínimo; IaC; deploy só pelo pipeline; acesso humano auditado |
| TEM.2 | test beds para execução consistente | F | imutáveis e efêmeros, criados por IaC; restauração automática de dados; preservar logs para depuração |
| TEM.3 | guardar e gerir resultados | F | centralizados, legíveis por máquina, versionados, criptografados, escrita restrita, retenção |
| TEM.4 | repositório unificado de dados de teste | R | versionado e sanitizado; ofuscação na atualização; contrato com quem depende |
| TEM.5 | paralelismo | R | scale-out de test beds com isolamento de dados |
| TEM.6 | plataformas de QA escaláveis | R | time de plataforma (self-service, device farm, ASPM); posse dos testes no time do fluxo de valor |

Antipadrões: pouca cobertura de dados de teste; dado de teste inseguro (produção sem ofuscação); QA
centralizado como gargalo. Métricas: tempo de provisionamento do test bed; tempo de execução.

## QA.FT — Functional testing

| ID | indicador | cat. | o que pede |
|---|---|---|---|
| FT.1 | unitário | F | isolado, fakes/mocks, rápido, local e CI, TDD |
| FT.2 | integração | F | componentes reais isolados de produção; IaC no setup/teardown; paralelo |
| FT.3 | aceitação | F | E2E pelo pipeline (BDD, Device Farm/Selenium), UAT, sintéticos (inclusive produção) |
| FT.4 | seleção avançada de testes | O | otimizar antes; análise de impacto; seleção preditiva só com controles e sem excluir segurança |

Antipadrões: **over indexing on coverage metrics** (use mutação; meça defeitos escapados × cobertura);
teste reativo; só requisitos funcionais; teste instável sem quarentena. Métricas: densidade de defeitos,
taxa de aprovação, defeitos escapados, tempo de execução, cobertura, razão feature/bug.

## QA.NT — Non-functional testing

| ID | indicador | cat. | o que pede |
|---|---|---|---|
| NT.1 | teste estático | F | código, docs e IaC (cfn-guard, cfn-lint), local e no pipeline, ferramentas atualizadas |
| NT.2 | desempenho | R | **load a cada deploy**; **stress** após mudança relevante ou ~mensal; **endurance** trimestral/semestral; ambiente espelho; comparar com histórico |
| NT.3 | UX | R | usabilidade e acessibilidade (WCAG; Cloudscape; Axe/WAVE de terceiros), automática e manual |
| NT.4 | experimentação | R | A/B em produção com feature flags até significância |
| NT.5 | conformidade | R | atestados e evidências gerados pelo pipeline em formato legível por máquina |
| NT.6 | resiliência | R | caos (FIS, Resilience Hub) pós-deploy no pipeline; recuperação de dados mensal/trimestral; DR semestral/anual (Elastic Disaster Recovery); começar em teste, depois produção com raio limitado |
| NT.7 | contrato | R | consumer-driven (Pact, Spring Cloud Contract) no pipeline do produtor e do consumidor |
| NT.8 | sustentabilidade | O | Graviton, right-sizing, profiling, Customer Carbon Footprint Tool |

Antipadrões: confundir resiliência de infraestrutura com confiabilidade do sistema; ignorar condições
reais; não usar observabilidade para ajustar desempenho; não colher feedback real. Métricas:
disponibilidade, latência (percentis, trimmed mean), limiar de pico, tempo de restauração × RTO, Apdex.

## QA.ST — Security testing

| ID | indicador | cat. | o que pede |
|---|---|---|---|
| ST.1 | gestão de vulnerabilidades DevOps | F | scan no pipeline, tickets automáticos com severidade, dashboards; segurança é de todos |
| ST.2 | normalizar achados | F | CVSS; SARIF/OCSF; painel único |
| ST.3 | avaliação de risco da aplicação | F | threat model; histórias de abuso com teste no Definition of Done |
| ST.4 | SAST | F | no CI; **critério principal: taxa de falso positivo**; regras introduzidas aos poucos (o exemplo citado, CodeGuru Security, foi descontinuado em 20/11/2025) |
| ST.5 | DAST | F | OWASP Top 10, integrado à autenticação |
| ST.6 | SCA | F | SBOM e manifests no CI; scans periódicos; SBOM centralizado |
| ST.7 | testes exploratórios | R | pentest (seguindo a política da AWS), red team, bug bounty |
| ST.8 | IAST | O | agentes em teste; passivos ou desligados em produção |

Antipadrões: confiar demais no resultado (falso negativo existe); ignorar ameaça interna; ignorar supply
chain. Métricas: defeitos escapados, falso positivo, MTTD, MTTR, taxa de descoberta.

## QA.DT — Data testing

DT.1 qualidade de dados com regras declarativas (R) · DT.2 profiling (O, Glue DataBrew) · DT.3 testes da
lógica de transformação versionados (O) · DT.4 detecção de anomalia (O) · DT.5 métricas incrementais
(O, Deequ do awslabs). Antipadrão: ambiente de teste que não espelha os dados de produção.

## Como usar no plano da Squad

1. Marque cada indicador como atendido / parcial / ausente, com evidência (arquivo, relatório, comando).
2. Todos os **F** ausentes viram itens do plano antes de qualquer **R**.
3. Reavalie a cada trimestre ou mudança grande de arquitetura.

## Fontes

- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/quality-assurance.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/indicators-for-test-environment-management.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/indicators-for-functional-testing.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/anti-patterns-for-functional-testing.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/indicators-for-non-functional-testing.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/anti-patterns-for-non-functional-testing.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/metrics-for-non-functional-testing.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/indicators-for-security-testing.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/anti-patterns-for-security-testing.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/indicators-for-data-testing.html
