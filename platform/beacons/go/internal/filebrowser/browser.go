package filebrowser

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"sync"
	"time"
	"unicode/utf8"
)

const DefaultPreviewLimitBytes int64 = 1024 * 1024
const DefaultTransferChunkBytes int64 = 512 * 1024

var (
	ErrAccessDenied         = errors.New("access denied")
	ErrBinaryFile           = errors.New("binary file preview blocked")
	ErrDuplicateSession     = errors.New("file browser session already exists")
	ErrHashMismatch         = errors.New("file transfer hash mismatch")
	ErrInvalidPath          = errors.New("path invalid")
	ErrNotFound             = errors.New("path not found")
	ErrUnsupportedOperation = errors.New("unsupported operation")
	ErrUnknownSession       = errors.New("unknown file browser session")
)

type Manager struct {
	mu       sync.Mutex
	sessions map[string]*Session
}

type Session struct {
	root    string
	uploads map[string]*UploadTransfer
}

type Entry struct {
	Name        string `json:"name"`
	Path        string `json:"path"`
	Type        string `json:"type"`
	Size        int64  `json:"size"`
	ModifiedAt  string `json:"modified_at"`
	Permissions string `json:"permissions"`
}

type ReadResult struct {
	Content   string
	Encoding  string
	Size      int64
	Truncated bool
}

type UploadTransfer struct {
	ChunkHashes      map[int]string
	ChunkSizeBytes   int64
	Overwrite        bool
	ReceivedSequence map[int]bool
	RemotePath       string
	SHA256           string
	SizeBytes        int64
	TargetPath       string
	TempPath         string
	TotalChunks      int
	TransferID       string
}

type TransferStatus struct {
	ReceivedSequences []int
	NextSequence      int
}

type DownloadInfo struct {
	ChunkSizeBytes int64
	Path           string
	SHA256         string
	SizeBytes      int64
	TotalChunks    int
}

func NewManager() *Manager {
	return &Manager{sessions: map[string]*Session{}}
}

func (m *Manager) Open(id string, rootPath string) (string, error) {
	id = strings.TrimSpace(id)
	if id == "" {
		return "", ErrUnknownSession
	}
	root, err := normalizeRoot(rootPath)
	if err != nil {
		return "", err
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	if _, exists := m.sessions[id]; exists {
		return "", ErrDuplicateSession
	}
	m.sessions[id] = &Session{root: root, uploads: map[string]*UploadTransfer{}}
	return root, nil
}

func (m *Manager) Close(id string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if _, exists := m.sessions[id]; !exists {
		return ErrUnknownSession
	}
	delete(m.sessions, id)
	return nil
}

func (m *Manager) CloseAll() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.sessions = map[string]*Session{}
}

func (m *Manager) ListDir(id string, path string) ([]Entry, error) {
	session, err := m.session(id)
	if err != nil {
		return nil, err
	}
	target, relative, err := session.safePath(path)
	if err != nil {
		return nil, err
	}
	entries, err := os.ReadDir(target)
	if err != nil {
		return nil, mapOSError(err)
	}
	result := make([]Entry, 0, len(entries))
	for _, entry := range entries {
		info, err := entry.Info()
		if err != nil {
			continue
		}
		result = append(result, entryFromInfo(joinBrowserPath(relative, entry.Name()), entry.Name(), info))
	}
	sort.Slice(result, func(i int, j int) bool {
		if result[i].Type == "directory" && result[j].Type != "directory" {
			return true
		}
		if result[i].Type != "directory" && result[j].Type == "directory" {
			return false
		}
		return strings.ToLower(result[i].Name) < strings.ToLower(result[j].Name)
	})
	return result, nil
}

func (m *Manager) Stat(id string, path string) (Entry, error) {
	session, err := m.session(id)
	if err != nil {
		return Entry{}, err
	}
	target, relative, err := session.safePath(path)
	if err != nil {
		return Entry{}, err
	}
	info, err := os.Lstat(target)
	if err != nil {
		return Entry{}, mapOSError(err)
	}
	name := info.Name()
	if relative == "" {
		name = filepath.Base(session.root)
	}
	return entryFromInfo(relative, name, info), nil
}

