package session

import (
	"bytes"
	"context"
	"os/exec"
	"runtime"
	"strings"
	"testing"
	"time"
)

func TestManagerStreamsInteractiveShellOutput(t *testing.T) {
	shellType, input := interactiveShellTestCommand(t)
	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	defer cancel()

	manager := NewManager()
	events := make(chan Event, 32)
	if err := manager.Open(ctx, "session-test", Options{ShellType: shellType, Rows: 24, Cols: 80}, func(event Event) {
		events <- event
	}); err != nil {
		t.Fatal(err)
	}
	defer manager.Close("session-test", "test_cleanup")

	if err := manager.Write("session-test", []byte(input)); err != nil {
		t.Fatal(err)
	}

	var output bytes.Buffer
	exitSeen := false
	for !strings.Contains(output.String(), "xero-session-test") || !exitSeen {
		select {
		case <-ctx.Done():
			t.Fatalf("timed out waiting for session output; output=%q exitSeen=%v", output.String(), exitSeen)
		case event := <-events:
			switch event.Op {
			case "stdout", "stderr":
				output.Write(event.Data)
			case "exit":
				exitSeen = true
			}
		}
	}
}

func TestManagerRejectsDuplicateSession(t *testing.T) {
	shellType, _ := interactiveShellTestCommand(t)
	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	defer cancel()

	manager := NewManager()
	if err := manager.Open(ctx, "duplicate-session", Options{ShellType: shellType}, func(Event) {}); err != nil {
		t.Fatal(err)
	}
	defer manager.Close("duplicate-session", "test_cleanup")

	if err := manager.Open(ctx, "duplicate-session", Options{ShellType: shellType}, func(Event) {}); err != ErrDuplicateSession {
		t.Fatalf("expected duplicate session error, got %v", err)
	}
}

func TestManagerResizesInteractiveShell(t *testing.T) {
	shellType, _ := interactiveShellTestCommand(t)
	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	defer cancel()

	manager := NewManager()
	if err := manager.Open(ctx, "resize-session", Options{ShellType: shellType, Rows: 24, Cols: 80}, func(Event) {}); err != nil {
		t.Fatal(err)
	}
	defer manager.Close("resize-session", "test_cleanup")

	if err := manager.Resize("resize-session", 30, 100); err != nil {
		t.Fatal(err)
	}
}

func interactiveShellTestCommand(t *testing.T) (string, string) {
	t.Helper()
	if runtime.GOOS == "windows" {
		if _, err := exec.LookPath("cmd"); err != nil {
			t.Skip("cmd shell is unavailable")
		}
		return "cmd", "echo xero-session-test\r\nexit\r\n"
	}
	if _, err := exec.LookPath("bash"); err != nil {
		t.Skip("bash shell is unavailable")
	}
	return "bash", "printf 'xero-session-test\\n'\nexit\n"
}
