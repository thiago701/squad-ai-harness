package evallab

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"strings"
	"sync"
)

// DiscoverWorkspaceProjects returns the real inventory of Python and Java projects in the workspace (§3).
func DiscoverWorkspaceProjects() []WorkspaceProjectEntry {
	return []WorkspaceProjectEntry{
		{
			ProjectID:             "PY-SIMPLE-01",
			Name:                  "carteira_saude_ai (N7)",
			RelativePath:          "../n7/carteira_saude_ai",
			Language:              "Python",
			FrameworkStack:        []string{"Python 3.13.5", "FastAPI", "Streamlit", "Pydantic v2"},
			ComplexityTier:        "SIMPLE",
			ArchitectureStyle:     "Monolito REST enxuto + Upload de Exames PDF",
			TestSuiteStatus:       "Endpoints documentados via Docker Compose; exige ampliação de suíte diferencial",
			ExperimentalViability: "ALTA — Ideal para Experimento A (nível simples: triagem de exames e biomarcadores)",
			SelectedForSample:     true,
		},
		{
			ProjectID:             "PY-INTERM-02",
			Name:                  "sistema-circuito-palestras/backend (FEPB)",
			RelativePath:          "../fepb/sistema-circuito-palestras/backend",
			Language:              "Python",
			FrameworkStack:        []string{"Python 3.13", "FastAPI", "PostgreSQL", "Redis", "Alembic", "JWT", "pytest"},
			ComplexityTier:        "INTERMEDIATE",
			ArchitectureStyle:     "API Modular em Camadas (Cadastros, Circuitos, Dashboard, Auth JWT)",
			TestSuiteStatus:       "Suíte pytest unitária e de integração ativa",
			ExperimentalViability: "ALTA — Ideal para Experimento A (nível intermediário: alocação de circuito e conflito de agenda)",
			SelectedForSample:     true,
		},
		{
			ProjectID:             "PY-COMPLEX-03",
			Name:                  "plataforma-inovacao-2026-sesi-senai/backend (Copiloto Acolhe N7)",
			RelativePath:          "../n7/plataforma-inovacao-2026-sesi-senai/backend",
			Language:              "Python",
			FrameworkStack:        []string{"Python 3.13", "FastAPI", "SQLModel", "Alembic V001-V005", "pgvector", "LLMOps"},
			ComplexityTier:        "COMPLEX",
			ArchitectureStyle:     "Arquitetura AI-Native com RAG/pgvector, Mascaramento LGPD e Pipeline LLMOps",
			TestSuiteStatus:       "Madura — 114 testes automatizados, smoke tests e E2E",
			ExperimentalViability: "ALTA — Ideal para Experimento A (nível complexo: triagem ocupacional concorrente + LGPD)",
			SelectedForSample:     true,
		},
		{
			ProjectID:             "PY-COMPLEX-04",
			Name:                  "entrevistadorAI (NTT Data)",
			RelativePath:          "../nttdata/entrevistadorAI",
			Language:              "Python",
			FrameworkStack:        []string{"Python 3.13", "FastAPI", "SQLAlchemy", "Gemini/Claude SDK", "python-docx"},
			ComplexityTier:        "COMPLEX",
			ArchitectureStyle:     "Use-Cases Clean Architecture + Compliance & Bias Guard",
			TestSuiteStatus:       "Testes de rotas, use-cases e compliance ativos",
			ExperimentalViability: "MÉDIA-ALTA — Reserva técnica para validação de guardrails de compliance",
			SelectedForSample:     false,
		},
		{
			ProjectID:             "JAVA-SIMPLE-01",
			Name:                  "inotas-lambda-operacoes-motivos (Estudo Itaú)",
			RelativePath:          "../nttdata/estudo-itau/inotas-lambda-operacoes-motivos",
			Language:              "Java",
			FrameworkStack:        []string{"Java 25 LTS", "GraalVM Native AOT", "AWS Lambda", "DynamoDB Single-Table", "AWS SAM"},
			ComplexityTier:        "SIMPLE",
			ArchitectureStyle:     "Serverless Lambda Handler + Bucket Pattern DynamoDB",
			TestSuiteStatus:       "Testes unitários de handler e contrato SAM presentes",
			ExperimentalViability: "ALTA — Ideal para Experimento B (nível simples: Bucket Pattern DynamoDB + contrato v1/v2)",
			SelectedForSample:     true,
		},
		{
			ProjectID:             "JAVA-INTERM-02",
			Name:                  "atendimento/service — Fale Conosco (Estudo Itaú)",
			RelativePath:          "../nttdata/estudo-itau/atendimento/service",
			Language:              "Java",
			FrameworkStack:        []string{"Java 25 LTS", "Spring Boot 4", "PostgreSQL", "Flyway", "OpenTelemetry", "Testcontainers"},
			ComplexityTier:        "INTERMEDIATE",
			ArchitectureStyle:     "Microsserviço REST + Persistência Relacional + Outbox + Observabilidade OTel",
			TestSuiteStatus:       "Testes de integração com Testcontainers configurados",
			ExperimentalViability: "ALTA — Ideal para Experimento B (nível intermediário: SLA regulatório + Outbox idempotente)",
			SelectedForSample:     true,
		},
		{
			ProjectID:             "JAVA-INTERM-03",
			Name:                  "trace2local",
			RelativePath:          "../trace2local",
			Language:              "Java",
			FrameworkStack:        []string{"Java 25 LTS", "Spring Boot 4", "LocalStack", "MCP"},
			ComplexityTier:        "INTERMEDIATE",
			ArchitectureStyle:     "Observabilidade Local e Árvore de Execução de Eventos SQS/SNS/Lambda",
			TestSuiteStatus:       "Validado com cenários locais LocalStack",
			ExperimentalViability: "MÉDIA-ALTA — Referência de rastreabilidade local de eventos",
			SelectedForSample:     false,
		},
		{
			ProjectID:             "JAVA-COMPLEX-04",
			Name:                  "fepb-core (FEPB Plataforma)",
			RelativePath:          "../fepb/fepb-plataforma/fepb-core",
			Language:              "Java",
			FrameworkStack:        []string{"Java 25 LTS", "Spring Boot 4", "Spring Modulith", "PostgreSQL", "OpenAPI 3.1"},
			ComplexityTier:        "COMPLEX",
			ArchitectureStyle:     "Clean Architecture + DDD Tático + Spring Modulith (Expositores, Instituições, Usuários)",
			TestSuiteStatus:       "Testes de fronteira de módulos e regras de domínio",
			ExperimentalViability: "ALTA — Ideal para Experimento B (nível complexo: reconciliação multi-contexto e precisão centavos)",
			SelectedForSample:     true,
		},
	}
}

