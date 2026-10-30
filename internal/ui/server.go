// Package ui implements the native zero-dependency Web GUI server for SquadAI Harness
// (`squad-harness ui`), using Go 1.24.3's standard library (`net/http` + `embed`).
// Every metric, count, limit, and integrity status is computed dynamically at runtime
// from the Go runtime, OS memory sensors, SEKG CSR graph, and on-disk skill catalog.
package ui

import (
	_ "embed"
	"encoding/json"
	"math"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"runtime/debug"
	"strings"

	"github.com/thiago701/squad-ai-harness/internal/catalog"
	"github.com/thiago701/squad-ai-harness/internal/cognitive/harness"
	"github.com/thiago701/squad-ai-harness/internal/installer"
	"github.com/thiago701/squad-ai-harness/internal/runtime/jobobject"
	"github.com/thiago701/squad-ai-harness/pkg/contracts"
)

//go:embed static/index.html
var indexHTML []byte

// Server serves the embedded Interactive Skills Catalog and live Resource Monitor API.
type Server struct {
	rootDir string
	engine  *harness.Engine
}

// NewServer initializes the UI Server backed by the live CognitiveHarness.
func NewServer(rootDir string) (*Server, error) {
	eng, err := harness.NewEngine(rootDir)
	if err != nil {
		return nil, err
	}
	return &Server{
		rootDir: rootDir,
		engine:  eng,
	}, nil
}

// SkillsCount returns the dynamic number of canonical skills loaded from disk.
func (s *Server) SkillsCount() int {
	return len(s.engine.Catalog().Skills)
}

// SEKGNodesCount returns the dynamic number of nodes in the SEKG CSR graph.
func (s *Server) SEKGNodesCount() int {
	return len(s.engine.Graph().Nodes)
}

// Handler returns the configured http.Handler with the UI and resource/skills routes registered.
func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/", s.handleIndex)
	mux.HandleFunc("/api/overview", s.handleOverview)
	mux.HandleFunc("/api/skills", s.handleSkills)
	mux.HandleFunc("/api/skills/detail", s.handleSkillDetail)
	mux.HandleFunc("/api/skills/open", s.handleOpenSkill)
	mux.HandleFunc("/api/skills/sync", s.handleSyncSkills)
	return mux
}

func (s *Server) handleIndex(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" && r.URL.Path != "/index.html" {
		http.NotFound(w, r)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	_, _ = w.Write(indexHTML)
}

func currentGoMemLimitMiB() float64 {
	limBytes := debug.SetMemoryLimit(-1)
	if limBytes <= 0 || limBytes == math.MaxInt64 {
		return 0
	}
	return float64(limBytes) / (1024 * 1024)
}

func (s *Server) inspectSyncStatus() installer.SyncReport {
	return installer.Verify(s.engine.Catalog(), nil)
}

func (s *Server) handleOverview(w http.ResponseWriter, _ *http.Request) {
	var ms runtime.MemStats
	runtime.ReadMemStats(&ms)
	sysMem, _ := jobobject.ProbeSystemMemory()
	cat := s.engine.Catalog()
	valRep := cat.Validate()
	g := s.engine.Graph()
	syncVal := s.inspectSyncStatus()

	writeJSON(w, map[string]any{
		"product":          contracts.ProductName,
		"technical_id":     contracts.TechnicalName,
		"version":          contracts.Version,
		"full_identity":    contracts.FullIdentity,
		"go_version":       runtime.Version(),
		"os_arch":          runtime.GOOS + "/" + runtime.GOARCH,
		"cpu_cores":        runtime.NumCPU(),
		"heap_alloc_mb":    float64(ms.Alloc) / (1024 * 1024),
		"heap_sys_mb":      float64(ms.HeapSys) / (1024 * 1024),
		"gomemlimit_mb":    currentGoMemLimitMiB(),
		"avail_ram_mb":     sysMem.AvailPhysMB,
		"total_ram_mb":     sysMem.TotalPhysMB,
		"skills_count":     valRep.CanonicalSkills,
		"defense_clean":    valRep.DefenseClean,
		"utf8_clean":       valRep.UTF8Clean,
		"agents_count":     valRep.AgentsCount,
		"commands_count":   valRep.CommandsCount,
		"sekg_nodes":       len(g.Nodes),
		"sekg_edges":       len(g.Edges),
		"sekg_communities": len(g.Communities),
		"sync_validation":  syncVal,
	})
}

