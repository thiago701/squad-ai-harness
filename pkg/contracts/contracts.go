// Package contracts defines the canonical types, version identity, gate verdicts,
// epistemic trust tiers, and JEV typed decision contracts for SquadAI Harness v0.8.0.
package contracts

import "time"

const (
	// ProductName is the official product name (Addendum 02).
	ProductName = "SquadAI Harness"
	// TechnicalName is the canonical repository and binary identifier (Addendum 02).
	TechnicalName = "squad-ai-harness"
	// Version is the official release version (Addendum 01).
	Version = "0.8.0"
	// FullIdentity is the complete versioned product string.
	FullIdentity = "SquadAI Harness v0.8.0"
	// GoToolchainTarget is the locked Go toolchain version from GATE 1 (ADR-020).
	GoToolchainTarget = "go1.24.3"
	// TrustedOrigin is the immutable provenance key across all canonical skills.
	TrustedOrigin = "squad-ai"
	// AuthorName is the creator and principal author of SquadAI Harness.
	AuthorName = "Thiago Gonçalo"
	// AuthorEmail is the official contact email of the author.
	AuthorEmail = "thiago701@gmail.com"
	// CreatedAt is the canonical creation date of SquadAI Harness.
	CreatedAt = "30/10/2026"
	// ExclusiveLanguage enforces the Go-only source code policy for the harness runtime.
	ExclusiveLanguage = "Go (Golang 1.24.3+, CGO_ENABLED=0)"
)

// GateState represents the canonical delivery gate verdict (AGENTS.md §9).
type GateState string

const (
	GatePass         GateState = "PASS"
	GateBlocked      GateState = "BLOCKED"
	GateInconclusive GateState = "INCONCLUSIVE"
	GateStale        GateState = "STALE"
)

// Precedence returns the numeric severity of a GateState (higher wins when aggregating).
// Order: BLOCKED (4) > STALE (3) > INCONCLUSIVE (2) > PASS (1).
func (s GateState) Precedence() int {
	switch s {
	case GateBlocked:
		return 4
	case GateStale:
		return 3
	case GateInconclusive:
		return 2
	case GatePass:
		return 1
	default:
		return 3
	}
}

// Authorize returns true exclusively when the state is PASS.
func (s GateState) Authorize() bool {
	return s == GatePass
}

// MergeGateStates aggregates multiple gate states using strict fail-closed precedence.
func MergeGateStates(states ...GateState) GateState {
	if len(states) == 0 {
		return GateInconclusive
	}
	worst := GatePass
	for _, st := range states {
		if st.Precedence() > worst.Precedence() {
			worst = st
		}
	}
	return worst
}

// TrustTier separates verified knowledge from observational data and quarantined hypotheses.
type TrustTier string

const (
	TrustVerified   TrustTier = "VERIFIED"
	TrustObserved   TrustTier = "OBSERVED"
	TrustHypothesis TrustTier = "HYPOTHESIS"
)

// ProvenanceKind classifies the epistemic origin of a metric or fact.
type ProvenanceKind string

const (
	ProvenanceMeasured  ProvenanceKind = "MEASURED"
	ProvenanceDerived   ProvenanceKind = "DERIVED"
	ProvenanceHeuristic ProvenanceKind = "HEURISTIC"
	ProvenanceAsserted  ProvenanceKind = "ASSERTED"
)

// ContextTier defines the token budget ceiling by task size.
type ContextTier string

const (
	Ctx0    ContextTier = "CTX-0"
	Ctx1    ContextTier = "CTX-1"
	Ctx2    ContextTier = "CTX-2"
	Ctx3    ContextTier = "CTX-3"
	CtxFull ContextTier = "CTX-FULL"
)

// ContextBudgetTokens returns the maximum token budget for the given tier.
func ContextBudgetTokens(tier ContextTier) int {
	switch tier {
	case Ctx0:
		return 800
	case Ctx1:
		return 2000
	case Ctx2:
		return 5000
	case Ctx3:
		return 12000
	case CtxFull:
		return 25000
	default:
		return 5000
	}
}

// JevDecision represents a typed zero-token deterministic decision (Choice/Score/Noul).
type JevDecision struct {
	Specialist  string    `json:"specialist"`
	Choice      string    `json:"choice"`
	Score       float64   `json:"score"`
	Confidence  float64   `json:"confidence"`
	Noul        bool      `json:"noul,omitempty"`
	Evidence    []string  `json:"evidence,omitempty"`
	DurationUs  int64     `json:"duration_us"`
	GeneratedAt time.Time `json:"generated_at"`
}
