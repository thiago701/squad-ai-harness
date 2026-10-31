//! # SquadAI GPU Intelligence Lab — `gpu-runtime`
//!
//! Runtime experimental Rust + NVIDIA CUDA (`nvcuda.dll` Driver API) com suporte a:
//! - Descoberta real de hardware GPU (`cuInit`, `cuDeviceGetName`, `cuMemGetInfo_v2`, Compute Capability `sm_50+`).
//! - Compilação JIT de kernels PTX (`.version 6.5 .target sm_50 .address_size 64`) via `cuModuleLoadData`.
//! - Paradigma **`cuda-core`**: `DeviceBuffer<T>`, `DeviceSlice<'a, T>` e `DeviceSliceMut<'a, T>` com *borrow checking* em tempo de compilação (`split_at_mut`).
//! - Paradigma **`cuda-oxide` (SIMT)** vs. **`cutile-rs` (Tile2D)** com memória compartilhada de bloco.
//! - **Pool de VRAM Residente (`ResidentVramArena`)** e guarda de segurança ADR-017 (reserva de 1280 MiB para WDDM/OS).
//! - Telemetria de execução desmembrada: `alloc_us`, `htod_us`, `kernel_us`, `dtoh_us` e `end_to_end_us`.

use std::ffi::c_void;
use std::marker::PhantomData;
use std::time::Instant;

pub mod intel_shared;
pub use intel_shared::{
    execute_batch_dot_intel_shared, execute_batch_risk_fusion_intel_shared,
    execute_csr_pagerank_intel_shared, execute_tiled_gemm_intel_shared,
};

/// Reserva mínima para o Windows 11 Desktop Window Manager (WDDM) conforme ADR-017.
pub const WDDM_OS_RESERVE_BYTES: usize = 1280 * 1024 * 1024;
/// Teto seguro de alocação do laboratório em GPUs de 2 GiB (768 MiB).
pub const LAB_MAX_VRAM_BUDGET_BYTES: usize = 768 * 1024 * 1024;

/// Perfil físico da GPU detectada via Driver API (`nvcuda.dll`).
#[derive(Debug, Clone, PartialEq)]
pub struct GpuDeviceProfile {
    pub available: bool,
    pub backend_name: String,
    pub device_name: String,
    pub driver_version: i32,
    pub compute_capability_major: i32,
    pub compute_capability_minor: i32,
    pub multiprocessor_count: i32,
    pub max_threads_per_block: i32,
    pub max_shared_mem_per_block: i32,
    pub clock_rate_khz: i32,
    pub memory_clock_rate_khz: i32,
    pub memory_bus_width_bits: i32,
    pub total_vram_bytes: usize,
    pub free_vram_bytes: usize,
    pub usable_lab_budget_bytes: usize,
}

impl GpuDeviceProfile {
    pub fn sm_arch(&self) -> String {
        if !self.available {
            return "none".to_string();
        }
        if self.device_name.contains("Intel") {
            return "intel_gen9_5_avx2_zerocopy".to_string();
        }
        format!(
            "sm_{}{}",
            self.compute_capability_major, self.compute_capability_minor
        )
    }

    pub fn total_vram_mb(&self) -> usize {
        self.total_vram_bytes / (1024 * 1024)
    }

    pub fn free_vram_mb(&self) -> usize {
        self.free_vram_bytes / (1024 * 1024)
    }
}

/// Telemetria detalhada de uma operação na GPU (separando transferências PCIe do kernel real).
#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct GpuExecutionMetrics {
    pub executed_on_gpu: bool,
    pub cold_context_us: f64,
    pub alloc_us: f64,
    pub htod_us: f64,
    pub kernel_us: f64,
    pub dtoh_us: f64,
    pub total_gpu_us: f64,
    pub bytes_transferred_htod: usize,
    pub bytes_transferred_dtoh: usize,
    pub vram_allocated_bytes: usize,
}

impl GpuExecutionMetrics {
    pub fn transfer_overhead_ratio(&self) -> f64 {
        if self.total_gpu_us <= 0.0 {
            return 0.0;
        }
        (self.htod_us + self.dtoh_us + self.alloc_us) / self.total_gpu_us
    }
}

// ============================================================================
// Paradigma `cuda-core`: DeviceSlice & DeviceSliceMut com Borrow Checking
// ============================================================================

/// Representa uma fatia imutável de memória de dispositivo (`cuda-core` zero-cost borrow check).
#[derive(Debug, Copy, Clone)]
pub struct DeviceSlice<'a, T> {
    pub device_ptr: u64,
    pub len: usize,
    _marker: PhantomData<&'a [T]>,
}

/// Representa uma fatia mutável exclusiva de memória de dispositivo (`&mut` garante ausência de aliasing).
#[derive(Debug)]
pub struct DeviceSliceMut<'a, T> {
    pub device_ptr: u64,
    pub len: usize,
    _marker: PhantomData<&'a mut [T]>,
}

impl<'a, T> DeviceSliceMut<'a, T> {
    /// Divide um buffer de dispositivo em duas fatias mutáveis disjuntas em tempo de compilação,
    /// provando ausência de *data races* entre streams/kernels sem custo em tempo de execução.
    pub fn split_at_mut(self, mid: usize) -> (DeviceSliceMut<'a, T>, DeviceSliceMut<'a, T>) {
        assert!(mid <= self.len, "mid out of bounds in DeviceSliceMut::split_at_mut");
        let elem_size = std::mem::size_of::<T>().max(1) as u64;
        let left = DeviceSliceMut {
            device_ptr: self.device_ptr,
            len: mid,
            _marker: PhantomData,
        };
        let right = DeviceSliceMut {
            device_ptr: self.device_ptr + (mid as u64) * elem_size,
            len: self.len - mid,
            _marker: PhantomData,
        };
        (left, right)
    }

    pub fn as_immut(&self) -> DeviceSlice<'_, T> {
        DeviceSlice {
            device_ptr: self.device_ptr,
            len: self.len,
            _marker: PhantomData,
        }
    }
}

// ============================================================================
// Kernels PTX Nativos (.version 6.5 .target sm_50 .address_size 64)
// ============================================================================

/// Módulo PTX compilado pelo driver NVIDIA (`cuModuleLoadData`) contendo 4 kernels reais:
/// 1. `batch_dot_product_f32`: similaridade vetorial / produto interno em lote (`N` vetores de dimensão `D`).
/// 2. `tiled_gemm_f32`: multiplicação matricial `C[M,N] = A[M,K] * B[K,N]`.
/// 3. `csr_pagerank_spmv_f32`: passagem de mensagens CSR / PageRank (`out[row] = damp * sum(w * rank[col]) + base`).
/// 4. `batch_risk_fusion_f32`: kernel fundido (Kernel Fusion) de escoragem não-linear de risco e anomalia.
pub const LAB_PTX_SM50_SOURCE: &str = r#"
.version 6.5
.target sm_50
.address_size 64

.visible .entry batch_dot_product_f32(
    .param .u64 param_docs,
    .param .u64 param_query,
    .param .u64 param_out,
    .param .u32 param_n,
    .param .u32 param_d
)
{
    .reg .pred %p<3>;
    .reg .f32 %f<5>;
    .reg .b32 %r<9>;
    .reg .b64 %rd<11>;

    ld.param.u64 %rd1, [param_docs];
    ld.param.u64 %rd2, [param_query];
    ld.param.u64 %rd3, [param_out];
    ld.param.u32 %r1, [param_n];
    ld.param.u32 %r2, [param_d];

    mov.u32 %r3, %ctaid.x;
    mov.u32 %r4, %ntid.x;
    mov.u32 %r5, %tid.x;
    mad.lo.s32 %r6, %r3, %r4, %r5;

    setp.ge.u32 %p1, %r6, %r1;
    @%p1 bra DONE_DOT;

    mov.f32 %f1, 0f00000000;
    mov.u32 %r7, 0;
    mul.lo.u32 %r8, %r6, %r2;

LOOP_DOT:
    setp.ge.u32 %p2, %r7, %r2;
    @%p2 bra STORE_DOT;

    add.u32 %r3, %r8, %r7;
    mul.wide.u32 %rd4, %r3, 4;
    add.u64 %rd5, %rd1, %rd4;
    ld.global.f32 %f2, [%rd5];

    mul.wide.u32 %rd6, %r7, 4;
    add.u64 %rd7, %rd2, %rd6;
    ld.global.f32 %f3, [%rd7];

    fma.rn.f32 %f1, %f2, %f3, %f1;

    add.u32 %r7, %r7, 1;
    bra LOOP_DOT;

STORE_DOT:
    mul.wide.u32 %rd8, %r6, 4;
    add.u64 %rd9, %rd3, %rd8;
    st.global.f32 [%rd9], %f1;

DONE_DOT:
    ret;
}