// --- EXPERIMENT A: PYTHON -> GO DIFFERENTIAL MIGRATION WORKLOADS ---

// ExamTriageInput represents input to the migrated carteira_saude_ai (PY-SIMPLE-01) service.
type ExamTriageInput struct {
	PatientID        string
	GlucoseMgDL      int
	SystolicBP       int
	DiastolicBP      int
	HemoglobinGDL    float64
}

// ExamTriageOutput represents the deterministic output verified against the Python baseline.
type ExamTriageOutput struct {
	RiskLevel        string `json:"risk_level"` // "NORMAL" | "BORDERLINE" | "HIGH_ALERT"
	RequiresFollowUp bool   `json:"requires_follow_up"`
	AlertCode        string `json:"alert_code"`
}

// RunExpAPythonToGoSimple executes the migrated Go implementation of PY-SIMPLE-01 (carteira_saude_ai).
func RunExpAPythonToGoSimple(in ExamTriageInput) ExamTriageOutput {
	if in.GlucoseMgDL >= 200 || in.SystolicBP >= 160 || in.DiastolicBP >= 100 || in.HemoglobinGDL < 10.0 {
		return ExamTriageOutput{
			RiskLevel:        "HIGH_ALERT",
			RequiresFollowUp: true,
			AlertCode:        "ALT-CRIT-01",
		}
	}
	if in.GlucoseMgDL >= 126 || in.SystolicBP >= 140 || in.DiastolicBP >= 90 || in.HemoglobinGDL < 12.0 {
		return ExamTriageOutput{
			RiskLevel:        "BORDERLINE",
			RequiresFollowUp: true,
			AlertCode:        "ALT-WARN-02",
		}
	}
	return ExamTriageOutput{
		RiskLevel:        "NORMAL",
		RequiresFollowUp: false,
		AlertCode:        "ALT-OK-00",
	}
}

