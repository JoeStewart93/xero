package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"

	"xero-beacon/internal/beacon"
	"xero-beacon/internal/config"
)

func main() {
	cfg, err := config.Load(os.Args[1:])
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	agent, err := beacon.New(cfg)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	if err := agent.Run(ctx); err != nil && err != context.Canceled {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
