// Package gomcpclient provides the experimental Go MCP client and Group A/B Go baselines
// for the SquadAI GPU Intelligence Lab without modifying any core SquadAI Harness package.
package gomcpclient

import (
	"bufio"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"math"
	"net"
	"time"
)

// KdgHeaderMagic identifies the 64-byte aligned binary CSR graph format shared with Rust/CUDA.
const KdgHeaderMagic = "SKDG"

// MCPRequest represents a JSON-RPC 2.0 tool call sent from Go to the Rust GPU Lab MCP server.
type MCPRequest struct {
	JSONRPC string         `json:"jsonrpc"`
	ID      int            `json:"id"`
	Method  string         `json:"method"`
	Params  map[string]any `json:"params,omitempty"`
}

// PersistentLabClient maintains a persistent TCP loopback connection to the Rust MCP server,
// eliminating the per-call CreateProcessW (~45ms) and cuCtxCreate_v2 (~120ms) overhead found in GAP-02.
type PersistentLabClient struct {
	conn   net.Conn
	reader *bufio.Reader
	nextID int
}

// DialLabLoopback connects to a running Rust Lab MCP TCP endpoint with TCP_NODELAY enabled.
func DialLabLoopback(addr string, timeout time.Duration) (*PersistentLabClient, error) {
	conn, err := net.DialTimeout("tcp", addr, timeout)
	if err != nil {
		return nil, err
	}
	if tcpConn, ok := conn.(*net.TCPConn); ok {
		_ = tcpConn.SetNoDelay(true)
	}
	return &PersistentLabClient{
		conn:   conn,
		reader: bufio.NewReader(conn),
		nextID: 1,
	}, nil
}

// CallTool invokes an experimental Rust/CUDA/Kumo MCP tool over the persistent connection.
func (c *PersistentLabClient) CallTool(toolName string) (string, time.Duration, error) {
	t0 := time.Now()
	req := MCPRequest{
		JSONRPC: "2.0",
		ID:      c.nextID,
		Method:  "tools/call",
		Params:  map[string]any{"name": toolName},
	}
	c.nextID++

	payload, err := json.Marshal(req)
	if err != nil {
		return "", 0, err
	}
	payload = append(payload, '\n')
	if _, err := c.conn.Write(payload); err != nil {
		return "", 0, err
	}
	line, err := c.reader.ReadString('\n')
	if err != nil {
		return "", 0, err
	}
	return line, time.Since(t0), nil
}

// Close gracefully terminates the persistent loopback session.
func (c *PersistentLabClient) Close() error {
	if c.conn == nil {
		return nil
	}
	_, _ = c.conn.Write([]byte("QUIT\n"))
	return c.conn.Close()
}

// GoBaselineBatchDot implements the Group A/B Go CPU baseline for dense vector similarity (D=128).
func GoBaselineBatchDot(docsFlat []float32, query []float32, n int, d int) []float32 {
	out := make([]float32, n)
	for i := 0; i < n; i++ {
		row := docsFlat[i*d : (i+1)*d]
		var sum float32
		for j := 0; j < d; j++ {
			sum += row[j] * query[j]
		}
		out[i] = sum
	}
	return out
}

// GoOptimizedBatchDotUnrolled implements Group B (Go CPU with 4-way loop unrolling).
func GoOptimizedBatchDotUnrolled(docsFlat []float32, query []float32, n int, d int) []float32 {
	out := make([]float32, n)
	chunks := d / 4
	for i := 0; i < n; i++ {
		row := docsFlat[i*d : (i+1)*d]
		var a0, a1, a2, a3 float32
		for c := 0; c < chunks; c++ {
			b := c * 4
			a0 += row[b] * query[b]
			a1 += row[b+1] * query[b+1]
			a2 += row[b+2] * query[b+2]
			a3 += row[b+3] * query[b+3]
		}
		out[i] = (a0 + a1) + (a2 + a3)
	}
	return out
}

