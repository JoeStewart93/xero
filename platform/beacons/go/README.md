# Xero Go Beacon

F0015 introduces a first real beacon agent for validation and operator tasking.
It uses the F0011 binary protocol, WebSocket as the primary F0012 transport, and
F0013 long-poll fallback after the beacon has a saved `beacon_id` and token.

## Configuration

Precedence is:

1. Compile-time `-ldflags -X xero-beacon/internal/config.<Name>=<value>`
2. JSON file from `-config` or `XERO_BEACON_CONFIG`
3. Environment variables

Required values are `c2_url` and `c2_public_key_b64`. Runtime state is stored
separately at `state_path` and contains only the `beacon_id` and beacon token.

Common environment overrides:

- `XERO_BEACON_C2_URL`
- `XERO_BEACON_C2_PUBLIC_KEY_B64`
- `XERO_BEACON_CONFIG`
- `XERO_BEACON_STATE_PATH`
- `XERO_BEACON_TRANSPORT=auto|websocket|long-poll`
- `XERO_BEACON_FALLBACK_LONGPOLL_ENABLED=true`

## Build And Test

```sh
go test ./...
make build-linux
make build-windows
```

If local Go is unavailable, use the platform CI helper, which falls back to
Docker:

```sh
python platform/scripts/ci.py go-beacon-test
python platform/scripts/ci.py go-beacon-build
```
