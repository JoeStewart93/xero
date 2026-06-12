package shell

import (
	"runtime"
	"strings"
	"testing"
)

func TestShellSuccess(t *testing.T) {
	result := Run("printf hello", "bash", 5, 4096)
	if runtime.GOOS == "windows" {
		t.Skip("bash success test runs in Linux CI/Docker")
	}
	if result.Status != "completed" || strings.TrimSpace(result.Stdout) != "hello" {
		t.Fatalf("unexpected result: %#v", result)
	}
}

func TestShellTimeout(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("bash timeout test runs in Linux CI/Docker")
	}
	result := Run("sleep 2", "bash", 1, 4096)
	if result.Status != "failed" || !result.TimedOut {
		t.Fatalf("expected timeout failure, got %#v", result)
	}
}

func TestShellOutputTruncation(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("bash truncation test runs in Linux CI/Docker")
	}
	result := Run("yes x | head -c 3000", "bash", 5, 1024)
	if !result.Truncated || len(result.Stdout) != 1024 {
		t.Fatalf("expected truncated stdout, got len=%d result=%#v", len(result.Stdout), result)
	}
}

func TestUnsupportedShellFails(t *testing.T) {
	result := Run("whoami", "fish", 5, 4096)
	if result.Status != "failed" || !strings.Contains(result.Stderr, "unsupported shell") {
		t.Fatalf("expected unsupported shell failure, got %#v", result)
	}
}
