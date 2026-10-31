package compute

import (
	"testing"
)

func TestMultiVendorBackendSelectionAndNoRustFallback(t *testing.T) {
	// 1. PC without GPU and without Rust installed -> Pure Go Native CPU
	profNoGpuNoRust := WorkstationProfile{
		HostClass:      "cpu",
		GPUVendor:      VendorNoneCPU,
		HasRustSidecar: false,
		TotalVRAMMB:    0,
		FreeVRAMMB:     0,
	}
	plan1 := SelectMultiVendorExecutionBackend(profNoGpuNoRust, "jev.gnn")
	if plan1.Backend != BackendGoPureNative || !plan1.FallbackToPureGo || plan1.UsedRustSidecar {
		t.Fatalf("expected BackendGoPureNative when Rust is absent, got %+v", plan1)
	}

	// 2. PC with AMD Radeon RX 7800 XT GPU + Rust Sidecar
	profAMD := WorkstationProfile{
		HostClass:      "cpu+dgpu",
		GPUVendor:      VendorAMDRadeon,
		HasDGPU:        true,
		HasAMDGPU:      true,
		HasRustSidecar: true,
		TotalVRAMMB:    16384,
		FreeVRAMMB:     15104,
	}
	planAMD := SelectMultiVendorExecutionBackend(profAMD, "reranker.cross_encoder")
	if planAMD.Backend != BackendAmdRocmWmma || !planAMD.UsedRustSidecar {
		t.Fatalf("expected BackendAmdRocmWmma for AMD Radeon, got %+v", planAMD)
	}

	// 3. PC with Intel Arc / Core Ultra NPU + Rust Sidecar
	profIntel := WorkstationProfile{
		HostClass:      "cpu+igpu+npu",
		GPUVendor:      VendorIntelXPU,
		HasIGPU:        true,
		HasNPU:         true,
		HasRustSidecar: true,
	}
	planIntel := SelectMultiVendorExecutionBackend(profIntel, "kumo.pql")
	if planIntel.Backend != BackendIntelArcXpuNpu || !planIntel.UsedRustSidecar {
		t.Fatalf("expected BackendIntelArcXpuNpu for Intel Arc/NPU, got %+v", planIntel)
	}

	// 4. PC with NVIDIA CUDA GPU + Sufficient VRAM
	profNvidia := WorkstationProfile{
		HostClass:      "cpu+dgpu",
		GPUVendor:      VendorNvidiaCUDA,
		HasDGPU:        true,
		HasRustSidecar: true,
		TotalVRAMMB:    12288,
		FreeVRAMMB:     11008,
	}
	planNvidia := SelectMultiVendorExecutionBackend(profNvidia, "jev.gnn")
	if planNvidia.Backend != BackendNvidiaCudaPTX {
		t.Fatalf("expected BackendNvidiaCudaPTX for NVIDIA RTX, got %+v", planNvidia)
	}

	// 5. PC without GPU (0 VRAM) but with Rust installed -> Rust SIMD CPU
	profCpuRust := WorkstationProfile{
		HostClass:      "cpu",
		GPUVendor:      VendorNoneCPU,
		HasRustSidecar: true,
		TotalVRAMMB:    0,
		FreeVRAMMB:     0,
	}
	planCpuRust := SelectMultiVendorExecutionBackend(profCpuRust, "jev.gnn")
	if planCpuRust.Backend != BackendRustSimdCpu {
		t.Fatalf("expected BackendRustSimdCpu for GPU-less PC with Rust, got %+v", planCpuRust)
	}

	// 6. Verify Pure Go INT8_STATIC parity >= 0.999
	vec := []float32{0.92, -0.45, 0.12, 0.88, -0.73, 0.34, 0.61, -0.19}
	_, _, cos := QuantizeDequantizeInt8StaticGo(vec)
	if cos < 0.999 {
		t.Fatalf("expected INT8 static cosine parity >= 0.999 in Pure Go, got %.5f", cos)
	}
}

func TestHybrid10GBGpuBudget80PctCeilingAndElasticScaling(t *testing.T) {
	// 1. Single repo (trivial workload): must NOT allocate 8 GB just to occupy memory!
	p1 := PlanHybrid10GBGpuBudget(2048, 8192, 1)
	if p1.CombinedTotalMB != 10240 {
		t.Fatalf("expected 10240 MiB combined (2GB + 8GB), got %d", p1.CombinedTotalMB)
	}
	if p1.CombinedAllocatedMB >= 1024 {
		t.Fatalf("expected compact elastic allocation for 1 repo (< 1024 MiB), got %d MiB", p1.CombinedAllocatedMB)
	}

	// 2. Maximum portfolio scale (127 repos): reaches 80% ceiling (1638 MiB Dedicated + 6553 MiB Shared = 8191 MiB)
	pMax := PlanHybrid10GBGpuBudget(2048, 8192, 127)
	if pMax.Tier1AllocatedMB != 1638 || pMax.Tier2AllocatedMB != 6553 || pMax.CombinedAllocatedMB != 8191 {
		t.Fatalf("expected 1638 + 6553 = 8191 MiB at 80%% ceiling, got %+v", pMax)
	}
	if pMax.Tier1UtilizationPct > 80.0 || pMax.Tier2UtilizationPct > 80.0 || pMax.CombinedUtilizationPct > 80.0 {
		t.Fatalf("expected <= 80.0%% utilization across all tiers, got %+v", pMax)
	}
	if pMax.OSAndDisplaySafetyReserveMB < 2048 {
		t.Fatalf("expected >= 2048 MiB OS & display safety reserve (20%%), got %d", pMax.OSAndDisplaySafetyReserveMB)
	}
	if pMax.MaxSekgTemporalEdges < 400_000_000 || pMax.MaxCachedEpisodesM1 < 6_000_000 || pMax.MaxParallelJevNodes < 12_000_000 {
		t.Fatalf("expected massive Squad AI capacity gains at 80%% budget, got edges=%d episodes=%d jev=%d",
			pMax.MaxSekgTemporalEdges, pMax.MaxCachedEpisodesM1, pMax.MaxParallelJevNodes)
	}

	// 3. Extreme overload request (500 repos): strictly clamped at 80% ceiling
	pOver := PlanHybrid10GBGpuBudget(2048, 8192, 500)
	if pOver.Tier1AllocatedMB > 1638 || pOver.Tier2AllocatedMB > 6553 || pOver.CombinedAllocatedMB > 8192 {
		t.Fatalf("expected strict 80%% clamp under 500-repo overload, got %+v", pOver)
	}

	// 4. If Rust sidecar binary is present, verify live JSON-RPC execution of gpu.tiered_10gb_bench
	if DetectRustSidecarAvailable() {
		resp, err := CallRustSidecarJSONRPC("", "gpu.tiered_10gb_bench", 60)
		if err != nil {
			t.Fatalf("expected live gpu.tiered_10gb_bench JSON-RPC response, got error: %v", err)
		}
		resMap, ok := resp["result"].(map[string]any)
		if !ok || resMap["status"] != "PASS_80PCT_HYBRID_10GB_GPU" {
			t.Fatalf("unexpected gpu.tiered_10gb_bench response: %+v", resp)
		}
	}
}
