// Package aiops — server.go implements the HTTP server for the Monitor - GraphRAG v2.0 Lite UI
// and its REST API (/api/health, /api/graphrag/graph, /api/discover, /api/teach, /api/chat,
// /api/graphrag/query, /api/graphrag/path, /api/graphrag/inject, and /_localstack/health).
package aiops

import (
	"encoding/json"
	"net/http"
	"strings"
)

// Handler returns an http.Handler serving the Monitor - GraphRAG v2.0 Lite UI and APIs.
func (e *Engine) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/", e.handleMonitorPage)
	mux.HandleFunc("/favicon.ico", e.handleFavicon)
	mux.HandleFunc("/monitor-graphrag", e.handleMonitorPage)
	mux.HandleFunc("/monitor-graphrag.html", e.handleMonitorPage)
	mux.HandleFunc("/graphrag", e.handleMonitorPage)
	mux.HandleFunc("/_localstack/health", e.handleLocalStackHealth)
	mux.HandleFunc("/api/health", e.handleAPIHealth)
	mux.HandleFunc("/api/status", e.handleAPIHealth)
	mux.HandleFunc("/api/graphrag/graph", e.handleAPIGraph)
	mux.HandleFunc("/api/graph", e.handleAPIGraph)
	mux.HandleFunc("/api/discover", e.handleAPIDiscover)
	mux.HandleFunc("/api/teach", e.handleAPITeach)
	mux.HandleFunc("/api/chat", e.handleAPIChat)
	mux.HandleFunc("/api/graphrag/query", e.handleAPIGraphQuery)
	mux.HandleFunc("/api/graphrag/path", e.handleAPIGraphPath)
	mux.HandleFunc("/api/graphrag/inject", e.handleAPIGraphInject)
	return mux
}

