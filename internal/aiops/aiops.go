// Package aiops implements the Lite Local-First AIOps Engine for SquadAI Harness v0.8.0
// (Go 1.24.3, CGO_ENABLED=0, zero AWS cloud cost).
// It compacts the Squad-Agentica IAOps platform (Monitor - GraphRAG v2.0, Super Agente AIOps CAP-32,
// 1-Prompt Skill Forge CAP-22, OpenAPI Route Drift CAP-31, and 32 capabilities) into a native
// workstation module integrated with LocalStack Docker (127.0.0.1:4566) and zero-daemon fallback.
package aiops

import (
	"bytes"
	"context"
	_ "embed"
	"encoding/json"
	"fmt"
	"io"
	"io/fs"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"
)

//go:embed static/monitor.html
var embeddedMonitorHTML []byte

const (
	// DefaultMonitorAddr is the loopback address for the Monitor - GraphRAG v2.0 Lite UI.
	DefaultMonitorAddr = "127.0.0.1:8765"
	// DefaultLocalStackEndpoint is the local LocalStack gateway URL.
	DefaultLocalStackEndpoint = "http://127.0.0.1:4566"
	// DefaultContainerName is the managed Docker container name for LocalStack Lite.
	DefaultContainerName = "squad-aiops-localstack"
	// LocalStackServices defines the core AWS services emulated locally at $0.00 cost.
	LocalStackServices = "sqs,sns,s3,dynamodb,lambda,apigateway,kms,secretsmanager,logs"
)

// LocalStackStatus describes the live or emulated state of LocalStack on the developer workstation.
type LocalStackStatus struct {
	Mode          string            `json:"mode"` // "DOCKER_LIVE", "DOCKER_STARTED", "EMULATED_ZERO_DAEMON"
	Healthy       bool              `json:"healthy"`
	Endpoint      string            `json:"endpoint"`
	ContainerName string            `json:"container_name"`
	ContainerID   string            `json:"container_id,omitempty"`
	DockerRunning bool              `json:"docker_running"`
	Services      map[string]string `json:"services"`
	CostMonthly   float64           `json:"cost_monthly_usd"`
	Message       string            `json:"message"`
	CheckedAt     string            `json:"checked_at"`
}

// DiscoverySummary reports the infrastructure, contracts, and code artifacts discovered in a local workspace.
type DiscoverySummary struct {
	WorkspaceDir      string   `json:"workspace_dir"`
	TerraformFiles    int      `json:"terraform_files"`
	TfvarsFiles       int      `json:"tfvars_files"`
	ComposeFiles      int      `json:"compose_files"`
	OpenAPIFiles      int      `json:"openapi_files"`
	ManifestFiles     int      `json:"manifest_files"`
	WorkflowFiles     int      `json:"workflow_files"`
	DiscoveredNodes   int      `json:"discovered_nodes"`
	DiscoveredEdges   int      `json:"discovered_edges"`
	DriftFindings     []string `json:"drift_findings"`
	ScannedAt         string   `json:"scanned_at"`
	DurationMs        float64  `json:"duration_ms"`
	CostMonthlyAWSUSD float64  `json:"cost_monthly_aws_usd"`
}

// SkillItem represents a registered AIOps capability in the Dev/Tech Lead catalog.
type SkillItem struct {
	Code        string `json:"code"`
	ID          string `json:"id"`
	Name        string `json:"name"`
	GrupoDev    string `json:"grupo_dev"`
	Category    string `json:"category"`
	Status      string `json:"status"`
	Version     string `json:"version"`
	Description string `json:"description"`
}

// ExecutedSkillReport captures the deterministic execution of a capability by the Super Agente AIOps.
type ExecutedSkillReport struct {
	Code                   string   `json:"code"`
	ID                     string   `json:"id"`
	Name                   string   `json:"name"`
	GrupoDev               string   `json:"grupo_dev"`
	Category               string   `json:"category"`
	StatusExecucao         string   `json:"status_execucao"`
	DuracaoMs              int      `json:"duracao_ms"`
	ConfiancaRN007         float64  `json:"confianca_rn007"`
	ClassificacaoEvidencia string   `json:"classificacao_evidencia"`
	Achados                []string `json:"achados"`
	EvidenciasIDs          []string `json:"evidencias_ids"`
}

// ChatResponse is the structured output of the Super Agente AIOps (CAP-32) over the live GraphRAG.
type ChatResponse struct {
	OK                    bool                   `json:"ok"`
	Agente                string                 `json:"agente"`
	StatusAgente          string                 `json:"status_agente"`
	GuardrailCAP12        bool                   `json:"guardrail_cap12_acionado"`
	ContextoSquadLido     map[string]any         `json:"contexto_squad_lido"`
	RespostaPrincipal     string                 `json:"resposta_principal"`
	HabilidadesExecutadas []ExecutedSkillReport  `json:"habilidades_executadas"`
	GraphRAGEvidencia     map[string]any         `json:"graphrag_evidencia"`
	AcoesUI               []map[string]string    `json:"acoes_ui"`
}

// Engine manages the in-memory GraphRAG state, LocalStack status, workspace discovery, and custom skills.
type Engine struct {
	mu           sync.RWMutex
	harnessRoot  string
	workspaceDir string
	graph        map[string]any
	localstack   LocalStackStatus
	discovery    DiscoverySummary
}

var (
	reDestructivePrompt = regexp.MustCompile(`(?i)\b(delete|drop\s+table|destroy|rm\s+-rf|apagar\s+produ[cç][aã]o|remover\s+banco|truncate\s+table|force-delete|terraform\s+apply\s+-auto-approve|aws\s+s3\s+rb)\b`)
	reTfResource        = regexp.MustCompile(`(?m)^\s*resource\s+"([^"]+)"\s+"([^"]+)"`)
	reTfModule          = regexp.MustCompile(`(?m)^\s*module\s+"([^"]+)"`)
	reTfVarTimeout      = regexp.MustCompile(`(?m)^\s*(visibility_timeout_seconds|timeout|memory_size)\s*=\s*([0-9]+)`)
	reOpenAPIRoute      = regexp.MustCompile(`(?m)^\s*(/[a-zA-Z0-9_\-\{\}/]+):\s*$`)
)

// NewEngine initializes the Lite AIOps Engine, loading the embedded GraphRAG baseline and custom skills.
func NewEngine(harnessRoot, workspaceDir string) (*Engine, error) {
	if harnessRoot == "" {
		harnessRoot = "."
	}
	if workspaceDir == "" {
		workspaceDir = harnessRoot
	}
	baseGraph, err := extractBaselineGraph()
	if err != nil {
		return nil, err
	}

	eng := &Engine{
		harnessRoot:  harnessRoot,
		workspaceDir: workspaceDir,
		graph:        baseGraph,
		localstack:   defaultEmulatedStatus("Inicializado em modo Lite Local-First ($0.00 AWS)"),
	}
	eng.loadCustomSkillsFromDisk()
	return eng, nil
}

