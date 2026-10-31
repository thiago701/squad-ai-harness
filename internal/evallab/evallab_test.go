package evallab

import (
	"encoding/json"
	"errors"
	"path/filepath"
	"runtime"
	"strings"
	"testing"

	"github.com/thiago701/squad-ai-harness/internal/catalog"
)

func TestWorkspaceProjectDiscoveryAndClassification(t *testing.T) {
	projects := DiscoverWorkspaceProjects()
	if len(projects) < 6 {
		t.Fatalf("expected at least 6 real Java/Python projects discovered, got %d", len(projects))
	}
	pyCount := 0
	javaCount := 0
	selectedCount := 0
	for _, p := range projects {
		if p.Language == "Python" {
			pyCount++
		}
		if p.Language == "Java" {
			javaCount++
		}
		if p.SelectedForSample {
			selectedCount++
		}
	}
	if pyCount < 3 || javaCount < 3 || selectedCount < 6 {
		t.Fatalf("expected representative sample across Python (%d) and Java (%d), selected=%d", pyCount, javaCount, selectedCount)
	}
}

func TestExperimentsAAndBDifferentialMigrations(t *testing.T) {
	// Experimento A1: carteira_saude_ai (Python -> Go Simple)
	outCrit := RunExpAPythonToGoSimple(ExamTriageInput{PatientID: "P1", GlucoseMgDL: 220, SystolicBP: 130, DiastolicBP: 80, HemoglobinGDL: 13.5})
	if outCrit.RiskLevel != "HIGH_ALERT" || !outCrit.RequiresFollowUp || outCrit.AlertCode != "ALT-CRIT-01" {
		t.Fatalf("Exp A1 HIGH_ALERT mismatch: %+v", outCrit)
	}
	outWarn := RunExpAPythonToGoSimple(ExamTriageInput{PatientID: "P2", GlucoseMgDL: 135, SystolicBP: 120, DiastolicBP: 80, HemoglobinGDL: 13.5})
	if outWarn.RiskLevel != "BORDERLINE" || outWarn.AlertCode != "ALT-WARN-02" {
		t.Fatalf("Exp A1 BORDERLINE mismatch: %+v", outWarn)
	}
	outNorm := RunExpAPythonToGoSimple(ExamTriageInput{PatientID: "P3", GlucoseMgDL: 92, SystolicBP: 118, DiastolicBP: 76, HemoglobinGDL: 14.1})
	if outNorm.RiskLevel != "NORMAL" || outNorm.RequiresFollowUp {
		t.Fatalf("Exp A1 NORMAL mismatch: %+v", outNorm)
	}

	// Experimento A2: sistema-circuito-palestras (Python -> Go Intermediate)
	slotConflict := RunExpAPythonToGoIntermediate(LectureSlotInput{
		TenantID: "FEPB", SpeakerID: "SPK-01", InstitutionID: "INST-01",
		StartEpochMin: 615, EndEpochMin: 675, ExistingStart: 540, ExistingEnd: 600, // 15 min gap < 30 min buffer
	})
	if slotConflict.Approved || slotConflict.HTTPStatus != 409 {
		t.Fatalf("Exp A2 expected 409 conflict when travel buffer < 30 min: %+v", slotConflict)
	}
	slotOK := RunExpAPythonToGoIntermediate(LectureSlotInput{
		TenantID: "FEPB", SpeakerID: "SPK-01", InstitutionID: "INST-01",
		StartEpochMin: 640, EndEpochMin: 700, ExistingStart: 540, ExistingEnd: 600, // 40 min gap >= 30 min buffer
	})
	if !slotOK.Approved || slotOK.HTTPStatus != 201 || slotOK.SlotTokenHash == "" {
		t.Fatalf("Exp A2 expected 201 approved: %+v", slotOK)
	}

	// Experimento A3: Copiloto Acolhe (Python -> Go Complex Concurrent + LGPD Masking)
	acolheOut := RunExpAPythonToGoComplex([]AcolheTriageRecord{
		{WorkerCPF: "123.456.789-01", SectorCode: "LINHA-A", FatigueScore: 70, ErgonomicAlerts: 2, ShiftHours: 10},
		{WorkerCPF: "987.654.321-09", SectorCode: "LINHA-B", FatigueScore: 25, ErgonomicAlerts: 0, ShiftHours: 8},
	})
	if len(acolheOut) != 2 || acolheOut[0].MaskedCPF != "***.456.789-**" || acolheOut[0].PriorityTier != "P1_IMMEDIATE" {
		t.Fatalf("Exp A3 LGPD masking or priority calculation failed: %+v", acolheOut)
	}

	// Experimento B1: inotas-lambda-operacoes-motivos (Java 25 -> Go Simple Dual-Contract v1/v2)
	inotasOut := RunExpBJavaToGoSimple(InotasReasonInput{
		TenantCode: "itau", OperationKind: "devolucao", ReasonCode: "div-07", AmountCents: 14990,
	})
	if inotasOut.LegacyV1ValorStr != "149.90" || inotasOut.ModernV2Cents != 14990 || !inotasOut.Allowed {
		t.Fatalf("Exp B1 Dual-Contract v1/v2 parity failed: %+v", inotasOut)
	}

	// Experimento B2: atendimento/service Fale Conosco (Java 25 -> Go Intermediate SLA + Outbox)
	slaOut := RunExpBJavaToGoIntermediate(AtendimentoSLAInput{
		TicketID: "TCK-900", CustomerSegment: "EMPRESAS", Severity: 1, OpenedDayOfWeek: 6, // Saturday
	})
	if slaOut.TargetBusinessHours != 26 || slaOut.EscalationQueue != "QUEUE_CRITICAL_N3" || !strings.HasPrefix(slaOut.OutboxEventID, "OBX-") {
		t.Fatalf("Exp B2 SLA or Outbox failed: %+v", slaOut)
	}

	// Experimento B3: fepb-core / inotas-seed (Java 25 -> Go Complex Exact Cents Settlement)
	splitOut := RunExpBJavaToGoComplex(SplitSettlementInput{
		TransactionID: "TX-777", TotalAmountCents: 100003, PlatformFeeBps: 250, InstitutionShares: []int{33, 33, 34},
	})
	if !splitOut.InvariantBalanced || (splitOut.PlatformFeeCents+splitOut.NetDistributed) != 100003 {
		t.Fatalf("Exp B3 penny conservation invariant broken: %+v", splitOut)
	}
}

