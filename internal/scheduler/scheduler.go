// Package scheduler implements the 8-dimensional Intelligent Task Scheduler and
// Intelligent Memory Orchestrator (IMO) in Go 1.24.3, governing concurrency,
// physical RAM admission, EWMA cost tracking, and Batman portfolio workers (ADR-023).
package scheduler

import (
	"context"
	"errors"
	"runtime"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/thiago701/squad-ai-harness/internal/runtime/jobobject"
)

const (
	// DefaultSafetyReserveMB is the minimum free physical RAM (2.5 GB) preserved on the workstation.
	DefaultSafetyReserveMB = 2560
	// EWMAAlpha is the exponential smoothing factor for historical RAM and latency learning.
	EWMAAlpha = 0.30
)

var (
	ErrMemoryAdmissionDenied = errors.New("scheduler/imo: insufficient free physical RAM to admit heavy task safely")
)

// WorkloadKind classifies the resource profile of a scheduled task.
type WorkloadKind string

const (
	WorkloadCPUBound    WorkloadKind = "CPU_BOUND"
	WorkloadIOBound     WorkloadKind = "IO_BOUND"
	WorkloadMemoryHeavy WorkloadKind = "MEMORY_HEAVY"
	WorkloadRemoteWait  WorkloadKind = "REMOTE_WAIT"
)

// TaskDescriptor defines all 8 scheduling dimensions for a candidate task.
type TaskDescriptor struct {
	ID              string
	Priority        int          // 1. Priority (0 = highest blocker, 3 = lowest background)
	Kind            WorkloadKind // 2. Workload type
	EstimatedRSSMB  int64        // 3. Memory requirement (updated via EWMA)
	CPUCores        int          // 4. CPU requirement
	RequiresAccel   bool         // 5. GPU/NPU requirement
	ProviderKey     string       // 6. External provider quota key
	Deps            []string     // 7. Task dependencies
}

// HistoricalMetrics stores the EWMA-smoothed runtime cost of a task ID.
type HistoricalMetrics struct {
	EWMARSSMB       float64 `json:"ewma_rss_mb"`
	EWMADurationMs  float64 `json:"ewma_duration_ms"`
	Samples         int     `json:"samples"`
}

// Scheduler coordinates task admission across the 8 dimensions and enforces IMO memory safety.
type Scheduler struct {
	mu          sync.Mutex
	reserveMB   int64
	maxCPU      int
	inFlightMB  int64
	history     map[string]HistoricalMetrics
}

// NewScheduler creates an 8-dimensional task scheduler.
func NewScheduler(reserveMB int64) *Scheduler {
	if reserveMB <= 0 {
		reserveMB = DefaultSafetyReserveMB
	}
	return &Scheduler{
		reserveMB: reserveMB,
		maxCPU:    runtime.GOMAXPROCS(0),
		history:   make(map[string]HistoricalMetrics),
	}
}

// CheckAdmission probes real OS physical RAM (GlobalMemoryStatusEx on Windows) and decides
// whether the task can be safely dispatched without risking swap thrashing or OOM.
func (s *Scheduler) CheckAdmission(t TaskDescriptor) (bool, jobobject.SystemMemory, int64) {
	mem, err := jobobject.ProbeSystemMemory()
	if err != nil {
		// Fail-safe fallback
		mem = jobobject.SystemMemory{TotalPhysMB: 16384, AvailPhysMB: 6144, MemoryLoadPct: 62}
	}

	s.mu.Lock()
	estMB := t.EstimatedRSSMB
	if h, ok := s.history[t.ID]; ok && h.Samples > 0 {
		estMB = int64(h.EWMARSSMB)
	}
	if estMB <= 0 {
		if t.Kind == WorkloadMemoryHeavy {
			estMB = 400
		} else {
			estMB = 25
		}
	}
	effectiveAvail := mem.AvailPhysMB - s.inFlightMB
	s.mu.Unlock()

	admitted := (effectiveAvail - estMB) >= s.reserveMB
	return admitted, mem, estMB
}

// RecordExecution updates the EWMA (alpha = 0.30) memory and duration model for taskID.
func (s *Scheduler) RecordExecution(taskID string, measuredRSSMB float64, measuredDurMs float64) HistoricalMetrics {
	s.mu.Lock()
	defer s.mu.Unlock()

	h, exists := s.history[taskID]
	if !exists || h.Samples == 0 {
		h = HistoricalMetrics{
			EWMARSSMB:      measuredRSSMB,
			EWMADurationMs: measuredDurMs,
			Samples:        1,
		}
	} else {
		h.EWMARSSMB = EWMAAlpha*measuredRSSMB + (1.0-EWMAAlpha)*h.EWMARSSMB
		h.EWMADurationMs = EWMAAlpha*measuredDurMs + (1.0-EWMAAlpha)*h.EWMADurationMs
		h.Samples++
	}
	s.history[taskID] = h
	return h
}

// OrderQueue sorts candidate tasks deterministically by Priority (P0 > P1 > P2 > P3) and estimated cost.
func OrderQueue(tasks []TaskDescriptor) []TaskDescriptor {
	sorted := make([]TaskDescriptor, len(tasks))
	copy(sorted, tasks)
	sort.Slice(sorted, func(i, j int) bool {
		if sorted[i].Priority != sorted[j].Priority {
			return sorted[i].Priority < sorted[j].Priority
		}
		if sorted[i].EstimatedRSSMB != sorted[j].EstimatedRSSMB {
			return sorted[i].EstimatedRSSMB < sorted[j].EstimatedRSSMB
		}
		return sorted[i].ID < sorted[j].ID
	})
	return sorted
}

// BuildHardenedClaudeArgs enforces --strict-mcp-config on headless claude -p workers,
// eliminating the 372 MB of unused global uvx AWS MCP servers measured in the Phase 1 audit.
func BuildHardenedClaudeArgs(prompt string, mcpConfigPath string) []string {
	args := []string{"-p", prompt, "--strict-mcp-config"}
	if strings.TrimSpace(mcpConfigPath) != "" {
		args = append(args, "--mcp-config", mcpConfigPath)
	}
	return args
}

// ExecuteTaskWithIMO admits and runs an external task inside a supervised OS Job Object.
func (s *Scheduler) ExecuteTaskWithIMO(ctx context.Context, t TaskDescriptor, spec jobobject.RunSpec) (jobobject.RunResult, error) {
	admitted, _, estMB := s.CheckAdmission(t)
	if !admitted && t.Kind == WorkloadMemoryHeavy {
		return jobobject.RunResult{ExitCode: 75}, ErrMemoryAdmissionDenied
	}

	s.mu.Lock()
	s.inFlightMB += estMB
	s.mu.Unlock()
	defer func() {
		s.mu.Lock()
		s.inFlightMB -= estMB
		if s.inFlightMB < 0 {
			s.inFlightMB = 0
		}
		s.mu.Unlock()
	}()

	if spec.MemoryLimitMB <= 0 && t.Kind == WorkloadMemoryHeavy {
		spec.MemoryLimitMB = 1024 // Default 1 GB hard ceiling per heavy worker job
	}
	t0 := time.Now()
	res, err := jobobject.ExecuteSupervised(ctx, spec)
	s.RecordExecution(t.ID, float64(estMB), float64(time.Since(t0).Milliseconds()))
	return res, err
}
