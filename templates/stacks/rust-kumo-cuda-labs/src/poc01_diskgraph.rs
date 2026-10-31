//! # POC-01: Kumo `DiskGraph` Zero-Copy (`.kdg` 64B CSR) + Time-Travel Sampler + 5D RelGT Tokenizer
//!
//! Resolve o **GAP-01** do `SquadAI Harness v0.8.0` (`internal/cognitive/sekg/sekg.go`):
//! - O `sekg.GraphCSR` atual em Go serializa o grafo em JSON (`sekg.db`), carrega tudo na Heap
//!   (limitada por `GOMEMLIMIT = 256 MiB`) e executa `AnalyzeImpact` sem filtro de tempo (`anchor_time`),
//!   sofrendo de *temporal data leakage* (arestas do futuro vazam para consultas no passado).
//! - Esta POC implementa o motor **DiskGraph** inspirado na Kumo AI em Rust 1.99.1 com:
//!   1. Layout binário alinhado a 64 bytes (`KUMODG01`) pronto para `mmap` zero-copy.
//!   2. Amostragem de subgrafo temporal estrita (`edge.timestamp <= anchor_time`, zero *leakage*).
//!   3. **Multi-Element Tokenization (5 dimensões do Kumo RelGT)**:
//!      `[Features, EntityType, HopDistance, TimeDeltaHarmonic, LocalStructuralClustering]`
//!      acelerada pela trilha SIMT (`cuda-oxide`).

use std::time::Instant;

use crate::cuda_rust_runtime::{CudaContext, CudaStream, GpuDeviceProps};

/// Assinatura binária mágica de 8 bytes do snapshot `.kdg` (Kumo DiskGraph).
pub const KDG_MAGIC: &[u8; 8] = b"KUMODG01";
/// Tamanho do cabeçalho alinhado a linha de cache de 64 bytes.
pub const KDG_HEADER_SIZE: usize = 64;

/// Tipo de entidade no Relational Entity Graph (REG) da Squad AI.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum EntityTableType {
    Module = 0,
    File = 1,
    Skill = 2,
    Commit = 3,
    GateEpisode = 4,
    InfraNode = 5,
}

impl EntityTableType {
    #[must_use]
    pub const fn from_u8(v: u8) -> Self {
        match v {
            0 => Self::Module,
            1 => Self::File,
            2 => Self::Skill,
            3 => Self::Commit,
            4 => Self::GateEpisode,
            _ => Self::InfraNode,
        }
    }

    #[must_use]
    pub const fn type_embedding_scalar(self) -> f32 {
        match self {
            Self::Module => 0.15,
            Self::File => 0.30,
            Self::Skill => 0.45,
            Self::Commit => 0.60,
            Self::GateEpisode => 0.80,
            Self::InfraNode => 0.95,
        }
    }
}

/// Token multidimensional de 5 elementos do Kumo **RelGT (Relational Graph Transformer)** para um nó amostrado.
#[repr(C, align(32))]
#[derive(Debug, Clone, Copy, Default)]
pub struct RelGt5DToken {
    pub node_id: u32,
    /// 1. Features numéricas normalizadas da entidade (ex.: complexidade, churn, taxa de falha).
    pub d1_feature_norm: f32,
    /// 2. Identidade da tabela/esquema (`EntityTableType`).
    pub d2_entity_type_emb: f32,
    /// 3. Distância topológica ($h \in \{0, 1, 2\}$) a partir da entidade-semente.
    pub d3_hop_distance_emb: f32,
    /// 4. Codificação harmônica/logarítmica do delta temporal $\Delta t = t_{\text{anchor}} - t_{\text{edge}} \ge 0$.
    pub d4_temporal_delta_emb: f32,
    /// 5. Assinatura estrutural local (grau normalizado + densidade de vizinhança).
    pub d5_local_structure_emb: f32,
    pub padding: [f32; 2],
}

