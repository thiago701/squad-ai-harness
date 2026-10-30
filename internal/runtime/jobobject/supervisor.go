// Package jobobject unifies process tree execution, Windows Job Object isolation,
// POSIX process group termination, and physical RAM admission probing (ADR-023).
package jobobject

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os/exec"
	"time"
)

// SystemMemory represents the host's physical memory state.
type SystemMemory struct {
	TotalPhysMB   int64 `json:"total_phys_mb"`
	AvailPhysMB   int64 `json:"avail_phys_mb"`
	MemoryLoadPct int   `json:"memory_load_pct"`
}

// CanAdmit checks if executing a task with estimatedRSSMB leaves at least reserveMB of physical RAM free.
func (m SystemMemory) CanAdmit(estimatedRSSMB, reserveMB int64) bool {
	if reserveMB <= 0 {
		reserveMB = 2560 // Default 2.5 GB safety reserve on 16 GB workstation
	}
	return (m.AvailPhysMB - estimatedRSSMB) >= reserveMB
}

// RunSpec configures a supervised process execution.
type RunSpec struct {
	Argv          []string
	Dir           string
	Env           []string
	Timeout       time.Duration
	MemoryLimitMB int64
}

// RunResult captures the outcome of a supervised process tree execution.
type RunResult struct {
	ExitCode   int           `json:"exit_code"`
	Stdout     string        `json:"stdout"`
	Stderr     string        `json:"stderr"`
	Duration   time.Duration `json:"duration"`
	TimedOut   bool          `json:"timed_out"`
	KilledTree bool          `json:"killed_tree"`
}

// ExecuteSupervised runs an external command inside an OS Job Object (Windows) or Process Group (POSIX),
// guaranteeing that on timeout or context cancellation the entire descendant tree is killed with zero orphans.
func ExecuteSupervised(ctx context.Context, spec RunSpec) (RunResult, error) {
	if len(spec.Argv) == 0 {
		return RunResult{ExitCode: -1}, errors.New("jobobject: empty argv")
	}
	timeout := spec.Timeout
	if timeout <= 0 {
		timeout = 5 * time.Minute
	}

	runCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	pJob, err := newPlatformJob(spec.MemoryLimitMB)
	if err != nil {
		return RunResult{ExitCode: -1}, fmt.Errorf("jobobject: create job: %w", err)
	}

	cmd := exec.Command(spec.Argv[0], spec.Argv[1:]...)
	if spec.Dir != "" {
		cmd.Dir = spec.Dir
	}
	if len(spec.Env) > 0 {
		cmd.Env = spec.Env
	}
	configureCmdPlatform(cmd)

	var stdoutBuf, stderrBuf bytes.Buffer
	cmd.Stdout = &stdoutBuf
	cmd.Stderr = &stderrBuf

	start := time.Now()
	if err := cmd.Start(); err != nil {
		_ = pJob.terminateAndClose(0)
		return RunResult{ExitCode: -1, Duration: time.Since(start)}, err
	}

	pid := cmd.Process.Pid
	_ = pJob.assignProcess(pid)

	waitDone := make(chan error, 1)
	go func() {
		waitDone <- cmd.Wait()
	}()

	var waitErr error
	var timedOut, killedTree bool

	select {
	case waitErr = <-waitDone:
		_ = pJob.terminateAndClose(pid)
	case <-runCtx.Done():
		timedOut = errors.Is(runCtx.Err(), context.DeadlineExceeded)
		killedTree = true
		_ = pJob.terminateAndClose(pid)
		if cmd.Process != nil {
			_ = cmd.Process.Kill()
		}
		waitErr = <-waitDone
	}

	exitCode := 0
	if waitErr != nil {
		var exitErr *exec.ExitError
		if errors.As(waitErr, &exitErr) {
			exitCode = exitErr.ExitCode()
		} else {
			exitCode = -1
		}
	}
	if timedOut && exitCode == 0 {
		exitCode = 124
	}

	return RunResult{
		ExitCode:   exitCode,
		Stdout:     stdoutBuf.String(),
		Stderr:     stderrBuf.String(),
		Duration:   time.Since(start),
		TimedOut:   timedOut,
		KilledTree: killedTree,
	}, nil
}
