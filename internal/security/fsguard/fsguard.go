// Package fsguard provides strict user-space path confinement for Go 1.24.3,
// mitigating stdlib os.Root traversal surfaces (GO-2026-4970 / GO-2026-4602)
// and enforcing AGENTS.md §5 workspace confinement rules.
package fsguard

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

var (
	ErrPathTraversal     = errors.New("fsguard: path escapes workspace root")
	ErrForbiddenStream   = errors.New("fsguard: NTFS alternate data stream or invalid colon forbidden")
	ErrReservedDevice    = errors.New("fsguard: reserved Windows device name forbidden")
	ErrSymlinkEscape     = errors.New("fsguard: symlink target escapes workspace root")
	ErrProtectedConfig   = errors.New("fsguard: critical configuration requires backup before write")
)

var reservedWindowsNames = map[string]struct{}{
	"CON": {}, "PRN": {}, "AUX": {}, "NUL": {},
	"COM1": {}, "COM2": {}, "COM3": {}, "COM4": {}, "COM5": {}, "COM6": {}, "COM7": {}, "COM8": {}, "COM9": {},
	"LPT1": {}, "LPT2": {}, "LPT3": {}, "LPT4": {}, "LPT5": {}, "LPT6": {}, "LPT7": {}, "LPT8": {}, "LPT9": {},
}

// SafeJoin resolves relPath inside rootDir and verifies that the canonical result
// (including any existing symlinks along the path) remains strictly inside rootDir.
func SafeJoin(rootDir, relPath string) (string, error) {
	if strings.TrimSpace(rootDir) == "" {
		return "", errors.New("fsguard: empty rootDir")
	}
	if strings.ContainsRune(relPath, 0) {
		return "", fmt.Errorf("%w: null byte in path", ErrPathTraversal)
	}
	// Reject UNC paths or volume prefixes in relative paths
	if strings.HasPrefix(relPath, `\\`) || strings.HasPrefix(relPath, "//") || filepath.VolumeName(relPath) != "" {
		return "", fmt.Errorf("%w: volume or UNC in relative path %q", ErrPathTraversal, relPath)
	}
	// Reject NTFS Alternate Data Streams (any ':' in relative path)
	if strings.Contains(relPath, ":") {
		return "", fmt.Errorf("%w: %q", ErrForbiddenStream, relPath)
	}

	absRoot, err := filepath.Abs(rootDir)
	if err != nil {
		return "", fmt.Errorf("fsguard: resolve root: %w", err)
	}
	evalRoot, err := filepath.EvalSymlinks(absRoot)
	if err == nil {
		absRoot = evalRoot
	}

	cleanedRel := filepath.Clean(relPath)
	if cleanedRel == ".." || strings.HasPrefix(cleanedRel, ".."+string(filepath.Separator)) {
		return "", fmt.Errorf("%w: %q", ErrPathTraversal, relPath)
	}

	for _, seg := range strings.Split(filepath.ToSlash(cleanedRel), "/") {
		if seg == ".." {
			return "", fmt.Errorf("%w: segment '..' in %q", ErrPathTraversal, relPath)
		}
		base := strings.ToUpper(strings.Split(seg, ".")[0])
		if _, reserved := reservedWindowsNames[base]; reserved {
			return "", fmt.Errorf("%w: %q", ErrReservedDevice, seg)
		}
	}

	joined := filepath.Join(absRoot, cleanedRel)
	if !isWithinRoot(absRoot, joined) {
		return "", fmt.Errorf("%w: %q outside %q", ErrPathTraversal, joined, absRoot)
	}

	// Verify existing ancestor symlinks do not escape absRoot
	if err := verifyAncestorsWithinRoot(absRoot, joined); err != nil {
		return "", err
	}

	return joined, nil
}

func isWithinRoot(absRoot, candidate string) bool {
	rel, err := filepath.Rel(absRoot, candidate)
	if err != nil {
		return false
	}
	if rel == "." {
		return true
	}
	if rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return false
	}
	return !filepath.IsAbs(rel)
}

func verifyAncestorsWithinRoot(absRoot, target string) error {
	curr := target
	for {
		info, err := os.Lstat(curr)
		if err == nil {
			if info.Mode()&os.ModeSymlink != 0 {
				resolved, evalErr := filepath.EvalSymlinks(curr)
				if evalErr != nil {
					return fmt.Errorf("%w: unresolvable symlink %q: %v", ErrSymlinkEscape, curr, evalErr)
				}
				if !isWithinRoot(absRoot, resolved) {
					return fmt.Errorf("%w: %q -> %q", ErrSymlinkEscape, curr, resolved)
				}
			}
		}
		if curr == absRoot {
			break
		}
		parent := filepath.Dir(curr)
		if parent == curr {
			break
		}
		curr = parent
	}
	return nil
}