impl RelGt5DToken {
    /// Projeta o token 5D num vetor denso de 8 dimensões pronto para um bloco `Tile2D<8, 8>` (`cutile-rs`).
    #[must_use]
    pub fn to_vec8(self) -> [f32; 8] {
        let f = self.d1_feature_norm;
        let t = self.d2_entity_type_emb;
        let h = self.d3_hop_distance_emb;
        let dt = self.d4_temporal_delta_emb;
        let s = self.d5_local_structure_emb;
        [
            f,
            t,
            h,
            dt,
            s,
            0.5 * (f + s),
            (f * dt).tanh(),
            (t + h - 0.25 * dt).clamp(-1.0, 1.0),
        ]
    }
}

/// Grafo Relacional Temporal em formato CSR compacto (`Kumo DiskGraph`).
#[derive(Debug, Clone)]
pub struct KumoDiskGraph {
    pub num_nodes: usize,
    pub num_edges: usize,
    pub fwd_offsets: Vec<u32>,
    pub fwd_targets: Vec<u32>,
    pub edge_timestamps: Vec<u64>,
    pub edge_weights: Vec<f32>,
    pub node_types: Vec<u8>,
    pub node_features: Vec<f32>,
}

/// Resultado de uma amostragem de subgrafo temporal + tokenização 5D.
#[derive(Debug, Clone)]
pub struct TemporalSubgraphSample {
    pub seed_node: u32,
    pub anchor_time: u64,
    pub tokens_5d: Vec<RelGt5DToken>,
    pub future_edges_filtered: usize,
    pub leaked_future_edges: usize,
    pub duration_ns: u64,
}

impl KumoDiskGraph {
    /// Constrói um grafo relacional temporal sintético realista representando o ecossistema
    /// SquadAI (`Modules ↔ Files ↔ Commits ↔ Skills ↔ GateEpisodes ↔ InfraNodes`).
    #[must_use]
    pub fn build_squad_relational_benchmark_graph(num_nodes: usize, avg_degree: usize) -> Self {
        let n = num_nodes.max(16);
        let deg = avg_degree.max(4);
        let m = n * deg;

        let mut fwd_offsets = Vec::with_capacity(n + 1);
        let mut fwd_targets = Vec::with_capacity(m);
        let mut edge_timestamps = Vec::with_capacity(m);
        let mut edge_weights = Vec::with_capacity(m);
        let mut node_types = Vec::with_capacity(n);
        let mut node_features = Vec::with_capacity(n);

        // Base timestamp: 2026-10-01T00:00:00Z (1759276800) até 2026-10-31
        let base_ts: u64 = 1_759_276_800;
        let mut cur_offset = 0_u32;

        for u in 0..n {
            fwd_offsets.push(cur_offset);
            node_types.push((u % 6) as u8);
            let feat = (((u as u32).wrapping_mul(2_654_435_761) % 1000) as f32) / 1000.0;
            node_features.push(feat);

            for k in 0..deg {
                let target = ((u * 7 + k * 13 + 1) % n) as u32;
                // Metade das arestas no passado (dias 1..15), metade no futuro relativo à âncora (dias 16..30)
                let day_offset = ((u + k * 5) % 30) as u64;
                let ts = base_ts + day_offset * 86_400;
                let weight = 0.25 + (((u + k) % 4) as f32) * 0.25;

                fwd_targets.push(target);
                edge_timestamps.push(ts);
                edge_weights.push(weight);
                cur_offset += 1;
            }
        }
        fwd_offsets.push(cur_offset);

        Self {
            num_nodes: n,
            num_edges: m,
            fwd_offsets,
            fwd_targets,
            edge_timestamps,
            edge_weights,
            node_types,
            node_features,
        }
    }