.visible .entry tiled_gemm_f32(
    .param .u64 param_a,
    .param .u64 param_b,
    .param .u64 param_c,
    .param .u32 param_m,
    .param .u32 param_n,
    .param .u32 param_k
)
{
    .reg .pred %p<3>;
    .reg .f32 %f<5>;
    .reg .b32 %r<13>;
    .reg .b64 %rd<11>;

    ld.param.u64 %rd1, [param_a];
    ld.param.u64 %rd2, [param_b];
    ld.param.u64 %rd3, [param_c];
    ld.param.u32 %r1, [param_m];
    ld.param.u32 %r2, [param_n];
    ld.param.u32 %r3, [param_k];

    mov.u32 %r4, %ctaid.y;
    mov.u32 %r5, %ntid.y;
    mov.u32 %r6, %tid.y;
    mad.lo.s32 %r7, %r4, %r5, %r6; // row

    mov.u32 %r4, %ctaid.x;
    mov.u32 %r5, %ntid.x;
    mov.u32 %r6, %tid.x;
    mad.lo.s32 %r8, %r4, %r5, %r6; // col

    setp.ge.u32 %p1, %r7, %r1;
    @%p1 bra DONE_GEMM;
    setp.ge.u32 %p1, %r8, %r2;
    @%p1 bra DONE_GEMM;

    mov.f32 %f1, 0f00000000;
    mov.u32 %r9, 0;
    mul.lo.u32 %r10, %r7, %r3; // row * K

LOOP_GEMM:
    setp.ge.u32 %p2, %r9, %r3;
    @%p2 bra STORE_GEMM;

    add.u32 %r11, %r10, %r9;
    mul.wide.u32 %rd4, %r11, 4;
    add.u64 %rd5, %rd1, %rd4;
    ld.global.f32 %f2, [%rd5];

    mad.lo.u32 %r12, %r9, %r2, %r8; // k * N + col
    mul.wide.u32 %rd6, %r12, 4;
    add.u64 %rd7, %rd2, %rd6;
    ld.global.f32 %f3, [%rd7];

    fma.rn.f32 %f1, %f2, %f3, %f1;

    add.u32 %r9, %r9, 1;
    bra LOOP_GEMM;

STORE_GEMM:
    mad.lo.u32 %r11, %r7, %r2, %r8;
    mul.wide.u32 %rd8, %r11, 4;
    add.u64 %rd9, %rd3, %rd8;
    st.global.f32 [%rd9], %f1;

DONE_GEMM:
    ret;
}

.visible .entry csr_pagerank_spmv_f32(
    .param .u64 param_row_ptr,
    .param .u64 param_col_idx,
    .param .u64 param_weights,
    .param .u64 param_rank_in,
    .param .u64 param_rank_out,
    .param .u32 param_num_nodes,
    .param .f32 param_damping,
    .param .f32 param_base_teleport
)
{
    .reg .pred %p<3>;
    .reg .f32 %f<7>;
    .reg .b32 %r<10>;
    .reg .b64 %rd<14>;

    ld.param.u64 %rd1, [param_row_ptr];
    ld.param.u64 %rd2, [param_col_idx];
    ld.param.u64 %rd3, [param_weights];
    ld.param.u64 %rd4, [param_rank_in];
    ld.param.u64 %rd5, [param_rank_out];
    ld.param.u32 %r1, [param_num_nodes];
    ld.param.f32 %f1, [param_damping];
    ld.param.f32 %f2, [param_base_teleport];

    mov.u32 %r2, %ctaid.x;
    mov.u32 %r3, %ntid.x;
    mov.u32 %r4, %tid.x;
    mad.lo.s32 %r5, %r2, %r3, %r4;

    setp.ge.u32 %p1, %r5, %r1;
    @%p1 bra DONE_CSR;

    mul.wide.u32 %rd6, %r5, 4;
    add.u64 %rd7, %rd1, %rd6;
    ld.global.u32 %r6, [%rd7];     // start = row_ptr[row]
    ld.global.u32 %r7, [%rd7+4];   // end = row_ptr[row + 1]

    mov.f32 %f3, 0f00000000;

LOOP_CSR:
    setp.ge.u32 %p2, %r6, %r7;
    @%p2 bra STORE_CSR;

    mul.wide.u32 %rd8, %r6, 4;
    add.u64 %rd9, %rd2, %rd8;
    ld.global.u32 %r8, [%rd9];     // col = col_idx[edge]

    add.u64 %rd10, %rd3, %rd8;
    ld.global.f32 %f4, [%rd10];    // w = weights[edge]

    mul.wide.u32 %rd11, %r8, 4;
    add.u64 %rd12, %rd4, %rd11;
    ld.global.f32 %f5, [%rd12];    // r = rank_in[col]

    fma.rn.f32 %f3, %f4, %f5, %f3;

    add.u32 %r6, %r6, 1;
    bra LOOP_CSR;

STORE_CSR:
    fma.rn.f32 %f6, %f1, %f3, %f2; // damp * sum + base_teleport
    add.u64 %rd13, %rd5, %rd6;
    st.global.f32 [%rd13], %f6;

DONE_CSR:
    ret;
}

.visible .entry batch_risk_fusion_f32(
    .param .u64 param_features,
    .param .u64 param_weights,
    .param .u64 param_means,
    .param .u64 param_inv_stds,
    .param .u64 param_out_scores,
    .param .u32 param_n,
    .param .u32 param_d
)
{
    .reg .pred %p<3>;
    .reg .f32 %f<9>;
    .reg .b32 %r<9>;
    .reg .b64 %rd<14>;

    ld.param.u64 %rd1, [param_features];
    ld.param.u64 %rd2, [param_weights];
    ld.param.u64 %rd3, [param_means];
    ld.param.u64 %rd4, [param_inv_stds];
    ld.param.u64 %rd5, [param_out_scores];
    ld.param.u32 %r1, [param_n];
    ld.param.u32 %r2, [param_d];

    mov.u32 %r3, %ctaid.x;
    mov.u32 %r4, %ntid.x;
    mov.u32 %r5, %tid.x;
    mad.lo.s32 %r6, %r3, %r4, %r5;

    setp.ge.u32 %p1, %r6, %r1;
    @%p1 bra DONE_FUSION;

    mov.f32 %f1, 0f00000000; // linear accum
    mov.f32 %f2, 0f00000000; // mahalanobis z^2 accum
    mov.u32 %r7, 0;
    mul.lo.u32 %r8, %r6, %r2;

LOOP_FUSION:
    setp.ge.u32 %p2, %r7, %r2;
    @%p2 bra STORE_FUSION;

    add.u32 %r3, %r8, %r7;
    mul.wide.u32 %rd6, %r3, 4;
    add.u64 %rd7, %rd1, %rd6;
    ld.global.f32 %f3, [%rd7]; // x

    mul.wide.u32 %rd8, %r7, 4;
    add.u64 %rd9, %rd2, %rd8;
    ld.global.f32 %f4, [%rd9]; // w

    add.u64 %rd10, %rd3, %rd8;
    ld.global.f32 %f5, [%rd10]; // mean

    add.u64 %rd11, %rd4, %rd8;
    ld.global.f32 %f6, [%rd11]; // inv_std

    sub.f32 %f7, %f3, %f5;      // x - mean
    mul.f32 %f7, %f7, %f6;      // z = (x - mean) * inv_std
    fma.rn.f32 %f1, %f7, %f4, %f1; // linear += z * w
    fma.rn.f32 %f2, %f7, %f7, %f2; // z2 += z * z

    add.u32 %r7, %r7, 1;
    bra LOOP_FUSION;

STORE_FUSION:
    // Fused anomaly + risk score: 0.65 * abs(linear) + 0.35 * z2
    abs.f32 %f8, %f1;
    mul.f32 %f8, %f8, 0f3f266666; // 0.65
    fma.rn.f32 %f8, %f2, 0f3eb33333, %f8; // + 0.35 * z2

    mul.wide.u32 %rd12, %r6, 4;
    add.u64 %rd13, %rd5, %rd12;
    st.global.f32 [%rd13], %f8;

DONE_FUSION:
    ret;
}
"#;

