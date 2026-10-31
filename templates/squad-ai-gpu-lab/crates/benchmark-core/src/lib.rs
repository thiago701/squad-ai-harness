//! # SquadAI GPU Intelligence Lab — `benchmark-core`
//!
//! Motor estatístico e avaliador científico do laboratório (Seções 8 e 10 do Prompt Master).
//! - Calcula `mean`, `median (p50)`, `p95`, `p99`, `std_dev` e intervalo de confiança de 95% (`ci95`).
//! - Separa **ganho de kernel isolado** de **ganho real fim a fim** (incluindo MCP + serialização + HtoD/DtoH).
//! - Aplica o modelo de pontuação ponderada `0–100` (30/25/15/10/10/10) e classifica cada POC.

use telemetry::PredictiveQualityMetrics;

/// Estatísticas descritivas completas de uma distribuição de latências em microssegundos ($\mu\text{s}$).
#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct DistributionStats {
    pub samples: usize,
    pub mean_us: f64,
    pub p50_us: f64,
    pub p95_us: f64,
    pub p99_us: f64,
    pub min_us: f64,
    pub max_us: f64,
    pub std_dev_us: f64,
    pub ci95_half_width_us: f64,
}

impl DistributionStats {
    pub fn from_samples(raw: &[f64]) -> Self {
        if raw.is_empty() {
            return Self::default();
        }
        let mut sorted: Vec<f64> = raw.iter().copied().collect();
        sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

        let n = sorted.len();
        let sum: f64 = sorted.iter().sum();
        let mean = sum / (n as f64);

        let var_sum: f64 = sorted.iter().map(|&x| (x - mean) * (x - mean)).sum();
        let variance = if n > 1 {
            var_sum / ((n - 1) as f64)
        } else {
            0.0
        };
        let std_dev = variance.sqrt();
        let ci95 = 1.96 * std_dev / (n as f64).sqrt();

        let percentile = |p: f64| -> f64 {
            let idx = ((p * ((n - 1) as f64)).round() as usize).min(n - 1);
            sorted[idx]
        };

        Self {
            samples: n,
            mean_us: mean,
            p50_us: percentile(0.50),
            p95_us: percentile(0.95),
            p99_us: percentile(0.99),
            min_us: sorted[0],
            max_us: sorted[n - 1],
            std_dev_us: std_dev,
            ci95_half_width_us: ci95,
        }
    }
}

/// Tamanho padronizado da carga de trabalho (Seção 8.2 do Prompt Master).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WorkloadScale {
    Small,
    Medium,
    Large,
    ExtraLarge,
}

impl WorkloadScale {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Small => "Small",
            Self::Medium => "Medium",
            Self::Large => "Large",
            Self::ExtraLarge => "XL",
        }
    }
}

/// Comparação experimental completa entre os Grupos A–H para uma POC em uma escala de carga.
#[derive(Debug, Clone)]
pub struct WorkloadBenchmarkRecord {
    pub poc_id: String,
    pub scale: WorkloadScale,
    pub workload_description: String,
    /// Grupo A: Baseline atual da SquadAI em Go (ou equivalente algorítmico exato).
    pub group_a_go_baseline_us: DistributionStats,
    /// Grupo B: Go otimizado.
    pub group_b_go_optimized_us: DistributionStats,
    /// Grupo C: Rust CPU single-thread.
    pub group_c_rust_cpu_single_us: DistributionStats,
    /// Grupo D: Rust CPU multi-thread paralelo.
    pub group_d_rust_cpu_parallel_us: DistributionStats,
    /// Grupo E/F/H: GPU CUDA Kernel puro (sem HtoD/DtoH).
    pub gpu_kernel_only_us: DistributionStats,
    /// GPU CUDA com transferência PCIe por chamada (`HtoD + Kernel + DtoH`).
    pub gpu_with_pcie_transfer_us: DistributionStats,
    /// GPU CUDA com buffers/pesos residentes na VRAM (apenas query/delta trafega).
    pub gpu_resident_vram_us: DistributionStats,
    /// Latência Real Fim a Fim via MCP (`Go -> MCP JSON-RPC / .kdg -> Rust/GPU -> Resposta`).
    pub end_to_end_mcp_us: DistributionStats,
    pub vram_used_bytes: usize,
    pub ram_used_bytes: usize,
}

impl WorkloadBenchmarkRecord {
    /// Speedup de kernel isolado contra o baseline Go (Grupo A).
    pub fn kernel_vs_go_speedup(&self) -> f64 {
        if self.gpu_kernel_only_us.p50_us <= 0.0 {
            return 0.0;
        }
        self.group_a_go_baseline_us.p50_us / self.gpu_kernel_only_us.p50_us
    }

