//! # SquadAI GPU Intelligence Lab — `cpu-baselines`
//!
//! Baselines científicos de referência em Rust para confrontar contra Go e GPU CUDA:
//! - **Grupo C:** Rust CPU single-thread otimizado (loops cache-friendly + auto-vetorização LLVM SIMD).
//! - **Grupo D:** Rust CPU multi-thread paralelo (`std::thread::scope` zero-overhead sobre os núcleos físicos/lógicos).
//! - **Pipelines não-fundidos (Unfused) vs. Fundidos (Fused):** permite isolar o ganho real de *Kernel Fusion*.

use std::thread;

/// Número padrão de workers paralelos para Grupo D (usa `available_parallelism` limitado a 8).
pub fn default_worker_threads() -> usize {
    thread::available_parallelism()
        .map(|n| n.get().clamp(2, 8))
        .unwrap_or(4)
}

/// Grupo C: Produto interno / similaridade em lote single-thread (auto-vetorizável em AVX2).
pub fn cpu_batch_dot_single(docs_flat: &[f32], query: &[f32], n: usize, d: usize) -> Vec<f32> {
    assert_eq!(docs_flat.len(), n * d);
    assert_eq!(query.len(), d);
    let mut out = vec![0.0f32; n];
    for (row_idx, out_val) in out.iter_mut().enumerate() {
        let row = &docs_flat[row_idx * d..(row_idx + 1) * d];
        let mut acc0 = 0.0f32;
        let mut acc1 = 0.0f32;
        let mut acc2 = 0.0f32;
        let mut acc3 = 0.0f32;
        let chunks = d / 4;
        for c in 0..chunks {
            let base = c * 4;
            acc0 += row[base] * query[base];
            acc1 += row[base + 1] * query[base + 1];
            acc2 += row[base + 2] * query[base + 2];
            acc3 += row[base + 3] * query[base + 3];
        }
        let mut tail = 0.0f32;
        for k in (chunks * 4)..d {
            tail += row[k] * query[k];
        }
        *out_val = (acc0 + acc1) + (acc2 + acc3) + tail;
    }
    out
}

/// Grupo D: Produto interno em lote multi-thread (`std::thread::scope`).
pub fn cpu_batch_dot_parallel(docs_flat: &[f32], query: &[f32], n: usize, d: usize) -> Vec<f32> {
    assert_eq!(docs_flat.len(), n * d);
    assert_eq!(query.len(), d);
    if n < 256 {
        return cpu_batch_dot_single(docs_flat, query, n, d);
    }
    let workers = default_worker_threads();
    let rows_per_worker = (n + workers - 1) / workers;
    let mut out = vec![0.0f32; n];

    thread::scope(|s| {
        for (chunk_idx, out_chunk) in out.chunks_mut(rows_per_worker).enumerate() {
            let row_start = chunk_idx * rows_per_worker;
            let row_count = out_chunk.len();
            let docs_slice = &docs_flat[row_start * d..(row_start + row_count) * d];
            s.spawn(move || {
                let partial = cpu_batch_dot_single(docs_slice, query, row_count, d);
                out_chunk.copy_from_slice(&partial);
            });
        }
    });
    out
}

/// Grupo C: Multiplicação de matrizes cache-friendly (`i-k-j`) single-thread.
pub fn cpu_gemm_single(a: &[f32], b: &[f32], m: usize, n: usize, k: usize) -> Vec<f32> {
    assert_eq!(a.len(), m * k);
    assert_eq!(b.len(), k * n);
    let mut c = vec![0.0f32; m * n];
    for i in 0..m {
        let c_row = &mut c[i * n..(i + 1) * n];
        for p in 0..k {
            let a_ip = a[i * k + p];
            let b_row = &b[p * n..(p + 1) * n];
            for j in 0..n {
                c_row[j] += a_ip * b_row[j];
            }
        }
    }
    c
}