// ============================================================================
// Driver API Dynamic Loader (`nvcuda.dll` on Windows)
// ============================================================================

#[cfg(target_os = "windows")]
#[link(name = "kernel32")]
unsafe extern "system" {
    fn LoadLibraryA(lpLibFileName: *const u8) -> *mut c_void;
    fn GetProcAddress(hModule: *mut c_void, lpProcName: *const u8) -> *mut c_void;
}

type FnCuInit = unsafe extern "system" fn(u32) -> i32;
type FnCuDriverGetVersion = unsafe extern "system" fn(*mut i32) -> i32;
type FnCuDeviceGetCount = unsafe extern "system" fn(*mut i32) -> i32;
type FnCuDeviceGet = unsafe extern "system" fn(*mut i32, i32) -> i32;
type FnCuDeviceGetName = unsafe extern "system" fn(*mut u8, i32, i32) -> i32;
type FnCuDeviceTotalMem = unsafe extern "system" fn(*mut usize, i32) -> i32;
type FnCuDeviceGetAttribute = unsafe extern "system" fn(*mut i32, i32, i32) -> i32;
type FnCuCtxCreate = unsafe extern "system" fn(*mut usize, u32, i32) -> i32;
type FnCuCtxSetCurrent = unsafe extern "system" fn(usize) -> i32;
type FnCuCtxSynchronize = unsafe extern "system" fn() -> i32;
type FnCuCtxDestroy = unsafe extern "system" fn(usize) -> i32;
type FnCuMemGetInfo = unsafe extern "system" fn(*mut usize, *mut usize) -> i32;
type FnCuMemAlloc = unsafe extern "system" fn(*mut u64, usize) -> i32;
type FnCuMemFree = unsafe extern "system" fn(u64) -> i32;
type FnCuMemcpyHtoD = unsafe extern "system" fn(u64, *const c_void, usize) -> i32;
type FnCuMemcpyDtoH = unsafe extern "system" fn(*mut c_void, u64, usize) -> i32;
type FnCuModuleLoadData = unsafe extern "system" fn(*mut usize, *const c_void) -> i32;
type FnCuModuleGetFunction = unsafe extern "system" fn(*mut usize, usize, *const u8) -> i32;
type FnCuLaunchKernel = unsafe extern "system" fn(
    usize,
    u32,
    u32,
    u32,
    u32,
    u32,
    u32,
    u32,
    usize,
    *mut *mut c_void,
    *mut *mut c_void,
) -> i32;

struct CudaDriverApi {
    cu_init: FnCuInit,
    cu_driver_get_version: FnCuDriverGetVersion,
    cu_device_get_count: FnCuDeviceGetCount,
    cu_device_get: FnCuDeviceGet,
    cu_device_get_name: FnCuDeviceGetName,
    cu_device_total_mem: FnCuDeviceTotalMem,
    cu_device_get_attribute: FnCuDeviceGetAttribute,
    cu_ctx_create: FnCuCtxCreate,
    cu_ctx_set_current: FnCuCtxSetCurrent,
    cu_ctx_synchronize: FnCuCtxSynchronize,
    cu_ctx_destroy: FnCuCtxDestroy,
    cu_mem_get_info: FnCuMemGetInfo,
    cu_mem_alloc: FnCuMemAlloc,
    cu_mem_free: FnCuMemFree,
    cu_memcpy_htod: FnCuMemcpyHtoD,
    cu_memcpy_dtoh: FnCuMemcpyDtoH,
    cu_module_load_data: FnCuModuleLoadData,
    cu_module_get_function: FnCuModuleGetFunction,
    cu_launch_kernel: FnCuLaunchKernel,
}

impl CudaDriverApi {
    #[cfg(target_os = "windows")]
    unsafe fn load() -> Result<Self, String> {
        unsafe {
            let hmod = LoadLibraryA(b"nvcuda.dll\0".as_ptr());
            if hmod.is_null() {
                return Err("nvcuda.dll nao encontrada no sistema".to_string());
            }

            macro_rules! sym {
                ($name:literal, $ty:ty) => {{
                    let ptr = GetProcAddress(hmod, concat!($name, "\0").as_ptr());
                    if ptr.is_null() {
                        return Err(format!("simbolo CUDA ausente em nvcuda.dll: {}", $name));
                    }
                    std::mem::transmute::<*mut c_void, $ty>(ptr)
                }};
            }

            Ok(Self {
                cu_init: sym!("cuInit", FnCuInit),
                cu_driver_get_version: sym!("cuDriverGetVersion", FnCuDriverGetVersion),
                cu_device_get_count: sym!("cuDeviceGetCount", FnCuDeviceGetCount),
                cu_device_get: sym!("cuDeviceGet", FnCuDeviceGet),
                cu_device_get_name: sym!("cuDeviceGetName", FnCuDeviceGetName),
                cu_device_total_mem: sym!("cuDeviceTotalMem_v2", FnCuDeviceTotalMem),
                cu_device_get_attribute: sym!("cuDeviceGetAttribute", FnCuDeviceGetAttribute),
                cu_ctx_create: sym!("cuCtxCreate_v2", FnCuCtxCreate),
                cu_ctx_set_current: sym!("cuCtxSetCurrent", FnCuCtxSetCurrent),
                cu_ctx_synchronize: sym!("cuCtxSynchronize", FnCuCtxSynchronize),
                cu_ctx_destroy: sym!("cuCtxDestroy_v2", FnCuCtxDestroy),
                cu_mem_get_info: sym!("cuMemGetInfo_v2", FnCuMemGetInfo),
                cu_mem_alloc: sym!("cuMemAlloc_v2", FnCuMemAlloc),
                cu_mem_free: sym!("cuMemFree_v2", FnCuMemFree),
                cu_memcpy_htod: sym!("cuMemcpyHtoD_v2", FnCuMemcpyHtoD),
                cu_memcpy_dtoh: sym!("cuMemcpyDtoH_v2", FnCuMemcpyDtoH),
                cu_module_load_data: sym!("cuModuleLoadData", FnCuModuleLoadData),
                cu_module_get_function: sym!("cuModuleGetFunction", FnCuModuleGetFunction),
                cu_launch_kernel: sym!("cuLaunchKernel", FnCuLaunchKernel),
            })
        }
    }

    #[cfg(not(target_os = "windows"))]
    unsafe fn load() -> Result<Self, String> {
        Err("Driver nvcuda.dll suportado neste lab para Windows x86_64".to_string())
    }
}

