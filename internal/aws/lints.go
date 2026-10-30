// Package aws implements deterministic linters for AWS Step Functions (ASL),
// API Gateway Velocity templates (VTL), and the production Read-Only Command Guard (AGENTS.md §8).
package aws

import (
	"encoding/json"
	"fmt"
	"strings"
)

// LintIssue represents a validation error in an ASL state machine or VTL template.
type LintIssue struct {
	Rule    string `json:"rule"`
	Path    string `json:"path"`
	Message string `json:"message"`
}

// ValidateASL validates an Amazon States Language (ASL) JSON state machine definition.
func ValidateASL(filePath string, rawJSON []byte) []LintIssue {
	var doc map[string]any
	if err := json.Unmarshal(rawJSON, &doc); err != nil {
		return []LintIssue{{Rule: "ASL-JSON-SYNTAX", Path: filePath, Message: fmt.Sprintf("JSON inválido: %v", err)}}
	}

	var issues []LintIssue
	startAt, _ := doc["StartAt"].(string)
	if strings.TrimSpace(startAt) == "" {
		issues = append(issues, LintIssue{Rule: "ASL-START-AT", Path: filePath, Message: "Campo obrigatório 'StartAt' ausente"})
	}

	states, ok := doc["States"].(map[string]any)
	if !ok || len(states) == 0 {
		issues = append(issues, LintIssue{Rule: "ASL-STATES-EMPTY", Path: filePath, Message: "Objeto 'States' ausente ou vazio"})
		return issues
	}

	if startAt != "" {
		if _, exists := states[startAt]; !exists {
			issues = append(issues, LintIssue{
				Rule:    "ASL-START-MISSING",
				Path:    filePath,
				Message: fmt.Sprintf("StartAt aponta para estado inexistente %q", startAt),
			})
		}
	}

	hasTerminal := false
	for stateName, stRaw := range states {
		st, ok := stRaw.(map[string]any)
		if !ok {
			continue
		}
		stType, _ := st["Type"].(string)
		if stType == "Succeed" || stType == "Fail" {
			hasTerminal = true
		}
		if endVal, ok := st["End"].(bool); ok && endVal {
			hasTerminal = true
		}
		if nextState, ok := st["Next"].(string); ok && nextState != "" {
			if _, targetExists := states[nextState]; !targetExists {
				issues = append(issues, LintIssue{
					Rule:    "ASL-DANGLING-NEXT",
					Path:    filePath,
					Message: fmt.Sprintf("Estado %q referencia Next %q inexistente", stateName, nextState),
				})
			}
		}
	}

	if !hasTerminal {
		issues = append(issues, LintIssue{
			Rule:    "ASL-NO-TERMINAL",
			Path:    filePath,
			Message: "Máquina de estados ASL não possui nenhum estado terminal (End: true, Succeed ou Fail)",
		})
	}
	return issues
}

// ValidateVTL checks API Gateway VTL templates for unescaped tenant isolation or stacktrace leaks.
func ValidateVTL(filePath string, content string) []LintIssue {
	var issues []LintIssue
	if strings.Contains(content, "stackTrace") || strings.Contains(content, "errorMessage") && strings.Contains(content, "$input.json('$')") {
		issues = append(issues, LintIssue{
			Rule:    "VTL-ERROR-EXPOSURE",
			Path:    filePath,
			Message: "Possível exposição de detalhes internos no payload VTL",
		})
	}
	return issues
}

var mutatingAWSVerbs = []string{
	"create-", "delete-", "update-", "put-", "remove-", "terminate-",
	"stop-", "start-", "reboot-", "modify-", "attach-", "detach-",
	"invoke", "execute-", "run-instances", "s3 rm", "s3 rb", "s3 mv", "s3 cp",
}

// CheckReadOnlyAWSCommand enforces the read-only production guard (scripts/aws/guarda_somente_leitura.py).
func CheckReadOnlyAWSCommand(cmdLine string) (bool, string) {
	lower := strings.ToLower(strings.TrimSpace(cmdLine))
	if !strings.HasPrefix(lower, "aws ") {
		return true, ""
	}
	for _, verb := range mutatingAWSVerbs {
		if strings.Contains(lower, " "+verb) {
			return false, fmt.Sprintf("comando AWS mutante bloqueado pela guarda somente-leitura (%s)", verb)
		}
	}
	return true, ""
}
