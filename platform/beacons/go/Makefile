GO ?= go
BINARY ?= xero-beacon

.PHONY: test build-linux build-windows

test:
	$(GO) test ./...

build-linux:
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 $(GO) build -trimpath -o dist/$(BINARY)-linux-amd64 .

build-windows:
	CGO_ENABLED=0 GOOS=windows GOARCH=amd64 $(GO) build -trimpath -o dist/$(BINARY)-windows-amd64.exe .
