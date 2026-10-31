// Package compute implements the Cognitive Compute Router (C0 Go Deterministic ->
// C1 Local NPU/GPU/CPU Assist -> C2 Specialized LLM) absorbing the empirical laws from
// SUPERDOC NPU-GPU-CPU (SPEC-NPU-GPU v2, ADR-014, ADR-017, Core Ultra 7 165U & WORKSTATION-GPU RTX 3060):
//   - Device selection comes from MEASUREMENT (~/.squad-ai/workstation.json "medido"), never fixed rules.
//   - Cosine cache HIT is REJECTED in all spaces; neural embeddings run strictly in "assist_only"
//     until a dedicated cross-encoder verifier is active.
//   - Core Ultra 165U NPU<->iGPU inversion: NPU wins interactive B=1 RAG query e2e (53.3ms vs 83.5ms iGPU,
//     1.62x vs CPU) due to zero host<->device copy overhead on SoC, while iGPU Arc FP32 wins batch B=16/64
//     kernel throughput (241.6 it/s = 19x vs CPU) and contention (11.76ms vs 16.37ms).
//   - WORKSTATION-GPU RTX 3060 (CUDA): 24-27x batch indexing (B=256); CPU+CUDA partitioning is forbidden on weak
//     CPUs (<= 4 cores); 3-tenant VRAM slices (1280/2048/5888/3072 MB) forbid co-loading Laya+LLM with Embedding.
//   - Quantization gate: INT8-ONNX dynamic is rejected on iGPU/NPU (NaN/0.80 parity break); INT8-NNCF static
//     (calibrated on sealed Golden v1) is allowed for CPU VNNI (2.07x); INT4 is rejected for embeddings (cos 0.936).
//   - 3-Layer Cascade Fallback: Device -> Backend -> Space (space_id change forces consumer reindexing).
package compute

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"time"
)

// ComputeLayer identifies the execution tier selected by the Cognitive Compute Router.
type ComputeLayer string

const (
	LayerC0Deterministic ComputeLayer = "C0_GO_DETERMINISTIC"
	LayerC1LocalAssist   ComputeLayer = "C1_LOCAL_ACCEL_ASSIST"
	LayerC2LLM           ComputeLayer = "C2_LLM_SPECIALIST"
)

// HitPolicy enforces ADR-014: neural embeddings never trigger blind cosine cache hits.
type HitPolicy string

const (
	HitPolicyAssistOnly HitPolicy = "assist_only"
	HitPolicyVerified   HitPolicy = "verified"
)

// Canonical SpaceIDs for Layer 3 fallback and reindexing (SPEC-NPU-GPU v2 §4.3).
const (
	SpaceIDTFIDF          = "tfidf"
	SpaceIDNeuralE5Small  = "neural:multilingual-e5-small@614241f6:mean"
	SpaceIDNeuralBGESmall = "neural:bge-small-en-v1.5@5c38ec7c:cls"
	SpaceIDNeuralMiniLM   = "neural:paraphrase-multilingual-MiniLM-L12-v2@e8f8c211:mean"
)

// VRAMBudget defines the measured 3-tenant VRAM slices on 12 GB NVIDIA RTX 3060 (WORKSTATION-GPU, ADR-017).
const (
	VRAMSystemReserveMB  = 1280
	VRAMTenantEmbedMB    = 2048
	VRAMTenantLayaJevMB  = 5888
	VRAMTenantLocalLLMMB = 3072
	VRAMSafetyMarginMB   = 512
)

// GPUVendor identifies the hardware accelerator vendor on the workstation (or VendorNoneCPU if GPU-less).
type GPUVendor string

const (
	VendorNoneCPU    GPUVendor = "NONE_CPU_ONLY"
	VendorNvidiaCUDA GPUVendor = "NVIDIA_CUDA"
	VendorAMDRadeon  GPUVendor = "AMD_ROCM_WMMA"
	VendorIntelXPU   GPUVendor = "INTEL_XPU_ARC_NPU"
)

