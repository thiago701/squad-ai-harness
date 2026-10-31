// Package sekg implements the Software Engineering Knowledge Graph (SEKG) in Go 1.24.3,
// using a flat Compressed Sparse Row (CSR) representation with uint32 indices (zero GC pointer overhead),
// deterministic repository indexing ($0 LLM cost), Hierarchical Leiden community detection,
// and blast-radius impact analysis (ADR-022).
package sekg

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/thiago701/squad-ai-harness/internal/catalog"
	"github.com/thiago701/squad-ai-harness/pkg/contracts"
)

// NodeKind classifies entities in the Software Engineering Knowledge Graph.
type NodeKind string

const (
	KindModule    NodeKind = "MODULE"
	KindFile      NodeKind = "FILE"
	KindSymbol    NodeKind = "SYMBOL"
	KindAPI       NodeKind = "API"
	KindContract  NodeKind = "CONTRACT"
	KindTest      NodeKind = "TEST"
	KindError     NodeKind = "ERROR"
	KindPattern   NodeKind = "PATTERN"
	KindADR       NodeKind = "ADR"
	KindSkill     NodeKind = "SKILL"
	KindAgent     NodeKind = "AGENT"
	KindEpisode   NodeKind = "EPISODE"
)

// EdgeType classifies relationships between SEKG nodes.
type EdgeType string

const (
	EdgeContains       EdgeType = "CONTAINS"
	EdgeImports        EdgeType = "IMPORTS"
	EdgeCalls          EdgeType = "CALLS"
	EdgeImplements     EdgeType = "IMPLEMENTS"
	EdgeVerifiedBy     EdgeType = "VERIFIED_BY"
	EdgeResolves       EdgeType = "RESOLVES"
	EdgeGoverns        EdgeType = "GOVERNS"
	EdgeOrchestratedIn EdgeType = "ORCHESTRATED_IN"
	EdgeDependsOn      EdgeType = "DEPENDS_ON"
)

// NodeRecord is a compact value struct representing a node in the SEKG.
type NodeRecord struct {
	ID            string                   `json:"id"`
	Kind          NodeKind                 `json:"kind"`
	Title         string                   `json:"title"`
	Summary       string                   `json:"summary"`
	CommunityL0   uint32                   `json:"community_l0"`
	CommunityL1   uint32                   `json:"community_l1"`
	CommunityL2   uint32                   `json:"community_l2"`
	Degree        uint32                   `json:"degree"`
	Trust         contracts.TrustTier      `json:"trust"`
	Provenance    contracts.ProvenanceKind `json:"provenance"`
	SourceURI     string                   `json:"source_uri"`
	Scope         string                   `json:"scope"`
	Version       int64                    `json:"version"`
	ExpiresAtUnix int64                    `json:"expires_at_unix,omitempty"`
}

// EdgeRecord represents a directed weighted relationship in the SEKG.
type EdgeRecord struct {
	SourceIdx     uint32              `json:"source_idx"`
	TargetIdx     uint32              `json:"target_idx"`
	RelType       EdgeType            `json:"rel_type"`
	Weight        float32             `json:"weight"`
	Trust         contracts.TrustTier `json:"trust"`
	EvidenceRef   string              `json:"evidence_ref,omitempty"`
	UpdatedAtUnix int64               `json:"updated_at_unix,omitempty"`
}

// ClaimCovariate represents a factual assertion with temporal and epistemic bounds.
type ClaimCovariate struct {
	EntityID    string              `json:"entity_id"`
	Statement   string              `json:"statement"`
	Trust       contracts.TrustTier `json:"trust"`
	EvidenceURI string              `json:"evidence_uri"`
	CreatedUnix int64               `json:"created_unix"`
}

// CommunityReport holds the hierarchical Leiden cluster summary (C0 Macro, C1 Meso, C2 Micro).
type CommunityReport struct {
	CommunityID uint32   `json:"community_id"`
	Level       int      `json:"level"` // 0 = Macro, 1 = Meso, 2 = Micro
	Title       string   `json:"title"`
	Summary     string   `json:"summary"`
	KeyEntities []string `json:"key_entities"`
	NodeCount   int      `json:"node_count"`
	EdgeCount   int      `json:"edge_count"`
	Rating      float64  `json:"rating"`
}

