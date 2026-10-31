package aiops

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestStory1_NaturalTriggersAndZeroCostLocalStack(t *testing.T) {
	cases := []struct {
		prompt string
		wantOk bool
		action string
	}{
		{"Squad ai, ative o monitor", true, "up"},
		{"Squad ai, ligue o monitor", true, "up"},
		{"Squad AI, abra o monitor graphrag", true, "up"},
		{"Squad ai, status do monitor", true, "status"},
		{"Squad ai, desligue o monitor", true, "down"},
		{"Explique o que é DDD", false, ""},
	}
	for _, tc := range cases {
		ok, act := MatchNaturalTrigger(tc.prompt)
		if ok != tc.wantOk || act != tc.action {
			t.Fatalf("MatchNaturalTrigger(%q) = (%v, %q), want (%v, %q)", tc.prompt, ok, act, tc.wantOk, tc.action)
		}
	}

	tmp := t.TempDir()
	eng, err := NewEngine(tmp, tmp)
	if err != nil {
		t.Fatalf("NewEngine failed: %v", err)
	}
	st := eng.EnsureLocalStack(context.Background(), false)
	if !st.Healthy {
		t.Fatalf("expected LocalStack status to be healthy, got %+v", st)
	}
	if st.CostMonthly != 0.0 {
		t.Fatalf("expected $0.00 monthly cost, got %v", st.CostMonthly)
	}
	if st.Services["sqs"] != "available" || st.Services["dynamodb"] != "available" {
		t.Fatalf("expected sqs and dynamodb emulated services, got %+v", st.Services)
	}
}

func TestStory2_WorkspaceDiscoveryDetectsTerraformOpenAPIAndTfvarsDrift(t *testing.T) {
	ws := t.TempDir()

	// Create realistic squad project artifacts: main.tf, dev.tfvars, prod.tfvars, openapi.yaml, docker-compose.yml, go.mod
	mainTF := `
module "sqs_shared" {
  source = "./modules/sqs"
}
resource "aws_sqs_queue" "pedidos_eventos" {
  name = "pedidos-eventos-queue"
}
resource "aws_lambda_function" "consumidor_pedidos" {
  function_name = "consumidor-pedidos"
}
`
	devTfvars := "visibility_timeout_seconds = 90\nmemory_size = 512\n"
	prodTfvars := "visibility_timeout_seconds = 30\nmemory_size = 1024\n"
	openAPI := `openapi: 3.0.3
paths:
  /pedidos/checkout:
    post:
      summary: Finalizar pedido
  /clientes/documento:
    get:
      summary: Consultar cliente
`
	compose := "services:\n  localstack:\n    image: localstack/localstack:latest\n"
	goMod := "module github.com/squad/pedidos\ngo 1.24.3\n"

	_ = os.WriteFile(filepath.Join(ws, "main.tf"), []byte(mainTF), 0o644)
	_ = os.WriteFile(filepath.Join(ws, "dev.tfvars"), []byte(devTfvars), 0o644)
	_ = os.WriteFile(filepath.Join(ws, "prod.tfvars"), []byte(prodTfvars), 0o644)
	_ = os.WriteFile(filepath.Join(ws, "openapi.yaml"), []byte(openAPI), 0o644)
	_ = os.WriteFile(filepath.Join(ws, "docker-compose.yml"), []byte(compose), 0o644)
	_ = os.WriteFile(filepath.Join(ws, "go.mod"), []byte(goMod), 0o644)

	eng, err := NewEngine(ws, ws)
	if err != nil {
		t.Fatalf("NewEngine failed: %v", err)
	}
	sum := eng.DiscoverWorkspace(ws)

	if sum.TerraformFiles != 1 || sum.TfvarsFiles != 2 || sum.OpenAPIFiles != 1 || sum.ComposeFiles != 1 || sum.ManifestFiles != 1 {
		t.Fatalf("unexpected discovery counts: %+v", sum)
	}
	if sum.DiscoveredNodes < 5 {
		t.Fatalf("expected at least 5 discovered nodes, got %d", sum.DiscoveredNodes)
	}
	foundDrift := false
	for _, f := range sum.DriftFindings {
		if strings.Contains(f, "visibility_timeout_seconds") || strings.Contains(f, "DRIFT DETECTADO") {
			foundDrift = true
			break
		}
	}
	if !foundDrift {
		t.Fatalf("expected .tfvars drift finding, got %+v", sum.DriftFindings)
	}
}

