# F0045: Scanner Worker Registry

## Metadata
| Field | Value |
|---|---|
| ID | F0045 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 5 |
| Depends on | F0049 |

## Summary
Register and manage scanner workers that execute recon jobs under Xero C2 control. The C2 backend remains the embedded/default scanner, while external scanner workers can be added for remote vantage points, capacity, and fault isolation.

## Implementation Note
F0049 now provides the shared infrastructure worker registry, one-time pairing tokens, worker heartbeat/liveness, embedded scanner identity, and the Settings > Infrastructure inventory surface. F0045 remains planned for scanner-specific execution semantics: scanner eligibility for jobs, assignment candidate selection, scan job integration, scanner draining, and execution-specific health/capability rules.

## Requirements
- C2 backend exposes an embedded scanner identity by default through F0049
- External scanners register with C2 through F0049 pairing and heartbeat
- Scanner workers report heartbeat, status, capacity, version, and capabilities through F0049
- C2 tracks scanner health and removes unhealthy scanners from scan assignment candidates
- UI shows scanner inventory, health, capabilities, and current job count

## Stages

### Stage 1: Scanner identity model
**Goal:** Define scanner worker records and embedded scanner defaults.
**Acceptance Criteria:**
- [x] Shared `infrastructure_workers` model includes id, name, kind, status, capabilities, capacity, last_seen, and version in F0049
- [x] Embedded C2 scanner is represented as a reserved scanner worker in F0049
- [x] External scanner records are distinct from embedded C2 scanner records in F0049
- [ ] Scanner execution eligibility fields are defined for recon job assignment

### Stage 2: Scanner registration and heartbeat
**Goal:** Allow external scanners to join and maintain liveness.
**Acceptance Criteria:**
- [x] Scanner registration validates a one-time F0049 pairing token
- [x] Scanner heartbeat updates status, capacity, capabilities, and last_seen in F0049
- [x] Missed heartbeats mark scanner unhealthy without deleting history in F0049
- [ ] Unhealthy scanner is excluded from scan assignment candidates

### Stage 3: Scanner inventory UI
**Goal:** Show scanner readiness to operators.
**Acceptance Criteria:**
- [x] Settings / Infrastructure lists embedded and external scanners in F0049
- [x] Scanner detail shows capabilities, current load, status, and last heartbeat in F0049
- [x] Unhealthy scanners are visually distinct in F0049
- [ ] Unhealthy scanners are unavailable for scan assignment

## Feature Acceptance Criteria

- [x] C2 embedded scanner is visible as the default scanner through F0049
- [x] External scanner can register, heartbeat, and appear online through F0049
- [ ] Offline scanner is removed from new job assignment candidates

## Test Plan

### Unit Tests
- [x] test_embedded_scanner_seed
- [x] test_scanner_registration_auth_required
- [x] test_scanner_heartbeat_updates_capacity
- [x] test_scanner_capability_schema
- [ ] test_unhealthy_scanner_excluded_from_assignment

### System / Integration Tests
- [x] Start C2; embedded scanner appears in scanner registry
- [x] Register external scanner; heartbeat keeps it online
- [x] Stop scanner heartbeat; C2 marks scanner unhealthy through shared stale detector
- [ ] Assign a scan job only to healthy scanner candidates

### Playwright Tests
- [x] Scanner inventory shows embedded C2 scanner
- [x] External scanner pairing workflow creates a startup token/command
- [ ] External scanner appears online after full worker process registration
- [ ] Unhealthy scanner displays warning state and unavailable assignment state