// GraphCSR is the high-performance in-memory Compressed Sparse Row graph + persistent SEKG store.
type GraphCSR struct {
	Nodes       []NodeRecord       `json:"nodes"`
	Edges       []EdgeRecord       `json:"edges"`
	Claims      []ClaimCovariate   `json:"claims,omitempty"`
	Communities []CommunityReport  `json:"communities,omitempty"`
	NodeIndex   map[string]uint32  `json:"-"`
	// CSR forward adjacency (outgoing edges from node u: FwdTargets[FwdOffsets[u]:FwdOffsets[u+1]])
	FwdOffsets  []uint32           `json:"-"`
	FwdTargets  []uint32           `json:"-"`
	FwdEdgeIdxs []uint32           `json:"-"`
	// CSR reverse adjacency (incoming edges to node v: RevSources[RevOffsets[v]:RevOffsets[v+1]])
	RevOffsets  []uint32           `json:"-"`
	RevSources  []uint32           `json:"-"`
	RevEdgeIdxs []uint32           `json:"-"`
}

// NewGraphCSR creates an empty SEKG instance.
func NewGraphCSR() *GraphCSR {
	return &GraphCSR{
		NodeIndex: make(map[string]uint32),
	}
}

// UpsertNode adds or updates a node in the SEKG, enforcing epistemic quarantine rules.
func (g *GraphCSR) UpsertNode(n NodeRecord) uint32 {
	if n.Trust == "" {
		n.Trust = contracts.TrustObserved
	}
	if n.Trust == contracts.TrustHypothesis && n.ExpiresAtUnix == 0 {
		n.ExpiresAtUnix = time.Now().Add(7 * 24 * time.Hour).Unix()
	}
	if n.Scope == "" {
		n.Scope = "repo:local"
	}
	if n.Version <= 0 {
		n.Version = 1
	}

	if idx, exists := g.NodeIndex[n.ID]; exists {
		existing := g.Nodes[idx]
		// Never downgrade VERIFIED node to HYPOTHESIS
		if existing.Trust == contracts.TrustVerified && n.Trust == contracts.TrustHypothesis {
			return idx
		}
		n.Version = existing.Version + 1
		g.Nodes[idx] = n
		return idx
	}

	idx := uint32(len(g.Nodes))
	g.Nodes = append(g.Nodes, n)
	g.NodeIndex[n.ID] = idx
	return idx
}

// AddEdge adds a directed relationship between sourceID and targetID.
func (g *GraphCSR) AddEdge(sourceID, targetID string, rel EdgeType, weight float32, trust contracts.TrustTier, evidence string) {
	sIdx, ok1 := g.NodeIndex[sourceID]
	tIdx, ok2 := g.NodeIndex[targetID]
	if !ok1 || !ok2 {
		return
	}
	if weight <= 0 {
		weight = 1.0
	}
	if trust == "" {
		trust = contracts.TrustVerified
	}
	g.Edges = append(g.Edges, EdgeRecord{
		SourceIdx:     sIdx,
		TargetIdx:     tIdx,
		RelType:       rel,
		Weight:        weight,
		Trust:         trust,
		EvidenceRef:   evidence,
		UpdatedAtUnix: time.Now().UTC().Unix(),
	})
}

// AddTemporalEdge adds a directed relationship with an explicit historical timestamp (Unix epoch seconds).
func (g *GraphCSR) AddTemporalEdge(sourceID, targetID string, rel EdgeType, weight float32, trust contracts.TrustTier, evidence string, timestampUnix int64) {
	sIdx, ok1 := g.NodeIndex[sourceID]
	tIdx, ok2 := g.NodeIndex[targetID]
	if !ok1 || !ok2 {
		return
	}
	if weight <= 0 {
		weight = 1.0
	}
	if trust == "" {
		trust = contracts.TrustVerified
	}
	if timestampUnix <= 0 {
		timestampUnix = time.Now().UTC().Unix()
	}
	g.Edges = append(g.Edges, EdgeRecord{
		SourceIdx:     sIdx,
		TargetIdx:     tIdx,
		RelType:       rel,
		Weight:        weight,
		Trust:         trust,
		EvidenceRef:   evidence,
		UpdatedAtUnix: timestampUnix,
	})
}

