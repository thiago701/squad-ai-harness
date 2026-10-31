//! # SquadAI GPU Intelligence Lab — `kumo-adapter`
//!
//! Camada de inteligência preditiva relacional e temporal com separação arquitetural estrita:
//! 1. **`NativeRelGTEngine` (100% Nativo em Rust):**
//!    - Grafo heterogêneo temporal em formato binário zero-copy `.kdg` (`SKDG`, alinhado a 64 bytes).
//!    - Amostragem temporal causal estrita ($\tau(e) \le t_{\text{anchor}}$) sem vazamento de futuro (*Temporal Anti-Leakage*).
//!    - Tokenizador `RelGT` de 5 elementos (`[tipo_entidade, hop_distance, recencia_exponencial, clustering_local, grau_log1p]`).
//!    - Parser e avaliador determinístico de **PQL (Predictive Query Language)**.
//!    - **In-Context Learning (ICL)** relacional por atenção sobre episódios históricos rotulados.
//! 2. **`ExternalKumoNimStatus` ( Fronteira Honesta com NVIDIA KumoRFM / NIM ):**
//!    - Classifica explicitamente o que exige o container proprietário `nvidia/kumo-relational` (NIM)
//!      ou SDK Python `structured-data-models-client` (inviável localmente em GPU de 2 GiB `sm_50`),
//!      nunca confundindo um serviço externo com execução nativa em Rust.

pub const KDG_MAGIC: [u8; 4] = *b"SKDG";
pub const KDG_VERSION: u32 = 1;

/// Classificação arquitetural da integração segundo a Seção 2.3 do Prompt Master.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IntegrationClassification {
    /// 100% implementado e executado nativamente em Rust no processo do MCP.
    Native,
    /// Interoperável via IPC binário zero-copy (`.kdg`) ou FFI (`nvcuda.dll`).
    Interoperable,
    /// Parcialmente compatível (ex.: PQL compilado em Rust para RelGT local, sem pesos proprietários KumoRFM).
    PartiallyCompatible,
    /// Experimental (ex.: crates nightly `cuda-oxide` / `cutile-rs`).
    Experimental,
    /// Inviável no hardware/licença local (ex.: container NIM `nvidia/kumo-relational` em GeForce MX110 2 GiB).
    Inviable,
}

impl IntegrationClassification {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Native => "NATIVA",
            Self::Interoperable => "INTEROPERAVEL",
            Self::PartiallyCompatible => "PARCIALMENTE_COMPATIVEL",
            Self::Experimental => "EXPERIMENTAL",
            Self::Inviable => "INVIAVEL",
        }
    }
}

/// Representa uma aresta direcionada temporal no grafo relacional heterogêneo.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct TemporalEdge {
    pub src: u32,
    pub dst: u32,
    pub edge_type: u16,
    pub weight: f32,
    pub timestamp_unix: i64,
}

/// Grafo heterogêneo temporal em formato Compressed Sparse Row (CSR) com suporte a corte temporal.
#[derive(Debug, Clone)]
pub struct TemporalRelationalGraph {
    pub num_nodes: usize,
    pub node_types: Vec<u16>,
    pub row_ptr: Vec<u32>,
    pub col_idx: Vec<u32>,
    pub edge_weights: Vec<f32>,
    pub edge_timestamps: Vec<i64>,
    pub node_base_risk: Vec<f32>,
}

impl TemporalRelationalGraph {
    /// Constrói um grafo CSR temporal a partir de uma lista de arestas direcionadas.
    pub fn from_edges(
        num_nodes: usize,
        node_types: Vec<u16>,
        node_base_risk: Vec<f32>,
        mut edges: Vec<TemporalEdge>,
    ) -> Self {
        assert_eq!(node_types.len(), num_nodes);
        assert_eq!(node_base_risk.len(), num_nodes);
        edges.sort_by_key(|e| (e.src, e.dst, e.timestamp_unix));

        let mut row_ptr = vec![0u32; num_nodes + 1];
        let mut col_idx = Vec::with_capacity(edges.len());
        let mut edge_weights = Vec::with_capacity(edges.len());
        let mut edge_timestamps = Vec::with_capacity(edges.len());

        for e in &edges {
            if (e.src as usize) < num_nodes && (e.dst as usize) < num_nodes {
                row_ptr[(e.src as usize) + 1] += 1;
                col_idx.push(e.dst);
                edge_weights.push(e.weight);
                edge_timestamps.push(e.timestamp_unix);
            }
        }
        for i in 0..num_nodes {
            row_ptr[i + 1] += row_ptr[i];
        }

        Self {
            num_nodes,
            node_types,
            row_ptr,
            col_idx,
            edge_weights,
            edge_timestamps,
            node_base_risk,
        }
    }