func (m *Manager) ReadFile(id string, path string, limitBytes int64) (ReadResult, error) {
	if limitBytes <= 0 {
		limitBytes = DefaultPreviewLimitBytes
	}
	session, err := m.session(id)
	if err != nil {
		return ReadResult{}, err
	}
	target, _, err := session.safePath(path)
	if err != nil {
		return ReadResult{}, err
	}
	info, err := os.Stat(target)
	if err != nil {
		return ReadResult{}, mapOSError(err)
	}
	if info.IsDir() {
		return ReadResult{}, ErrInvalidPath
	}
	file, err := os.Open(target)
	if err != nil {
		return ReadResult{}, mapOSError(err)
	}
	defer file.Close()

	data, err := io.ReadAll(io.LimitReader(file, limitBytes+4))
	if err != nil {
		return ReadResult{}, mapOSError(err)
	}
	truncated := info.Size() > limitBytes || int64(len(data)) > limitBytes
	if int64(len(data)) > limitBytes {
		data = validUTF8Prefix(data[:limitBytes])
	}
	if containsNUL(data) || !utf8.Valid(data) {
		return ReadResult{}, ErrBinaryFile
	}
	return ReadResult{
		Content:   string(data),
		Encoding:  "utf-8",
		Size:      info.Size(),
		Truncated: truncated,
	}, nil
}

func (m *Manager) StartUpload(
	id string,
	transferID string,
	path string,
	sizeBytes int64,
	sha256Hex string,
	chunkSizeBytes int64,
	totalChunks int,
	overwrite bool,
) (TransferStatus, error) {
	session, err := m.session(id)
	if err != nil {
		return TransferStatus{}, err
	}
	if chunkSizeBytes <= 0 {
		chunkSizeBytes = DefaultTransferChunkBytes
	}
	if strings.TrimSpace(transferID) == "" || !isSHA256Hex(sha256Hex) || sizeBytes < 0 {
		return TransferStatus{}, ErrInvalidPath
	}
	expectedChunks := totalChunksForSize(sizeBytes, chunkSizeBytes)
	if totalChunks != expectedChunks {
		return TransferStatus{}, ErrInvalidPath
	}
	normalizedPath, err := normalizeRelativePath(path)
	if err != nil || normalizedPath == "" {
		return TransferStatus{}, ErrInvalidPath
	}
	if existing := session.uploads[transferID]; existing != nil {
		if existing.RemotePath != normalizedPath ||
			existing.SizeBytes != sizeBytes ||
			existing.SHA256 != strings.ToLower(sha256Hex) ||
			existing.ChunkSizeBytes != chunkSizeBytes ||
			existing.TotalChunks != totalChunks {
			return TransferStatus{}, ErrInvalidPath
		}
		return existing.status(), nil
	}
	target, relative, err := session.safeCreatePath(path)
	if err != nil {
		return TransferStatus{}, err
	}
	if existing, statErr := os.Lstat(target); statErr == nil {
		if existing.IsDir() || existing.Mode()&os.ModeSymlink != 0 {
			return TransferStatus{}, ErrInvalidPath
		}
		if !overwrite {
			return TransferStatus{}, ErrUnsupportedOperation
		}
	} else if !errors.Is(statErr, os.ErrNotExist) {
		return TransferStatus{}, mapOSError(statErr)
	}
	tempPath := target + ".xero-transfer-" + safeTransferID(transferID) + ".tmp"
	if err := os.WriteFile(tempPath, nil, 0o600); err != nil {
		return TransferStatus{}, mapOSError(err)
	}
	upload := &UploadTransfer{
		ChunkHashes:      map[int]string{},
		ChunkSizeBytes:   chunkSizeBytes,
		Overwrite:        overwrite,
		ReceivedSequence: map[int]bool{},
		RemotePath:       relative,
		SHA256:           strings.ToLower(sha256Hex),
		SizeBytes:        sizeBytes,
		TargetPath:       target,
		TempPath:         tempPath,
		TotalChunks:      totalChunks,
		TransferID:       transferID,
	}
	session.uploads[transferID] = upload
	return upload.status(), nil
}

