// Package evallab implements the Agentic Software Engineering Evaluation Lab,
// the 7 evolved modules of eval-agentic-api v2.0 (AgenticEvaluationEngine,
// DecisionTraceAnalyzer, PredictiveFailureAnalyzer, AutonomousRecoveryEvaluator,
// QualityEvidenceCollector, RegressionBenchmarkSuite, ResourceAwareEvaluation),
// and the reproducible multi-experiment benchmark suite (Experiments A, B, C, D, E).
package evallab

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"time"
)

// DeliveryVerdict represents the 4 formal outcome states required by Criterion 11 (§15).
type DeliveryVerdict string

const (
	VerdictProvenSuccess  DeliveryVerdict = "PROVEN_SUCCESS"
	VerdictPartialSuccess DeliveryVerdict = "PARTIAL_SUCCESS"
	VerdictFailed         DeliveryVerdict = "FAILED"
	VerdictInconclusive   DeliveryVerdict = "INCONCLUSIVE"
)

// GateKind distinguishes consultative questions from mandatory blocking human gates (§8).
type GateKind string

const (
	GateConsultive GateKind = "CONSULTIVE"
	GateBlocking   GateKind = "BLOCKING"
)

// AgentActionChoice represents the autonomous decision action taken when facing uncertainty (§5).
type AgentActionChoice string

const (
	ActionContinue        AgentActionChoice = "CONTINUE"
	ActionFixAutonomous   AgentActionChoice = "FIX_AUTONOMOUS"
	ActionReplanDAG       AgentActionChoice = "REPLAN_DAG"
	ActionEscalateToHuman AgentActionChoice = "ESCALATE_TO_HUMAN_GATE"
)

// FailureCategory classifies defects and gaps into the 8 canonical root-cause classes (§11).
type FailureCategory string

const (
	FailImplementation  FailureCategory = "1_IMPLEMENTATION_DEFECT"
	FailArchitectural   FailureCategory = "2_ARCHITECTURAL_FAILURE"
	FailPlanning        FailureCategory = "3_PLANNING_FAILURE"
	FailCognitive       FailureCategory = "4_COGNITIVE_DECISION_FAILURE"
	FailIntegration     FailureCategory = "5_INTEGRATION_FAILURE"
	FailPerformance     FailureCategory = "6_PERFORMANCE_RESOURCE_ISSUE"
	FailSecurity        FailureCategory = "7_SECURITY_FAILURE"
	FailEvaluationFlaw  FailureCategory = "8_EVALUATION_DEFICIENCY"
)

// WorkspaceProjectEntry catalogs a real Java or Python project discovered in the workspace (§3).
type WorkspaceProjectEntry struct {
	ProjectID            string   `json:"project_id"`
	Name                 string   `json:"name"`
	RelativePath         string   `json:"relative_path"`
	Language             string   `json:"language"` // "Python" | "Java"
	FrameworkStack       []string `json:"framework_stack"`
	ComplexityTier       string   `json:"complexity_tier"` // "SIMPLE" | "INTERMEDIATE" | "COMPLEX"
	ArchitectureStyle    string   `json:"architecture_style"`
	TestSuiteStatus      string   `json:"test_suite_status"`
	ExperimentalViability string  `json:"experimental_viability"`
	SelectedForSample    bool     `json:"selected_for_sample"`
}

// IntermediateGateQuestion represents a prioritized, non-redundant question or gate (§8).
type IntermediateGateQuestion struct {
	GateID       string   `json:"gate_id"`
	PriorityRank int      `json:"priority_rank"`
	Kind         GateKind `json:"kind"`
	Question     string   `json:"question"`
	Options      []string `json:"options,omitempty"`
	Selected     string   `json:"selected"`
	Rationale    string   `json:"rationale"`
	ApprovedBy   string   `json:"approved_by"`
}

// DecisionTraceRecord captures an auditable intermediate decision without exposing private CoT (§5, §10).
type DecisionTraceRecord struct {
	DecisionID       string            `json:"decision_id"`
	Stage            string            `json:"stage"`
	AgentSpecialist  string            `json:"agent_specialist"`
	ContextSummary   string            `json:"context_summary"`
	OptionsEvaluated []string          `json:"options_evaluated"`
	ChosenOption     string            `json:"chosen_option"`
	ActionChoice     AgentActionChoice `json:"action_choice"`
	Confidence       float64           `json:"confidence"`
	Evidence         []string          `json:"evidence"`
	TechnicallySound bool              `json:"technically_sound"`
	DurationUs       int64             `json:"duration_us"`
}

