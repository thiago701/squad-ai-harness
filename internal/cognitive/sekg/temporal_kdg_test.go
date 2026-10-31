package sekg

import (
	"fmt"
	"testing"

	"github.com/thiago701/squad-ai-harness/pkg/contracts"
)

func TestTemporalKDGZeroLeakageAndBinaryParity(t *testing.T) {
	g := NewGraphCSR()
	baseTs := int64(1_759_276_800)

	for i := 0; i < 64; i++ {
		g.UpsertNode(NodeRecord{
			ID:     fmt.Sprintf("mod:%d", i),
			Kind:   KindModule,
			Title:  fmt.Sprintf("Módulo %d", i),
			Degree: uint32(i % 8),
			Trust:  contracts.TrustVerified,
		})
	}
	// Add 32 past edges and 32 future edges
	for i := 1; i <= 32; i++ {
		g.AddTemporalEdge("mod:0", fmt.Sprintf("mod:%d", i), EdgeDependsOn, 1.0, contracts.TrustVerified, "past", baseTs+int64(i)*3600)
	}
	for i := 33; i < 64; i++ {
		g.AddTemporalEdge("mod:0", fmt.Sprintf("mod:%d", i), EdgeDependsOn, 1.0, contracts.TrustVerified, "future", baseTs+int64(i)*86400)
	}
	g.BuildCSR()

	kdgBytes := g.MarshalKDGBytes()
	n, m, _, err := VerifyKDGBytes(kdgBytes)
	if err != nil {
		t.Fatalf("expected valid KDG1 binary snapshot, got err: %v", err)
	}
	if n != 64 || m != 63 {
		t.Fatalf("unexpected node/edge count in KDG header: n=%d m=%d", n, m)
	}

	anchor := baseTs + 48*3600
	sample := g.SampleTemporalSubgraph5D("mod:0", anchor, 32)
	if sample.LeakedFutureEdges != 0 {
		t.Fatalf("expected 0 leaked future edges, got %d", sample.LeakedFutureEdges)
	}
	if sample.FutureEdgesFiltered == 0 {
		t.Fatalf("expected future edges to be filtered out strictly")
	}
	if len(sample.Tokens5D) < 2 {
		t.Fatalf("expected sampled 5D tokens, got %d", len(sample.Tokens5D))
	}

	// POC-002: Verify 4-hop edge-type-weighted temporal impact propagation and .kdg binary size in AnalyzeImpact
	g.UpsertNode(NodeRecord{ID: "mod:100", Kind: KindModule, Title: "Hop2 Node", Trust: contracts.TrustVerified})
	g.UpsertNode(NodeRecord{ID: "mod:101", Kind: KindModule, Title: "Hop3 Node", Trust: contracts.TrustVerified})
	g.AddEdge("mod:1", "mod:100", EdgeOrchestratedIn, 1.0, contracts.TrustVerified, "chain-hop2")
	g.AddEdge("mod:100", "mod:101", EdgeVerifiedBy, 1.0, contracts.TrustVerified, "chain-hop3")
	g.BuildCSR()
	imp := g.AnalyzeImpact([]string{"mod:0"})
	if imp.KDGBinaryBytes <= 64 || len(imp.TemporalImpactScores) == 0 {
		t.Fatalf("POC-002 expected KDG binary bytes > 64 and temporal impact scores, got %+v", imp)
	}
	if len(imp.AffectedNodes3Hop) == 0 {
		t.Fatalf("POC-002 expected 3-hop affected nodes (mod:101) to be captured, got %+v", imp)
	}
}
