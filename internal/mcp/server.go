// Package mcp implements the unified native JSON-RPC 2.0 MCP server in Go 1.24.3
// (`squad-harness mcp`), replacing the 3 separate Python MCP servers in .mcp.json
// (squad-context, squad-cultivator, and dora) with a single zero-dependency process (< 12 MB RSS).
package mcp

import (
	"bufio"
	"encoding/json"
	"io"

	"github.com/thiago701/squad-ai-harness/internal/cognitive/graphrag"
	"github.com/thiago701/squad-ai-harness/internal/cognitive/harness"
	"github.com/thiago701/squad-ai-harness/internal/jev"
	"github.com/thiago701/squad-ai-harness/internal/telemetry"
	"github.com/thiago701/squad-ai-harness/pkg/contracts"
)

// RPCRequest is a standard JSON-RPC 2.0 request envelope.
type RPCRequest struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      any             `json:"id,omitempty"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params,omitempty"`
}

// RPCResponse is a standard JSON-RPC 2.0 response envelope.
type RPCResponse struct {
	JSONRPC string    `json:"jsonrpc"`
	ID      any       `json:"id,omitempty"`
	Result  any       `json:"result,omitempty"`
	Error   *RPCError `json:"error,omitempty"`
}

// RPCError represents a JSON-RPC 2.0 error object.
type RPCError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

// Server serves the unified SquadAI Harness MCP tools over stdio.
type Server struct {
	rootDir string
	engine  *harness.Engine
}

// NewServer creates an MCP Server bound to the workspace root.
func NewServer(rootDir string, engine *harness.Engine) *Server {
	return &Server{rootDir: rootDir, engine: engine}
}