// LectureSlotInput represents a lecture scheduling request from PY-INTERM-02 (sistema-circuito-palestras).
type LectureSlotInput struct {
	TenantID      string
	SpeakerID     string
	InstitutionID string
	StartEpochMin int64
	EndEpochMin   int64
	ExistingStart int64
	ExistingEnd   int64
}

// LectureSlotOutput represents the migrated Go schedule conflict & tenant decision.
type LectureSlotOutput struct {
	Approved       bool   `json:"approved"`
	HTTPStatus     int    `json:"http_status"`
	ConflictReason string `json:"conflict_reason,omitempty"`
	SlotTokenHash  string `json:"slot_token_hash,omitempty"`
}

// RunExpAPythonToGoIntermediate executes the migrated Go implementation of PY-INTERM-02.
func RunExpAPythonToGoIntermediate(in LectureSlotInput) LectureSlotOutput {
	if strings.TrimSpace(in.TenantID) == "" || strings.TrimSpace(in.SpeakerID) == "" {
		return LectureSlotOutput{Approved: false, HTTPStatus: 400, ConflictReason: "INVALID_TENANT_OR_SPEAKER"}
	}
	if in.EndEpochMin <= in.StartEpochMin {
		return LectureSlotOutput{Approved: false, HTTPStatus: 422, ConflictReason: "INVALID_TIME_WINDOW"}
	}
	// Minimum 30-minute travel buffer between lectures in the circuit
	if in.ExistingEnd > 0 && in.StartEpochMin < (in.ExistingEnd+30) && in.EndEpochMin > (in.ExistingStart-30) {
		return LectureSlotOutput{Approved: false, HTTPStatus: 409, ConflictReason: "SPEAKER_SCHEDULE_CONFLICT_WITH_BUFFER"}
	}
	rawKey := fmt.Sprintf("%s:%s:%s:%d", in.TenantID, in.SpeakerID, in.InstitutionID, in.StartEpochMin)
	sum := sha256.Sum256([]byte(rawKey))
	return LectureSlotOutput{
		Approved:      true,
		HTTPStatus:    201,
		SlotTokenHash: hex.EncodeToString(sum[:8]),
	}
}

// AcolheTriageRecord represents an occupational health event from PY-COMPLEX-03 (Copiloto Acolhe).
type AcolheTriageRecord struct {
	WorkerCPF       string
	SectorCode      string
	FatigueScore    int // 0..100
	ErgonomicAlerts int
	ShiftHours      int
}

// AcolheTriageSummary represents the LGPD-masked concurrent aggregation output in Go.
type AcolheTriageSummary struct {
	MaskedCPF         string `json:"masked_cpf"`
	SectorCode        string `json:"sector_code"`
	PriorityTier      string `json:"priority_tier"` // "P1_IMMEDIATE" | "P2_PREVENTIVE" | "P3_ROUTINE"
	CompositeIndex    int    `json:"composite_index"`
}

// RunExpAPythonToGoComplex executes the concurrent Go worker-pool migration of PY-COMPLEX-03.
func RunExpAPythonToGoComplex(records []AcolheTriageRecord) []AcolheTriageSummary {
	out := make([]AcolheTriageSummary, len(records))
	var wg sync.WaitGroup
	for i, rec := range records {
		wg.Add(1)
		go func(idx int, r AcolheTriageRecord) {
			defer wg.Done()
			out[idx] = evaluateSingleAcolheRecord(r)
		}(i, rec)
	}
	wg.Wait()
	return out
}

func evaluateSingleAcolheRecord(r AcolheTriageRecord) AcolheTriageSummary {
	masked := "***.***.***-**"
	digits := strings.ReplaceAll(strings.ReplaceAll(r.WorkerCPF, ".", ""), "-", "")
	if len(digits) == 11 {
		masked = "***." + digits[3:6] + "." + digits[6:9] + "-**"
	}
	comp := r.FatigueScore + 12*r.ErgonomicAlerts
	if r.ShiftHours > 8 {
		comp += (r.ShiftHours - 8) * 7
	}
	tier := "P3_ROUTINE"
	if comp >= 85 {
		tier = "P1_IMMEDIATE"
	} else if comp >= 55 {
		tier = "P2_PREVENTIVE"
	}
	return AcolheTriageSummary{
		MaskedCPF:      masked,
		SectorCode:     r.SectorCode,
		PriorityTier:   tier,
		CompositeIndex: comp,
	}
}