// PredictiveRiskRecord differentiates pre-execution risk anticipation from post-hoc error detection (§7).
type PredictiveRiskRecord struct {
	RiskID                string          `json:"risk_id"`
	Category              FailureCategory `json:"category"`
	TargetComponent       string          `json:"target_component"`
	PredictedBeforeExec   bool            `json:"predicted_before_exec"` // true = prediction, false = post-hoc detection
	CalibratedProbability float64         `json:"calibrated_probability"`
	ImpactSeverity        string          `json:"impact_severity"` // "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
	Evidence              string          `json:"evidence"`
	PreventiveAction      string          `json:"preventive_action"`
	FallbackPlan          string          `json:"fallback_plan"`
	AutoResolvedBySquad   bool            `json:"auto_resolved_by_squad"`
	GroundTruthOccurred   bool            `json:"ground_truth_occurred"`
}

// CheckpointRecord stores an idempotent execution checkpoint for Experiment E (§4, §8).
type CheckpointRecord struct {
	CheckpointID      string   `json:"checkpoint_id"`
	StageIndex        int      `json:"stage_index"`
	StageName         string   `json:"stage_name"`
	StateDigestSHA256 string   `json:"state_digest_sha256"`
	IdempotencyKeys   []string `json:"idempotency_keys"`
	TimestampUnix     int64    `json:"timestamp_unix"`
	Resumable         bool     `json:"resumable"`
}

// RecoveryAttemptRecord tracks autonomous fault diagnosis and recovery without duplicate side effects (§4, §11).
type RecoveryAttemptRecord struct {
	IncidentID           string          `json:"incident_id"`
	InterruptedStage     string          `json:"interrupted_stage"`
	InjectedFault        string          `json:"injected_fault"`
	Category             FailureCategory `json:"category"`
	RootCause            string          `json:"root_cause"`
	RestoredCheckpointID string          `json:"restored_checkpoint_id"`
	DuplicateSideEffects int             `json:"duplicate_side_effects"`
	TimeToDetectUs       int64           `json:"time_to_detect_us"`
	TimeToRecoverUs      int64           `json:"time_to_recover_us"`
	RecoveredAutonomous  bool            `json:"recovered_autonomous"`
}

// QualityEvidenceBundle collects deterministic verification evidence across all 8 pipeline stages (§9, §10).
type QualityEvidenceBundle struct {
	CompiledCleanly          bool    `json:"compiled_cleanly"`
	UnitTestsPassed          int     `json:"unit_tests_passed"`
	IntegrationTestsPassed   int     `json:"integration_tests_passed"`
	ContractTestsPassed      int     `json:"contract_tests_passed"`
	E2ETestsPassed           int     `json:"e2e_tests_passed"`
	DifferentialCasesMatched int     `json:"differential_cases_matched"`
	DifferentialCasesTotal   int     `json:"differential_cases_total"`
	MutationScore            float64 `json:"mutation_score"`
	MaxCyclomaticComplexity  int     `json:"max_cyclomatic_complexity"`
	MaxIndentationDepth      int     `json:"max_indentation_depth"`
	SecurityCriticalHigh     int     `json:"security_critical_high"`
	LogsSecretLeakCount      int     `json:"logs_secret_leak_count"`
	BackwardCompatibleV1     bool    `json:"backward_compatible_v1"`
}

