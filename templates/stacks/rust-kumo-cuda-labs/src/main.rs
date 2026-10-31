//! Binário CLI e Servidor Sidecar JSON-RPC 2.0 do Laboratório Experimental
//! `squad-kumo-cuda-lab` (Kumo AI + `NVIDIA/cuda-rust` para o `SquadAI Harness`).

use std::env;
use std::io::{self, BufRead, Write};

use squad_kumo_cuda_lab::cuda_rust_runtime::emit_verified_ptx_module;
use squad_kumo_cuda_lab::ipc_bridge::handle_jsonrpc_line;
use squad_kumo_cuda_lab::run_full_scientific_suite;

fn main() {
    let args: Vec<String> = env::args().collect();
    let mode = args.get(1).map_or("--bench-scientific", String::as_str);

    match mode {
        "--emit-ptx" => {
            println!("{}", emit_verified_ptx_module());
        }
        "--serve-stdio" => {
            let stdin = io::stdin();
            let mut stdout = io::stdout();
            for line in stdin.lock().lines().map_while(Result::ok) {
                let trimmed = line.trim();
                if trimmed.is_empty() {
                    continue;
                }
                if trimmed == "QUIT" {
                    break;
                }
                let resp = handle_jsonrpc_line(trimmed);
                let _ = writeln!(stdout, "{resp}");
                let _ = stdout.flush();
            }
        }
        _ => {
            let suite = run_full_scientific_suite(10);
            println!("{}", suite.to_executive_ascii_table());
            println!(
                "DETALHE_POC01: nodes={} edges={} json_bytes={} kdg_bytes={} red_pct={:.2}% base_p50_us={:.2} base_p95_us={:.2} poc_p50_us={:.3} poc_p95_us={:.3} speedup={:.1}x base_leak={} poc_leak={}",
                suite.poc01.graph_nodes,
                suite.poc01.graph_edges,
                suite.poc01.json_size_bytes,
                suite.poc01.kdg_binary_size_bytes,
                suite.poc01.size_reduction_pct,
                suite.poc01.baseline_p50_us,
                suite.poc01.baseline_p95_us,
                suite.poc01.poc01_p50_us,
                suite.poc01.poc01_p95_us,
                suite.poc01.speedup_x,
                suite.poc01.baseline_leakage_edges,
                suite.poc01.poc01_leakage_edges
            );
            println!(
                "DETALHE_POC02: mods={} base_prec={:.3} base_rec={:.3} base_f1={:.3} base_brier={:.4} poc_prec={:.3} poc_rec={:.3} poc_f1={:.3} poc_brier={:.4} p50_us={:.2} p95_us={:.2}",
                suite.poc02.total_modules_evaluated,
                suite.poc02.baseline_precision,
                suite.poc02.baseline_recall,
                suite.poc02.baseline_f1,
                suite.poc02.baseline_brier_score,
                suite.poc02.poc02_precision,
                suite.poc02.poc02_recall,
                suite.poc02.poc02_f1,
                suite.poc02.poc02_brier_score,
                suite.poc02.poc02_p50_us,
                suite.poc02.poc02_p95_us
            );
            println!(
                "DETALHE_POC03: queries={} bm25_r1={:.3} bm25_mrr={:.3} poc_r1={:.3} poc_mrr={:.3} int8_cos={:.5} int4_cos={:.5} policy={} p50_us={:.2} p95_us={:.2}",
                suite.poc03.total_queries,
                suite.poc03.bm25_baseline_recall_at_1,
                suite.poc03.bm25_baseline_mrr,
                suite.poc03.poc03_reranker_recall_at_1,
                suite.poc03.poc03_reranker_mrr,
                suite.poc03.int8_static_cosine_parity,
                suite.poc03.int4_rejected_cosine_parity,
                suite.poc03.promoted_hit_policy,
                suite.poc03.poc03_p50_us,
                suite.poc03.poc03_p95_us
            );
            println!(
                "DETALHE_POC04: muts={} base_tp={} base_tn={} base_fp={} base_fn={} base_f1={:.3} poc_tp={} poc_tn={} poc_fp={} poc_fn={} poc_f1={:.3} p50_us={:.2} p95_us={:.2}",
                suite.poc04.total_mutations,
                suite.poc04.go_baseline_tp,
                suite.poc04.go_baseline_tn,
                suite.poc04.go_baseline_fp,
                suite.poc04.go_baseline_fn,
                suite.poc04.go_baseline_f1,
                suite.poc04.poc04_tp,
                suite.poc04.poc04_tn,
                suite.poc04.poc04_fp,
                suite.poc04.poc04_fn,
                suite.poc04.poc04_f1,
                suite.poc04.poc04_p50_us,
                suite.poc04.poc04_p95_us
            );
            println!(
                "DETALHE_POC05: workloads={} base_ram_mae={:.2} poc_ram_mae={:.2} red_pct={:.2}% base_oom={} poc_oom={} base_blast_mae={:.2} poc_blast_mae={:.2} p50_us={:.2} p95_us={:.2}",
                suite.poc05.workloads_evaluated,
                suite.poc05.baseline_ram_mae_mb,
                suite.poc05.poc05_ram_mae_mb,
                suite.poc05.mae_reduction_pct,
                suite.poc05.baseline_underprediction_oom_risk_count,
                suite.poc05.poc05_underprediction_oom_risk_count,
                suite.poc05.baseline_blast_radius_mae,
                suite.poc05.poc05_blast_radius_mae,
                suite.poc05.poc05_p50_us,
                suite.poc05.poc05_p95_us
            );
            println!(
                "DETALHE_POC06_REAL_10GB_GPU: nvcuda={} gpu=\"{}\" ded_total_mb={} ded_free_mb={} shared_mb={} combined_mb={} alloc_hot_ded_mb={} ({:.1}%) alloc_warm_shd_mb={} ({:.1}%) alloc_combined_mb={} ({:.1}%) cap_repos={} cap_edges={} cap_episodes={} cap_jev_nodes={} elems={} cpu_p50_us={:.2} gpu_p50_us={:.2} gpu_p95_us={:.2} speedup={:.2}x max_diff={:.6}",
                suite.poc06_real_10gb.real_nvcuda_loaded,
                suite.poc06_real_10gb.physical_gpu_name,
                suite.poc06_real_10gb.driver_reported_total_vram_mb,
                suite.poc06_real_10gb.driver_reported_free_vram_mb,
                suite.poc06_real_10gb.shared_gpu_system_mb,
                suite.poc06_real_10gb.combined_gpu_pool_mb,
                suite.poc06_real_10gb.budget_plan_80pct.allocated_hot_dedicated_mb,
                suite.poc06_real_10gb.budget_plan_80pct.dedicated_utilization_pct,
                suite.poc06_real_10gb.budget_plan_80pct.allocated_warm_shared_mb,
                suite.poc06_real_10gb.budget_plan_80pct.shared_utilization_pct,
                suite.poc06_real_10gb.budget_plan_80pct.allocated_combined_mb,
                suite.poc06_real_10gb.budget_plan_80pct.combined_utilization_pct,
                suite.poc06_real_10gb.budget_plan_80pct.indexed_repos_capacity,
                suite.poc06_real_10gb.budget_plan_80pct.indexed_sekg_edges_capacity,
                suite.poc06_real_10gb.budget_plan_80pct.cached_m1_episodes_capacity,
                suite.poc06_real_10gb.budget_plan_80pct.parallel_jev_ast_nodes_capacity,
                suite.poc06_real_10gb.elements_processed_per_launch,
                suite.poc06_real_10gb.cpu_baseline_p50_us,
                suite.poc06_real_10gb.gpu_hybrid_kernel_p50_us,
                suite.poc06_real_10gb.gpu_hybrid_kernel_p95_us,
                suite.poc06_real_10gb.speedup_vs_cpu_x,
                suite.poc06_real_10gb.max_abs_numerical_diff
            );
        }
    }
}