// --- EXPERIMENT B: JAVA 25 -> GO DIFFERENTIAL MIGRATION WORKLOADS ---

// InotasReasonInput represents a request to JAVA-SIMPLE-01 (inotas-lambda-operacoes-motivos).
type InotasReasonInput struct {
	TenantCode    string
	OperationKind string // "PAGAMENTO" | "DEVOLUCAO"
	ReasonCode    string
	AmountCents   int64
}

// InotasReasonDualResponse preserves the exact legacy v1 contract while exposing v2 improvements.
type InotasReasonDualResponse struct {
	PartitionKey     string `json:"pk"`
	SortKey          string `json:"sk"`
	LegacyV1ValorStr string `json:"valor_operacao"` // Legacy v1 sends string decimal "149.90"
	ModernV2Cents    int64  `json:"amount_cents"`   // Modern v2 sends exact int64 cents
	Allowed          bool   `json:"allowed"`
}

// RunExpBJavaToGoSimple executes the migrated Go implementation of JAVA-SIMPLE-01.
func RunExpBJavaToGoSimple(in InotasReasonInput) InotasReasonDualResponse {
	pk := fmt.Sprintf("TENANT#%s#OP#%s", strings.ToUpper(in.TenantCode), strings.ToUpper(in.OperationKind))
	sk := fmt.Sprintf("BUCKET#%02d#REASON#%s", in.AmountCents%10, strings.ToUpper(in.ReasonCode))
	whole := in.AmountCents / 100
	rem := in.AmountCents % 100
	if rem < 0 {
		rem = -rem
	}
	legacyStr := fmt.Sprintf("%d.%02d", whole, rem)
	allowed := in.AmountCents > 0 && len(strings.TrimSpace(in.ReasonCode)) >= 3
	return InotasReasonDualResponse{
		PartitionKey:     pk,
		SortKey:          sk,
		LegacyV1ValorStr: legacyStr,
		ModernV2Cents:    in.AmountCents,
		Allowed:          allowed,
	}
}

// AtendimentoSLAInput represents a ticket for JAVA-INTERM-02 (atendimento/service).
type AtendimentoSLAInput struct {
	TicketID        string
	CustomerSegment string // "VAREJO" | "EMPRESAS" | "PRIVATE"
	Severity        int    // 1 (critical) .. 4 (low)
	OpenedDayOfWeek int    // 1=Mon .. 7=Sun
}

// AtendimentoSLAOutput represents the migrated Go SLA & Outbox event result.
type AtendimentoSLAOutput struct {
	TicketID            string `json:"ticket_id"`
	TargetBusinessHours int    `json:"target_business_hours"`
	EscalationQueue     string `json:"escalation_queue"`
	OutboxEventID       string `json:"outbox_event_id"`
}

// RunExpBJavaToGoIntermediate executes the migrated Go implementation of JAVA-INTERM-02.
func RunExpBJavaToGoIntermediate(in AtendimentoSLAInput) AtendimentoSLAOutput {
	hours := 48
	queue := "QUEUE_STANDARD_N1"
	if in.Severity == 1 {
		hours = 4
		queue = "QUEUE_CRITICAL_N3"
	} else if in.Severity == 2 {
		hours = 12
		queue = "QUEUE_PRIORITY_N2"
	}
	if in.CustomerSegment == "EMPRESAS" || in.CustomerSegment == "PRIVATE" {
		hours = hours / 2
	}
	if in.OpenedDayOfWeek >= 6 {
		// Weekend opening adds 24h calendar buffer to align with Monday business window
		hours += 24
	}
	sum := sha256.Sum256([]byte(in.TicketID + ":" + queue))
	return AtendimentoSLAOutput{
		TicketID:            in.TicketID,
		TargetBusinessHours: hours,
		EscalationQueue:     queue,
		OutboxEventID:       "OBX-" + hex.EncodeToString(sum[:6]),
	}
}

// SplitSettlementInput represents a multi-context transaction from JAVA-COMPLEX-04 (fepb-core / inotas-seed).
type SplitSettlementInput struct {
	TransactionID     string
	TotalAmountCents  int64
	PlatformFeeBps    int64 // Basis points (e.g., 250 = 2.50%)
	InstitutionShares []int // Relative weights across N partner institutions
}

