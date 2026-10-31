package router

import (
	"path/filepath"
	"runtime"
	"testing"

	"github.com/thiago701/squad-ai-harness/internal/catalog"
	"github.com/thiago701/squad-ai-harness/internal/compute"
)

func repoRoot(t *testing.T) string {
	t.Helper()
	_, file, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("cannot resolve caller")
	}
	return filepath.Clean(filepath.Join(filepath.Dir(file), "..", "..", ".."))
}

func TestHybridRouterUsabilityErgonomicsFrontend(t *testing.T) {
	root := repoRoot(t)
	cat, err := catalog.Load(root)
	if err != nil {
		t.Fatalf("catalog.Load failed: %v", err)
	}
	r := NewHybridRouter(cat)

	queries := []struct {
		query        string
		expectedTop1 string
	}{
		{
			query:        "usabilidade ergonomia cognitiva heuristica nielsen frontend angular",
			expectedTop1: "especialista-frontend",
		},
		{
			query:        "ISO 9241 Bastien Scapin KLM-GOMS Steering Law Safe Triangle APCA",
			expectedTop1: "especialista-frontend",
		},
		{
			query:        "roving tabindex URL as state spring physics microinteracoes",
			expectedTop1: "especialista-frontend",
		},
	}

	for _, tc := range queries {
		matches := r.Route(tc.query, 5)
		if len(matches) == 0 {
			t.Fatalf("Route(%q) returned 0 matches", tc.query)
		}
		if matches[0].SkillName != tc.expectedTop1 {
			t.Fatalf("Route(%q) top-1 = %q (score=%.2f), want %q",
				tc.query, matches[0].SkillName, matches[0].Score, tc.expectedTop1)
		}
	}
}

func TestCrossEncoderRerankerVocabularyMismatchAndNoRustFallback(t *testing.T) {
	root := repoRoot(t)
	cat, err := catalog.Load(root)
	if err != nil {
		t.Fatalf("catalog.Load failed: %v", err)
	}
	r := NewHybridRouter(cat)

	// Workstation without GPU and without Rust installed
	profGoOnly := compute.WorkstationProfile{
		HostClass:      "cpu",
		GPUVendor:      compute.VendorNoneCPU,
		HasRustSidecar: false,
	}

	cases := []struct {
		query    string
		expected string
	}{
		{
			query:    "desfazer cobranca distribuida quando o terceiro microservico cai no meio da transacao",
			expected: "orquestracao-step-functions",
		},
		{
			query:    "cliente consegue ler pedidos de outro inquilino trocando o identificador na requisicao",
			expected: "engenheiro-seguranca",
		},
		{
			query:    "processo do container morre subitamente ao materializar lista gigante do cursor",
			expected: "python-memoria",
		},
		{
			query:    "garantir que mudanca no payload do backend nao quebre o aplicativo movel em producao",
			expected: "contrato-reverso",
		},
	}

	for _, tc := range cases {
		ranked, rep := r.RerankWithCrossEncoder(profGoOnly, tc.query, nil, 3)
		if rep.PromotedHitPolicy != compute.HitPolicyVerified || rep.Int8StaticCosineParity < 0.999 {
			t.Fatalf("expected HitPolicyVerified and INT8 parity >= 0.999, got %+v", rep)
		}
		if len(ranked) == 0 || ranked[0].SkillName != tc.expected {
			t.Fatalf("RerankWithCrossEncoder(%q) top-1 = %v, want %q", tc.query, ranked, tc.expected)
		}
	}

	// POC-006: Verify 128D dense semantic retrieval across non-canonical skills in the 106-skill catalog
	nonCanon, _ := r.RerankWithCrossEncoder(profGoOnly, "usabilidade ergonomia cognitiva heuristica nielsen frontend angular", nil, 3)
	if len(nonCanon) == 0 || nonCanon[0].SkillName != "especialista-frontend" {
		t.Fatalf("POC-006 full-catalog rerank top-1 = %v, want especialista-frontend", nonCanon)
	}
}
