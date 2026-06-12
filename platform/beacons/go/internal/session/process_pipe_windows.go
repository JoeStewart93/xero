//go:build windows

package session

import (
	"context"
	"os"
	"os/exec"
)

func startShellProcess(ctx context.Context, args []string, shellType string, rows int, cols int) (*terminalProcess, error) {
	cmd := exec.CommandContext(ctx, args[0], args[1:]...)
	cmd.Env = append(os.Environ(), "TERM=xterm-256color", "XERO_SESSION_SHELL="+shellType)
	stdin, err := cmd.StdinPipe()
	if err != nil {
		return nil, err
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}
	stderr, err := cmd.StderrPipe()
	if err != nil {
		return nil, err
	}
	if err := cmd.Start(); err != nil {
		return nil, err
	}
	return &terminalProcess{
		cmd:    cmd,
		stdin:  stdin,
		stdout: stdout,
		stderr: stderr,
	}, nil
}