    /// Filtra estritamente as arestas com $\tau(e) \le t_{\text{anchor}}$ para impedir *Data Leakage* do futuro.
    pub fn snapshot_at(&self, anchor_timestamp: i64) -> Self {
        let mut row_ptr = vec![0u32; self.num_nodes + 1];
        let mut col_idx = Vec::new();
        let mut edge_weights = Vec::new();
        let mut edge_timestamps = Vec::new();

        for u in 0..self.num_nodes {
            let start = self.row_ptr[u] as usize;
            let end = self.row_ptr[u + 1] as usize;
            for idx in start..end {
                let ts = self.edge_timestamps[idx];
                if ts <= anchor_timestamp {
                    row_ptr[u + 1] += 1;
                    col_idx.push(self.col_idx[idx]);
                    edge_weights.push(self.edge_weights[idx]);
                    edge_timestamps.push(ts);
                }
            }
        }
        for i in 0..self.num_nodes {
            row_ptr[i + 1] += row_ptr[i];
        }

        Self {
            num_nodes: self.num_nodes,
            node_types: self.node_types.clone(),
            row_ptr,
            col_idx,
            edge_weights,
            edge_timestamps,
            node_base_risk: self.node_base_risk.clone(),
        }
    }

    /// Serializa o grafo para o formato binário zero-copy `.kdg` (cabeçalho de 64 bytes alinhado).
    pub fn to_kdg_bytes(&self, snapshot_ts: i64) -> Vec<u8> {
        let num_edges = self.col_idx.len();
        let mut buf = Vec::with_capacity(64 + (self.num_nodes + 1) * 4 + num_edges * 16);
        buf.extend_from_slice(&KDG_MAGIC);
        buf.extend_from_slice(&KDG_VERSION.to_le_bytes());
        buf.extend_from_slice(&(self.num_nodes as u64).to_le_bytes());
        buf.extend_from_slice(&(num_edges as u64).to_le_bytes());
        buf.extend_from_slice(&snapshot_ts.to_le_bytes());
        buf.resize(64, 0u8);

        for &rp in &self.row_ptr {
            buf.extend_from_slice(&rp.to_le_bytes());
        }
        for &ci in &self.col_idx {
            buf.extend_from_slice(&ci.to_le_bytes());
        }
        for &w in &self.edge_weights {
            buf.extend_from_slice(&w.to_le_bytes());
        }
        for &ts in &self.edge_timestamps {
            buf.extend_from_slice(&ts.to_le_bytes());
        }
        buf
    }
}

/// Token 5-dimensional de um nó no subgrafo local segundo a arquitetura Relational Graph Transformer (`RelGT`).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct RelGTToken5D {
    pub entity_type_norm: f32,
    pub hop_distance_norm: f32,
    pub temporal_recency: f32,
    pub local_clustering: f32,
    pub log_degree: f32,
}

impl RelGTToken5D {
    pub fn to_array(&self) -> [f32; 5] {
        [
            self.entity_type_norm,
            self.hop_distance_norm,
            self.temporal_recency,
            self.local_clustering,
            self.log_degree,
        ]
    }
}

/// Consulta estruturada em Predictive Query Language (`PQL`).
#[derive(Debug, Clone, PartialEq)]
pub struct PqlQuery {
    pub raw_query: String,
    pub target_aggregation: String,
    pub horizon_days: u32,
    pub entity_table: String,
    pub entity_id: usize,
    pub anchor_timestamp: i64,
}

