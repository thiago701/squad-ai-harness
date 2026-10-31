package jev

import (
	"testing"

	"github.com/thiago701/squad-ai-harness/internal/compute"
)

func TestJevStructuralSpecialistsAndHybridGNNAcrossVendors(t *testing.T) {
	// 1. Structural Hexagonal breach caught in Pure Go
	hexBreach := ReviewInput{
		FilesChanged: []string{"internal/domain/order.go"},
		DiffContent:  "package domain\nimport \"github.com/aws/aws-sdk-go-v2/service/dynamodb\"",
	}
	vHex := EvaluateTribunal(hexBreach)
	if vHex.GateState.Authorize() {
		t.Fatalf("expected hexagonal breach to be blocked by Go JEV specialist, got %+v", vHex)
	}

	// 2. Inter-procedural Taint caught by 2-layer GNN even on a PC without GPU and without Rust
	profNoGpuNoRust := compute.WorkstationProfile{
		HostClass:      "cpu",
		GPUVendor:      compute.VendorNoneCPU,
		HasRustSidecar: false,
	}
	nodes := []CodeGraphNode{
		{Symbol: "readHeader", Features8D: [8]float32{1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0}},
		{Symbol: "aliasPass", Features8D: [8]float32{0.4, 0.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0}},
		{Symbol: "dbConn.RunRaw", Features8D: [8]float32{0.0, 1.0, 0.0, 0.8, 0.0, 0.0, 0.0, 0.0}},
	}
	edges := [][3]float32{{0, 1, 1.0}, {1, 2, 1.0}}

	evalGo := EvaluateGraphNeuralTribunal(profNoGpuNoRust, ReviewInput{DiffContent: "clean text"}, nodes, edges)
	if !evalGo.Blocked || evalGo.ExecutionBackend != compute.BackendGoPureNative {
		t.Fatalf("expected Pure Go GNN to block 2-hop taint on GPU-less/Rust-less PC, got %+v", evalGo)
	}

	// 3. Same evaluation on AMD Radeon GPU + Rust Sidecar
	profAMD := compute.WorkstationProfile{
		HostClass:      "cpu+dgpu",
		GPUVendor:      compute.VendorAMDRadeon,
		HasDGPU:        true,
		HasAMDGPU:      true,
		HasRustSidecar: true,
	}
	evalAMD := EvaluateGraphNeuralTribunal(profAMD, ReviewInput{DiffContent: "clean text"}, nodes, edges)
	if !evalAMD.Blocked || evalAMD.ExecutionBackend != compute.BackendAmdRocmWmma {
		t.Fatalf("expected AMD ROCm/WMMA backend to block 2-hop taint, got %+v", evalAMD)
	}

	// 4. POC-007: Verify Predictive Quality Analyzer regression probability & quality score
	vClean := EvaluateTribunal(ReviewInput{
		FilesChanged: []string{"internal/service/order.go", "internal/service/order_test.go"},
		DiffContent:  "func TestOrder(t *testing.T) {}",
	})
	vHighRiskNoTest := EvaluateTribunal(ReviewInput{
		FilesChanged: []string{"internal/auth/jwt.go"},
		TouchesAuth:  true,
		DiffContent:  "if a { if b { if c { for x := range y { switch z { case 1: } } } } }" + string(make([]byte, 700)),
	})
	if vHighRiskNoTest.RegressionRiskProb <= vClean.RegressionRiskProb {
		t.Fatalf("POC-007 expected higher regression risk for untested auth diff (%.4f <= %.4f)",
			vHighRiskNoTest.RegressionRiskProb, vClean.RegressionRiskProb)
	}
}