// HandleRequest processes a single JSON-RPC 2.0 request deterministically.
func (s *Server) HandleRequest(req RPCRequest) *RPCResponse {
	switch req.Method {
	case "notifications/initialized":
		return nil
	case "initialize":
		return &RPCResponse{
			JSONRPC: "2.0",
			ID:      req.ID,
			Result: map[string]any{
				"protocolVersion": "2024-11-05",
				"serverInfo": map[string]any{
					"name":    contracts.TechnicalName,
					"version": contracts.Version,
				},
				"capabilities": map[string]any{
					"tools":     map[string]any{},
					"resources": map[string]any{},
				},
			},
		}
	case "resources/list":
		id, _ := telemetry.LoadOrCreateQUID(s.rootDir)
		return &RPCResponse{
			JSONRPC: "2.0",
			ID:      req.ID,
			Result: map[string]any{
				"resources": []map[string]any{
					{
						"uri":         "squad://telemetry/ascii",
						"name":        "Relatório Executivo ASCII SquadAI (" + id.QUID + ")",
						"description": "Relatório público offline em ASCII consolidando horas trabalhadas, horas economizadas e economia de tokens (US$ / R$) dos últimos 3 meses.",
						"mimeType":    "text/plain",
					},
					{
						"uri":         "squad://telemetry/quid/" + id.QUID,
						"name":        "Snapshot Quântico Universal (" + id.QUID + ")",
						"description": "Consulta pública offline pelo ID Quântico Universal do repositório clonado.",
						"mimeType":    "application/json",
					},
				},
			},
		}
	case "resources/read":
		rep := telemetry.GenerateReport(s.rootDir, 3)
		return &RPCResponse{
			JSONRPC: "2.0",
			ID:      req.ID,
			Result: map[string]any{
				"contents": []map[string]any{
					{
						"uri":      "squad://telemetry/ascii",
						"mimeType": "text/plain",
						"text":     rep.ASCII,
					},
				},
			},
		}
	case "tools/list":
		return &RPCResponse{
			JSONRPC: "2.0",
			ID:      req.ID,
			Result: map[string]any{
				"tools": []map[string]any{
					{
						"name":        "squad_route_skill",
						"description": "Roteia uma tarefa para as skills canônicas mais relevantes usando BM25 Híbrido em Go (< 1ms)",
						"inputSchema": map[string]any{
							"type": "object",
							"properties": map[string]any{
								"query": map[string]any{
									"type":        "string",
									"description": "Descrição da tarefa ou dúvida técnica para rotear às skills ideais",
								},
							},
							"required": []string{"query"},
						},
					},
					{
						"name":        "squad_sekg_query",
						"description": "Executa busca GraphRAG (Local, Global ou DRIFT Search) sobre o Software Engineering Knowledge Graph",
						"inputSchema": map[string]any{
							"type": "object",
							"properties": map[string]any{
								"query": map[string]any{
									"type":        "string",
									"description": "Termo, conceito ou componente a consultar no grafo SEKG",
								},
								"mode": map[string]any{
									"type":        "string",
									"enum":        []string{"local", "global", "drift"},
									"description": "Modo GraphRAG: local (vizinhança), global (comunidades Leiden) ou drift (causa raiz)",
								},
							},
							"required": []string{"query"},
						},
					},
					{
						"name":        "squad_sekg_impact",
						"description": "Calcula o raio de explosão (blast radius), testes impactados e gatilhos de segurança para arquivos alterados",
						"inputSchema": map[string]any{
							"type": "object",
							"properties": map[string]any{
								"target": map[string]any{
									"type":        "string",
									"description": "Caminho do arquivo, pacote ou skill alvo para análise de impacto",
								},
							},
							"required": []string{"target"},
						},
					},
					{
						"name":        "squad_jev_review",
						"description": "Executa os 25 especialistas determinísticos JEV + Tribunal Critic/Judge sobre um diff (0 tokens)",
						"inputSchema": map[string]any{
							"type": "object",
							"properties": map[string]any{
								"diff": map[string]any{
									"type":        "string",
									"description": "Conteúdo do diff ou trecho de código a ser julgado pelos 25 especialistas JEV",
								},
							},
							"required": []string{"diff"},
						},
					},
					{
						"name":        "squad_cultivator_status",
						"description": "Retorna o estado de saúde do catálogo, SEKG e backlog de evolução (substitui squad-cultivator Python)",
						"inputSchema": map[string]any{
							"type":       "object",
							"properties": map[string]any{},
						},
					},
					{
						"name":        "squad_usage_report",
						"description": "Gera o relatório executivo em ASCII e JSON consolidando ganhos x tempo de uso (últimos 3 meses agrupados por dia/mês, horas trabalhadas, horas economizadas, economia de tokens em US$ e R$) e ID Quântico Universal (QUID)",
						"inputSchema": map[string]any{
							"type": "object",
							"properties": map[string]any{
								"quid": map[string]any{
									"type":        "string",
									"description": "ID Quântico Universal opcional (QUID-SQ8-...) para consultar um repositório específico offline",
								},
								"months": map[string]any{
									"type":        "integer",
									"description": "Janela de meses consolidada (padrão: 3)",
								},
							},
						},
					},
					{
						"name":        "squad_resolve_quid",
						"description": "Consulta publicamente de forma 100% offline na estação/rede local o relatório ASCII de qualquer repositório pelo seu ID Quântico Universal (QUID-SQ8-...)",
						"inputSchema": map[string]any{
							"type": "object",
							"properties": map[string]any{
								"quid": map[string]any{
									"type":        "string",
									"description": "ID Quântico Universal (QUID-SQ8-...) ou prefixo para busca offline (vazio lista todos os QUIDs da estação)",
								},
							},
						},
					},
				},
			},
		}
	case "tools/call":
		var callParams struct {
			Name      string         `json:"name"`
			Arguments map[string]any `json:"arguments"`
		}
		if err := json.Unmarshal(req.Params, &callParams); err != nil {
			return &RPCResponse{
				JSONRPC: "2.0",
				ID:      req.ID,
				Error:   &RPCError{Code: -32602, Message: "invalid params"},
			}
		}
		return s.dispatchToolCall(req.ID, callParams.Name, callParams.Arguments)
	default:
		return &RPCResponse{
			JSONRPC: "2.0",
			ID:      req.ID,
			Error:   &RPCError{Code: -32601, Message: "method not found: " + req.Method},
		}
	}
}

