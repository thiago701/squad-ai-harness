# Testes de fluxos distribuídos na AWS

> Parte da skill `especialista-qualidade`. Hub: `../SKILL.md`. Níveis de validação V0–V5 e marcas:
> `governance/politica-evidencias-sigilo-qualidade.md`. Exemplo executável completo:
> `labs/aws-referencia-ordens/` (JUnit + Velocity, pytest + simulador, Robot Framework, cfn-lint).

## 1. Pirâmide — o que cada nível prova e o que NÃO prova

| Nível | Ferramenta | Prova | Não prova |
|---|---|---|---|
| Lint estático | `scripts/aws/asl_lint.py`, `vtl_lint.py`, `cfn-lint` | estrutura, compatibilidade, padrões de segurança | comportamento |
| Contrato | JSON Schema (validador + diferencial com `jsonschema`) | exemplos válidos/inválidos; campos coerentes entre produtor e consumidor | serialização real do serviço |
| Unidade | JUnit/pytest com fakes das portas | regra de negócio, idempotência, tradução de erro | SDK/rede |
| Transformação | VTL no Velocity real com `$input/$util/$context` emulados | JSON válido, escape, isolamento | versão exata do Velocity da AWS |
| Caminho do workflow | `scripts/aws/asl_simulador.py` | retries, Catch, timeouts, parâmetros entre tentativas | runtime, IAM, quotas |
| Integração local | LocalStack/emuladores (se usados) | chamadas de API e fiação | **IAM real, limites, comportamento gerenciado** |
| Aceitação | **Robot Framework** | jornadas legíveis pelo negócio | o que o backend da suíte não exercita |
| Ponta a ponta | conta AWS **autorizada** | V4 | nada sem autorização (sem deploy/custo sem pedido) |

## 2. Robot Framework — avaliação e uso

- **Interpretação adotada:** "robot testing service" = **Robot Framework** (não existe serviço AWS
  com esse nome; nenhuma AWS doc o cita). Confirmado pelo dono do repositório em 2026-10-08.
- **Use para** aceitação: casos em linguagem de negócio, revisáveis por quem não programa, com o
  mesmo texto rodando contra backend local (simuladores) ou HTTP (ambiente autorizado).
- **Não use para** unidade/transformação (JUnit/pytest são mais rápidos e precisos) nem como
  substituto do lint.
- **Custo:** dependência extra (`robotframework==7.5`, pinada) e segundo runner — por isso a etapa é
  opcional no harness (`aws-integracao`, pula se `robot` não estiver instalado).
- Consistência eventual: `Wait Until Keyword Succeeds    <prazo>    <intervalo>    <condição>`.

## 3. Consistência eventual sem esperas fixas

Polling com **prazo** e **condição verificável** (ex.: até 30 s, a cada 500 ms, "GET devolve versão
≥ N"). `sleep` fixo longo deixa a suíte lenta e ainda assim intermitente.

## 4. Cenários obrigatórios para fluxo distribuído

API iniciando o workflow · entrada inválida rejeitada · requisição duplicada · falha e timeout em
Lambda/ECS · retry sem duplicar efeito · evento duplicado e fora de ordem · projeção CQRS atualizada ·
cliente WebSocket desconectado · reconexão e consulta de estado · callback válido, inválido, duplicado
e expirado · dispositivo IoT intermitente. O mapa cenário → teste do cenário de referência está em
`labs/aws-referencia-ordens/docs/06-testes-observabilidade-recuperacao.md`.

## 5. Mocks × emuladores × LocalStack × AWS

Declare a fonte de cada teste. Fake reproduz só a semântica exigida pelo teste (ex.: escrita
condicional, `TaskTimedOut`, `GoneException`); emulador reproduz a API, não o serviço; LocalStack só
com credenciais fictícias (`test`/`test`) e nunca é evidência de IAM, quota ou latência; só a conta
autorizada dá V4.

## 6. Eficiência sem enfraquecer o gate

- Rodar direcionado na iteração (`pytest tests/test_aws_* -q`, `mvn -q test -Dtest=...`) e os gates
  completos antes da entrega.
- Não remover teste que protege contrato ou limite de integração para acelerar pipeline; eliminar
  redundância só com evidência (cobertura/mutação equivalente).
- Cache só com invalidação por conteúdo + regras + versões; resultado antigo não é evidência da revisão atual.
