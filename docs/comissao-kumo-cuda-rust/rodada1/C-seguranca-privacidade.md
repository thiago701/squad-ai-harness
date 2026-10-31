# Memo — Arquiteto C (Segurança, Privacidade & FFI/GPU Safety · `engenheiro-seguranca` + `rust-unsafe-security`)

## Posição em 5 linhas
A combinação de **Go + Rust + GPU (CUDA) + Machine Learning (Kumo)** introduz três superfícies críticas de segurança: (1) fronteira de memória CPU↔GPU (data races em buffers assíncronos de streams CUDA), (2) fronteira IPC Go↔Rust (injeção de comando/PQL ou exaustão de memória DoS), e (3) risco epistêmico de um modelo probabilístico (GNN/RelGT) aprovar código vulnerável que uma regra determinística bloquearia. Minha posição é: **o compilador Rust carrega a prova de memória (`cuda-core` borrow checking), e o ML atua exclusivamente como amplificador de detecção (OR lógico de bloqueio nos gates de segurança, nunca bypass de bloqueio determinístico)**.

## Propostas concretas
1. **Segurança de Memória CPU↔GPU (`cuda-core` Safe Launch Boundary):** Modelar `DeviceBuffer<T>` e `HostPinnedBuffer<T>` em Rust onde o lançamento de um kernel (`cutile-rs` ou `cuda-oxide`) exige empréstimos imutáveis (`&DeviceSlice<T>`) para entradas e empréstimo mutável exclusivo ou partição disjunta (`DisjointMutSplit<'a, T>`) para saídas. `#[forbid(unsafe_code)]` em todas as 5 crates de POCs de negócio!
2. **Invariante de Cláusula Pétrea no Tribunal JEV (POC-04):** Os 7 especialistas determinísticos de segurança (`jev.sec.sqli`, `ssrf`, `xxe`, `xss`, `secrets`, etc.) permanecem **soberanos e inegociáveis**. O coprocessador **JEV-GNN em Rust (POC-04)** atua sobre os **18 especialistas que hoje estão em `passDefault` (`internal/jev/engine.go:164`)** e sobre análise de fluxo *taint* multi-função: ele pode **elevar** o risco (`APPROVE → BLOCK / ESCALATE_LLM`), mas **jamais rebaixar** um `BLOCK` determinístico!
3. **Hardening do Parser PQL e do Servidor IPC (STRIDE):**
   - **S (Spoofing) / E (Elevation):** Servidor IPC escuta exclusivamente em `127.0.0.1` (loopback local) ou `stdio` pipe herdado do processo pai Go.
   - **T (Tampering):** Grafo binário `DiskGraph` (POC-01) validado por envelope SHA-256 antes do mapeamento.
   - **D (Denial of Service):** Limite estrito de tamanho de payload IPC (`max 1 MiB`), limite de tokens na query PQL (`max 64 tokens`) e limite de saltos no grafo (`max_hops <= 3`).

## Respostas às tensões do meu domínio
- **T4 (`NVIDIA/cuda-rust` Borrow Checking):** A grande inovação do `NVIDIA/cuda-rust` sobre CUDA C++ é impedir *use-after-free* e *data race* entre streams assíncronos usando lifetimes de Rust (`'stream`, `'buf`). Demonstraremos isso em código compilável na crate `cuda_rust_core`.
- **T5 (Segurança vs. ML):** Regra formal: $\text{Veredito}_{\text{final}} = \text{Block}_{\text{Det}} \lor \text{Block}_{\text{GNN}}$. Zero regressão nos falsos negativos de segurança ($\text{Recall}_{\text{sec}} = 1.00$).

## Riscos e armadilhas
- 🔴 **Uso indiscriminado de `unsafe` em Rust para simular ponteiros de GPU:** Viola a doutrina `rust-pro` e `rust-unsafe-security`. Mitigação: isolar a abstração de buffers e usar tipos seguros em Rust 1.99.1 com `#[forbid(unsafe_code)]` nos módulos de domínio/ML.
- 🔴 **Vazamento Temporal (*Time Leakage*) em Predições de Risco (POC-01/POC-02):** Se o amostrador de subgrafo incluir arestas com `timestamp > anchor_time`, o benchmark de ML terá acurácia artificialmente inflada (reward hacking). Mitigação: filtro estrito `edge.timestamp <= query.anchor_time` verificado por teste unitário de contrato.

## Dúvidas que SÓ o usuário pode responder (com default)
- **Q3:** A comunicação TCP loopback entre Go e Rust deve exigir um token efêmero de sessão (`X-Squad-IPC-Token` gerado pelo processo Go ao iniciar o sidecar)? *(Default: Sim, implementar validação de token ou framing autenticado local por defesa em profundidade).*

## O que eu vetaria se visse no plano
- Veto qualquer POC de ML que possa **anular** um bloqueio de segurança do `secretscan` ou do `jev.sec.*`.
- Veto `.unwrap()` / `.expect()` sem tratamento na fronteira IPC.