// WorkstationProfile represents the hardware acceleration capabilities and calibrated policy of the host.
type WorkstationProfile struct {
	HostClass         string         `json:"host_class"` // "cpu", "cpu+igpu", "cpu+npu", "cpu+igpu+npu", "cpu+dgpu", "cpu+dgpu+npu"
	Runtime           string         `json:"runtime"`    // "go-native", "openvino", "onnxruntime", "rust-sidecar"
	Origin            string         `json:"origin"`     // "default", "detectado", "calibrado"
	GPUVendor         GPUVendor      `json:"gpu_vendor,omitempty"`
	GPUName           string         `json:"gpu_name,omitempty"`
	HasNPU            bool           `json:"has_npu"`
	HasIGPU           bool           `json:"has_igpu"`
	HasDGPU           bool           `json:"has_dgpu"`
	HasAMDGPU         bool           `json:"has_amd_gpu,omitempty"`
	HasRustSidecar    bool           `json:"has_rust_sidecar,omitempty"`
	TotalVRAMMB       int64          `json:"total_vram_mb"`
	FreeVRAMMB        int64          `json:"free_vram_mb"`
	EmbeddingPolicy   HitPolicy      `json:"embedding_policy"`
	ActiveSpaceID     string         `json:"active_space_id"`
	CPUCores          int            `json:"cpu_cores"`
	PhysicalCores     int            `json:"physical_cores"`
	QueryDeviceOrder  []string       `json:"query_device_order,omitempty"`
	IndexDeviceOrder  []string       `json:"index_device_order,omitempty"`
	IndexPartition    []string       `json:"index_partition,omitempty"`
	IndexBucketsB     []int          `json:"index_buckets_b,omitempty"`
	OptimalNireq      map[string]int `json:"optimal_nireq,omitempty"`
}

// RouteDecision describes how a cognitive workload was routed across C0/C1/C2.
type RouteDecision struct {
	Workload        string       `json:"workload"`
	SelectedLayer   ComputeLayer `json:"selected_layer"`
	Device          string       `json:"device"` // "CPU_GO", "NPU_INTEL", "IGPU_INTEL", "DGPU_CUDA", "LLM_HAIKU", "LLM_SONNET", "LLM_OPUS"
	Precision       string       `json:"precision,omitempty"`
	HitPolicy       HitPolicy    `json:"hit_policy"`
	SpaceID         string       `json:"space_id,omitempty"`
	ReindexRequired bool         `json:"reindex_required,omitempty"`
	StaticBucket    string       `json:"static_bucket,omitempty"` // e.g., "B=1,L=64,LATENCY" or "B=256,L=128,THROUGHPUT"
	EstimatedCost   float64      `json:"estimated_cost_usd"`
	Reason          string       `json:"reason"`
}

// PromotionGateInput captures the criteria required to promote an accelerator/model in production (SUPERDOC §8.1).
type PromotionGateInput struct {
	CosineParityVsCPU float64
	SpeedupVsBaseline float64
	Repetitions       int
	GoldenSealed      bool
	NoSealedRegressed bool
	HumanApproved     bool
}

// EvaluateAccelPromotion enforces the strict gated promotion rule (SUPERDOC §8.1):
// Parity (cos >= 0.99) AND Speedup > 1.0 with N >= 3 AND GoldenSealed AND NoSealedRegressed AND HumanApproved.
func EvaluateAccelPromotion(in PromotionGateInput) (bool, string) {
	if in.CosineParityVsCPU < 0.99 {
		return false, fmt.Sprintf("REPROVADO: paridade de cosseno %.4f < 0.99 vs CPU FP32", in.CosineParityVsCPU)
	}
	if in.Repetitions < 3 {
		return false, fmt.Sprintf("REPROVADO: repetições N=%d < 3 exigidas pelo protocolo", in.Repetitions)
	}
	if in.SpeedupVsBaseline <= 1.0 {
		return false, fmt.Sprintf("REPROVADO: speedup %.2fx não supera o baseline (> 1.0x)", in.SpeedupVsBaseline)
	}
	if !in.GoldenSealed {
		return false, "REPROVADO: dataset golden não está selado por humano (veredito apenas provisório)"
	}
	if !in.NoSealedRegressed {
		return false, "REPROVADO: regressão detectada contra ganho selado no ratchet-qualidade"
	}
	if !in.HumanApproved {
		return false, "PENDENTE_GATE_HUMANO: promoção exige ADR + aprovação humana explícita"
	}
	return true, "APROVADO: paridade cos>=0.99, ganho provado (N>=3), golden selado e gate humano aprovado"
}

