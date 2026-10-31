package gomcpclient

import (
	"testing"
	"time"
)

func TestGoBaselinesAndKdgHeader(t *testing.T) {
	hdr := EncodeKdgBinaryHeader(1024, 16384, 1730000000)
	if len(hdr) != 64 || string(hdr[0:4]) != KdgHeaderMagic {
		t.Fatalf("cabeçalho .kdg inválido: len=%d magic=%q", len(hdr), string(hdr[0:4]))
	}

	n := 1024
	d := 128
	docs := make([]float32, n*d)
	query := make([]float32, d)
	for i := range docs {
		docs[i] = 0.15
	}
	for j := range query {
		query[j] = 0.25
	}

	t0 := time.Now()
	outA := GoBaselineBatchDot(docs, query, n, d)
	durA := time.Since(t0)

	t1 := time.Now()
	outB := GoOptimizedBatchDotUnrolled(docs, query, n, d)
	durB := time.Since(t1)

	sim, err := ComputeCosineSimilarity(outA, outB)
	if err != nil || sim < 0.99999 {
		t.Fatalf("paridade cosseno falhou: sim=%f err=%v", sim, err)
	}
	t.Logf("Go BatchDot 1024x128: GroupA=%v GroupB=%v Cosine=%f", durA, durB, sim)
}

func TestGoCSRPageRankBaseline(t *testing.T) {
	nodes := 2048
	deg := 16
	rowPtr := make([]uint32, nodes+1)
	colIdx := make([]uint32, 0, nodes*deg)
	weights := make([]float32, 0, nodes*deg)
	invDeg := float32(1.0) / float32(deg)

	for u := 0; u < nodes; u++ {
		for k := 0; k < deg; k++ {
			colIdx = append(colIdx, uint32((u+k*7+1)%nodes))
			weights = append(weights, invDeg)
		}
		rowPtr[u+1] = uint32(len(colIdx))
	}

	t0 := time.Now()
	ranks := GoBaselineCSRPageRank(rowPtr, colIdx, weights, nodes, 0.85, 20)
	dur := time.Since(t0)
	if len(ranks) != nodes {
		t.Fatalf("tamanho inesperado: %d", len(ranks))
	}
	t.Logf("Go CSR PageRank 2048 nodes (20 iters): %v", dur)

	for _, n := range []int{106, 1024, 8192, 32768} {
		docs := make([]float32, n*128)
		q := make([]float32, 128)
		tA := time.Now()
		for r := 0; r < 10; r++ {
			_ = GoBaselineBatchDot(docs, q, n, 128)
		}
		usA := float64(time.Since(tA).Nanoseconds()) / 10000.0
		tB := time.Now()
		for r := 0; r < 10; r++ {
			_ = GoOptimizedBatchDotUnrolled(docs, q, n, 128)
		}
		usB := float64(time.Since(tB).Nanoseconds()) / 10000.0
		t.Logf("Go BatchDot N=%d: GroupA=%.2fus GroupB=%.2fus", n, usA, usB)
	}

	for _, dim := range []int{64, 128, 256} {
		a := make([]float32, dim*dim)
		b := make([]float32, dim*dim)
		tA := time.Now()
		_ = GoBaselineGEMM(a, b, dim)
		usA := float64(time.Since(tA).Nanoseconds()) / 1000.0
		tB := time.Now()
		_ = GoOptimizedGEMM(a, b, dim)
		usB := float64(time.Since(tB).Nanoseconds()) / 1000.0
		t.Logf("Go GEMM %dx%d: GroupA_ijk=%.2fus GroupB_ikj=%.2fus", dim, dim, usA, usB)
	}
}
