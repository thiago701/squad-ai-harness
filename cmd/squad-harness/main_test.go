package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/thiago701/squad-ai-harness/internal/aws"
	"github.com/thiago701/squad-ai-harness/internal/catalog"
	"github.com/thiago701/squad-ai-harness/internal/cognitive/cultivator"
	"github.com/thiago701/squad-ai-harness/internal/cognitive/graphrag"
	"github.com/thiago701/squad-ai-harness/internal/cognitive/harness"
	"github.com/thiago701/squad-ai-harness/internal/cognitive/memory"
	"github.com/thiago701/squad-ai-harness/internal/cognitive/router"
	"github.com/thiago701/squad-ai-harness/internal/cognitive/sekg"
	"github.com/thiago701/squad-ai-harness/internal/compute"
	"github.com/thiago701/squad-ai-harness/internal/dag"
	"github.com/thiago701/squad-ai-harness/internal/gates"
	"github.com/thiago701/squad-ai-harness/internal/git"
	"github.com/thiago701/squad-ai-harness/internal/hooks"
	"github.com/thiago701/squad-ai-harness/internal/jev"
	"github.com/thiago701/squad-ai-harness/internal/mcp"
	"github.com/thiago701/squad-ai-harness/internal/runtime/gitstate"
	"github.com/thiago701/squad-ai-harness/internal/runtime/jobobject"
	"github.com/thiago701/squad-ai-harness/internal/scheduler"
	"github.com/thiago701/squad-ai-harness/internal/security/fsguard"
	"github.com/thiago701/squad-ai-harness/internal/security/secretscan"
	"github.com/thiago701/squad-ai-harness/internal/sonar"
	"github.com/thiago701/squad-ai-harness/pkg/contracts"
)

func repoRootForTest(t testing.TB) string {
	t.Helper()
	abs, err := filepath.Abs(filepath.Join("..", ".."))
	if err != nil {
		t.Fatalf("resolve repo root: %v", err)
	}
	return abs
}

func TestContractsAndGatePrecedence(t *testing.T) {
	if contracts.Version != "0.8.0" || contracts.TechnicalName != "squad-ai-harness" {
		t.Fatalf("unexpected identity: %s v%s", contracts.TechnicalName, contracts.Version)
	}
	merged := contracts.MergeGateStates(contracts.GatePass, contracts.GateInconclusive, contracts.GateStale)
	if merged != contracts.GateStale {
		t.Fatalf("expected STALE > INCONCLUSIVE > PASS, got %s", merged)
	}
	mergedBlocked := contracts.MergeGateStates(contracts.GatePass, contracts.GateBlocked, contracts.GateStale)
	if mergedBlocked != contracts.GateBlocked || mergedBlocked.Authorize() {
		t.Fatalf("expected BLOCKED to win and never authorize, got %s", mergedBlocked)
	}
}

func TestFSGuardBlocksTraversalAndStreams(t *testing.T) {
	tmp := t.TempDir()
	okPath, err := fsguard.SafeJoin(tmp, "subdir/file.txt")
	if err != nil || !strings.HasPrefix(okPath, tmp) {
		t.Fatalf("expected valid SafeJoin, got %q err=%v", okPath, err)
	}

	invalidCases := []string{
		"../outside.txt",
		"subdir/../../escape.txt",
		"file.txt:secret_stream",
		"CON.txt",
		`\\server\share\file.txt`,
	}
	for _, tc := range invalidCases {
		if _, err := fsguard.SafeJoin(tmp, tc); err == nil {
			t.Errorf("expected SafeJoin to block %q, but it succeeded", tc)
		}
	}
}

func TestJobObjectSupervisorAndSystemMemory(t *testing.T) {
	mem, err := jobobject.ProbeSystemMemory()
	if err != nil {
		t.Fatalf("ProbeSystemMemory failed: %v", err)
	}
	if mem.TotalPhysMB <= 0 || mem.AvailPhysMB <= 0 {
		t.Fatalf("unexpected memory values: %+v", mem)
	}

	res, err := jobobject.ExecuteSupervised(t.Context(), jobobject.RunSpec{
		Argv:          []string{"go", "version"},
		Timeout:       10 * time.Second,
		MemoryLimitMB: 512,
	})
	if err != nil || res.ExitCode != 0 || !strings.Contains(res.Stdout, "go1.24.3") {
		t.Fatalf("ExecuteSupervised failed: res=%+v err=%v", res, err)
	}
}

