// Package installer implements the native Go 1.24.3 multi-target skill installer
// and synchronizer (`squad-harness install`), supporting 12 agentic coding tools
// across diverse developers and enterprises without polluting workstations with
// unused agent directories.
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

// ToolAdoptionStatus classifies how an agentic tool relates to the current workstation.
type ToolAdoptionStatus string

const (
	// StatusActiveSynced means the tool is used on this machine and all 106 skills are up to date.
	StatusActiveSynced ToolAdoptionStatus = "ACTIVE_SYNCED"
	// StatusActiveOutdated means the tool is used on this machine and has missing/outdated skills.
	StatusActiveOutdated ToolAdoptionStatus = "ACTIVE_OUTDATED"
	// StatusDetectedOptIn means the tool's base folder exists on the host, available for 1-click activation.
	StatusDetectedOptIn ToolAdoptionStatus = "DETECTED_OPT_IN"
	// StatusNotInstalled means the tool is not used on this workstation (silently ignored).
	StatusNotInstalled ToolAdoptionStatus = "NOT_INSTALLED"
)

// TargetDef describes a supported agentic tool environment in the enterprise/developer catalog.
type TargetDef struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Vendor      string `json:"vendor"`
	DisplayPath string `json:"display_path"`
	RootDir     string `json:"root_dir"`
	SkillsDir   string `json:"skills_dir"`
	PrimaryAuto bool   `json:"primary_auto"` // Auto-targeted when RootDir exists
	HostPresent bool   `json:"host_present"` // Whether RootDir exists on this workstation
	ActiveSync  bool   `json:"active_sync"`  // Whether this target participates in active sync/validation
}

// TargetSyncReport reports the live synchronization status of one agentic environment.
type TargetSyncReport struct {
	ID            string             `json:"id"`
	Name          string             `json:"name"`
	Vendor        string             `json:"vendor"`
	DisplayPath   string             `json:"display_path"`
	SkillsDir     string             `json:"skills_dir"`
	Status        ToolAdoptionStatus `json:"status"`
	HostPresent   bool               `json:"host_present"`
	ActiveSync    bool               `json:"active_sync"`
	TotalSkills   int                `json:"total_skills"`
	SyncedCount   int                `json:"synced_count"`
	MissingCount  int                `json:"missing_count"`
	OutdatedCount int                `json:"outdated_count"`
	IsSynced      bool               `json:"is_synced"`
}

// SyncReport aggregates synchronization status across active targets and lists all supported tools.
type SyncReport struct {
	AllSynced         bool               `json:"all_synced"`
	TargetsDetected   int                `json:"targets_detected"`   // Active sync targets count
	HostToolsDetected int                `json:"host_tools_detected"` // Total agentic tools found on host
	CatalogToolsCount int                `json:"catalog_tools_count"` // Total supported tools in catalog (12)
	TotalMissing      int                `json:"total_missing"`
	TotalOutdated     int                `json:"total_outdated"`
	Targets           []TargetSyncReport `json:"targets"`      // Active targets participating in validation
	AllCatalog        []TargetSyncReport `json:"all_catalog"`  // Full 12-tool enterprise catalog with adoption status
	SkillSynced       map[string]bool    `json:"skill_synced"` // Per-skill sync flag across active targets
}

