// Package installer implements the native Go 1.24.3 multi-target skill installer
// and synchronizer (`squad-harness install`), replacing the legacy Python
// `install-squad-ai.py` script with concurrent, fail-closed, SHA-256-verified
// synchronization across all detected agentic environments (~/.claude,
// ~/.gemini/config, ~/.dsh, ~/.resolveai).
package installer

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/thiago701/squad-ai-harness/internal/catalog"
	"github.com/thiago701/squad-ai-harness/internal/security/secretscan"
)

// TargetDef describes a detected agentic tool environment on the host machine.
type TargetDef struct {
	ID        string `json:"id"`
	Name      string `json:"name"`
	RootDir   string `json:"root_dir"`
	SkillsDir string `json:"skills_dir"`
}

// TargetSyncReport reports the live synchronization status of one agentic environment.
type TargetSyncReport struct {
	ID            string `json:"id"`
	Name          string `json:"name"`
	SkillsDir     string `json:"skills_dir"`
	TotalSkills   int    `json:"total_skills"`
	SyncedCount   int    `json:"synced_count"`
	MissingCount  int    `json:"missing_count"`
	OutdatedCount int    `json:"outdated_count"`
	IsSynced      bool   `json:"is_synced"`
}

// SyncReport aggregates synchronization status across all detected targets.
type SyncReport struct {
	AllSynced       bool               `json:"all_synced"`
	TargetsDetected int                `json:"targets_detected"`
	TotalMissing    int                `json:"total_missing"`
	TotalOutdated   int                `json:"total_outdated"`
	Targets         []TargetSyncReport `json:"targets"`
	SkillSynced     map[string]bool    `json:"skill_synced"`
}

// TargetInstallResult summarizes files synchronized for a single target environment.
type TargetInstallResult struct {
	ID             string `json:"id"`
	Name           string `json:"name"`
	SkillsDir      string `json:"skills_dir"`
	SkillsSynced   int    `json:"skills_synced"`
	FilesInstalled int    `json:"files_installed"`
	FilesUpdated   int    `json:"files_updated"`
	FilesUnchanged int    `json:"files_unchanged"`
	ManifestPath   string `json:"manifest_path"`
}

// InstallSummary is returned by InstallAll / InstallToTargets.
type InstallSummary struct {
	Generator       string                `json:"generator"`
	DurationMs      float64               `json:"duration_ms"`
	CanonicalSkills int                   `json:"canonical_skills"`
	BlockedSkills   map[string][]string   `json:"blocked_skills,omitempty"`
	Targets         []TargetInstallResult `json:"targets"`
	PostSync        SyncReport            `json:"post_sync"`
}

var excludedDirNames = map[string]bool{
	".git":          true,
	"__pycache__":   true,
	".pytest_cache": true,
	".mypy_cache":   true,
	".ruff_cache":   true,
	"node_modules":  true,
	".venv":         true,
	"venv":          true,
}

// DetectTargets probes the host filesystem for known agentic environments.
func DetectTargets() []TargetDef {
	home, err := os.UserHomeDir()
	if err != nil || home == "" {
		return nil
	}

	candidates := []TargetDef{
		{
			ID:        "claude",
			Name:      "Claude Code (~/.claude)",
			RootDir:   filepath.Join(home, ".claude"),
			SkillsDir: filepath.Join(home, ".claude", "skills"),
		},
		{
			ID:        "antigravity",
			Name:      "Google Antigravity (~/.gemini/config)",
			RootDir:   filepath.Join(home, ".gemini", "config"),
			SkillsDir: filepath.Join(home, ".gemini", "config", "skills"),
		},
		{
			ID:        "dsh",
			Name:      "DeepSeek Harness (~/.dsh)",
			RootDir:   filepath.Join(home, ".dsh"),
			SkillsDir: filepath.Join(home, ".dsh", "skills"),
		},
	}

	if localApp := os.Getenv("LOCALAPPDATA"); localApp != "" {
		raiDir := filepath.Join(localApp, "RAI", "CLI")
		candidates = append(candidates, TargetDef{
			ID:        "resolveai",
			Name:      "Resolve AI (%LOCALAPPDATA%/RAI/CLI)",
			RootDir:   raiDir,
			SkillsDir: filepath.Join(raiDir, "skills"),
		})
	} else {
		raiDir := filepath.Join(home, ".resolveai")
		candidates = append(candidates, TargetDef{
			ID:        "resolveai",
			Name:      "Resolve AI (~/.resolveai)",
			RootDir:   raiDir,
			SkillsDir: filepath.Join(raiDir, "skills"),
		})
	}

	var detected []TargetDef
	for _, c := range candidates {
		if st, err := os.Stat(c.RootDir); err == nil && st.IsDir() {
			detected = append(detected, c)
		}
	}
	return detected
}