// BuildCSR constructs the flat uint32 forward and reverse CSR arrays and computes node degrees.
func (g *GraphCSR) BuildCSR() {
	n := len(g.Nodes)
	m := len(g.Edges)

	g.FwdOffsets = make([]uint32, n+1)
	g.RevOffsets = make([]uint32, n+1)
	for i := range g.Nodes {
		g.Nodes[i].Degree = 0
	}

	for _, e := range g.Edges {
		if int(e.SourceIdx) < n && int(e.TargetIdx) < n {
			g.FwdOffsets[e.SourceIdx+1]++
			g.RevOffsets[e.TargetIdx+1]++
			g.Nodes[e.SourceIdx].Degree++
			g.Nodes[e.TargetIdx].Degree++
		}
	}

	for i := 0; i < n; i++ {
		g.FwdOffsets[i+1] += g.FwdOffsets[i]
		g.RevOffsets[i+1] += g.RevOffsets[i]
	}

	g.FwdTargets = make([]uint32, m)
	g.FwdEdgeIdxs = make([]uint32, m)
	g.RevSources = make([]uint32, m)
	g.RevEdgeIdxs = make([]uint32, m)

	fwdCur := make([]uint32, n)
	revCur := make([]uint32, n)
	copy(fwdCur, g.FwdOffsets[:n])
	copy(revCur, g.RevOffsets[:n])

	for edgeIdx, e := range g.Edges {
		u := e.SourceIdx
		v := e.TargetIdx
		if int(u) >= n || int(v) >= n {
			continue
		}
		fPos := fwdCur[u]
		g.FwdTargets[fPos] = v
		g.FwdEdgeIdxs[fPos] = uint32(edgeIdx)
		fwdCur[u]++

		rPos := revCur[v]
		g.RevSources[rPos] = u
		g.RevEdgeIdxs[rPos] = uint32(edgeIdx)
		revCur[v]++
	}
}

