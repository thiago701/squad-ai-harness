package router

import (
	"math"
	"strings"
	"testing"

	"github.com/thiago701/squad-ai-harness/internal/catalog"
)

type syntheticIntakeAnswers struct {
	Question1Stack          string // "a) Go" | "b) Java" | "c) Rust" | "d) Python"
	Question2AWSSolution    string // "a) AWS Step Functions" | "b) AWS Lambda" | "c) AWS ECS" | "d) Decida por mim"
	Question3APIMode        string // "a) Nova API" | "b) Migracao de API existente"
	Question4ExpectedJSON   string // "a) API Nova JSON + URLs" | "b) Migracao confirmar v1 e gerar v2/v3"
	SourceReposProvided     bool
	ReuseExistingInfra      bool
	NeedsSagaCompensation   bool
	SustainedLongRunningRPS bool
}

type syntheticTrialOutcome struct {
	TrialIndex          int
	TranscriptClaimedOK bool
	HTTPStatus          int
	ExpectedHTTPStatus  int
	JSONContractMatchV1 bool
	JSONContractMatchV2 bool
	DynamicHeldOutMatch bool
	MutationKilled      bool
	ZeroSecurityBlocker bool
}

type syntheticLoopMetrics struct {
	ScenarioName       string
	ResolvedAWSTarget  string
	SuggestedURLs      []string
	LoopIteration      int
	TrialsCount        int
	SingleTrialSuccess float64
	PassAtK            float64
	PassHatK           float64
	MutationKillRate   float64
	Gate2Ready         bool
}

func resolveDecideForMeAWS(in syntheticIntakeAnswers) string {
	if !strings.HasPrefix(in.Question2AWSSolution, "d)") {
		return in.Question2AWSSolution
	}
	if in.NeedsSagaCompensation {
		return "AWS Step Functions Express + AWS Lambda (P1-Simplicidade: Saga/compensacao declarativa)"
	}
	if in.SustainedLongRunningRPS {
		return "AWS ECS Fargate Graviton arm64 (P2-Performance: carga continua sem cold start)"
	}
	return "AWS Lambda provided.al2023 arm64 + API Gateway HTTP (P1-Simplicidade + P3-CustoBaixo)"
}

func gradeTrialOutcome(t syntheticTrialOutcome, isMigration bool) bool {
	// Regra de ouro Anthropic: Grade the Outcome, not the Transcript claim!
	if t.HTTPStatus != t.ExpectedHTTPStatus {
		return false
	}
	if !t.JSONContractMatchV1 || !t.DynamicHeldOutMatch || !t.ZeroSecurityBlocker {
		return false
	}
	if isMigration && (!t.JSONContractMatchV2 || !t.MutationKilled) {
		return false
	}
	return true
}

func computeAgentEvalMetrics(
	name string,
	in syntheticIntakeAnswers,
	loopIter int,
	trials []syntheticTrialOutcome,
	urls []string,
) syntheticLoopMetrics {
	isMig := strings.HasPrefix(in.Question3APIMode, "b)")
	k := len(trials)
	passed := 0
	mutKilled := 0
	for _, tr := range trials {
		if gradeTrialOutcome(tr, isMig) {
			passed++
		}
		if tr.MutationKilled {
			mutKilled++
		}
	}
	p := float64(passed) / float64(k)
	passAtK := 1.0 - math.Pow(1.0-p, float64(k))
	passHatK := math.Pow(p, float64(k))
	mutRate := float64(mutKilled) / float64(k)

	gateOK := passHatK >= 0.999 && (!isMig || (in.SourceReposProvided && mutRate >= 0.999))
	return syntheticLoopMetrics{
		ScenarioName:       name,
		ResolvedAWSTarget:  resolveDecideForMeAWS(in),
		SuggestedURLs:      urls,
		LoopIteration:      loopIter,
		TrialsCount:        k,
		SingleTrialSuccess: p,
		PassAtK:            passAtK,
		PassHatK:           passHatK,
		MutationKillRate:   mutRate,
		Gate2Ready:         gateOK,
	}
}

