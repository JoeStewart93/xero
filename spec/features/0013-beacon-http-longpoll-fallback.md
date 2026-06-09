# F0013: Beacon HTTP Long-Poll Fallback

## Metadata
| Field | Value |
|---|---|
| ID | F0013 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 2 |
| Depends on | F0009, F0011 |

## Summary
HTTP long-polling fallback transport for beacons unable to maintain WebSocket connections, using hold-open GET requests for task delivery and POST for outbound frames.

## Requirements
- FR-02: HTTP long-polling fallback when WebSocket unavailable
- GET /api/v1/beacons/{id}/poll holds up to 60s for pending tasks
- POST /api/v1/beacons/{id}/frame accepts binary protocol frames
- Beacon auto-fallback from WS to long-poll on connection failure
- Same codec and encryption as WebSocket transport

## Stages

### Stage 1: Long-poll endpoint
**Goal:** Implement task poll with timeout and immediate return on task.
**Acceptance Criteria:**
- [ ] Poll request blocks until task available or timeout
- [ ] Timeout returns 204 No Content
- [ ] Task available returns encrypted binary frame in body

### Stage 2: Frame POST endpoint
**Goal:** Accept beacon-originated frames via HTTP POST.
**Acceptance Criteria:**
- [ ] POST body contains raw encoded binary frame
- [ ] Same validation and decoding as WebSocket path
- [ ] Returns encoded ACK frame in response body

### Stage 3: Beacon fallback logic
**Goal:** Go beacon switches transport on WS failure.
**Acceptance Criteria:**
- [ ] Beacon retries WS 3 times then switches to long-poll
- [ ] Transport mode reported in heartbeat metadata
- [ ] Operator can see active transport per beacon

## Feature Acceptance Criteria

- [ ] Beacon completes full task cycle using long-poll only
- [ ] Fallback from WS to long-poll automatic without operator action
- [ ] Long-poll and WS beacons interoperate on same task queue

## Test Plan

### Unit Tests
- [ ] test_longpoll_returns_task_when_queued
- [ ] test_longpoll_timeout_returns_204
- [ ] test_frame_post_decodes_same_as_ws
- [ ] test_beacon_transport_fallback_detection

### System / Integration Tests
- [ ] Queue task for long-poll beacon; poll returns task within 5s
- [ ] Beacon sends result via POST; result stored in database
- [ ] WS failure simulation triggers long-poll mode in test beacon

### Playwright Tests
- [ ] Beacon detail shows transport mode Long-Poll when applicable
- [ ] Task dispatched to long-poll beacon shows In Progress then Complete
- [ ] Settings transport stats show WS vs long-poll beacon counts
