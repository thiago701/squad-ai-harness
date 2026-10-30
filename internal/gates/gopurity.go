// Package gates — gopurity.go enforces the exclusive Go-only source code lock
// and immutable authorship verification (.author) for SquadAI Harness.
// It guarantees that no colleague or agent can mix Python, Node/JS/TS, Java, Rust,
// C#, Ruby, PHP, or shell scripts into the harness codebase.
package gates

import (
	"encoding/json"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"

	"github.com/thiago701/squad-ai-harness/pkg/contracts"
)

// AuthorMetadata represents the canonical hidden .author file at the repository root.
type AuthorMetadata struct {
	Project           string `json:"project"`
	Author            string `json:"author"`
	Email             string `json:"email"`
	GitHub            string `json:"github"`
	CreatedAt         string `json:"created_at"`
	ExclusiveLanguage string `json:"exclusive_language"`
}

// GoPurityReport summarizes the Go-exclusive language lock and authorship check.
type GoPurityReport struct {
	Passed       bool     `json:"passed"`
	AuthorValid  bool     `json:"author_valid"`
	GoFilesCount int      `json:"go_files_count"`
	Violations   []string `json:"violations,omitempty"`
}

var forbiddenRootManifests = map[string]bool{
	"package.json":      true,
	"package-lock.json": true,
	"yarn.lock":         true,
	"pnpm-lock.yaml":    true,
	"tsconfig.json":     true,
	"pyproject.toml":    true,
	"requirements.txt":  true,
	"setup.py":          true,
	"pipfile":           true,
	"poetry.lock":       true,
	"uv.lock":           true,
	"cargo.toml":        true,
	"cargo.lock":        true,
	"pom.xml":           true,
	"build.gradle":      true,
	"build.gradle.kts":  true,
	"gemfile":           true,
	"composer.json":     true,
}

var forbiddenHarnessSourceExts = map[string]string{
	".py":     "Python",
	".pyc":    "Python Bytecode",
	".pyo":    "Python Bytecode",
	".ipynb":  "Jupyter Notebook",
	".js":     "JavaScript",
	".mjs":    "JavaScript ESM",
	".cjs":    "JavaScript CommonJS",
	".ts":     "TypeScript",
	".tsx":    "TypeScript JSX",
	".jsx":    "React JSX",
	".java":   "Java",
	".class":  "Java Bytecode",
	".jar":    "Java Archive",
	".kt":     "Kotlin",
	".cs":     "C# / .NET",
	".fs":     "F# / .NET",
	".vb":     "VB.NET",
	".rs":     "Rust",
	".rb":     "Ruby",
	".php":    "PHP",
	".pl":     "Perl",
	".lua":    "Lua",
	".scala":  "Scala",
	".groovy": "Groovy",
	".dart":   "Dart",
	".swift":  "Swift",
	".c":      "C (CGO proibido)",
	".cpp":    "C++ (CGO proibido)",
	".cc":     "C++ (CGO proibido)",
	".h":      "C Header (CGO proibido)",
	".hpp":    "C++ Header (CGO proibido)",
	".sh":     "Shell Script",
	".bash":   "Bash Script",
	".zsh":    "Zsh Script",
	".ps1":    "PowerShell Script",
	".bat":    "Batch Script",
	".cmd":    "Windows CMD Script",
	".vbs":    "VBScript",
}