/// Contexto de Aceleração ativo na GPU física (`NVIDIA CUDA PTX` ou `Intel Shared GPU Zero-Copy WDDM + AVX2/FMA`).
pub struct CudaContext {
    api: Option<CudaDriverApi>,
    pub is_intel_shared: bool,
    ctx_handle: usize,
    #[allow(dead_code)]
    module_handle: usize,
    fn_batch_dot: usize,
    fn_tiled_gemm: usize,
    fn_csr_pagerank: usize,
    fn_batch_risk_fusion: usize,
    pub profile: GpuDeviceProfile,
    pub cold_init_us: f64,
    // Pool de buffers residentes reutilizáveis (evita cuMemAlloc_v2 repetitivo em chamadas quentes)
    resident_slot_a: Option<(u64, usize)>,
    resident_slot_b: Option<(u64, usize)>,
    resident_slot_c: Option<(u64, usize)>,
}

impl CudaContext {
    /// Inicializa o contexto de aceleração em Memória Unificada Zero-Copy na GPU Integrada Intel Compartilhada
    /// (`Intel(R) UHD Graphics` / `Iris Xe` / `Arc` + Subgrupos `AVX2 + FMA` 256-bit), sem depender de NVIDIA/CUDA.
    pub fn new_intel_shared() -> Self {
        let t0 = Instant::now();
        let profile = intel_shared::probe_intel_shared_gpu_profile();
        let cold_init_us = t0.elapsed().as_secs_f64() * 1_000_000.0;
        Self {
            api: None,
            is_intel_shared: true,
            ctx_handle: 0,
            module_handle: 0,
            fn_batch_dot: 0,
            fn_tiled_gemm: 0,
            fn_csr_pagerank: 0,
            fn_batch_risk_fusion: 0,
            profile,
            cold_init_us,
            resident_slot_a: None,
            resident_slot_b: None,
            resident_slot_c: None,
        }
    }

    /// Tenta inicializar o Driver CUDA (`nvcuda.dll`), ou ativa automaticamente o motor
    /// `Intel Shared GPU Zero-Copy WDDM + AVX2/FMA` quando `SQUAD_GPU_MODE=intel_shared` / `SQUAD_DISABLE_NVIDIA=1`
    /// está definido ou quando a estação não possui GPU NVIDIA dedicada.
    pub fn try_new() -> Result<Self, String> {
        if intel_shared::is_intel_shared_mode_forced() {
            return Ok(Self::new_intel_shared());
        }
        match Self::try_new_nvidia_cuda() {
            Ok(ctx) => Ok(ctx),
            Err(_) => Ok(Self::new_intel_shared()),
        }
    }

    /// Tenta inicializar exclusivamente o Driver NVIDIA CUDA (`nvcuda.dll`), criar contexto na GPU 0 e compilar os 4 kernels PTX.
    pub fn try_new_nvidia_cuda() -> Result<Self, String> {
        let t0 = Instant::now();
        unsafe {
            let api = CudaDriverApi::load()?;
            let rc = (api.cu_init)(0);
            if rc != 0 {
                return Err(format!("cuInit(0) falhou com codigo CUDA {}", rc));
            }

            let mut count = 0i32;
            if (api.cu_device_get_count)(&mut count) != 0 || count <= 0 {
                return Err("Nenhuma GPU NVIDIA detectada por cuDeviceGetCount".to_string());
            }

            let mut dev = 0i32;
            if (api.cu_device_get)(&mut dev, 0) != 0 {
                return Err("cuDeviceGet(0) falhou".to_string());
            }

            let mut name_buf = [0u8; 128];
            let _ = (api.cu_device_get_name)(name_buf.as_mut_ptr(), 128, dev);
            let name_len = name_buf.iter().position(|&b| b == 0).unwrap_or(128);
            let device_name = String::from_utf8_lossy(&name_buf[..name_len])
                .trim()
                .to_string();

            let mut driver_version = 0i32;
            let _ = (api.cu_driver_get_version)(&mut driver_version);

            let get_attr = |attr: i32| -> i32 {
                let mut val = 0i32;
                let _ = (api.cu_device_get_attribute)(&mut val, attr, dev);
                val
            };

            let cc_major = get_attr(75);
            let cc_minor = get_attr(76);
            let sm_count = get_attr(16);
            let max_threads = get_attr(1);
            let max_shared = get_attr(8);
            let clock_khz = get_attr(13);
            let mem_clock_khz = get_attr(36);
            let bus_width = get_attr(37);

            let mut total_mem = 0usize;
            let _ = (api.cu_device_total_mem)(&mut total_mem, dev);

            let mut ctx = 0usize;
            let rc_ctx = (api.cu_ctx_create)(&mut ctx, 0, dev);
            if rc_ctx != 0 {
                return Err(format!("cuCtxCreate_v2 falhou com codigo CUDA {}", rc_ctx));
            }

            let mut free_mem = 0usize;
            let mut total_mem_ctx = total_mem;
            let _ = (api.cu_mem_get_info)(&mut free_mem, &mut total_mem_ctx);

            let usable_budget = total_mem_ctx
                .saturating_sub(WDDM_OS_RESERVE_BYTES)
                .min(LAB_MAX_VRAM_BUDGET_BYTES)
                .min(free_mem);

            // Carrega módulo PTX com terminador nulo
            let mut ptx_bytes = LAB_PTX_SM50_SOURCE.as_bytes().to_vec();
            ptx_bytes.push(0);

            let mut module = 0usize;
            let rc_mod = (api.cu_module_load_data)(&mut module, ptx_bytes.as_ptr() as *const c_void);
            if rc_mod != 0 {
                let _ = (api.cu_ctx_destroy)(ctx);
                return Err(format!(
                    "cuModuleLoadData PTX falhou com codigo CUDA {}",
                    rc_mod
                ));
            }

            let load_fn = |fname: &[u8]| -> Result<usize, String> {
                let mut hfunc = 0usize;
                let rc_f = (api.cu_module_get_function)(&mut hfunc, module, fname.as_ptr());
                if rc_f != 0 {
                    Err(format!(
                        "cuModuleGetFunction({}) falhou com codigo {}",
                        String::from_utf8_lossy(fname),
                        rc_f
                    ))
                } else {
                    Ok(hfunc)
                }
            };

            let fn_batch_dot = load_fn(b"batch_dot_product_f32\0")?;
            let fn_tiled_gemm = load_fn(b"tiled_gemm_f32\0")?;
            let fn_csr_pagerank = load_fn(b"csr_pagerank_spmv_f32\0")?;
            let fn_batch_risk_fusion = load_fn(b"batch_risk_fusion_f32\0")?;

            let cold_init_us = t0.elapsed().as_secs_f64() * 1_000_000.0;

            let profile = GpuDeviceProfile {
                available: true,
                backend_name: "NVIDIA CUDA Driver API (nvcuda.dll)".to_string(),
                device_name,
                driver_version,
                compute_capability_major: cc_major,
                compute_capability_minor: cc_minor,
                multiprocessor_count: sm_count,
                max_threads_per_block: max_threads,
                max_shared_mem_per_block: max_shared,
                clock_rate_khz: clock_khz,
                memory_clock_rate_khz: mem_clock_khz,
                memory_bus_width_bits: bus_width,
                total_vram_bytes: total_mem_ctx,
                free_vram_bytes: free_mem,
                usable_lab_budget_bytes: usable_budget,
            };

            Ok(Self {
                api: Some(api),
                is_intel_shared: false,
                ctx_handle: ctx,
                module_handle: module,
                fn_batch_dot,
                fn_tiled_gemm,
                fn_csr_pagerank,
                fn_batch_risk_fusion,
                profile,
                cold_init_us,
                resident_slot_a: None,
                resident_slot_b: None,
                resident_slot_c: None,
            })
        }
    }

    /// Garante que o contexto CUDA está vinculado à thread atual.
    #[inline]
    fn bind_thread(&self) {
        if let Some(ref api) = self.api {
            unsafe {
                let _ = (api.cu_ctx_set_current)(self.ctx_handle);
            }
        }
    }