func normalizeLF(b []byte) []byte {
	return bytes.ReplaceAll(b, []byte("\r\n"), []byte("\n"))
}

func sha256Hex(b []byte) string {
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

// Verify compares all canonical skills in cat against the given targets (or DetectTargets() if nil).
func Verify(cat *catalog.Catalog, targets []TargetDef) SyncReport {
	if targets == nil {
		targets = DetectTargets()
	}
	totalSkills := len(cat.Skills)
	skillSynced := make(map[string]bool, totalSkills)

	if len(targets) == 0 {
		return SyncReport{
			AllSynced:       false,
			TargetsDetected: 0,
			TotalMissing:    totalSkills,
			TotalOutdated:   0,
			Targets:         []TargetSyncReport{},
			SkillSynced:     skillSynced,
		}
	}

	for _, sk := range cat.Skills {
		skillSynced[sk.Name] = true
	}

	canonBytes := make(map[string][]byte, totalSkills)
	for _, sk := range cat.Skills {
		raw, err := os.ReadFile(sk.FilePath)
		if err == nil {
			canonBytes[sk.Name] = normalizeLF(raw)
		}
	}

	reports := make([]TargetSyncReport, 0, len(targets))
	totalMissing := 0
	totalOutdated := 0
	allSynced := true

	for _, td := range targets {
		rep := TargetSyncReport{
			ID:          td.ID,
			Name:        td.Name,
			SkillsDir:   filepath.ToSlash(td.SkillsDir),
			TotalSkills: totalSkills,
		}
		for _, sk := range cat.Skills {
			dstFile := filepath.Join(td.SkillsDir, sk.Name, "SKILL.md")
			dstRaw, err := os.ReadFile(dstFile)
			if err != nil {
				rep.MissingCount++
				skillSynced[sk.Name] = false
				continue
			}
			if !bytes.Equal(normalizeLF(dstRaw), canonBytes[sk.Name]) {
				rep.OutdatedCount++
				skillSynced[sk.Name] = false
				continue
			}
			rep.SyncedCount++
		}
		rep.IsSynced = rep.MissingCount == 0 && rep.OutdatedCount == 0 && rep.SyncedCount == totalSkills
		if !rep.IsSynced {
			allSynced = false
		}
		totalMissing += rep.MissingCount
		totalOutdated += rep.OutdatedCount
		reports = append(reports, rep)
	}

	return SyncReport{
		AllSynced:       allSynced,
		TargetsDetected: len(reports),
		TotalMissing:    totalMissing,
		TotalOutdated:   totalOutdated,
		Targets:         reports,
		SkillSynced:     skillSynced,
	}
}

// AuditSkills performs the fail-closed security gate on canonical skills before installation.
func AuditSkills(cat *catalog.Catalog) map[string][]string {
	blocked := make(map[string][]string)
	for _, sk := range cat.Skills {
		var reasons []string
		if !sk.ValidUTF8 {
			reasons = append(reasons, "UTF-8 inválido em SKILL.md")
		}
		if !sk.HasDefense {
			reasons = append(reasons, "Linha de Defesa de Prompt ausente em SKILL.md")
		}
		raw, err := os.ReadFile(sk.FilePath)
		if err != nil {
			reasons = append(reasons, fmt.Sprintf("erro ao ler SKILL.md: %v", err))
		} else {
			findings := secretscan.ScanContent(sk.FilePath, raw)
			for _, f := range findings {
				if f.Severity == "CRITICAL" || f.Severity == "HIGH" {
					reasons = append(reasons, fmt.Sprintf("[%s] linha %d", f.RuleID, f.Line))
				}
			}
		}
		if len(reasons) > 0 {
			blocked[sk.Name] = reasons
		}
	}
	return blocked
}

type skillFileAsset struct {
	skillName string
	relPath   string
	data      []byte
	sha256    string
}

func collectSkillAssets(cat *catalog.Catalog, blocked map[string][]string) ([]skillFileAsset, error) {
	var assets []skillFileAsset
	for _, sk := range cat.Skills {
		if _, isBlocked := blocked[sk.Name]; isBlocked {
			continue
		}
		err := filepath.WalkDir(sk.DirPath, func(path string, d fs.DirEntry, err error) error {
			if err != nil {
				return err
			}
			if d.IsDir() {
				if path != sk.DirPath && excludedDirNames[d.Name()] {
					return filepath.SkipDir
				}
				return nil
			}
			if excludedDirNames[d.Name()] || strings.HasSuffix(d.Name(), ".pyc") {
				return nil
			}
			rel, err := filepath.Rel(sk.DirPath, path)
			if err != nil {
				return err
			}
			raw, err := os.ReadFile(path)
			if err != nil {
				return err
			}
			// Normalize SKILL.md and .md files to LF so cross-target comparisons are 100% deterministic
			ext := strings.ToLower(filepath.Ext(path))
			if ext == ".md" || ext == ".txt" || ext == ".yaml" || ext == ".yml" || ext == ".json" {
				raw = normalizeLF(raw)
			}
			assets = append(assets, skillFileAsset{
				skillName: sk.Name,
				relPath:   filepath.ToSlash(rel),
				data:      raw,
				sha256:    sha256Hex(raw),
			})
			return nil
		})
		if err != nil {
			return nil, err
		}
	}
	return assets, nil
}

// InstallAll synchronizes all audited canonical skills concurrently across all detected targets.
func InstallAll(rootDir string) (*InstallSummary, error) {
	cat, err := catalog.Load(rootDir)
	if err != nil {
		return nil, err
	}
	return InstallToTargets(cat, DetectTargets())
}

// InstallToTargets synchronizes all audited canonical skills concurrently to the specified targets.
func InstallToTargets(cat *catalog.Catalog, targets []TargetDef) (*InstallSummary, error) {
	if targets == nil {
		targets = DetectTargets()
	}
	t0 := time.Now()
	blocked := AuditSkills(cat)
	assets, err := collectSkillAssets(cat, blocked)
	if err != nil {
		return nil, err
	}

	results := make([]TargetInstallResult, len(targets))
	var wg sync.WaitGroup
	var firstErr error
	var errMu sync.Mutex

	validSkillsCount := len(cat.Skills) - len(blocked)

	for i, td := range targets {
		wg.Add(1)
		go func(idx int, target TargetDef) {
			defer wg.Done()
			res, err := syncSingleTarget(target, assets, validSkillsCount)
			if err != nil {
				errMu.Lock()
				if firstErr == nil {
					firstErr = err
				}
				errMu.Unlock()
				return
			}
			results[idx] = res
		}(i, td)
	}
	wg.Wait()

	if firstErr != nil {
		return nil, firstErr
	}

	postSync := Verify(cat, targets)
	durMs := float64(time.Since(t0).Microseconds()) / 1000.0

	return &InstallSummary{
		Generator:       "squad-harness install (Go 1.24.3 native)",
		DurationMs:      durMs,
		CanonicalSkills: len(cat.Skills),
		BlockedSkills:   blocked,
		Targets:         results,
		PostSync:        postSync,
	}, nil
}

func syncSingleTarget(target TargetDef, assets []skillFileAsset, validSkillsCount int) (TargetInstallResult, error) {
	res := TargetInstallResult{
		ID:           target.ID,
		Name:         target.Name,
		SkillsDir:    filepath.ToSlash(target.SkillsDir),
		SkillsSynced: validSkillsCount,
	}

	if err := os.MkdirAll(target.SkillsDir, 0o755); err != nil {
		return res, err
	}

	manifestFiles := make(map[string]map[string]string, len(assets))

	for _, a := range assets {
		dstPath := filepath.Join(target.SkillsDir, a.skillName, filepath.FromSlash(a.relPath))
		relKey := "skills/" + a.skillName + "/" + a.relPath

		existing, err := os.ReadFile(dstPath)
		if err != nil {
			if err := os.MkdirAll(filepath.Dir(dstPath), 0o755); err != nil {
				return res, err
			}
			if err := os.WriteFile(dstPath, a.data, 0o644); err != nil {
				return res, err
			}
			res.FilesInstalled++
		} else if bytes.Equal(normalizeLF(existing), normalizeLF(a.data)) {
			// If destination had CRLF and canonical is LF, normalize on disk so SHA-256 matches
			if !bytes.Equal(existing, a.data) {
				_ = os.WriteFile(dstPath, a.data, 0o644)
				res.FilesUpdated++
			} else {
				res.FilesUnchanged++
			}
		} else {
			if err := os.WriteFile(dstPath, a.data, 0o644); err != nil {
				return res, err
			}
			res.FilesUpdated++
		}

		manifestFiles[relKey] = map[string]string{
			"sha256":   a.sha256,
			"category": "skills",
		}
	}

	// Write deterministic .squad-ai-manifest.json
	keys := make([]string, 0, len(manifestFiles))
	for k := range manifestFiles {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	manifestPath := filepath.Join(target.RootDir, ".squad-ai-manifest.json")
	manifestPayload := map[string]any{
		"schema":       1,
		"installed_at": time.Now().UTC().Format(time.RFC3339),
		"generator":    "squad-harness install (Go 1.24.3)",
		"target":       filepath.ToSlash(target.RootDir),
		"files":        manifestFiles,
	}
	if rawManifest, err := json.MarshalIndent(manifestPayload, "", "  "); err == nil {
		_ = os.WriteFile(manifestPath, append(rawManifest, '\n'), 0o644)
	}
	res.ManifestPath = filepath.ToSlash(manifestPath)
	return res, nil
}