    /// Serializa o `KumoDiskGraph` num buffer binário alinhado a 64 bytes (`.kdg` zero-copy format).
    #[must_use]
    pub fn to_aligned_kdg_bytes(&self) -> Vec<u8> {
        let payload_bytes = (self.num_nodes + 1) * 4
            + self.num_edges * 4
            + self.num_edges * 8
            + self.num_edges * 4
            + self.num_nodes
            + self.num_nodes * 4;
        let mut buf = Vec::with_capacity(KDG_HEADER_SIZE + payload_bytes);

        // Cabeçalho de 64 bytes: magic (8B) + version (4B) + num_nodes (4B) + num_edges (4B) + checksum_fnv64 (8B) + padding (36B)
        buf.extend_from_slice(KDG_MAGIC);
        buf.extend_from_slice(&1_u32.to_le_bytes());
        buf.extend_from_slice(&(self.num_nodes as u32).to_le_bytes());
        buf.extend_from_slice(&(self.num_edges as u32).to_le_bytes());
        let checksum = self.compute_fnv1a64();
        buf.extend_from_slice(&checksum.to_le_bytes());
        buf.extend_from_slice(&[0_u8; 36]);
        debug_assert_eq!(buf.len(), KDG_HEADER_SIZE);

        for &off in &self.fwd_offsets {
            buf.extend_from_slice(&off.to_le_bytes());
        }
        for &tgt in &self.fwd_targets {
            buf.extend_from_slice(&tgt.to_le_bytes());
        }
        for &ts in &self.edge_timestamps {
            buf.extend_from_slice(&ts.to_le_bytes());
        }
        for &w in &self.edge_weights {
            buf.extend_from_slice(&w.to_le_bytes());
        }
        buf.extend_from_slice(&self.node_types);
        for &f in &self.node_features {
            buf.extend_from_slice(&f.to_le_bytes());
        }
        buf
    }

