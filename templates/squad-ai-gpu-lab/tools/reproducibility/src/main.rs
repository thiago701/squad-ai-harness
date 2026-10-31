use benchmark_core::DistributionStats;
use cpu_baselines::{
    cpu_batch_dot_parallel, cpu_batch_dot_single, cpu_batch_risk_fusion_parallel,
    cpu_batch_risk_fusion_single, cpu_csr_pagerank_parallel, cpu_csr_pagerank_single,
    cpu_gemm_parallel, cpu_gemm_single, cpu_unfused_risk_pipeline_single,
};
use gpu_runtime::CudaContext;
use mcp_server::LabMcpServer;
use std::time::Instant;

fn measure_us<F: FnMut()>(repeats: usize, mut f: F) -> DistributionStats {
    // 2 warm-up iterations
    for _ in 0..2 {
        f();
    }
    let mut samples = Vec::with_capacity(repeats);
    for _ in 0..repeats {
        let t0 = Instant::now();
        f();
        samples.push(t0.elapsed().as_secs_f64() * 1_000_000.0);
    }
    DistributionStats::from_samples(&samples)
}

fn main() {
    let repeats = 20usize;
    let mut cuda_ctx = CudaContext::try_new().ok();
    let gpu_profile = cuda_ctx
        .as_ref()
        .map(|c| c.profile.clone())
        .unwrap_or_else(gpu_runtime::probe_gpu_device);
    let cold_ctx_us = cuda_ctx.as_ref().map(|c| c.cold_init_us).unwrap_or(0.0);

    // 1. Medição de IPC: Loopback TCP Keep-Alive vs In-Process JSON-RPC
    let mut mcp_srv = LabMcpServer::new();
    let tcp_ipc_samples = mcp_srv.benchmark_tcp_keepalive_ipc(repeats);
    let tcp_ipc_stats = DistributionStats::from_samples(&tcp_ipc_samples);
    let inproc_jsonrpc_stats = measure_us(repeats, || {
        let _ = mcp_srv.handle_jsonrpc_line(
            r#"{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"lab_gpu_probe"}}"#,
        );
    });

    // 2. POC-006 / POC-003: Semantic Retrieval & Batch Vector Dot Product (D=128) em 4 escalas:
    // Small (106 skills), Medium (1.024 chunks), Large (8.192 chunks), XL (32.768 chunks)
    let retrieval_scales = [
        ("Small_106x128", 106usize),
        ("Medium_1024x128", 1024usize),
        ("Large_8192x128", 8192usize),
        ("XL_32768x128", 32768usize),
    ];

    println!("=== SQUAD-AI GPU INTELLIGENCE LAB — SCIENTIFIC BENCHMARK SUITE ===");
    println!(
        "Hardware: GPU={} (arch={}, VRAM={} MiB, Driver={}), ColdInit={:.1} us",
        gpu_profile.device_name,
        gpu_profile.sm_arch(),
        gpu_profile.total_vram_mb(),
        gpu_profile.driver_version,
        cold_ctx_us
    );
    println!(
        "IPC Overhead (N={}): InProc_JSONRPC p50={:.2} us (p95={:.2} us) | TCP_Loopback_KeepAlive p50={:.2} us (p95={:.2} us)",
        repeats,
        inproc_jsonrpc_stats.p50_us,
        inproc_jsonrpc_stats.p95_us,
        tcp_ipc_stats.p50_us,
        tcp_ipc_stats.p95_us
    );

    println!("\n--- [1] BATCH DOT PRODUCT / SEMANTIC RETRIEVAL (D=128) ---");
    for &(label, n) in &retrieval_scales {
        let d = 128usize;
        let docs = vec![0.15f32; n * d];
        let query = vec![0.25f32; d];

        let cpu_s = measure_us(repeats, || {
            let v = cpu_batch_dot_single(&docs, &query, n, d);
            std::hint::black_box(v);
        });
        let cpu_p = measure_us(repeats, || {
            let v = cpu_batch_dot_parallel(&docs, &query, n, d);
            std::hint::black_box(v);
        });

        let mut gpu_unamort_kern = Vec::new();
        let mut gpu_unamort_tot = Vec::new();
        let mut gpu_res_kern = Vec::new();
        let mut gpu_res_tot = Vec::new();

        if let Some(ref mut ctx) = cuda_ctx {
            let _ = ctx.execute_batch_dot_f32(&docs, &query, n, d, false);
            for _ in 0..repeats {
                if let Ok((_, m)) = ctx.execute_batch_dot_f32(&docs, &query, n, d, false) {
                    gpu_unamort_kern.push(m.kernel_us);
                    gpu_unamort_tot.push(m.total_gpu_us);
                }
            }
            let _ = ctx.preload_resident_corpus(&docs);
            let _ = ctx.execute_batch_dot_f32(&docs, &query, n, d, true);
            for _ in 0..repeats {
                if let Ok((_, m)) = ctx.execute_batch_dot_f32(&docs, &query, n, d, true) {
                    gpu_res_kern.push(m.kernel_us);
                    gpu_res_tot.push(m.total_gpu_us);
                }
            }
        }

        let st_uk = DistributionStats::from_samples(&gpu_unamort_kern);
        let st_ut = DistributionStats::from_samples(&gpu_unamort_tot);
        let st_rk = DistributionStats::from_samples(&gpu_res_kern);
        let st_rt = DistributionStats::from_samples(&gpu_res_tot);

        println!(
            "{}: CPU_Single p50={:.2}us (p95={:.2}) | CPU_Par p50={:.2}us (p95={:.2}) | GPU_Kernel p50={:.2}us | GPU_Unamort_Total p50={:.2}us | GPU_Resident_Total p50={:.2}us (p95={:.2})",
            label,
            cpu_s.p50_us,
            cpu_s.p95_us,
            cpu_p.p50_us,
            cpu_p.p95_us,
            st_rk.p50_us.max(st_uk.p50_us),
            st_ut.p50_us,
            st_rt.p50_us,
            st_rt.p95_us
        );
    }

    // 3. POC-008: Tiled GEMM Matrix Multiplication (Small 64x64, Medium 128x128, Large 256x256, XL 512x512)
    println!("\n--- [2] TILED GEMM MATRIX MULTIPLICATION (M=N=K) ---");
    for &dim in &[64usize, 128, 256, 512] {
        let a = vec![0.1f32; dim * dim];
        let b = vec![0.2f32; dim * dim];
        let rep = if dim >= 512 { 8 } else { repeats };

        let cpu_s = measure_us(rep, || {
            let c = cpu_gemm_single(&a, &b, dim, dim, dim);
            std::hint::black_box(c);
        });
        let cpu_p = measure_us(rep, || {
            let c = cpu_gemm_parallel(&a, &b, dim, dim, dim);
            std::hint::black_box(c);
        });

        let mut gpu_k = Vec::new();
        let mut gpu_ut = Vec::new();
        let mut gpu_rt = Vec::new();
        if let Some(ref mut ctx) = cuda_ctx {
            let _ = ctx.execute_tiled_gemm_f32(&a, &b, dim, dim, dim, false);
            for _ in 0..rep {
                if let Ok((_, m)) = ctx.execute_tiled_gemm_f32(&a, &b, dim, dim, dim, false) {
                    gpu_k.push(m.kernel_us);
                    gpu_ut.push(m.total_gpu_us);
                }
                if let Ok((_, m_res)) = ctx.execute_tiled_gemm_f32(&a, &b, dim, dim, dim, true) {
                    gpu_rt.push(m_res.total_gpu_us);
                }
            }
        }
        let st_k = DistributionStats::from_samples(&gpu_k);
        let st_ut = DistributionStats::from_samples(&gpu_ut);
        let st_rt = DistributionStats::from_samples(&gpu_rt);
        println!(
            "GEMM_{}x{}: CPU_Single p50={:.2}us (p95={:.2}) | CPU_Par p50={:.2}us (p95={:.2}) | GPU_Kernel p50={:.2}us | GPU_Unamort p50={:.2}us | GPU_ResidentB p50={:.2}us (p95={:.2})",
            dim,
            dim,
            cpu_s.p50_us,
            cpu_s.p95_us,
            cpu_p.p50_us,
            cpu_p.p95_us,
            st_k.p50_us,
            st_ut.p50_us,
            st_rt.p50_us,
            st_rt.p95_us
        );
    }

    // 4. POC-004: CSR PageRank 20 Iterations (Small 256, Medium 2048, Large 16384, XL 65536 nodes, deg=16)
    println!("\n--- [3] CSR PAGERANK 20 ITERATIONS (DEGREE=16) ---");
    for &nodes in &[256usize, 2048, 16384, 65536] {
        let (rp, ci, w) = poc_004_cognitive_graph_accel::build_synthetic_sekg_csr(nodes, 16);
        let rep = if nodes >= 65536 { 10 } else { repeats };

        let cpu_s = measure_us(rep, || {
            let r = cpu_csr_pagerank_single(&rp, &ci, &w, nodes, 0.85, 20);
            std::hint::black_box(r);
        });
        let cpu_p = measure_us(rep, || {
            let r = cpu_csr_pagerank_parallel(&rp, &ci, &w, nodes, 0.85, 20);
            std::hint::black_box(r);
        });

        let mut gpu_k = Vec::new();
        let mut gpu_t = Vec::new();
        if let Some(ref mut ctx) = cuda_ctx {
            let _ = ctx.execute_csr_pagerank_f32(&rp, &ci, &w, nodes, 0.85, 20);
            for _ in 0..rep {
                if let Ok((_, m)) = ctx.execute_csr_pagerank_f32(&rp, &ci, &w, nodes, 0.85, 20) {
                    gpu_k.push(m.kernel_us);
                    gpu_t.push(m.total_gpu_us);
                }
            }
        }
        let st_k = DistributionStats::from_samples(&gpu_k);
        let st_t = DistributionStats::from_samples(&gpu_t);
        println!(
            "CSR_PR_{}_nodes ({} edges): CPU_Single p50={:.2}us (p95={:.2}) | CPU_Par p50={:.2}us (p95={:.2}) | GPU_20Iter_Kernel p50={:.2}us | GPU_Total p50={:.2}us (p95={:.2})",
            nodes,
            ci.len(),
            cpu_s.p50_us,
            cpu_s.p95_us,
            cpu_p.p50_us,
            cpu_p.p95_us,
            st_k.p50_us,
            st_t.p50_us,
            st_t.p95_us
        );
    }

    // 5. POC-010: Kernel Fusion vs Unfused Risk & Anomaly Scoring (D=8)
    println!("\n--- [4] KERNEL FUSION ANOMALY SCORING (D=8) ---");
    for &n in &[256usize, 4096, 32768, 131072] {
        let d = 8usize;
        let feats = vec![12.5f32; n * d];
        let w = vec![0.35f32; d];
        let m = vec![10.0f32; d];
        let s = vec![0.50f32; d];
        let rep = if n >= 131072 { 10 } else { repeats };

        let cpu_unfused = measure_us(rep, || {
            let v = cpu_unfused_risk_pipeline_single(&feats, &w, &m, &s, n, d);
            std::hint::black_box(v);
        });
        let cpu_fused_s = measure_us(rep, || {
            let v = cpu_batch_risk_fusion_single(&feats, &w, &m, &s, n, d);
            std::hint::black_box(v);
        });
        let cpu_fused_p = measure_us(rep, || {
            let v = cpu_batch_risk_fusion_parallel(&feats, &w, &m, &s, n, d);
            std::hint::black_box(v);
        });

        let mut gpu_k = Vec::new();
        let mut gpu_t = Vec::new();
        if let Some(ref mut ctx) = cuda_ctx {
            let _ = ctx.execute_batch_risk_fusion_f32(&feats, &w, &m, &s, n, d);
            for _ in 0..rep {
                if let Ok((_, met)) = ctx.execute_batch_risk_fusion_f32(&feats, &w, &m, &s, n, d) {
                    gpu_k.push(met.kernel_us);
                    gpu_t.push(met.total_gpu_us);
                }
            }
        }
        let st_k = DistributionStats::from_samples(&gpu_k);
        let st_t = DistributionStats::from_samples(&gpu_t);
        println!(
            "FUSION_{}x8: CPU_Unfused p50={:.2}us | CPU_Fused_Single p50={:.2}us | CPU_Fused_Par p50={:.2}us | GPU_Kernel p50={:.2}us | GPU_Total p50={:.2}us",
            n, cpu_unfused.p50_us, cpu_fused_s.p50_us, cpu_fused_p.p50_us, st_k.p50_us, st_t.p50_us
        );
    }

    // 6. Métricas Preditivas e Latências das POCs Relacionais (POC-001, POC-002, POC-003, POC-005, POC-007, POC-009, POC-010)
    println!("\n--- [5] PREDICTIVE QUALITY & LATENCY SUMMARY ACROSS ALL 10 POCS ---");
    let p1_lat = measure_us(repeats, || {
        std::hint::black_box(poc_001_predictive_failure::run_poc_001_evaluation(250));
    });
    let p1 = poc_001_predictive_failure::run_poc_001_evaluation(250);
    println!(
        "POC-001 (Predictive Failure): p50={:.2}us (p95={:.2}us) | Go_F1={:.4} -> Kumo_RelGT_F1={:.4} | AUROC={:.4} | Brier={:.4} (Go={:.4}) | BlockedFuture={}",
        p1_lat.p50_us,
        p1_lat.p95_us,
        p1.baseline_go_metrics.f1_score,
        p1.kumo_relgt_metrics.f1_score,
        p1.kumo_relgt_metrics.auroc,
        p1.kumo_relgt_metrics.brier_score,
        p1.baseline_go_metrics.brier_score,
        p1.future_edges_blocked
    );

    let p2_lat = measure_us(repeats, || {
        std::hint::black_box(poc_002_dependency_impact::run_poc_002_evaluation(300));
    });
    let p2 = poc_002_dependency_impact::run_poc_002_evaluation(300);
    println!(
        "POC-002 (Dependency Impact): p50={:.2}us (p95={:.2}us) | BFS2_F1={:.4} -> Temporal_CSR_F1={:.4} | AUROC={:.4} | KDG_Bytes={} vs JSON_Bytes={}",
        p2_lat.p50_us,
        p2_lat.p95_us,
        p2.unweighted_bfs2_metrics.f1_score,
        p2.temporal_csr_impact_metrics.f1_score,
        p2.temporal_csr_impact_metrics.auroc,
        p2.kdg_binary_bytes,
        p2.json_equivalent_bytes
    );

    let p3 = poc_003_gpu_code_intelligence::run_poc_003_evaluation(512, cuda_ctx.as_mut(), true);
    println!(
        "POC-003 (GPU Code Intel): Regex_F1={:.4} -> AST_GNN_F1={:.4} | Recall={:.4} | AUROC={:.4}",
        p3.regex_baseline_metrics.f1_score,
        p3.structural_ast_gnn_metrics.f1_score,
        p3.structural_ast_gnn_metrics.recall,
        p3.structural_ast_gnn_metrics.auroc
    );

    let p5_lat = measure_us(repeats, || {
        std::hint::black_box(poc_005_intelligent_scheduler::run_poc_005_evaluation(256));
    });
    let p5 = poc_005_intelligent_scheduler::run_poc_005_evaluation(256);
    println!(
        "POC-005 (Task Scheduler IMO): p50={:.2}us | Go_EWMA_OOM={:.2}% (MAE={:.1}MB) -> Ridge_Quantile_OOM={:.2}% (MAE={:.1}MB)",
        p5_lat.p50_us,
        p5.go_ewma_oom_rate * 100.0,
        p5.go_ewma_mae_mb,
        p5.ridge_quantile_oom_rate * 100.0,
        p5.ridge_quantile_mae_mb
    );

    let p7_lat = measure_us(repeats, || {
        std::hint::black_box(poc_007_predictive_quality::run_poc_007_evaluation(200));
    });
    let p7 = poc_007_predictive_quality::run_poc_007_evaluation(200);
    println!(
        "POC-007 (Predictive Quality): p50={:.2}us | PassDefault_F1={:.4} | LOC_F1={:.4} -> Relational_F1={:.4} (AUROC={:.4}, Brier={:.4})",
        p7_lat.p50_us,
        p7.go_pass_default_metrics.f1_score,
        p7.simple_loc_heuristic_metrics.f1_score,
        p7.relational_quality_metrics.f1_score,
        p7.relational_quality_metrics.auroc,
        p7.relational_quality_metrics.brier_score
    );

    let p8 = poc_008_gpu_batch_engine::run_poc_008_evaluation(128, cuda_ctx.as_mut());
    println!(
        "POC-008 (GPU Batch & Quantization): MaxErr_FP32={:.6} | INT8_CosineParity={:.6} | INT4_CosineParity={:.6}",
        p8.max_abs_error, p8.int8_cosine_parity, p8.int4_cosine_parity
    );

    let p9_lat = measure_us(repeats, || {
        std::hint::black_box(poc_009_agent_perf_predictor::run_poc_009_evaluation(200));
    });
    let p9 = poc_009_agent_perf_predictor::run_poc_009_evaluation(200);
    println!(
        "POC-009 (Agent Perf Predictor): p50={:.2}us | Static_F1={:.4} | CPU_EmpiricalBayes_F1={:.4} (Brier={:.4}) vs Heavy_GNN_F1={:.4}",
        p9_lat.p50_us,
        p9.static_tier_metrics.f1_score,
        p9.cpu_empirical_bayes_metrics.f1_score,
        p9.cpu_empirical_bayes_metrics.brier_score,
        p9.heavy_gnn_simulated_metrics.f1_score
    );

    let p10 = poc_010_anomaly_intelligence::run_poc_010_evaluation(500, cuda_ctx.as_mut());
    println!(
        "POC-010 (Anomaly Intelligence): SingleMetric_F1={:.4} -> Multivariate_Fused_F1={:.4} (AUROC={:.4}, Brier={:.4})",
        p10.single_metric_threshold_metrics.f1_score,
        p10.multivariate_fused_metrics.f1_score,
        p10.multivariate_fused_metrics.auroc,
        p10.multivariate_fused_metrics.brier_score
    );

    println!("\n--- [6] PHASE 2 EMPIRICAL EVOLUTIONS (POC-008 v2, POC-010 v2, POC-003 v2, POC-004 v2) ---");
    let p8_small = poc_008_gpu_batch_engine::run_poc_008_evaluation(64, cuda_ctx.as_mut());
    let p8_large = poc_008_gpu_batch_engine::run_poc_008_evaluation(256, cuda_ctx.as_mut());
    println!(
        "POC-008 v2 (Hybrid GEMM & Per-Channel/Group-Wise Quant): Route_64x64={} ({:.2}us) | Route_256x256={} ({:.2}us) | Outlier_INT8_PerTensor={:.6} -> PerChannel={:.6} | Outlier_INT4_PerTensor={:.6} -> GroupWise_G16={:.6}",
        p8_small.selected_hybrid_route,
        p8_small.hybrid_metrics.total_gpu_us,
        p8_large.selected_hybrid_route,
        p8_large.hybrid_metrics.total_gpu_us,
        p8_small.outlier_study.per_tensor_int8_cos,
        p8_small.outlier_study.per_channel_int8_cos,
        p8_small.outlier_study.per_tensor_int4_cos,
        p8_small.outlier_study.groupwise_g16_int4_cos
    );

    println!(
        "POC-010 v2 (Zero-Copy YMM-1-Reg + Adaptive Welford + Attribution): YMM_500x8={:.2}us (htod={:.2}us) | SilentDrifts={} | PoisonBlocked={}/{}",
        p10.zero_copy_ymm_metrics.total_gpu_us,
        p10.zero_copy_ymm_metrics.htod_us,
        p10.detected_silent_drift_count,
        p10.adaptive_rejected_poison_count,
        p10.num_windows
    );

    println!(
        "POC-003 v2 (Real AST/CFG D=32 Extractor + 512x32x16 Multi-Pattern Matrix Scan): RealSnippets_F1={:.4} | MatrixScan_512x16_us={:.2}us (htod={:.2}us)",
        p3.extracted_real_snippets_f1,
        p3.multi_pattern_gemm_metrics.total_gpu_us,
        p3.multi_pattern_gemm_metrics.htod_us
    );

    let p4_small = poc_004_cognitive_graph_accel::run_poc_004_evaluation(2048, 16, 20, cuda_ctx.as_mut());
    let p4_xl = poc_004_cognitive_graph_accel::run_poc_004_evaluation(65536, 16, 20, cuda_ctx.as_mut());
    println!(
        "POC-004 v2 (Early-Exit PageRank + Subgraph PPR Blast Radius): 2048_Nodes_ConvIters={}/20 ({}, {:.2}us) | 65536_Nodes_Subgraph_PPR={:.2}us (ActiveSubgraph={} nodes, BlastRadius={})",
        p4_small.converged_iterations,
        p4_small.selected_hybrid_route,
        p4_small.adaptive_hybrid_latency_us,
        p4_xl.localized_ppr.localized_ppr_latency_us,
        p4_xl.localized_ppr.active_subgraph_nodes,
        p4_xl.localized_ppr.computed_blast_radius_score
    );
}