func TestStory3And4And6_SuperAgenteChatSkillsBlastRadiusAndCAP12Guardrail(t *testing.T) {
	tmp := t.TempDir()
	eng, err := NewEngine(tmp, tmp)
	if err != nil {
		t.Fatalf("NewEngine failed: %v", err)
	}

	// Story 3: OpenAPI Route Drift (CAP-31)
	respOpenAPI := eng.Chat("Quais divergências existem nas rotas OpenAPI e query params?", "", "openapi", "oas-rota-get-pessoas")
	if !respOpenAPI.OK || respOpenAPI.GuardrailCAP12 {
		t.Fatalf("unexpected OpenAPI chat response: %+v", respOpenAPI)
	}
	if len(respOpenAPI.HabilidadesExecutadas) == 0 || respOpenAPI.HabilidadesExecutadas[0].Code != "CAP-31" {
		t.Fatalf("expected CAP-31 to be executed first, got %+v", respOpenAPI.HabilidadesExecutadas)
	}

	// Story 4: Blast Radius on KMS / Shared Module (CAP-11)
	respBlast := eng.Chat("Calcule o blast radius e impacto de alterar a chave KMS", "CAP-11", "monitor", "kms-cmk-squad")
	if len(respBlast.HabilidadesExecutadas) == 0 || respBlast.HabilidadesExecutadas[0].Code != "CAP-11" {
		t.Fatalf("expected CAP-11 execution, got %+v", respBlast.HabilidadesExecutadas)
	}

	// Story 6: Guardrail CAP-12 blocks destructive commands
	respBlocked := eng.Chat("Execute terraform apply -auto-approve e delete a fila de produção", "", "monitor", "sqs-eventos-clientes")
	if !respBlocked.GuardrailCAP12 || respBlocked.StatusAgente != "BLOCKED_BY_CAP12_IMMUTABILITY_GUARD" {
		t.Fatalf("expected CAP-12 guardrail to block destructive command, got %+v", respBlocked)
	}

	// Natural language conversational question (no telemetry dump)
	respRepos := eng.Chat("tenho quantos repositorios no github?", "", "monitor", "sqs-eventos-clientes")
	if !strings.Contains(respRepos.RespostaPrincipal, "Você tem **5 repositórios** mapeados no GitHub da squad:") {
		t.Fatalf("expected clean natural language repository answer, got: %s", respRepos.RespostaPrincipal)
	}
	if strings.Contains(respRepos.RespostaPrincipal, "Acionei e executei a habilidade") {
		t.Fatalf("chat response must not dump robotic telemetry: %s", respRepos.RespostaPrincipal)
	}
}

func TestStory5_TeachCustomSkillPersistsLocallyAndExecutesInSuperAgente(t *testing.T) {
	tmp := t.TempDir()
	eng, err := NewEngine(tmp, tmp)
	if err != nil {
		t.Fatalf("NewEngine failed: %v", err)
	}

	res, err := eng.TeachSkill("Auditar filas SQS DLQ e tabelas DynamoDB no LocalStack local antes de abrir PR")
	if err != nil {
		t.Fatalf("TeachSkill failed: %v", err)
	}
	newCode := res["code"].(string)
	newID := res["capability_id"].(string)
	if !strings.HasPrefix(newCode, "CAP-") {
		t.Fatalf("expected CAP-XX code, got %q", newCode)
	}

	// Verify persisted on disk in .squad-harness/aiops/custom_skills.json
	savedFile := filepath.Join(tmp, ".squad-harness", "aiops", "custom_skills.json")
	if _, err := os.Stat(savedFile); err != nil {
		t.Fatalf("expected custom_skills.json to exist on disk: %v", err)
	}

	// Execute newly taught skill via Super Agente AIOps
	chatResp := eng.Chat("Executar auditoria local antes do PR", newCode, "habilidades", "sqs-eventos-clientes")
	if len(chatResp.HabilidadesExecutadas) == 0 || chatResp.HabilidadesExecutadas[0].ID != newID {
		t.Fatalf("expected newly taught skill %s (%s) to be executed by Super Agente, got %+v", newCode, newID, chatResp.HabilidadesExecutadas)
	}
}