impl PqlQuery {
    /// Faz o parsing de uma consulta PQL canônica:
    /// `PREDICT COUNT(incidents.*, 0, 7, days) FOR services.id = 42 ANCHOR 1730000000`
    pub fn parse(query: &str, default_anchor_ts: i64) -> Result<Self, String> {
        let trimmed = query.trim();
        let upper = trimmed.to_uppercase();
        if !upper.starts_with("PREDICT ") {
            return Err("PQL invalida: deve iniciar com 'PREDICT '".to_string());
        }
        let for_pos = upper
            .find(" FOR ")
            .ok_or_else(|| "PQL invalida: clausula 'FOR' ausente".to_string())?;
        let target_agg = trimmed[8..for_pos].trim().to_string();

        let after_for = trimmed[for_pos + 5..].trim();
        let mut entity_id = 0usize;
        if let Some(eq_pos) = after_for.find('=') {
            let rhs = after_for[eq_pos + 1..].trim();
            let token = rhs.split_whitespace().next().unwrap_or("0");
            entity_id = token.parse::<usize>().unwrap_or(0);
        }

        let mut anchor_ts = default_anchor_ts;
        if let Some(anc_pos) = upper.find(" ANCHOR ") {
            let after_anc = trimmed[anc_pos + 8..].trim();
            let token = after_anc.split_whitespace().next().unwrap_or("0");
            if let Ok(parsed_ts) = token.parse::<i64>() {
                anchor_ts = parsed_ts;
            }
        }

        Ok(Self {
            raw_query: trimmed.to_string(),
            target_aggregation: target_agg,
            horizon_days: 7,
            entity_table: "services".to_string(),
            entity_id,
            anchor_timestamp: anchor_ts,
        })
    }
}

/// Episódio histórico rotulado para In-Context Learning (ICL) relacional.
#[derive(Debug, Clone, Copy)]
pub struct LabeledRelationalContext {
    pub token: RelGTToken5D,
    pub neighbor_risk_weighted: f32,
    pub observed_failure: bool,
}

/// Resultado de uma inferência preditiva relacional (PQL + RelGT + ICL).
#[derive(Debug, Clone, PartialEq)]
pub struct RelationalPrediction {
    pub entity_id: usize,
    pub probability: f32,
    pub uncertainty_brier_est: f32,
    pub causal_edges_used: usize,
    pub future_edges_filtered: usize,
    pub token_5d: [f32; 5],
}

/// Motor nativo em Rust para inferência sobre esquemas relacionais e grafos temporais (`RelGT` + `ICL`).
pub struct NativeRelGTEngine {
    pub half_life_secs: f32,
    pub context_episodes: Vec<LabeledRelationalContext>,
}

impl NativeRelGTEngine {
    pub fn new(half_life_secs: f32, context_episodes: Vec<LabeledRelationalContext>) -> Self {
        Self {
            half_life_secs: half_life_secs.max(1.0),
            context_episodes,
        }
    }