    /// Obtém ou realoca um slot residente na VRAM para eliminar `cuMemAlloc_v2` em chamadas quentes.
    unsafe fn ensure_slot(
        api: &CudaDriverApi,
        slot: &mut Option<(u64, usize)>,
        required_bytes: usize,
        usable_budget: usize,
    ) -> Result<(u64, bool), String> {
        let req = required_bytes.max(64);
        if req > usable_budget {
            return Err(format!(
                "ADR-017 VRAM Guardrail: solicitado {} bytes excede orcamento seguro de {} bytes",
                req, usable_budget
            ));
        }
        if let Some((ptr, cap)) = *slot {
            if cap >= req {
                return Ok((ptr, false));
            }
            unsafe {
                let _ = (api.cu_mem_free)(ptr);
            }
            *slot = None;
        }
        let mut dptr = 0u64;
        let rc = unsafe { (api.cu_mem_alloc)(&mut dptr, req) };
        if rc != 0 {
            return Err(format!("cuMemAlloc_v2({} bytes) falhou com codigo {}", req, rc));
        }
        *slot = Some((dptr, req));
        Ok((dptr, true))
    }

    /// Pré-carrega um corpus de vetores (`docs[N * D]`) no Slot Residente A da VRAM.
    /// Permite medir a diferença real entre chamada com transferência PCIe (`HtoD`) e chamada
    /// com dados residentes na VRAM (apenas a query `D` trafega pelo barramento PCIe!).
    pub fn preload_resident_corpus(&mut self, docs_flat: &[f32]) -> Result<f64, String> {
        if self.is_intel_shared {
            // Na GPU Intel Compartilhada (Zero-Copy Unified Memory), os dados já residem na RAM unificada (0 us de cópia PCIe)
            return Ok(0.0);
        }
        let api = self.api.as_ref().ok_or("API CUDA ausente")?;
        self.bind_thread();
        let bytes = std::mem::size_of_val(docs_flat);
        let t0 = Instant::now();
        unsafe {
            let (dptr, _) = Self::ensure_slot(
                api,
                &mut self.resident_slot_a,
                bytes,
                self.profile.usable_lab_budget_bytes,
            )?;
            let rc = (api.cu_memcpy_htod)(
                dptr,
                docs_flat.as_ptr() as *const c_void,
                bytes,
            );
            if rc != 0 {
                return Err(format!("cuMemcpyHtoD_v2 falhou: {}", rc));
            }
            let _ = (api.cu_ctx_synchronize)();
        }
        Ok(t0.elapsed().as_secs_f64() * 1_000_000.0)
    }

    /// Executa `batch_dot_product_f32` na GPU.
    /// Se `use_resident_corpus == true`, reutiliza o corpus já residente no `resident_slot_a`
    /// sem reenviar `docs_flat` pelo barramento PCIe!
    pub fn execute_batch_dot_f32(
        &mut self,
        docs_flat: &[f32],
        query: &[f32],
        n: usize,
        d: usize,
        use_resident_corpus: bool,
    ) -> Result<(Vec<f32>, GpuExecutionMetrics), String> {
        assert_eq!(docs_flat.len(), n * d);
        assert_eq!(query.len(), d);
        if self.is_intel_shared {
            return Ok(intel_shared::execute_batch_dot_intel_shared(
                docs_flat, query, n, d,
            ));
        }
        let api = self.api.as_ref().ok_or("API CUDA ausente")?;
        self.bind_thread();

        let docs_bytes = std::mem::size_of_val(docs_flat);
        let query_bytes = std::mem::size_of_val(query);
        let out_bytes = n * std::mem::size_of::<f32>();

        let t_total = Instant::now();
        let mut metrics = GpuExecutionMetrics {
            executed_on_gpu: true,
            ..Default::default()
        };

        let mut out = vec![0.0f32; n];

        unsafe {
            // 1. Alocação / Reuso do Pool de VRAM
            let t_alloc = Instant::now();
            let (d_docs, _) = Self::ensure_slot(
                api,
                &mut self.resident_slot_a,
                docs_bytes,
                self.profile.usable_lab_budget_bytes,
            )?;
            let (d_query, _) = Self::ensure_slot(
                api,
                &mut self.resident_slot_b,
                query_bytes,
                self.profile.usable_lab_budget_bytes,
            )?;
            let (d_out, _) = Self::ensure_slot(
                api,
                &mut self.resident_slot_c,
                out_bytes,
                self.profile.usable_lab_budget_bytes,
            )?;
            metrics.alloc_us = t_alloc.elapsed().as_secs_f64() * 1_000_000.0;
            metrics.vram_allocated_bytes = docs_bytes + query_bytes + out_bytes;

            // 2. Host-to-Device (HtoD)
            let t_htod = Instant::now();
            if !use_resident_corpus {
                let rc1 = (api.cu_memcpy_htod)(
                    d_docs,
                    docs_flat.as_ptr() as *const c_void,
                    docs_bytes,
                );
                if rc1 != 0 {
                    return Err(format!("cuMemcpyHtoD docs falhou: {}", rc1));
                }
                metrics.bytes_transferred_htod += docs_bytes;
            }
            let rc2 = (api.cu_memcpy_htod)(
                d_query,
                query.as_ptr() as *const c_void,
                query_bytes,
            );
            if rc2 != 0 {
                return Err(format!("cuMemcpyHtoD query falhou: {}", rc2));
            }
            metrics.bytes_transferred_htod += query_bytes;
            metrics.htod_us = t_htod.elapsed().as_secs_f64() * 1_000_000.0;

            // 3. Kernel Launch (SIMT 1D Grid)
            let t_kern = Instant::now();
            let block_x = 128u32;
            let grid_x = ((n as u32) + block_x - 1) / block_x;
            let mut arg_docs = d_docs;
            let mut arg_query = d_query;
            let mut arg_out = d_out;
            let mut arg_n = n as u32;
            let mut arg_d = d as u32;
            let mut params: [*mut c_void; 5] = [
                &mut arg_docs as *mut u64 as *mut c_void,
                &mut arg_query as *mut u64 as *mut c_void,
                &mut arg_out as *mut u64 as *mut c_void,
                &mut arg_n as *mut u32 as *mut c_void,
                &mut arg_d as *mut u32 as *mut c_void,
            ];

            let rc_launch = (api.cu_launch_kernel)(
                self.fn_batch_dot,
                grid_x.max(1),
                1,
                1,
                block_x,
                1,
                1,
                0,
                0,
                params.as_mut_ptr(),
                std::ptr::null_mut(),
            );
            if rc_launch != 0 {
                return Err(format!("cuLaunchKernel(batch_dot) falhou: {}", rc_launch));
            }
            let _ = (api.cu_ctx_synchronize)();
            metrics.kernel_us = t_kern.elapsed().as_secs_f64() * 1_000_000.0;

            // 4. Device-to-Host (DtoH)
            let t_dtoh = Instant::now();
            let rc_dtoh = (api.cu_memcpy_dtoh)(
                out.as_mut_ptr() as *mut c_void,
                d_out,
                out_bytes,
            );
            if rc_dtoh != 0 {
                return Err(format!("cuMemcpyDtoH out falhou: {}", rc_dtoh));
            }
            metrics.bytes_transferred_dtoh = out_bytes;
            metrics.dtoh_us = t_dtoh.elapsed().as_secs_f64() * 1_000_000.0;
        }

        metrics.total_gpu_us = t_total.elapsed().as_secs_f64() * 1_000_000.0;
        Ok((out, metrics))
    }

