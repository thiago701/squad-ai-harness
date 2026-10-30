// Package graphrag implements the Microsoft GraphRAG query strategies adapted for
// Software Engineering in Go 1.24.3: Local Search (entity neighborhood + CSR expansion),
// Global Search (Map-Reduce over Leiden Community Reports with Dynamic Community Selection),
// and DRIFT Search (Dynamic Reasoning and Inference with Flexible Traversal).
package graphrag

import (
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/thiago701/squad-ai-harness/internal/cognitive/sekg"
	"github.com/thiago701/squad-ai-harness/pkg/contracts"
)

// SearchMode identifies the GraphRAG retrieval algorithm.
type SearchMode string

const (
	ModeLocal  SearchMode = "LOCAL_SEARCH"
	ModeGlobal SearchMode = "GLOBAL_SEARCH"
	ModeDRIFT  SearchMode = "DRIFT_SEARCH"
)

// QueryRequest defines a GraphRAG retrieval request.
type QueryRequest struct {
	Query             string                `json:"query"`
	Mode              SearchMode            `json:"mode"`
	BudgetTier        contracts.ContextTier `json:"budget_tier"`
	IncludeHypotheses bool                  `json:"include_hypotheses"`
	TopK              int                   `json:"top_k"`
}

// QueryResponse captures the structured GraphRAG retrieval result.
type QueryResponse struct {
	Mode               SearchMode             `json:"mode"`
	MatchedEntities    []sekg.NodeRecord      `json:"matched_entities,omitempty"`
	ExpandedRelations  []string               `json:"expanded_relations,omitempty"`
	CommunitySummaries []sekg.CommunityReport `json:"community_summaries,omitempty"`
	FollowUpHierarchy  []DRIFTStep            `json:"follow_up_hierarchy,omitempty"`
	SynthesizedContext string                 `json:"synthesized_context"`
	Confidence         float64                `json:"confidence"`
	DurationUs         int64                  `json:"duration_us"`
}

// DRIFTStep represents a single Primer/Follow-Up node in DRIFT Search.
type DRIFTStep struct {
	SubQuery   string   `json:"sub_query"`
	Findings   []string `json:"findings"`
	Confidence float64  `json:"confidence"`
}

// Engine executes hybrid GraphRAG queries over an in-memory SEKG.
type Engine struct {
	graph *sekg.GraphCSR
}

// NewEngine creates a GraphRAG query engine bound to a GraphCSR instance.
func NewEngine(g *sekg.GraphCSR) *Engine {
	return &Engine{graph: g}
}

// Search automatically selects or executes the requested GraphRAG search mode.
func (e *Engine) Search(req QueryRequest) QueryResponse {
	if req.TopK <= 0 {
		req.TopK = 6
	}
	if req.BudgetTier == "" {
		req.BudgetTier = contracts.Ctx2
	}
	mode := req.Mode
	if mode == "" {
		mode = ClassifySearchMode(req.Query)
	}

	switch mode {
	case ModeGlobal:
		return e.GlobalSearch(req)
	case ModeDRIFT:
		return e.DRIFTSearch(req)
	default:
		return e.LocalSearch(req)
	}
}

// ClassifySearchMode deterministically selects Local, Global, or DRIFT search from query intent.
func ClassifySearchMode(query string) SearchMode {
	lower := strings.ToLower(query)
	for _, kw := range []string{"global", "visao geral", "panorama", "comunidades", "temas", "arquitetura geral", "riscos gerais"} {
		if strings.Contains(lower, kw) {
			return ModeGlobal
		}
	}
	for _, kw := range []string{"causa raiz", "por que", "investigue", "drift", "cadeia de impacto", "multi-hop"} {
		if strings.Contains(lower, kw) {
			return ModeDRIFT
		}
	}
	return ModeLocal
}

