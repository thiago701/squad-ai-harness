// Package sekg — Kumo DiskGraph (.kdg) 64-byte aligned binary CSR serializer and
// strict temporal subgraph sampler with 5D RelGT tokenization in 100% pure Go (CGO_ENABLED=0).
// Eliminates GAP-01 (JSON heap overhead and temporal data leakage) without requiring Rust or a GPU.
package sekg

import (
	"encoding/binary"
	"errors"
	"math"
	"os"
	"path/filepath"
	"time"
)

const (
	// KDGMagic identifies the 64-byte aligned binary header ("KDG1") shared by Go and Rust.
	KDGMagic       = "KDG1"
	KDGVersion     = uint32(1)
	KDGHeaderBytes = 64
)

var (
	ErrInvalidKDGHeader = errors.New("sekg/kdg: invalid or corrupted 64-byte KDG1 binary header")
)

// RelGt5DToken represents the 5-dimensional relational graph token inspired by Kumo RelGT:
// [d1: normalized feature, d2: entity table type embedding, d3: structural hop distance,
// d4: temporal recency encoding, d5: local neighborhood topology].
type RelGt5DToken struct {
	NodeID              uint32     `json:"node_id"`
	NodeKey             string     `json:"node_key,omitempty"`
	D1FeatureNorm       float32    `json:"d1_feature_norm"`
	D2EntityTypeEmb     float32    `json:"d2_entity_type_emb"`
	D3HopDistanceEmb    float32    `json:"d3_hop_distance_emb"`
	D4TemporalDeltaEmb  float32    `json:"d4_temporal_delta_emb"`
	D5LocalStructureEmb float32    `json:"d5_local_structure_emb"`
	Padding             [2]float32 `json:"-"`
}

// TemporalSubgraphSample holds the causal subgraph sampled strictly at or before AnchorTimeUnix.
type TemporalSubgraphSample struct {
	SeedNodeID          string         `json:"seed_node_id"`
	AnchorTimeUnix      int64          `json:"anchor_time_unix"`
	Tokens5D            []RelGt5DToken `json:"tokens_5d"`
	FutureEdgesFiltered int            `json:"future_edges_filtered"`
	LeakedFutureEdges   int            `json:"leaked_future_edges"`
	DurationNs          int64          `json:"duration_ns"`
}

func nodeKindToCode(k NodeKind) uint8 {
	switch k {
	case KindSkill:
		return 0
	case KindModule, KindFile, KindSymbol:
		return 1
	case KindADR, KindContract, KindAPI:
		return 2
	case KindEpisode, KindError:
		return 3
	case KindTest:
		return 4
	default:
		return 5
	}
}

func nodeKindEmbeddingScalar(k NodeKind) float32 {
	switch nodeKindToCode(k) {
	case 0:
		return 0.15
	case 1:
		return 0.35
	case 2:
		return 0.55
	case 3:
		return 0.75
	default:
		return 0.95
	}
}

// MarshalKDGBytes serializes the GraphCSR into the 64-byte aligned binary .kdg format
// (byte-compatible with the Rust POC-01 zero-copy reader).
func (g *GraphCSR) MarshalKDGBytes() []byte {
	n := len(g.Nodes)
	m := len(g.Edges)
	if len(g.FwdOffsets) != n+1 {
		g.BuildCSR()
	}

	totalSize := KDGHeaderBytes + (n+1)*4 + m*4 + m*8 + m*4 + n
	buf := make([]byte, totalSize)

	copy(buf[0:4], []byte(KDGMagic))
	binary.LittleEndian.PutUint32(buf[4:8], KDGVersion)
	binary.LittleEndian.PutUint64(buf[8:16], uint64(n))
	binary.LittleEndian.PutUint64(buf[16:24], uint64(m))
	binary.LittleEndian.PutUint64(buf[24:32], g.computeFNV1a64())

	pos := KDGHeaderBytes
	for _, off := range g.FwdOffsets {
		binary.LittleEndian.PutUint32(buf[pos:pos+4], off)
		pos += 4
	}
	for _, tgt := range g.FwdTargets {
		binary.LittleEndian.PutUint32(buf[pos:pos+4], tgt)
		pos += 4
	}
	for _, eIdx := range g.FwdEdgeIdxs {
		ts := g.Edges[eIdx].UpdatedAtUnix
		if ts <= 0 {
			ts = 1_759_276_800
		}
		binary.LittleEndian.PutUint64(buf[pos:pos+8], uint64(ts))
		pos += 8
	}
	for _, eIdx := range g.FwdEdgeIdxs {
		bits := math.Float32bits(g.Edges[eIdx].Weight)
		binary.LittleEndian.PutUint32(buf[pos:pos+4], bits)
		pos += 4
	}
	for _, nd := range g.Nodes {
		buf[pos] = nodeKindToCode(nd.Kind)
		pos++
	}
	return buf
}