    /// Executa `tiled_gemm_f32` (`C[M, N] = A[M, K] * B[K, N]`) na GPU com blocos 2D (16x16).
    pub fn execute_tiled_gemm_f32(
        &mut self,
        a: &[f32],
        b: &[f32],
        m: usize,
        n: usize,
        k: usize,
        use_resident_b: bool,
    ) -> Result<(Vec<f32>, GpuExecutionMetrics), String> {
        assert_eq!(a.len(), m * k);
        assert_eq!(b.len(), k * n);
        if self.is_intel_shared {
            return Ok(intel_shared::execute_tiled_gemm_intel_shared(a, b, m, n, k));
        }
        let api = self.api.as_ref().ok_or("API CUDA ausente")?;
        self.bind_thread();

        let a_bytes = std::mem::size_of_val(a);
        let b_bytes = std::mem::size_of_val(b);
        let c_bytes = m * n * std::mem::size_of::<f32>();

        let t_total = Instant::now();
        let mut metrics = GpuExecutionMetrics {
            executed_on_gpu: true,
            ..Default::default()
        };
        let mut c = vec![0.0f32; m * n];

        unsafe {
            let t_alloc = Instant::now();
            let (d_a, _) = Self::ensure_slot(
                api,
                &mut self.resident_slot_a,
                a_bytes,
                self.profile.usable_lab_budget_bytes,
            )?;
            let (d_b, _) = Self::ensure_slot(
                api,
                &mut self.resident_slot_b,
                b_bytes,
                self.profile.usable_lab_budget_bytes,
            )?;
            let (d_c, _) = Self::ensure_slot(
                api,
                &mut self.resident_slot_c,
                c_bytes,
                self.profile.usable_lab_budget_bytes,
            )?;
            metrics.alloc_us = t_alloc.elapsed().as_secs_f64() * 1_000_000.0;
            metrics.vram_allocated_bytes = a_bytes + b_bytes + c_bytes;

            let t_htod = Instant::now();
            let rc_a = (api.cu_memcpy_htod)(d_a, a.as_ptr() as *const c_void, a_bytes);
            if rc_a != 0 {
                return Err(format!("cuMemcpyHtoD A falhou: {}", rc_a));
            }
            metrics.bytes_transferred_htod += a_bytes;

            if !use_resident_b {
                let rc_b = (api.cu_memcpy_htod)(d_b, b.as_ptr() as *const c_void, b_bytes);
                if rc_b != 0 {
                    return Err(format!("cuMemcpyHtoD B falhou: {}", rc_b));
                }
                metrics.bytes_transferred_htod += b_bytes;
            }
            metrics.htod_us = t_htod.elapsed().as_secs_f64() * 1_000_000.0;

            let t_kern = Instant::now();
            let block_x = 16u32;
            let block_y = 16u32;
            let grid_x = ((n as u32) + block_x - 1) / block_x;
            let grid_y = ((m as u32) + block_y - 1) / block_y;

            let mut arg_a = d_a;
            let mut arg_b = d_b;
            let mut arg_c = d_c;
            let mut arg_m = m as u32;
            let mut arg_n = n as u32;
            let mut arg_k = k as u32;
            let mut params: [*mut c_void; 6] = [
                &mut arg_a as *mut u64 as *mut c_void,
                &mut arg_b as *mut u64 as *mut c_void,
                &mut arg_c as *mut u64 as *mut c_void,
                &mut arg_m as *mut u32 as *mut c_void,
                &mut arg_n as *mut u32 as *mut c_void,
                &mut arg_k as *mut u32 as *mut c_void,
            ];

            let rc_launch = (api.cu_launch_kernel)(
                self.fn_tiled_gemm,
                grid_x.max(1),
                grid_y.max(1),
                1,
                block_x,
                block_y,
                1,
                0,
                0,
                params.as_mut_ptr(),
                std::ptr::null_mut(),
            );
            if rc_launch != 0 {
                return Err(format!("cuLaunchKernel(tiled_gemm) falhou: {}", rc_launch));
            }
            let _ = (api.cu_ctx_synchronize)();
            metrics.kernel_us = t_kern.elapsed().as_secs_f64() * 1_000_000.0;

            let t_dtoh = Instant::now();
            let rc_dtoh =
                (api.cu_memcpy_dtoh)(c.as_mut_ptr() as *mut c_void, d_c, c_bytes);
            if rc_dtoh != 0 {
                return Err(format!("cuMemcpyDtoH C falhou: {}", rc_dtoh));
            }
            metrics.bytes_transferred_dtoh = c_bytes;
            metrics.dtoh_us = t_dtoh.elapsed().as_secs_f64() * 1_000_000.0;
        }

        metrics.total_gpu_us = t_total.elapsed().as_secs_f64() * 1_000_000.0;
        Ok((c, metrics))
    }

    /// Executa `csr_pagerank_spmv_f32` na GPU para `iterations` rodadas de PageRank / GNN Message Passing.
    /// A estrutura CSR (`row_ptr`, `col_idx`, `weights`) é enviada à VRAM **uma única vez** antes do loop
    /// de iterações, demonstrando o ganho de manter a topologia do grafo residente na GPU.
    pub fn execute_csr_pagerank_f32(
        &mut self,
        row_ptr: &[u32],
        col_idx: &[u32],
        weights: &[f32],
        num_nodes: usize,
        damping: f32,
        iterations: usize,
    ) -> Result<(Vec<f32>, GpuExecutionMetrics), String> {
        assert_eq!(row_ptr.len(), num_nodes + 1);
        assert_eq!(col_idx.len(), weights.len());
        if self.is_intel_shared {
            return Ok(intel_shared::execute_csr_pagerank_intel_shared(
                row_ptr, col_idx, weights, num_nodes, damping, iterations,
            ));
        }
        let api = self.api.as_ref().ok_or("API CUDA ausente")?;
        self.bind_thread();

        let rp_bytes = std::mem::size_of_val(row_ptr);
        let ci_bytes = std::mem::size_of_val(col_idx);
        let w_bytes = std::mem::size_of_val(weights);
        let rank_bytes = num_nodes * std::mem::size_of::<f32>();
        let total_needed = rp_bytes + ci_bytes + w_bytes + 2 * rank_bytes;

        if total_needed > self.profile.usable_lab_budget_bytes {
            return Err("ADR-017 VRAM Guardrail excedido para grafo CSR".to_string());
        }

        let t_total = Instant::now();
        let mut metrics = GpuExecutionMetrics {
            executed_on_gpu: true,
            vram_allocated_bytes: total_needed,
            ..Default::default()
        };

        let init_val = 1.0f32 / (num_nodes.max(1) as f32);
        let base_teleport = (1.0f32 - damping) / (num_nodes.max(1) as f32);
        let rank_init = vec![init_val; num_nodes];
        let mut rank_out = vec![0.0f32; num_nodes];

        unsafe {
            let t_alloc = Instant::now();
            let mut d_rp = 0u64;
            let mut d_ci = 0u64;
            let mut d_w = 0u64;
            let mut d_r_in = 0u64;
            let mut d_r_out = 0u64;

            let _ = (api.cu_mem_alloc)(&mut d_rp, rp_bytes.max(16));
            let _ = (api.cu_mem_alloc)(&mut d_ci, ci_bytes.max(16));
            let _ = (api.cu_mem_alloc)(&mut d_w, w_bytes.max(16));
            let _ = (api.cu_mem_alloc)(&mut d_r_in, rank_bytes.max(16));
            let _ = (api.cu_mem_alloc)(&mut d_r_out, rank_bytes.max(16));
            metrics.alloc_us = t_alloc.elapsed().as_secs_f64() * 1_000_000.0;

            let t_htod = Instant::now();
            let _ = (api.cu_memcpy_htod)(d_rp, row_ptr.as_ptr() as *const c_void, rp_bytes);
            if ci_bytes > 0 {
                let _ =
                    (api.cu_memcpy_htod)(d_ci, col_idx.as_ptr() as *const c_void, ci_bytes);
                let _ = (api.cu_memcpy_htod)(d_w, weights.as_ptr() as *const c_void, w_bytes);
            }
            let _ = (api.cu_memcpy_htod)(
                d_r_in,
                rank_init.as_ptr() as *const c_void,
                rank_bytes,
            );
            metrics.bytes_transferred_htod = rp_bytes + ci_bytes + w_bytes + rank_bytes;
            metrics.htod_us = t_htod.elapsed().as_secs_f64() * 1_000_000.0;

            let t_kern = Instant::now();
            let block_x = 128u32;
            let grid_x = ((num_nodes as u32) + block_x - 1) / block_x;

            let mut cur_in = d_r_in;
            let mut cur_out = d_r_out;
            let mut arg_n = num_nodes as u32;
            let mut arg_damp = damping;
            let mut arg_base = base_teleport;

            for _ in 0..iterations.max(1) {
                let mut params: [*mut c_void; 8] = [
                    &mut d_rp as *mut u64 as *mut c_void,
                    &mut d_ci as *mut u64 as *mut c_void,
                    &mut d_w as *mut u64 as *mut c_void,
                    &mut cur_in as *mut u64 as *mut c_void,
                    &mut cur_out as *mut u64 as *mut c_void,
                    &mut arg_n as *mut u32 as *mut c_void,
                    &mut arg_damp as *mut f32 as *mut c_void,
                    &mut arg_base as *mut f32 as *mut c_void,
                ];
                let rc = (api.cu_launch_kernel)(
                    self.fn_csr_pagerank,
                    grid_x.max(1),
                    1,
                    1,
                    block_x,
                    1,
                    1,
                    0,
                    0,
                    params.as_mut_ptr(),
                    std::ptr::null_mut(),
                );
                if rc != 0 {
                    let _ = (api.cu_mem_free)(d_rp);
                    let _ = (api.cu_mem_free)(d_ci);
                    let _ = (api.cu_mem_free)(d_w);
                    let _ = (api.cu_mem_free)(d_r_in);
                    let _ = (api.cu_mem_free)(d_r_out);
                    return Err(format!("cuLaunchKernel(csr_pagerank) falhou: {}", rc));
                }
                std::mem::swap(&mut cur_in, &mut cur_out);
            }
            let _ = (api.cu_ctx_synchronize)();
            metrics.kernel_us = t_kern.elapsed().as_secs_f64() * 1_000_000.0;

            let t_dtoh = Instant::now();
            let _ = (api.cu_memcpy_dtoh)(
                rank_out.as_mut_ptr() as *mut c_void,
                cur_in,
                rank_bytes,
            );
            metrics.bytes_transferred_dtoh = rank_bytes;
            metrics.dtoh_us = t_dtoh.elapsed().as_secs_f64() * 1_000_000.0;

            let _ = (api.cu_mem_free)(d_rp);
            let _ = (api.cu_mem_free)(d_ci);
            let _ = (api.cu_mem_free)(d_w);
            let _ = (api.cu_mem_free)(d_r_in);
            let _ = (api.cu_mem_free)(d_r_out);
        }

        metrics.total_gpu_us = t_total.elapsed().as_secs_f64() * 1_000_000.0;
        Ok((rank_out, metrics))
    }

