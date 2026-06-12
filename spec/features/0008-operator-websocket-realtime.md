# F0008: Operator WebSocket Realtime

## Metadata
| Field | Value |
|---|---|
| ID | F0008 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 2 |
| Depends on | F0004, F0006, F0007 |

## Summary
Direct-to-C2 operator WebSocket gateway that pushes beacon status changes, future task completions, and future session events to the Xero UI in real time via Redis pub/sub fan-out.

## Current Implementation Notes
- The operator UI connects directly to `/ws/operator` on the configured C2 backend using the C2 session token from Settings; non-C2 service roles reject the socket with `4403`.
- Redis broadcast channel `events:operator` fans out versioned JSON events to all connected operator tabs.
- F0009/F0010 beacon APIs now publish real `beacon.registered`, `beacon.heartbeat`, and `beacon.status.changed` events for realtime verification.
- Task result and session output producers remain owned by F0014/F0017/F0018+, but the F0008 event envelope accepts those event types.

## Requirements
- FR-02: WebSocket support for operator-facing real-time updates
- JWT-authenticated WebSocket connections from the Xero UI/BFF stack
- Redis pub/sub bridge for backend event broadcasting
- Automatic reconnection and heartbeat on client disconnect
- Event envelope supports beacon registration/status events today and future task result/session output events as their producers land.

## Stages

### Stage 1: WebSocket endpoint
**Goal:** Expose authenticated /ws/operator endpoint on the C2 FastAPI role.
**Acceptance Criteria:**
- [x] WebSocket accepts connection with valid JWT query param or header
- [x] Invalid or missing JWT closes connection with 4401 code
- [x] Non-C2 backend roles close connection with 4403 code
- [x] Connection registered in active subscriber registry

### Stage 2: Redis pub/sub bridge
**Goal:** Subscribe to Redis channels and forward events to connected clients.
**Acceptance Criteria:**
- [x] Backend publishes beacon events to redis channels; task/session producers remain in their owning features
- [x] WebSocket handler forwards JSON events to all connected operators
- [x] Unsubscribe and cleanup on client disconnect

### Stage 3: Client reconnection
**Goal:** Implement resilient client-side WebSocket with backoff.
**Acceptance Criteria:**
- [x] Frontend realtime client reconnects with exponential backoff
- [x] Missed beacon events reconciled via REST on reconnect
- [x] Connection status indicator in UI shell

## Feature Acceptance Criteria

- [x] Operator UI receives beacon registration/status updates within 2 seconds of change
- [x] Multiple operator tabs can connect simultaneously without event loss
- [x] WebSocket survives brief Redis blip with graceful degradation message

## Test Plan

### Unit Tests
- [x] test_ws_rejects_unauthenticated_connection
- [x] test_ws_accepts_valid_jwt
- [x] test_pubsub_event_serialized_to_ws_message
- [x] test_subscriber_cleanup_on_disconnect
- [x] test_reconnect_backoff_schedule

### System / Integration Tests
- [x] Publish beacon event to Redis; connected WS client receives payload
- [x] Disconnect Redis; WS clients receive degraded status event
- [x] Two concurrent WS clients both receive same realtime event

### Playwright Tests
- [x] App shell realtime indicator shows Connected when WS established
- [x] Simulate beacon check-in; Home beacon count updates without refresh
- [x] Backend integration covers Redis degradation/recovery; frontend unit tests cover reconnecting/degraded/recovered client states.

## Follow-up (F0074)

- WebSocket auth must accept C2 operator JWTs (`kind: operator-session`); anonymous `c2-connect` tokens are rejected.
- `RealtimePrincipal` includes `operator_id` and username for future audit and RBAC (F0105).
