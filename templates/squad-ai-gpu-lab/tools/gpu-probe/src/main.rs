use gpu_runtime::CudaContext;

fn main() {
    match CudaContext::try_new() {
        Ok(mut ctx) => {
            let p = ctx.profile.clone();
            let cold_us = ctx.cold_init_us;
            let docs = vec![0.5f32; 1024 * 128];
            let query = vec![2.0f32; 128];
            let (_, m_unamort) = ctx
                .execute_batch_dot_f32(&docs, &query, 1024, 128, false)
                .expect("GPU smoke test (unamortized)");
            let _ = ctx.preload_resident_corpus(&docs);
            let (_, m_res) = ctx
                .execute_batch_dot_f32(&docs, &query, 1024, 128, true)
                .expect("GPU smoke test (resident)");

            println!(
                r#"{{"status":"GPU_ACTIVE","device_name":"{}","backend":"{}","driver_version":{},"sm_arch":"{}","multiprocessors":{},"max_threads_per_block":{},"shared_mem_per_block_bytes":{},"clock_rate_khz":{},"memory_clock_rate_khz":{},"bus_width_bits":{},"total_vram_mb":{},"free_vram_mb":{},"usable_lab_budget_mb":{},"cold_context_init_us":{:.2},"smoke_1024x128_unamortized_us":{{"alloc_us":{:.2},"htod_us":{:.2},"kernel_us":{:.2},"dtoh_us":{:.2},"total_us":{:.2}}},"smoke_1024x128_resident_us":{{"alloc_us":{:.2},"htod_us":{:.2},"kernel_us":{:.2},"dtoh_us":{:.2},"total_us":{:.2}}}}}"#,
                p.device_name,
                p.backend_name,
                p.driver_version,
                p.sm_arch(),
                p.multiprocessor_count,
                p.max_threads_per_block,
                p.max_shared_mem_per_block,
                p.clock_rate_khz,
                p.memory_clock_rate_khz,
                p.memory_bus_width_bits,
                p.total_vram_mb(),
                p.free_vram_mb(),
                p.usable_lab_budget_bytes / (1024 * 1024),
                cold_us,
                m_unamort.alloc_us,
                m_unamort.htod_us,
                m_unamort.kernel_us,
                m_unamort.dtoh_us,
                m_unamort.total_gpu_us,
                m_res.alloc_us,
                m_res.htod_us,
                m_res.kernel_us,
                m_res.dtoh_us,
                m_res.total_gpu_us
            );
        }
        Err(e) => {
            println!(r#"{{"status":"CPU_FALLBACK","reason":"{}"}}"#, e);
        }
    }
}
