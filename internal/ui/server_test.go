package ui

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func repoRoot(t *testing.T) string {
	t.Helper()
	_, file, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("cannot resolve caller")
	}
	return filepath.Clean(filepath.Join(filepath.Dir(file), "..", ".."))
}

func TestUIServerCatalogAndMonitorDynamicConsistency(t *testing.T) {
	root := repoRoot(t)
	srv, err := NewServer(root)
	if err != nil {
		t.Fatalf("NewServer error: %v", err)
	}
	h := srv.Handler()

	// 1. GET / (Embedded HTML UI must have zero hardcoded fallback numbers)
	{
		req := httptest.NewRequest(http.MethodGet, "/", nil)
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		if rec.Code != http.StatusOK {
			t.Fatalf("GET / status = %d", rec.Code)
		}
		body := rec.Body.String()
		if !strings.Contains(body, "Catálogo Interativo de Skills") || !strings.Contains(body, "Monitor de recursos:") {
			t.Fatalf("GET / missing expected catalog or resource monitor markers")
		}
		if !strings.Contains(body, "Abrir skill") || !strings.Contains(body, "sync-validator-banner") {
			t.Fatalf("GET / missing expected 'Abrir skill' button or sync validator banner")
		}
		// Ensure no hardcoded dummy telemetry strings exist in the static HTML template
		for _, forbidden := range []string{"3.43 MiB", "1131 MB", "154 Nós"} {
			if strings.Contains(body, forbidden) {
				t.Fatalf("GET / contains hardcoded dummy number %q in HTML template", forbidden)
			}
		}
	}

	// 2. GET /api/overview (Monitor de Recursos 100% dinâmico + Sync Validation)
	var overviewSkillsCount int
	var overviewSEKGNodes int
	{
		req := httptest.NewRequest(http.MethodGet, "/api/overview", nil)
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		if rec.Code != http.StatusOK {
			t.Fatalf("GET /api/overview status = %d", rec.Code)
		}
		var out map[string]any
		if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
			t.Fatalf("overview JSON error: %v", err)
		}
		overviewSkillsCount = int(out["skills_count"].(float64))
		overviewSEKGNodes = int(out["sekg_nodes"].(float64))
		if overviewSkillsCount != srv.SkillsCount() {
			t.Fatalf("overview skills_count (%d) != srv.SkillsCount() (%d)", overviewSkillsCount, srv.SkillsCount())
		}
		if overviewSEKGNodes != srv.SEKGNodesCount() {
			t.Fatalf("overview sekg_nodes (%d) != srv.SEKGNodesCount() (%d)", overviewSEKGNodes, srv.SEKGNodesCount())
		}
		if float64(out["heap_alloc_mb"].(float64)) <= 0 {
			t.Fatalf("expected positive live heap_alloc_mb, got %v", out["heap_alloc_mb"])
		}
		if float64(out["avail_ram_mb"].(float64)) <= 0 {
			t.Fatalf("expected positive live avail_ram_mb from OS sensor, got %v", out["avail_ram_mb"])
		}
		syncVal, ok := out["sync_validation"].(map[string]any)
		if !ok || syncVal["targets"] == nil {
			t.Fatalf("expected sync_validation object in /api/overview, got %v", out["sync_validation"])
		}
	}

	// 3. GET /api/skills (Full catalog consistency & dynamic categories)
	{
		req := httptest.NewRequest(http.MethodGet, "/api/skills", nil)
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		if rec.Code != http.StatusOK {
			t.Fatalf("GET /api/skills status = %d", rec.Code)
		}
		var out struct {
			TotalCatalog int `json:"total_catalog"`
			MatchedCount int `json:"matched_count"`
			Categories   []struct {
				ID    string `json:"id"`
				Label string `json:"label"`
				Count int    `json:"count"`
			} `json:"categories"`
			Skills []struct {
				Name      string   `json:"name"`
				DirPath   string   `json:"dir_path"`
				TechLabel string   `json:"tech_label"`
				Techs     []string `json:"techs"`
				IsSynced  bool     `json:"is_synced"`
			} `json:"skills"`
		}
		if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
			t.Fatalf("skills JSON error: %v", err)
		}
		if out.TotalCatalog != overviewSkillsCount || len(out.Skills) != overviewSkillsCount {
			t.Fatalf("skills count mismatch: overview=%d total_catalog=%d len(skills)=%d",
				overviewSkillsCount, out.TotalCatalog, len(out.Skills))
		}
		if len(out.Categories) < 5 || out.Categories[0].ID != "all" || out.Categories[0].Count != overviewSkillsCount {
			t.Fatalf("unexpected dynamic categories: %+v", out.Categories)
		}
		if out.Skills[0].DirPath == "" {
			t.Fatalf("expected non-empty dir_path for skill %s", out.Skills[0].Name)
		}
	}

	// 4. GET /api/skills/detail (Dynamic disk & SEKG inspection)
	{
		reqDet := httptest.NewRequest(http.MethodGet, "/api/skills/detail?name=engenheiro-seguranca", nil)
		recDet := httptest.NewRecorder()
		h.ServeHTTP(recDet, reqDet)
		if recDet.Code != http.StatusOK {
			t.Fatalf("GET /api/skills/detail status = %d", recDet.Code)
		}
		var det map[string]any
		if err := json.Unmarshal(recDet.Body.Bytes(), &det); err != nil {
			t.Fatalf("detail JSON error: %v", err)
		}
		if int(det["size_bytes"].(float64)) <= 100 {
			t.Fatalf("expected real size_bytes > 100, got %v", det["size_bytes"])
		}
		if det["valid_utf8"] != true {
			t.Fatalf("expected valid_utf8 = true")
		}
		if det["dir_path"] == nil || det["dir_path"].(string) == "" {
			t.Fatalf("expected non-empty dir_path in skill detail")
		}
	}

	// 5. POST /api/skills/open (Open skill folder in Explorer — dry_run for test safety)
	{
		body := strings.NewReader(`{"name":"engenheiro-seguranca","dry_run":true}`)
		reqOpen := httptest.NewRequest(http.MethodPost, "/api/skills/open", body)
		recOpen := httptest.NewRecorder()
		h.ServeHTTP(recOpen, reqOpen)
		if recOpen.Code != http.StatusOK {
			t.Fatalf("POST /api/skills/open status = %d: %s", recOpen.Code, recOpen.Body.String())
		}
		var openRes map[string]any
		if err := json.Unmarshal(recOpen.Body.Bytes(), &openRes); err != nil {
			t.Fatalf("open JSON error: %v", err)
		}
		if openRes["opened"] != true || !strings.Contains(openRes["dir_path"].(string), "engenheiro-seguranca") {
			t.Fatalf("unexpected open response: %+v", openRes)
		}
	}
}