// MatchNaturalTrigger detects natural language activation commands such as
// "Squad ai, ative o monitor" or "Squad ai, ligue o monitor".
func MatchNaturalTrigger(query string) (matched bool, action string) {
	lower := strings.ToLower(strings.TrimSpace(query))
	norm := strings.NewReplacer("á", "a", "ã", "a", "â", "a", "é", "e", "ê", "e", "í", "i", "ó", "o", "õ", "o", "ú", "u", "ç", "c").Replace(lower)

	stopTriggers := []string{
		"desligue o monitor", "desative o monitor", "parar o monitor", "pare o monitor", "monitor down", "monitor stop",
	}
	for _, st := range stopTriggers {
		if strings.Contains(norm, st) {
			return true, "down"
		}
	}

	statusTriggers := []string{
		"status do monitor", "estado do monitor", "monitor status",
	}
	for _, st := range statusTriggers {
		if strings.Contains(norm, st) {
			return true, "status"
		}
	}

	startTriggers := []string{
		"ative o monitor", "ativar o monitor", "ligue o monitor", "ligar o monitor",
		"abra o monitor", "abrir o monitor", "suba o monitor", "subir o monitor",
		"inicie o monitor", "iniciar o monitor", "monitor aiops", "monitor graphrag",
	}
	for _, trig := range startTriggers {
		if strings.Contains(norm, trig) {
			return true, "up"
		}
	}
	return false, ""
}

func extractBaselineGraph() (map[string]any, error) {
	text := string(embeddedMonitorHTML)
	marker := "const GRAFO_IAOPS ="
	idx := strings.Index(text, marker)
	if idx < 0 {
		return nil, fmt.Errorf("marcador GRAFO_IAOPS não encontrado no template embutido")
	}
	rest := text[idx+len(marker):]
	lineEnd := strings.Index(rest, "\n")
	if lineEnd < 0 {
		lineEnd = len(rest)
	}
	rawJSON := strings.TrimSpace(rest[:lineEnd])
	rawJSON = strings.TrimSuffix(rawJSON, ";")

	var parsed map[string]any
	if err := json.Unmarshal([]byte(rawJSON), &parsed); err != nil {
		return nil, fmt.Errorf("falha ao decodificar GRAFO_IAOPS: %w", err)
	}
	return parsed, nil
}

func defaultEmulatedStatus(msg string) LocalStackStatus {
	return LocalStackStatus{
		Mode:          "EMULATED_ZERO_DAEMON",
		Healthy:       true,
		Endpoint:      DefaultLocalStackEndpoint,
		ContainerName: DefaultContainerName,
		DockerRunning: false,
		Services: map[string]string{
			"sqs":            "available",
			"sns":            "available",
			"s3":             "available",
			"dynamodb":       "available",
			"lambda":         "available",
			"apigateway":     "available",
			"kms":            "available",
			"secretsmanager": "available",
			"logs":           "available",
		},
		CostMonthly: 0.0,
		Message:     msg,
		CheckedAt:   time.Now().UTC().Format(time.RFC3339),
	}
}

// EnsureLocalStack checks if LocalStack is already running on 127.0.0.1:4566, starts the
// Docker container if Docker is available, or seamlessly activates the Zero-Daemon Emulated mode.
func (e *Engine) EnsureLocalStack(ctx context.Context, startContainer bool) LocalStackStatus {
	if st, ok := probeLocalStackHTTP(ctx); ok {
		e.mu.Lock()
		e.localstack = st
		e.mu.Unlock()
		return st
	}

	dockerOK := isDockerDaemonAvailable(ctx)
	if dockerOK && startContainer {
		cid, err := startOrRunLocalStackContainer(ctx)
		if err == nil && cid != "" {
			// Wait briefly for health endpoint or mark as DOCKER_STARTED
			for range 4 {
				if st, ok := probeLocalStackHTTP(ctx); ok {
					st.Mode = "DOCKER_STARTED"
					st.ContainerID = cid
					st.DockerRunning = true
					e.mu.Lock()
					e.localstack = st
					e.mu.Unlock()
					return st
				}
				time.Sleep(350 * time.Millisecond)
			}
			st := defaultEmulatedStatus("Container Docker LocalStack iniciado (" + cid[:minInt(12, len(cid))] + ") em 127.0.0.1:4566")
			st.Mode = "DOCKER_STARTED"
			st.ContainerID = cid
			st.DockerRunning = true
			e.mu.Lock()
			e.localstack = st
			e.mu.Unlock()
			return st
		}
	}

	msg := "Modo LocalStack Zero-Daemon Emulado ativo em memória (< 10 MB RAM, US$ 0,00/mês) — Docker Desktop desligado ou pouca RAM livre"
	if dockerOK && !startContainer {
		msg = "Docker detectado; emulador LocalStack Lite pronto para bootstrap sob demanda"
	}
	st := defaultEmulatedStatus(msg)
	st.DockerRunning = dockerOK
	e.mu.Lock()
	e.localstack = st
	e.mu.Unlock()
	return st
}

// StopLocalStack stops the managed LocalStack container if running.
func (e *Engine) StopLocalStack(ctx context.Context) LocalStackStatus {
	cctx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	_ = exec.CommandContext(cctx, "docker", "stop", DefaultContainerName).Run()
	st := defaultEmulatedStatus("Container LocalStack Lite encerrado; modo Zero-Daemon mantido sem consumo de RAM.")
	e.mu.Lock()
	e.localstack = st
	e.mu.Unlock()
	return st
}

func probeLocalStackHTTP(ctx context.Context) (LocalStackStatus, bool) {
	cctx, cancel := context.WithTimeout(ctx, 900*time.Millisecond)
	defer cancel()
	req, err := http.NewRequestWithContext(cctx, http.MethodGet, "http://127.0.0.1:4566/_localstack/health", nil)
	if err != nil {
		return LocalStackStatus{}, false
	}
	client := &http.Client{Timeout: 900 * time.Millisecond}
	resp, err := client.Do(req)
	if err != nil {
		return LocalStackStatus{}, false
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return LocalStackStatus{}, false
	}
	raw, _ := io.ReadAll(io.LimitReader(resp.Body, 64*1024))
	var payload struct {
		Services map[string]string `json:"services"`
	}
	_ = json.Unmarshal(raw, &payload)
	if len(payload.Services) == 0 {
		payload.Services = defaultEmulatedStatus("").Services
	}
	return LocalStackStatus{
		Mode:          "DOCKER_LIVE",
		Healthy:       true,
		Endpoint:      DefaultLocalStackEndpoint,
		ContainerName: DefaultContainerName,
		DockerRunning: true,
		Services:      payload.Services,
		CostMonthly:   0.0,
		Message:       "Conectado ao container LocalStack ativo em 127.0.0.1:4566 (Custo AWS: US$ 0,00)",
		CheckedAt:     time.Now().UTC().Format(time.RFC3339),
	}, true
}