// ValidatePrecisionForDevice enforces empirical quantization rules (SUPERDOC §2c/d, §4.2, §9.8):
//   - INT4 is rejected for embeddings (cos = 0.936 < 0.99).
//   - INT8_ONNX_DYNAMIC is rejected on IGPU/NPU (breaks parity: iGPU cos=NaN, NPU cos=0.80).
//   - INT8_NNCF_STATIC (calibrated on Golden v1, cos>=0.997) is approved on CPU (2.07x VNNI),
//     while FP16/FP32 is preferred on IGPU/NPU.
func ValidatePrecisionForDevice(device, precision string) (bool, string) {
	dev := strings.ToUpper(device)
	prec := strings.ToUpper(precision)
	if prec == "INT4" {
		return false, "INT4 rejeitado para embeddings (paridade cos=0.936 < 0.99)"
	}
	if prec == "INT8_ONNX_DYNAMIC" && (strings.Contains(dev, "IGPU") || strings.Contains(dev, "GPU") || strings.Contains(dev, "NPU")) {
		return false, "INT8-ONNX dinâmico reprovado em iGPU/NPU (quebra paridade: iGPU cos=NaN, NPU cos=0.80)"
	}
	if prec == "INT8_NNCF_STATIC" && (strings.Contains(dev, "IGPU") || strings.Contains(dev, "NPU")) {
		return false, "INT8-NNCF estático só traz ganho em CPU (VNNI 2.07x); em iGPU/NPU use FP16/FP32"
	}
	return true, "precisão validada para o dispositivo"
}

// CircuitBreaker3Layer isolates failures at Specialist, Attempt, and Model/Device levels.
type CircuitBreaker3Layer struct {
	mu               sync.Mutex
	specialistFails  map[string]int
	modelCooldownEnd map[string]time.Time
	activeSpaceID    string
}

// NewCircuitBreaker creates a 3-layer resilience breaker.
func NewCircuitBreaker() *CircuitBreaker3Layer {
	return &CircuitBreaker3Layer{
		specialistFails:  make(map[string]int),
		modelCooldownEnd: make(map[string]time.Time),
		activeSpaceID:    SpaceIDTFIDF,
	}
}

// RecordFailure increments failure counters and trips model/device cooldown if threshold (>= 2) is reached.
func (cb *CircuitBreaker3Layer) RecordFailure(specialist, modelOrDevice string) {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	cb.specialistFails[specialist]++
	if cb.specialistFails[specialist] >= 2 {
		cb.modelCooldownEnd[modelOrDevice] = time.Now().Add(60 * time.Second)
	}
}

// IsModelHealthy returns true if the model or hardware device is not in lockout cooldown.
func (cb *CircuitBreaker3Layer) IsModelHealthy(modelOrDevice string) bool {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	until, exists := cb.modelCooldownEnd[modelOrDevice]
	if !exists {
		return true
	}
	if time.Now().After(until) {
		delete(cb.modelCooldownEnd, modelOrDevice)
		return true
	}
	return false
}

// TransitionSpace updates the active embedding space and reports whether consumers must reindex (Layer 3 cascade).
func (cb *CircuitBreaker3Layer) TransitionSpace(newSpaceID string) bool {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	if newSpaceID == "" || cb.activeSpaceID == newSpaceID {
		return false
	}
	cb.activeSpaceID = newSpaceID
	return true
}

// FilterPhantomOpenVINOGPUs applies the 24/10/2026 _merge_nvidia fix:
// When NVIDIA CUDA is present via nvidia-smi, OpenVINO 2026.4 may enumerate the RTX as a generic discrete "GPU"
// without FULL_DEVICE_NAME. Any discrete GPU without a non-NVIDIA vendor name (Intel/AMD) is discarded,
// while integrated Intel iGPUs are preserved.
func FilterPhantomOpenVINOGPUs(devices map[string]map[string]any, hasNvidiaCUDA bool) map[string]map[string]any {
	out := make(map[string]map[string]any, len(devices))
	for dev, info := range devices {
		if strings.HasPrefix(dev, "GPU") {
			name := strings.ToLower(fmt.Sprint(info["nome"]))
			devType := strings.ToLower(fmt.Sprint(info["tipo"]))
			if isNvidiaName(name) {
				continue
			}
			if hasNvidiaCUDA && !strings.Contains(devType, "integrated") && !isNonNvidiaVendorName(name) {
				// Phantom discrete GPU enumerated by OpenVINO without FULL_DEVICE_NAME when CUDA is present
				continue
			}
		}
		out[dev] = info
	}
	return out
}