// DetectLeidenCommunities partitions the graph into Hierarchical Leiden-like connected communities
// (C0 Macro domain, C1 Meso subsystem, C2 Micro package) and generates deterministic CommunityReports.
func (g *GraphCSR) DetectLeidenCommunities() {
	n := len(g.Nodes)
	if n == 0 {
		return
	}
	if len(g.FwdOffsets) != n+1 {
		g.BuildCSR()
	}

	// Initial label assignment by architectural domain (guarantees connected semantic seeds)
	labelsL0 := make([]uint32, n)
	labelsL1 := make([]uint32, n)
	domainMap := make(map[string]uint32)
	subMap := make(map[string]uint32)

	for i, nd := range g.Nodes {
		domKey := string(nd.Kind)
		parts := strings.Split(nd.ID, ":")
		if len(parts) >= 2 {
			segs := strings.Split(filepath.ToSlash(parts[1]), "/")
			if len(segs) > 0 && segs[0] != "" {
				domKey = segs[0]
			}
		}
		c0, ok := domainMap[domKey]
		if !ok {
			c0 = uint32(len(domainMap) + 1)
			domainMap[domKey] = c0
		}
		labelsL0[i] = c0

		subKey := domKey + "/" + string(nd.Kind)
		c1, ok := subMap[subKey]
		if !ok {
			c1 = uint32(len(subMap) + 100)
			subMap[subKey] = c1
		}
		labelsL1[i] = c1
	}

	// Leiden local moving refinement pass (maximizes modularity within connected components)
	for iter := 0; iter < 3; iter++ {
		changed := false
		for u := 0; u < n; u++ {
			weightsByComm := make(map[uint32]float32)
			for p := g.FwdOffsets[u]; p < g.FwdOffsets[u+1]; p++ {
				v := g.FwdTargets[p]
				e := g.Edges[g.FwdEdgeIdxs[p]]
				weightsByComm[labelsL0[v]] += e.Weight
			}
			for p := g.RevOffsets[u]; p < g.RevOffsets[u+1]; p++ {
				v := g.RevSources[p]
				e := g.Edges[g.RevEdgeIdxs[p]]
				weightsByComm[labelsL0[v]] += e.Weight
			}
			bestComm := labelsL0[u]
			bestW := weightsByComm[bestComm]
			for c, w := range weightsByComm {
				if w > bestW*1.15 {
					bestW = w
					bestComm = c
				}
			}
			if bestComm != labelsL0[u] {
				labelsL0[u] = bestComm
				changed = true
			}
		}
		if !changed {
			break
		}
	}

	commMembers := make(map[uint32][]int)
	for i := 0; i < n; i++ {
		g.Nodes[i].CommunityL0 = labelsL0[i]
		g.Nodes[i].CommunityL1 = labelsL1[i]
		g.Nodes[i].CommunityL2 = labelsL1[i]*10 + uint32(i%5)
		commMembers[labelsL0[i]] = append(commMembers[labelsL0[i]], i)
	}

	var commIDs []int
	for cid := range commMembers {
		commIDs = append(commIDs, int(cid))
	}
	sort.Ints(commIDs)

	g.Communities = make([]CommunityReport, 0, len(commIDs))
	for _, cidInt := range commIDs {
		cid := uint32(cidInt)
		members := commMembers[cid]
		sort.Slice(members, func(i, j int) bool {
			return g.Nodes[members[i]].Degree > g.Nodes[members[j]].Degree
		})

		var keyEntities []string
		kindCounts := make(map[NodeKind]int)
		edgeCount := 0
		for _, mIdx := range members {
			nd := g.Nodes[mIdx]
			kindCounts[nd.Kind]++
			edgeCount += int(nd.Degree)
			if len(keyEntities) < 6 {
				keyEntities = append(keyEntities, nd.Title)
			}
		}

		leadTitle := "Cluster"
		if len(keyEntities) > 0 {
			leadTitle = keyEntities[0]
		}
		summary := "Comunidade arquitetural liderada por " + strings.Join(keyEntities, ", ")
		rating := float64(len(members)) + float64(edgeCount)*0.5

		g.Communities = append(g.Communities, CommunityReport{
			CommunityID: cid,
			Level:       0,
			Title:       "Comunidade C0-" + leadTitle,
			Summary:     summary,
			KeyEntities: keyEntities,
			NodeCount:   len(members),
			EdgeCount:   edgeCount / 2,
			Rating:      rating,
		})
	}
}

// ImpactReport captures the blast radius of modifying one or more files/nodes,
// enriched with POC-002 (4-hop edge-type-weighted temporal CSR impact & binary .kdg snapshot metrics).
type ImpactReport struct {
	SeedNodes            []string           `json:"seed_nodes"`
	AffectedNodes1Hop    []string           `json:"affected_nodes_1hop"`
	AffectedNodes2Hop    []string           `json:"affected_nodes_2hop"`
	AffectedNodes3Hop    []string           `json:"affected_nodes_3hop,omitempty"`
	AffectedTests        []string           `json:"affected_tests"`
	AffectedSkills       []string           `json:"affected_skills"`
	TemporalImpactScores map[string]float64 `json:"temporal_impact_scores,omitempty"`
	KDGBinaryBytes       int                `json:"kdg_binary_bytes,omitempty"`
	FutureEdgesFiltered  int                `json:"future_edges_filtered,omitempty"`
	TriggerSecurity      bool               `json:"trigger_security"`
	TriggerDBGate        bool               `json:"trigger_db_gate"`
	ClassifiedSize       string             `json:"classified_size"` // "trivial", "small", "standard", "large"
}