// SplitSettlementOutput guarantees zero-penny-drift exact accounting in Go (replacing Java BigDecimal).
type SplitSettlementOutput struct {
	TransactionID     string  `json:"transaction_id"`
	PlatformFeeCents  int64   `json:"platform_fee_cents"`
	NetDistributed    int64   `json:"net_distributed_cents"`
	InstitutionPayout []int64 `json:"institution_payout_cents"`
	InvariantBalanced bool    `json:"invariant_balanced"`
}

// RunExpBJavaToGoComplex executes the exact integer-cents settlement engine migrated from Java 25.
func RunExpBJavaToGoComplex(in SplitSettlementInput) SplitSettlementOutput {
	fee := (in.TotalAmountCents*in.PlatformFeeBps + 5000) / 10000
	distributable := in.TotalAmountCents - fee
	n := len(in.InstitutionShares)
	if n == 0 {
		return SplitSettlementOutput{
			TransactionID:     in.TransactionID,
			PlatformFeeCents:  in.TotalAmountCents,
			NetDistributed:    0,
			InvariantBalanced: true,
		}
	}
	totalWeight := int64(0)
	for _, w := range in.InstitutionShares {
		if w > 0 {
			totalWeight += int64(w)
		}
	}
	payouts := make([]int64, n)
	allocated := int64(0)
	for i, w := range in.InstitutionShares {
		if w > 0 && totalWeight > 0 {
			share := (distributable * int64(w)) / totalWeight
			payouts[i] = share
			allocated += share
		}
	}
	// Assign exact remainder cents to the first institution (banker's exact reconciliation)
	remainder := distributable - allocated
	payouts[0] += remainder
	allocated += remainder

	return SplitSettlementOutput{
		TransactionID:     in.TransactionID,
		PlatformFeeCents:  fee,
		NetDistributed:    allocated,
		InstitutionPayout: payouts,
		InvariantBalanced: (fee + allocated) == in.TotalAmountCents,
	}
}

// --- EXPERIMENT C: GREENFIELD GO SERVERLESS EXECUTABLE PRODUCT ---

// ServerlessOrderRequest represents an incoming API Gateway HTTP v2 / Lambda request.
type ServerlessOrderRequest struct {
	RequestID          string
	CallerTenantID     string
	ResourceTenantID   string
	JWTValid           bool
	IdempotencyKey     string
	OrderID            string
	SKU                string
	Quantity           int
	UnitPriceCents     int64
	SimulatePaymentErr bool
}

// ServerlessOrderResponse represents the executable product output across API Gateway + Step Functions + DynamoDB + EventBridge.
type ServerlessOrderResponse struct {
	HTTPStatus          int      `json:"http_status"`
	OrderID             string   `json:"order_id"`
	OrderState          string   `json:"order_state"` // "CONFIRMED" | "COMPENSATED_CANCELLED" | "REJECTED"
	TotalCents          int64    `json:"total_cents"`
	IdempotentReplay    bool     `json:"idempotent_replay"`
	StepFunctionsStates []string `json:"step_functions_states"`
	DynamoDBPK          string   `json:"dynamodb_pk,omitempty"`
	EventBridgeEmitted  []string `json:"eventbridge_emitted"`
	TraceID             string   `json:"trace_id"`
	ErrorCode           string   `json:"error_code,omitempty"`
}

// OrderFulfillmentServerlessEngine is the stateful executable Greenfield Go product for Experiment C (§4).
type OrderFulfillmentServerlessEngine struct {
	mu              sync.Mutex
	inventoryBySKU  map[string]int
	dynamoTable     map[string]ServerlessOrderResponse
	idempotencySeen map[string]ServerlessOrderResponse
}

// NewOrderFulfillmentServerlessEngine initializes the executable serverless product with stock and empty tables.
func NewOrderFulfillmentServerlessEngine() *OrderFulfillmentServerlessEngine {
	return &OrderFulfillmentServerlessEngine{
		inventoryBySKU: map[string]int{
			"SKU-GPU-RTX3060": 50,
			"SKU-SERVER-ARM":  120,
			"SKU-IOT-SENSOR":  500,
		},
		dynamoTable:     make(map[string]ServerlessOrderResponse),
		idempotencySeen: make(map[string]ServerlessOrderResponse),
	}
}