func TestExperimentCGreenfieldServerlessProduct(t *testing.T) {
	eng := NewOrderFulfillmentServerlessEngine()

	// 1. Reject BOLA cross-tenant attack (HTTP 403)
	bolaResp := eng.HandleCreateOrder(ServerlessOrderRequest{
		RequestID: "R-BOLA", CallerTenantID: "TENANT-A", ResourceTenantID: "TENANT-B",
		JWTValid: true, IdempotencyKey: "K1", OrderID: "O-1", SKU: "SKU-GPU-RTX3060", Quantity: 1, UnitPriceCents: 1000,
	})
	if bolaResp.HTTPStatus != 403 || bolaResp.ErrorCode != "BOLA_TENANT_MISMATCH" {
		t.Fatalf("expected 403 BOLA rejection, got %+v", bolaResp)
	}

	// 2. Nominal Order Confirmation + Idempotent Replay
	nomReq := ServerlessOrderRequest{
		RequestID: "R-NOM", CallerTenantID: "TENANT-A", ResourceTenantID: "TENANT-A",
		JWTValid: true, IdempotencyKey: "K-NOM-1", OrderID: "O-100", SKU: "SKU-GPU-RTX3060", Quantity: 2, UnitPriceCents: 250000,
	}
	nomResp := eng.HandleCreateOrder(nomReq)
	if nomResp.HTTPStatus != 201 || nomResp.OrderState != "CONFIRMED" || eng.GetAvailableStock("SKU-GPU-RTX3060") != 48 {
		t.Fatalf("nominal order failed: %+v (stock=%d)", nomResp, eng.GetAvailableStock("SKU-GPU-RTX3060"))
	}
	replayResp := eng.HandleCreateOrder(nomReq)
	if !replayResp.IdempotentReplay || eng.GetAvailableStock("SKU-GPU-RTX3060") != 48 {
		t.Fatalf("idempotent replay deducted stock twice! stock=%d", eng.GetAvailableStock("SKU-GPU-RTX3060"))
	}

	// 3. Payment Gateway Failure triggers Step Functions Saga Compensation (restores stock back to 48)
	failResp := eng.HandleCreateOrder(ServerlessOrderRequest{
		RequestID: "R-FAIL", CallerTenantID: "TENANT-A", ResourceTenantID: "TENANT-A",
		JWTValid: true, IdempotencyKey: "K-FAIL-1", OrderID: "O-101", SKU: "SKU-GPU-RTX3060", Quantity: 5, UnitPriceCents: 250000,
		SimulatePaymentErr: true,
	})
	if failResp.HTTPStatus != 502 || failResp.OrderState != "COMPENSATED_CANCELLED" || eng.GetAvailableStock("SKU-GPU-RTX3060") != 48 {
		t.Fatalf("Saga compensation failed to restore stock to 48: resp=%+v stock=%d", failResp, eng.GetAvailableStock("SKU-GPU-RTX3060"))
	}
}