func (m *Manager) WriteUploadChunk(
	id string,
	transferID string,
	sequence int,
	data []byte,
	chunkSHA256 string,
) (TransferStatus, error) {
	session, err := m.session(id)
	if err != nil {
		return TransferStatus{}, err
	}
	upload := session.uploads[transferID]
	if upload == nil {
		return TransferStatus{}, ErrNotFound
	}
	if sequence < 0 || sequence >= upload.TotalChunks {
		return TransferStatus{}, ErrInvalidPath
	}
	expectedSize := upload.ChunkSizeBytes
	if sequence == upload.TotalChunks-1 {
		expectedSize = upload.SizeBytes - int64(sequence)*upload.ChunkSizeBytes
	}
	if int64(len(data)) != expectedSize {
		return TransferStatus{}, ErrInvalidPath
	}
	chunkSHA256 = strings.ToLower(strings.TrimSpace(chunkSHA256))
	if !isSHA256Hex(chunkSHA256) || sha256Hex(data) != chunkSHA256 {
		return TransferStatus{}, ErrHashMismatch
	}
	if previous, ok := upload.ChunkHashes[sequence]; ok && previous != chunkSHA256 {
		return TransferStatus{}, ErrHashMismatch
	}
	file, err := os.OpenFile(upload.TempPath, os.O_CREATE|os.O_WRONLY, 0o600)
	if err != nil {
		return TransferStatus{}, mapOSError(err)
	}
	defer file.Close()
	if _, err := file.WriteAt(data, int64(sequence)*upload.ChunkSizeBytes); err != nil {
		return TransferStatus{}, mapOSError(err)
	}
	upload.ChunkHashes[sequence] = chunkSHA256
	upload.ReceivedSequence[sequence] = true
	return upload.status(), nil
}

func (m *Manager) CompleteUpload(id string, transferID string) (string, error) {
	session, err := m.session(id)
	if err != nil {
		return "", err
	}
	upload := session.uploads[transferID]
	if upload == nil {
		return "", ErrNotFound
	}
	if len(upload.ReceivedSequence) != upload.TotalChunks {
		return "", ErrInvalidPath
	}
	digest, err := fileSHA256(upload.TempPath)
	if err != nil {
		return "", err
	}
	if digest != upload.SHA256 {
		return "", ErrHashMismatch
	}
	if upload.Overwrite {
		if err := os.Remove(upload.TargetPath); err != nil && !errors.Is(err, os.ErrNotExist) {
			return "", mapOSError(err)
		}
	}
	if err := os.Rename(upload.TempPath, upload.TargetPath); err != nil {
		return "", mapOSError(err)
	}
	delete(session.uploads, transferID)
	return digest, nil
}

func (m *Manager) StartDownload(id string, path string, chunkSizeBytes int64) (DownloadInfo, error) {
	if chunkSizeBytes <= 0 {
		chunkSizeBytes = DefaultTransferChunkBytes
	}
	session, err := m.session(id)
	if err != nil {
		return DownloadInfo{}, err
	}
	target, relative, err := session.safePath(path)
	if err != nil {
		return DownloadInfo{}, err
	}
	info, err := os.Stat(target)
	if err != nil {
		return DownloadInfo{}, mapOSError(err)
	}
	if info.IsDir() {
		return DownloadInfo{}, ErrInvalidPath
	}
	digest, err := fileSHA256(target)
	if err != nil {
		return DownloadInfo{}, err
	}
	return DownloadInfo{
		ChunkSizeBytes: chunkSizeBytes,
		Path:           relative,
		SHA256:         digest,
		SizeBytes:      info.Size(),
		TotalChunks:    totalChunksForSize(info.Size(), chunkSizeBytes),
	}, nil
}