// VerifyKDGBytes validates the 64-byte aligned KDG1 binary header in nanoseconds (zero-copy slice inspection).
func VerifyKDGBytes(raw []byte) (numNodes uint64, numEdges uint64, checksum uint64, err error) {
	if len(raw) < KDGHeaderBytes || string(raw[0:4]) != KDGMagic {
		return 0, 0, 0, ErrInvalidKDGHeader
	}
	ver := binary.LittleEndian.Uint32(raw[4:8])
	if ver != KDGVersion {
		return 0, 0, 0, ErrInvalidKDGHeader
	}
	n := binary.LittleEndian.Uint64(raw[8:16])
	m := binary.LittleEndian.Uint64(raw[16:24])
	csum := binary.LittleEndian.Uint64(raw[24:32])
	minExpected := KDGHeaderBytes + int(n+1)*4 + int(m)*16 + int(n)
	if len(raw) < minExpected {
		return 0, 0, 0, ErrInvalidKDGHeader
	}
	return n, m, csum, nil
}

// SaveKDGAtomic persists the binary .kdg CSR snapshot atomically to disk.
func (g *GraphCSR) SaveKDGAtomic(kdgPath string) error {
	if err := os.MkdirAll(filepath.Dir(kdgPath), 0o755); err != nil {
		return err
	}
	raw := g.MarshalKDGBytes()
	tmp := kdgPath + ".tmp"
	if err := os.WriteFile(tmp, raw, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, kdgPath)
}

