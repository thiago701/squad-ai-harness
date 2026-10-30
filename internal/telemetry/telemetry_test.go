package telemetry

import (
	"strings"
	"testing"
)

func TestMatchTriggerNaturalLanguageAndTypos(t *testing.T) {
	cases := []struct {
		prompt   string
		expected bool
		quid     string
	}{
		{"Squad ai, gere relatorio de usoi", true, ""},
		{"Squad ai, gere relatorio de uso", true, ""},
		{"Squad ai. me mostre seu relatorio", true, ""},
		{"Squad ai, me mostre seu relatório", true, ""},
		{"Squad ai, mostre seu relatorio QUID-SQ8-1A2B-3C4D", true, "QUID-SQ8-1A2B-3C4D"},
		{"Squad ai, prepare a equipe", false, ""},
		{"implemente um endpoint em golang", false, ""},
	}

	for _, tc := range cases {
		matched, q := MatchTrigger(tc.prompt)
		if matched != tc.expected {
			t.Fatalf("MatchTrigger(%q) = %v, want %v", tc.prompt, matched, tc.expected)
		}
		if q != tc.quid {
			t.Fatalf("MatchTrigger(%q) quid = %q, want %q", tc.prompt, q, tc.quid)
		}
	}
}

func TestQuantumIDAndExecutiveASCIIReport(t *testing.T) {
	tmpDir := t.TempDir()

	id1, err := LoadOrCreateQUID(tmpDir)
	if err != nil {
		t.Fatalf("LoadOrCreateQUID failed: %v", err)
	}
	if !strings.HasPrefix(id1.QUID, "QUID-SQ8-") {
		t.Fatalf("invalid QUID prefix: %s", id1.QUID)
	}

	id2, err := LoadOrCreateQUID(tmpDir)
	if err != nil {
		t.Fatalf("second LoadOrCreateQUID failed: %v", err)
	}
	if id1.QUID != id2.QUID || id1.QuantumDigest != id2.QuantumDigest {
		t.Fatalf("QUID must be stable and persistent per cloned repo: got %s vs %s", id1.QUID, id2.QUID)
	}

	// Measure non-blocking async recording overhead
	RecordAsync(tmpDir, "preflight", 9.4)
	RecordOperation(tmpDir, "gate", 288.1)

	rep := GenerateReport(tmpDir, 3)
	if rep.TotalWorkedHours <= 0 || rep.TotalSavedHours <= 0 {
		t.Fatalf("expected positive worked and saved hours: worked=%.2f saved=%.2f", rep.TotalWorkedHours, rep.TotalSavedHours)
	}
	if rep.TotalTokensSaved <= 0 || rep.TotalSavingsUSD <= 0 || rep.TotalSavingsBRL <= 0 {
		t.Fatalf("expected positive token savings in USD and BRL: tokens=%d usd=%.2f brl=%.2f",
			rep.TotalTokensSaved, rep.TotalSavingsUSD, rep.TotalSavingsBRL)
	}
	if len(rep.Monthly) < 3 {
		t.Fatalf("expected at least 3 monthly buckets, got %d", len(rep.Monthly))
	}
	if len(rep.Daily) == 0 {
		t.Fatalf("expected daily buckets in 3-month report")
	}
	if !strings.Contains(rep.ASCII, id1.QUID) || !strings.Contains(rep.ASCII, "US$") || !strings.Contains(rep.ASCII, "R$") {
		t.Fatalf("ASCII report missing expected sections:\n%s", rep.ASCII)
	}

	// Test offline QUID resolution
	resolved, ok := ResolveByQUID(id1.ShortID, tmpDir)
	if !ok {
		t.Fatalf("expected ResolveByQUID(%s) to succeed offline", id1.ShortID)
	}
	if resolved.QUID != id1.QUID {
		t.Fatalf("resolved QUID mismatch: got %s, want %s", resolved.QUID, id1.QUID)
	}
}