func (m *Manager) ReadDownloadChunk(id string, path string, sequence int, chunkSizeBytes int64) ([]byte, string, error) {
	if chunkSizeBytes <= 0 {
		chunkSizeBytes = DefaultTransferChunkBytes
	}
	session, err := m.session(id)
	if err != nil {
		return nil, "", err
	}
	target, _, err := session.safePath(path)
	if err != nil {
		return nil, "", err
	}
	info, err := os.Stat(target)
	if err != nil {
		return nil, "", mapOSError(err)
	}
	if info.IsDir() {
		return nil, "", ErrInvalidPath
	}
	totalChunks := totalChunksForSize(info.Size(), chunkSizeBytes)
	if sequence < 0 || sequence >= totalChunks {
		return nil, "", ErrInvalidPath
	}
	size := chunkSizeBytes
	if sequence == totalChunks-1 {
		size = info.Size() - int64(sequence)*chunkSizeBytes
	}
	data := make([]byte, size)
	file, err := os.Open(target)
	if err != nil {
		return nil, "", mapOSError(err)
	}
	defer file.Close()
	n, err := file.ReadAt(data, int64(sequence)*chunkSizeBytes)
	if err != nil && !errors.Is(err, io.EOF) {
		return nil, "", mapOSError(err)
	}
	data = data[:n]
	return data, sha256Hex(data), nil
}

func (m *Manager) session(id string) (*Session, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	session := m.sessions[strings.TrimSpace(id)]
	if session == nil {
		return nil, ErrUnknownSession
	}
	return session, nil
}

func normalizeRoot(rootPath string) (string, error) {
	rootPath = strings.TrimSpace(rootPath)
	if rootPath == "" {
		rootPath = defaultRoot()
	}
	absolute, err := filepath.Abs(rootPath)
	if err != nil {
		return "", ErrInvalidPath
	}
	info, err := os.Stat(absolute)
	if err != nil {
		return "", mapOSError(err)
	}
	if !info.IsDir() {
		return "", ErrInvalidPath
	}
	resolved, err := filepath.EvalSymlinks(absolute)
	if err != nil {
		return "", mapOSError(err)
	}
	return filepath.Clean(resolved), nil
}