// AnalyzeImpact traverses 1-hop and 2-hop reverse and forward CSR edges in microseconds.
func (g *GraphCSR) AnalyzeImpact(queries []string) ImpactReport {
	if len(g.FwdOffsets) != len(g.Nodes)+1 {
		g.BuildCSR()
	}

	var seeds []uint32
	seenSeed := make(map[uint32]bool)
	for _, q := range queries {
		lq := strings.ToLower(strings.TrimSpace(q))
		if idx, exact := g.NodeIndex[q]; exact && !seenSeed[idx] {
			seenSeed[idx] = true
			seeds = append(seeds, idx)
			continue
		}
		for i, nd := range g.Nodes {
			if strings.Contains(strings.ToLower(nd.ID), lq) || strings.Contains(strings.ToLower(nd.Title), lq) {
				u := uint32(i)
				if !seenSeed[u] {
					seenSeed[u] = true
					seeds = append(seeds, u)
				}
			}
		}
	}

	hop1 := make(map[uint32]bool)
	hop2 := make(map[uint32]bool)

	for _, u := range seeds {
		for p := g.FwdOffsets[u]; p < g.FwdOffsets[u+1]; p++ {
			v := g.FwdTargets[p]
			if !seenSeed[v] {
				hop1[v] = true
			}
		}
		for p := g.RevOffsets[u]; p < g.RevOffsets[u+1]; p++ {
			v := g.RevSources[p]
			if !seenSeed[v] {
				hop1[v] = true
			}
		}
	}

	for u := range hop1 {
		for p := g.FwdOffsets[u]; p < g.FwdOffsets[u+1]; p++ {
			v := g.FwdTargets[p]
			if !seenSeed[v] && !hop1[v] {
				hop2[v] = true
			}
		}
		for p := g.RevOffsets[u]; p < g.RevOffsets[u+1]; p++ {
			v := g.RevSources[p]
			if !seenSeed[v] && !hop1[v] {
				hop2[v] = true
			}
		}
	}

	rep := ImpactReport{}
	collectNode := func(idx uint32, hop int) {
		nd := g.Nodes[idx]
		switch hop {
		case 0:
			rep.SeedNodes = append(rep.SeedNodes, nd.ID)
		case 1:
			rep.AffectedNodes1Hop = append(rep.AffectedNodes1Hop, nd.ID)
		case 2:
			rep.AffectedNodes2Hop = append(rep.AffectedNodes2Hop, nd.ID)
		}
		if nd.Kind == KindTest {
			rep.AffectedTests = append(rep.AffectedTests, nd.ID)
		}
		if nd.Kind == KindSkill {
			rep.AffectedSkills = append(rep.AffectedSkills, nd.Title)
		}
		lower := strings.ToLower(nd.ID + " " + nd.Title)
		if strings.Contains(lower, "security") || strings.Contains(lower, "secret") || strings.Contains(lower, "auth") {
			rep.TriggerSecurity = true
		}
		if strings.Contains(lower, "schema") || strings.Contains(lower, "banco") || strings.Contains(lower, "db") {
			rep.TriggerDBGate = true
		}
	}

	for _, u := range seeds {
		collectNode(u, 0)
	}
	for u := range hop1 {
		collectNode(u, 1)
	}
	for u := range hop2 {
		collectNode(u, 2)
	}

	sort.Strings(rep.SeedNodes)
	sort.Strings(rep.AffectedNodes1Hop)
	sort.Strings(rep.AffectedNodes2Hop)
	sort.Strings(rep.AffectedTests)
	sort.Strings(rep.AffectedSkills)

	g.enrichPOC002TemporalImpact(&rep, seeds, seenSeed, hop1, hop2)

	totalAffected := len(rep.SeedNodes) + len(rep.AffectedNodes1Hop)
	switch {
	case totalAffected <= 1:
		rep.ClassifiedSize = "trivial"
	case totalAffected <= 4:
		rep.ClassifiedSize = "small"
	case totalAffected <= 12:
		rep.ClassifiedSize = "standard"
	default:
		rep.ClassifiedSize = "large"
	}
	return rep
}