type techCategoryDef struct {
	ID    string `json:"id"`
	Label string `json:"label"`
	Count int    `json:"count"`
}

var canonicalTechCategories = []struct {
	id    string
	label string
}{
	{id: "java", label: "Java / Spring / Quarkus"},
	{id: "aws", label: "AWS / Cloud / IaC"},
	{id: "go", label: "Go & Rust"},
	{id: "python", label: "Python"},
	{id: "frontend", label: "Angular / TS / Web"},
	{id: "dotnet", label: ".NET / C#"},
	{id: "db", label: "Banco / Dados"},
	{id: "ia", label: "IA & Agentes"},
	{id: "sec", label: "Segurança, QA & Obs"},
}

func (s *Server) handleSkills(w http.ResponseWriter, r *http.Request) {
	q := strings.TrimSpace(r.URL.Query().Get("q"))
	cat := s.engine.Catalog()
	totalCatalogSkills := len(cat.Skills)
	syncVal := s.inspectSyncStatus()

	type skillDTO struct {
		Name         string   `json:"name"`
		DirPath      string   `json:"dir_path"`
		Description  string   `json:"description"`
		TechLabel    string   `json:"tech_label"`
		Techs        []string `json:"techs"`
		Model        string   `json:"model"`
		Origin       string   `json:"origin"`
		HasDefense   bool     `json:"has_defense"`
		ValidUTF8    bool     `json:"valid_utf8"`
		HasCRLF      bool     `json:"has_crlf"`
		IsSynced     bool     `json:"is_synced"`
		HeadersCount int      `json:"headers_count"`
		Score        float64  `json:"score,omitempty"`
	}

	var out []skillDTO
	if q != "" {
		matches := s.engine.Router().Route(q, totalCatalogSkills)
		byName := make(map[string]catalog.SkillEntry, totalCatalogSkills)
		for _, sk := range cat.Skills {
			byName[sk.Name] = sk
		}
		out = make([]skillDTO, 0, len(matches))
		for _, m := range matches {
			sk := byName[m.SkillName]
			label, techs := classifySkillTech(sk.Name, sk.Description)
			out = append(out, skillDTO{
				Name:         m.SkillName,
				DirPath:      filepath.ToSlash(sk.DirPath),
				Description:  sk.Description,
				TechLabel:    label,
				Techs:        techs,
				Model:        sk.Model,
				Origin:       sk.Origin,
				HasDefense:   sk.HasDefense,
				ValidUTF8:    sk.ValidUTF8,
				HasCRLF:      sk.HasCRLF,
				IsSynced:     syncVal.SkillSynced[sk.Name],
				HeadersCount: len(sk.Headers),
				Score:        m.Score,
			})
		}
	} else {
		out = make([]skillDTO, 0, totalCatalogSkills)
		for _, sk := range cat.Skills {
			label, techs := classifySkillTech(sk.Name, sk.Description)
			out = append(out, skillDTO{
				Name:         sk.Name,
				DirPath:      filepath.ToSlash(sk.DirPath),
				Description:  sk.Description,
				TechLabel:    label,
				Techs:        techs,
				Model:        sk.Model,
				Origin:       sk.Origin,
				HasDefense:   sk.HasDefense,
				ValidUTF8:    sk.ValidUTF8,
				HasCRLF:      sk.HasCRLF,
				IsSynced:     syncVal.SkillSynced[sk.Name],
				HeadersCount: len(sk.Headers),
			})
		}
	}

	countsByTech := make(map[string]int, len(canonicalTechCategories))
	for _, item := range out {
		for _, t := range item.Techs {
			countsByTech[t]++
		}
	}

	categories := make([]techCategoryDef, 0, len(canonicalTechCategories)+1)
	categories = append(categories, techCategoryDef{
		ID:    "all",
		Label: "Todas",
		Count: len(out),
	})
	for _, def := range canonicalTechCategories {
		if countsByTech[def.id] > 0 {
			categories = append(categories, techCategoryDef{
				ID:    def.id,
				Label: def.label,
				Count: countsByTech[def.id],
			})
		}
	}

	writeJSON(w, map[string]any{
		"total_catalog": totalCatalogSkills,
		"matched_count": len(out),
		"categories":    categories,
		"skills":        out,
	})
}