// TargetInstallResult summarizes files synchronized for a single target environment.
type TargetInstallResult struct {
	ID             string `json:"id"`
	Name           string `json:"name"`
	DisplayPath    string `json:"display_path"`
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

// SupportedCatalog returns the 12 supported enterprise/developer agentic tools
// and probes the host filesystem non-destructively to determine which ones are present
// and which ones are actively managing skills.
func SupportedCatalog() []TargetDef {
	home, err := os.UserHomeDir()
	if err != nil || home == "" {
		return nil
	}

	raiRoot := filepath.Join(home, ".resolveai")
	raiDisplay := "~/.resolveai/skills"
	if localApp := os.Getenv("LOCALAPPDATA"); localApp != "" {
		cand := filepath.Join(localApp, "RAI", "CLI")
		if st, err := os.Stat(cand); err == nil && st.IsDir() {
			raiRoot = cand
			raiDisplay = "%LOCALAPPDATA%/RAI/CLI/skills"
		}
	}

	defs := []TargetDef{
		{
			ID:          "claude",
			Name:        "Claude Code / Cowork",
			Vendor:      "Anthropic",
			DisplayPath: "~/.claude/skills",
			RootDir:     filepath.Join(home, ".claude"),
			SkillsDir:   filepath.Join(home, ".claude", "skills"),
			PrimaryAuto: true,
		},
		{
			ID:          "antigravity",
			Name:        "Google Antigravity",
			Vendor:      "Google DeepMind",
			DisplayPath: "~/.gemini/config/skills",
			RootDir:     filepath.Join(home, ".gemini", "config"),
			SkillsDir:   filepath.Join(home, ".gemini", "config", "skills"),
			PrimaryAuto: true,
		},
		{
			ID:          "cursor",
			Name:        "Cursor IDE",
			Vendor:      "Anysphere",
			DisplayPath: "~/.cursor/skills",
			RootDir:     filepath.Join(home, ".cursor"),
			SkillsDir:   filepath.Join(home, ".cursor", "skills"),
			PrimaryAuto: true,
		},
		{
			ID:          "copilot",
			Name:        "GitHub Copilot Agent",
			Vendor:      "GitHub / Microsoft",
			DisplayPath: "~/.copilot/skills",
			RootDir:     filepath.Join(home, ".copilot"),
			SkillsDir:   filepath.Join(home, ".copilot", "skills"),
			PrimaryAuto: true,
		},
		{
			ID:          "codex",
			Name:        "OpenAI Codex CLI",
			Vendor:      "OpenAI",
			DisplayPath: "~/.codex/skills",
			RootDir:     filepath.Join(home, ".codex"),
			SkillsDir:   filepath.Join(home, ".codex", "skills"),
			PrimaryAuto: true,
		},
		{
			ID:          "windsurf",
			Name:        "Windsurf IDE",
			Vendor:      "Codeium",
			DisplayPath: "~/.codeium/windsurf/skills",
			RootDir:     filepath.Join(home, ".codeium", "windsurf"),
			SkillsDir:   filepath.Join(home, ".codeium", "windsurf", "skills"),
			PrimaryAuto: true,
		},
		{
			ID:          "gemini",
			Name:        "Gemini CLI",
			Vendor:      "Google",
			DisplayPath: "~/.gemini/skills",
			RootDir:     filepath.Join(home, ".gemini"),
			SkillsDir:   filepath.Join(home, ".gemini", "skills"),
			PrimaryAuto: true,
		},
		{
			ID:          "cline",
			Name:        "Cline / Roo Code",
			Vendor:      "Cline",
			DisplayPath: "~/.cline/skills",
			RootDir:     filepath.Join(home, ".cline"),
			SkillsDir:   filepath.Join(home, ".cline", "skills"),
			PrimaryAuto: true,
		},
		{
			ID:          "opencode",
			Name:        "OpenCode CLI",
			Vendor:      "OpenCode",
			DisplayPath: "~/.opencode/skills",
			RootDir:     filepath.Join(home, ".opencode"),
			SkillsDir:   filepath.Join(home, ".opencode", "skills"),
			PrimaryAuto: true,
		},
		{
			ID:          "qwen",
			Name:        "Qwen Code CLI",
			Vendor:      "Alibaba Cloud",
			DisplayPath: "~/.qwen/skills",
			RootDir:     filepath.Join(home, ".qwen"),
			SkillsDir:   filepath.Join(home, ".qwen", "skills"),
			PrimaryAuto: true,
		},
		{
			ID:          "dsh",
			Name:        "DeepSeek Harness",
			Vendor:      "DeepSeek",
			DisplayPath: "~/.dsh/skills",
			RootDir:     filepath.Join(home, ".dsh"),
			SkillsDir:   filepath.Join(home, ".dsh", "skills"),
			PrimaryAuto: true,
		},
		{
			ID:          "resolveai",
			Name:        "Resolve AI CLI",
			Vendor:      "Resolve AI",
			DisplayPath: raiDisplay,
			RootDir:     raiRoot,
			SkillsDir:   filepath.Join(raiRoot, "skills"),
			PrimaryAuto: true,
		},
	}

	for i := range defs {
		if st, err := os.Stat(defs[i].RootDir); err == nil && st.IsDir() {
			defs[i].HostPresent = true
		}
		manifestPath := filepath.Join(defs[i].RootDir, ".squad-ai-manifest.json")
		_, hasManifest := os.Stat(manifestPath)
		stSkills, errSkills := os.Stat(defs[i].SkillsDir)
		hasSkillsDir := errSkills == nil && stSkills.IsDir()

		// A tool is an active sync target if:
		// 1) It is present on host AND is a primary auto-target, OR
		// 2) The developer/company already opted in (has `.squad-ai-manifest.json` or `<tool>/skills/` directory).
		if defs[i].HostPresent && (defs[i].PrimaryAuto || hasManifest == nil || hasSkillsDir) {
			defs[i].ActiveSync = true
		}
	}
	return defs
}

// DetectTargets returns the active agentic environments on this workstation.
func DetectTargets() []TargetDef {
	all := SupportedCatalog()
	var active []TargetDef
	for _, d := range all {
		if d.ActiveSync {
			active = append(active, d)
		}
	}
	return active
}

// ResolveTargetsByIDs resolves specific tool IDs (e.g. ["cursor", "claude"]) from the supported catalog,
// allowing developers or enterprises to activate any tool on demand via `--target <id>`.
func ResolveTargetsByIDs(ids []string) ([]TargetDef, error) {
	all := SupportedCatalog()
	byID := make(map[string]TargetDef, len(all))
	for _, d := range all {
		byID[strings.ToLower(d.ID)] = d
	}

	var resolved []TargetDef
	seen := make(map[string]bool)
	for _, raw := range ids {
		for _, part := range strings.Split(raw, ",") {
			id := strings.ToLower(strings.TrimSpace(part))
			if id == "" || seen[id] {
				continue
			}
			d, ok := byID[id]
			if !ok {
				return nil, fmt.Errorf("ferramenta agêntica desconhecida %q (suportadas: claude, antigravity, cursor, copilot, codex, windsurf, gemini, cline, opencode, qwen, dsh, resolveai)", id)
			}
			d.HostPresent = true
			d.ActiveSync = true
			resolved = append(resolved, d)
			seen[id] = true
		}
	}
	return resolved, nil
}

func normalizeLF(b []byte) []byte {
	return bytes.ReplaceAll(b, []byte("\r\n"), []byte("\n"))
}

func sha256Hex(b []byte) string {
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

// Verify compares all canonical skills in cat against the given targets (or DetectTargets() if nil),
// and also populates AllCatalog for the 12 supported enterprise/developer tools.
func Verify(cat *catalog.Catalog, customTargets []TargetDef) SyncReport {
	totalSkills := len(cat.Skills)
	skillSynced := make(map[string]bool, totalSkills)

	canonBytes := make(map[string][]byte, totalSkills)
	for _, sk := range cat.Skills {
		raw, err := os.ReadFile(sk.FilePath)
		if err == nil {
			canonBytes[sk.Name] = normalizeLF(raw)
		}
	}

	var catalogDefs []TargetDef
	if customTargets != nil {
		catalogDefs = make([]TargetDef, len(customTargets))
		for i, t := range customTargets {
			t.HostPresent = true
			t.ActiveSync = true
			if t.DisplayPath == "" {
				t.DisplayPath = filepath.ToSlash(t.SkillsDir)
			}
			catalogDefs[i] = t
		}
	} else {
		catalogDefs = SupportedCatalog()
	}

	activeReports := make([]TargetSyncReport, 0, len(catalogDefs))
	allCatalogReports := make([]TargetSyncReport, 0, len(catalogDefs))
	totalMissing := 0
	totalOutdated := 0
	hostToolsCount := 0
	allSynced := true

	for _, sk := range cat.Skills {
		skillSynced[sk.Name] = true
	}

	for _, td := range catalogDefs {
		if td.HostPresent {
			hostToolsCount++
		}
		rep := TargetSyncReport{
			ID:          td.ID,
			Name:        td.Name,
			Vendor:      td.Vendor,
			DisplayPath: td.DisplayPath,
			SkillsDir:   filepath.ToSlash(td.SkillsDir),
			HostPresent: td.HostPresent,
			ActiveSync:  td.ActiveSync,
			TotalSkills: totalSkills,
		}

		if !td.ActiveSync {
			if td.HostPresent {
				rep.Status = StatusDetectedOptIn
			} else {
				rep.Status = StatusNotInstalled
			}
			allCatalogReports = append(allCatalogReports, rep)
			continue
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
		if rep.IsSynced {
			rep.Status = StatusActiveSynced
		} else {
			rep.Status = StatusActiveOutdated
			allSynced = false
		}

		totalMissing += rep.MissingCount
		totalOutdated += rep.OutdatedCount
		activeReports = append(activeReports, rep)
		allCatalogReports = append(allCatalogReports, rep)
	}

	if len(activeReports) == 0 {
		allSynced = false
		for _, sk := range cat.Skills {
			skillSynced[sk.Name] = false
		}
	}

	return SyncReport{
		AllSynced:         allSynced,
		TargetsDetected:   len(activeReports),
		HostToolsDetected: hostToolsCount,
		CatalogToolsCount: len(allCatalogReports),
		TotalMissing:      totalMissing,
		TotalOutdated:     totalOutdated,
		Targets:           activeReports,
		AllCatalog:        allCatalogReports,
		SkillSynced:       skillSynced,
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

type commandFileAsset struct {
	name   string
	data   []byte
	sha256 string
}

func collectCommandAssets(rootDir string) []commandFileAsset {
	cmdsGlob, err := filepath.Glob(filepath.Join(rootDir, ".claude", "commands", "*.md"))
	if err != nil {
		return nil
	}
	sort.Strings(cmdsGlob)
	var out []commandFileAsset
	for _, p := range cmdsGlob {
		raw, err := os.ReadFile(p)
		if err != nil {
			continue
		}
		norm := normalizeLF(raw)
		out = append(out, commandFileAsset{
			name:   filepath.Base(p),
			data:   norm,
			sha256: sha256Hex(norm),
		})
	}
	return out
}

// InstallAll synchronizes all audited canonical skills concurrently across all active targets.
func InstallAll(rootDir string) (*InstallSummary, error) {
	cat, err := catalog.Load(rootDir)
	if err != nil {
		return nil, err
	}
	return InstallToTargets(cat, nil)
}

// InstallToTargets synchronizes all audited canonical skills concurrently to the specified targets.
func InstallToTargets(cat *catalog.Catalog, targets []TargetDef) (*InstallSummary, error) {
	isCustom := targets != nil
	if targets == nil {
		targets = DetectTargets()
	}
	t0 := time.Now()
	blocked := AuditSkills(cat)
	assets, err := collectSkillAssets(cat, blocked)
	if err != nil {
		return nil, err
	}
	cmdAssets := collectCommandAssets(cat.RootDir)

	results := make([]TargetInstallResult, len(targets))
	var wg sync.WaitGroup
	var firstErr error
	var errMu sync.Mutex

	validSkillsCount := len(cat.Skills) - len(blocked)

	for i, td := range targets {
		wg.Add(1)
		go func(idx int, target TargetDef) {
			defer wg.Done()
			res, err := syncSingleTarget(target, assets, cmdAssets, validSkillsCount)
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

	// Keep interoperable ~/.agents/skills synchronized if ~/.agents exists on workstation
	if !isCustom {
		if home, err := os.UserHomeDir(); err == nil && home != "" {
			agentsRoot := filepath.Join(home, ".agents")
			if st, err := os.Stat(agentsRoot); err == nil && st.IsDir() {
				_, _ = syncSingleTarget(TargetDef{
					ID:          "agents",
					Name:        "Interoperable Agent Skills (~/.agents/skills)",
					DisplayPath: "~/.agents/skills",
					RootDir:     agentsRoot,
					SkillsDir:   filepath.Join(agentsRoot, "skills"),
				}, assets, nil, validSkillsCount)
			}
		}
	}

	var verifyTargets []TargetDef
	if isCustom {
		verifyTargets = targets
	}
	postSync := Verify(cat, verifyTargets)
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

func syncSingleTarget(target TargetDef, assets []skillFileAsset, cmdAssets []commandFileAsset, validSkillsCount int) (TargetInstallResult, error) {
	res := TargetInstallResult{
		ID:           target.ID,
		Name:         target.Name,
		DisplayPath:  target.DisplayPath,
		SkillsDir:    filepath.ToSlash(target.SkillsDir),
		SkillsSynced: validSkillsCount,
	}

	if err := os.MkdirAll(target.SkillsDir, 0o755); err != nil {
		return res, err
	}

	// Retire legacy Python installer artifacts (squad-ai-manifest.json without leading dot, report, log)
	for _, legacyName := range []string{"squad-ai-manifest.json", "squad-ai-install-report.md", "squad-ai-install.log"} {
		_ = os.Remove(filepath.Join(target.RootDir, legacyName))
	}

	manifestFiles := make(map[string]map[string]string, len(assets)+len(cmdAssets))

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

	// Synchronize .claude/commands/*.md for Claude Code and DeepSeek Harness
	if len(cmdAssets) > 0 && (target.ID == "claude" || target.ID == "dsh") {
		cmdsDir := filepath.Join(target.RootDir, "commands")
		if err := os.MkdirAll(cmdsDir, 0o755); err == nil {
			for _, cmdAsset := range cmdAssets {
				dstCmd := filepath.Join(cmdsDir, cmdAsset.name)
				existing, err := os.ReadFile(dstCmd)
				if err != nil {
					if err := os.WriteFile(dstCmd, cmdAsset.data, 0o644); err == nil {
						res.FilesInstalled++
					}
				} else if !bytes.Equal(normalizeLF(existing), cmdAsset.data) {
					if err := os.WriteFile(dstCmd, cmdAsset.data, 0o644); err == nil {
						res.FilesUpdated++
					}
				}
				manifestFiles["commands/"+cmdAsset.name] = map[string]string{
					"sha256":   cmdAsset.sha256,
					"category": "commands",
				}
			}
		}
	}

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