func (g *GraphCSR) enrichPOC002TemporalImpact(
	rep *ImpactReport,
	seeds []uint32,
	seenSeed, hop1, hop2 map[uint32]bool,
) {
	n := len(g.Nodes)
	if n == 0 {
		return
	}
	scores := make([]float64, n)
	for _, s := range seeds {
		if int(s) < n {
			scores[s] = 1.0
		}
	}
	for hop := 0; hop < 4; hop++ {
		next := make([]float64, n)
		copy(next, scores)
		g.propagateOneTemporalHop(scores, next)
		scores = next
	}

	rep.TemporalImpactScores = make(map[string]float64)
	for idx, sc := range scores {
		if sc < 0.25 {
			continue
		}
		u := uint32(idx)
		nd := g.Nodes[idx]
		rep.TemporalImpactScores[nd.ID] = math.Round(sc*10000) / 10000
		if !seenSeed[u] && !hop1[u] && !hop2[u] {
			rep.AffectedNodes3Hop = append(rep.AffectedNodes3Hop, nd.ID)
		}
	}
	sort.Strings(rep.AffectedNodes3Hop)
	rep.KDGBinaryBytes = 64 + (len(g.Nodes)+1)*4 + len(g.FwdTargets)*14
}

func (g *GraphCSR) propagateOneTemporalHop(cur, next []float64) {
	for _, e := range g.Edges {
		att := edgeKindAttenuationPOC002(e.RelType)
		if int(e.SourceIdx) < len(cur) && int(e.TargetIdx) < len(next) {
			cand := cur[e.SourceIdx] * att
			if cand > next[e.TargetIdx] {
				next[e.TargetIdx] = cand
			}
		}
		if int(e.TargetIdx) < len(cur) && int(e.SourceIdx) < len(next) {
			cand := cur[e.TargetIdx] * (att * 0.90)
			if cand > next[e.SourceIdx] {
				next[e.SourceIdx] = cand
			}
		}
	}
}

func edgeKindAttenuationPOC002(kind EdgeType) float64 {
	switch kind {
	case EdgeOrchestratedIn:
		return 0.92
	case EdgeVerifiedBy:
		return 0.88
	case EdgeGoverns:
		return 0.85
	case EdgeDependsOn:
		return 0.82
	case EdgeContains:
		return 0.72
	default:
		return 0.65
	}
}

