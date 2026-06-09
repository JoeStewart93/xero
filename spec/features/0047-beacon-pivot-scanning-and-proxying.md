# F0047: Beacon Pivot Scanning and Proxying

## Metadata
| Field | Value |
|---|---|
| ID | F0047 |
| Priority | P2 |
| Status | Planned |
| MVP Phase | 5 |
| Depends on | F0015, F0016, F0046 |

## Summary
Allow an installed beacon to act as a controlled scanner or proxy vantage point for authorized project scope. Pivot mode is a later capability and is not available by default.

## Requirements
- Pivot jobs require explicit operator action and active project scope
- Beacon pivot worker can execute approved scan shards from its network vantage point
- Beacon pivot proxy can relay approved connections through the beacon route
- C2 records beacon, operator, project, route, target, and timing audit metadata
- Pivot jobs reuse scan job/result aggregation where possible

## Stages

### Stage 1: Pivot route model
**Goal:** Define beacon-backed scan/proxy routes.
**Acceptance Criteria:**
- [ ] `pivot_routes` tracks beacon id, project id, route kind, status, and audit metadata
- [ ] Pivot route creation requires active beacon and active project scope
- [ ] Pivot routes can be disabled without deleting historical audit records

### Stage 2: Pivot scan execution
**Goal:** Dispatch scan shards through an approved beacon route.
**Acceptance Criteria:**
- [ ] Scan request supports beacon pivot execution target
- [ ] Pivot scan shard reports progress and results through C2
- [ ] Pivot scan failure is isolated to that route and reported clearly

### Stage 3: Pivot proxy workflow
**Goal:** Support controlled proxying through a beacon route.
**Acceptance Criteria:**
- [ ] Operator can request an approved proxy route to a scoped target
- [ ] Proxy lifecycle emits start, stop, error, and audit events
- [ ] C2 enforces route and target scope before proxy activation

## Feature Acceptance Criteria

- [ ] Operator can launch a scoped scan through a selected beacon pivot
- [ ] Pivot results merge into the normal scan result view with route provenance
- [ ] Proxy route cannot be created outside active project scope

## Test Plan

### Unit Tests
- [ ] test_pivot_route_requires_active_project
- [ ] test_pivot_route_requires_active_beacon
- [ ] test_pivot_target_scope_validation
- [ ] test_pivot_scan_result_provenance
- [ ] test_pivot_proxy_audit_event_schema

### System / Integration Tests
- [ ] Run pivot scan through lab beacon and verify internal-only target reachability
- [ ] Attempt out-of-scope pivot target and verify rejection
- [ ] Start and stop pivot proxy; audit events are persisted

### Playwright Tests
- [ ] Beacon operations modal offers pivot scan/proxy actions when feature is available
- [ ] Recon scan form can select an eligible beacon pivot route
- [ ] Pivot route detail shows beacon, project, target, status, and audit trail
