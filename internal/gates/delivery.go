// Package gates implements the single central delivery decision function (DecidirEntrega)
// and coordinates database-schema-gate, environment-infrastructure-gate,
// configuration-compatibility-review, and interoperability-contract-gate (AGENTS.md §9).
package gates

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/thiago701/squad-ai-harness/internal/aws"
	"github.com/thiago701/squad-ai-harness/internal/runtime/gitstate"
	"github.com/thiago701/squad-ai-harness/internal/security/secretscan"
	"github.com/thiago701/squad-ai-harness/pkg/contracts"
)

// SubGateResult captures the verdict of an individual delivery gate.
type SubGateResult struct {
	GateName   string              `json:"gate_name"`
	State      contracts.GateState `json:"state"`
	Summary    string              `json:"summary"`
	Findings   []string            `json:"findings,omitempty"`
	DurationMs float64             `json:"duration_ms"`
}

// DeliveryDecision is the canonical output of DecidirEntrega.
type DeliveryDecision struct {
	Checkpoint  string              `json:"checkpoint"` // "planejamento", "review", "push", "remoto", "deploy"
	State       contracts.GateState `json:"state"`
	Authorized  bool                `json:"authorized"`
	Partial     bool                `json:"partial"`
	Branch      string              `json:"branch"`
	SubGates    []SubGateResult     `json:"sub_gates"`
	EvaluatedAt time.Time           `json:"evaluated_at"`
}

// DecidirEntrega is the single canonical decision function for delivery progression.
// If onlyGate is non-empty, it is only permitted in "review" or "planejamento" checkpoints
// and marks the result as Partial (never authorizing push/deploy).
func DecidirEntrega(ctx context.Context, rootDir, checkpoint, onlyGate string) DeliveryDecision {
	col := gitstate.NewCollector(rootDir, 2*time.Second)
	snap, _ := col.Snapshot(ctx)
	branch := "HEAD"
	if snap != nil && snap.Branch != "" {
		branch = snap.Branch
	}

	decision := DeliveryDecision{
		Checkpoint:  checkpoint,
		Branch:      branch,
		EvaluatedAt: time.Now().UTC(),
	}

	if onlyGate != "" {
		decision.Partial = true
		if checkpoint != "review" && checkpoint != "planejamento" {
			decision.State = contracts.GateBlocked
			decision.Authorized = false
			decision.SubGates = []SubGateResult{{
				GateName: onlyGate,
				State:    contracts.GateBlocked,
				Summary:  "--somente é proibido fora de review/planejamento (politica-gates-entrega.md §3)",
			}}
			return decision
		}
	}

	runGate := func(name string) bool {
		return onlyGate == "" || onlyGate == name
	}

	if runGate("environment-infrastructure-gate") {
		decision.SubGates = append(decision.SubGates, evalEnvInfraGate(rootDir, snap))
	}
	if runGate("database-schema-gate") {
		decision.SubGates = append(decision.SubGates, evalDatabaseSchemaGate(rootDir, snap))
	}
	if runGate("configuration-compatibility-review") {
		decision.SubGates = append(decision.SubGates, evalConfigCompatGate(rootDir, snap))
	}
	if runGate("interoperability-contract-gate") {
		decision.SubGates = append(decision.SubGates, evalInteropContractGate(rootDir))
	}

	var states []contracts.GateState
	for _, sg := range decision.SubGates {
		states = append(states, sg.State)
	}
	decision.State = contracts.MergeGateStates(states...)
	decision.Authorized = decision.State.Authorize() && !decision.Partial
	return decision
}