// SampleTemporalSubgraph5D executes Kumo-style strict temporal 1-hop and 2-hop sampling directly in pure Go,
// filtering out any edge with UpdatedAtUnix > anchorUnix (zero temporal data leakage) and building 5D RelGT tokens.
func (g *GraphCSR) SampleTemporalSubgraph5D(seedQuery string, anchorUnix int64, maxNeighbors int) TemporalSubgraphSample {
	t0 := time.Now()
	n := len(g.Nodes)
	if n == 0 {
		return TemporalSubgraphSample{SeedNodeID: seedQuery, AnchorTimeUnix: anchorUnix}
	}
	if len(g.FwdOffsets) != n+1 {
		g.BuildCSR()
	}
	if maxNeighbors <= 0 {
		maxNeighbors = 32
	}
	if anchorUnix <= 0 {
		anchorUnix = time.Now().UTC().Unix()
	}

	u0, ok := g.NodeIndex[seedQuery]
	if !ok {
		u0 = 0
	}

	tokens := make([]RelGt5DToken, 0, maxNeighbors)
	seedNode := g.Nodes[u0]
	seedDeg := float64(g.FwdOffsets[u0+1] - g.FwdOffsets[u0])
	tokens = append(tokens, RelGt5DToken{
		NodeID:              u0,
		NodeKey:             seedNode.ID,
		D1FeatureNorm:       float32(math.Tanh(float64(seedNode.Degree+1) / 16.0)),
		D2EntityTypeEmb:     nodeKindEmbeddingScalar(seedNode.Kind),
		D3HopDistanceEmb:    0.0,
		D4TemporalDeltaEmb:  1.0,
		D5LocalStructureEmb: float32(math.Tanh(seedDeg / 32.0)),
	})

	type hop1Entry struct {
		nodeIdx uint32
		edgeTs  int64
	}
	var hop1List []hop1Entry
	futureFiltered := 0

	// 1-hop causal expansion (strictly edgeTs <= anchorUnix)
	for pos := g.FwdOffsets[u0]; pos < g.FwdOffsets[u0+1]; pos++ {
		edge := g.Edges[g.FwdEdgeIdxs[pos]]
		edgeTs := edge.UpdatedAtUnix
		if edgeTs > anchorUnix {
			futureFiltered++
			continue
		}
		if len(tokens) >= maxNeighbors {
			continue
		}
		v := g.FwdTargets[pos]
		hop1List = append(hop1List, hop1Entry{nodeIdx: v, edgeTs: edgeTs})

		deltaDays := math.Max(0, float64(anchorUnix-edgeTs)/86400.0)
		temporalEmb := float32(1.0 / (1.0 + math.Log1p(deltaDays)))
		vNode := g.Nodes[v]
		vDeg := float64(g.FwdOffsets[v+1] - g.FwdOffsets[v])

		tokens = append(tokens, RelGt5DToken{
			NodeID:              v,
			NodeKey:             vNode.ID,
			D1FeatureNorm:       float32(math.Tanh(float64(vNode.Degree+1) / 16.0)),
			D2EntityTypeEmb:     nodeKindEmbeddingScalar(vNode.Kind),
			D3HopDistanceEmb:    0.50,
			D4TemporalDeltaEmb:  temporalEmb,
			D5LocalStructureEmb: float32(math.Tanh((vDeg * float64(edge.Weight)) / 16.0)),
		})
	}

	// 2-hop causal expansion (strictly edgeTs2 <= hop1.edgeTs <= anchorUnix)
	for _, h1 := range hop1List {
		if len(tokens) >= maxNeighbors {
			break
		}
		for pos2 := g.FwdOffsets[h1.nodeIdx]; pos2 < g.FwdOffsets[h1.nodeIdx+1]; pos2++ {
			if len(tokens) >= maxNeighbors {
				break
			}
			edge2 := g.Edges[g.FwdEdgeIdxs[pos2]]
			edgeTs2 := edge2.UpdatedAtUnix
			if edgeTs2 > h1.edgeTs {
				futureFiltered++
				continue
			}
			v2 := g.FwdTargets[pos2]
			deltaDays := math.Max(0, float64(anchorUnix-edgeTs2)/86400.0)
			temporalEmb := float32(1.0 / (1.0 + math.Log1p(deltaDays)))
			v2Node := g.Nodes[v2]
			v2Deg := float64(g.FwdOffsets[v2+1] - g.FwdOffsets[v2])

			tokens = append(tokens, RelGt5DToken{
				NodeID:              v2,
				NodeKey:             v2Node.ID,
				D1FeatureNorm:       float32(math.Tanh(float64(v2Node.Degree+1) / 16.0)),
				D2EntityTypeEmb:     nodeKindEmbeddingScalar(v2Node.Kind),
				D3HopDistanceEmb:    1.00,
				D4TemporalDeltaEmb:  temporalEmb,
				D5LocalStructureEmb: float32(math.Tanh((v2Deg * float64(edge2.Weight)) / 16.0)),
			})
		}
	}

	return TemporalSubgraphSample{
		SeedNodeID:          seedNode.ID,
		AnchorTimeUnix:      anchorUnix,
		Tokens5D:            tokens,
		FutureEdgesFiltered: futureFiltered,
		LeakedFutureEdges:   0,
		DurationNs:          time.Since(t0).Nanoseconds(),
	}
}

func (g *GraphCSR) computeFNV1a64() uint64 {
	var hash uint64 = 0xcbf29ce484222325
	var b [4]byte
	for _, t := range g.FwdTargets {
		binary.LittleEndian.PutUint32(b[:], t)
		for _, v := range b {
			hash ^= uint64(v)
			hash *= 0x0100000001b3
		}
	}
	return hash
}
