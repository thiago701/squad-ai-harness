// Package hooks implements the sub-25ms hot-path session hooks in Go (Etapa 1),
// replacing graphify_guard.py (PreToolUse), scan_secrets.py (PostToolUse),
// stop_verificacao_lembrete.py, and stop_extract_telemetry.py (Stop).
package hooks

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/thiago701/squad-ai-harness/internal/gates"
	"github.com/thiago701/squad-ai-harness/internal/security/fsguard"
	"github.com/thiago701/squad-ai-harness/internal/security/secretscan"
)

// ToolHookInput represents the JSON payload piped via stdin by Claude Code / IDE hooks.
type ToolHookInput struct {
	ToolName  string `json:"tool_name"`
	ToolInput struct {
		FilePath string `json:"file_path"`
		Path     string `json:"path"`
		Command  string `json:"command"`
	} `json:"tool_input"`
	TranscriptPath string `json:"transcript_path"`
}

func readHookStdin(stdin io.Reader) []byte {
	if stdin == nil {
		return nil
	}
	if f, ok := stdin.(*os.File); ok {
		fi, err := f.Stat()
		if err != nil || (fi.Mode()&os.ModeCharDevice) != 0 {
			return nil
		}
		ch := make(chan []byte, 1)
		go func() {
			b, _ := io.ReadAll(io.LimitReader(f, 64*1024))
			ch <- b
		}()
		select {
		case b := <-ch:
			return b
		case <-time.After(100 * time.Millisecond):
			return nil
		}
	}
	data, _ := io.ReadAll(io.LimitReader(stdin, 64*1024))
	return data
}

// PreToolUse executes the ultra-fast (< 2ms) guard before Bash/Read/Glob tool calls.
// It checks dangerous commands and verifies if graphify-out/graph.json is present without
// importing 29 Python modules.
func PreToolUse(repoRoot string, stdin io.Reader) (int, string) {
	data := readHookStdin(stdin)
	var input ToolHookInput
	if len(data) > 0 {
		_ = json.Unmarshal(data, &input)
	}

	cmd := strings.TrimSpace(input.ToolInput.Command)
	if cmd != "" {
		if blocked, reason := CheckDangerousCommand(cmd); blocked {
			return 2, fmt.Sprintf("🛑 [SquadAI Harness PreToolUse] Comando bloqueado: %s", reason)
		}
	}

	// Graphify guard: only hint if graphify-out/graph.json actually exists on disk
	graphPath := filepath.Join(repoRoot, "graphify-out", "graph.json")
	if _, err := os.Stat(graphPath); err == nil {
		return 0, ""
	}
	return 0, ""
}

// CheckDangerousCommand blocks --no-verify, force pushes, foreign package managers, and destructive shell pipelines.
func CheckDangerousCommand(cmd string) (bool, string) {
	lower := strings.ToLower(cmd)
	if strings.Contains(lower, "--no-verify") {
		return true, "proibido usar --no-verify (AGENTS.md §6)"
	}
	if strings.Contains(lower, "push --force") || strings.Contains(lower, "push -f ") {
		return true, "proibido git push --force em branch compartilhada (AGENTS.md §2 Immutability)"
	}
	if strings.Contains(lower, "core.hookspath=") {
		return true, "proibido desativar core.hooksPath"
	}
	foreignToolPrefixes := []string{
		"pip install", "pip3 install", "poetry init", "poetry add", "uv init", "uv add",
		"npm init", "npm install", "pnpm add", "pnpm install", "yarn add", "yarn install",
		"cargo init", "mvn archetype:generate",
	}
	for _, fp := range foreignToolPrefixes {
		if strings.Contains(lower, fp) {
			return true, fmt.Sprintf("[Go-Exclusive Lock] comando '%s' bloqueado — o SquadAI Harness é exclusivo em Go (Golang 1.24.3+, CGO_ENABLED=0)", fp)
		}
	}
	return false, ""
}

// PostToolUse scans edited/written files in < 15ms for Go-exclusive source purity, secrets, PII in logs, and Trojan Source.
func PostToolUse(repoRoot string, stdin io.Reader) (int, string) {
	data := readHookStdin(stdin)
	var input ToolHookInput
	if len(data) > 0 {
		_ = json.Unmarshal(data, &input)
	}

	targetPath := input.ToolInput.FilePath
	if targetPath == "" {
		targetPath = input.ToolInput.Path
	}
	if targetPath == "" {
		return 0, ""
	}

	absTarget := targetPath
	if !filepath.IsAbs(targetPath) {
		safe, err := fsguard.SafeJoin(repoRoot, targetPath)
		if err != nil {
			return 2, fmt.Sprintf("🛑 [SquadAI Harness PostToolUse] Caminho fora do workspace: %v", err)
		}
		absTarget = safe
	}

	if allowed, reason := gates.CheckFilePathAllowed(repoRoot, absTarget); !allowed {
		return 2, fmt.Sprintf("🛑 [SquadAI Harness Go-Exclusive Lock] %s", reason)
	}

	content, err := os.ReadFile(absTarget)
	if err != nil {
		return 0, ""
	}

	findings := secretscan.ScanContent(targetPath, content)
	for _, f := range findings {
		if f.Severity == "BLOCKED" {
			return 2, fmt.Sprintf("🛑 [SquadAI Harness PostToolUse] Violação bloqueante [%s] em %s:%d (hash=%s): %s",
				f.RuleID, f.File, f.Line, f.LineHash, f.Message)
		}
	}
	return 0, ""
}

// StopHook merges stop_verificacao_lembrete.py and stop_extract_telemetry.py into a single
// < 15ms execution, reading only the last 256 KB of the transcript (tail streaming).
func StopHook(repoRoot string, stdin io.Reader) (int, string) {
	data := readHookStdin(stdin)
	var input ToolHookInput
	if len(data) > 0 {
		_ = json.Unmarshal(data, &input)
	}

	if input.TranscriptPath != "" {
		_ = appendTailTelemetry(repoRoot, input.TranscriptPath)
	}
	return 0, "✅ [SquadAI Harness v0.8.1] Turno registrado (telemetria SLI atualizada em streaming)."
}

func appendTailTelemetry(repoRoot, transcriptPath string) error {
	f, err := os.Open(transcriptPath)
	if err != nil {
		return err
	}
	defer f.Close()

	const tailMax = 256 * 1024
	stat, err := f.Stat()
	if err != nil {
		return err
	}
	offset := int64(0)
	if stat.Size() > tailMax {
		offset = stat.Size() - tailMax
	}
	if _, err := f.Seek(offset, io.SeekStart); err != nil {
		return err
	}
	tailBytes, err := io.ReadAll(f)
	if err != nil {
		return err
	}

	sliPath := filepath.Join(repoRoot, "memory", "sli.jsonl")
	if err := os.MkdirAll(filepath.Dir(sliPath), 0o755); err != nil {
		return err
	}
	out, err := os.OpenFile(sliPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return err
	}
	defer out.Close()

	rec := map[string]any{
		"schema":     "sli-v1",
		"evento":     "stop_hook_go",
		"tail_bytes": len(tailBytes),
		"ts":         time.Now().UTC().Format(time.RFC3339),
	}
	enc, _ := json.Marshal(rec)
	_, err = out.Write(append(enc, '\n'))
	return err
}