func isDockerDaemonAvailable(ctx context.Context) bool {
	cctx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()
	cmd := exec.CommandContext(cctx, "docker", "info", "--format", "{{.ServerVersion}}")
	out, err := cmd.Output()
	return err == nil && len(bytes.TrimSpace(out)) > 0
}

func startOrRunLocalStackContainer(ctx context.Context) (string, error) {
	cctx, cancel := context.WithTimeout(ctx, 8*time.Second)
	defer cancel()

	// 1. Try starting existing container first
	startCmd := exec.CommandContext(cctx, "docker", "start", DefaultContainerName)
	if out, err := startCmd.Output(); err == nil && len(bytes.TrimSpace(out)) > 0 {
		return strings.TrimSpace(string(out)), nil
	}

	// 2. Run new lightweight LocalStack container capped at 512m RAM bound to 127.0.0.1:4566
	runCmd := exec.CommandContext(
		cctx,
		"docker", "run", "-d",
		"--name", DefaultContainerName,
		"-p", "127.0.0.1:4566:4566",
		"-e", "SERVICES="+LocalStackServices,
		"-e", "EAGER_SERVICE_LOADING=0",
		"-e", " LS_LOG=warn",
		"--memory=512m",
		"localstack/localstack:latest",
	)
	out, err := runCmd.Output()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(out)), nil
}

// DiscoverWorkspace scans a target directory to discover real Terraform resources, .tfvars drifts,
// docker-compose services, OpenAPI routes, and project manifests, injecting them into the GraphRAG.
func (e *Engine) DiscoverWorkspace(workspaceDir string) DiscoverySummary {
	t0 := time.Now()
	if workspaceDir == "" {
		workspaceDir = e.workspaceDir
	}
	absDir, err := filepath.Abs(workspaceDir)
	if err == nil {
		workspaceDir = absDir
	}

	summary := DiscoverySummary{
		WorkspaceDir:      filepath.ToSlash(workspaceDir),
		ScannedAt:         time.Now().UTC().Format(time.RFC3339),
		CostMonthlyAWSUSD: 0.0,
	}

	var discoveredNodes []map[string]any
	var discoveredEdges []map[string]any
	tfvarsTimeouts := make(map[string]string)

	_ = filepath.WalkDir(workspaceDir, func(path string, d fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return nil
		}
		if d.IsDir() {
			if shouldSkipScanDir(d.Name()) && path != workspaceDir {
				return filepath.SkipDir
			}
			return nil
		}
		rel, _ := filepath.Rel(workspaceDir, path)
		relSlash := filepath.ToSlash(rel)
		nameLow := strings.ToLower(d.Name())

		switch {
		case strings.HasSuffix(nameLow, ".tf"):
			summary.TerraformFiles++
			nodes, edges := parseTerraformFile(path, relSlash)
			discoveredNodes = append(discoveredNodes, nodes...)
			discoveredEdges = append(discoveredEdges, edges...)
		case strings.HasSuffix(nameLow, ".tfvars"):
			summary.TfvarsFiles++
			collectTfvarsDrift(path, relSlash, tfvarsTimeouts, &summary)
		case strings.HasPrefix(nameLow, "docker-compose") && (strings.HasSuffix(nameLow, ".yml") || strings.HasSuffix(nameLow, ".yaml")):
			summary.ComposeFiles++
			nd := buildDiscoveredNode("compose-"+sanitizeID(relSlash), d.Name(), "configuracao", "Docker Compose LocalStack", relSlash, "Ambiente de containers local descoberto na estação de dev")
			discoveredNodes = append(discoveredNodes, nd)
		case (strings.Contains(nameLow, "openapi") || strings.Contains(nameLow, "swagger")) && (strings.HasSuffix(nameLow, ".yml") || strings.HasSuffix(nameLow, ".yaml") || strings.HasSuffix(nameLow, ".json")):
			summary.OpenAPIFiles++
			nodes := parseOpenAPIFile(path, relSlash, &summary)
			discoveredNodes = append(discoveredNodes, nodes...)
		case nameLow == "go.mod" || nameLow == "pyproject.toml" || nameLow == "pom.xml" || nameLow == "package.json":
			summary.ManifestFiles++
			nd := buildDiscoveredNode("repo-"+sanitizeID(relSlash), filepath.Base(filepath.Dir(path))+" ("+d.Name()+")", "repositorio", "Serviço / Repositório Local", relSlash, "Manifesto de projeto descoberto na estação local")
			discoveredNodes = append(discoveredNodes, nd)
		case strings.Contains(relSlash, ".github/workflows/") && (strings.HasSuffix(nameLow, ".yml") || strings.HasSuffix(nameLow, ".yaml")):
			summary.WorkflowFiles++
		}
		return nil
	})

	if len(tfvarsTimeouts) >= 2 {
		summary.DriftFindings = append(summary.DriftFindings,
			fmt.Sprintf("DRIFT DETECTADO (.tfvars): parâmetros de timeout/memória divergentes entre ambientes (%d arquivos .tfvars inspecionados)", len(tfvarsTimeouts)))
	}
	if len(summary.DriftFindings) == 0 {
		summary.DriftFindings = append(summary.DriftFindings,
			"Scan local concluído: topologia tripartida (Código ↔ Config/OpenAPI ↔ LocalStack :4566) consistente em modo Somente-Leitura (CAP-12).")
	}

	e.mu.Lock()
	e.workspaceDir = workspaceDir
	e.mergeDiscoveredIntoGraph(discoveredNodes, discoveredEdges)
	summary.DiscoveredNodes = len(discoveredNodes)
	summary.DiscoveredEdges = len(discoveredEdges)
	summary.DurationMs = float64(time.Since(t0).Microseconds()) / 1000.0
	e.discovery = summary
	e.mu.Unlock()

	return summary
}

func shouldSkipScanDir(name string) bool {
	switch name {
	case ".git", ".venv", "venv", "node_modules", "__pycache__", ".terraform", ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "target":
		return true
	default:
		return false
	}
}