// LocalSearch identifies access-point entities by lexical/semantic match and expands their 1-hop/2-hop
// neighborhood in the CSR graph, filtering out quarantined hypotheses unless explicitly requested.
func (e *Engine) LocalSearch(req QueryRequest) QueryResponse {
	t0 := time.Now()
	g := e.graph
	if len(g.FwdOffsets) != len(g.Nodes)+1 {
		g.BuildCSR()
	}

	qTerms := extractTerms(req.Query)
	type scoredNode struct {
		idx   uint32
		score float64
	}
	var candidates []scoredNode

	for i, nd := range g.Nodes {
		if !req.IncludeHypotheses && nd.Trust == contracts.TrustHypothesis {
			continue
		}
		sc := scoreNodeMatch(nd, qTerms)
		if sc > 0 {
			candidates = append(candidates, scoredNode{idx: uint32(i), score: sc})
		}
	}

	sort.Slice(candidates, func(i, j int) bool {
		if candidates[i].score == candidates[j].score {
			return g.Nodes[candidates[i].idx].Degree > g.Nodes[candidates[j].idx].Degree
		}
		return candidates[i].score > candidates[j].score
	})

	if len(candidates) > req.TopK {
		candidates = candidates[:req.TopK]
	}

	var entities []sekg.NodeRecord
	var relations []string
	commSeen := make(map[uint32]bool)
	var commReports []sekg.CommunityReport

	for _, c := range candidates {
		u := c.idx
		nd := g.Nodes[u]
		entities = append(entities, nd)
		commSeen[nd.CommunityL0] = true

		// Expand 1-hop outgoing edges
		for p := g.FwdOffsets[u]; p < g.FwdOffsets[u+1] && len(relations) < req.TopK*3; p++ {
			v := g.FwdTargets[p]
			edge := g.Edges[g.FwdEdgeIdxs[p]]
			if !req.IncludeHypotheses && edge.Trust == contracts.TrustHypothesis {
				continue
			}
			relations = append(relations, nd.Title+" --["+string(edge.RelType)+"]--> "+g.Nodes[v].Title)
		}
		// Expand 1-hop incoming edges
		for p := g.RevOffsets[u]; p < g.RevOffsets[u+1] && len(relations) < req.TopK*4; p++ {
			v := g.RevSources[p]
			edge := g.Edges[g.RevEdgeIdxs[p]]
			if !req.IncludeHypotheses && edge.Trust == contracts.TrustHypothesis {
				continue
			}
			relations = append(relations, g.Nodes[v].Title+" --["+string(edge.RelType)+"]--> "+nd.Title)
		}
	}

	for _, cr := range g.Communities {
		if commSeen[cr.CommunityID] {
			commReports = append(commReports, cr)
		}
	}

	var sb strings.Builder
	sb.WriteString("[GraphRAG Local Search] Entidades recuperadas: ")
	for i, en := range entities {
		if i > 0 {
			sb.WriteString(", ")
		}
		sb.WriteString(en.Title + " (" + string(en.Kind) + ")")
	}
	if len(relations) > 0 {
		sb.WriteString(" | Relações: " + strings.Join(relations, "; "))
	}

	conf := 0.88
	if len(entities) == 0 {
		conf = 0.20
	}

	return QueryResponse{
		Mode:               ModeLocal,
		MatchedEntities:    entities,
		ExpandedRelations:  relations,
		CommunitySummaries: commReports,
		SynthesizedContext: sb.String(),
		Confidence:         conf,
		DurationUs:         time.Since(t0).Microseconds(),
	}
}

