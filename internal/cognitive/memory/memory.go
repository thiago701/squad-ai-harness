// Package memory implements the 4-layer cognitive memory architecture (M0 Working,
// M1 Episodic with surprise novelty detection, M2 Semantic SEKG, M3 Procedural)
// and enforces epistemic anti-hallucination quarantine rules (Fase 3).
package memory

import (
	"errors"
	"sync"
	"time"

	"github.com/thiago701/squad-ai-harness/pkg/contracts"
)

const (
	// SurpriseThreshold triggers long-term retention and Cultivator inspection when >= 0.86.
	SurpriseThreshold = 0.86
	// ColdStartEpisodes is the minimum number of historical episodes before surprise filtering activates.
	ColdStartEpisodes = 20
)

var (
	ErrUnverifiedPromotion = errors.New("memory: cannot promote HYPOTHESIS to VERIFIED without passing test oracle and gate PASS")
)

// Episode represents a task execution record in M1 Episodic Memory.
type Episode struct {
	RunID       string              `json:"run_id"`
	TaskSlug    string              `json:"task_slug"`
	Skills      []string            `json:"skills"`
	FilesTouched []string           `json:"files_touched,omitempty"`
	Outcome     string              `json:"outcome"` // "success", "failure", "partial"
	GateVerdict contracts.GateState `json:"gate_verdict"`
	TestPassed  bool                `json:"test_passed"`
	Surprise    float64             `json:"surprise"`
	Trust       contracts.TrustTier `json:"trust"`
	Timestamp   time.Time           `json:"ts"`
}

// WorkingState represents M0 Working Memory for the active session/task.
type WorkingState struct {
	TaskSlug    string                `json:"task_slug"`
	BudgetTier  contracts.ContextTier `json:"budget_tier"`
	MaxTokens   int                   `json:"max_tokens"`
	UsedTokens  int                   `json:"used_tokens"`
	ActiveNodes []string              `json:"active_nodes"`
}

// Store manages M0 Working Memory, M1 Episodic Memory, and Epistemic Quarantine promotion.
type Store struct {
	mu          sync.RWMutex
	working     WorkingState
	episodes    []Episode
	skillCounts map[string]int
}

// NewStore creates a multilayer memory store.
func NewStore() *Store {
	return &Store{
		skillCounts: make(map[string]int),
	}
}

// InitWorking initializes M0 Working Memory with strict context token budget enforcement.
func (s *Store) InitWorking(slug string, tier contracts.ContextTier) WorkingState {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.working = WorkingState{
		TaskSlug:   slug,
		BudgetTier: tier,
		MaxTokens:  contracts.ContextBudgetTokens(tier),
	}
	return s.working
}

// RecordEpisode appends an episode to M1, computing its surprise novelty score.
func (s *Store) RecordEpisode(ep Episode) Episode {
	s.mu.Lock()
	defer s.mu.Unlock()

	ep.Surprise = s.computeSurpriseLocked(ep.Skills)
	for _, sk := range ep.Skills {
		s.skillCounts[sk]++
	}
	if ep.Timestamp.IsZero() {
		ep.Timestamp = time.Now().UTC()
	}
	if ep.TestPassed && ep.GateVerdict == contracts.GatePass && ep.Outcome == "success" {
		ep.Trust = contracts.TrustVerified
	} else if ep.Outcome == "success" {
		ep.Trust = contracts.TrustObserved
	} else {
		ep.Trust = contracts.TrustHypothesis
	}

	s.episodes = append(s.episodes, ep)
	return ep
}

// PromoteToVerified enforces the anti-hallucination guardrail: a hypothesis or pattern can ONLY
// be promoted to VERIFIED if backed by a passing executable test oracle and GatePass verdict.
func PromoteToVerified(current contracts.TrustTier, testPassed bool, gateState contracts.GateState) (contracts.TrustTier, error) {
	if !testPassed || !gateState.Authorize() {
		return contracts.TrustHypothesis, ErrUnverifiedPromotion
	}
	return contracts.TrustVerified, nil
}

func (s *Store) computeSurpriseLocked(skills []string) float64 {
	total := len(s.episodes)
	if total < ColdStartEpisodes || len(skills) == 0 {
		return 1.0
	}
	unseen := 0
	for _, sk := range skills {
		if s.skillCounts[sk] == 0 {
			unseen++
		}
	}
	ratio := float64(unseen) / float64(len(skills))
	return 0.50 + 0.50*ratio
}