    /// Speedup REAL fim a fim (incluindo IPC MCP) do melhor caminho proposto contra o baseline Go (Grupo A).
    pub fn end_to_end_vs_go_speedup(&self) -> f64 {
        if self.end_to_end_mcp_us.p50_us <= 0.0 {
            return 0.0;
        }
        self.group_a_go_baseline_us.p50_us / self.end_to_end_mcp_us.p50_us
    }

    /// Speedup da GPU Residente contra o Rust CPU Paralelo (Grupo D) — mede se a GPU realmente vence a CPU Rust!
    pub fn gpu_resident_vs_rust_parallel_speedup(&self) -> f64 {
        if self.gpu_resident_vram_us.p50_us <= 0.0 {
            return 0.0;
        }
        self.group_d_rust_cpu_parallel_us.p50_us / self.gpu_resident_vram_us.p50_us
    }
}

/// Categorias oficiais de recomendação (Seção 10.2 do Prompt Master).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RecommendationCategory {
    StrongIntegrationCandidate,
    PromisingNeedsEvolution,
    UsefulOnlyInSpecificScenarios,
    NotSuperiorToCurrentBaseline,
    DiscardedByCostOrComplexity,
}

impl RecommendationCategory {
    pub fn label_pt(&self) -> &'static str {
        match self {
            Self::StrongIntegrationCandidate => "Candidato forte para futura integracao",
            Self::PromisingNeedsEvolution => "Promissor, mas exige evolucao adicional",
            Self::UsefulOnlyInSpecificScenarios => "Util apenas em cenarios especificos",
            Self::NotSuperiorToCurrentBaseline => "Nao superior ao baseline atual",
            Self::DiscardedByCostOrComplexity => "Descartado por custo, complexidade ou baixo retorno",
        }
    }
}

/// Avaliação científica ponderada `0–100` (Seção 10.1 do Prompt Master).
#[derive(Debug, Clone)]
pub struct ScientificPocEvaluation {
    pub poc_id: String,
    pub poc_name: String,
    pub primary_tech: String,
    /// 1. Ganho de Desempenho Real Fim a Fim (Peso 30%): nota 0..100
    pub score_perf_end_to_end: f64,
    /// 2. Impacto Operacional na SquadAI (Peso 25%): nota 0..100
    pub score_operational_impact: f64,
    /// 3. Qualidade, Precisão ou Inteligência Preditiva (Peso 15%): nota 0..100
    pub score_quality_precision: f64,
    /// 4. Eficiência de Recursos e Custo (Peso 10%): nota 0..100
    pub score_resource_efficiency: f64,
    /// 5. Diferencial Tecnológico Comprovado CUDA/Kumo (Peso 10%): nota 0..100
    pub score_tech_differential: f64,
    /// 6. Viabilidade Técnica, Maturidade e Segurança (Peso 10%): nota 0..100
    pub score_viability_maturity: f64,
    /// Atribuição explícita do ganho: quanto veio de Rust vs CUDA vs Kumo vs Integração.
    pub attribution_rust_pct: u8,
    pub attribution_cuda_pct: u8,
    pub attribution_kumo_pct: u8,
    pub attribution_integration_pct: u8,
    pub predictive_metrics: Option<PredictiveQualityMetrics>,
    pub recommendation: RecommendationCategory,
    pub honest_verdict: String,
}

impl ScientificPocEvaluation {
    /// Calcula a nota composta ponderada (`0.0` a `100.0`) segundo os pesos estritos da Seção 10.1.
    pub fn composite_score(&self) -> f64 {
        0.30 * self.score_perf_end_to_end
            + 0.25 * self.score_operational_impact
            + 0.15 * self.score_quality_precision
            + 0.10 * self.score_resource_efficiency
            + 0.10 * self.score_tech_differential
            + 0.10 * self.score_viability_maturity
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_distribution_stats_and_composite_score() {
        let samples = vec![10.0, 12.0, 11.0, 13.0, 14.0, 100.0];
        let st = DistributionStats::from_samples(&samples);
        assert_eq!(st.samples, 6);
        assert!(st.p50_us >= 11.0 && st.p50_us <= 13.0);
        assert!(st.p99_us >= 90.0);

        let ev = ScientificPocEvaluation {
            poc_id: "POC-001".to_string(),
            poc_name: "Test".to_string(),
            primary_tech: "Rust + Kumo RelGT".to_string(),
            score_perf_end_to_end: 80.0,
            score_operational_impact: 90.0,
            score_quality_precision: 85.0,
            score_resource_efficiency: 90.0,
            score_tech_differential: 75.0,
            score_viability_maturity: 85.0,
            attribution_rust_pct: 40,
            attribution_cuda_pct: 0,
            attribution_kumo_pct: 50,
            attribution_integration_pct: 10,
            predictive_metrics: None,
            recommendation: RecommendationCategory::StrongIntegrationCandidate,
            honest_verdict: "Aprovado".to_string(),
        };
        let total = ev.composite_score();
        assert!((total - 84.25).abs() < 1e-6);
    }
}
