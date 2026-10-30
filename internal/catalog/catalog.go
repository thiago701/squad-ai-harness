// Package catalog loads and validates the entire SquadAI Harness skill & agent
// ecosystem in a single concurrent memory pass (Etapa 2), replacing 5 separate
// Python scripts that repeatedly parsed the 106 SKILL.md files.
package catalog

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"unicode/utf8"

	"github.com/thiago701/squad-ai-harness/internal/security/secretscan"
)

// SkillEntry holds the parsed metadata and sections of a single canonical SKILL.md.
type SkillEntry struct {
	Name          string            `json:"name"`
	Description   string            `json:"description"`
	Origin        string            `json:"origin"`
	Model         string            `json:"model,omitempty"`
	DirPath       string            `json:"dir_path"`
	FilePath      string            `json:"file_path"`
	Body          string            `json:"-"`
	Headers       []string          `json:"headers,omitempty"`
	HasDefense    bool              `json:"has_defense"`
	ValidUTF8     bool              `json:"valid_utf8"`
	HasCRLF       bool              `json:"has_crlf"`
	Frontmatter   map[string]string `json:"frontmatter,omitempty"`
}

// ValidationReport summarizes the single-pass validation of the entire catalog.
type ValidationReport struct {
	CanonicalSkills int      `json:"canonical_skills"`
	AgentsCount     int      `json:"agents_count"`
	CommandsCount   int      `json:"commands_count"`
	DefenseClean    int      `json:"defense_clean"`
	UTF8Clean       int      `json:"utf8_clean"`
	RegistryDrift   bool     `json:"registry_drift"`
	Errors          []string `json:"errors,omitempty"`
}

// Catalog holds the in-memory representation of all skills, agents, and commands.
type Catalog struct {
	RootDir  string
	Skills   []SkillEntry
	Agents   []string
	Commands []string
}

// Load reads all skills/*/SKILL.md, .claude/agents/*.md, and .claude/commands/*.md
// concurrently in a single memory pass.
func Load(rootDir string) (*Catalog, error) {
	skillsGlob, err := filepath.Glob(filepath.Join(rootDir, "skills", "*", "SKILL.md"))
	if err != nil {
		return nil, err
	}
	sort.Strings(skillsGlob)

	entries := make([]SkillEntry, len(skillsGlob))
	var wg sync.WaitGroup
	sem := make(chan struct{}, 16)

	for i, p := range skillsGlob {
		wg.Add(1)
		go func(idx int, skillPath string) {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()
			entries[idx] = parseSkillFile(skillPath)
		}(i, p)
	}
	wg.Wait()

	agentsGlob, _ := filepath.Glob(filepath.Join(rootDir, ".claude", "agents", "*.md"))
	var agents []string
	for _, a := range agentsGlob {
		base := strings.TrimSuffix(filepath.Base(a), ".md")
		if strings.EqualFold(base, "README") {
			continue
		}
		agents = append(agents, base)
	}
	sort.Strings(agents)

	cmdsGlob, _ := filepath.Glob(filepath.Join(rootDir, ".claude", "commands", "*.md"))
	var commands []string
	for _, c := range cmdsGlob {
		base := strings.TrimSuffix(filepath.Base(c), ".md")
		if strings.EqualFold(base, "README") {
			continue
		}
		commands = append(commands, base)
	}
	sort.Strings(commands)

	return &Catalog{
		RootDir:  rootDir,
		Skills:   entries,
		Agents:   agents,
		Commands: commands,
	}, nil
}

