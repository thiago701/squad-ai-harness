# Segurança de Runtime — Isolamento & Sandboxing Zero-Trust

## Princípio
Conceder a um agente-LLM a capacidade de gerar/executar código é **risco severo**. Postura **zero-trust**:
**todo** código gerado é potencialmente hostil — por erro do modelo **ou** por **injeção de prompt** que
altere as instruções do sistema. Docker padrão **partilha o kernel do host**: um 0-day no kernel Linux ou
uma permissão privilegiada mal configurada expõe SSH keys, credenciais locais e portas internas.

## Tecnologias de isolamento (trade-off segurança × latência)

| Tecnologia | Mecanismo | Cold start | Segurança de kernel | Overhead |
|---|---|---|---|---|
| **Docker (padrão)** | namespaces+cgroups; **partilha kernel** do host | <90 ms (Daytona) | **Fraco** (0-day no kernel expõe host) | Mínimo (<2%) |
| **gVisor (Google)** | kernel em Go no **espaço de utilizador** (Sentry) interceta syscalls | ~150 ms | **Alto** (convidado não toca o kernel do host) | Moderado (10–30% em I/O intenso) |
| **Firecracker (microVM)** | microVM minimalista sobre **KVM** (hardware) | <2 s | **Excelente** (isolamento por virtualização de hardware) | Baixo (ótimo uso de CPU/RAM) |
| **WebAssembly (WASM)** | segurança por capacidades; isolamento na sandbox do runtime | <10 ms | **Excelente** (memória linear, sem dependência de kernel) | Variável (maturidade do JIT) |

Regra prática: **código não confiável de agente em produção → Firecracker/microVM** (fronteira de
hardware) ou **gVisor** (compute-heavy, I/O limitado). WASM para arranque ultrarrápido e código compilável
a ele. Docker padrão **não** é fronteira de segurança para código hostil. *(cold-starts verificados como
aproximados — ver PROCEDENCIA.md)*

## Quatro regras rígidas de execução
1. **Efemeridade total** — cada execução arranca numa sandbox **limpa** e é **destruída** após devolver o
   resultado. Impede persistência de código malicioso entre sessões.
2. **Rootfs read-only** — toda a árvore montada só-leitura, exceto **`/workspace`** e **`/tmp`**. Neutraliza
   baixar/compilar/executar binários ocultos.
3. **Sem credenciais de longa duração** — nenhuma API key de produção/DB/cloud nas variáveis de ambiente.
   Um **proxy de segurança externo** valida a tarefa e injeta **tokens de curta duração** só no payload de saída.
4. **Rede restrita** — namespace de rede privado por padrão; só outbound para APIs de modelo/registos de
   pacotes validados, sob **regras estritas de DNS**.

> Ponte com a Squad: casa com `engenheiro-seguranca`, `auditoria-skill-externa` e a decisão de CI local
> em Docker (memória `ci-local-docker-harness`). Para código realmente não confiável, elevar de Docker.
