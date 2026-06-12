# F0013: Beacon HTTP Long-Poll Fallback

## Metadata
| Field | Value |
|---|---|
| ID | F0013 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 2 |
| Depends on | F0009, F0011, F0012 |

## Summary
Authenticated HTTP long-poll fallback transport for beacons that cannot hold WebSocket connections. F0013 provides the fallback transport harness: held poll requests, beacon-originated binary frame POSTs, shared F0011 protocol validation, transport observability, and UI status. Real task queues remain F0014, and Go beacon automatic fallback remains F0015.

## Requirements
- FR-02: HTTP long-polling fallback when WebSocket is unavailable
- `GET /api/v1/beacons/{id}/poll` holds up to the configured timeout and returns `204 No Content` until F0014 supplies task frames
- `POST /api/v1/beacons/{id}/frame` accepts raw F0011 binary frames from an already registered/authenticated beacon
- Same codec, encryption, HMAC, replay, receipt, and security-event path as WebSocket transport
- C2-token-protected transport status exposes WebSocket and long-poll pressure

## Stages

### Stage 1: Long-Poll Endpoint
**Goal:** Implement authenticated held-poll fallback transport.
**Acceptance Criteria:**
- [x] Poll requests require valid beacon bearer token authentication.
- [x] Poll requests mark latest transport as `long-poll` and set `transport_connected=true` only while held.
- [x] Duplicate active poll for the same beacon returns `409`.
- [x] Timeout returns `204 No Content`; task delivery is a future F0014 hook.
- [x] Poll cleanup clears only the matching active poll and publishes transport changes.

### Stage 2: Frame POST Endpoint
**Goal:** Accept beacon-originated protocol frames over HTTP.
**Acceptance Criteria:**
- [x] POST body contains a raw encoded binary frame.
- [x] HEARTBEAT, TASK_POLL, and TASK_RESULT decode through shared protocol processing.
- [x] Path beacon id and payload `beacon_id` must match; binary REGISTER is not accepted on this fallback endpoint.
- [x] Valid frames record receipts and return encrypted ACK frames.
- [x] Malformed, tampered, replayed, oversized, and mismatched frames log redacted protocol security events and never 500.

### Stage 3: Observability
**Goal:** Show long-poll transport state to operators.
**Acceptance Criteria:**
- [x] `GET /api/v1/transport` reports active long-poll requests, transport-mode counts, long-poll timeout, and max frame size.
- [x] Settings/C2 shows WebSocket vs long-poll activity and long-poll limits.
- [x] Beacons roster/detail show `Long-poll` mode and connected/disconnected state.

### Deferred To Later Features
- [ ] F0014: Real task queues, task frames returned from poll, task status transitions, and queue interoperability.
- [ ] F0015: Go beacon automatic retry/fallback from WebSocket to long-poll.
- [ ] F0017: Full task-result domain storage beyond protocol frame receipts.

## Feature Acceptance Criteria

- [x] Existing registered beacons can use long-poll-only frame POSTs for heartbeat, task poll, and result receipt ACKs.
- [x] Long-poll and WebSocket transports share protocol validation and observability.
- [x] Long-poll timeout and active-count behavior are operator-visible.
- [x] Invalid frames are redacted in security events and never expose tokens, keys, or plaintext payloads.

## Test Plan

### Unit Tests
- [x] Poll requires valid beacon token, marks `long-poll`, reports active count while held, rejects duplicate poll, returns 204 on timeout, and clears the active state.
- [x] Frame POST decodes HEARTBEAT, TASK_POLL, and TASK_RESULT through shared protocol logic.
- [x] HMAC tamper, replay, beacon-id mismatch, and oversized frames log security events and do not 500.
- [x] Transport status reports WebSocket, long-poll, and REST counts.

### System / Integration Tests
- [x] Compose C2 accepts long-poll frame POST and lists beacon as `long-poll`.
- [x] Poll timeout returns `204` within requested/configured timeout.
- [x] Roughly 1MB frame POST round-trips without corruption and records receipt.

### Playwright Tests
- [x] Beacon detail shows `Long-poll` after a long-poll frame POST.
- [x] Settings/C2 active long-poll count increases during a held poll and decreases after timeout.
- [x] Settings/C2 shows long-poll timeout and max frame limits.

## Completion Evidence

- Completed on June 11, 2026 with backend lint/unit/behave/integration, OpenAPI export/check, Go protocol tests, frontend lint/unit/build, rebuilt Docker BFF+C2 stacks, full Playwright E2E, and Browser sanity validation passing.
- Browser sanity confirmed Settings/C2 renders active WebSocket/long-poll counts, latest transport-mode counts, long-poll timeout/max frame limits, and Beacons detail renders `Protocol version v1`, `Transport Long-poll`, and `Transport state Disconnected` for an F0013 long-poll beacon.
