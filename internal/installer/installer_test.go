package installer

import (
	"os"
	"path/filepath"
	"runtime"
	"testing"

	"github.com/thiago701/squad-ai-harness/internal/catalog"
)

func repoRoot(t *testing.T) string {
	t.Helper()
	_, file, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("cannot resolve caller")
	}
	return filepath.Clean(filepath.Join(filepath.Dir(file), "..", ".."))
}

func TestNativeGoInstallerSyncAndVerify(t *testing.T) {
	root := repoRoot(t)
	cat, err := catalog.Load(root)
	if err != nil {
		t.Fatalf("catalog.Load error: %v", err)
	}

	tmpHome := t.TempDir()
	targets := []TargetDef{
		{
			ID:        "claude-test",
			Name:      "Claude Code Test",
			RootDir:   filepath.Join(tmpHome, ".claude"),
			SkillsDir: filepath.Join(tmpHome, ".claude", "skills"),
		},
		{
			ID:        "antigravity-test",
			Name:      "Antigravity Test",
			RootDir:   filepath.Join(tmpHome, ".gemini", "config"),
			SkillsDir: filepath.Join(tmpHome, ".gemini", "config", "skills"),
		},
	}

	// 1. Before installation, Verify must report AllSynced = false and TotalMissing = 2 * len(cat.Skills)
	before := Verify(cat, targets)
	if before.AllSynced || before.TotalMissing != 2*len(cat.Skills) {
		t.Fatalf("expected all skills missing before install, got %+v", before)
	}

	// 2. Run InstallToTargets (concurrent native Go installer)
	sum, err := InstallToTargets(cat, targets)
	if err != nil {
		t.Fatalf("InstallToTargets error: %v", err)
	}
	if len(sum.BlockedSkills) != 0 {
		t.Fatalf("expected 0 blocked skills, got %+v", sum.BlockedSkills)
	}
	if !sum.PostSync.AllSynced {
		t.Fatalf("expected PostSync.AllSynced = true after install, got %+v", sum.PostSync)
	}

	// 3. Verify manifest was written in each target
	for _, tr := range sum.Targets {
		if _, err := os.Stat(filepath.FromSlash(tr.ManifestPath)); err != nil {
			t.Fatalf("missing manifest %s: %v", tr.ManifestPath, err)
		}
	}

	// 4. Mutate one skill in target 0 and verify OutdatedCount == 1
	tampered := filepath.Join(targets[0].SkillsDir, "squad-ai", "SKILL.md")
	if err := os.WriteFile(tampered, []byte("outdated content\n"), 0o644); err != nil {
		t.Fatalf("tamper write error: %v", err)
	}
	afterTamper := Verify(cat, targets)
	if afterTamper.AllSynced || afterTamper.TotalOutdated != 1 || afterTamper.SkillSynced["squad-ai"] {
		t.Fatalf("expected squad-ai to be flagged as outdated, got %+v", afterTamper)
	}
}