func isNvidiaName(lowerName string) bool {
	for _, k := range []string{"nvidia", "geforce", "quadro", "tesla", "rtx", "gtx"} {
		if strings.Contains(lowerName, k) {
			return true
		}
	}
	return false
}

func isNonNvidiaVendorName(lowerName string) bool {
	for _, k := range []string{"intel", "arc", "iris", "uhd", "amd", "radeon"} {
		if strings.Contains(lowerName, k) {
			return true
		}
	}
	return false
}

// DetectWorkstation loads ~/.squad-ai/workstation.json (both SPEC-NPU-GPU v2 Portuguese schema and English keys)
// or returns the safe CPU-first profile. Never panics or fails.
func DetectWorkstation() WorkstationProfile {
	prof := WorkstationProfile{
		HostClass:        "cpu",
		Runtime:          "go-native",
		Origin:           "default",
		GPUVendor:        VendorNoneCPU,
		HasRustSidecar:   DetectRustSidecarAvailable(),
		EmbeddingPolicy:  HitPolicyAssistOnly,
		ActiveSpaceID:    SpaceIDTFIDF,
		CPUCores:         runtime.NumCPU(),
		PhysicalCores:    runtime.NumCPU(),
		QueryDeviceOrder: []string{"CPU"},
		IndexDeviceOrder: []string{"CPU"},
		IndexBucketsB:    []int{16, 64},
	}

	wsPath := os.Getenv("SQUAD_WORKSTATION_PROFILE")
	if wsPath == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			return prof
		}
		wsPath = filepath.Join(home, ".squad-ai", "workstation.json")
	}
	raw, err := os.ReadFile(wsPath)
	if err != nil {
		if os.Getenv("SQUAD_DISABLE_LIVE_GPU_PROBE") == "1" {
			return prof
		}
		return ProbePhysicalGPUViaSidecar(prof)
	}
	return ParseWorkstationJSON(raw, prof)
}