/// Grupo D: Multiplicação de matrizes multi-thread (`std::thread::scope`) particionada por blocos de linhas de `A`.
pub fn cpu_gemm_parallel(a: &[f32], b: &[f32], m: usize, n: usize, k: usize) -> Vec<f32> {
    assert_eq!(a.len(), m * k);
    assert_eq!(b.len(), k * n);
    if m < 32 {
        return cpu_gemm_single(a, b, m, n, k);
    }
    let workers = default_worker_threads();
    let rows_per_worker = (m + workers - 1) / workers;
    let mut c = vec![0.0f32; m * n];

    thread::scope(|s| {
        for (chunk_idx, c_chunk) in c.chunks_mut(rows_per_worker * n).enumerate() {
            let row_start = chunk_idx * rows_per_worker;
            let row_count = c_chunk.len() / n;
            let a_slice = &a[row_start * k..(row_start + row_count) * k];
            s.spawn(move || {
                for i in 0..row_count {
                    let c_row = &mut c_chunk[i * n..(i + 1) * n];
                    for p in 0..k {
                        let a_ip = a_slice[i * k + p];
                        let b_row = &b[p * n..(p + 1) * n];
                        for j in 0..n {
                            c_row[j] += a_ip * b_row[j];
                        }
                    }
                }
            });
        }
    });
    c
}

/// Grupo C: PageRank / GNN SpMV sobre grafo CSR single-thread.
pub fn cpu_csr_pagerank_single(
    row_ptr: &[u32],
    col_idx: &[u32],
    weights: &[f32],
    num_nodes: usize,
    damping: f32,
    iterations: usize,
) -> Vec<f32> {
    assert_eq!(row_ptr.len(), num_nodes + 1);
    assert_eq!(col_idx.len(), weights.len());
    let init_val = 1.0f32 / (num_nodes.max(1) as f32);
    let base_teleport = (1.0f32 - damping) / (num_nodes.max(1) as f32);
    let mut r_in = vec![init_val; num_nodes];
    let mut r_out = vec![0.0f32; num_nodes];

    for _ in 0..iterations.max(1) {
        for row in 0..num_nodes {
            let start = row_ptr[row] as usize;
            let end = row_ptr[row + 1] as usize;
            let mut sum = 0.0f32;
            for edge in start..end {
                let col = col_idx[edge] as usize;
                sum += weights[edge] * r_in[col];
            }
            r_out[row] = damping * sum + base_teleport;
        }
        std::mem::swap(&mut r_in, &mut r_out);
    }
    r_in
}

/// Grupo D: PageRank / GNN SpMV sobre grafo CSR multi-thread.
pub fn cpu_csr_pagerank_parallel(
    row_ptr: &[u32],
    col_idx: &[u32],
    weights: &[f32],
    num_nodes: usize,
    damping: f32,
    iterations: usize,
) -> Vec<f32> {
    if num_nodes < 1024 {
        return cpu_csr_pagerank_single(row_ptr, col_idx, weights, num_nodes, damping, iterations);
    }
    let init_val = 1.0f32 / (num_nodes.max(1) as f32);
    let base_teleport = (1.0f32 - damping) / (num_nodes.max(1) as f32);
    let mut r_in = vec![init_val; num_nodes];
    let mut r_out = vec![0.0f32; num_nodes];
    let workers = default_worker_threads();
    let nodes_per_worker = (num_nodes + workers - 1) / workers;

    for _ in 0..iterations.max(1) {
        let r_in_ref = &r_in;
        thread::scope(|s| {
            for (chunk_idx, out_chunk) in r_out.chunks_mut(nodes_per_worker).enumerate() {
                let row_start = chunk_idx * nodes_per_worker;
                s.spawn(move || {
                    for (local_i, slot) in out_chunk.iter_mut().enumerate() {
                        let row = row_start + local_i;
                        let start = row_ptr[row] as usize;
                        let end = row_ptr[row + 1] as usize;
                        let mut sum = 0.0f32;
                        for edge in start..end {
                            let col = col_idx[edge] as usize;
                            sum += weights[edge] * r_in_ref[col];
                        }
                        *slot = damping * sum + base_teleport;
                    }
                });
            }
        });
        std::mem::swap(&mut r_in, &mut r_out);
    }
    r_in
}