func TestSecretScanAndPromptDefense(t *testing.T) {
	fakeKey := "AKIA" + "IOSFODNN7REALKEY"
	findings := secretscan.ScanContent("config.yaml", []byte("aws_key: "+fakeKey+"\n"))
	if len(findings) != 1 || findings[0].RuleID != "SEC-AWS-ACCESS-KEY" {
		t.Fatalf("expected AWS key detection, got %+v", findings)
	}

	// Sentinel must be ignored
	sentinelFindings := secretscan.ScanContent("doc.md", []byte("aws_key: AKIAIOSFODNN7EXAMPLE\n"))
	if len(sentinelFindings) != 0 {
		t.Fatalf("expected sentinel to be ignored, got %+v", sentinelFindings)
	}

	// Trojan Source Bidi character must be blocked
	bidiFindings := secretscan.ScanContent("main.go", []byte("func main() { /* \u202E */ }\n"))
	if len(bidiFindings) == 0 || bidiFindings[0].RuleID != "SEC-UNICODE-BIDI" {
		t.Fatalf("expected Bidi Trojan detection, got %+v", bidiFindings)
	}
}

func TestHotPathHooks(t *testing.T) {
	root := repoRootForTest(t)

	// 1. PreToolUse blocks --no-verify
	code, msg := hooks.PreToolUse(root, strings.NewReader(`{"tool_name":"Bash","tool_input":{"command":"git commit -m test --no-verify"}}`))
	if code != 2 || !strings.Contains(msg, "bloqueado") {
		t.Fatalf("expected PreToolUse to block --no-verify, got code=%d msg=%q", code, msg)
	}

	// 2. PreToolUse allows safe command
	codeSafe, _ := hooks.PreToolUse(root, strings.NewReader(`{"tool_name":"Bash","tool_input":{"command":"git status"}}`))
	if codeSafe != 0 {
		t.Fatalf("expected safe command to pass, got %d", codeSafe)
	}

	// 3. PostToolUse blocks file containing secret
	tmp := t.TempDir()
	badFile := filepath.Join(tmp, "bad.py")
	_ = os.WriteFile(badFile, []byte("logger.info(os.environ)\n"), 0o644)
	payload, _ := json.Marshal(map[string]any{
		"tool_name":  "Write",
		"tool_input": map[string]string{"file_path": badFile},
	})
	codePost, msgPost := hooks.PostToolUse(tmp, bytes.NewReader(payload))
	if codePost != 2 || !strings.Contains(msgPost, "LOG-ENV-DUMP") {
		t.Fatalf("expected PostToolUse to block LOG-ENV-DUMP, got code=%d msg=%q", codePost, msgPost)
	}
}

func TestDAGEngineConcurrencyAndCycleDetection(t *testing.T) {
	eng := dag.NewEngine(4)
	_ = eng.AddNode(dag.Node{ID: "A", Action: func(ctx context.Context) error { return nil }})
	_ = eng.AddNode(dag.Node{ID: "B", Deps: []string{"A"}, Action: func(ctx context.Context) error { return nil }})
	_ = eng.AddNode(dag.Node{ID: "C", Deps: []string{"A"}, Action: func(ctx context.Context) error { return nil }})
	_ = eng.AddNode(dag.Node{ID: "D", Deps: []string{"B", "C"}, Action: func(ctx context.Context) error { return nil }})

	sum, err := eng.Execute(t.Context())
	if err != nil || !sum.Success || sum.PassedNodes != 4 {
		t.Fatalf("DAG execution failed: %+v err=%v", sum, err)
	}

	// Verify cycle detection
	cyc := dag.NewEngine(2)
	_ = cyc.AddNode(dag.Node{ID: "X", Deps: []string{"Y"}, Action: func(ctx context.Context) error { return nil }})
	_ = cyc.AddNode(dag.Node{ID: "Y", Deps: []string{"X"}, Action: func(ctx context.Context) error { return nil }})
	if _, err := cyc.Execute(t.Context()); !errors.Is(err, dag.ErrCycleDetected) {
		t.Fatalf("expected ErrCycleDetected, got %v", err)
	}
}

