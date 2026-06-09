# F0045: Scanner Worker Registry

## Metadata
| Field | Value |
|---|---|
| ID | F0045 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 5 |
| Depends on | F0004, F0005, F0006, F0007 |

## Summary
Register and manage scanner workers that execute recon jobs under Xero C2 control. The C2 backend remains the embedded/default scanner, while external scanner workers can be added for remote vantage points, capacity, and fault isolation.

## Requirements
- C2 backend exposes an embedded scanner identity by default
- External scanners register with C2 using a scanner registration secret or certificate
- Scanner workers report heartbeat, status, capacity, version, and capabilities
- C2 tracks scanner health and removes unhealthy scanners from assignment
- UI shows scanner inventory, health, capabilities, and current job count

## Stages

### Stage 1: Scanner identity model
**Goal:** Define scanner worker records and embedded scanner defaults.
**Acceptance Criteria:**
- [ ] `scanner_workers` data model includes id, name, kind, status, capabilities, capacity, last_seen, and version
- [ ] Embedded C2 scanner is represented as a reserved scanner worker
- [ ] External scanner records are distinct from embedded C2 scanner records

### Stage 2: Scanner registration and heartbeat
**Goal:** Allow external scanners to join and maintain liveness.
**Acceptance Criteria:**
- [ ] Scanner registration validates configured scanner credential
- [ ] Scanner heartbeat updates status, capacity, capabilities, and last_seen
- [ ] Missed heartbeats mark scanner unhealthy without deleting history

### Stage 3: Scanner inventory UI
**Goal:** Show scanner readiness to operators.
**Acceptance Criteria:**
- [ ] Settings or Inventory area lists embedded and external scanners
- [ ] Scanner detail shows capabilities, current jobs, status, and last heartbeat
- [ ] Unhealthy scanners are visually distinct and unavailable for assignment

## Feature Acceptance Criteria

- [ ] C2 embedded scanner is visible and selectable as the default scanner
- [ ] External scanner can register, heartbeat, and appear online
- [ ] Offline scanner is removed from new job assignment candidates

## Test Plan

### Unit Tests
- [ ] test_embedded_scanner_seed
- [ ] test_scanner_registration_auth_required
- [ ] test_scanner_heartbeat_updates_capacity
- [ ] test_scanner_capability_schema
- [ ] test_unhealthy_scanner_excluded_from_assignment

### System / Integration Tests
- [ ] Start C2; embedded scanner appears in scanner registry
- [ ] Register external scanner; heartbeat keeps it online
- [ ] Stop scanner heartbeat; C2 marks scanner unhealthy

### Playwright Tests
- [ ] Scanner inventory shows embedded C2 scanner
- [ ] External scanner appears online after registration
- [ ] Unhealthy scanner displays warning state and unavailable assignment state
