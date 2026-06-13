module xero-beacon

go 1.26

require (
	github.com/creack/pty v1.1.24
	github.com/gorilla/websocket v1.5.3
	xero-protocol v0.0.0
)

require golang.org/x/sys v0.46.0 // indirect

replace xero-protocol => ../../protocol/go