func TestEvalAgenticAPIRoutingAndSquadVariations(t *testing.T) {
	root := repoRoot(t)
	cat, err := catalog.Load(root)
	if err != nil {
		t.Fatalf("catalog.Load failed: %v", err)
	}
	rep := cat.Validate()
	if rep.RegistryDrift || len(rep.Errors) > 0 {
		t.Fatalf("catalog.Validate reported errors/drift: %+v", rep)
	}

	r := NewHybridRouter(cat)

	prompts := []string{
		"Squad ai, prepare a equipe. Quero migrar uma api usando o eval.",
		"Squad ai, prepare a equipe. Quero migrar uma api usando evals.",
		"Squad ai, prepare a equipe. Quero criar uma nova api usando eval-agentic.",
		"Quero migrar uma API legada para Go na AWS Lambda usando eval-agentic-api",
		"Desenvolver nova API em Rust com Step Functions orientada a evals (Demystifying Evals)",
	}

	for _, q := range prompts {
		matches := r.Route(q, 5)
		if len(matches) == 0 {
			t.Fatalf("Route(%q) returned 0 matches", q)
		}
		if matches[0].SkillName != "eval-agentic-api" {
			t.Fatalf("Route(%q) top-1 = %q (score=%.2f), want \"eval-agentic-api\" (full=%+v)",
				q, matches[0].SkillName, matches[0].Score, matches)
		}
	}
}

