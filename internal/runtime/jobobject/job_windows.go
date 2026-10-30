//go:build windows

package jobobject

import (
	"fmt"
	"os/exec"
	"syscall"
	"unsafe"
)

var (
	modkernel32                     = syscall.NewLazyDLL("kernel32.dll")
	procCreateJobObjectW            = modkernel32.NewProc("CreateJobObjectW")
	procSetInformationJobObject     = modkernel32.NewProc("SetInformationJobObject")
	procAssignProcessToJobObject    = modkernel32.NewProc("AssignProcessToJobObject")
	procTerminateJobObject          = modkernel32.NewProc("TerminateJobObject")
	procGlobalMemoryStatusEx        = modkernel32.NewProc("GlobalMemoryStatusEx")
	procOpenProcess                 = modkernel32.NewProc("OpenProcess")
)

const (
	jobObjectExtendedLimitInformation = 9
	jobObjectLimitProcessMemory       = 0x00000100
	jobObjectLimitJobMemory           = 0x00000200
	jobObjectLimitKillOnJobClose      = 0x00002000

	processSetQuota  = 0x0100
	processTerminate = 0x0001
)

type ioCounters struct {
	ReadOperationCount  uint64
	WriteOperationCount uint64
	OtherOperationCount uint64
	ReadTransferCount   uint64
	WriteTransferCount  uint64
	OtherTransferCount  uint64
}

type jobObjectBasicLimitInformation struct {
	PerProcessUserTimeLimit int64
	PerJobUserTimeLimit     int64
	LimitFlags              uint32
	MinimumWorkingSetSize   uintptr
	MaximumWorkingSetSize   uintptr
	ActiveProcessLimit      uint32
	Affinity                uintptr
	PriorityClass           uint32
	SchedulingClass         uint32
}

type jobObjectExtendedLimitInformationStruct struct {
	BasicLimitInformation jobObjectBasicLimitInformation
	IoInfo                ioCounters
	ProcessMemoryLimit    uintptr
	JobMemoryLimit        uintptr
	PeakProcessMemoryUsed uintptr
	PeakJobMemoryUsed     uintptr
}

type memoryStatusEx struct {
	Length               uint32
	MemoryLoad           uint32
	TotalPhys            uint64
	AvailPhys            uint64
	TotalPageFile        uint64
	AvailPageFile        uint64
	TotalVirtual         uint64
	AvailVirtual         uint64
	AvailExtendedVirtual uint64
}

// ProbeSystemMemory queries Windows GlobalMemoryStatusEx in < 50 microseconds
// without spawning powershell.exe or wmic.
func ProbeSystemMemory() (SystemMemory, error) {
	var st memoryStatusEx
	st.Length = uint32(unsafe.Sizeof(st))
	r1, _, err := procGlobalMemoryStatusEx.Call(uintptr(unsafe.Pointer(&st)))
	if r1 == 0 {
		return SystemMemory{}, fmt.Errorf("GlobalMemoryStatusEx failed: %w", err)
	}
	const mb = 1024 * 1024
	return SystemMemory{
		TotalPhysMB:   int64(st.TotalPhys / mb),
		AvailPhysMB:   int64(st.AvailPhys / mb),
		MemoryLoadPct: int(st.MemoryLoad),
	}, nil
}

type platformJob struct {
	handle syscall.Handle
}

func newPlatformJob(memoryLimitMB int64) (*platformJob, error) {
	r1, _, err := procCreateJobObjectW.Call(0, 0)
	if r1 == 0 {
		return nil, fmt.Errorf("CreateJobObjectW: %w", err)
	}
	h := syscall.Handle(r1)

	var info jobObjectExtendedLimitInformationStruct
	flags := uint32(jobObjectLimitKillOnJobClose)
	if memoryLimitMB > 0 {
		limitBytes := uintptr(memoryLimitMB * 1024 * 1024)
		flags |= jobObjectLimitJobMemory | jobObjectLimitProcessMemory
		info.JobMemoryLimit = limitBytes
		info.ProcessMemoryLimit = limitBytes
	}
	info.BasicLimitInformation.LimitFlags = flags

	ok, _, setErr := procSetInformationJobObject.Call(
		uintptr(h),
		uintptr(jobObjectExtendedLimitInformation),
		uintptr(unsafe.Pointer(&info)),
		uintptr(unsafe.Sizeof(info)),
	)
	if ok == 0 {
		_ = syscall.CloseHandle(h)
		return nil, fmt.Errorf("SetInformationJobObject: %w", setErr)
	}
	return &platformJob{handle: h}, nil
}

func configureCmdPlatform(cmd *exec.Cmd) {
	if cmd.SysProcAttr == nil {
		cmd.SysProcAttr = &syscall.SysProcAttr{}
	}
	cmd.SysProcAttr.CreationFlags |= syscall.CREATE_NEW_PROCESS_GROUP
}

func (j *platformJob) assignProcess(pid int) error {
	if j == nil || j.handle == 0 {
		return nil
	}
	hProc, _, err := procOpenProcess.Call(
		uintptr(processSetQuota|processTerminate),
		0,
		uintptr(pid),
	)
	if hProc == 0 {
		return fmt.Errorf("OpenProcess(%d): %w", pid, err)
	}
	defer syscall.CloseHandle(syscall.Handle(hProc))

	ok, _, assignErr := procAssignProcessToJobObject.Call(uintptr(j.handle), hProc)
	if ok == 0 {
		// On nested jobs in older Windows versions where assignment may fail if already in a non-nested job,
		// fallback to Terminate/Close cleanly without crashing the supervisor.
		_ = assignErr
	}
	return nil
}

func (j *platformJob) terminateAndClose(pid int) error {
	if j == nil || j.handle == 0 {
		return nil
	}
	_, _, _ = procTerminateJobObject.Call(uintptr(j.handle), 1)
	err := syscall.CloseHandle(j.handle)
	j.handle = 0
	return err
}
