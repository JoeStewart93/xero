# F0010: Beacon Heartbeat Keepalive

## Metadata
| Field | Value |
|---|---|
| ID | F0010 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 2 |
| Depends on | F0009 |

## Summary
Heartbeat mechanism that tracks beacon liveness via periodic check-ins, marks stale beacons offline, and surfaces last-seen timestamps to operators.

## Current Implementation Notes
F0010 completes token-authenticated beacon keepalive for the C2 backend. `POST /api/v1/beacons/{beacon_id}/heartbeat` is C2-role only and authenticates with the F0009 opaque per-beacon token via `Authorization: Bearer <beacon_token>`. Heartbeats update `last_seen`, keep or restore `status=online`, optionally update runtime metadata, return sleep/jitter profile values, and publish `beacon.heartbeat`. Offline-to-online recovery and stale offline transitions are logged in `beacon_events` and publish `beacon.status.changed`. The C2 app runs a C2-only stale monitor using `BEACON_HEARTBEAT_CHECK_INTERVAL_SECONDS`, `BEACON_STALE_THRESHOLD_MULTIPLIER`, and optional `BEACON_STALE_THRESHOLD_SECONDS`. The operator UI shows relative last heartbeat values plus active/offline counts.

## Requirements
- Configurable heartbeat interval and stale threshold per profile
- POST /api/v1/beacons/{id}/heartbeat endpoint
- Automatic offline transition when heartbeat missed
- Redis pub/sub event on status change for realtime UI
- last_seen updated atomically on each heartbeat

## Stages

### Stage 1: Heartbeat endpoint
**Goal:** Accept lightweight heartbeat payloads from registered beacons.
**Acceptance Criteria:**
- [x] Heartbeat updates last_seen and status=online
- [x] Unknown beacon_id returns 404
- [x] Heartbeat payload optional fields update runtime metadata

### Stage 2: Stale detection
**Goal:** Background job marks beacons offline after threshold.
**Acceptance Criteria:**
- [x] Scheduler runs every 30s checking last_seen vs threshold
- [x] Missed threshold sets status=offline and emits event
- [x] Threshold configurable via environment default 3x sleep interval

### Stage 3: Status API
**Goal:** Expose beacon online/offline status in list and detail endpoints.
**Acceptance Criteria:**
- [x] GET /beacons includes status and last_seen fields
- [x] Filter query param ?status=online returns only live beacons
- [x] Status transitions logged in beacon_events table

## Feature Acceptance Criteria

- [x] Beacon marked offline within 3x sleep interval of last heartbeat
- [x] Heartbeat check-in restores offline beacon to online with event
- [x] Operator can see last_seen relative time in UI

## Test Plan

### Unit Tests
- [x] test_heartbeat_updates_last_seen
- [x] test_stale_beacon_marked_offline
- [x] test_heartbeat_unknown_id_returns_404
- [x] test_status_filter_online_only
- [x] test_offline_to_online_transition_emits_event

### System / Integration Tests
- [x] Register beacon; send heartbeat; verify status online
- [x] Stop heartbeats; wait threshold; verify status offline
- [x] Resume heartbeat; verify status returns online

### Playwright Tests
- [x] Beacon list shows green Online badge after heartbeat
- [x] Stale beacon shows Offline badge and last seen timestamp
- [x] Dashboard offline count increments when beacon goes stale
