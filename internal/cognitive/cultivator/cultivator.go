// Package cultivator implements the Phase 10 Continuous Evolution Engine in Go 1.24.3,
// detecting recurring verified patterns in the SEKG and validating skill/JEV evolution
// proposals against the held-out anti-regression oracle.
package cultivator

import (
	"errors"

	"github.com/thiago701/squad-ai-harness/internal/cognitive/memory"
	"github.com/thiago701/squad-ai-harness/pkg/contracts"
)

const (
	// MinVerifiedOccurrences is the minimum count of verified episodes required before proposing an evolution.
	MinVerifiedOccurrences = 3
)

var (
	ErrHeldOutRegression = errors.New("cultivator: proposal rejected by anti-regression oracle (held-out score below baseline)")
)

// EvolutionProposal represents a gated candidate improvement to a skill or JEV rule.
type EvolutionProposal struct {
	TargetSkill       string              `json:"target_skill"`
	VerifiedEpisodes  int                 `json:"verified_episodes"`
	BaselineRecall    float64             `json:"baseline_recall"`
	CandidateRecall   float64             `json:"candidate_recall"`
	FabricatedMetrics int                 `json:"fabricated_metrics"`
	Trust             contracts.TrustTier `json:"trust"`
	ApprovedForPR     bool                `json:"approved_for_pr"`
}

// HarvestCandidates scans M1 Episodic Memory for skills with >= 3 verified high-surprise episodes.
func HarvestCandidates(episodes []memory.Episode) []string {
	counts := make(map[string]int)
	for _, ep := range episodes {
		if ep.Trust != contracts.TrustVerified || !ep.TestPassed || ep.GateVerdict != contracts.GatePass {
			continue
		}
		for _, sk := range ep.Skills {
			counts[sk]++
		}
	}

	var ready []string
	for sk, c := range counts {
		if c >= MinVerifiedOccurrences {
			ready = append(ready, sk)
		}
	}
	return ready
}

// ValidateProposal enforces the strict anti-regression and anti-fabrication gate (evolution-gate).
func ValidateProposal(prop EvolutionProposal) (EvolutionProposal, error) {
	if prop.FabricatedMetrics > 0 {
		prop.ApprovedForPR = false
		return prop, errors.New("cultivator: zero-tolerance for fabricated metrics")
	}
	if prop.VerifiedEpisodes < MinVerifiedOccurrences {
		prop.ApprovedForPR = false
		return prop, errors.New("cultivator: insufficient verified episodes")
	}
	if prop.CandidateRecall < prop.BaselineRecall {
		prop.ApprovedForPR = false
		return prop, ErrHeldOutRegression
	}
	prop.Trust = contracts.TrustVerified
	prop.ApprovedForPR = true
	return prop, nil
}