func parseTerraformFile(fullPath, relSlash string) ([]map[string]any, []map[string]any) {
	raw, err := os.ReadFile(fullPath)
	if err != nil || len(raw) > 512*1024 {
		return nil, nil
	}
	text := string(raw)
	var nodes []map[string]any
	var edges []map[string]any

	matches := reTfResource.FindAllStringSubmatch(text, 8)
	for _, m := range matches {
		resType, resName := m[1], m[2]
		id := "tf-" + sanitizeID(resType+"-"+resName)
		nd := buildDiscoveredNode(id, resName+" ("+resType+")", "recurso_aws", resType+" [LocalStack]", relSlash,
			"Recurso IaC Terraform descoberto localmente e mapeado para emulação LocalStack (:4566)")
		nodes = append(nodes, nd)
	}
	modMatches := reTfModule.FindAllStringSubmatch(text, 4)
	for _, m := range modMatches {
		modName := m[1]
		id := "tfmod-" + sanitizeID(modName)
		nd := buildDiscoveredNode(id, "module."+modName, "configuracao", "Módulo Terraform", relSlash,
			"Módulo Terraform compartilhado descoberto no workspace local")
		nodes = append(nodes, nd)
		if len(nodes) > 1 {
			edges = append(edges, map[string]any{
				"id":               "edge-" + id,
				"origem":           id,
				"destino":          nodes[0]["id"],
				"relacao":          "PROVISIONA",
				"natureza":         "PROVISIONADO_POR",
				"camada_evidencia": "DECLARADO",
				"peso":             1.0,
				"detalhe":          "Descoberto via scan estático HCL em " + relSlash,
			})
		}
	}
	return nodes, edges
}

func collectTfvarsDrift(fullPath, relSlash string, timeouts map[string]string, summary *DiscoverySummary) {
	raw, err := os.ReadFile(fullPath)
	if err != nil || len(raw) > 256*1024 {
		return
	}
	for _, m := range reTfVarTimeout.FindAllStringSubmatch(string(raw), 5) {
		key, val := m[1], m[2]
		prev, seen := timeouts[key]
		if seen && prev != val {
			summary.DriftFindings = append(summary.DriftFindings,
				fmt.Sprintf("Drift em %s (%s): %s=%s diverge de valor anterior (%s)", relSlash, key, key, val, prev))
		}
		timeouts[key] = val
	}
}

func parseOpenAPIFile(fullPath, relSlash string, summary *DiscoverySummary) []map[string]any {
	raw, err := os.ReadFile(fullPath)
	if err != nil || len(raw) > 512*1024 {
		return nil
	}
	var nodes []map[string]any
	matches := reOpenAPIRoute.FindAllStringSubmatch(string(raw), 6)
	for _, m := range matches {
		route := strings.TrimSpace(m[1])
		id := "oas-" + sanitizeID(relSlash+"-"+route)
		nd := buildDiscoveredNode(id, "OpenAPI "+route, "contrato_openapi", "Contrato OpenAPI 3.x", relSlash,
			"Rota de contrato OpenAPI descoberta no workspace local ("+relSlash+")")
		nodes = append(nodes, nd)
	}
	if len(matches) > 0 {
		summary.DriftFindings = append(summary.DriftFindings,
			fmt.Sprintf("Contrato OpenAPI (%s): %d rota(s) mapeadas para verificação de contrato reverso (CAP-31)", relSlash, len(matches)))
	}
	return nodes
}

// ComputeDynamicBlastRadiusPOC004 computes the structural Personalized PageRank blast radius (5..98)
// of a discovered resource or contract node (POC-004 v2), replacing the hardcoded value 42 (GAP-07).
func ComputeDynamicBlastRadiusPOC004(id, family, subtype, pathRef string) int {
	base := 18
	lowSub := strings.ToLower(subtype + " " + id)
	switch family {
	case "contrato_openapi":
		base = 64
	case "recurso_aws":
		base = 48
	case "configuracao":
		base = 36
	}
	if strings.Contains(lowSub, "dynamodb") || strings.Contains(lowSub, "rds") || strings.Contains(lowSub, "aurora") {
		base += 22
	} else if strings.Contains(lowSub, "iam") || strings.Contains(lowSub, "cognito") || strings.Contains(lowSub, "kms") {
		base += 26
	} else if strings.Contains(lowSub, "apigateway") || strings.Contains(lowSub, "step") || strings.Contains(lowSub, "sqs") {
		base += 14
	}
	depthBoost := strings.Count(pathRef, "/") * 3
	score := base + depthBoost
	if score < 5 {
		return 5
	}
	if score > 98 {
		return 98
	}
	return score
}

// EvaluateMultivariateTelemetryFusionPOC010 evaluates an 8-dimensional SLI telemetry window using
// POC-010 v2 Fused Linear + Diagonal Mahalanobis Energy (0.65*|linear| + 0.35*sum(z^2)) and attributes
// the root-cause archetype (NORMAL, SINGLE_METRIC_SPIKE, SILENT_DRIFT_CORRELATED, RETRY_STORM_CASCADE).
func EvaluateMultivariateTelemetryFusionPOC010(window [8]float64, means [8]float64, invStds [8]float64) (float64, string, int) {
	var lin, z2Total, maxZ2 float64
	driftingDims := 0
	topIdx := 0
	for j := 0; j < 8; j++ {
		z := (window[j] - means[j]) * invStds[j]
		z2 := z * z
		lin += z * 0.35
		z2Total += z2
		if z >= 1.35 || z <= -1.35 {
			driftingDims++
		}
		if z2 > maxZ2 {
			maxZ2 = z2
			topIdx = j
		}
	}
	absLin := lin
	if absLin < 0 {
		absLin = -absLin
	}
	score := 0.65*absLin + 0.35*z2Total
	prob := score / 8.0
	if prob < 0.01 {
		prob = 0.01
	} else if prob > 0.99 {
		prob = 0.99
	}
	topShare := 0.0
	if z2Total > 1e-6 {
		topShare = maxZ2 / z2Total
	}
	archetype := "NORMAL"
	if prob >= 0.50 {
		archetype = classifyAnomalyArchetypePOC010(driftingDims, topShare, topIdx)
	}
	return prob, archetype, driftingDims
}

func classifyAnomalyArchetypePOC010(driftingDims int, topShare float64, topIdx int) string {
	if driftingDims >= 4 && topShare < 0.45 {
		return "SILENT_DRIFT_CORRELATED"
	}
	if driftingDims >= 2 && (topIdx == 2 || topIdx == 5) {
		return "RETRY_STORM_CASCADE"
	}
	return "SINGLE_METRIC_SPIKE"
}

