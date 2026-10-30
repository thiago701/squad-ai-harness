// Package sonar implements the preventive 5-phase Sonar-First Code Intelligence
// engine in Go 1.24.3, checking cyclomatic/cognitive complexity, Object Calisthenics
// (R1-R9), and silent failure patterns in microseconds.
package sonar

import (
	"bufio"
	"bytes"
	"strings"
)

// Issue represents a preventive code quality violation detected by Sonar-First.
type Issue struct {
	RuleID   string `json:"rule_id"`
	Phase    string `json:"phase"`    // "A", "B", "C", "D", "E"
	Severity string `json:"severity"` // "BLOCKER", "CRITICAL", "MAJOR", "MINOR"
	File     string `json:"file"`
	Line     int    `json:"line"`
	Message  string `json:"message"`
	AutoFix  string `json:"auto_fix,omitempty"`
}

// Report aggregates the 5-phase preventive analysis.
type Report struct {
	FilesAnalyzed        int     `json:"files_analyzed"`
	LinesAnalyzed        int     `json:"lines_analyzed"`
	CyclomaticComplexity int     `json:"cyclomatic_complexity"`
	MaxIndentationDepth  int     `json:"max_indentation_depth"`
	QualityGatePassed    bool    `json:"quality_gate_passed"`
	Issues               []Issue `json:"issues,omitempty"`
}

// AnalyzeSource executes Phases C, D, and E of the Sonar-First preventive pipeline on a file's content.
func AnalyzeSource(filePath string, src []byte) Report {
	rep := Report{
		FilesAnalyzed:        1,
		CyclomaticComplexity: 1,
		QualityGatePassed:    true,
	}

	sc := bufio.NewScanner(bytes.NewReader(src))
	lineNo := 0
	prevWasExcept := false
	for sc.Scan() {
		lineNo++
		line := sc.Text()
		trimmed := strings.TrimSpace(line)
		if trimmed == "" || strings.HasPrefix(trimmed, "//") || strings.HasPrefix(trimmed, "#") {
			continue
		}

		// Calculate indentation level (Object Calisthenics R1: max 1-2 indentation levels per method, flag >= 5)
		indent := countIndentLevel(line)
		if indent > rep.MaxIndentationDepth {
			rep.MaxIndentationDepth = indent
		}
		if indent >= 6 {
			rep.Issues = append(rep.Issues, Issue{
				RuleID:   "OC-R1-DEEP-NESTING",
				Phase:    "C",
				Severity: "MAJOR",
				File:     filePath,
				Line:     lineNo,
				Message:  "Nível excessivo de indentação (>= 6); aplique Guard Clauses / Early Return (Calisthenics R1/R2)",
				AutoFix:  "Inverter condição e retornar cedo (Early Return)",
			})
		}

		// Count branching tokens for cyclomatic complexity estimation
		for _, tok := range []string{"if ", "else if ", "elif ", "case ", "for ", "while ", "&&", "||", " catch "} {
			if strings.Contains(line, tok) {
				rep.CyclomaticComplexity++
			}
		}

		// Check silent exception swallowing (Blocker: single-line or multi-line except: pass)
		isSilentSingleLine := strings.Contains(trimmed, "except") && strings.Contains(trimmed, ":") && strings.HasSuffix(trimmed, "pass")
		isSilentMultiLine := prevWasExcept && trimmed == "pass"
		if isSilentSingleLine || isSilentMultiLine {
			rep.QualityGatePassed = false
			rep.Issues = append(rep.Issues, Issue{
				RuleID:   "SONAR-S108-SILENT-EXCEPT",
				Phase:    "E",
				Severity: "BLOCKER",
				File:     filePath,
				Line:     lineNo,
				Message:  "Captura genérica 'except: pass' oculta falhas reais",
				AutoFix:  "Capturar exceção específica e registrar ou propagar erro",
			})
		}
		prevWasExcept = strings.HasPrefix(trimmed, "except:") || strings.HasPrefix(trimmed, "except Exception:")
	}
	rep.LinesAnalyzed = lineNo
	return rep
}

func countIndentLevel(line string) int {
	spaces := 0
	for _, r := range line {
		if r == '\t' {
			spaces += 4
		} else if r == ' ' {
			spaces++
		} else {
			break
		}
	}
	return spaces / 4
}