func TestEvalAgenticAPISyntheticSimulationLoops(t *testing.T) {
	// Cenario 1: Migracao de API Legada (1a Go + 2b Lambda + 3b Migracao + 4b Contrato v1 + v2)
	scen1Intake := syntheticIntakeAnswers{
		Question1Stack:       "a) Go",
		Question2AWSSolution: "b) AWS Lambda",
		Question3APIMode:     "b) Migracao de API existente",
		Question4ExpectedJSON: "b) Confirmar URLs legadas v1 e gerar v2 com melhorias",
		SourceReposProvided:  false, // Loop 1 bloqueia no GATE de repositorios!
		ReuseExistingInfra:   true,
	}
	loop1Trials := makeUniformTrials(5, 200, 200, false, true, true, true, true)
	m1Loop1 := computeAgentEvalMetrics("Mig-Go-Lambda-v1-v2", scen1Intake, 1, loop1Trials, []string{"GET /v1/pedidos/{id}", "GET /v2/orders/{id}"})
	if m1Loop1.Gate2Ready {
		t.Fatalf("Loop 1 should block when SourceReposProvided=false and v1 JSON drifts")
	}

	// Loop 2: Repositorios informados no Gate, mas 1 trial de 5 falha (p=0.80 -> pass@5=0.99968 vs pass^5=0.32768)
	scen1Intake.SourceReposProvided = true
	loop2Trials := makeUniformTrials(5, 200, 200, true, true, true, true, true)
	loop2Trials[4].JSONContractMatchV1 = false
	m1Loop2 := computeAgentEvalMetrics("Mig-Go-Lambda-v1-v2", scen1Intake, 2, loop2Trials, []string{"GET /v1/pedidos/{id}", "GET /v2/orders/{id}"})
	if m1Loop2.PassAtK < 0.99 || m1Loop2.PassHatK > 0.35 || m1Loop2.Gate2Ready {
		t.Fatalf("Loop 2 must expose pass@5 vs pass^5 gap (pass@5=%.4f, pass^5=%.4f)", m1Loop2.PassAtK, m1Loop2.PassHatK)
	}

	// Loop 3: Auto-correcao do Adapter v1 -> pass^5 = 1.00 e Gate2Ready = true
	loop3Trials := makeUniformTrials(5, 200, 200, true, true, true, true, true)
	m1Loop3 := computeAgentEvalMetrics("Mig-Go-Lambda-v1-v2", scen1Intake, 3, loop3Trials, []string{"GET /v1/pedidos/{id}", "GET /v2/orders/{id}"})
	if !m1Loop3.Gate2Ready || m1Loop3.PassHatK != 1.0 || m1Loop3.MutationKillRate != 1.0 {
		t.Fatalf("Loop 3 failed convergence: %+v", m1Loop3)
	}

	// Cenario 2: Nova API Java 25 + 2d "Decida por mim" (Saga -> Step Functions) + Anti-Goodhart
	scen2Intake := syntheticIntakeAnswers{
		Question1Stack:        "b) Java",
		Question2AWSSolution:  "d) Decida por mim",
		Question3APIMode:      "a) Nova API",
		Question4ExpectedJSON: "a) JSON colado + sugestao de URLs RESTful",
		NeedsSagaCompensation: true,
	}
	goodhartTrials := makeUniformTrials(5, 201, 201, true, true, false, true, true) // Held-out falha (JSON hardcoded)
	m2Loop1 := computeAgentEvalMetrics("New-Java25-DecideForMe-Saga", scen2Intake, 1, goodhartTrials, []string{"POST /v1/checkouts", "GET /v1/checkouts/{id}"})
	if m2Loop1.Gate2Ready || !strings.Contains(m2Loop1.ResolvedAWSTarget, "Step Functions") {
		t.Fatalf("Scenario 2 Loop 1 must catch Goodhart hardcoded JSON and pick Step Functions: %+v", m2Loop1)
	}
	m2Loop2 := computeAgentEvalMetrics("New-Java25-DecideForMe-Saga", scen2Intake, 2, makeUniformTrials(5, 201, 201, true, true, true, true, true), []string{"POST /v1/checkouts", "GET /v1/checkouts/{id}"})
	if !m2Loop2.Gate2Ready || m2Loop2.PassHatK != 1.0 {
		t.Fatalf("Scenario 2 Loop 2 failed convergence: %+v", m2Loop2)
	}

	// Cenario 3: Migracao Rust + ECS Fargate + Outcome vs Transcript Grading
	scen3Intake := syntheticIntakeAnswers{
		Question1Stack:          "c) Rust",
		Question2AWSSolution:    "d) Decida por mim",
		Question3APIMode:        "b) Migracao de API existente",
		Question4ExpectedJSON:   "b) Confirmar v1 e gerar v2/v3",
		SourceReposProvided:     true,
		ReuseExistingInfra:      true,
		SustainedLongRunningRPS: true,
	}
	transcriptLieTrials := makeUniformTrials(5, 500, 200, true, true, true, true, true) // Transcript diz OK, mas Outcome HTTP=500
	m3Loop1 := computeAgentEvalMetrics("Mig-Rust-ECS-v1-v3", scen3Intake, 1, transcriptLieTrials, []string{"POST /v1/telemetry", "POST /v2/telemetry", "POST /v3/telemetry"})
	if m3Loop1.Gate2Ready || !strings.Contains(m3Loop1.ResolvedAWSTarget, "ECS Fargate") {
		t.Fatalf("Scenario 3 Loop 1 must grade Outcome (HTTP 500) over Transcript claim and select ECS Fargate: %+v", m3Loop1)
	}
	m3Loop2 := computeAgentEvalMetrics("Mig-Rust-ECS-v1-v3", scen3Intake, 2, makeUniformTrials(5, 200, 200, true, true, true, true, true), []string{"POST /v1/telemetry", "POST /v2/telemetry", "POST /v3/telemetry"})
	if !m3Loop2.Gate2Ready || m3Loop2.PassHatK != 1.0 {
		t.Fatalf("Scenario 3 Loop 2 failed convergence: %+v", m3Loop2)
	}

	// Cenario 4: Nova API Python 3.14 + AWS Lambda + Recomendacao do Arquiteto
	scen4Intake := syntheticIntakeAnswers{
		Question1Stack:       "d) Python",
		Question2AWSSolution: "d) Decida por mim",
		Question3APIMode:     "a) Nova API",
		Question4ExpectedJSON: "a) Recomendacao do agente de arquitetura",
	}
	m4 := computeAgentEvalMetrics("New-Python314-Lambda", scen4Intake, 1, makeUniformTrials(5, 200, 200, true, true, true, true, true), []string{"POST /v1/predictions", "GET /v1/predictions/{id}"})
	if !m4.Gate2Ready || !strings.Contains(m4.ResolvedAWSTarget, "AWS Lambda") {
		t.Fatalf("Scenario 4 failed convergence or AWS recommendation: %+v", m4)
	}
}

func makeUniformTrials(
	k int,
	httpStatus int,
	expectedStatus int,
	matchV1 bool,
	matchV2 bool,
	heldOutOK bool,
	mutKilled bool,
	secOK bool,
) []syntheticTrialOutcome {
	out := make([]syntheticTrialOutcome, k)
	for i := 0; i < k; i++ {
		out[i] = syntheticTrialOutcome{
			TrialIndex:          i + 1,
			TranscriptClaimedOK: true,
			HTTPStatus:          httpStatus,
			ExpectedHTTPStatus:  expectedStatus,
			JSONContractMatchV1: matchV1,
			JSONContractMatchV2: matchV2,
			DynamicHeldOutMatch: heldOutOK,
			MutationKilled:      mutKilled,
			ZeroSecurityBlocker: secOK,
		}
	}
	return out
}
