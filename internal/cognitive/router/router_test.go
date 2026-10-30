package router

import (
	"path/filepath"
	"runtime"
	"testing"

	"github.com/thiago701/squad-ai-harness/internal/catalog"
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