func TestCriteriaSealAntiTamperingAndVerdictStates(t *testing.T) {
	orig := []string{"CA-1: pass^5 == 1.00", "CA-2: zero BOLA vulnerabilities"}
	seal := SealAcceptanceCriteria(orig)
	if !VerifyCriteriaSeal(orig, seal) {
		t.Fatal("expected unmodified criteria to pass seal verification")
	}
	tampered := []string{"CA-1: pass^5 >= 0.50", "CA-2: zero BOLA vulnerabilities"}
	if VerifyCriteriaSeal(tampered, seal) {
		t.Fatal("expected tampered criteria to be rejected by SHA-256 seal")
	}
}

func TestAdversarialCognitiveSuiteAndDecisionTrace(t *testing.T) {
	cases := RunAdversarialCognitiveSuite()
	if len(cases) != 6 {
		t.Fatalf("expected 6 adversarial cognitive cases, got %d", len(cases))
	}
	for _, c := range cases {
		if !c.EvolvedPassed || c.ChosenByEvolved != c.CorrectOption || c.ActionByEvolved != c.ExpectedAction {
			t.Fatalf("adversarial cognitive case %s failed: %+v", c.CaseID, c)
		}
	}
}

func TestPredictiveFailureAnalyzerAndCriticalPath(t *testing.T) {
	risks, critPath := RunPredictiveFailureAnalysis()
	if len(critPath) != 8 || len(risks) < 5 {
		t.Fatalf("expected 8 critical path stages and >= 5 predictive risks, got %d / %d", len(critPath), len(risks))
	}
	for _, r := range risks {
		if !r.PredictedBeforeExec || r.CalibratedProbability <= 0.5 {
			t.Fatalf("expected pre-execution calibrated prediction for %s, got %+v", r.RiskID, r)
		}
	}
}

func TestExperimentEAutonomousCheckpointRecovery(t *testing.T) {
	cps, recs := RunAutonomousRecoveryExperiment()
	if len(cps) != 4 || len(recs) != 4 {
		t.Fatalf("expected 4 checkpoints and 4 recovery records, got %d / %d", len(cps), len(recs))
	}
	for _, r := range recs {
		if !r.RecoveredAutonomous || r.DuplicateSideEffects != 0 {
			t.Fatalf("expected autonomous recovery with 0 duplicate side effects: %+v", r)
		}
	}
}

func TestResourceAwareTelemetryAndPCIeGuard(t *testing.T) {
	hw := CollectResourceAwareTelemetry()
	if hw.CPULogicalCores <= 0 || hw.TotalPhysicalRAMMB <= 0 {
		t.Fatalf("invalid hardware telemetry: %+v", hw)
	}
	if !strings.Contains(hw.SmallWorkloadSelectedDev, "CPU_GO_NATIVE") {
		t.Fatalf("expected small workload to stay on CPU_GO_NATIVE, got %s", hw.SmallWorkloadSelectedDev)
	}
	if hw.SpeedupIntelSharedVsGoCPU <= 1.0 || hw.SpeedupNvidiaCUDAVsGoCPU <= 1.0 {
		t.Fatalf("expected > 1.0x speedup on large batches for Intel Shared (%.2fx) and NVIDIA CUDA (%.2fx)",
			hw.SpeedupIntelSharedVsGoCPU, hw.SpeedupNvidiaCUDAVsGoCPU)
	}
}

func TestEndToEndAgenticDeliveryContractV2(t *testing.T) {
	rep := RunEndToEndAgenticEvaluation(20)
	if rep.SampleDeliveryContract.FinalVerdict != VerdictProvenSuccess {
		t.Fatalf("expected FinalVerdict = PROVEN_SUCCESS, got %s", rep.SampleDeliveryContract.FinalVerdict)
	}
	if rep.SampleDeliveryContract.CriteriaTamperDetected {
		t.Fatal("unexpected criteria tampering detected")
	}
	if len(rep.ControlledGroups) != 5 || len(rep.GapsCatalog) != 8 || len(rep.ExpDAdverseConditions) != 10 {
		t.Fatalf("unexpected counts: groups=%d gaps=%d adv=%d",
			len(rep.ControlledGroups), len(rep.GapsCatalog), len(rep.ExpDAdverseConditions))
	}
	rawJSON, err := json.MarshalIndent(rep, "", "  ")
	if err != nil || len(rawJSON) < 1000 {
		t.Fatalf("failed to serialize FullAuditExperimentReport to JSON: %v", err)
	}
}