func TestJevTribunalAndSonarFirst(t *testing.T) {
	cleanVerdict := jev.EvaluateTribunal(jev.ReviewInput{
		FilesChanged: []string{"internal/dag/engine.go"},
		DiffContent:  "func Add(a, b int) int { return a + b }",
	})
	if cleanVerdict.Verdict != "READY" || len(cleanVerdict.Decisions) != 25 {
		t.Fatalf("expected READY from 25 JEV specialists, got %+v", cleanVerdict)
	}

	vulnVerdict := jev.EvaluateTribunal(jev.ReviewInput{
		FilesChanged: []string{"auth/login.py"},
		DiffContent:  `query = "SELECT * FROM users WHERE name = " + userInput`,
	})
	if vulnVerdict.Verdict != "NOT_READY" || vulnVerdict.GateState != contracts.GateBlocked {
		t.Fatalf("expected SQLi diff to be blocked by JEV tribunal, got %+v", vulnVerdict)
	}

	sonarRep := sonar.AnalyzeSource("bad.py", []byte("try:\n    x()\nexcept:\n    pass\n"))
	if sonarRep.QualityGatePassed || len(sonarRep.Issues) == 0 {
		t.Fatalf("expected Sonar-First to block silent except: pass, got %+v", sonarRep)
	}
}

func TestAWSLintsAndReadOnlyGuard(t *testing.T) {
	validASL := []byte(`{"StartAt":"Init","States":{"Init":{"Type":"Succeed"}}}`)
	if issues := aws.ValidateASL("ok.asl.json", validASL); len(issues) != 0 {
		t.Fatalf("expected valid ASL, got %+v", issues)
	}
	badASL := []byte(`{"StartAt":"Missing","States":{"Init":{"Type":"Task","Next":"Ghost"}}}`)
	if issues := aws.ValidateASL("bad.asl.json", badASL); len(issues) < 2 {
		t.Fatalf("expected ASL errors for missing StartAt and no terminal state, got %+v", issues)
	}

	if ok, _ := aws.CheckReadOnlyAWSCommand("aws dynamodb delete-table --table-name prod"); ok {
		t.Fatal("expected mutating AWS command to be blocked by read-only guard")
	}
	if ok, _ := aws.CheckReadOnlyAWSCommand("aws dynamodb describe-table --table-name prod"); !ok {
		t.Fatal("expected read-only AWS command to be allowed")
	}
}

func TestCatalogSEKGAndGraphRAGModes(t *testing.T) {
	root := repoRootForTest(t)
	cat, err := catalog.Load(root)
	if err != nil {
		t.Fatalf("catalog.Load failed: %v", err)
	}
	if len(cat.Skills) < 100 {
		t.Fatalf("expected >= 100 canonical skills, got %d", len(cat.Skills))
	}

	rt := router.NewHybridRouter(cat)
	matches := rt.Route("arquitetura aws step functions", 3)
	if len(matches) == 0 {
		t.Fatal("expected hybrid router matches")
	}

	g := sekg.IndexRepository(root, cat)
	if len(g.Nodes) < 100 || len(g.Communities) == 0 {
		t.Fatalf("expected SEKG nodes and Leiden communities, got nodes=%d comms=%d", len(g.Nodes), len(g.Communities))
	}

	impact := g.AnalyzeImpact([]string{"engenheiro-seguranca"})
	if !impact.TriggerSecurity || len(impact.SeedNodes) == 0 {
		t.Fatalf("expected security trigger on engenheiro-seguranca impact, got %+v", impact)
	}

	rag := graphrag.NewEngine(g)
	locRes := rag.LocalSearch(graphrag.QueryRequest{Query: "golang-pro", TopK: 3})
	if locRes.Mode != graphrag.ModeLocal || len(locRes.MatchedEntities) == 0 {
		t.Fatalf("LocalSearch failed: %+v", locRes)
	}

	globRes := rag.GlobalSearch(graphrag.QueryRequest{Query: "visao geral comunidades", TopK: 3})
	if globRes.Mode != graphrag.ModeGlobal || len(globRes.CommunitySummaries) == 0 {
		t.Fatalf("GlobalSearch failed: %+v", globRes)
	}

	driftRes := rag.DRIFTSearch(graphrag.QueryRequest{Query: "causa raiz seguranca", TopK: 3})
	if driftRes.Mode != graphrag.ModeDRIFT || len(driftRes.FollowUpHierarchy) == 0 {
		t.Fatalf("DRIFTSearch failed: %+v", driftRes)
	}
}