func (s *Server) handleSkillDetail(w http.ResponseWriter, r *http.Request) {
	name := strings.TrimSpace(r.URL.Query().Get("name"))
	g := s.engine.Graph()
	syncVal := s.inspectSyncStatus()

	for _, sk := range s.engine.Catalog().Skills {
		if sk.Name == name {
			raw, _ := os.ReadFile(filepath.Clean(sk.FilePath))
			label, techs := classifySkillTech(sk.Name, sk.Description)

			var sekgDegree uint32
			var sekgCommunity uint32
			if idx, ok := g.NodeIndex["skill:"+sk.Name]; ok && int(idx) < len(g.Nodes) {
				nd := g.Nodes[idx]
				sekgDegree = nd.Degree
				sekgCommunity = nd.CommunityL0
			}

			writeJSON(w, map[string]any{
				"name":          sk.Name,
				"description":   sk.Description,
				"tech_label":    label,
				"techs":         techs,
				"model":         sk.Model,
				"origin":        sk.Origin,
				"has_defense":   sk.HasDefense,
				"valid_utf8":    sk.ValidUTF8,
				"has_crlf":      sk.HasCRLF,
				"is_synced":     syncVal.SkillSynced[sk.Name],
				"headers_count": len(sk.Headers),
				"size_bytes":    len(raw),
				"sekg_degree":   sekgDegree,
				"sekg_comm_l0":  sekgCommunity,
				"dir_path":      filepath.ToSlash(sk.DirPath),
				"file_path":     filepath.ToSlash(sk.FilePath),
				"raw_markdown":  string(raw),
			})
			return
		}
	}
	http.NotFound(w, r)
}