// ParseWorkstationJSON parses a workstation.json payload (supporting both SPEC-NPU-GPU v2 and legacy schemas).
func ParseWorkstationJSON(raw []byte, fallback WorkstationProfile) WorkstationProfile {
	prof := fallback
	var doc struct {
		Class        string                    `json:"class"`
		Classe       string                    `json:"classe"`
		Runtime      string                    `json:"runtime"`
		Origem       string                    `json:"origem"`
		HasNPU       bool                      `json:"has_npu"`
		HasIGPU      bool                      `json:"has_igpu"`
		HasDGPU      bool                      `json:"has_dgpu"`
		VRAMMB       int64                     `json:"vram_mb"`
		Dispositivos map[string]map[string]any `json:"dispositivos"`
		Nvidia       struct {
			GPUs []struct {
				MemMB int64 `json:"mem_mb"`
			} `json:"gpus"`
		} `json:"nvidia"`
		Host struct {
			NucleosFisicos int `json:"nucleos_fisicos"`
			Logicos        int `json:"logicos"`
		} `json:"host"`
		Politica map[string]struct {
			Ordem    []string `json:"ordem"`
			Particao []string `json:"particao"`
			B        []int    `json:"B"`
			Origem   string   `json:"origem"`
		} `json:"politica"`
	}
	if json.Unmarshal(raw, &doc) != nil {
		return prof
	}

	if doc.Classe != "" {
		prof.HostClass = doc.Classe
	} else if doc.Class != "" {
		prof.HostClass = doc.Class
	}
	if doc.Runtime != "" {
		prof.Runtime = doc.Runtime
	}
	if doc.Origem != "" {
		prof.Origin = doc.Origem
	}
	if doc.Host.NucleosFisicos > 0 {
		prof.PhysicalCores = doc.Host.NucleosFisicos
	}
	if doc.Host.Logicos > 0 {
		prof.CPUCores = doc.Host.Logicos
	}

	hasCUDA := len(doc.Nvidia.GPUs) > 0 || doc.HasDGPU
	cleanedDevs := FilterPhantomOpenVINOGPUs(doc.Dispositivos, hasCUDA)
	for dev, info := range cleanedDevs {
		devName := strings.ToLower(fmt.Sprint(info["nome"]))
		if prof.GPUName == "" && devName != "" && devName != "<nil>" {
			prof.GPUName = fmt.Sprint(info["nome"])
		}
		if strings.Contains(devName, "amd") || strings.Contains(devName, "radeon") || strings.Contains(devName, "instinct") {
			prof.HasAMDGPU = true
			prof.GPUVendor = VendorAMDRadeon
		} else if strings.Contains(devName, "intel") || strings.Contains(devName, "arc") || strings.Contains(devName, "iris") || strings.Contains(devName, "uhd") {
			if prof.GPUVendor == "" || prof.GPUVendor == VendorNoneCPU {
				prof.GPUVendor = VendorIntelXPU
			}
		} else if isNvidiaName(devName) {
			prof.GPUVendor = VendorNvidiaCUDA
		}
		switch {
		case strings.HasPrefix(dev, "NPU"):
			prof.HasNPU = true
			if prof.GPUVendor == "" || prof.GPUVendor == VendorNoneCPU {
				prof.GPUVendor = VendorIntelXPU
			}
		case strings.HasPrefix(dev, "CUDA"):
			if exec, ok := info["executavel"].(bool); !ok || exec {
				prof.HasDGPU = true
				prof.GPUVendor = VendorNvidiaCUDA
			}
		case strings.HasPrefix(dev, "ROCM") || strings.HasPrefix(dev, "HIP") || strings.HasPrefix(dev, "AMDGPU"):
			prof.HasDGPU = true
			prof.HasAMDGPU = true
			prof.GPUVendor = VendorAMDRadeon
		case strings.HasPrefix(dev, "GPU"):
			devType := strings.ToLower(fmt.Sprint(info["tipo"]))
			if strings.Contains(devType, "discrete") {
				prof.HasDGPU = true
			} else {
				prof.HasIGPU = true
			}
		}
	}
	noDevsMap := len(doc.Dispositivos) == 0
	if doc.HasNPU || (noDevsMap && strings.Contains(prof.HostClass, "npu")) {
		prof.HasNPU = true
		if prof.GPUVendor == "" {
			prof.GPUVendor = VendorIntelXPU
		}
	}
	if doc.HasIGPU || (noDevsMap && strings.Contains(prof.HostClass, "igpu")) {
		prof.HasIGPU = true
		if prof.GPUVendor == "" {
			prof.GPUVendor = VendorIntelXPU
		}
	}
	if doc.HasDGPU || (noDevsMap && strings.Contains(prof.HostClass, "dgpu")) {
		prof.HasDGPU = true
		if prof.GPUVendor == "" {
			prof.GPUVendor = VendorNvidiaCUDA
		}
	}
	if prof.GPUVendor == "" {
		prof.GPUVendor = VendorNoneCPU
	}
	prof.HasRustSidecar = DetectRustSidecarAvailable()

	if doc.VRAMMB > 0 {
		prof.TotalVRAMMB = doc.VRAMMB
	} else if len(doc.Nvidia.GPUs) > 0 && doc.Nvidia.GPUs[0].MemMB > 0 {
		prof.TotalVRAMMB = doc.Nvidia.GPUs[0].MemMB
	}
	if prof.TotalVRAMMB > VRAMSystemReserveMB {
		prof.FreeVRAMMB = prof.TotalVRAMMB - VRAMSystemReserveMB
	}

	if qPol, ok := doc.Politica["embed.query"]; ok && len(qPol.Ordem) > 0 {
		prof.QueryDeviceOrder = qPol.Ordem
	}
	if ixPol, ok := doc.Politica["embed.index"]; ok {
		if len(ixPol.Ordem) > 0 {
			prof.IndexDeviceOrder = ixPol.Ordem
		}
		if len(ixPol.Particao) > 0 {
			prof.IndexPartition = ixPol.Particao
		}
		if len(ixPol.B) > 0 {
			prof.IndexBucketsB = ixPol.B
		}
	}
	if prof.HasNPU || prof.HasIGPU || prof.HasDGPU {
		prof.ActiveSpaceID = SpaceIDNeuralE5Small
	}
	return prof
}

// AdmitVRAM checks whether a single GPU tenant can be admitted while preserving the 512 MB safety margin.
func AdmitVRAM(freeVRAMMB, tenantRequiredMB int64) bool {
	return (freeVRAMMB - tenantRequiredMB) >= VRAMSafetyMarginMB
}