func TestMemoryQuarantineComputeRouterSchedulerAndMCP(t *testing.T) {
	// 1. Epistemic anti-hallucination guard
	if _, err := memory.PromoteToVerified(contracts.TrustHypothesis, false, contracts.GatePass); err == nil {
		t.Fatal("expected unverified promotion without passing test to fail")
	}
	tier, err := memory.PromoteToVerified(contracts.TrustHypothesis, true, contracts.GatePass)
	if err != nil || tier != contracts.TrustVerified {
		t.Fatalf("expected verified promotion with passing test + GatePass, got %s err=%v", tier, err)
	}

	// 2. Compute Router C0/C1/C2 + Core Ultra 165U NPU<->iGPU inversion + SERVER01 VRAM + Precision Gates
	prof := compute.WorkstationProfile{HostClass: "cpu+igpu+npu", HasNPU: true, HasIGPU: true, EmbeddingPolicy: compute.HitPolicyAssistOnly}
	cb := compute.NewCircuitBreaker()
	dC1 := compute.RouteWorkload(prof, cb, "embed.query", 1, 48, false)
	if dC1.SelectedLayer != compute.LayerC1LocalAssist || dC1.HitPolicy != compute.HitPolicyAssistOnly || dC1.Device != "NPU_INTEL" {
		t.Fatalf("unexpected C1 NPU query routing: %+v", dC1)
	}
	dIdx := compute.RouteWorkload(prof, cb, "embed.index", 16, 128, false)
	if dIdx.Device != "IGPU_INTEL_FP32" || dIdx.Precision != "FP32" {
		t.Fatalf("expected Core Ultra batch B=16 to route to IGPU_INTEL_FP32, got %+v", dIdx)
	}
	if ok, _ := compute.ValidatePrecisionForDevice("NPU_INTEL", "INT8_ONNX_DYNAMIC"); ok {
		t.Fatal("expected INT8_ONNX_DYNAMIC on NPU to be rejected")
	}
	if ok, _ := compute.ValidatePrecisionForDevice("CPU_GO", "INT4"); ok {
		t.Fatal("expected INT4 for embeddings to be rejected")
	}
	if ok, _ := compute.AdmitVRAMMultiTenant(12288, []string{"embedding", "laya"}, "llm"); ok {
		t.Fatal("expected 3-tenant co-location (embedding+laya+llm) on 12 GB VRAM to be blocked")
	}
	cleanedDevs := compute.FilterPhantomOpenVINOGPUs(map[string]map[string]any{
		"GPU.0": {"nome": "Intel(R) Arc(TM) Graphics", "tipo": "integrated"},
		"GPU.1": {"nome": "", "tipo": "discrete"},
	}, true)
	if _, hasIGPU := cleanedDevs["GPU.0"]; !hasIGPU || len(cleanedDevs) != 1 {
		t.Fatalf("expected FilterPhantomOpenVINOGPUs to preserve Intel iGPU and drop phantom discrete GPU, got %+v", cleanedDevs)
	}
	if ok, _ := compute.EvaluateAccelPromotion(compute.PromotionGateInput{
		CosineParityVsCPU: 0.997, SpeedupVsBaseline: 1.62, Repetitions: 5,
		GoldenSealed: true, NoSealedRegressed: true, HumanApproved: true,
	}); !ok {
		t.Fatal("expected valid Core Ultra 1.62x promotion input to be approved")
	}

	// Verify multi-PC routing: (a) pure CPU Go-native, (b) CPU with local OpenVINO/ORT, (c) legacy CUDA (executavel=false)
	cpuGoProf := compute.WorkstationProfile{HostClass: "cpu", Runtime: "go-native"}
	if dGo := compute.RouteWorkload(cpuGoProf, cb, "embed.query", 1, 32, false); dGo.SelectedLayer != compute.LayerC0Deterministic || dGo.Device != "CPU_GO" {
		t.Fatalf("expected pure CPU Go-native station to route to C0 CPU_GO, got %+v", dGo)
	}
	cpuNeuralProf := compute.WorkstationProfile{HostClass: "cpu", Runtime: "openvino"}
	if dNeu := compute.RouteWorkload(cpuNeuralProf, cb, "embed.query", 1, 32, false); dNeu.SelectedLayer != compute.LayerC1LocalAssist || dNeu.Device != "CPU_NEURAL_INT8_NNCF" {
		t.Fatalf("expected CPU station with OpenVINO/ORT to route to CPU_NEURAL_INT8_NNCF, got %+v", dNeu)
	}
	parsedLegacyGPU := compute.ParseWorkstationJSON([]byte(`{"classe":"cpu+dgpu","runtime":"openvino","dispositivos":{"CUDA":{"executavel":false,"mem_mb":2048}}}`), cpuGoProf)
	if parsedLegacyGPU.HasDGPU {
		t.Fatalf("expected unexecutable legacy CUDA GPU (MX110 CUDA 11.0) to have HasDGPU=false, got %+v", parsedLegacyGPU)
	}


	// 3. Scheduler 8D + --strict-mcp-config + Git Sync classifier
	args := scheduler.BuildHardenedClaudeArgs("ok", "scheduler/batman-mcp.json")
	if len(args) < 3 || args[2] != "--strict-mcp-config" {
		t.Fatalf("expected --strict-mcp-config in Batman worker args, got %v", args)
	}
	plan := git.ClassifyAndPlan(&gitstate.RepoSnapshot{Branch: "master", DefaultBranch: true, Changes: []gitstate.FileChange{{Status: "M", Path: "README.md"}}})
	if plan.StateClass != "SUJO_LOCAL" || len(plan.Steps) == 0 {
		t.Fatalf("unexpected git sync plan: %+v", plan)
	}

	// 4. Cultivator anti-regression oracle
	_, err = cultivator.ValidateProposal(cultivator.EvolutionProposal{
		TargetSkill:      "golang-pro",
		VerifiedEpisodes: 3,
		BaselineRecall:   0.96,
		CandidateRecall:  0.90,
	})
	if !errors.Is(err, cultivator.ErrHeldOutRegression) {
		t.Fatalf("expected ErrHeldOutRegression, got %v", err)
	}

	// 5. Native MCP Server
	root := repoRootForTest(t)
	eng, err := harness.NewEngine(root)
	if err != nil {
		t.Fatalf("NewEngine failed: %v", err)
	}
	srv := mcp.NewServer(root, eng)
	resp := srv.HandleRequest(mcp.RPCRequest{JSONRPC: "2.0", ID: 1, Method: "tools/list"})
	if resp == nil || resp.Error != nil {
		t.Fatalf("MCP tools/list failed: %+v", resp)
	}

	// 6. Delivery Gate --somente restriction outside review/planejamento
	decBlocked := gates.DecidirEntrega(t.Context(), root, "push", "database-schema-gate")
	if decBlocked.State != contracts.GateBlocked || decBlocked.Authorized {
		t.Fatalf("expected --somente on push checkpoint to be BLOCKED, got %+v", decBlocked)
	}
}

func BenchmarkHybridRouterAndJevTribunal(b *testing.B) {
	root := repoRootForTest(b)
	cat, err := catalog.Load(root)
	if err != nil {
		b.Fatalf("load catalog: %v", err)
	}
	rt := router.NewHybridRouter(cat)
	b.ReportAllocs()

	for b.Loop() {
		_ = rt.Route("arquitetura aws step functions lambda go performance", 5)
		_ = jev.EvaluateTribunal(jev.ReviewInput{
			FilesChanged: []string{"internal/dag/engine.go"},
			DiffContent:  "func Fast() {}",
		})
	}
}