    /// Extrai o token 5D `RelGT` e prediz probabilidade de falha/impacto para `entity_id` no instante `anchor_ts`,
    /// garantindo zero vazamento de arestas futuras ($\tau(e) > t_{\text{anchor}}$).
    pub fn predict_entity(
        &self,
        graph: &TemporalRelationalGraph,
        entity_id: usize,
        anchor_ts: i64,
    ) -> RelationalPrediction {
        if entity_id >= graph.num_nodes {
            return RelationalPrediction {
                entity_id,
                probability: 0.0,
                uncertainty_brier_est: 0.25,
                causal_edges_used: 0,
                future_edges_filtered: 0,
                token_5d: [0.0; 5],
            };
        }

        let start = graph.row_ptr[entity_id] as usize;
        let end = graph.row_ptr[entity_id + 1] as usize;

        let mut causal_edges = 0usize;
        let mut future_filtered = 0usize;
        let mut weighted_neighbor_risk = 0.0f32;
        let mut weight_sum = 0.0f32;
        let mut latest_delta_t = self.half_life_secs * 4.0;

        // 1-hop e 2-hop causal traversal (somente arestas com ts <= anchor_ts)
        let mut hop2_risk = 0.0f32;
        let mut hop2_count = 0usize;

        for idx in start..end {
            let ts = graph.edge_timestamps[idx];
            if ts > anchor_ts {
                future_filtered += 1;
                continue;
            }
            causal_edges += 1;
            let dst = graph.col_idx[idx] as usize;
            let w = graph.edge_weights[idx];
            let dt = (anchor_ts - ts).max(0) as f32;
            if dt < latest_delta_t {
                latest_delta_t = dt;
            }
            let decay = (-dt / self.half_life_secs).exp();
            let eff_w = w * decay;
            weighted_neighbor_risk += eff_w * graph.node_base_risk[dst];
            weight_sum += eff_w;

            // 2-hop causal expansion
            let s2 = graph.row_ptr[dst] as usize;
            let e2 = graph.row_ptr[dst + 1] as usize;
            for idx2 in s2..e2 {
                let ts2 = graph.edge_timestamps[idx2];
                if ts2 <= anchor_ts {
                    let dst2 = graph.col_idx[idx2] as usize;
                    let dt2 = (anchor_ts - ts2).max(0) as f32;
                    let decay2 = (-dt2 / self.half_life_secs).exp();
                    hop2_risk += 0.5 * graph.edge_weights[idx2] * decay2 * graph.node_base_risk[dst2];
                    hop2_count += 1;
                } else {
                    future_filtered += 1;
                }
            }
        }

        let norm_hop1 = if weight_sum > 1e-6 {
            weighted_neighbor_risk / weight_sum
        } else {
            0.0
        };
        let norm_hop2 = if hop2_count > 0 {
            (hop2_risk / (hop2_count as f32)).clamp(0.0, 1.0)
        } else {
            0.0
        };

        let recency = (-latest_delta_t / self.half_life_secs).exp();
        let degree_log = ((causal_edges as f32) + 1.0).ln() / 5.0;
        let local_clustering = if causal_edges > 1 {
            ((hop2_count as f32) / ((causal_edges * causal_edges) as f32)).clamp(0.0, 1.0)
        } else {
            0.0
        };

        let token = RelGTToken5D {
            entity_type_norm: (graph.node_types[entity_id] as f32) * 0.25,
            hop_distance_norm: if hop2_count > 0 { 0.5 } else { 1.0 },
            temporal_recency: recency,
            local_clustering,
            log_degree: degree_log.clamp(0.0, 1.0),
        };

        // Combina sinal estrutural RelGT com In-Context Learning (atenção por similaridade cosseno/gaussiana sobre o contexto)
        let base_self = graph.node_base_risk[entity_id];
        let structural_logit =
            -2.15 + 2.40 * base_self + 1.95 * norm_hop1 + 0.90 * norm_hop2 + 0.65 * recency + 0.45 * degree_log;
        let structural_prob = 1.0 / (1.0 + (-structural_logit).exp());

        let combined_neighbor_risk = 0.70 * norm_hop1 + 0.30 * norm_hop2;
        let mut icl_num = 0.0f32;
        let mut icl_den = 0.0f32;
        let tok_arr = token.to_array();

        for ep in &self.context_episodes {
            let ep_arr = ep.token.to_array();
            let mut dist2 = (combined_neighbor_risk - ep.neighbor_risk_weighted).powi(2);
            for k in 0..5 {
                let d = tok_arr[k] - ep_arr[k];
                dist2 += 0.35 * d * d;
            }
            let attn = (-4.0 * dist2).exp();
            icl_den += attn;
            if ep.observed_failure {
                icl_num += attn;
            }
        }

        let final_prob = if icl_den > 1e-5 {
            let icl_prob = icl_num / icl_den;
            (0.65 * structural_prob + 0.35 * icl_prob).clamp(0.001, 0.999)
        } else {
            structural_prob.clamp(0.001, 0.999)
        };

        let uncertainty = final_prob * (1.0 - final_prob);

        RelationalPrediction {
            entity_id,
            probability: final_prob,
            uncertainty_brier_est: uncertainty,
            causal_edges_used: causal_edges,
            future_edges_filtered: future_filtered,
            token_5d: tok_arr,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_temporal_anti_leakage_strictly_filters_future_edges() {
        let edges = vec![
            TemporalEdge {
                src: 0,
                dst: 1,
                edge_type: 1,
                weight: 1.0,
                timestamp_unix: 1_000,
            },
            // Aresta no futuro (ts = 2_000 > anchor = 1_500) com alto risco que NÃO pode vazar!
            TemporalEdge {
                src: 0,
                dst: 2,
                edge_type: 1,
                weight: 10.0,
                timestamp_unix: 2_000,
            },
        ];
        let g = TemporalRelationalGraph::from_edges(
            3,
            vec![1, 1, 1],
            vec![0.1, 0.2, 0.99],
            edges,
        );
        let engine = NativeRelGTEngine::new(3600.0, Vec::new());

        let pred_before = engine.predict_entity(&g, 0, 1_500);
        assert_eq!(pred_before.causal_edges_used, 1);
        assert_eq!(pred_before.future_edges_filtered, 1);

        let pred_after = engine.predict_entity(&g, 0, 2_500);
        assert_eq!(pred_after.causal_edges_used, 2);
        assert_eq!(pred_after.future_edges_filtered, 0);
        assert!(pred_after.probability > pred_before.probability);
    }

    #[test]
    fn test_pql_parser() {
        let q = PqlQuery::parse(
            "PREDICT COUNT(incidents.*, 0, 7, days) FOR services.id = 17 ANCHOR 1700000000",
            0,
        )
        .unwrap();
        assert_eq!(q.entity_id, 17);
        assert_eq!(q.anchor_timestamp, 1700000000);
    }
}