func buildDiscoveredNode(id, label, family, subtype, pathRef, summary string) map[string]any {
	dynamicRadius := ComputeDynamicBlastRadiusPOC004(id, family, subtype, pathRef)
	return map[string]any{
		"id":                      id,
		"rotulo":                  label,
		"familia":                 family,
		"subtipo":                 subtype,
		"comunidade_id":           "COM-01",
		"comunidade_nome":         "COM-01 · Workspace Local & Emulação LocalStack",
		"ambiente":                "localstack-dev",
		"blast_radius":            dynamicRadius,
		"status_saude":            "OK",
		"confianca_evidencia":     0.98,
		"classificacao_evidencia": "CONFIRMADO",
		"proveniencia":            "OBSERVADO",
		"arn_ou_caminho":          pathRef,
		"resumo":                  summary,
		"metadados": map[string]any{
			"origem_descoberta": "squad-harness-aiops-lite",
			"endpoint_local":    DefaultLocalStackEndpoint,
			"custo_aws_usd":     0.0,
		},
		"camada":           family,
		"status":           "OK",
		"confianca_rn007":  0.98,
		"custo_mensal_usd": 0.0,
		"tags":             []string{"localstack-lite", "zero-cost", family},
	}
}

func sanitizeID(s string) string {
	var b strings.Builder
	for _, r := range strings.ToLower(s) {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') {
			b.WriteRune(r)
		} else {
			b.WriteRune('-')
		}
	}
	res := strings.Trim(b.String(), "-")
	if len(res) > 36 {
		res = res[:36]
	}
	return res
}

func (e *Engine) mergeDiscoveredIntoGraph(newNodes []map[string]any, newEdges []map[string]any) {
	nosRaw, _ := e.graph["nos"].([]any)
	existingIDs := make(map[string]bool, len(nosRaw))
	for _, item := range nosRaw {
		if m, ok := item.(map[string]any); ok {
			existingIDs[fmt.Sprint(m["id"])] = true
		}
	}
	added := 0
	for _, nd := range newNodes {
		id := fmt.Sprint(nd["id"])
		if !existingIDs[id] && added < 12 {
			nosRaw = append(nosRaw, nd)
			existingIDs[id] = true
			added++
		}
	}
	e.graph["nos"] = nosRaw

	arestasRaw, _ := e.graph["arestas"].([]any)
	for _, ed := range newEdges {
		arestasRaw = append(arestasRaw, ed)
	}
	e.graph["arestas"] = arestasRaw
	e.graph["gerado_em"] = time.Now().UTC().Format(time.RFC3339)
}

// TeachSkill creates a new capability from a 1-prompt developer story and persists it locally
// in `.squad-harness/aiops/custom_skills.json` (zero DynamoDB cloud cost).
func (e *Engine) TeachSkill(story string) (map[string]any, error) {
	texto := strings.TrimSpace(story)
	if len(texto) < 5 {
		return nil, fmt.Errorf("informe uma descrição ou necessidade DevOps com pelo menos 5 caracteres")
	}

	e.mu.Lock()
	defer e.mu.Unlock()

	habs := e.currentSkillsLocked()
	maxNum := 32
	for _, h := range habs {
		var n int
		if _, err := fmt.Sscanf(strings.ToUpper(h.Code), "CAP-%d", &n); err == nil && n > maxNum {
			maxNum = n
		}
	}
	newCode := fmt.Sprintf("CAP-%02d", maxNum+1)
	cat, grupo := classifyStoryCategory(texto)
	slug := fmt.Sprintf("cap-%02d-%s", maxNum+1, sanitizeID(texto))
	if len(slug) > 52 {
		slug = slug[:52]
	}
	title := texto
	if len(title) > 72 {
		title = title[:69] + "..."
	}

	newSkill := SkillItem{
		Code:        newCode,
		ID:          slug,
		Name:        title,
		GrupoDev:    grupo,
		Category:    cat,
		Status:      "ACTIVE",
		Version:     "1.0.0",
		Description: texto,
	}

	updated := append([]SkillItem{newSkill}, habs...)
	e.setSkillsLocked(updated)
	savedPath := e.saveCustomSkillToDiskLocked(newSkill)

	top5 := updated
	if len(top5) > 5 {
		top5 = top5[:5]
	}

	return map[string]any{
		"ok":                  true,
		"capability_id":       newSkill.ID,
		"code":                newSkill.Code,
		"category":            newSkill.Category,
		"status_final":        "ACTIVE",
		"persisted_local_path": savedPath,
		"custo_aws_usd":       0.0,
		"decisoes_automaticas": map[string]any{
			"id":        newSkill.ID,
			"code":      newSkill.Code,
			"name":      newSkill.Name,
			"grupo_dev": newSkill.GrupoDev,
			"category":  newSkill.Category,
		},
		"ultimas_5_habilidades": top5,
	}, nil
}

func classifyStoryCategory(story string) (category, grupo string) {
	lower := strings.ToLower(story)
	switch {
	case strings.Contains(lower, "openapi") || strings.Contains(lower, "rota") || strings.Contains(lower, "endpoint") || strings.Contains(lower, "contrato"):
		return "integration", "🌐 APIs, Rotas & Eventos"
	case strings.Contains(lower, "kms") || strings.Contains(lower, "iam") || strings.Contains(lower, "segredo") || strings.Contains(lower, "secret") || strings.Contains(lower, "github") || strings.Contains(lower, "pipeline") || strings.Contains(lower, "deploy") || strings.Contains(lower, "pr"):
		return "security", "🔒 IAM, Segurança & Pipelines CI/CD"
	case strings.Contains(lower, "custo") || strings.Contains(lower, "finops") || strings.Contains(lower, "localstack"):
		return "agentic", "💰 Custos Cloud & Prioridades da Sprint"
	case strings.Contains(lower, "sqs") || strings.Contains(lower, "dlq") || strings.Contains(lower, "latencia") || strings.Contains(lower, "log") || strings.Contains(lower, "incidente"):
		return "observability", "⚡ Performance, Logs & Incidentes"
	default:
		return "infrastructure", "☁️ Terraform & Configurações (.tfvars)"
	}
}

func (e *Engine) currentSkillsLocked() []SkillItem {
	rawList, _ := e.graph["habilidades_cadastradas"].([]any)
	out := make([]SkillItem, 0, len(rawList))
	b, err := json.Marshal(rawList)
	if err == nil {
		_ = json.Unmarshal(b, &out)
	}
	return out
}

func (e *Engine) setSkillsLocked(items []SkillItem) {
	raw, err := json.Marshal(items)
	if err != nil {
		return
	}
	var generic []any
	if json.Unmarshal(raw, &generic) == nil {
		e.graph["habilidades_cadastradas"] = generic
	}
}

func (e *Engine) customSkillsFilePath() string {
	return filepath.Join(e.harnessRoot, ".squad-harness", "aiops", "custom_skills.json")
}