// CheckFilePathAllowed checks if a single file path violates the Go-Exclusive Source Lock.
// Passive reference catalogs (`skills/` and `templates/`) are exempted because they hold
// multi-stack reference templates for target user projects, never harness runtime code.
func CheckFilePathAllowed(rootDir, targetPath string) (bool, string) {
	absRoot, err := filepath.Abs(rootDir)
	if err != nil {
		absRoot = filepath.Clean(rootDir)
	}
	absTarget := targetPath
	if !filepath.IsAbs(targetPath) {
		absTarget = filepath.Join(absRoot, targetPath)
	}
	absTarget = filepath.Clean(absTarget)

	rel, err := filepath.Rel(absRoot, absTarget)
	if err != nil || strings.HasPrefix(rel, "..") {
		return true, ""
	}
	relSlash := filepath.ToSlash(rel)
	parts := strings.Split(relSlash, "/")
	if len(parts) == 0 {
		return true, ""
	}

	topDir := parts[0]
	// Passive reference catalogs for target projects
	if topDir == "skills" || topDir == "templates" || topDir == ".git" || topDir == ".squad-harness" {
		return true, ""
	}

	baseLower := strings.ToLower(filepath.Base(absTarget))
	if forbiddenRootManifests[baseLower] {
		return false, fmt.Sprintf("manifesto de outra linguagem/ecossistema proibido no SquadAI Harness (%s) — projeto travado exclusivamente para Go (Golang 1.24.3+)", relSlash)
	}

	ext := strings.ToLower(filepath.Ext(absTarget))
	if lang, bad := forbiddenHarnessSourceExts[ext]; bad {
		return false, fmt.Sprintf("arquivo de código %s (%s) proibido fora de skills/ e templates/ — o fonte do SquadAI Harness é exclusivo em Go (Golang)", lang, relSlash)
	}

	return true, ""
}

// VerifyGoExclusiveLock audits the entire repository to enforce the Go-only source lock
// and verify the hidden `.author` metadata file.
func VerifyGoExclusiveLock(rootDir string) GoPurityReport {
	var rep GoPurityReport

	// 1. Validate hidden .author file at repository root
	authorPath := filepath.Join(rootDir, ".author")
	rawAuthor, err := os.ReadFile(authorPath)
	if err != nil {
		rep.Violations = append(rep.Violations, "arquivo oculto obrigatório '.author' ausente na raiz do repositório")
	} else {
		var meta AuthorMetadata
		if err := json.Unmarshal(rawAuthor, &meta); err != nil {
			rep.Violations = append(rep.Violations, fmt.Sprintf("arquivo '.author' corrompido (JSON inválido): %v", err))
		} else if meta.Email != contracts.AuthorEmail || meta.CreatedAt != contracts.CreatedAt || !strings.Contains(meta.Author, "Thiago") {
			rep.Violations = append(rep.Violations, fmt.Sprintf("metadados de autoria adulterados em '.author': got author=%q email=%q created_at=%q",
				meta.Author, meta.Email, meta.CreatedAt))
		} else {
			rep.AuthorValid = true
		}
	}

	// 2. Validate go.mod (Go 1.24.3+ and zero external dependencies)
	goModPath := filepath.Join(rootDir, "go.mod")
	rawMod, err := os.ReadFile(goModPath)
	if err != nil {
		rep.Violations = append(rep.Violations, "go.mod ausente na raiz do projeto")
	} else {
		modText := string(rawMod)
		if !strings.Contains(modText, "go 1.24") {
			rep.Violations = append(rep.Violations, "go.mod deve declarar toolchain Go 1.24+")
		}
		if strings.Contains(modText, "require ") || strings.Contains(modText, "require(") {
			rep.Violations = append(rep.Violations, "go.mod contém dependências externas ('require') — o SquadAI Harness exige stdlib pura (Zero External Dependencies)")
		}
	}

	// 3. Walk repository (excluding skills/, templates/, .git/, .squad-harness/) to block any non-Go code
	_ = filepath.WalkDir(rootDir, func(path string, d fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return nil
		}
		if d.IsDir() {
			name := d.Name()
			if path != rootDir && (name == ".git" || name == ".squad-harness" || name == "skills" || name == "templates") {
				return filepath.SkipDir
			}
			return nil
		}
		if strings.EqualFold(filepath.Ext(d.Name()), ".go") {
			rep.GoFilesCount++
			return nil
		}
		if ok, reason := CheckFilePathAllowed(rootDir, path); !ok {
			rep.Violations = append(rep.Violations, reason)
		}
		return nil
	})

	if rep.GoFilesCount == 0 {
		rep.Violations = append(rep.Violations, "nenhum arquivo .go encontrado no projeto")
	}

	rep.Passed = rep.AuthorValid && len(rep.Violations) == 0
	return rep
}