func (s *Server) handleOpenSkill(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		Name   string `json:"name"`
		DryRun bool   `json:"dry_run"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid JSON", http.StatusBadRequest)
		return
	}
	targetName := strings.TrimSpace(req.Name)

	for _, sk := range s.engine.Catalog().Skills {
		if sk.Name == targetName {
			absDir, err := filepath.Abs(sk.DirPath)
			if err != nil {
				absDir = filepath.Clean(sk.DirPath)
			}
			if !req.DryRun {
				var cmd *exec.Cmd
				switch runtime.GOOS {
				case "windows":
					cmd = exec.Command("explorer.exe", absDir)
				case "darwin":
					cmd = exec.Command("open", absDir)
				default:
					cmd = exec.Command("xdg-open", absDir)
				}
				_ = cmd.Start()
			}
			writeJSON(w, map[string]any{
				"opened":   true,
				"skill":    sk.Name,
				"dir_path": filepath.ToSlash(absDir),
			})
			return
		}
	}
	http.NotFound(w, r)
}

func (s *Server) handleSyncSkills(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	summary, err := installer.InstallToTargets(s.engine.Catalog(), nil)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	writeJSON(w, summary)
}

func classifySkillTech(name, desc string) (string, []string) {
	lowerName := strings.ToLower(name)
	lowerAll := strings.ToLower(name + " " + desc)

	var techs []string
	addTech := func(t string) {
		for _, existing := range techs {
			if existing == t {
				return
			}
		}
		techs = append(techs, t)
	}

	if strings.Contains(lowerName, "java") || strings.Contains(lowerName, "spring") || strings.Contains(lowerName, "quarkus") || strings.Contains(lowerName, "jskill") || strings.Contains(lowerAll, "java 25") || strings.Contains(lowerAll, "spring boot") {
		addTech("java")
	}
	if strings.Contains(lowerName, "aws") || strings.Contains(lowerName, "lambda") || strings.Contains(lowerName, "step-functions") || strings.Contains(lowerName, "api-gateway") || strings.Contains(lowerName, "localstack") || strings.Contains(lowerName, "iac") || strings.Contains(lowerAll, "terraform") || strings.Contains(lowerAll, "serverless") {
		addTech("aws")
	}
	if strings.Contains(lowerName, "go") || strings.Contains(lowerName, "rust") || strings.Contains(lowerAll, "golang") || strings.Contains(lowerAll, "cargo") {
		addTech("go")
	}
	if strings.Contains(lowerName, "python") || strings.Contains(lowerName, "langgraph") || strings.Contains(lowerName, "markitdown") || strings.Contains(lowerAll, "fastapi") || strings.Contains(lowerAll, "cpython") {
		addTech("python")
	}
	if strings.Contains(lowerName, "angular") || strings.Contains(lowerName, "typescript") || strings.Contains(lowerName, "nodejs") || strings.Contains(lowerName, "ui-ux") || strings.Contains(lowerName, "web") || strings.Contains(lowerName, "chrome") || strings.Contains(lowerName, "navegador") || strings.Contains(lowerName, "remotion") || strings.Contains(lowerName, "frontend") {
		addTech("frontend")
	}
	if strings.Contains(lowerName, "dotnet") || strings.Contains(lowerName, "csharp") || strings.Contains(lowerAll, ".net 10") {
		addTech("dotnet")
	}
	if strings.Contains(lowerName, "banco") || strings.Contains(lowerName, "dados") || strings.Contains(lowerName, "streaming") || strings.Contains(lowerAll, "dbml") || strings.Contains(lowerAll, "dynamodb") || strings.Contains(lowerAll, "postgresql") {
		addTech("db")
	}
	if strings.Contains(lowerName, "ia") || strings.Contains(lowerName, "ai") || strings.Contains(lowerName, "mcp") || strings.Contains(lowerName, "graphify") || strings.Contains(lowerName, "roteamento") || strings.Contains(lowerName, "memoria") || strings.Contains(lowerName, "compactacao") || strings.Contains(lowerName, "headroom") || strings.Contains(lowerName, "gpu") || strings.Contains(lowerName, "visao") || strings.Contains(lowerName, "chatbot") || strings.Contains(lowerName, "squad") || strings.Contains(lowerName, "sandeco") || strings.Contains(lowerName, "batman") {
		addTech("ia")
	}
	if strings.Contains(lowerName, "seguranca") || strings.Contains(lowerName, "veracode") || strings.Contains(lowerName, "auditoria") || strings.Contains(lowerName, "qualidade") || strings.Contains(lowerName, "teste") || strings.Contains(lowerName, "qa") || strings.Contains(lowerName, "sonar") || strings.Contains(lowerName, "contrato") || strings.Contains(lowerName, "error") || strings.Contains(lowerName, "logs") || strings.HasPrefix(lowerName, "dd-") || strings.Contains(lowerName, "datadog") || strings.Contains(lowerName, "ratchet") || strings.Contains(lowerName, "verificacao") || strings.Contains(lowerName, "review") {
		addTech("sec")
	}

	if len(techs) == 0 {
		addTech("ia")
	}

	labelMap := map[string]string{
		"java":     "Java / Spring",
		"aws":      "AWS / Cloud",
		"go":       "Go & Rust",
		"python":   "Python",
		"frontend": "Angular / TS",
		"dotnet":   ".NET / C#",
		"db":       "Banco / Dados",
		"ia":       "IA & Agentes",
		"sec":      "Segurança & QA",
	}

	primary := labelMap[techs[0]]
	if len(techs) >= 2 && techs[0] != techs[1] {
		shortMap := map[string]string{
			"java":     "Java",
			"aws":      "AWS",
			"go":       "Go/Rust",
			"python":   "Python",
			"frontend": "Angular/TS",
			"dotnet":   ".NET",
			"db":       "Dados",
			"ia":       "IA",
			"sec":      "Sec/QA",
		}
		primary = shortMap[techs[0]] + " · " + shortMap[techs[1]]
	}
	return primary, techs
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	enc := json.NewEncoder(w)
	enc.SetIndent("", "  ")
	_ = enc.Encode(v)
}
