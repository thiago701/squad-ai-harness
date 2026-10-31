package cultivator

import (
	"testing"

	"github.com/thiago701/squad-ai-harness/internal/cognitive/sekg"
	"github.com/thiago701/squad-ai-harness/internal/compute"
)

func makeTestRecord(id string, seedFeat, nbFeat, recency float32, blocked bool) RelationalEntityRecord {
	var toks [8]sekg.RelGt5DToken
	toks[0] = sekg.RelGt5DToken{
		NodeID:              1,
		D1FeatureNorm:       seedFeat,
		D2EntityTypeEmb:     0.35,
		D3HopDistanceEmb:    0.0,
		D4TemporalDeltaEmb:  recency,
		D5LocalStructureEmb: 0.85,
	}
	for i := 1; i < 8; i++ {
		toks[i] = sekg.RelGt5DToken{
			NodeID:              uint32(i + 1),
			D1FeatureNorm:       nbFeat,
			D2EntityTypeEmb:     0.75,
			D3HopDistanceEmb:    0.5,
			D4TemporalDeltaEmb:  recency,
			D5LocalStructureEmb: 0.80,
		}
	}
	return RelationalEntityRecord{
		EntityID:            id,
		TouchesAuth:         true,
		SubgraphTokens5D:    toks,
		ActualFutureBlocked: blocked,
	}
}

func TestPQLAndRelGTAcrossPureGoAndMultiVendorGPUs(t *testing.T) {
	support := []RelationalEntityRecord{
		makeTestRecord("sup-pos-1", 0.90, 0.88, 0.95, true),
		makeTestRecord("sup-pos-2", 0.78, 0.91, 0.92, true),
		makeTestRecord("sup-neg-1", 0.15, 0.12, 0.18, false),
		makeTestRecord("sup-neg-2", 0.20, 0.14, 0.10, false),
	}
	eval := []RelationalEntityRecord{
		makeTestRecord("mod-propagated-risk", 0.76, 0.91, 0.93, true),
		makeTestRecord("mod-stabilized-old", 0.18, 0.15, 0.12, false),
	}
	pql := "PREDICT COUNT(gate_episodes.gate_state = 'BLOCKED', 0, 7, days) > 0 FOR EACH modules.module_id ASSUMING touches_auth = true"

	// 1. Run on a PC WITHOUT GPU and WITHOUT Rust installed (Pure Go Engine)
	profGoOnly := compute.WorkstationProfile{
		HostClass:      "cpu",
		GPUVendor:      compute.VendorNoneCPU,
		HasRustSidecar: false,
	}
	repGo, err := EvaluatePQLWithRelGT(profGoOnly, pql, support, eval)
	if err != nil {
		t.Fatalf("unexpected PQL error: %v", err)
	}
	if repGo.ExecutionBackend != compute.BackendGoPureNative || repGo.F1Score < 0.99 || repGo.BrierScore > 0.10 {
		t.Fatalf("expected F1=1.0 and Brier<=0.10 on Pure Go engine, got %+v", repGo)
	}

	// 2. Run on Intel Arc / Core Ultra NPU with Rust Sidecar
	profIntel := compute.WorkstationProfile{
		HostClass:      "cpu+igpu+npu",
		GPUVendor:      compute.VendorIntelXPU,
		HasIGPU:        true,
		HasNPU:         true,
		HasRustSidecar: true,
	}
	repIntel, err := EvaluatePQLWithRelGT(profIntel, pql, support, eval)
	if err != nil || repIntel.ExecutionBackend != compute.BackendIntelArcXpuNpu || repIntel.F1Score < 0.99 {
		t.Fatalf("expected Intel XPU backend with F1=1.0, got %+v (err=%v)", repIntel, err)
	}

	// 3. POC-001: Verify EvaluatePredictiveFailurePOC001 integrated into cultivator
	repPOC001, err := EvaluatePredictiveFailurePOC001(profGoOnly, nil, 0)
	if err != nil || repPOC001.F1Score < 0.99 || repPOC001.BrierScore > 0.10 {
		t.Fatalf("POC-001 cultivator failure prediction failed: %+v (err=%v)", repPOC001, err)
	}
}
