package scheduler

import (
	"testing"
)

func TestRelationalPeakRAMPredictorPreventsOOM(t *testing.T) {
	s := NewScheduler(2560)
	task := TaskDescriptor{
		ID:                "sekg-full-index",
		Kind:              WorkloadMemoryHeavy,
		InputSizeKB:       850,
		SubgraphNodes:     600,
		SubgraphEdges:     4800,
		ConcurrentWorkers: 4,
	}
	_, _, estMB := s.CheckAdmission(task)
	// True peak around 830 MB; old static 400 MB guess would underpredict and risk OOM!
	if estMB < 800 || estMB > 950 {
		t.Fatalf("expected relational 8D prediction in [800, 950] MB with P95 margin, got %d MB", estMB)
	}
}
