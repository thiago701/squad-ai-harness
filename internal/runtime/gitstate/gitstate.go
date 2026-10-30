// Package gitstate unifies the 8 duplicate Python Git wrappers into a single
// Singleflight-cached state collector and batch reader (ADR-025).
package gitstate

import (
	"bytes"
	"context"
	"os/exec"
	"strconv"
	"strings"
	"sync"
	"time"
)

// RepoSnapshot holds the complete Git repository state read once per pipeline/gate run.
type RepoSnapshot struct {
	RootDir       string       `json:"root_dir"`
	Branch        string       `json:"branch"`
	Detached      bool         `json:"detached"`
	DefaultBranch bool         `json:"default_branch"`
	HasRemote     bool         `json:"has_remote"`
	HasUpstream   bool         `json:"has_upstream"`
	Ahead         int          `json:"ahead"`
	Behind        int          `json:"behind"`
	Diverged      bool         `json:"diverged"`
	StagedCount   int          `json:"staged_count"`
	Changes       []FileChange `json:"changes"`
	Conflicts     []string     `json:"conflicts"`
	CollectedAt   time.Time    `json:"collected_at"`
}

// FileChange represents a single entry from git status --porcelain=v1.
type FileChange struct {
	Status string `json:"status"`
	Path   string `json:"path"`
}

// Collector deduplicates concurrent Git state queries using singleflight semantics.
type Collector struct {
	rootDir string
	mu      sync.Mutex
	cached  *RepoSnapshot
	ttl     time.Duration
	inFlight chan struct{}
}

// NewCollector creates a shared Git state collector for rootDir.
func NewCollector(rootDir string, ttl time.Duration) *Collector {
	if ttl <= 0 {
		ttl = 2 * time.Second
	}
	return &Collector{rootDir: rootDir, ttl: ttl}
}

// Snapshot returns the cached RepoSnapshot or collects a fresh one if expired,
// collapsing concurrent callers into a single Git execution.
func (c *Collector) Snapshot(ctx context.Context) (*RepoSnapshot, error) {
	c.mu.Lock()
	if c.cached != nil && time.Since(c.cached.CollectedAt) < c.ttl {
		snap := c.cached
		c.mu.Unlock()
		return snap, nil
	}
	if c.inFlight != nil {
		waitCh := c.inFlight
		c.mu.Unlock()
		select {
		case <-waitCh:
			c.mu.Lock()
			snap := c.cached
			c.mu.Unlock()
			return snap, nil
		case <-ctx.Done():
			return nil, ctx.Err()
		}
	}
	waitCh := make(chan struct{})
	c.inFlight = waitCh
	c.mu.Unlock()

	snap, err := collectSnapshot(ctx, c.rootDir)

	c.mu.Lock()
	if err == nil {
		c.cached = snap
	}
	c.inFlight = nil
	close(waitCh)
	c.mu.Unlock()

	return snap, err
}

func collectSnapshot(ctx context.Context, rootDir string) (*RepoSnapshot, error) {
	snap := &RepoSnapshot{
		RootDir:     rootDir,
		Branch:      "HEAD",
		CollectedAt: time.Now(),
	}

	// Single git invocation (--porcelain=v2 --branch) replaces 5 separate git subprocesses
	if code, out := runGit(ctx, rootDir, "status", "--porcelain=v2", "--branch"); code == 0 {
		for _, line := range strings.Split(out, "\n") {
			line = strings.TrimRight(line, "\r")
			if line == "" {
				continue
			}
			if strings.HasPrefix(line, "# ") {
				parseBranchHeader(line, snap)
				continue
			}
			parseChangeLineV2(line, snap)
		}
	}

	return snap, nil
}

func parseBranchHeader(line string, snap *RepoSnapshot) {
	switch {
	case strings.HasPrefix(line, "# branch.head "):
		b := strings.TrimSpace(strings.TrimPrefix(line, "# branch.head "))
		if b == "(detached)" {
			snap.Branch = "HEAD"
			snap.Detached = true
		} else {
			snap.Branch = b
			snap.DefaultBranch = b == "master" || b == "main"
		}
	case strings.HasPrefix(line, "# branch.upstream "):
		snap.HasRemote = true
		snap.HasUpstream = true
	case strings.HasPrefix(line, "# branch.ab "):
		fields := strings.Fields(strings.TrimPrefix(line, "# branch.ab "))
		if len(fields) >= 2 {
			snap.Ahead, _ = strconv.Atoi(strings.TrimPrefix(fields[0], "+"))
			snap.Behind, _ = strconv.Atoi(strings.TrimPrefix(fields[1], "-"))
			snap.Diverged = snap.Ahead > 0 && snap.Behind > 0
		}
	}
}

func parseChangeLineV2(line string, snap *RepoSnapshot) {
	switch line[0] {
	case '1', '2':
		// 1 <XY> <sub> <mH> <mI> <mW> <hH> <hI> <path>
		fields := strings.Fields(line)
		if len(fields) >= 9 {
			xy := fields[1]
			if len(xy) > 0 && xy[0] != '.' {
				snap.StagedCount++
			}
			p := fields[len(fields)-1]
			if tabIdx := strings.IndexByte(p, '\t'); tabIdx >= 0 {
				p = p[:tabIdx]
			}
			snap.Changes = append(snap.Changes, FileChange{Status: xy, Path: p})
		}
	case 'u':
		fields := strings.Fields(line)
		if len(fields) >= 11 {
			snap.Conflicts = append(snap.Conflicts, fields[len(fields)-1])
		}
	case '?':
		p := strings.TrimSpace(line[2:])
		snap.Changes = append(snap.Changes, FileChange{Status: "??", Path: p})
	}
}

func runGit(ctx context.Context, dir string, args ...string) (int, string) {
	fullArgs := append([]string{"--no-optional-locks"}, args...)
	cmd := exec.CommandContext(ctx, "git", fullArgs...)
	if dir != "" {
		cmd.Dir = dir
	}
	var out bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &out
	err := cmd.Run()
	if err != nil {
		var exitErr *exec.ExitError
		if ok := strings.Contains(err.Error(), "exit status"); ok && exitErr != nil {
			return exitErr.ExitCode(), out.String()
		}
		return 1, out.String()
	}
	return 0, out.String()
}
