//go:build !windows

package session

import (
	"context"
	"os"
	"os/exec"

	"github.com/creack/pty"
)

func startShellProcess(ctx context.Context, args []string, shellType string, rows int, cols int) (*terminalProcess, error) {
	cmd := exec.CommandContext(ctx, args[0], args[1:]...)
	cmd.Env = append(os.Environ(), "TERM=xterm-256color", "XERO_SESSION_SHELL="+shellType)
	tty, err := pty.StartWithSize(cmd, &pty.Winsize{Rows: uint16(rows), Cols: uint16(cols)})
	if err != nil {
		return nil, err
	}
	return &terminalProcess{
		cmd:    cmd,
		stdin:  tty,
		stdout: tty,
		cleanup: func() {
			_ = tty.Close()
		},
		resize: func(rows int, cols int) error {
			return pty.Setsize(tty, &pty.Winsize{Rows: uint16(rows), Cols: uint16(cols)})
		},
	}, nil
}