func parseSkillFile(skillPath string) SkillEntry {
	dirName := filepath.Base(filepath.Dir(skillPath))
	entry := SkillEntry{
		Name:        dirName,
		DirPath:     filepath.Dir(skillPath),
		FilePath:    skillPath,
		Frontmatter: make(map[string]string),
	}

	raw, err := os.ReadFile(skillPath)
	if err != nil {
		return entry
	}
	entry.ValidUTF8 = utf8.Valid(raw)
	entry.HasCRLF = bytes.Contains(raw, []byte("\r\n"))

	text := string(raw)
	fm, body := splitFrontmatter(text)
	for k, v := range fm {
		entry.Frontmatter[k] = v
	}
	if name := fm["name"]; name != "" {
		entry.Name = name
	}
	entry.Description = fm["description"]
	entry.Origin = fm["origin"]
	entry.Model = fm["model"]
	entry.Body = body

	okDef, _ := secretscan.VerifyPromptDefenseLine(text)
	entry.HasDefense = okDef

	for _, line := range strings.Split(body, "\n") {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "## ") || strings.HasPrefix(trimmed, "### ") {
			entry.Headers = append(entry.Headers, trimmed)
		}
	}
	return entry
}

func splitFrontmatter(text string) (map[string]string, string) {
	res := make(map[string]string)
	trimmed := strings.TrimPrefix(text, "\uFEFF")
	if !strings.HasPrefix(trimmed, "---") {
		return res, text
	}
	rest := trimmed[3:]
	idx := strings.Index(rest, "\n---")
	if idx < 0 {
		return res, text
	}
	fmBlock := rest[:idx]
	body := rest[idx+4:]

	var currentKey string
	var currentVal strings.Builder
	flush := func() {
		if currentKey != "" {
			res[currentKey] = strings.Trim(strings.TrimSpace(currentVal.String()), `"'`)
			currentKey = ""
			currentVal.Reset()
		}
	}

	for _, line := range strings.Split(fmBlock, "\n") {
		if strings.TrimSpace(line) == "" || strings.HasPrefix(strings.TrimSpace(line), "#") {
			continue
		}
		if (strings.HasPrefix(line, "  ") || strings.HasPrefix(line, "\t")) && currentKey != "" {
			currentVal.WriteString(" ")
			currentVal.WriteString(strings.TrimSpace(line))
			continue
		}
		colonIdx := strings.Index(line, ":")
		if colonIdx > 0 {
			flush()
			currentKey = strings.TrimSpace(line[:colonIdx])
			val := strings.TrimSpace(line[colonIdx+1:])
			if val != "|" && val != ">" && val != ">-" && val != "|-" {
				currentVal.WriteString(val)
			}
		}
	}
	flush()
	return res, body
}

// Validate runs all structural, UTF-8, defense-line, and registry drift checks on the loaded Catalog.
func (c *Catalog) Validate() ValidationReport {
	rep := ValidationReport{
		CanonicalSkills: len(c.Skills),
		AgentsCount:     len(c.Agents),
		CommandsCount:   len(c.Commands),
	}

	var diskNames []string
	for _, sk := range c.Skills {
		folderName := filepath.Base(sk.DirPath)
		diskNames = append(diskNames, folderName)
		if sk.ValidUTF8 {
			rep.UTF8Clean++
		} else {
			rep.Errors = append(rep.Errors, fmt.Sprintf("invalid UTF-8 in %s", sk.FilePath))
		}
		if sk.HasDefense {
			rep.DefenseClean++
		} else {
			rep.Errors = append(rep.Errors, fmt.Sprintf("missing canonical Prompt Defense Line in %s", folderName))
		}
		if sk.Name != folderName {
			rep.Errors = append(rep.Errors, fmt.Sprintf("skill name %q != folder %q", sk.Name, folderName))
		}
	}
	sort.Strings(diskNames)

	regPath := filepath.Join(c.RootDir, "governance", "registry", "registry.json")
	if rawReg, err := os.ReadFile(regPath); err == nil {
		var reg struct {
			Contagens struct {
				SkillsCanonicas int `json:"skills_canonicas"`
			} `json:"contagens"`
		}
		if json.Unmarshal(rawReg, &reg) == nil {
			if reg.Contagens.SkillsCanonicas != len(c.Skills) {
				rep.RegistryDrift = true
				rep.Errors = append(rep.Errors, fmt.Sprintf("registry drift: registry.json has %d skills, disk has %d",
					reg.Contagens.SkillsCanonicas, len(c.Skills)))
			}
		}
	}

	return rep
}
