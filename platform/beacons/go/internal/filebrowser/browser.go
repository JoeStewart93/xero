package filebrowser

import (
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

var (
	ErrAccessDenied         = errors.New("access denied")
	ErrBinaryFile           = errors.New("binary file preview blocked")
	ErrDuplicateSession     = errors.New("file browser session already exists")
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
	root string
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
	m.sessions[id] = &Session{root: root}
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
	case errors.Is(err, ErrInvalidPath):
		return "path_invalid"
	case errors.Is(err, ErrNotFound), errors.Is(err, ErrUnknownSession):
		return "not_found"
	default:
		return "unsupported_operation"
	}
}