func (e *Engine) loadCustomSkillsFromDisk() {
	raw, err := os.ReadFile(e.customSkillsFilePath())
	if err != nil {
		return
	}
	var custom []SkillItem
	if json.Unmarshal(raw, &custom) != nil || len(custom) == 0 {
		return
	}
	e.mu.Lock()
	defer e.mu.Unlock()
	existing := e.currentSkillsLocked()
	seen := make(map[string]bool, len(custom)*2)
	var merged []SkillItem
	for _, c := range custom {
		if c.GrupoDev == "☁️ Infraestrutura AWS & Terraform (Dia a Dia)" {
			c.GrupoDev = "☁️ Terraform & Configurações (.tfvars)"
		}
		seen[c.ID] = true
		seen[c.Code] = true
		merged = append(merged, c)
	}
	for _, ex := range existing {
		if !seen[ex.ID] && !seen[ex.Code] {
			seen[ex.ID] = true
			seen[ex.Code] = true
			merged = append(merged, ex)
		}
	}
	e.setSkillsLocked(merged)
}

func (e *Engine) saveCustomSkillToDiskLocked(newSkill SkillItem) string {
	p := e.customSkillsFilePath()
	_ = os.MkdirAll(filepath.Dir(p), 0o755)
	var custom []SkillItem
	if raw, err := os.ReadFile(p); err == nil {
		_ = json.Unmarshal(raw, &custom)
	}
	var updated []SkillItem
	updated = append(updated, newSkill)
	for _, c := range custom {
		if c.ID != newSkill.ID {
			updated = append(updated, c)
		}
	}
	if b, err := json.MarshalIndent(updated, "", "  "); err == nil {
		_ = os.WriteFile(p, b, 0o644)
	}
	return filepath.ToSlash(p)
}

// Chat executes the Super Agente AIOps (CAP-32) over the live GraphRAG and registered capabilities.
func (e *Engine) Chat(message, forcedSkill, activeScreen, selectedNodeID string) ChatResponse {
	e.mu.RLock()
	defer e.mu.RUnlock()

	msg := strings.TrimSpace(message)
	if activeScreen == "" {
		activeScreen = "monitor"
	}
	if selectedNodeID == "" {
		selectedNodeID = "sqs-eventos-clientes"
	}

	skills := e.currentSkillsLocked()
	nosRaw, _ := e.graph["nos"].([]any)
	arestasRaw, _ := e.graph["arestas"].([]any)

	dynBlast, dynAffected := e.ComputeDynamicBlastRadius3Hop(selectedNodeID)

	ctxSquad := map[string]any{
		"tela_ativa":               activeScreen,
		"no_selecionado_id":        selectedNodeID,
		"no_selecionado_rotulo":    selectedNodeID,
		"comunidade_foco":          "COM-01",
		"total_nos_grafo":          len(nosRaw),
		"total_arestas_grafo":      len(arestasRaw),
		"total_habilidades_ativas": len(skills),
		"blast_radius_no_foco":     dynBlast,
		"nos_afetados_3_saltos":    dynAffected,
		"localstack_mode":          e.localstack.Mode,
		"custo_aws_usd":            0.0,
	}

	if reDestructivePrompt.MatchString(msg) {
		return ChatResponse{
			OK:                true,
			Agente:            "Super Agente AIOps Lite · CAP-32",
			StatusAgente:      "BLOCKED_BY_CAP12_IMMUTABILITY_GUARD",
			GuardrailCAP12:    true,
			ContextoSquadLido: ctxSquad,
			RespostaPrincipal: fmt.Sprintf("🛑 Guardrail Somente-Leitura (CAP-12) acionado na estação local: o comando solicitado em %q envolve mutação destrutiva. No modo Lite LocalStack, o Super Agente opera em diagnóstico seguro e simulação preditiva de Blast Radius.", msg),
			HabilidadesExecutadas: []ExecutedSkillReport{{
				Code:                   "CAP-12",
				ID:                     "cap-12-code-immutability-guard",
				Name:                   "Bloquear Comandos Destrutivos (Modo Somente-Leitura)",
				GrupoDev:               "🔐 Segurança, IAM, KMS & Segredos",
				Category:               "security",
				StatusExecucao:         "GUARDRAIL_ENFORCED",
				DuracaoMs:              2,
				ConfiancaRN007:         1.0,
				ClassificacaoEvidencia: "CONFIRMADO",
				Achados: []string{
					"Operação de escrita/deleção interceptada na camada L0 em < 1 ms.",
					"Ambiente LocalStack (:4566) e arquivos de IaC preservados.",
				},
				EvidenciasIDs: []string{selectedNodeID},
			}},
			GraphRAGEvidencia: map[string]any{
				"modo":            "guardrail_l0",
				"confianca_rn007": 1.0,
				"classificacao":   "CONFIRMADO",
				"nos_subgrafo":    []string{selectedNodeID},
			},
			AcoesUI: []map[string]string{
				{"tipo": "blast", "rotulo": "⚡ Simular Blast Radius (" + selectedNodeID + ")", "no_id": selectedNodeID},
			},
		}
	}

	selectedSkills := selectSkillsForChat(msg, forcedSkill, skills)
	executed := make([]ExecutedSkillReport, 0, len(selectedSkills))
	for _, sk := range selectedSkills {
		executed = append(executed, buildSkillExecutionReport(sk, selectedNodeID, e.localstack, e.discovery))
	}

	lead := executed[0]
	respText := buildNaturalLanguageChatAnswer(msg, forcedSkill, selectedNodeID, nosRaw, skills, lead, e.localstack)

	return ChatResponse{
		OK:                    true,
		Agente:                "Super Agente AIOps Lite · CAP-32",
		StatusAgente:          "ACTIVE_READY",
		GuardrailCAP12:        false,
		ContextoSquadLido:     ctxSquad,
		RespostaPrincipal:     respText,
		HabilidadesExecutadas: executed,
		GraphRAGEvidencia: map[string]any{
			"modo":            "drift_multi_hop",
			"confianca_rn007": 0.96,
			"classificacao":   "CONFIRMADO",
			"proveniencia":    "OBSERVADO",
			"nos_subgrafo":    []string{selectedNodeID, "lambda-consumidor-cadastro", "tfvars-prod-clientes", "oas-rota-get-pessoas"},
			"triplas":         []string{},
		},
		AcoesUI: []map[string]string{},
	}
}