// GlobalSearch executes Map-Reduce over Leiden Community Reports with Dynamic Community Selection.
func (e *Engine) GlobalSearch(req QueryRequest) QueryResponse {
	t0 := time.Now()
	g := e.graph
	if len(g.Communities) == 0 {
		g.DetectLeidenCommunities()
	}

	qTerms := extractTerms(req.Query)
	type scoredComm struct {
		report sekg.CommunityReport
		score  float64
	}
	scored := make([]scoredComm, len(g.Communities))

	// Map phase in parallel goroutines over Community Reports
	var wg sync.WaitGroup
	for i, cr := range g.Communities {
		wg.Add(1)
		go func(idx int, rep sekg.CommunityReport) {
			defer wg.Done()
			relevance := rep.Rating
			lowerText := strings.ToLower(rep.Title + " " + rep.Summary + " " + strings.Join(rep.KeyEntities, " "))
			for _, t := range qTerms {
				if strings.Contains(lowerText, t) {
					relevance += 25.0
				}
			}
			scored[idx] = scoredComm{report: rep, score: relevance}
		}(i, cr)
	}
	wg.Wait()

	// Reduce phase: sort by importance rating and select top-K communities
	sort.Slice(scored, func(i, j int) bool {
		return scored[i].score > scored[j].score
	})

	limit := req.TopK
	if limit > len(scored) {
		limit = len(scored)
	}
	selected := make([]sekg.CommunityReport, 0, limit)
	var summaries []string
	for i := 0; i < limit; i++ {
		selected = append(selected, scored[i].report)
		summaries = append(summaries, scored[i].report.Title+": "+scored[i].report.Summary)
	}

	return QueryResponse{
		Mode:               ModeGlobal,
		CommunitySummaries: selected,
		SynthesizedContext: "[GraphRAG Global Search] " + strings.Join(summaries, " || "),
		Confidence:         0.92,
		DurationUs:         time.Since(t0).Microseconds(),
	}
}

// DRIFTSearch combines Global Primer over top communities with parallel Local Search Follow-Ups.
func (e *Engine) DRIFTSearch(req QueryRequest) QueryResponse {
	t0 := time.Now()
	// Phase A — Primer (Global top-3 communities)
	globalRes := e.GlobalSearch(QueryRequest{
		Query:      req.Query,
		Mode:       ModeGlobal,
		BudgetTier: req.BudgetTier,
		TopK:       3,
	})

	// Generate follow-up sub-queries from the key entities of the top communities
	var followUpQueries []string
	followUpQueries = append(followUpQueries, req.Query)
	for _, comm := range globalRes.CommunitySummaries {
		if len(comm.KeyEntities) > 0 {
			followUpQueries = append(followUpQueries, comm.KeyEntities[0])
		}
	}

	// Phase B — Parallel Local Follow-Ups
	steps := make([]DRIFTStep, len(followUpQueries))
	var wg sync.WaitGroup
	for i, fq := range followUpQueries {
		wg.Add(1)
		go func(idx int, subQ string) {
			defer wg.Done()
			loc := e.LocalSearch(QueryRequest{
				Query:             subQ,
				Mode:              ModeLocal,
				IncludeHypotheses: req.IncludeHypotheses,
				TopK:              3,
			})
			steps[idx] = DRIFTStep{
				SubQuery:   subQ,
				Findings:   loc.ExpandedRelations,
				Confidence: loc.Confidence,
			}
		}(i, fq)
	}
	wg.Wait()

	// Phase C — Output Hierarchy
	primaryLocal := e.LocalSearch(req)
	return QueryResponse{
		Mode:               ModeDRIFT,
		MatchedEntities:    primaryLocal.MatchedEntities,
		ExpandedRelations:  primaryLocal.ExpandedRelations,
		CommunitySummaries: globalRes.CommunitySummaries,
		FollowUpHierarchy:  steps,
		SynthesizedContext: globalRes.SynthesizedContext + " => " + primaryLocal.SynthesizedContext,
		Confidence:         0.94,
		DurationUs:         time.Since(t0).Microseconds(),
	}
}

func extractTerms(q string) []string {
	fields := strings.Fields(strings.ToLower(q))
	var out []string
	for _, f := range fields {
		clean := strings.Trim(f, ".,;:!?()[]{}\"'")
		if len(clean) >= 2 {
			out = append(out, clean)
		}
	}
	return out
}

func scoreNodeMatch(nd sekg.NodeRecord, terms []string) float64 {
	if len(terms) == 0 {
		return float64(nd.Degree) * 0.1
	}
	titleLow := strings.ToLower(nd.Title)
	idLow := strings.ToLower(nd.ID)
	sumLow := strings.ToLower(nd.Summary)
	score := 0.0
	for _, t := range terms {
		if titleLow == t || idLow == t {
			score += 10.0
		} else if strings.Contains(titleLow, t) || strings.Contains(idLow, t) {
			score += 5.0
		}
		if strings.Contains(sumLow, t) {
			score += 1.5
		}
	}
	if score > 0 && nd.Trust == contracts.TrustVerified {
		score *= 1.25
	}
	return score
}