// CognitiveScorecard10D holds the 10 cognitive dimensions and 12 formal metrics (§5).
type CognitiveScorecard10D struct {
	// 10 Cognitive Dimensions [0.0 .. 1.0]
	Dim1Interpretation float64 `json:"dim1_interpretation"`
	Dim2Planning       float64 `json:"dim2_planning"`
	Dim3Autonomy       float64 `json:"dim3_autonomy"`
	Dim4Consistency    float64 `json:"dim4_consistency"`
	Dim5Precision      float64 `json:"dim5_precision"`
	Dim6Anticipation   float64 `json:"dim6_anticipation"`
	Dim7Recovery       float64 `json:"dim7_recovery"`
	Dim8Collaboration  float64 `json:"dim8_collaboration"`
	Dim9Quality        float64 `json:"dim9_quality"`
	Dim10Efficiency    float64 `json:"dim10_efficiency"`

	// 12 Specific Quantitative Metrics (§5)
	AutonomousTaskSuccessRate       float64 `json:"autonomous_task_success_rate"`
	FirstPassSuccessRate            float64 `json:"first_pass_success_rate"`
	DecisionAccuracy                float64 `json:"decision_accuracy"`
	DecisionConsistencyPassHatK     float64 `json:"decision_consistency_pass_hat_k"`
	RecoverySuccessRate             float64 `json:"recovery_success_rate"`
	HumanInterventionRate           float64 `json:"human_intervention_rate"`
	DefectEscapeRate                float64 `json:"defect_escape_rate"`
	PredictiveRiskRecall            float64 `json:"predictive_risk_recall"`
	PredictivePrecision             float64 `json:"predictive_precision"`
	TimeToDetectMeanUs              float64 `json:"time_to_detect_mean_us"`
	TimeToRecoverMeanUs             float64 `json:"time_to_recover_mean_us"`
	ReworkRate                      float64 `json:"rework_rate"`
	TokenCostPerSuccessfulDelivery  float64 `json:"token_cost_per_successful_delivery"`
}

// AgenticDeliveryContract is the canonical versioned JSON contract for E2E delivery (§8).
type AgenticDeliveryContract struct {
	ExecutionID               string                     `json:"execution_id"`
	ContractSchemaVersion     string                     `json:"contract_schema_version"`
	CriteriaSealSHA256        string                     `json:"criteria_seal_sha256"`
	CriteriaTamperDetected    bool                       `json:"criteria_tamper_detected"`
	UserStory                 string                     `json:"user_story"`
	TargetStack               string                     `json:"target_stack"`
	TargetAWSSolution         string                     `json:"target_aws_solution"`
	OperationMode             string                     `json:"operation_mode"` // "GREENFIELD" | "MIGRATION"
	SourceRepositories        []string                   `json:"source_repositories,omitempty"`
	ReuseExistingInfra        bool                       `json:"reuse_existing_infra"`
	FunctionalRequirements    []string                   `json:"functional_requirements"`
	NonFunctionalRequirements []string                   `json:"non_functional_requirements"`
	AcceptanceCriteria        []string                   `json:"acceptance_criteria"`
	Gates                     []IntermediateGateQuestion `json:"gates"`
	ApprovedArchitecture      map[string]string          `json:"approved_architecture"`
	DependencyDAGCriticalPath []string                   `json:"dependency_dag_critical_path"`
	Decisions                 []DecisionTraceRecord      `json:"decisions"`
	PredictiveRisks           []PredictiveRiskRecord     `json:"predictive_risks"`
	Checkpoints               []CheckpointRecord         `json:"checkpoints"`
	Recoveries                []RecoveryAttemptRecord    `json:"recoveries"`
	QualityEvidence           QualityEvidenceBundle      `json:"quality_evidence"`
	CognitiveScorecard        CognitiveScorecard10D      `json:"cognitive_scorecard"`
	DeliveredArtifacts        []string                   `json:"delivered_artifacts"`
	FinalVerdict              DeliveryVerdict            `json:"final_verdict"`
	PendingCriteria           []string                   `json:"pending_criteria,omitempty"`
	GeneratedAtUTC            string                     `json:"generated_at_utc"`
}

// SealAcceptanceCriteria computes an immutable SHA-256 seal over the acceptance criteria
// so the evaluation engine can detect any attempt by an evaluated agent to weaken the rubric (§10, §16).
func SealAcceptanceCriteria(criteria []string) string {
	raw, _ := json.Marshal(criteria)
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:])
}

// VerifyCriteriaSeal checks that the active criteria match the immutable pre-execution seal.
func VerifyCriteriaSeal(criteria []string, expectedSeal string) bool {
	return SealAcceptanceCriteria(criteria) == expectedSeal
}

// FormatTimestampUTC returns an ISO-8601 UTC timestamp string.
func FormatTimestampUTC() string {
	return time.Now().UTC().Format(time.RFC3339)
}