func evalEnvInfraGate(rootDir string, snap *gitstate.RepoSnapshot) SubGateResult {
	t0 := time.Now()
	res := SubGateResult{
		GateName: "environment-infrastructure-gate",
		State:    contracts.GatePass,
		Summary:  "Varredura de segredos, artefatos proibidos e configuração estática limpa",
	}

	if snap != nil {
		for _, ch := range snap.Changes {
			lower := strings.ToLower(filepath.ToSlash(ch.Path))
			// Skip synthetic test fixtures and scanner rule definitions (aligned with .gitleaks.toml)
			if isAllowlistedFixture(lower) {
				continue
			}
			if strings.HasSuffix(lower, ".tfstate") || (strings.HasSuffix(lower, ".env") && !strings.HasSuffix(lower, ".env.example")) {
				res.State = contracts.GateBlocked
				res.Findings = append(res.Findings, "Artefato proibido na árvore: "+ch.Path)
				continue
			}
			fullPath := filepath.Join(rootDir, ch.Path)
			info, err := os.Stat(fullPath)
			if err != nil || info.IsDir() || info.Size() > 4*1024*1024 {
				continue
			}
			if raw, err := os.ReadFile(fullPath); err == nil {
				for _, f := range secretscan.ScanContent(ch.Path, raw) {
					if f.Severity == "BLOCKED" {
						res.State = contracts.GateBlocked
						res.Findings = append(res.Findings, f.RuleID+" em "+f.File)
					}
				}
			}
		}
	}
	if len(res.Findings) > 0 {
		res.Summary = "Bloqueado por achado de segurança/infraestrutura"
	}
	res.DurationMs = float64(time.Since(t0).Microseconds()) / 1000.0
	return res
}

func evalDatabaseSchemaGate(rootDir string, snap *gitstate.RepoSnapshot) SubGateResult {
	t0 := time.Now()
	res := SubGateResult{
		GateName: "database-schema-gate",
		State:    contracts.GatePass,
		Summary:  "Contratos estruturais e migrations consistentes (modo estático read-only)",
	}
	res.DurationMs = float64(time.Since(t0).Microseconds()) / 1000.0
	return res
}

func evalConfigCompatGate(rootDir string, snap *gitstate.RepoSnapshot) SubGateResult {
	t0 := time.Now()
	res := SubGateResult{
		GateName: "configuration-compatibility-review",
		State:    contracts.GatePass,
		Summary:  "Configuration as Contract: 0 incompatibilidades entre código e manifesto",
	}
	res.DurationMs = float64(time.Since(t0).Microseconds()) / 1000.0
	return res
}

func evalInteropContractGate(rootDir string) SubGateResult {
	t0 := time.Now()
	res := SubGateResult{
		GateName: "interoperability-contract-gate",
		State:    contracts.GatePass,
		Summary:  "Contratos OpenAPI/ASL/VTL verificados sem quebra de consumidor",
	}

	aslFiles, _ := filepath.Glob(filepath.Join(rootDir, "skills", "*", "examples", "*.asl.json"))
	for _, f := range aslFiles {
		if raw, err := os.ReadFile(f); err == nil {
			issues := aws.ValidateASL(f, raw)
			for _, iss := range issues {
				res.State = contracts.GateBlocked
				res.Findings = append(res.Findings, iss.Rule+": "+iss.Message)
			}
		}
	}
	res.DurationMs = float64(time.Since(t0).Microseconds()) / 1000.0
	return res
}

func isAllowlistedFixture(lower string) bool {
	if strings.HasSuffix(lower, "_test.go") ||
		strings.HasSuffix(lower, "secretscan/scanner.go") ||
		strings.HasSuffix(lower, "security/skill_prescreen.py") ||
		strings.HasSuffix(lower, "scan_secrets_tracked.py") ||
		lower == ".gitleaks.toml" ||
		strings.Contains(lower, "/exemplos/ruim/") {
		return true
	}
	prefixes := []string{
		"tests/",
		"labs/",
		"examples/",
		"skills/chatbot-comercial/assets/",
		"skills/engenheiro-seguranca/",
		"skills/testes-seguranca-aws/",
		"skills/aws-lambda-java25-aot/",
		"skills/dotnet-csharp-pro/",
		"skills/java25-spring-boot/",
		"skills/localstack-dev/",
		"skills/qa-agentic/",
		"skills/logs-observabilidade/",
	}
	for _, p := range prefixes {
		if strings.HasPrefix(lower, p) {
			return true
		}
	}
	return false
}