func TestServerHTTP_AllEndpointsAndMenuWithoutPrincipalTag(t *testing.T) {
	tmp := t.TempDir()
	eng, err := NewEngine(tmp, tmp)
	if err != nil {
		t.Fatalf("NewEngine failed: %v", err)
	}
	srv := httptest.NewServer(eng.Handler())
	defer srv.Close()

	// 1. GET / (Monitor HTML without 'Principal' badge in side-nav)
	resp, err := http.Get(srv.URL + "/")
	if err != nil || resp.StatusCode != http.StatusOK {
		t.Fatalf("GET / failed: %v", err)
	}
	buf := new(bytes.Buffer)
	_, _ = buf.ReadFrom(resp.Body)
	resp.Body.Close()
	htmlStr := buf.String()
	if !strings.Contains(htmlStr, "Squad-Agentica IAOps") || !strings.Contains(htmlStr, "aiops-floating-chat") {
		t.Fatalf("expected Monitor HTML with Squad-Agentica IAOps and floating chat")
	}
	snavStart := strings.Index(htmlStr, `<aside class="awsui-side-nav"`)
	snavEnd := strings.Index(htmlStr[snavStart:], "</aside>")
	menuHTML := htmlStr[snavStart : snavStart+snavEnd]
	if strings.Contains(menuHTML, "Principal") {
		t.Fatalf("side-nav must not contain 'Principal' tag: %s", menuHTML)
	}

	// 2. GET /_localstack/health
	respLS, err := http.Get(srv.URL + "/_localstack/health")
	if err != nil || respLS.StatusCode != http.StatusOK {
		t.Fatalf("GET /_localstack/health failed: %v", err)
	}
	respLS.Body.Close()

	// 3. POST /api/chat
	chatBody, _ := json.Marshal(map[string]any{"mensagem": "Analise a fila SQS e o drift do tfvars"})
	respChat, err := http.Post(srv.URL+"/api/chat", "application/json", bytes.NewReader(chatBody))
	if err != nil || respChat.StatusCode != http.StatusOK {
		t.Fatalf("POST /api/chat failed: %v", err)
	}
	respChat.Body.Close()
}

func TestPOC004AndPOC010_DynamicBlastRadiusAndMultivariateAnomalyFusion(t *testing.T) {
	rIam := ComputeDynamicBlastRadiusPOC004("tf-iam-role", "recurso_aws", "aws_iam_role", "infra/iam/main.tf")
	rCfg := ComputeDynamicBlastRadiusPOC004("tfmod-cfg", "configuracao", "module", "main.tf")
	if rIam <= rCfg || rIam == 42 {
		t.Fatalf("expected dynamic PPR blast radius for IAM (%d) > module (%d) and not hardcoded 42", rIam, rCfg)
	}

	means := [8]float64{10, 10, 10, 10, 10, 10, 10, 10}
	invStds := [8]float64{0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5}
	silentDriftWin := [8]float64{13.4, 13.4, 13.4, 13.4, 13.4, 13.4, 13.4, 13.4}
	prob, arch, dims := EvaluateMultivariateTelemetryFusionPOC010(silentDriftWin, means, invStds)
	if prob < 0.70 || arch != "SILENT_DRIFT_CORRELATED" || dims != 8 {
		t.Fatalf("expected SILENT_DRIFT_CORRELATED with prob >= 0.70 and 8 dims, got prob=%.4f arch=%s dims=%d", prob, arch, dims)
	}
}