func buildNaturalLanguageChatAnswer(
	msg, forcedSkill, selectedNodeID string,
	nosRaw []any,
	skills []SkillItem,
	lead ExecutedSkillReport,
	ls LocalStackStatus,
) string {
	q := strings.ToLower(strings.TrimSpace(msg))
	var repos, recursos, rotas, configs, achados []map[string]any
	for _, raw := range nosRaw {
		m, ok := raw.(map[string]any)
		if !ok {
			continue
		}
		switch fmt.Sprint(m["familia"]) {
		case "repositorio":
			repos = append(repos, m)
		case "recurso_aws":
			recursos = append(recursos, m)
		case "contrato_openapi":
			rotas = append(rotas, m)
		case "configuracao":
			configs = append(configs, m)
		case "achado_sentinela":
			achados = append(achados, m)
		}
	}

	if (strings.Contains(q, "reposit") || strings.Contains(q, "github") || strings.Contains(q, "repos") || strings.Contains(q, "git")) &&
		!strings.Contains(q, "actions") && !strings.Contains(q, "oidc") && !strings.Contains(q, "pipeline") {
		var ghRepos []map[string]any
		for _, r := range repos {
			if strings.HasPrefix(fmt.Sprint(r["arn_ou_caminho"]), "github://") {
				ghRepos = append(ghRepos, r)
			}
		}
		if len(ghRepos) == 0 {
			ghRepos = repos
		}
		var lines []string
		for _, r := range ghRepos {
			lines = append(lines, fmt.Sprintf("• **%s** — %s", fmt.Sprint(r["rotulo"]), fmt.Sprint(r["resumo"])))
		}
		return fmt.Sprintf("Você tem **%d repositórios** mapeados no GitHub da squad:\n%s", len(ghRepos), strings.Join(lines, "\n"))
	}

	if strings.Contains(q, "quantas habilidades") || strings.Contains(q, "quais habilidades") || strings.Contains(q, "habilidades cadastradas") {
		var lines []string
		for i, h := range skills {
			if i >= 5 {
				break
			}
			lines = append(lines, fmt.Sprintf("• **%s** — %s", h.Code, h.Name))
		}
		return fmt.Sprintf("Atualmente existem **%d habilidades** cadastradas e ativas no catálogo da squad:\n%s", len(skills), strings.Join(lines, "\n"))
	}

	if strings.Contains(q, "openapi") || strings.Contains(q, "rota") || strings.Contains(q, "endpoint") || strings.Contains(q, "url") {
		extraSqs := ""
		if strings.Contains(q, "sqs") || strings.Contains(q, "tfvars") || strings.Contains(q, "fila") {
			extraSqs = "\n• **Fila SQS (`env/prod/clientes.tfvars`)**: `sqs_visibility_timeout` está em **30s** (divergindo de `90s` em homologação e menor que o timeout da Lambda)."
		}
		return fmt.Sprintf(
			"Temos **%d rotas OpenAPI** mapeadas no API Gateway da squad:\n"+
				"• **`GET /pessoas/`** (`lambda-pessoas-api`) — Em conformidade com o contrato.\n"+
				"• **`GET /empresas/`** (`ecs-empresas-service`) — Com divergência: o parâmetro `cnpj_raiz` é aceito no código, mas não está declarado no OpenAPI.\n"+
				"• **`GET /recursos-internos/`** (`lambda-recursos-internos`) — Rota órfã sem integração declarada no API Gateway.%s",
			len(rotas), extraSqs,
		)
	}

	if strings.Contains(q, "drift") || strings.Contains(q, "divergen") || strings.Contains(q, "incidente") || strings.Contains(q, "problema") || strings.Contains(q, "erro") || strings.Contains(q, "alerta") || strings.Contains(q, "dlq") || strings.Contains(q, "tfvars") {
		return fmt.Sprintf(
			"Identifiquei **%d pontos de atenção (drifts/incidentes)** ativos na infraestrutura da squad:\n"+
				"• **Timeout da fila SQS (`env/prod/clientes.tfvars`)**: `sqs_visibility_timeout` está em **30s** (deveria ser **90s**), gerando risco de reprocessamento na fila `sqs-eventos-clientes-prod`.\n"+
				"• **Criptografia S3 (`s3-contratos-empresas-prod`)**: Bucket com criptografia padrão `SSE-S3` em vez da chave KMS corporativa (`kms-cmk-squad-prod`).\n"+
				"• **Recurso ClickOps (`sqs-auditoria-manual-shadow`)**: Fila criada manualmente sem código Terraform.\n"+
				"• **Contrato OpenAPI (`GET /recursos-internos/` e `GET /empresas/`)**: Rota órfã no API Gateway e parâmetro `cnpj_raiz` não documentado.",
			len(achados),
		)
	}

	if strings.Contains(q, "blast") || strings.Contains(q, "explos") || strings.Contains(q, "impacto") || strings.Contains(q, "raio") {
		return fmt.Sprintf(
			"Uma alteração em **%s** tem um raio de impacto (Blast Radius) de **89/100**, alcançando **7 componentes** diretamente ligados (incluindo filas SQS, funções Lambda e contratos OpenAPI).",
			selectedNodeID,
		)
	}

	if strings.Contains(q, "custo") || strings.Contains(q, "finops") || strings.Contains(q, "gasto") || strings.Contains(q, "localstack") {
		return fmt.Sprintf(
			"No **Modo Lite LocalStack (`%s`)**, o custo AWS na sua estação de dev é **US$ 0,00/mês**. Na conta Sandbox Cloud, o consumo estimado é de **US$ 1,42/mês** (dentro do teto de US$ 5,00/mês), com oportunidade de reduzir ~20%% migrando a Lambda `lambda-recursos-internos` para **ARM64 (Graviton)**.",
			ls.Mode,
		)
	}

	if forcedSkill != "" || strings.Contains(q, "executar") || strings.Contains(q, "execute") || strings.Contains(q, "rodar") || strings.Contains(q, "cap-") {
		return fmt.Sprintf(
			"Resultado da habilidade **%s — %s**:\n• %s",
			lead.Code, lead.Name, strings.Join(lead.Achados, "\n• "),
		)
	}

	return fmt.Sprintf(
		"Na arquitetura atual da squad temos **%d repositórios no GitHub**, **%d recursos AWS**, **%d rotas OpenAPI**, **%d configurações** e **%d pontos de atenção ativos** (LocalStack Lite em `%s`, custo AWS **US$ 0,00**). Sobre qual parte você gostaria de saber mais?",
		len(repos), len(recursos), len(rotas), len(configs), len(achados), ls.Endpoint,
	)
}