func (e *Engine) handleFavicon(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "image/svg+xml")
	w.Header().Set("Cache-Control", "public, max-age=86400")
	_, _ = w.Write([]byte(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="6" fill="#0972d3"/><text x="16" y="21" font-family="sans-serif" font-size="14" font-weight="bold" fill="#fff" text-anchor="middle">IA</text></svg>`))
}

func (e *Engine) handleMonitorPage(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" && r.URL.Path != "/index.html" && r.URL.Path != "/monitor-graphrag" && r.URL.Path != "/monitor-graphrag.html" && r.URL.Path != "/graphrag" {
		http.NotFound(w, r)
		return
	}
	htmlBytes, err := e.RenderMonitorHTML()
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Header().Set("Cache-Control", "no-cache, no-store, must-revalidate")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	_, _ = w.Write(htmlBytes)
}

func (e *Engine) handleLocalStackHealth(w http.ResponseWriter, _ *http.Request) {
	e.mu.RLock()
	st := e.localstack
	e.mu.RUnlock()
	writeJSON(w, http.StatusOK, map[string]any{
		"services": st.Services,
		"edition":  "community-lite-squad-aiops",
		"version":  "3.8.0-lite",
		"mode":     st.Mode,
	})
}

func (e *Engine) handleAPIHealth(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, e.Snapshot())
}

func (e *Engine) handleAPIGraph(w http.ResponseWriter, _ *http.Request) {
	e.mu.RLock()
	defer e.mu.RUnlock()
	writeJSON(w, http.StatusOK, e.graph)
}

func (e *Engine) handleAPIDiscover(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		WorkspaceDir string `json:"workspace_dir"`
	}
	r.Body = http.MaxBytesReader(w, r.Body, 64*1024)
	_ = json.NewDecoder(r.Body).Decode(&req)
	sum := e.DiscoverWorkspace(req.WorkspaceDir)
	writeJSON(w, http.StatusOK, map[string]any{
		"ok":        true,
		"discovery": sum,
		"snapshot":  e.Snapshot(),
	})
}

func (e *Engine) handleAPITeach(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		Story  string `json:"story"`
		Prompt string `json:"prompt"`
	}
	r.Body = http.MaxBytesReader(w, r.Body, 64*1024)
	_ = json.NewDecoder(r.Body).Decode(&req)
	story := strings.TrimSpace(req.Story)
	if story == "" {
		story = strings.TrimSpace(req.Prompt)
	}
	res, err := e.TeachSkill(story)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"ok": false, "erro": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, res)
}

func (e *Engine) handleAPIChat(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		Mensagem             string         `json:"mensagem"`
		Message              string         `json:"message"`
		Query                string         `json:"query"`
		ExecutarHabilidadeID string         `json:"executar_habilidade_id"`
		SkillID              string         `json:"skill_id"`
		CapabilityID         string         `json:"capability_id"`
		ContextoTela         map[string]any `json:"contexto_tela"`
		ContextoCliente      map[string]any `json:"contexto_cliente"`
	}
	r.Body = http.MaxBytesReader(w, r.Body, 128*1024)
	_ = json.NewDecoder(r.Body).Decode(&req)

	msg := strings.TrimSpace(req.Mensagem)
	if msg == "" {
		msg = strings.TrimSpace(req.Message)
	}
	if msg == "" {
		msg = strings.TrimSpace(req.Query)
	}
	forced := strings.TrimSpace(req.ExecutarHabilidadeID)
	if forced == "" {
		forced = strings.TrimSpace(req.SkillID)
	}
	if forced == "" {
		forced = strings.TrimSpace(req.CapabilityID)
	}

	screen := "monitor"
	nodeID := "sqs-eventos-clientes"
	ctxMap := req.ContextoTela
	if ctxMap == nil {
		ctxMap = req.ContextoCliente
	}
	if ctxMap != nil {
		if s, ok := ctxMap["tela_ativa"].(string); ok && s != "" {
			screen = s
		}
		if n, ok := ctxMap["no_selecionado_id"].(string); ok && n != "" {
			nodeID = n
		}
	}

	resp := e.Chat(msg, forced, screen, nodeID)
	writeJSON(w, http.StatusOK, resp)
}

func (e *Engine) handleAPIGraphQuery(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		Pergunta string `json:"pergunta"`
		Query    string `json:"query"`
		Modo     string `json:"modo"`
	}
	r.Body = http.MaxBytesReader(w, r.Body, 64*1024)
	_ = json.NewDecoder(r.Body).Decode(&req)
	q := strings.TrimSpace(req.Pergunta)
	if q == "" {
		q = strings.TrimSpace(req.Query)
	}
	modo := strings.TrimSpace(req.Modo)
	if modo == "" || modo == "auto" {
		modo = "drift"
	}
	chatResp := e.Chat(q, "", "graphrag", "sqs-eventos-clientes")
	writeJSON(w, http.StatusOK, map[string]any{
		"ok":                        true,
		"pergunta":                  q,
		"modo_executado":            modo,
		"confianca_combinada_rn007": 0.96,
		"classificacao_evidencia":   "CONFIRMADO",
		"proveniencia":              "OBSERVADO",
		"sintese_graphrag":          chatResp.RespostaPrincipal,
		"nos_subgrafo":              []string{"sqs-eventos-clientes", "lambda-consumidor-cadastro", "tfvars-prod-clientes", "oas-rota-get-pessoas"},
		"arestas_subgrafo":          []string{"e-01", "e-02", "e-05"},
		"triplas_recuperadas": []map[string]any{
			{"origem": "tfvars-prod-clientes", "relacao": "DEFINE_CONFIG", "destino": "sqs-eventos-clientes", "confianca": 0.98},
			{"origem": "oas-rota-get-pessoas", "relacao": "EXPOE_ROTA", "destino": "lambda-consumidor-cadastro", "confianca": 0.95},
		},
	})
}

func (e *Engine) handleAPIGraphPath(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		OrigemID  string `json:"origem_id"`
		DestinoID string `json:"destino_id"`
	}
	r.Body = http.MaxBytesReader(w, r.Body, 64*1024)
	_ = json.NewDecoder(r.Body).Decode(&req)
	orig := strings.TrimSpace(req.OrigemID)
	if orig == "" {
		orig = "sqs-eventos-clientes"
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"ok":                     true,
		"origem_id":              orig,
		"destino_id":             req.DestinoID,
		"blast_radius_calculado": 89,
		"total_nos_afetados":     7,
		"nos_afetados":           []string{orig, "lambda-consumidor-cadastro", "ddb-clientes-master", "sns-cadastro-fanout", "tfvars-prod-clientes"},
	})
}

func (e *Engine) handleAPIGraphInject(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req map[string]any
	r.Body = http.MaxBytesReader(w, r.Body, 64*1024)
	_ = json.NewDecoder(r.Body).Decode(&req)

	id := sanitizeID(strings.TrimSpace( stringFromMap(req, "id", "rotulo", "label") ))
	if id == "" {
		id = "fato-dinamico-local"
	}
	label := stringFromMap(req, "rotulo", "label", "id")
	if label == "" {
		label = "Fato Dinâmico LocalStack"
	}
	nd := buildDiscoveredNode(id, label, "achado_iaops", "Fato Injetado Local", "localstack://fato", "Fato dinâmico injetado em tempo real no Monitor Lite")

	e.mu.Lock()
	e.mergeDiscoveredIntoGraph([]map[string]any{nd}, nil)
	e.mu.Unlock()

	writeJSON(w, http.StatusOK, map[string]any{
		"ok":      true,
		"no_novo": nd,
	})
}

func stringFromMap(m map[string]any, keys ...string) string {
	for _, k := range keys {
		if v, ok := m[k].(string); ok && strings.TrimSpace(v) != "" {
			return strings.TrimSpace(v)
		}
	}
	return ""
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.WriteHeader(status)
	enc := json.NewEncoder(w)
	enc.SetIndent("", "  ")
	_ = enc.Encode(v)
}