/// Pipeline Não-Fundido (Unfused — 3 alocações intermediárias) para medir o ganho de Kernel Fusion.
pub fn cpu_unfused_risk_pipeline_single(
    features: &[f32],
    weights: &[f32],
    means: &[f32],
    inv_stds: &[f32],
    n: usize,
    d: usize,
) -> Vec<f32> {
    // Passo 1: Normaliza Z-score em matriz intermediária
    let mut z_mat = vec![0.0f32; n * d];
    for i in 0..n {
        for j in 0..d {
            z_mat[i * d + j] = (features[i * d + j] - means[j]) * inv_stds[j];
        }
    }
    // Passo 2: Score linear em vetor intermediário
    let mut lin_vec = vec![0.0f32; n];
    for i in 0..n {
        let mut s = 0.0f32;
        for j in 0..d {
            s += z_mat[i * d + j] * weights[j];
        }
        lin_vec[i] = s.abs();
    }
    // Passo 3: Energia Mahalanobis diagonal + combinação
    let mut out = vec![0.0f32; n];
    for i in 0..n {
        let mut z2 = 0.0f32;
        for j in 0..d {
            let z = z_mat[i * d + j];
            z2 += z * z;
        }
        out[i] = 0.65 * lin_vec[i] + 0.35 * z2;
    }
    out
}

/// Grupo C: Kernel Fundido (Fused) single-thread em passagem única sem alocações intermediárias.
pub fn cpu_batch_risk_fusion_single(
    features: &[f32],
    weights: &[f32],
    means: &[f32],
    inv_stds: &[f32],
    n: usize,
    d: usize,
) -> Vec<f32> {
    let mut out = vec![0.0f32; n];
    for i in 0..n {
        let row = &features[i * d..(i + 1) * d];
        let mut lin = 0.0f32;
        let mut z2 = 0.0f32;
        for j in 0..d {
            let z = (row[j] - means[j]) * inv_stds[j];
            lin += z * weights[j];
            z2 += z * z;
        }
        out[i] = 0.65 * lin.abs() + 0.35 * z2;
    }
    out
}

/// Grupo D: Kernel Fundido (Fused) multi-thread.
pub fn cpu_batch_risk_fusion_parallel(
    features: &[f32],
    weights: &[f32],
    means: &[f32],
    inv_stds: &[f32],
    n: usize,
    d: usize,
) -> Vec<f32> {
    if n < 512 {
        return cpu_batch_risk_fusion_single(features, weights, means, inv_stds, n, d);
    }
    let workers = default_worker_threads();
    let rows_per_worker = (n + workers - 1) / workers;
    let mut out = vec![0.0f32; n];

    thread::scope(|s| {
        for (chunk_idx, out_chunk) in out.chunks_mut(rows_per_worker).enumerate() {
            let row_start = chunk_idx * rows_per_worker;
            let row_count = out_chunk.len();
            let feat_slice = &features[row_start * d..(row_start + row_count) * d];
            s.spawn(move || {
                let partial = cpu_batch_risk_fusion_single(
                    feat_slice, weights, means, inv_stds, row_count, d,
                );
                out_chunk.copy_from_slice(&partial);
            });
        }
    });
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cpu_single_and_parallel_equivalence() {
        let n = 512;
        let d = 16;
        let docs: Vec<f32> = (0..n * d).map(|i| ((i % 13) as f32) * 0.1).collect();
        let query: Vec<f32> = (0..d).map(|i| (i as f32) * 0.25).collect();

        let s = cpu_batch_dot_single(&docs, &query, n, d);
        let p = cpu_batch_dot_parallel(&docs, &query, n, d);
        for (a, b) in s.iter().zip(p.iter()) {
            assert!((a - b).abs() < 1e-5);
        }
    }

    #[test]
    fn test_fused_vs_unfused_equivalence() {
        let n = 128;
        let d = 8;
        let feats = vec![2.0f32; n * d];
        let w = vec![0.25f32; d];
        let m = vec![1.0f32; d];
        let s = vec![1.0f32; d];

        let unfused = cpu_unfused_risk_pipeline_single(&feats, &w, &m, &s, n, d);
        let fused = cpu_batch_risk_fusion_single(&feats, &w, &m, &s, n, d);
        for (a, b) in unfused.iter().zip(fused.iter()) {
            assert!((a - b).abs() < 1e-5);
        }
    }
}
