module xero-beacon

go 1.26

require (
	github.com/gorilla/websocket v1.5.3
	xero-protocol v0.0.0
)

replace xero-protocol => ../../protocol/go