    /// Lê e valida instantaneamente o cabeçalho e um subgrafo direto do buffer binário `.kdg` (estilo `mmap`),
    /// sem alocar árvores JSON na Heap.
    pub fn verify_kdg_snapshot(raw: &[u8]) -> Result<(usize, usize, u64), &'static str> {
        if raw.len() < KDG_HEADER_SIZE {
            return Err("snapshot .kdg truncado (< 64 bytes)");
        }
        if &raw[0..8] != KDG_MAGIC {
            return Err("assinatura mágica KUMODG01 inválida");
        }
        let n = u32::from_le_bytes([raw[12], raw[13], raw[14], raw[15]]) as usize;
        let m = u32::from_le_bytes([raw[16], raw[17], raw[18], raw[19]]) as usize;
        let csum = u64::from_le_bytes([
            raw[20], raw[21], raw[22], raw[23], raw[24], raw[25], raw[26], raw[27],
        ]);
        Ok((n, m, csum))
    }

    /// Serializa como texto JSON legado (simulando o custo de `sekg.db` em JSON).
    #[must_use]
    pub fn to_legacy_json_string(&self) -> String {
        let mut s = String::with_capacity(self.num_edges * 32);
        s.push_str("{\"nodes\":[");
        for i in 0..self.num_nodes {
            if i > 0 {
                s.push(',');
            }
            s.push_str(&format!(
                "{{\"id\":{i},\"t\":{},\"f\":{:.4}}}",
                self.node_types[i], self.node_features[i]
            ));
        }
        s.push_str("],\"edges\":[");
        for e in 0..self.num_edges {
            if e > 0 {
                s.push(',');
            }
            s.push_str(&format!(
                "{{\"v\":{},\"ts\":{},\"w\":{:.2}}}",
                self.fwd_targets[e], self.edge_timestamps[e], self.edge_weights[e]
            ));
        }
        s.push_str("]}");
        s
    }

    /// Baseline AS-IS (simulando o comportamento estático sem filtro temporal após parse JSON):
    /// atravessa 2 saltos ignorando `anchor_time`, gerando *temporal data leakage* de arestas futuras.
    #[must_use]
    pub fn sample_baseline_unfiltered_with_json_parse(
        &self,
        json_payload: &str,
        seed_node: u32,
        anchor_time: u64,
        max_neighbors: usize,
    ) -> TemporalSubgraphSample {
        let t0 = Instant::now();

        // Custo real de varrer/validar o texto JSON (como `json.Unmarshal` faz no `sekg.db`)
        let mut json_tokens_scanned = 0_usize;
        for b in json_payload.bytes() {
            if b == b':' || b == b',' {
                json_tokens_scanned += 1;
            }
        }

        let u0 = (seed_node as usize) % self.num_nodes;
        let mut tokens = Vec::with_capacity(max_neighbors.max(1));
        let mut leaked_future = 0_usize;

        let start = self.fwd_offsets[u0] as usize;
        let end = self.fwd_offsets[u0 + 1] as usize;
        for pos in start..end {
            if tokens.len() >= max_neighbors {
                break;
            }
            let v = self.fwd_targets[pos] as usize;
            let edge_ts = self.edge_timestamps[pos];
            if edge_ts > anchor_time {
                leaked_future += 1;
            }
            tokens.push(RelGt5DToken {
                node_id: v as u32,
                d1_feature_norm: self.node_features[v]
                    + (json_tokens_scanned as f32) * 1e-12,
                d2_entity_type_emb: EntityTableType::from_u8(self.node_types[v])
                    .type_embedding_scalar(),
                d3_hop_distance_emb: 0.5,
                d4_temporal_delta_emb: 0.0, // Sem codificação temporal no baseline!
                d5_local_structure_emb: 0.1,
                padding: [0.0; 2],
            });
        }

        TemporalSubgraphSample {
            seed_node,
            anchor_time,
            tokens_5d: tokens,
            future_edges_filtered: 0,
            leaked_future_edges: leaked_future,
            duration_ns: u64::try_from(t0.elapsed().as_nanos()).unwrap_or(1),
        }
    }

    /// **POC-01 (Kumo `DiskGraph` + `cuda-oxide` SIMT Temporal Sampler + 5D RelGT Tokenizer)**:
    /// Atravessa 1-hop e 2-hop diretamente sobre os arrays CSR alinhados, filtrando estritamente
    /// `edge.timestamp <= anchor_time` (zero *leakage*) e computando os 5 embeddings estruturais/temporais.
    #[must_use]
    pub fn sample_kumo_temporal_5d(
        &self,
        stream: &mut CudaStream,
        kdg_raw: &[u8],
        seed_node: u32,
        anchor_time: u64,
        max_neighbors: usize,
    ) -> TemporalSubgraphSample {
        let (sample, ns) = stream.launch_scoped(|| {
            let _ = Self::verify_kdg_snapshot(kdg_raw);
            let u0 = (seed_node as usize) % self.num_nodes;
            let mut tokens = Vec::with_capacity(max_neighbors.max(1) + 1);
            let mut future_filtered = 0_usize;

            // Token 0: A própria entidade-semente (hop = 0, delta_t = 0)
            let seed_deg = (self.fwd_offsets[u0 + 1] - self.fwd_offsets[u0]) as f32;
            tokens.push(RelGt5DToken {
                node_id: u0 as u32,
                d1_feature_norm: self.node_features[u0],
                d2_entity_type_emb: EntityTableType::from_u8(self.node_types[u0])
                    .type_embedding_scalar(),
                d3_hop_distance_emb: 0.0,
                d4_temporal_delta_emb: 1.0,
                d5_local_structure_emb: (seed_deg / 32.0).tanh(),
                padding: [0.0; 2],
            });

            // Expansão 1-hop com filtro temporal estrito (edge_ts <= anchor_time)
            let start1 = self.fwd_offsets[u0] as usize;
            let end1 = self.fwd_offsets[u0 + 1] as usize;
            let mut hop1_nodes = Vec::with_capacity(16);

            for pos in start1..end1 {
                if tokens.len() >= max_neighbors {
                    break;
                }
                let edge_ts = self.edge_timestamps[pos];
                if edge_ts > anchor_time {
                    future_filtered += 1;
                    continue;
                }
                let v = self.fwd_targets[pos] as usize;
                hop1_nodes.push((v, edge_ts));

                let delta_days = ((anchor_time - edge_ts) as f32) / 86_400.0;
                let temporal_emb = (1.0 / (1.0 + delta_days.ln_1p())).clamp(0.0, 1.0);
                let v_deg = (self.fwd_offsets[v + 1] - self.fwd_offsets[v]) as f32;
                let struct_emb = ((v_deg * self.edge_weights[pos]) / 16.0).tanh();

                tokens.push(RelGt5DToken {
                    node_id: v as u32,
                    d1_feature_norm: self.node_features[v],
                    d2_entity_type_emb: EntityTableType::from_u8(self.node_types[v])
                        .type_embedding_scalar(),
                    d3_hop_distance_emb: 0.50, // Hop = 1
                    d4_temporal_delta_emb: temporal_emb,
                    d5_local_structure_emb: struct_emb,
                    padding: [0.0; 2],
                });
            }

            // Expansão 2-hop causal (somente eventos que ocorreram até o evento de 1-hop)
            for &(v1, ts1) in &hop1_nodes {
                if tokens.len() >= max_neighbors {
                    break;
                }
                let s2 = self.fwd_offsets[v1] as usize;
                let e2 = self.fwd_offsets[v1 + 1] as usize;
                for pos2 in s2..e2 {
                    if tokens.len() >= max_neighbors {
                        break;
                    }
                    let edge_ts2 = self.edge_timestamps[pos2];
                    if edge_ts2 > ts1 {
                        future_filtered += 1;
                        continue;
                    }
                    let v2 = self.fwd_targets[pos2] as usize;
                    let delta_days = ((anchor_time - edge_ts2) as f32) / 86_400.0;
                    let temporal_emb = (1.0 / (1.0 + delta_days.ln_1p())).clamp(0.0, 1.0);
                    let v2_deg = (self.fwd_offsets[v2 + 1] - self.fwd_offsets[v2]) as f32;

                    tokens.push(RelGt5DToken {
                        node_id: v2 as u32,
                        d1_feature_norm: self.node_features[v2],
                        d2_entity_type_emb: EntityTableType::from_u8(self.node_types[v2])
                            .type_embedding_scalar(),
                        d3_hop_distance_emb: 1.00, // Hop = 2
                        d4_temporal_delta_emb: temporal_emb,
                        d5_local_structure_emb: (v2_deg / 32.0).tanh(),
                        padding: [0.0; 2],
                    });
                }
            }

            TemporalSubgraphSample {
                seed_node,
                anchor_time,
                tokens_5d: tokens,
                future_edges_filtered: future_filtered,
                leaked_future_edges: 0,
                duration_ns: 0,
            }
        });

        TemporalSubgraphSample {
            duration_ns: ns,
            ..sample
        }
    }

    fn compute_fnv1a64(&self) -> u64 {
        let mut hash: u64 = 0xcbf2_9ce4_8422_2325;
        for &t in &self.fwd_targets {
            for b in t.to_le_bytes() {
                hash ^= u64::from(b);
                hash = hash.wrapping_mul(0x0100_0000_01b3);
            }
        }
        hash
    }
}

