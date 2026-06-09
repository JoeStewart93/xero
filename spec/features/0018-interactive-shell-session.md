# F0018: Interactive Shell Session

## Metadata
| Field | Value |
|---|---|
| ID | F0018 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 3 |
| Depends on | F0016, F0017 |

## Summary
Persistent interactive shell sessions (cmd, PowerShell, bash) between operator and beacon with real-time stdin/stdout streaming over the session channel of the binary protocol.

## Requirements
- Session types: cmd, powershell, bash per beacon OS
- POST /api/v1/sessions/shell opens session; DELETE closes
- Bidirectional streaming via SESSION_DATA protocol messages
- Operator WebSocket relays session output to terminal UI
- Session timeout after configurable idle period

## Stages

### Stage 1: Session manager
**Goal:** Backend session registry with lifecycle management.
**Acceptance Criteria:**
- [ ] sessions table tracks type, beacon_id, status, opened_at
- [ ] Open session sends SESSION_OPEN frame to beacon
- [ ] Close session sends SESSION_CLOSE and cleans up resources

### Stage 2: Beacon PTY
**Goal:** Go beacon spawns interactive shell with PTY.
**Acceptance Criteria:**
- [ ] Beacon maintains PTY process for session lifetime
- [ ] stdin from SESSION_DATA written to PTY
- [ ] stdout/stderr streamed back as SESSION_DATA chunks

### Stage 3: Terminal UI
**Goal:** Browser terminal component with xterm.js.
**Acceptance Criteria:**
- [ ] Open shell from beacon context menu
- [ ] Keystrokes sent via WebSocket to backend session relay
- [ ] Terminal resizes propagated to beacon PTY

## Feature Acceptance Criteria

- [ ] Operator opens shell and runs interactive commands with live output
- [ ] Session survives 5 minutes idle within configured timeout
- [ ] Closing browser tab triggers session cleanup within 30s

## Test Plan

### Unit Tests
- [ ] test_session_open_close_lifecycle
- [ ] test_session_data_relay_encode_decode
- [ ] test_idle_timeout_closes_session
- [ ] test_pty_resize_propagation
- [ ] test_concurrent_sessions_different_beacons

### System / Integration Tests
- [ ] Open shell session; send ls/dir; output appears in relay
- [ ] Close session; beacon terminates PTY process
- [ ] Two operators cannot attach to same session simultaneously

### Playwright Tests
- [ ] Open interactive shell from beacon row; terminal renders prompt
- [ ] Type command in terminal; output appears within 2 seconds
- [ ] Close session button terminates session and disables terminal input