// AdmitVRAMMultiTenant enforces the WORKSTATION-GPU 3-tenant VRAM governance rule (SUPERDOC §2, §7.4):
// Slices: system=1280 MB, embedding=2048 MB, laya=5888 MB, llm=3072 MB.
// Never co-load Laya + Local LLM alongside Embedding on 12 GB VRAM (peak 11,783 MB violates the 512 MB safety margin).
func AdmitVRAMMultiTenant(totalVRAMMB int64, activeTenants []string, candidateTenant string) (bool, string) {
	sliceOf := func(t string) int64 {
		switch strings.ToLower(t) {
		case "embedding", "embed":
			return VRAMTenantEmbedMB
		case "laya", "jev_encoder":
			return VRAMTenantLayaJevMB
		case "llm", "local_llm":
			return VRAMTenantLocalLLMMB
		default:
			return 1024
		}
	}

	usedMB := int64(VRAMSystemReserveMB)
	hasEmbed, hasLaya, hasLLM := false, false, false
	all := append(append([]string{}, activeTenants...), candidateTenant)
	for _, t := range all {
		usedMB += sliceOf(t)
		switch strings.ToLower(t) {
		case "embedding", "embed":
			hasEmbed = true
		case "laya", "jev_encoder":
			hasLaya = true
		case "llm", "local_llm":
			hasLLM = true
		}
	}

	if hasEmbed && hasLaya && hasLLM && totalVRAMMB <= 12288 {
		return false, "BLOQUEADO (ADR-017): proibido co-alocar embedding + laya + llm local em 12 GB VRAM (pico 11.783 MB viola margem de 512 MB)"
	}
	if (totalVRAMMB - usedMB) < VRAMSafetyMarginMB {
		return false, fmt.Sprintf("BLOQUEADO: VRAM insuficiente (usado=%d MB, total=%d MB, margem exigida=%d MB)",
			usedMB, totalVRAMMB, VRAMSafetyMarginMB)
	}
	return true, fmt.Sprintf("ADMITIDO: VRAM livre pós-alocação = %d MB (>= %d MB margem)", totalVRAMMB-usedMB, VRAMSafetyMarginMB)
}

// RouteWorkload selects the optimal compute layer and device according to P1 > P2 > P3, ADR-014, ADR-017, and ADR-024.
func RouteWorkload(prof WorkstationProfile, cb *CircuitBreaker3Layer, workload string, batchSize int, tokenLen int, riskCritical bool) RouteDecision {
	// 1. Deterministic tasks ALWAYS run in Layer C0 (Go native on CPU, < 2ms, $0)
	switch workload {
	case "jev.review", "sonar.check", "sekg.impact", "catalog.validate", "secret.scan", "git.sync":
		return RouteDecision{
			Workload:      workload,
			SelectedLayer: LayerC0Deterministic,
			Device:        "CPU_GO",
			Precision:     "DETERMINISTIC",
			HitPolicy:     HitPolicyVerified,
			EstimatedCost: 0.0,
			Reason:        "Tarefa determinística executada em Camada C0 Go nativo (< 2ms, 0 tokens)",
		}
	}

	// 2. Embedding / Rerank tasks run in Layer C1 (strictly assist_only per ADR-014; cosine HIT = REJECT)
	if workload == "embed.query" || workload == "embed.index" {
		return routeEmbeddingWorkload(prof, cb, workload, batchSize, tokenLen)
	}

	// 3. Generative / Deep Reasoning tasks escalate to Layer C2 (LLM Tier with fallback chain)
	preferredModel := "LLM_SONNET"
	if riskCritical {
		preferredModel = "LLM_OPUS"
	} else if workload == "explore" || workload == "community.summarize" {
		preferredModel = "LLM_HAIKU"
	}

	if cb != nil && !cb.IsModelHealthy(preferredModel) {
		switch preferredModel {
		case "LLM_OPUS":
			preferredModel = "LLM_SONNET"
		case "LLM_SONNET":
			preferredModel = "LLM_HAIKU"
		}
	}

	return RouteDecision{
		Workload:      workload,
		SelectedLayer: LayerC2LLM,
		Device:        preferredModel,
		HitPolicy:     HitPolicyVerified,
		EstimatedCost: estimateLLMCost(preferredModel, tokenLen),
		Reason:        "Escalação seletiva para Camada C2 com proteção de Circuit Breaker",
	}
}