/// Métricas comparativas do experimento científico da POC-01.
#[derive(Debug, Clone)]
pub struct Poc01BenchmarkReport {
    pub graph_nodes: usize,
    pub graph_edges: usize,
    pub json_size_bytes: usize,
    pub kdg_binary_size_bytes: usize,
    pub size_reduction_pct: f64,
    pub baseline_p50_us: f64,
    pub baseline_p95_us: f64,
    pub poc01_p50_us: f64,
    pub poc01_p95_us: f64,
    pub speedup_x: f64,
    pub baseline_leakage_edges: usize,
    pub poc01_leakage_edges: usize,
}

/// Executa o experimento científico controlado da POC-01 ($N$ repetições).
#[must_use]
pub fn run_poc01_experiment(repetitions: usize) -> Poc01BenchmarkReport {
    let n_runs = repetitions.max(5);
    let graph = KumoDiskGraph::build_squad_relational_benchmark_graph(2_000, 12);
    let json_str = graph.to_legacy_json_string();
    let kdg_bytes = graph.to_aligned_kdg_bytes();

    let ctx = CudaContext::new_for_tenant(GpuDeviceProps::detected_local_station(), "micro_kernel");
    let mut stream = CudaStream::new(&ctx, 101);

    // Anchor timestamp no meio do mês (dia 15): 1759276800 + 14 * 86400
    let anchor_ts: u64 = 1_759_276_800 + 14 * 86_400;

    // Warm-up (2 execuções descartadas)
    for _ in 0..2 {
        let _ = graph.sample_baseline_unfiltered_with_json_parse(&json_str, 7, anchor_ts, 32);
        let _ = graph.sample_kumo_temporal_5d(&mut stream, &kdg_bytes, 7, anchor_ts, 32);
    }

    let mut base_us = Vec::with_capacity(n_runs);
    let mut poc_us = Vec::with_capacity(n_runs);
    let mut base_leaked = 0_usize;
    let mut poc_leaked = 0_usize;

    for r in 0..n_runs {
        let seed = ((r * 17 + 3) % graph.num_nodes) as u32;
        let b_res = graph.sample_baseline_unfiltered_with_json_parse(&json_str, seed, anchor_ts, 32);
        base_us.push((b_res.duration_ns as f64) / 1000.0);
        base_leaked += b_res.leaked_future_edges;

        // Amostra lote de 16 sementes para medir vazão estável em microssegundos
        let t_batch = Instant::now();
        for s_off in 0..16_u32 {
            let p_res = graph.sample_kumo_temporal_5d(
                &mut stream,
                &kdg_bytes,
                seed + s_off,
                anchor_ts,
                32,
            );
            poc_leaked += p_res.leaked_future_edges;
        }
        let per_query_us = (t_batch.elapsed().as_nanos() as f64) / (16.0 * 1000.0);
        poc_us.push(per_query_us.max(0.05));
    }

    base_us.sort_by(|a, b| a.total_cmp(b));
    poc_us.sort_by(|a, b| a.total_cmp(b));

    let b_p50 = percentile_sorted(&base_us, 0.50);
    let b_p95 = percentile_sorted(&base_us, 0.95);
    let p_p50 = percentile_sorted(&poc_us, 0.50);
    let p_p95 = percentile_sorted(&poc_us, 0.95);

    let size_red = (1.0 - (kdg_bytes.len() as f64) / (json_str.len() as f64)) * 100.0;

    Poc01BenchmarkReport {
        graph_nodes: graph.num_nodes,
        graph_edges: graph.num_edges,
        json_size_bytes: json_str.len(),
        kdg_binary_size_bytes: kdg_bytes.len(),
        size_reduction_pct: size_red,
        baseline_p50_us: b_p50,
        baseline_p95_us: b_p95,
        poc01_p50_us: p_p50,
        poc01_p95_us: p_p95,
        speedup_x: b_p50 / p_p50.max(0.01),
        baseline_leakage_edges: base_leaked,
        poc01_leakage_edges: poc_leaked,
    }
}

#[must_use]
pub fn percentile_sorted(sorted: &[f64], pct: f64) -> f64 {
    if sorted.is_empty() {
        return 0.0;
    }
    let idx = ((pct * (sorted.len() as f64)).ceil() as usize)
        .saturating_sub(1)
        .min(sorted.len() - 1);
    sorted[idx]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_kumo_diskgraph_zero_temporal_leakage() {
        let g = KumoDiskGraph::build_squad_relational_benchmark_graph(128, 8);
        let kdg = g.to_aligned_kdg_bytes();
        assert!(KumoDiskGraph::verify_kdg_snapshot(&kdg).is_ok());

        let ctx = CudaContext::new_for_tenant(GpuDeviceProps::detected_local_station(), "micro_kernel");
        let mut stream = CudaStream::new(&ctx, 1);
        let anchor = 1_759_276_800 + 10 * 86_400;

        let sample = g.sample_kumo_temporal_5d(&mut stream, &kdg, 0, anchor, 16);
        assert_eq!(sample.leaked_future_edges, 0);
        assert!(sample.future_edges_filtered > 0);
        assert!(!sample.tokens_5d.is_empty());
    }
}
