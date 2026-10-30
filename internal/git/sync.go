// Package git implements the JEV-directed git-sync state classifier and planner in Go (Etapa 2),
// replacing scripts/git/squad_sync.py and scripts/git/jev_git.py.
package git

import (
	"context"
	"fmt"
	"path/filepath"
	"sort"
	"strings"

	"github.com/thiago701/squad-ai-harness/internal/runtime/gitstate"
)

// SyncStep describes a single planned Git synchronization action with its autonomy level.
type SyncStep struct {
	Level   string   `json:"level"` // "N0", "N1", "N2", "N3"
	Action  string   `json:"action"`
	Reason  string   `json:"reason"`
	Commits []string `json:"commits,omitempty"`
}

// SyncPlan represents the deterministic JEV git-sync decision.
type SyncPlan struct {
	Branch     string     `json:"branch"`
	StateClass string     `json:"state_class"`
	RiskTier   string     `json:"risk_tier"`
	Confidence float64    `json:"confidence"`
	Blocked    bool       `json:"blocked"`
	BlockCause string     `json:"block_cause,omitempty"`
	Steps      []SyncStep `json:"steps"`
}

// BuildPlan classifies the repository state and builds a fail-closed synchronization plan (0 tokens).
func BuildPlan(ctx context.Context, rootDir string) (SyncPlan, error) {
	col := gitstate.NewCollector(rootDir, 0)
	snap, err := col.Snapshot(ctx)
	if err != nil {
		return SyncPlan{}, err
	}
	return ClassifyAndPlan(snap), nil
}

// ClassifyAndPlan executes the pure JEV state machine over a RepoSnapshot.
func ClassifyAndPlan(snap *gitstate.RepoSnapshot) SyncPlan {
	plan := SyncPlan{
		Branch:     snap.Branch,
		Confidence: 0.99,
		RiskTier:   "LOW",
	}

	if len(snap.Conflicts) > 0 {
		plan.StateClass = "CONFLITO"
		plan.RiskTier = "CRITICAL"
		plan.Blocked = true
		plan.BlockCause = fmt.Sprintf("%d arquivo(s) em conflito de merge", len(snap.Conflicts))
		plan.Steps = append(plan.Steps, SyncStep{
			Level:  "N3",
			Action: "abort_and_escalate_conflicts",
			Reason: "Conflitos exigem resolução humana explícita antes de continuar",
		})
		return plan
	}

	if snap.Detached {
		plan.StateClass = "DETACHED_HEAD"
		plan.RiskTier = "HIGH"
		plan.Blocked = true
		plan.BlockCause = "HEAD destacado (detached HEAD)"
		plan.Steps = append(plan.Steps, SyncStep{
			Level:  "N3",
			Action: "create_or_checkout_branch",
			Reason: "Criar branch nomeada antes de commitar (AGENTS.md §6)",
		})
		return plan
	}

	if snap.Diverged {
		plan.StateClass = "DIVERGIDO"
		plan.RiskTier = "HIGH"
		plan.Blocked = true
		plan.BlockCause = fmt.Sprintf("Branch divergiu do upstream (ahead=%d, behind=%d)", snap.Ahead, snap.Behind)
		plan.Steps = append(plan.Steps, SyncStep{
			Level:  "N3",
			Action: "escalate_divergence",
			Reason: "Proibido rebase/force-push automático; humano decide merge vs branch",
		})
		return plan
	}

	switch {
	case len(snap.Changes) == 0 && snap.Ahead == 0 && snap.Behind == 0:
		plan.StateClass = "LIMPO_SINCRONIZADO"
		plan.Steps = append(plan.Steps, SyncStep{
			Level:  "N0",
			Action: "noop",
			Reason: "Repositório limpo e em dia com o remoto",
		})
	case len(snap.Changes) > 0:
		plan.StateClass = "SUJO_LOCAL"
		if snap.DefaultBranch {
			plan.RiskTier = "MEDIUM"
			plan.Steps = append(plan.Steps, SyncStep{
				Level:  "N2",
				Action: "checkout_feature_branch",
				Reason: "Na branch padrão (master/main), criar branch antes de commitar (AGENTS.md §6)",
			})
		}
		if snap.Behind > 0 {
			plan.Steps = append(plan.Steps, SyncStep{
				Level:  "N2",
				Action: "git pull --ff-only",
				Reason: fmt.Sprintf("Atualizar %d commit(s) do remoto sem reescrever história", snap.Behind),
			})
		}
		commits := GroupConventionalCommits(snap.Changes)
		plan.Steps = append(plan.Steps, SyncStep{
			Level:   "N2",
			Action:  "commit_grouped_by_domain",
			Reason:  fmt.Sprintf("Agrupar %d arquivo(s) modificado(s) em Conventional Commits PT-BR", len(snap.Changes)),
			Commits: commits,
		})
		plan.Steps = append(plan.Steps, SyncStep{
			Level:  "N3",
			Action: "git push (gated by delivery gates)",
			Reason: "Push requer aprovação humana (--push) e gates de entrega PASS",
		})
	case snap.Ahead > 0:
		plan.StateClass = "AHEAD_PRONTO_PARA_PUSH"
		plan.Steps = append(plan.Steps, SyncStep{
			Level:  "N3",
			Action: "git push (gated by delivery gates)",
			Reason: fmt.Sprintf("Enviar %d commit(s) locais após validar gates de entrega", snap.Ahead),
		})
	case snap.Behind > 0:
		plan.StateClass = "BEHIND_FAST_FORWARD"
		plan.Steps = append(plan.Steps, SyncStep{
			Level:  "N2",
			Action: "git pull --ff-only",
			Reason: fmt.Sprintf("Avançar %d commit(s) do upstream com fast-forward", snap.Behind),
		})
	}

	return plan
}

// GroupConventionalCommits groups changed files by architectural scope and generates PT-BR Conventional Commit titles.
func GroupConventionalCommits(changes []gitstate.FileChange) []string {
	groups := make(map[string][]string)
	for _, ch := range changes {
		p := filepath.ToSlash(ch.Path)
		scope := classifyScope(p)
		groups[scope] = append(groups[scope], p)
	}

	var scopes []string
	for sc := range groups {
		scopes = append(scopes, sc)
	}
	sort.Strings(scopes)

	var msgs []string
	for _, sc := range scopes {
		files := groups[sc]
		prefix := "feat"
		if strings.HasPrefix(sc, "test") {
			prefix = "test"
		} else if strings.HasPrefix(sc, "docs") {
			prefix = "docs"
		} else if strings.HasPrefix(sc, "ops") || strings.HasPrefix(sc, "governance") {
			prefix = "chore"
		}
		msgs = append(msgs, fmt.Sprintf("%s(%s): atualizar %d artefato(s) no escopo %s", prefix, sc, len(files), sc))
	}
	return msgs
}

func classifyScope(slashPath string) string {
	parts := strings.Split(slashPath, "/")
	if len(parts) == 1 {
		return "raiz"
	}
	switch parts[0] {
	case "skills":
		if len(parts) >= 2 {
			return parts[1]
		}
		return "skills"
	case "internal", "cmd", "pkg":
		if len(parts) >= 2 {
			return "harness-" + parts[1]
		}
		return "harness-go"
	default:
		return parts[0]
	}
}