func routeEmbeddingWorkload(prof WorkstationProfile, cb *CircuitBreaker3Layer, workload string, batchSize int, tokenLen int) RouteDecision {
	bucketL := selectBucketLength(tokenLen)

	// Case A: Station with Intel NPU (e.g., Core Ultra 7 165U — cpu+igpu+npu or cpu+npu)
	// Empirical law (SUPERDOC §2 27/10/2026):
	//   - Interactive query (B=1): NPU wins RAG e2e (53.3 ms vs 83.5 ms iGPU vs 86.6 ms CPU = 1.62x)
	//     because iGPU pays host<->device copy overhead per call while SoC-integrated NPU does not.
	//   - Batch indexing (B>=16): iGPU Arc FP32 wins kernel throughput (241.6 it/s = 19x vs CPU) and contention
	//     (11.76 ms vs 16.37 ms NPU); for >= 256 items, partition across NPU + iGPU + CPU via work-stealing queue.
	if prof.HasNPU && (cb == nil || cb.IsModelHealthy("NPU_INTEL")) {
		if workload == "embed.query" || batchSize <= 1 {
			return RouteDecision{
				Workload:      workload,
				SelectedLayer: LayerC1LocalAssist,
				Device:        "NPU_INTEL",
				Precision:     "FP16",
				HitPolicy:     HitPolicyAssistOnly,
				SpaceID:       SpaceIDNeuralE5Small,
				StaticBucket:  "B=1,L=" + bucketL + ",LATENCY",
				EstimatedCost: 0.0,
				Reason:        "Core Ultra NPU-first para query B=1 interativa (53,3 ms p50 = 1,62x vs CPU, zero cópia host<->device, assist_only)",
			}
		}
		if prof.HasIGPU && batchSize < 256 {
			return RouteDecision{
				Workload:      workload,
				SelectedLayer: LayerC1LocalAssist,
				Device:        "IGPU_INTEL_FP32",
				Precision:     "FP32",
				HitPolicy:     HitPolicyAssistOnly,
				SpaceID:       SpaceIDNeuralE5Small,
				StaticBucket:  "B=16,L=" + bucketL + ",THROUGHPUT",
				EstimatedCost: 0.0,
				Reason:        "iGPU Intel Arc FP32 vence lote médio e sob contenção (241,6 it/s B16, cos=1.0, assist_only)",
			}
		}
		return RouteDecision{
			Workload:      workload,
			SelectedLayer: LayerC1LocalAssist,
			Device:        "NPU_IGPU_PARTITIONED",
			Precision:     "FP16",
			HitPolicy:     HitPolicyAssistOnly,
			SpaceID:       SpaceIDNeuralE5Small,
			StaticBucket:  "B=64,L=" + bucketL + ",THROUGHPUT",
			EstimatedCost: 0.0,
			Reason:        "Partição multi-dispositivo (lote >= 256) entre NPU + iGPU Intel via fila work-stealing (assist_only)",
		}
	}

	// Case B: Station with Intel Shared iGPU (cpu+igpu, e.g., Intel UHD Graphics / Iris Xe Shared WDDM)
	// When Rust Sidecar Zero-Copy WDDM + AVX2/FMA is active, host<->device copy is 0.00 us (Unified Memory),
	// accelerating both interactive B=1 queries and batch B>1 indexing with 100% FP32 parity!
	if prof.HasIGPU && (cb == nil || cb.IsModelHealthy("IGPU_INTEL")) {
		if prof.HasRustSidecar {
			bStr := "B=1"
			modeHint := "LATENCY"
			if workload == "embed.index" && batchSize > 1 {
				bStr = "B=64"
				modeHint = "THROUGHPUT"
			}
			return RouteDecision{
				Workload:      workload,
				SelectedLayer: LayerC1LocalAssist,
				Device:        "IGPU_INTEL_SHARED_FP32",
				Precision:     "FP32",
				HitPolicy:     HitPolicyAssistOnly,
				SpaceID:       SpaceIDNeuralE5Small,
				StaticBucket:  bStr + ",L=" + bucketL + "," + modeHint,
				EstimatedCost: 0.0,
				Reason:        "iGPU Intel Compartilhada (Zero-Copy WDDM Unified Memory 0.00 us + AVX2/FMA Subgroup Tile, cos=1.0, assist_only)",
			}
		}
		if workload == "embed.index" && batchSize > 1 {
			return RouteDecision{
				Workload:      workload,
				SelectedLayer: LayerC1LocalAssist,
				Device:        "IGPU_INTEL_FP32",
				Precision:     "FP32",
				HitPolicy:     HitPolicyAssistOnly,
				SpaceID:       SpaceIDNeuralE5Small,
				StaticBucket:  "B=16,L=" + bucketL + ",THROUGHPUT",
				EstimatedCost: 0.0,
				Reason:        "iGPU Intel FP32 para indexação em lote (assist_only)",
			}
		}
	}

	// Case C: Station with NVIDIA dGPU CUDA (e.g., WORKSTATION-GPU RTX 3060 12 GB — cpu+dgpu)
	// Empirical law (SUPERDOC §2 17-18/10/2026):
	//   - 24-27x CUDA vs CPU on batch indexing (B=256 when calibrated).
	//   - NEVER partition CPU+CUDA when CPU has <= 4 cores (weak CPU delays GPU -> policy ['CUDA'] only).
	if prof.HasDGPU && AdmitVRAM(prof.FreeVRAMMB, VRAMTenantEmbedMB) && (cb == nil || cb.IsModelHealthy("DGPU_CUDA")) {
		batchBucket := "B=64"
		for _, b := range prof.IndexBucketsB {
			if b == 256 && batchSize >= 64 {
				batchBucket = "B=256"
				break
			}
		}
		reason := "dGPU CUDA exclusiva ['CUDA'] (24-27x vs CPU, margem >= 512 MB VRAM, sem partição CPU+CUDA em CPU fraca, assist_only)"
		return RouteDecision{
			Workload:      workload,
			SelectedLayer: LayerC1LocalAssist,
			Device:        "DGPU_CUDA",
			Precision:     "FP16",
			HitPolicy:     HitPolicyAssistOnly,
			SpaceID:       SpaceIDNeuralE5Small,
			StaticBucket:  batchBucket + ",L=" + bucketL + ",THROUGHPUT",
			EstimatedCost: 0.0,
			Reason:        reason,
		}
	}

	// Case D1: Station without NPU/dGPU (or B=1 on cpu+igpu), but with local neural runtime (OpenVINO / ONNX Runtime CPU)
	if (prof.Runtime == "openvino" || prof.Runtime == "onnxruntime") && (cb == nil || cb.IsModelHealthy("CPU_NEURAL")) {
		bStr := "B=1"
		hint := "LATENCY"
		if workload == "embed.index" && batchSize > 1 {
			bStr = "B=16"
			hint = "THROUGHPUT"
		}
		return RouteDecision{
			Workload:      workload,
			SelectedLayer: LayerC1LocalAssist,
			Device:        "CPU_NEURAL_INT8_NNCF",
			Precision:     "INT8_NNCF_STATIC",
			HitPolicy:     HitPolicyAssistOnly,
			SpaceID:       SpaceIDNeuralE5Small,
			StaticBucket:  bStr + ",L=" + bucketL + "," + hint,
			EstimatedCost: 0.0,
			Reason:        "Estação CPU/iGPU com runtime neural local (OpenVINO/ORT CPU INT8-NNCF VNNI 2,07x ou FP32, assist_only)",
		}
	}

	// Case D2: Layer 2 & Layer 3 Fallback to CPU deterministic BM25/CSR (Zero-GPU, Zero-NPU, Zero-Python/OpenVINO)
	reindex := false
	if cb != nil {
		reindex = cb.TransitionSpace(SpaceIDTFIDF)
	}
	return RouteDecision{
		Workload:        workload,
		SelectedLayer:   LayerC0Deterministic,
		Device:          "CPU_GO",
		Precision:       "BM25_CSR_INT8_NNCF",
		HitPolicy:       HitPolicyAssistOnly,
		SpaceID:         SpaceIDTFIDF,
		ReindexRequired: reindex,
		EstimatedCost:   0.0,
		Reason:          "Estação sem NPU/dGPU disponível: fallback determinístico BM25/CSR em Go",
	}
}

func selectBucketLength(tokenLen int) string {
	switch {
	case tokenLen <= 32:
		return "32"
	case tokenLen <= 64:
		return "64"
	case tokenLen <= 128:
		return "128"
	default:
		return "256"
	}
}

func estimateLLMCost(model string, tokens int) float64 {
	if tokens <= 0 {
		tokens = 1000
	}
	switch model {
	case "LLM_HAIKU":
		return float64(tokens) * 0.000001
	case "LLM_SONNET":
		return float64(tokens) * 0.000003
	case "LLM_OPUS":
		return float64(tokens) * 0.000015
	default:
		return 0.0
	}
}