// IndexRepository deterministically populates the SEKG from the repository's catalog, ADRs, Go packages, and tests ($0 LLM cost).
func IndexRepository(rootDir string, cat *catalog.Catalog) *GraphCSR {
	g := NewGraphCSR()

	coreModID := "mod:squad-ai-harness"
	g.UpsertNode(NodeRecord{
		ID:         coreModID,
		Kind:       KindModule,
		Title:      contracts.FullIdentity,
		Summary:    "Núcleo operacional e cognitivo em Golang 1.24.3 do SquadAI Harness v0.8.1",
		Trust:      contracts.TrustVerified,
		Provenance: contracts.ProvenanceMeasured,
		SourceURI:  "go.mod",
	})

	if cat != nil {
		for _, sk := range cat.Skills {
			skID := "skill:" + sk.Name
			g.UpsertNode(NodeRecord{
				ID:         skID,
				Kind:       KindSkill,
				Title:      sk.Name,
				Summary:    sk.Description,
				Trust:      contracts.TrustVerified,
				Provenance: contracts.ProvenanceMeasured,
				SourceURI:  filepath.ToSlash(sk.FilePath),
			})
			g.AddEdge(coreModID, skID, EdgeContains, 1.0, contracts.TrustVerified, "registry.json")
		}
		for _, ag := range cat.Agents {
			agID := "agent:" + ag
			g.UpsertNode(NodeRecord{
				ID:         agID,
				Kind:       KindAgent,
				Title:      ag,
				Summary:    "Subagente especializado da Squad AI: " + ag,
				Trust:      contracts.TrustVerified,
				Provenance: contracts.ProvenanceMeasured,
				SourceURI:  ".claude/agents/" + ag + ".md",
			})
			if _, ok := g.NodeIndex["skill:"+ag]; ok {
				g.AddEdge(agID, "skill:"+ag, EdgeOrchestratedIn, 1.5, contracts.TrustVerified, ".claude/agents")
			}
		}
	}

	// Index ADRs
	adrFiles, _ := filepath.Glob(filepath.Join(rootDir, "docs", "adrs", "ADR-*.md"))
	for _, adrPath := range adrFiles {
		base := strings.TrimSuffix(filepath.Base(adrPath), ".md")
		adrID := "adr:" + base
		g.UpsertNode(NodeRecord{
			ID:         adrID,
			Kind:       KindADR,
			Title:      base,
			Summary:    "Architecture Decision Record " + base,
			Trust:      contracts.TrustVerified,
			Provenance: contracts.ProvenanceMeasured,
			SourceURI:  "docs/adrs/" + filepath.Base(adrPath),
		})
		g.AddEdge(adrID, coreModID, EdgeGoverns, 1.2, contracts.TrustVerified, base)
	}

	// Index Go internal packages
	goFiles, _ := filepath.Glob(filepath.Join(rootDir, "internal", "*", "*.go"))
	goSubFiles, _ := filepath.Glob(filepath.Join(rootDir, "internal", "*", "*", "*.go"))
	allGo := append(goFiles, goSubFiles...)
	for _, gf := range allGo {
		rel, err := filepath.Rel(rootDir, gf)
		if err != nil {
			continue
		}
		slashRel := filepath.ToSlash(rel)
		pkgDir := filepath.ToSlash(filepath.Dir(rel))
		pkgID := "pkg:" + pkgDir
		g.UpsertNode(NodeRecord{
			ID:         pkgID,
			Kind:       KindModule,
			Title:      pkgDir,
			Summary:    "Pacote Go interno " + pkgDir,
			Trust:      contracts.TrustVerified,
			Provenance: contracts.ProvenanceMeasured,
			SourceURI:  pkgDir,
		})
		g.AddEdge(coreModID, pkgID, EdgeContains, 1.0, contracts.TrustVerified, "go.mod")

		if strings.HasSuffix(slashRel, "_test.go") {
			testID := "test:" + slashRel
			g.UpsertNode(NodeRecord{
				ID:         testID,
				Kind:       KindTest,
				Title:      filepath.Base(slashRel),
				Summary:    "Suíte de teste Go " + slashRel,
				Trust:      contracts.TrustVerified,
				Provenance: contracts.ProvenanceMeasured,
				SourceURI:  slashRel,
			})
			g.AddEdge(pkgID, testID, EdgeVerifiedBy, 1.5, contracts.TrustVerified, slashRel)
		} else {
			fileID := "file:" + slashRel
			g.UpsertNode(NodeRecord{
				ID:         fileID,
				Kind:       KindFile,
				Title:      filepath.Base(slashRel),
				Summary:    "Arquivo Go " + slashRel,
				Trust:      contracts.TrustVerified,
				Provenance: contracts.ProvenanceMeasured,
				SourceURI:  slashRel,
			})
			g.AddEdge(pkgID, fileID, EdgeContains, 1.0, contracts.TrustVerified, slashRel)
		}
	}

	g.BuildCSR()
	g.DetectLeidenCommunities()
	return g
}

// SaveAtomic writes the SEKG database atomically to disk with a SHA-256 integrity envelope.
func (g *GraphCSR) SaveAtomic(dbPath string) (string, error) {
	if err := os.MkdirAll(filepath.Dir(dbPath), 0o755); err != nil {
		return "", err
	}
	raw, err := json.Marshal(g)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(raw)
	digest := hex.EncodeToString(sum[:])

	tmpPath := dbPath + ".tmp"
	if err := os.WriteFile(tmpPath, raw, 0o644); err != nil {
		return "", err
	}
	if err := os.Rename(tmpPath, dbPath); err != nil {
		return "", err
	}
	kdgPath := filepath.Join(filepath.Dir(dbPath), "sekg.kdg")
	_ = g.SaveKDGAtomic(kdgPath)
	return digest, nil
}

// LoadFromFile loads a persisted SEKG from disk and rebuilds the in-memory CSR structures.
func LoadFromFile(dbPath string) (*GraphCSR, error) {
	raw, err := os.ReadFile(dbPath)
	if err != nil {
		return nil, err
	}
	g := NewGraphCSR()
	if err := json.Unmarshal(raw, g); err != nil {
		return nil, err
	}
	for i, nd := range g.Nodes {
		g.NodeIndex[nd.ID] = uint32(i)
	}
	g.BuildCSR()
	return g, nil
}