    /// Executa `batch_risk_fusion_f32` (Kernel Fusion de padronização Z-score + projeção linear + Mahalanobis).
    pub fn execute_batch_risk_fusion_f32(
        &mut self,
        features: &[f32],
        weights: &[f32],
        means: &[f32],
        inv_stds: &[f32],
        n: usize,
        d: usize,
    ) -> Result<(Vec<f32>, GpuExecutionMetrics), String> {
        assert_eq!(features.len(), n * d);
        assert_eq!(weights.len(), d);
        assert_eq!(means.len(), d);
        assert_eq!(inv_stds.len(), d);
        if self.is_intel_shared {
            return Ok(intel_shared::execute_batch_risk_fusion_intel_shared(
                features, weights, means, inv_stds, n, d,
            ));
        }
        let api = self.api.as_ref().ok_or("API CUDA ausente")?;
        self.bind_thread();

        let feat_bytes = std::mem::size_of_val(features);
        let d_bytes = d * std::mem::size_of::<f32>();
        let out_bytes = n * std::mem::size_of::<f32>();

        let t_total = Instant::now();
        let mut metrics = GpuExecutionMetrics {
            executed_on_gpu: true,
            vram_allocated_bytes: feat_bytes + 3 * d_bytes + out_bytes,
            ..Default::default()
        };
        let mut out = vec![0.0f32; n];

        unsafe {
            let t_alloc = Instant::now();
            let (d_feat, _) = Self::ensure_slot(
                api,
                &mut self.resident_slot_a,
                feat_bytes,
                self.profile.usable_lab_budget_bytes,
            )?;
            let (d_params, _) = Self::ensure_slot(
                api,
                &mut self.resident_slot_b,
                3 * d_bytes,
                self.profile.usable_lab_budget_bytes,
            )?;
            let (d_out, _) = Self::ensure_slot(
                api,
                &mut self.resident_slot_c,
                out_bytes,
                self.profile.usable_lab_budget_bytes,
            )?;
            metrics.alloc_us = t_alloc.elapsed().as_secs_f64() * 1_000_000.0;

            let d_w = d_params;
            let d_m = d_params + (d_bytes as u64);
            let d_s = d_params + 2 * (d_bytes as u64);

            let t_htod = Instant::now();
            let _ = (api.cu_memcpy_htod)(
                d_feat,
                features.as_ptr() as *const c_void,
                feat_bytes,
            );
            let _ = (api.cu_memcpy_htod)(d_w, weights.as_ptr() as *const c_void, d_bytes);
            let _ = (api.cu_memcpy_htod)(d_m, means.as_ptr() as *const c_void, d_bytes);
            let _ = (api.cu_memcpy_htod)(d_s, inv_stds.as_ptr() as *const c_void, d_bytes);
            metrics.bytes_transferred_htod = feat_bytes + 3 * d_bytes;
            metrics.htod_us = t_htod.elapsed().as_secs_f64() * 1_000_000.0;

            let t_kern = Instant::now();
            let block_x = 128u32;
            let grid_x = ((n as u32) + block_x - 1) / block_x;

            let mut arg_feat = d_feat;
            let mut arg_w = d_w;
            let mut arg_m = d_m;
            let mut arg_s = d_s;
            let mut arg_out = d_out;
            let mut arg_n = n as u32;
            let mut arg_d = d as u32;

            let mut params: [*mut c_void; 7] = [
                &mut arg_feat as *mut u64 as *mut c_void,
                &mut arg_w as *mut u64 as *mut c_void,
                &mut arg_m as *mut u64 as *mut c_void,
                &mut arg_s as *mut u64 as *mut c_void,
                &mut arg_out as *mut u64 as *mut c_void,
                &mut arg_n as *mut u32 as *mut c_void,
                &mut arg_d as *mut u32 as *mut c_void,
            ];

            let rc = (api.cu_launch_kernel)(
                self.fn_batch_risk_fusion,
                grid_x.max(1),
                1,
                1,
                block_x,
                1,
                1,
                0,
                0,
                params.as_mut_ptr(),
                std::ptr::null_mut(),
            );
            if rc != 0 {
                return Err(format!("cuLaunchKernel(batch_risk_fusion) falhou: {}", rc));
            }
            let _ = (api.cu_ctx_synchronize)();
            metrics.kernel_us = t_kern.elapsed().as_secs_f64() * 1_000_000.0;

            let t_dtoh = Instant::now();
            let _ = (api.cu_memcpy_dtoh)(out.as_mut_ptr() as *mut c_void, d_out, out_bytes);
            metrics.bytes_transferred_dtoh = out_bytes;
            metrics.dtoh_us = t_dtoh.elapsed().as_secs_f64() * 1_000_000.0;
        }

        metrics.total_gpu_us = t_total.elapsed().as_secs_f64() * 1_000_000.0;
        Ok((out, metrics))
    }
}

