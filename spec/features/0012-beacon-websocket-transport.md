# F0012: Beacon WebSocket Transport

## Metadata
| Field | Value |
|---|---|
| ID | F0012 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 2 |
| Depends on | F0009, F0011 |

## Summary
Primary WebSocket transport layer for beacon-to-C2/handler communication, carrying binary protocol frames over TLS-upgraded persistent connections with backpressure handling.

## Requirements
- FR-02: WebSocket as primary beacon transport
- TLS 1.3 termination at reverse proxy or backend
- Binary WebSocket frames carrying protocol codec payloads
- Per-beacon connection registry with graceful close
- Ping/pong keepalive at transport layer

## Stages

### Stage 1: Beacon WS endpoint
**Goal:** Expose /ws/beacon for authenticated binary frame exchange.
**Acceptance Criteria:**
- [ ] Beacon connects with registration token or beacon_id
- [ ] Binary frames decoded via protocol codec
- [ ] Text frames rejected with protocol error close code

### Stage 2: Connection manager
**Goal:** Track active beacon WebSocket connections by beacon_id.
**Acceptance Criteria:**
- [ ] Duplicate connection for same beacon_id closes older socket
- [ ] Disconnect updates beacon status via heartbeat stale logic
- [ ] Connection count exposed in /health metrics

### Stage 3: Backpressure and ping
**Goal:** Handle slow consumers and transport keepalive.
**Acceptance Criteria:**
- [ ] Send buffer limit closes connection if exceeded
- [ ] Server sends WS ping every 30s; missing pong triggers disconnect
- [ ] Large frames chunked per WebSocket max frame size config

## Feature Acceptance Criteria

- [ ] Beacon maintains persistent WS connection for task poll and result delivery
- [ ] Binary frames round-trip without corruption at 1MB payload size
- [ ] Duplicate beacon connection handled without message cross-talk

## Test Plan

### Unit Tests
- [ ] test_beacon_ws_accepts_binary_frame
- [ ] test_beacon_ws_rejects_text_frame
- [ ] test_duplicate_connection_closes_prior
- [ ] test_ping_pong_keepalive
- [ ] test_backpressure_disconnect

### System / Integration Tests
- [ ] Test beacon connects via WS; sends REGISTER frame; receives ACK
- [ ] Disconnect WS; beacon marked offline after stale threshold
- [ ] Send 100 sequential frames; all decoded without loss

### Playwright Tests
- [ ] Settings shows active WebSocket beacon connection count
- [ ] Beacon transport column shows WebSocket in beacon detail
- [ ] Disconnect event reflected in dashboard within 5 seconds
