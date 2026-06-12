# F0018: Interactive Shell Session

## Metadata
| Field | Value |
|---|---|
| ID | F0018 |
| Priority | P0 |
| Status | Completed |
| MVP Phase | 3 |
| Depends on | F0016, F0017 |

## Summary
Persistent interactive shell sessions (cmd, PowerShell, bash) between operator and beacon with real-time stdin/stdout streaming over the session channel of the binary protocol.

## Requirements
- Session types: cmd, powershell, bash per beacon OS
- POST /api/v1/sessions/shell opens session; DELETE closes
- Bidirectional streaming via `SESSION_DATA` protocol messages
- Operator WebSocket relays session output to terminal UI
- Session timeout after configurable idle period

## Stages

### Stage 1: Session manager
**Goal:** Backend session registry with lifecycle management.
**Acceptance Criteria:**
- [x] sessions table tracks type, beacon_id, status, opened_at
- [x] Open session sends `SESSION_DATA` `op=open` frame to beacon
- [x] Close session sends `SESSION_DATA` `op=close` and cleans up resources

### Stage 2: Beacon PTY
**Goal:** Go beacon spawns interactive shell with PTY.
**Acceptance Criteria:**
- [x] Beacon maintains PTY process for session lifetime
- [x] stdin from SESSION_DATA written to PTY
- [x] stdout/stderr streamed back as SESSION_DATA chunks

### Stage 3: Terminal UI
**Goal:** Browser terminal component with xterm.js.
**Acceptance Criteria:**
- [x] Open shell from beacon context menu
- [x] Keystrokes sent via WebSocket to backend session relay
- [x] Terminal resizes propagated to beacon PTY

## Feature Acceptance Criteria

- [x] Operator opens shell and runs interactive commands with live output
- [x] Session survives 5 minutes idle within configured timeout
- [x] Closing browser tab triggers session cleanup within 30s

## Test Plan

### Unit Tests
- [x] test_session_open_close_lifecycle
- [x] test_session_data_relay_encode_decode
- [x] test_idle_timeout_closes_session
- [x] test_pty_resize_propagation
- [x] test_concurrent_sessions_different_beacons

### System / Integration Tests
- [x] Open shell session; send ls/dir; output appears in relay
- [x] Close session; beacon terminates PTY process
- [x] Two operators cannot attach to same session simultaneously

### Playwright Tests
- [x] Open interactive shell from beacon row; terminal renders prompt
- [x] Type command in terminal; output appears within 2 seconds
- [x] Close session button terminates session and disables terminal input

## Implementation Notes

- F0018 uses the existing protocol message type `SESSION_DATA`; lifecycle operations are encoded in the payload as `op=open`, `op=close`, `op=stdin`, `op=stdout`, `op=stderr`, `op=resize`, `op=exit`, and `op=error`.
- The interactive shell session ID is an application session ID and is distinct from the protocol frame `session_id` used for cryptographic replay protection.
- The Go beacon session manager uses an OS-specific terminal backend: Unix builds use `github.com/creack/pty` with resize propagation, and Windows builds keep a portable process-stream fallback behind the same session manager boundary.

## Validation Evidence

- `python platform/scripts/ci.py backend-lint`
- `python platform/scripts/ci.py backend-unit`
- `python platform/scripts/ci.py go-beacon-build`
- `npm --prefix platform/frontend run lint`
- `npm --prefix platform/frontend test -- --run`
- `npm --prefix platform/frontend run build`
- `python platform/scripts/ci.py openapi-export`
- `python platform/scripts/ci.py openapi-check`
- Browser QA on `http://127.0.0.1:3001/beacons` with mocked C2 responses verified the beacon modal, interactive session panel, xterm render, `open` status, and live `whoami` output.

## Maintainability Review

- Backend session lifecycle, relay, protocol encoding, and cleanup logic are isolated in `xero_c2.sessions`, keeping route handlers thin.
- Beacon terminal process management is isolated in `internal/session` with OS-specific backend files, leaving room for a future Windows ConPTY implementation without changing protocol or UI contracts.
- Frontend session WebSocket behavior lives in `shellSessionClient.ts`; the Beacons page owns only UI state and terminal lifecycle wiring.
- No additional refactor round is required for F0018.