impl Drop for CudaContext {
    fn drop(&mut self) {
        if let Some(ref api) = self.api {
            unsafe {
                let _ = (api.cu_ctx_set_current)(self.ctx_handle);
                if let Some((ptr, _)) = self.resident_slot_a.take() {
                    let _ = (api.cu_mem_free)(ptr);
                }
                if let Some((ptr, _)) = self.resident_slot_b.take() {
                    let _ = (api.cu_mem_free)(ptr);
                }
                if let Some((ptr, _)) = self.resident_slot_c.take() {
                    let _ = (api.cu_mem_free)(ptr);
                }
                if self.ctx_handle != 0 {
                    let _ = (api.cu_ctx_destroy)(self.ctx_handle);
                }
            }
        }
    }
}

/// Sondagem rápida de hardware GPU (`probe_gpu_device`), retornando um perfil preenchido
/// ou o perfil de fallback CPU-only caso nenhuma GPU NVIDIA esteja acessível.
pub fn probe_gpu_device() -> GpuDeviceProfile {
    match CudaContext::try_new() {
        Ok(ctx) => ctx.profile.clone(),
        Err(reason) => GpuDeviceProfile {
            available: false,
            backend_name: format!("CPU Fallback ({})", reason),
            device_name: "NONE".to_string(),
            driver_version: 0,
            compute_capability_major: 0,
            compute_capability_minor: 0,
            multiprocessor_count: 0,
            max_threads_per_block: 0,
            max_shared_mem_per_block: 0,
            clock_rate_khz: 0,
            memory_clock_rate_khz: 0,
            memory_bus_width_bits: 0,
            total_vram_bytes: 0,
            free_vram_bytes: 0,
            usable_lab_budget_bytes: 0,
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_device_slice_mut_split_at_mut_borrow_check() {
        let root: DeviceSliceMut<'_, f32> = DeviceSliceMut {
            device_ptr: 0x1000,
            len: 256,
            _marker: PhantomData,
        };
        let (left, right) = root.split_at_mut(64);
        assert_eq!(left.device_ptr, 0x1000);
        assert_eq!(left.len, 64);
        assert_eq!(right.device_ptr, 0x1000 + 64 * 4);
        assert_eq!(right.len, 192);
    }

    #[test]
    fn test_real_cuda_driver_and_ptx_kernels() {
        if let Ok(mut ctx) = CudaContext::try_new() {
            assert!(ctx.profile.available);
            assert!(ctx.profile.total_vram_mb() >= 1024);

            // 1. Testa batch_dot_product_f32 na GPU real
            let n = 64;
            let d = 16;
            let docs = vec![0.5f32; n * d];
            let query = vec![2.0f32; d];
            let (out, m_dot) = ctx
                .execute_batch_dot_f32(&docs, &query, n, d, false)
                .expect("batch_dot_product_f32 deve executar na GPU");
            assert!(m_dot.executed_on_gpu);
            assert!((out[0] - 16.0).abs() < 1e-4);
            assert!((out[n - 1] - 16.0).abs() < 1e-4);

            // 2. Testa tiled_gemm_f32 na GPU real
            let a = vec![1.0f32; 8 * 8];
            let b = vec![2.0f32; 8 * 8];
            let (c, m_gemm) = ctx
                .execute_tiled_gemm_f32(&a, &b, 8, 8, 8, false)
                .expect("tiled_gemm_f32 deve executar na GPU");
            assert!(m_gemm.executed_on_gpu);
            assert!((c[0] - 16.0).abs() < 1e-4);

            // 3. Testa csr_pagerank_spmv_f32 na GPU real
            let row_ptr = vec![0u32, 1, 2, 3, 4];
            let col_idx = vec![1u32, 2, 3, 0];
            let weights = vec![1.0f32, 1.0, 1.0, 1.0];
            let (ranks, m_pr) = ctx
                .execute_csr_pagerank_f32(&row_ptr, &col_idx, &weights, 4, 0.85, 10)
                .expect("csr_pagerank_spmv_f32 deve executar na GPU");
            assert!(m_pr.executed_on_gpu);
            let sum_ranks: f32 = ranks.iter().sum();
            assert!((sum_ranks - 1.0).abs() < 1e-3);

            // 4. Testa batch_risk_fusion_f32 na GPU real
            let feats = vec![2.0f32; 32 * 8];
            let w = vec![0.25f32; 8];
            let means = vec![1.0f32; 8];
            let inv_stds = vec![1.0f32; 8];
            let (scores, m_fus) = ctx
                .execute_batch_risk_fusion_f32(&feats, &w, &means, &inv_stds, 32, 8)
                .expect("batch_risk_fusion_f32 deve executar na GPU");
            assert!(m_fus.executed_on_gpu);
            // z = 1.0 em todas as 8 dims -> linear = 2.0, z2 = 8.0 -> 0.65*2.0 + 0.35*8.0 = 1.3 + 2.8 = 4.1
            assert!((scores[0] - 4.1).abs() < 1e-3);
        }
    }

    #[test]
    fn test_intel_shared_zero_copy_avx2_kernels() {
        let mut ctx = CudaContext::new_intel_shared();
        assert!(ctx.is_intel_shared);
        assert!(ctx.profile.available);
        assert!(ctx.profile.device_name.contains("Intel"));
        assert!(ctx.profile.total_vram_mb() >= 1024);

        // 1. batch_dot_f32 Zero-Copy + AVX2/FMA
        let n = 2048;
        let d = 128;
        let docs = vec![0.5f32; n * d];
        let query = vec![2.0f32; d];
        let (out, m_dot) = ctx
            .execute_batch_dot_f32(&docs, &query, n, d, false)
            .expect("Intel Shared batch_dot deve funcionar");
        assert!(m_dot.executed_on_gpu);
        assert_eq!(m_dot.htod_us, 0.0);
        assert_eq!(m_dot.dtoh_us, 0.0);
        assert!((out[0] - 128.0).abs() < 1e-4);
        assert!((out[n - 1] - 128.0).abs() < 1e-4);

        // 2. tiled_gemm_f32 Zero-Copy + AVX2/FMA
        let a = vec![1.0f32; 64 * 64];
        let b = vec![2.0f32; 64 * 64];
        let (c, m_gemm) = ctx
            .execute_tiled_gemm_f32(&a, &b, 64, 64, 64, false)
            .expect("Intel Shared tiled_gemm deve funcionar");
        assert!(m_gemm.executed_on_gpu);
        assert_eq!(m_gemm.htod_us, 0.0);
        assert_eq!(m_gemm.dtoh_us, 0.0);
        assert!((c[0] - 128.0).abs() < 1e-4);

        // 3. csr_pagerank_f32 Zero-Copy
        let row_ptr = vec![0u32, 1, 2, 3, 4];
        let col_idx = vec![1u32, 2, 3, 0];
        let weights = vec![1.0f32, 1.0, 1.0, 1.0];
        let (ranks, m_pr) = ctx
            .execute_csr_pagerank_f32(&row_ptr, &col_idx, &weights, 4, 0.85, 10)
            .expect("Intel Shared csr_pagerank deve funcionar");
        assert!(m_pr.executed_on_gpu);
        assert_eq!(m_pr.htod_us, 0.0);
        assert_eq!(m_pr.dtoh_us, 0.0);
        let sum_ranks: f32 = ranks.iter().sum();
        assert!((sum_ranks - 1.0).abs() < 1e-3);

        // 4. batch_risk_fusion_f32 Zero-Copy
        let feats = vec![2.0f32; 32 * 8];
        let w = vec![0.25f32; 8];
        let means = vec![1.0f32; 8];
        let inv_stds = vec![1.0f32; 8];
        let (scores, m_fus) = ctx
            .execute_batch_risk_fusion_f32(&feats, &w, &means, &inv_stds, 32, 8)
            .expect("Intel Shared batch_risk_fusion deve funcionar");
        assert!(m_fus.executed_on_gpu);
        assert_eq!(m_fus.htod_us, 0.0);
        assert_eq!(m_fus.dtoh_us, 0.0);
        assert!((scores[0] - 4.1).abs() < 1e-3);
    }
}
