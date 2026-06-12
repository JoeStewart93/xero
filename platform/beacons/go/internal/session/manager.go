package session

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os/exec"
	"runtime"
	"strings"
	"sync"
)

const streamChunkBytes = 16 * 1024

var (
	ErrDuplicateSession = errors.New("session already exists")
	ErrUnknownSession   = errors.New("unknown session")
)

type Event struct {
	Op       string
	Data     []byte
	Reason   string
	ExitCode int
}

type Options struct {
	ShellType string
	Rows      int
	Cols      int
}

type EmitFunc func(Event)

type Manager struct {
	mu       sync.Mutex
	sessions map[string]*ShellSession
}

type ShellSession struct {
	id      string
	cmd     *exec.Cmd
	stdin   io.WriteCloser
	cancel  context.CancelFunc
	emit    EmitFunc
	done    chan struct{}
	cleanup func()
	resize  func(rows int, cols int) error

	mu     sync.Mutex
	rows   int
	cols   int
	closed bool
}

type terminalProcess struct {
	cmd     *exec.Cmd
	stdin   io.WriteCloser
	stdout  io.Reader
	stderr  io.Reader
	cleanup func()
	resize  func(rows int, cols int) error
}

func NewManager() *Manager {
	return &Manager{sessions: map[string]*ShellSession{}}
}

func (m *Manager) Open(ctx context.Context, id string, options Options, emit EmitFunc) error {
	id = strings.TrimSpace(id)
	if id == "" {
		return errors.New("session id is required")
	}
	args, shellType, err := commandArgs(options.ShellType)
	if err != nil {
		return err
	}

	m.mu.Lock()
	if _, exists := m.sessions[id]; exists {
		m.mu.Unlock()
		return ErrDuplicateSession
	}
	m.mu.Unlock()

	rows := clampInt(options.Rows, 24, 5, 80)
	cols := clampInt(options.Cols, 80, 20, 300)
	sessionCtx, cancel := context.WithCancel(ctx)
	process, err := startShellProcess(sessionCtx, args, shellType, rows, cols)
	if err != nil {
		cancel()
		return err
	}

	shellSession := &ShellSession{
		id:      id,
		cmd:     process.cmd,
		stdin:   process.stdin,
		cancel:  cancel,
		emit:    emit,
		done:    make(chan struct{}),
		cleanup: process.cleanup,
		resize:  process.resize,
		rows:    rows,
		cols:    cols,
	}

	m.mu.Lock()
	if _, exists := m.sessions[id]; exists {
		m.mu.Unlock()
		shellSession.close("duplicate_session")
		return ErrDuplicateSession
	}
	m.sessions[id] = shellSession
	m.mu.Unlock()

	go shellSession.copyStream("stdout", process.stdout)
	if process.stderr != nil {
		go shellSession.copyStream("stderr", process.stderr)
	}
	go shellSession.wait(m)
	return nil
}

func (m *Manager) Write(id string, data []byte) error {
	shellSession := m.get(id)
	if shellSession == nil {
		return ErrUnknownSession
	}
	shellSession.mu.Lock()
	defer shellSession.mu.Unlock()
	if shellSession.closed {
		return ErrUnknownSession
	}
	_, err := shellSession.stdin.Write(data)
	return err
}

func (m *Manager) Resize(id string, rows int, cols int) error {
	shellSession := m.get(id)
	if shellSession == nil {
		return ErrUnknownSession
	}
	shellSession.mu.Lock()
	shellSession.rows = clampInt(rows, shellSession.rows, 5, 80)
	shellSession.cols = clampInt(cols, shellSession.cols, 20, 300)
	rows = shellSession.rows
	cols = shellSession.cols
	resize := shellSession.resize
	shellSession.mu.Unlock()
	if resize == nil {
		return nil
	}
	return resize(rows, cols)
}

func (m *Manager) Close(id string, reason string) error {
	shellSession := m.get(id)
	if shellSession == nil {
		return ErrUnknownSession
	}
	shellSession.close(reason)
	return nil
}

func (m *Manager) CloseAll(reason string) {
	m.mu.Lock()
	sessions := make([]*ShellSession, 0, len(m.sessions))
	for _, shellSession := range m.sessions {
		sessions = append(sessions, shellSession)
	}
	m.mu.Unlock()
	for _, shellSession := range sessions {
		shellSession.close(reason)
	}
}

func (m *Manager) get(id string) *ShellSession {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.sessions[id]
}

func (m *Manager) remove(id string, shellSession *ShellSession) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if current := m.sessions[id]; current == shellSession {
		delete(m.sessions, id)
	}
}

func (s *ShellSession) copyStream(op string, reader io.Reader) {
	buffer := make([]byte, streamChunkBytes)
	for {
		n, err := reader.Read(buffer)
		if n > 0 && s.emit != nil {
			chunk := make([]byte, n)
			copy(chunk, buffer[:n])
			s.emit(Event{Op: op, Data: chunk})
		}
		if err != nil {
			return
		}
	}
}

func (s *ShellSession) wait(manager *Manager) {
	err := s.cmd.Wait()
	s.mu.Lock()
	closedByRequest := s.closed
	s.closed = true
	s.mu.Unlock()

	exitCode := 0
	if s.cmd.ProcessState != nil {
		exitCode = s.cmd.ProcessState.ExitCode()
	}
	reason := "process_exit"
	if err != nil {
		reason = err.Error()
	}
	if closedByRequest {
		reason = "closed"
	}
	if s.emit != nil {
		s.emit(Event{Op: "exit", Reason: reason, ExitCode: exitCode})
	}
	manager.remove(s.id, s)
	close(s.done)
}

func (s *ShellSession) close(reason string) {
	s.mu.Lock()
	if s.closed {
		s.mu.Unlock()
		return
	}
	s.closed = true
	s.mu.Unlock()
	_ = s.stdin.Close()
	if s.cleanup != nil {
		s.cleanup()
	}
	s.cancel()
	if s.cmd.Process != nil {
		_ = s.cmd.Process.Kill()
	}
}

func commandArgs(shellType string) ([]string, string, error) {
	shellType = strings.ToLower(strings.TrimSpace(shellType))
	if shellType == "" || shellType == "auto" {
		if runtime.GOOS == "windows" {
			shellType = "powershell"
		} else {
			shellType = "bash"
		}
	}
	switch shellType {
	case "bash":
		return []string{"bash", "-i"}, shellType, nil
	case "cmd":
		return []string{"cmd"}, shellType, nil
	case "powershell":
		return []string{"powershell", "-NoProfile", "-ExecutionPolicy", "Bypass"}, shellType, nil
	default:
		return nil, "", fmt.Errorf("unsupported shell type %q", shellType)
	}
}

func clampInt(value int, fallback int, minimum int, maximum int) int {
	if value < minimum || value > maximum {
		return fallback
	}
	return value
}
