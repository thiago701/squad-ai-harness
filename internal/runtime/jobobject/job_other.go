//go:build !windows

package jobobject

import (
	"bufio"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"syscall"
)

// ProbeSystemMemory reads /proc/meminfo on Linux or returns a conservative fallback on other POSIX systems.
func ProbeSystemMemory() (SystemMemory, error) {
	f, err := os.Open("/proc/meminfo")
	if err != nil {
		return SystemMemory{TotalPhysMB: 16384, AvailPhysMB: 8192, MemoryLoadPct: 50}, nil
	}
	defer f.Close()

	var totalKB, availKB int64
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := sc.Text()
		if strings.HasPrefix(line, "MemTotal:") {
			totalKB = parseMemKB(line)
		} else if strings.HasPrefix(line, "MemAvailable:") {
			availKB = parseMemKB(line)
		}
	}
	if totalKB <= 0 {
		return SystemMemory{TotalPhysMB: 16384, AvailPhysMB: 8192, MemoryLoadPct: 50}, nil
	}
	totalMB := totalKB / 1024
	availMB := availKB / 1024
	loadPct := int(((totalMB - availMB) * 100) / totalMB)
	return SystemMemory{
		TotalPhysMB:   totalMB,
		AvailPhysMB:   availMB,
		MemoryLoadPct: loadPct,
	}, nil
}

func parseMemKB(line string) int64 {
	fields := strings.Fields(line)
	if len(fields) < 2 {
		return 0
	}
	v, _ := strconv.ParseInt(fields[1], 10, 64)
	return v
}

type platformJob struct {
	memLimitMB int64
}

func newPlatformJob(memoryLimitMB int64) (*platformJob, error) {
	return &platformJob{memLimitMB: memoryLimitMB}, nil
}

func configureCmdPlatform(cmd *exec.Cmd) {
	if cmd.SysProcAttr == nil {
		cmd.SysProcAttr = &syscall.SysProcAttr{}
	}
	cmd.SysProcAttr.Setpgid = true
}

func (j *platformJob) assignProcess(pid int) error {
	return nil
}

func (j *platformJob) terminateAndClose(pid int) error {
	if pid > 0 {
		_ = syscall.Kill(-pid, syscall.SIGKILL)
	}
	return nil
}
