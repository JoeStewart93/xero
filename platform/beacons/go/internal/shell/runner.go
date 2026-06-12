package shell

import (
	"bytes"
	"context"
	"errors"
	"os/exec"
	"runtime"
	"time"
)

type Result struct {
	Status    string
	Stdout    string
	Stderr    string
	ExitCode  int
	TimedOut  bool
	Truncated bool
}

type limitedBuffer struct {
	buffer     bytes.Buffer
	limit      int
	truncated  bool
	totalBytes int
}

func (w *limitedBuffer) Write(p []byte) (int, error) {
	w.totalBytes += len(p)
	remaining := w.limit - w.buffer.Len()
	if remaining > 0 {
		if len(p) > remaining {
			w.buffer.Write(p[:remaining])
			w.truncated = true
			return len(p), nil
		}
		w.buffer.Write(p)
	}
	if w.buffer.Len() >= w.limit && w.totalBytes > w.limit {
		w.truncated = true
	}
	return len(p), nil
}

func (w *limitedBuffer) String() string {
	return w.buffer.String()
}

func Run(command string, shellType string, timeoutSeconds int, outputLimitBytes int) Result {
	if timeoutSeconds < 1 {
		timeoutSeconds = 60
	}
	if outputLimitBytes < 1024 {
		outputLimitBytes = 1024
	}
	args, err := commandArgs(command, shellType)
	if err != nil {
		return Result{Status: "failed", Stderr: err.Error(), ExitCode: -1}
	}
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeoutSeconds)*time.Second)
	defer cancel()

	cmd := exec.CommandContext(ctx, args[0], args[1:]...)
	stdout := &limitedBuffer{limit: outputLimitBytes}
	stderr := &limitedBuffer{limit: outputLimitBytes}
	cmd.Stdout = stdout
	cmd.Stderr = stderr
	err = cmd.Run()

	result := Result{
		Status:    "completed",
		Stdout:    stdout.String(),
		Stderr:    stderr.String(),
		ExitCode:  0,
		TimedOut:  errors.Is(ctx.Err(), context.DeadlineExceeded),
		Truncated: stdout.truncated || stderr.truncated,
	}
	if cmd.ProcessState != nil {
		result.ExitCode = cmd.ProcessState.ExitCode()
	}
	if err != nil || result.TimedOut || result.ExitCode != 0 {
		result.Status = "failed"
		if result.TimedOut && result.Stderr == "" {
			result.Stderr = "command timed out"
		}
	}
	return result
}

func commandArgs(command string, shellType string) ([]string, error) {
	if shellType == "" || shellType == "auto" {
		if runtime.GOOS == "windows" {
			shellType = "powershell"
		} else {
			shellType = "bash"
		}
	}
	switch shellType {
	case "bash":
		return []string{"bash", "-lc", command}, nil
	case "cmd":
		return []string{"cmd", "/C", command}, nil
	case "powershell":
		return []string{"powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command}, nil
	default:
		return nil, errors.New("unsupported shell type")
	}
}
