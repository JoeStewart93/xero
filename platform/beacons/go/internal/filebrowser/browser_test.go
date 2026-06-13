package filebrowser

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io"
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

func TestUploadChunksCompleteWithMatchingHash(t *testing.T) {
	root := t.TempDir()
	manager := NewManager()
	if _, err := manager.Open("session-one", root); err != nil {
		t.Fatalf("open file browser: %v", err)
	}
	content := []byte("hello world!")
	first := content[:8]
	second := content[8:]
	fileHash := testSHA256(content)

	if _, err := manager.StartUpload("session-one", "transfer-one", "uploads/payload.bin", int64(len(content)), fileHash, 8, 2, false); !errors.Is(err, ErrNotFound) {
		t.Fatalf("expected missing parent to be rejected as not found, got %v", err)
	}
	if err := os.Mkdir(filepath.Join(root, "uploads"), 0o755); err != nil {
		t.Fatalf("mkdir uploads: %v", err)
	}
	status, err := manager.StartUpload("session-one", "transfer-one", "uploads/payload.bin", int64(len(content)), fileHash, 8, 2, false)
	if err != nil {
		t.Fatalf("start upload: %v", err)
	}
	if status.NextSequence != 0 {
		t.Fatalf("unexpected initial status: %#v", status)
	}
	if _, err := manager.WriteUploadChunk("session-one", "transfer-one", 0, first, testSHA256(first)); err != nil {
		t.Fatalf("write first chunk: %v", err)
	}
	status, err = manager.StartUpload("session-one", "transfer-one", "uploads/payload.bin", int64(len(content)), fileHash, 8, 2, false)
	if err != nil {
		t.Fatalf("resume upload: %v", err)
	}
	if status.NextSequence != 1 || len(status.ReceivedSequences) != 1 || status.ReceivedSequences[0] != 0 {
		t.Fatalf("unexpected resume status: %#v", status)
	}
	if _, err := manager.WriteUploadChunk("session-one", "transfer-one", 1, second, testSHA256(second)); err != nil {
		t.Fatalf("write second chunk: %v", err)
	}
	digest, err := manager.CompleteUpload("session-one", "transfer-one")
	if err != nil {
		t.Fatalf("complete upload: %v", err)
	}
	stored, err := os.ReadFile(filepath.Join(root, "uploads", "payload.bin"))
	if err != nil {
		t.Fatalf("read uploaded file: %v", err)
	}
	if digest != fileHash || string(stored) != string(content) {
		t.Fatalf("unexpected uploaded content digest=%s content=%q", digest, string(stored))
	}
}

func TestUploadCompletes100MBFileWithMatchingHash(t *testing.T) {
	root := t.TempDir()
	manager := NewManager()
	if _, err := manager.Open("session-one", root); err != nil {
		t.Fatalf("open file browser: %v", err)
	}
	const sizeBytes int64 = 100 * 1024 * 1024
	chunkSize := DefaultTransferChunkBytes
	totalChunks := int(sizeBytes / chunkSize)
	fileHasher := sha256.New()
	chunks := make([][]byte, 0, totalChunks)
	for sequence := 0; sequence < totalChunks; sequence++ {
		chunk := deterministicChunk(sequence, int(chunkSize))
		if _, err := fileHasher.Write(chunk); err != nil {
			t.Fatalf("hash chunk: %v", err)
		}
		chunks = append(chunks, chunk)
	}
	fileHash := hex.EncodeToString(fileHasher.Sum(nil))

	status, err := manager.StartUpload(
		"session-one",
		"transfer-100mb",
		"payload-100mb.bin",
		sizeBytes,
		fileHash,
		chunkSize,
		totalChunks,
		false,
	)
	if err != nil {
		t.Fatalf("start upload: %v", err)
	}
	if status.NextSequence != 0 || len(status.ReceivedSequences) != 0 {
		t.Fatalf("unexpected initial status: %#v", status)
	}
	for sequence, chunk := range chunks {
		if _, err := manager.WriteUploadChunk("session-one", "transfer-100mb", sequence, chunk, testSHA256(chunk)); err != nil {
			t.Fatalf("write chunk %d: %v", sequence, err)
		}
	}
	digest, err := manager.CompleteUpload("session-one", "transfer-100mb")
	if err != nil {
		t.Fatalf("complete upload: %v", err)
	}
	file, err := os.Open(filepath.Join(root, "payload-100mb.bin"))
	if err != nil {
		t.Fatalf("open uploaded file: %v", err)
	}
	defer file.Close()
	storedHasher := sha256.New()
	if _, err := io.Copy(storedHasher, file); err != nil {
		t.Fatalf("hash uploaded file: %v", err)
	}
	storedHash := hex.EncodeToString(storedHasher.Sum(nil))
	if digest != fileHash || storedHash != fileHash {
		t.Fatalf("unexpected uploaded hash digest=%s stored=%s expected=%s", digest, storedHash, fileHash)
	}
}

func TestUploadRejectsChunkHashMismatch(t *testing.T) {
	root := t.TempDir()
	manager := NewManager()
	if _, err := manager.Open("session-one", root); err != nil {
		t.Fatalf("open file browser: %v", err)
	}
	content := []byte("hello")
	if _, err := manager.StartUpload("session-one", "transfer-one", "payload.bin", int64(len(content)), testSHA256(content), 5, 1, false); err != nil {
		t.Fatalf("start upload: %v", err)
	}

	_, err := manager.WriteUploadChunk("session-one", "transfer-one", 0, content, strings.Repeat("0", 64))

	if !errors.Is(err, ErrHashMismatch) {
		t.Fatalf("expected ErrHashMismatch, got %v", err)
	}
}

func TestDownloadChunkReturnsBinaryDataAndHash(t *testing.T) {
	root := t.TempDir()
	content := []byte{0x00, 0x01, 0x02, 0x03, 0x04}
	if err := os.WriteFile(filepath.Join(root, "binary.bin"), content, 0o644); err != nil {
		t.Fatalf("write binary: %v", err)
	}
	manager := NewManager()
	if _, err := manager.Open("session-one", root); err != nil {
		t.Fatalf("open file browser: %v", err)
	}

	info, err := manager.StartDownload("session-one", "binary.bin", 3)
	if err != nil {
		t.Fatalf("start download: %v", err)
	}
	chunk, digest, err := manager.ReadDownloadChunk("session-one", "binary.bin", 1, 3)
	if err != nil {
		t.Fatalf("read download chunk: %v", err)
	}

	if info.SizeBytes != 5 || info.TotalChunks != 2 || info.SHA256 != testSHA256(content) {
		t.Fatalf("unexpected download info: %#v", info)
	}
	if string(chunk) != string(content[3:]) || digest != testSHA256(content[3:]) {
		t.Fatalf("unexpected chunk digest=%s content=%#v", digest, chunk)
	}
}

func testSHA256(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func deterministicChunk(sequence int, size int) []byte {
	chunk := make([]byte, size)
	for i := range chunk {
		chunk[i] = byte((sequence + i) % 251)
	}
	return chunk
}