// GoBaselineCSRPageRank implements Group A/B Go CPU 20-iteration CSR PageRank.
func GoBaselineCSRPageRank(rowPtr []uint32, colIdx []uint32, weights []float32, numNodes int, damping float32, iterations int) []float32 {
	initVal := float32(1.0) / float32(max(numNodes, 1))
	baseTeleport := (1.0 - damping) / float32(max(numNodes, 1))
	rIn := make([]float32, numNodes)
	rOut := make([]float32, numNodes)
	for i := range rIn {
		rIn[i] = initVal
	}
	for iter := 0; iter < iterations; iter++ {
		stepCSRPageRank(rowPtr, colIdx, weights, rIn, rOut, numNodes, damping, baseTeleport)
		rIn, rOut = rOut, rIn
	}
	return rIn
}

func stepCSRPageRank(rowPtr []uint32, colIdx []uint32, weights []float32, rIn []float32, rOut []float32, numNodes int, damping float32, baseTeleport float32) {
	for row := 0; row < numNodes; row++ {
		start := rowPtr[row]
		end := rowPtr[row+1]
		var sum float32
		for edge := start; edge < end; edge++ {
			col := colIdx[edge]
			sum += weights[edge] * rIn[col]
		}
		rOut[row] = damping*sum + baseTeleport
	}
}

// EncodeKdgBinaryHeader writes the 64-byte aligned SKDG header for zero-copy Go <-> Rust graph transfer.
func EncodeKdgBinaryHeader(numNodes uint64, numEdges uint64, snapshotUnix int64) []byte {
	hdr := make([]byte, 64)
	copy(hdr[0:4], []byte(KdgHeaderMagic))
	binary.LittleEndian.PutUint32(hdr[4:8], 1)
	binary.LittleEndian.PutUint64(hdr[8:16], numNodes)
	binary.LittleEndian.PutUint64(hdr[16:24], numEdges)
	binary.LittleEndian.PutUint64(hdr[24:32], uint64(snapshotUnix))
	return hdr
}

// GoBaselineGEMM computes naive i-j-k matrix multiplication (Group A Go baseline).
func GoBaselineGEMM(a []float32, b []float32, dim int) []float32 {
	c := make([]float32, dim*dim)
	for i := 0; i < dim; i++ {
		for j := 0; j < dim; j++ {
			var sum float32
			for k := 0; k < dim; k++ {
				sum += a[i*dim+k] * b[k*dim+j]
			}
			c[i*dim+j] = sum
		}
	}
	return c
}

// GoOptimizedGEMM computes cache-friendly i-k-j matrix multiplication (Group B Go optimized).
func GoOptimizedGEMM(a []float32, b []float32, dim int) []float32 {
	c := make([]float32, dim*dim)
	for i := 0; i < dim; i++ {
		cRow := c[i*dim : (i+1)*dim]
		for k := 0; k < dim; k++ {
			aik := a[i*dim+k]
			bRow := b[k*dim : (k+1)*dim]
			for j := 0; j < dim; j++ {
				cRow[j] += aik * bRow[j]
			}
		}
	}
	return c
}

// GoBaselineRiskFusion computes fused anomaly and risk scoring in Go.
func GoBaselineRiskFusion(features []float32, weights []float32, means []float32, invStds []float32, n int, d int) []float32 {
	out := make([]float32, n)
	for i := 0; i < n; i++ {
		row := features[i*d : (i+1)*d]
		var lin, z2 float32
		for j := 0; j < d; j++ {
			z := (row[j] - means[j]) * invStds[j]
			lin += z * weights[j]
			z2 += z * z
		}
		if lin < 0 {
			lin = -lin
		}
		out[i] = 0.65*lin + 0.35*z2
	}
	return out
}

// ComputeCosineSimilarity calculates exact FP64 cosine similarity between two FP32 vectors.
func ComputeCosineSimilarity(a []float32, b []float32) (float64, error) {
	if len(a) != len(b) || len(a) == 0 {
		return 0, fmt.Errorf("dimensoes invalidas para similaridade cosseno")
	}
	var dot, normA, normB float64
	for i := range a {
		va := float64(a[i])
		vb := float64(b[i])
		dot += va * vb
		normA += va * va
		normB += vb * vb
	}
	denom := math.Sqrt(normA) * math.Sqrt(normB)
	if denom < 1e-12 {
		return 0, nil
	}
	return dot / denom, nil
}