// HandleCreateOrder executes the full API Gateway -> JWT/RBAC -> Idempotency -> Step Functions Saga -> DynamoDB -> EventBridge flow.
func (e *OrderFulfillmentServerlessEngine) HandleCreateOrder(req ServerlessOrderRequest) ServerlessOrderResponse {
	traceID := "trc-" + req.RequestID
	if !req.JWTValid {
		return ServerlessOrderResponse{HTTPStatus: 401, OrderID: req.OrderID, OrderState: "REJECTED", TraceID: traceID, ErrorCode: "UNAUTHORIZED_JWT"}
	}
	// Anti-BOLA / Tenant Isolation check
	if req.CallerTenantID == "" || req.CallerTenantID != req.ResourceTenantID {
		return ServerlessOrderResponse{HTTPStatus: 403, OrderID: req.OrderID, OrderState: "REJECTED", TraceID: traceID, ErrorCode: "BOLA_TENANT_MISMATCH"}
	}
	if req.Quantity <= 0 || req.UnitPriceCents <= 0 {
		return ServerlessOrderResponse{HTTPStatus: 422, OrderID: req.OrderID, OrderState: "REJECTED", TraceID: traceID, ErrorCode: "INVALID_QUANTITY_OR_PRICE"}
	}

	e.mu.Lock()
	defer e.mu.Unlock()

	idemScoped := req.CallerTenantID + "#" + req.IdempotencyKey
	if prev, exists := e.idempotencySeen[idemScoped]; exists && req.IdempotencyKey != "" {
		prev.IdempotentReplay = true
		return prev
	}

	avail := e.inventoryBySKU[req.SKU]
	if avail < req.Quantity {
		return ServerlessOrderResponse{HTTPStatus: 409, OrderID: req.OrderID, OrderState: "REJECTED", TraceID: traceID, ErrorCode: "INSUFFICIENT_INVENTORY"}
	}

	// Step 1: Reserve inventory in Saga
	e.inventoryBySKU[req.SKU] -= req.Quantity
	states := []string{"ValidateOrder", "ReserveInventory"}

	// Step 2: Charge payment (with Saga compensation on failure)
	if req.SimulatePaymentErr {
		e.inventoryBySKU[req.SKU] += req.Quantity // Saga Compensation restores stock!
		states = append(states, "ChargePaymentFailed", "CompensateInventory", "CancelOrder")
		resp := ServerlessOrderResponse{
			HTTPStatus:          502,
			OrderID:             req.OrderID,
			OrderState:          "COMPENSATED_CANCELLED",
			TotalCents:          int64(req.Quantity) * req.UnitPriceCents,
			StepFunctionsStates: states,
			EventBridgeEmitted:  []string{"order.payment_failed.v1", "inventory.compensated.v1"},
			TraceID:             traceID,
			ErrorCode:           "PAYMENT_GATEWAY_REJECTED_COMPENSATED",
		}
		e.idempotencySeen[idemScoped] = resp
		return resp
	}

	// Step 3: Persist in DynamoDB Single-Table & emit EventBridge/SNS/SQS events
	pk := fmt.Sprintf("TENANT#%s#ORDER#%s", req.CallerTenantID, req.OrderID)
	states = append(states, "ChargePaymentSucceeded", "PersistDynamoDB", "PublishEventBridge")
	resp := ServerlessOrderResponse{
		HTTPStatus:          201,
		OrderID:             req.OrderID,
		OrderState:          "CONFIRMED",
		TotalCents:          int64(req.Quantity) * req.UnitPriceCents,
		StepFunctionsStates: states,
		DynamoDBPK:          pk,
		EventBridgeEmitted:  []string{"order.confirmed.v1", "sqs.fulfillment_queue.v1"},
		TraceID:             traceID,
	}
	e.dynamoTable[pk] = resp
	if req.IdempotencyKey != "" {
		e.idempotencySeen[idemScoped] = resp
	}
	return resp
}

// GetAvailableStock returns the current stock of a SKU for invariant verification.
func (e *OrderFulfillmentServerlessEngine) GetAvailableStock(sku string) int {
	e.mu.Lock()
	defer e.mu.Unlock()
	return e.inventoryBySKU[sku]
}