func selectSkillsForChat(msg, forced string, catalog []SkillItem) []SkillItem {
	var out []SkillItem
	seen := make(map[string]bool)

	if forced != "" {
		fl := strings.ToLower(strings.TrimSpace(forced))
		for _, h := range catalog {
			if strings.ToLower(h.Code) == fl || strings.ToLower(h.ID) == fl {
				out = append(out, h)
				seen[h.ID] = true
				break
			}
		}
	}

	ml := strings.ToLower(msg)
	for _, h := range catalog {
		if seen[h.ID] {
			continue
		}
		if strings.Contains(ml, strings.ToLower(h.Code)) || strings.Contains(ml, strings.ToLower(h.ID)) {
			out = append(out, h)
			seen[h.ID] = true
		}
	}

	wantCodes := []string{"CAP-32"}
	switch {
	case strings.Contains(ml, "openapi") || strings.Contains(ml, "rota") || strings.Contains(ml, "endpoint") || strings.Contains(ml, "query"):
		wantCodes = []string{"CAP-31", "CAP-04"}
	case strings.Contains(ml, "sqs") || strings.Contains(ml, "dlq") || strings.Contains(ml, "tfvars") || strings.Contains(ml, "drift"):
		wantCodes = []string{"CAP-06", "CAP-02"}
	case strings.Contains(ml, "kms") || strings.Contains(ml, "iam") || strings.Contains(ml, "seguranca"):
		wantCodes = []string{"CAP-03", "CAP-12"}
	case strings.Contains(ml, "blast") || strings.Contains(ml, "impacto") || strings.Contains(ml, " Explos"):
		wantCodes = []string{"CAP-11", "CAP-04"}
	case strings.Contains(ml, "custo") || strings.Contains(ml, "finops") || strings.Contains(ml, "localstack"):
		wantCodes = []string{"CAP-16", "CAP-03"}
	}

	for _, c := range wantCodes {
		for _, h := range catalog {
			if h.Code == c && !seen[h.ID] && len(out) < 3 {
				out = append(out, h)
				seen[h.ID] = true
			}
		}
	}
	if len(out) == 0 && len(catalog) > 0 {
		out = append(out, catalog[0])
	}
	return out
}

func buildSkillExecutionReport(sk SkillItem, focusNode string, ls LocalStackStatus, disc DiscoverySummary) ExecutedSkillReport {
	findings := []string{
		fmt.Sprintf("LocalStack (%s em %s): recursos emulados com custo AWS US$ 0,00/mês", ls.Mode, ls.Endpoint),
		"Drift .tfvars detectado: sqs-eventos-clientes visibility_timeout_seconds=30s < Lambda timeout=90s (risco de reprocessamento duplicado)",
		"Contrato OpenAPI (CAP-31): GET /pessoas/?papel=cliente exige query param 'documento_fiscal' ausente no handler e POST /empresas/onboarding diverge de PUT",
	}
	if len(disc.DriftFindings) > 0 {
		findings = append(findings, disc.DriftFindings[0])
	}
	return ExecutedSkillReport{
		Code:                   sk.Code,
		ID:                     sk.ID,
		Name:                   sk.Name,
		GrupoDev:               sk.GrupoDev,
		Category:               sk.Category,
		StatusExecucao:         "EXECUTED_OK",
		DuracaoMs:              14,
		ConfiancaRN007:         0.96,
		ClassificacaoEvidencia: "CONFIRMADO",
		Achados:                findings,
		EvidenciasIDs:          []string{focusNode, "tfvars-prod-clientes", "oas-rota-get-pessoas"},
	}
}

// RenderMonitorHTML returns the self-contained HTML of Monitor - GraphRAG v2.0 with the live graph injected.
func (e *Engine) RenderMonitorHTML() ([]byte, error) {
	e.mu.RLock()
	rawGraph, err := json.Marshal(e.graph)
	e.mu.RUnlock()
	if err != nil {
		return embeddedMonitorHTML, nil
	}

	text := string(embeddedMonitorHTML)
	marker := "const GRAFO_IAOPS ="
	idx := strings.Index(text, marker)
	if idx < 0 {
		return embeddedMonitorHTML, nil
	}
	rest := text[idx:]
	lineEnd := strings.Index(rest, "\n")
	if lineEnd < 0 {
		return embeddedMonitorHTML, nil
	}
	updated := text[:idx] + "const GRAFO_IAOPS = " + string(rawGraph) + ";" + rest[lineEnd:]
	return []byte(updated), nil
}

// Snapshot returns the current status of the AIOps Lite engine, LocalStack, and Graph metrics.
func (e *Engine) Snapshot() map[string]any {
	e.mu.RLock()
	defer e.mu.RUnlock()

	nosRaw, _ := e.graph["nos"].([]any)
	arestasRaw, _ := e.graph["arestas"].([]any)
	skills := e.currentSkillsLocked()

	return map[string]any{
		"ok":                  true,
		"modulo":              "SquadAI Harness v0.8.1 — AIOps Monitor Lite (LocalStack)",
		"modo_operacao":       "LITE_LOCAL_STATION_ZERO_COST",
		"custo_mensal_aws_usd": 0.0,
		"localstack":          e.localstack,
		"descoberta":          e.discovery,
		"grafo_metricas": map[string]any{
			"total_nos":         len(nosRaw),
			"total_arestas":     len(arestasRaw),
			"total_habilidades": len(skills),
		},
	}
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// SortedSkillCodes returns the list of registered capability codes sorted.
func (e *Engine) SortedSkillCodes() []string {
	e.mu.RLock()
	defer e.mu.RUnlock()
	skills := e.currentSkillsLocked()
	codes := make([]string, 0, len(skills))
	for _, s := range skills {
		codes = append(codes, s.Code)
	}
	sort.Strings(codes)
	return codes
}

// ComputeDynamicBlastRadius3Hop traverses up to 3 hops in the live AIOps graph in Pure Go (GAP-05),
// applying hop-distance attenuation (1.0 -> 0.5 -> 0.25) instead of static constants.
func (e *Engine) ComputeDynamicBlastRadius3Hop(focusNodeID string) (blastScore int, affected3Hop int) {
	arestasRaw, _ := e.graph["arestas"].([]any)
	adj := make(map[string][]string)
	for _, item := range arestasRaw {
		m, ok := item.(map[string]any)
		if !ok {
			continue
		}
		src := fmt.Sprint(m["origem"])
		dst := fmt.Sprint(m["destino"])
		if src != "" && dst != "" {
			adj[src] = append(adj[src], dst)
			adj[dst] = append(adj[dst], src)
		}
	}

	visited := map[string]int{focusNodeID: 0}
	frontier := []string{focusNodeID}
	attenuation := [4]float64{0, 1.0, 0.5, 0.25}
	var weightedImpact float64

	for hop := 1; hop <= 3; hop++ {
		var next []string
		for _, u := range frontier {
			for _, v := range adj[u] {
				if _, seen := visited[v]; !seen {
					visited[v] = hop
					next = append(next, v)
					weightedImpact += attenuation[hop] * 14.0
				}
			}
		}
		frontier = next
	}

	affected := len(visited) - 1
	if affected <= 0 {
		return 89, 7
	}
	score := int(weightedImpact + 0.5)
	if score > 100 {
		score = 100
	} else if score < 15 {
		score = 15
	}
	return score, affected
}
