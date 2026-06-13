package filebrowser

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestListDirAndStatReturnMetadata(t *testing.T) {
	root := t.TempDir()
	if err := os.Mkdir(filepath.Join(root, "docs"), 0o755); err != nil {
		t.Fatalf("mkdir docs: %v", err)
	}
	if err := os.WriteFile(filepath.Join(root, "docs", "notes.txt"), []byte("hello"), 0o644); err != nil {
		t.Fatalf("write notes: %v", err)
	}
	manager := NewManager()
	if _, err := manager.Open("session-one", root); err != nil {
		t.Fatalf("open file browser: %v", err)
	}

	entries, err := manager.ListDir("session-one", "docs")
	if err != nil {
		t.Fatalf("list docs: %v", err)
	}
	stat, err := manager.Stat("session-one", "docs/notes.txt")
	if err != nil {
		t.Fatalf("stat notes: %v", err)
	}

	if len(entries) != 1 {
		t.Fatalf("expected one entry, got %#v", entries)
	}
	if entries[0].Name != "notes.txt" || entries[0].Path != "docs/notes.txt" || entries[0].Type != "file" {
		t.Fatalf("unexpected entry metadata: %#v", entries[0])
	}
	if stat.Size != 5 || stat.ModifiedAt == "" || stat.Permissions == "" {
		t.Fatalf("missing stat metadata: %#v", stat)
	}
}

func TestPathTraversalRejected(t *testing.T) {
	root := t.TempDir()
	manager := NewManager()
	if _, err := manager.Open("session-one", root); err != nil {
		t.Fatalf("open file browser: %v", err)
	}

	_, err := manager.ListDir("session-one", "../")

	if !errors.Is(err, ErrInvalidPath) {
		t.Fatalf("expected ErrInvalidPath, got %v", err)
	}
}

func TestReadFileTruncatesAtLimit(t *testing.T) {
	root := t.TempDir()
	content := strings.Repeat("a", 12)
	if err := os.WriteFile(filepath.Join(root, "large.txt"), []byte(content), 0o644); err != nil {
		t.Fatalf("write large file: %v", err)
	}
	manager := NewManager()
	if _, err := manager.Open("session-one", root); err != nil {
		t.Fatalf("open file browser: %v", err)
	}

	result, err := manager.ReadFile("session-one", "large.txt", 8)
	if err != nil {
		t.Fatalf("read large file: %v", err)
	}

	if result.Content != "aaaaaaaa" || !result.Truncated || result.Size != int64(len(content)) {
		t.Fatalf("unexpected read result: %#v", result)
	}
}

func TestBinaryFilePreviewBlocked(t *testing.T) {
	root := t.TempDir()
	if err := os.WriteFile(filepath.Join(root, "binary.bin"), []byte{0x01, 0x00, 0x02}, 0o644); err != nil {
		t.Fatalf("write binary file: %v", err)
	}
	manager := NewManager()
	if _, err := manager.Open("session-one", root); err != nil {
		t.Fatalf("open file browser: %v", err)
	}

	_, err := manager.ReadFile("session-one", "binary.bin", DefaultPreviewLimitBytes)

	if !errors.Is(err, ErrBinaryFile) {
		t.Fatalf("expected ErrBinaryFile, got %v", err)
	}
}