func repoRootForEvalLabTest(t *testing.T) string {
	t.Helper()
	_, file, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("cannot resolve caller")
	}
	return filepath.Clean(filepath.Join(filepath.Dir(file), "..", ".."))
}

func TestContinuousSkillEvalModelAll108SkillsAndEvolutionGate(t *testing.T) {
	root := repoRootForEvalLabTest(t)
	cat, err := catalog.Load(root)
	if err != nil {
		t.Fatalf("catalog.Load failed: %v", err)
	}

	rep := EvaluateAllSkillsContinuously(cat, "")
	if rep.TotalSkillsEvaluated < 108 {
		t.Fatalf("expected >= 108 skills evaluated, got %d", rep.TotalSkillsEvaluated)
	}
	if rep.FailedCount > 0 || rep.OverallVerdict != VerdictProvenSuccess {
		for _, r := range rep.Results {
			if r.Verdict != VerdictProvenSuccess {
				t.Logf("skill %s verdict=%s score=%.2f pass^5=%.2f gates=%+v issues=%v",
					r.SkillName, r.Verdict, r.CompositeScore, r.PassHat5, r.Gates, r.Issues)
			}
		}
		t.Fatalf("expected all %d skills to achieve PROVEN_SUCCESS, got proven=%d partial=%d failed=%d",
			rep.TotalSkillsEvaluated, rep.ProvenSuccessCount, rep.PartialSuccessCount, rep.FailedCount)
	}

	// Verify evolution gate approves valid skill and blocks regression
	decOK, err := EvaluateSkillEvolutionDelta(cat, "eval-agentic-api", 95.0, 1.0)
	if err != nil || !decOK.Approved || decOK.Verdict != VerdictProvenSuccess {
		t.Fatalf("expected eval-agentic-api evolution delta to pass, got %+v err=%v", decOK, err)
	}

	_, errReg := EvaluateSkillEvolutionDelta(cat, "eval-agentic-api", 105.0, 1.0)
	if !errors.Is(errReg, ErrSkillEvolutionRegression) {
		t.Fatalf("expected ErrSkillEvolutionRegression when candidate score < baseline, got %v", errReg)
	}

	// Verify template generator
	tpl := GenerateCanonicalSkillEvalTemplate(cat.Skills[0])
	if tpl.SkillName == "" || tpl.CriteriaSealSHA256 == "" || len(tpl.Evals) == 0 {
		t.Fatalf("invalid generated template: %+v", tpl)
	}
}

func TestVaultVPCAndLocalStackInfraSimulation(t *testing.T) {
	subnets, sgs, cfg := DefaultCanonicalVaultVPCSpec()
	rep, err := SimulateVaultAndVPCInfra(subnets, sgs, cfg)
	if err != nil || rep.Verdict != VerdictProvenSuccess {
		t.Fatalf("expected canonical Vault+VPC+LocalStack simulation to pass, got %+v err=%v", rep, err)
	}
	if !rep.ZeroTrustVPCValid || !rep.KMSAutoUnsealValid || !rep.DynamicSTSCredsValid || !rep.SGChainingValid {
		t.Fatalf("expected all zero-trust and LocalStack checks true: %+v", rep)
	}

	// Adversarial case: open 0.0.0.0/0 on Vault port 8200
	badSGs := []SecurityGroupSpec{
		{
			Name: "squad-vault-cluster-sg",
			Ingress: []SecurityGroupRuleSpec{
				{Port: 8200, Protocol: "tcp", SourceCIDR: "0.0.0.0/0"},
			},
		},
	}
	badRep, badErr := SimulateVaultAndVPCInfra(subnets, badSGs, cfg)
	if !errors.Is(badErr, ErrVPCZeroTrustViolation) || badRep.Verdict != VerdictFailed {
		t.Fatalf("expected ErrVPCZeroTrustViolation on 0.0.0.0/0 Vault SG rule, got %+v err=%v", badRep, badErr)
	}

	// Verify the new skill vault-aws-vpc-localstack in continuous eval
	root := repoRootForEvalLabTest(t)
	cat, loadErr := catalog.Load(root)
	if loadErr != nil {
		t.Fatalf("catalog.Load failed: %v", loadErr)
	}
	skillRep := EvaluateAllSkillsContinuously(cat, "vault-aws-vpc-localstack")
	if skillRep.TotalSkillsEvaluated != 1 || skillRep.OverallVerdict != VerdictProvenSuccess || skillRep.MeanCompositeScore != 100.0 {
		t.Fatalf("expected vault-aws-vpc-localstack to score 100.0 PROVEN_SUCCESS, got %+v", skillRep)
	}
}


