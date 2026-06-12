# F0012: Beacon WebSocket Transport

## Metadata
| Field | Value |
|---|---|
| ID | F0012 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 2 |
| Depends on | F0009, F0011 |

## Summary
Primary WebSocket transport layer for beacon-to-C2 communication, carrying F0011 binary protocol frames over persistent WebSocket connections with backpressure handling, duplicate replacement, encrypted ACKs, redacted security events, and operator-visible transport state.

## Requirements
- FR-02: WebSocket as primary beacon transport
- TLS 1.3 termination at reverse proxy or backend
- Binary WebSocket frames carrying protocol codec payloads
- Per-beacon connection registry with graceful close
- Ping/pong keepalive at transport layer
- C2-token-protected transport status endpoint for operator UI observability

## Stages

### Stage 1: Beacon WS endpoint
**Goal:** Expose /ws/beacon for authenticated binary frame exchange.
**Acceptance Criteria:**
- [x] New beacons connect with subprotocol `xero.beacon.v1` and send encrypted `REGISTER` within the registration timeout.
- [x] Existing beacons reconnect with `beacon_id` plus bearer token via `Authorization` or `bearer.<token>` subprotocol.
- [x] Binary frames decode through the shared F0011 protocol codec.
- [x] Text frames are rejected with a protocol close code and redacted security event.
- [x] Malformed, tampered, replayed, and oversized frames close without 500s.

### Stage 2: Connection manager
**Goal:** Track active beacon WebSocket connections by beacon_id.
**Acceptance Criteria:**
- [x] Duplicate connection for same beacon_id closes older socket with duplicate close code.
- [x] Disconnect clears only the matching active connection and updates transport connected state immediately.
- [x] Beacon online/offline status remains owned by heartbeat stale logic.
- [x] Active connection count and WebSocket limits are exposed through C2-token-protected `GET /api/v1/transport`.

### Stage 3: Backpressure and ping
**Goal:** Handle slow consumers and transport keepalive.
**Acceptance Criteria:**
- [x] Bounded send queue closes overloaded connections.
- [x] Uvicorn native WebSocket ping interval, ping timeout, and max message bytes are configured from `C2_BEACON_WS_*` env values.
- [x] Encrypted HEARTBEAT frames update `last_seen`, `protocol_last_seen`, `transport_last_seen`, status, and runtime metadata.
- [x] Large frames up to the configured WebSocket max message size round-trip without corruption; app-level chunking remains out of scope for F0017.

### Stage 4: Harness reuse and UI observability
**Goal:** Share protocol processing and expose transport state to operators.
**Acceptance Criteria:**
- [x] HTTP harness and WebSocket transport share decoding, replay checks, receipt recording, REGISTER handling, ACK creation, and security-event logging.
- [x] `REGISTER` rotates the beacon token and returns it only inside the encrypted ACK.
- [x] `TASK_POLL` returned encrypted no-task ACKs before F0014; F0014 now dispatches queued tasks over the same ACK path.
- [x] `TASK_RESULT` records protocol frame receipts and returns `receipt=stored` without task-result domain storage.
- [x] Settings/C2 shows protocol status, active WebSocket count, queue size, max message bytes, registration timeout, heartbeat timeout, and ping settings.
- [x] Beacons roster/detail show transport mode and connected/disconnected state.

## Feature Acceptance Criteria

- [x] Beacon maintains persistent WS connection for registration, heartbeat, task poll, and result receipt ACKs.
- [x] Binary frames round-trip without corruption at roughly 1MB wire-frame size.
- [x] Duplicate beacon connection handled without message cross-talk.
- [x] Invalid frames log redacted security events and never expose token/key/plaintext material.
- [x] Public `/health` and `/ready` remain simple container health contracts; transport metrics live behind C2 auth.

## Test Plan

### Unit Tests
- [x] WebSocket accepts encrypted REGISTER and returns encrypted ACK with token.
- [x] Existing beacon authenticates with `beacon_id` and token.
- [x] Text frames are rejected.
- [x] Duplicate connection closes prior socket and avoids cross-talk.
- [x] HMAC tamper, replay, malformed, and oversized frames log security events and do not 500.
- [x] Send-queue backpressure closes overloaded connection.
- [x] HEARTBEAT updates beacon transport and heartbeat metadata.
- [x] Transport status endpoint requires C2 auth and reports active count.

### System / Integration Tests
- [x] Compose C2 accepts WebSocket REGISTER fixture and lists beacon as WebSocket transport.
- [x] Roughly 1MB binary frame round-trips without corruption.
- [x] 100 sequential frames are ACKed and receipt count matches.
- [x] Disconnect clears active transport count immediately; stale/offline behavior remains heartbeat-owned.

### Playwright Tests
- [x] Settings/C2 shows active WebSocket beacon connection count.
- [x] Beacon roster/detail shows WebSocket transport for a binary-registered beacon.
- [x] Disconnect event is reflected in Settings/C2 within 5 seconds.

## Completion Evidence

- Backend lint, unit, behave, integration, OpenAPI export/check, Go protocol tests, frontend lint/unit/build, Docker BFF+C2 stacks, full Playwright E2E, and Browser sanity validation passed on June 11, 2026.
