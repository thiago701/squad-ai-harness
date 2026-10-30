// Package dag implements the semantic Directed Acyclic Graph execution engine in Go 1.24.3,
// replacing the 27 sequential Python subprocess spawns of ops/run.py with bounded
// concurrent goroutines, topological level scheduling, and fail-closed cancellation.
package dag

import (
	"context"
	"errors"
	"fmt"
	"runtime"
	"sort"
	"sync"
	"time"
)

var (
	ErrCycleDetected = errors.New("dag: dependency cycle detected in pipeline graph")
	ErrNodeFailed    = errors.New("dag: fail-closed node failed")
)

// ActionFunc is the in-memory execution callback for a DAG node.
type ActionFunc func(ctx context.Context) error

// Node defines a single unit of work in the development/quality pipeline DAG.
type Node struct {
	ID          string
	Description string
	Deps        []string
	AllowFail   bool
	WeightMB    int64
	Action      ActionFunc
}

// NodeResult captures the execution telemetry of a single DAG node.
type NodeResult struct {
	ID          string        `json:"id"`
	Description string        `json:"description"`
	Status      string        `json:"status"` // "PASS", "FAILED", "SKIPPED", "WARN"
	DurationMs  float64       `json:"duration_ms"`
	AllocKB     int64         `json:"alloc_kb"`
	Error       string        `json:"error,omitempty"`
}

// ExecutionSummary holds the complete outcome of a DAG execution.
type ExecutionSummary struct {
	TotalNodes   int           `json:"total_nodes"`
	PassedNodes  int           `json:"passed_nodes"`
	FailedNodes  int           `json:"failed_nodes"`
	SkippedNodes int           `json:"skipped_nodes"`
	TotalDurMs   float64       `json:"total_dur_ms"`
	Results      []NodeResult  `json:"results"`
	Success      bool          `json:"success"`
}

// Engine executes a validated DAG with bounded concurrency.
type Engine struct {
	maxParallel int
	nodes       map[string]Node
	order       []string
}

// NewEngine creates a DAG Engine with bounded parallelism (defaults to GOMAXPROCS).
func NewEngine(maxParallel int) *Engine {
	if maxParallel <= 0 {
		maxParallel = runtime.GOMAXPROCS(0)
	}
	return &Engine{
		maxParallel: maxParallel,
		nodes:       make(map[string]Node),
	}
}

// AddNode registers a node in the DAG.
func (e *Engine) AddNode(n Node) error {
	if n.ID == "" {
		return errors.New("dag: node ID cannot be empty")
	}
	if _, exists := e.nodes[n.ID]; exists {
		return fmt.Errorf("dag: duplicate node ID %q", n.ID)
	}
	e.nodes[n.ID] = n
	e.order = append(e.order, n.ID)
	return nil
}

// TopologicalLevels computes the parallel execution waves (Kahn's algorithm) and rejects cycles.
func (e *Engine) TopologicalLevels() ([][]string, error) {
	inDegree := make(map[string]int, len(e.nodes))
	dependents := make(map[string][]string, len(e.nodes))

	for id, n := range e.nodes {
		if _, ok := inDegree[id]; !ok {
			inDegree[id] = 0
		}
		for _, dep := range n.Deps {
			if _, exists := e.nodes[dep]; !exists {
				return nil, fmt.Errorf("dag: node %q depends on unknown node %q", id, dep)
			}
			inDegree[id]++
			dependents[dep] = append(dependents[dep], id)
		}
	}

	var currentWave []string
	for id, deg := range inDegree {
		if deg == 0 {
			currentWave = append(currentWave, id)
		}
	}
	sort.Strings(currentWave)

	var levels [][]string
	visited := 0

	for len(currentWave) > 0 {
		levels = append(levels, currentWave)
		visited += len(currentWave)

		var nextWave []string
		for _, u := range currentWave {
			for _, v := range dependents[u] {
				inDegree[v]--
				if inDegree[v] == 0 {
					nextWave = append(nextWave, v)
				}
			}
		}
		sort.Strings(nextWave)
		currentWave = nextWave
	}

	if visited != len(e.nodes) {
		return nil, ErrCycleDetected
	}
	return levels, nil
}

// Execute runs the DAG wave by wave with bounded worker concurrency and fail-closed semantics.
func (e *Engine) Execute(ctx context.Context) (ExecutionSummary, error) {
	levels, err := e.TopologicalLevels()
	if err != nil {
		return ExecutionSummary{}, err
	}

	startAll := time.Now()
	runCtx, cancel := context.WithCancelCause(ctx)
	defer cancel(nil)

	resultsMap := make(map[string]NodeResult, len(e.nodes))
	var mu sync.Mutex
	sem := make(chan struct{}, e.maxParallel)
	aborted := false

	for _, wave := range levels {
		mu.Lock()
		isAborted := aborted
		mu.Unlock()

		if isAborted || runCtx.Err() != nil {
			for _, id := range wave {
				n := e.nodes[id]
				resultsMap[id] = NodeResult{
					ID:          id,
					Description: n.Description,
					Status:      "SKIPPED",
				}
			}
			continue
		}

		var wg sync.WaitGroup
		for _, id := range wave {
			node := e.nodes[id]
			wg.Add(1)
			go func(n Node) {
				defer wg.Done()
				select {
				case sem <- struct{}{}:
					defer func() { <-sem }()
				case <-runCtx.Done():
					mu.Lock()
					resultsMap[n.ID] = NodeResult{ID: n.ID, Description: n.Description, Status: "SKIPPED"}
					mu.Unlock()
					return
				}

				var memBefore, memAfter runtime.MemStats
				runtime.ReadMemStats(&memBefore)
				t0 := time.Now()
				execErr := n.Action(runCtx)
				durMs := float64(time.Since(t0).Microseconds()) / 1000.0
				runtime.ReadMemStats(&memAfter)

				var allocKB int64
				if memAfter.TotalAlloc >= memBefore.TotalAlloc {
					allocKB = int64((memAfter.TotalAlloc - memBefore.TotalAlloc) / 1024)
				}

				res := NodeResult{
					ID:          n.ID,
					Description: n.Description,
					DurationMs:  durMs,
					AllocKB:     allocKB,
					Status:      "PASS",
				}
				if execErr != nil {
					res.Error = execErr.Error()
					if n.AllowFail {
						res.Status = "WARN"
					} else {
						res.Status = "FAILED"
					}
				}

				mu.Lock()
				resultsMap[n.ID] = res
				if res.Status == "FAILED" && !aborted {
					aborted = true
					cancel(fmt.Errorf("%w: %s (%v)", ErrNodeFailed, n.ID, execErr))
				}
				mu.Unlock()
			}(node)
		}
		wg.Wait()
	}

	summary := ExecutionSummary{
		TotalNodes: len(e.nodes),
		TotalDurMs: float64(time.Since(startAll).Microseconds()) / 1000.0,
		Success:    !aborted,
	}
	for _, id := range e.order {
		r := resultsMap[id]
		summary.Results = append(summary.Results, r)
		switch r.Status {
		case "PASS", "WARN":
			summary.PassedNodes++
		case "FAILED":
			summary.FailedNodes++
		case "SKIPPED":
			summary.SkippedNodes++
		}
	}
	return summary, nil
}