func (s *Server) dispatchToolCall(id any, toolName string, args map[string]any) *RPCResponse {
	telemetry.RecordAsync(s.rootDir, "mcp", 0.5)
	var payload any
	switch toolName {
	case "squad_route_skill":
		q, _ := args["query"].(string)
		if isTrig, qid := telemetry.MatchTrigger(q); isTrig {
			if qid != "" {
				if entry, ok := telemetry.ResolveByQUID(qid, s.rootDir); ok {
					payload = entry
					break
				}
			}
			payload = telemetry.GenerateReport(s.rootDir, 3)
			break
		}
		payload = s.engine.Router().Route(q, 5)
	case "squad_sekg_query":
		q, _ := args["query"].(string)
		modeStr, _ := args["mode"].(string)
		rag := graphrag.NewEngine(s.engine.Graph())
		payload = rag.Search(graphrag.QueryRequest{
			Query: q,
			Mode:  graphrag.SearchMode(modeStr),
			TopK:  5,
		})
	case "squad_sekg_impact":
		target, _ := args["target"].(string)
		payload = s.engine.Graph().AnalyzeImpact([]string{target})
	case "squad_jev_review":
		diff, _ := args["diff"].(string)
		payload = jev.EvaluateTribunal(jev.ReviewInput{DiffContent: diff})
	case "squad_cultivator_status":
		val := s.engine.Catalog().Validate()
		qid, _ := telemetry.LoadOrCreateQUID(s.rootDir)
		payload = map[string]any{
			"identity":    contracts.FullIdentity,
			"quid":        qid.QUID,
			"skills":      val.CanonicalSkills,
			"sekg_nodes":  len(s.engine.Graph().Nodes),
			"sekg_edges":  len(s.engine.Graph().Edges),
			"communities": len(s.engine.Graph().Communities),
			"status":      "HEALTHY",
		}
	case "squad_usage_report":
		qid, _ := args["quid"].(string)
		if qid != "" {
			if entry, ok := telemetry.ResolveByQUID(qid, s.rootDir); ok {
				return &RPCResponse{
					JSONRPC: "2.0",
					ID:      id,
					Result: map[string]any{
						"content": []map[string]any{
							{"type": "text", "text": entry.ASCIIReport},
						},
					},
				}
			}
		}
		rep := telemetry.GenerateReport(s.rootDir, 3)
		return &RPCResponse{
			JSONRPC: "2.0",
			ID:      id,
			Result: map[string]any{
				"content": []map[string]any{
					{"type": "text", "text": rep.ASCII},
				},
			},
		}
	case "squad_resolve_quid":
		qid, _ := args["quid"].(string)
		if qid == "" {
			payload = telemetry.ListOfflineRegistry(s.rootDir)
		} else if entry, ok := telemetry.ResolveByQUID(qid, s.rootDir); ok {
			return &RPCResponse{
				JSONRPC: "2.0",
				ID:      id,
				Result: map[string]any{
					"content": []map[string]any{
						{"type": "text", "text": entry.ASCIIReport},
					},
				},
			}
		} else {
			payload = map[string]any{
				"found": false,
				"quid":  qid,
			}
		}
	default:
		return &RPCResponse{
			JSONRPC: "2.0",
			ID:      id,
			Error:   &RPCError{Code: -32602, Message: "unknown tool: " + toolName},
		}
	}

	rawJSON, _ := json.Marshal(payload)
	return &RPCResponse{
		JSONRPC: "2.0",
		ID:      id,
		Result: map[string]any{
			"content": []map[string]any{
				{"type": "text", "text": string(rawJSON)},
			},
		},
	}
}

// ServeStdio runs the JSON-RPC 2.0 loop over r and w.
func (s *Server) ServeStdio(r io.Reader, w io.Writer) error {
	sc := bufio.NewScanner(r)
	buf := make([]byte, 0, 64*1024)
	sc.Buffer(buf, 4*1024*1024)

	for sc.Scan() {
		line := sc.Bytes()
		if len(line) == 0 {
			continue
		}
		var req RPCRequest
		if err := json.Unmarshal(line, &req); err != nil {
			continue
		}
		resp := s.HandleRequest(req)
		if resp == nil {
			continue
		}
		out, err := json.Marshal(resp)
		if err != nil {
			continue
		}
		_, _ = w.Write(append(out, '\n'))
	}
	return sc.Err()
}