func defaultRoot() string {
	if runtime.GOOS == "windows" {
		if drive := strings.TrimSpace(os.Getenv("SystemDrive")); drive != "" {
			return drive + `\`
		}
		return `C:\`
	}
	return "/"
}

func (s *Session) safePath(path string) (string, string, error) {
	normalized, err := normalizeRelativePath(path)
	if err != nil {
		return "", "", err
	}
	target := filepath.Join(s.root, filepath.FromSlash(normalized))
	resolved := target
	if evaluated, err := filepath.EvalSymlinks(target); err == nil {
		resolved = evaluated
	}
	if !isWithinRoot(s.root, resolved) {
		return "", "", ErrInvalidPath
	}
	return resolved, normalized, nil
}

func (s *Session) safeCreatePath(path string) (string, string, error) {
	normalized, err := normalizeRelativePath(path)
	if err != nil {
		return "", "", err
	}
	if normalized == "" {
		return "", "", ErrInvalidPath
	}
	parent := filepath.ToSlash(filepath.Dir(filepath.FromSlash(normalized)))
	if parent == "." {
		parent = ""
	}
	parentTarget, _, err := s.safePath(parent)
	if err != nil {
		return "", "", err
	}
	info, err := os.Stat(parentTarget)
	if err != nil {
		return "", "", mapOSError(err)
	}
	if !info.IsDir() {
		return "", "", ErrInvalidPath
	}
	target := filepath.Join(parentTarget, filepath.Base(filepath.FromSlash(normalized)))
	if !isWithinRoot(s.root, target) {
		return "", "", ErrInvalidPath
	}
	return target, normalized, nil
}

func normalizeRelativePath(path string) (string, error) {
	path = strings.TrimSpace(strings.ReplaceAll(path, "\\", "/"))
	if path == "" || path == "." {
		return "", nil
	}
	if strings.HasPrefix(path, "/") || strings.Contains(path, ":") {
		return "", ErrInvalidPath
	}
	cleaned := filepath.ToSlash(filepath.Clean(filepath.FromSlash(path)))
	if cleaned == "." {
		return "", nil
	}
	parts := strings.Split(cleaned, "/")
	for _, part := range parts {
		if part == ".." {
			return "", ErrInvalidPath
		}
	}
	return strings.Join(parts, "/"), nil
}

func isWithinRoot(root string, target string) bool {
	relative, err := filepath.Rel(root, target)
	if err != nil {
		return false
	}
	return relative == "." || (relative != ".." && !strings.HasPrefix(relative, ".."+string(filepath.Separator)))
}

func entryFromInfo(path string, name string, info os.FileInfo) Entry {
	entryType := "file"
	mode := info.Mode()
	switch {
	case mode&os.ModeSymlink != 0:
		entryType = "symlink"
	case info.IsDir():
		entryType = "directory"
	case !mode.IsRegular():
		entryType = "other"
	}
	return Entry{
		Name:        name,
		Path:        filepath.ToSlash(path),
		Type:        entryType,
		Size:        info.Size(),
		ModifiedAt:  info.ModTime().UTC().Format(time.RFC3339),
		Permissions: mode.String(),
	}
}

func joinBrowserPath(parent string, name string) string {
	if parent == "" {
		return name
	}
	return parent + "/" + name
}

func validUTF8Prefix(data []byte) []byte {
	for len(data) > 0 && !utf8.Valid(data) {
		data = data[:len(data)-1]
	}
	return data
}

func containsNUL(data []byte) bool {
	for _, value := range data {
		if value == 0 {
			return true
		}
	}
	return false
}

func totalChunksForSize(sizeBytes int64, chunkSizeBytes int64) int {
	if sizeBytes == 0 {
		return 0
	}
	return int((sizeBytes + chunkSizeBytes - 1) / chunkSizeBytes)
}

func (u *UploadTransfer) status() TransferStatus {
	received := make([]int, 0, len(u.ReceivedSequence))
	for sequence := range u.ReceivedSequence {
		received = append(received, sequence)
	}
	sort.Ints(received)
	next := -1
	for sequence := range u.TotalChunks {
		if !u.ReceivedSequence[sequence] {
			next = sequence
			break
		}
	}
	return TransferStatus{ReceivedSequences: received, NextSequence: next}
}

func safeTransferID(value string) string {
	value = strings.TrimSpace(value)
	replacer := strings.NewReplacer("/", "-", "\\", "-", ":", "-", "..", "-")
	return replacer.Replace(value)
}

func isSHA256Hex(value string) bool {
	value = strings.TrimSpace(value)
	if len(value) != 64 {
		return false
	}
	_, err := hex.DecodeString(value)
	return err == nil
}

func sha256Hex(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func fileSHA256(path string) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", mapOSError(err)
	}
	defer file.Close()
	hash := sha256.New()
	if _, err := io.Copy(hash, file); err != nil {
		return "", mapOSError(err)
	}
	return hex.EncodeToString(hash.Sum(nil)), nil
}

func mapOSError(err error) error {
	if errors.Is(err, os.ErrPermission) {
		return ErrAccessDenied
	}
	if errors.Is(err, os.ErrNotExist) {
		return ErrNotFound
	}
	return err
}

func ErrorCode(err error) string {
	switch {
	case errors.Is(err, ErrAccessDenied):
		return "access_denied"
	case errors.Is(err, ErrBinaryFile):
		return "binary_file"
	case errors.Is(err, ErrHashMismatch):
		return "hash_mismatch"
	case errors.Is(err, ErrInvalidPath):
		return "path_invalid"
	case errors.Is(err, ErrNotFound), errors.Is(err, ErrUnknownSession):
		return "not_found"
	default:
		return "unsupported_operation"
	}
}
