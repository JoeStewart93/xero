# F0043: Plugin Hot Reload

## Metadata
| Field | Value |
|---|---|
| ID | F0043 |
| Priority | P2 |
| Status | Planned |
| MVP Phase | 5 |
| Depends on | F0041, F0015 |

## Summary
Hot-reload capability that updates plugin modules on beacons and C2 without beacon restart, using versioned plugin packages and in-place module registry refresh.

## Requirements
- Upload new plugin version without disabling beacon
- C2 pushes plugin update notification to beacons via heartbeat
- Beacon downloads and loads new plugin package in background
- Rollback to prior plugin version on load failure
- Hot-reload status visible in plugin management UI

## Stages

### Stage 1: Versioned plugins
**Goal:** Plugin versioning and update detection.
**Acceptance Criteria:**
- [ ] Plugin manifest includes version semver
- [ ] C2 compares beacon-reported plugin versions on heartbeat
- [ ] Update available flag in heartbeat response

### Stage 2: Beacon plugin loader
**Goal:** Go beacon dynamic plugin load without restart.
**Acceptance Criteria:**
- [ ] Beacon downloads plugin artifact from C2 on update notification
- [ ] Load failure retains previous version and reports error
- [ ] Plugin load completes within one sleep cycle

### Stage 3: UI status
**Goal:** Show reload status per plugin per beacon.
**Acceptance Criteria:**
- [ ] Plugin page shows version deployed per beacon
- [ ] Reload in progress spinner during update
- [ ] Reload failure shows error with rollback confirmation

## Feature Acceptance Criteria

- [ ] Plugin update deployed to beacon without beacon process restart
- [ ] Failed reload rolls back to previous working version
- [ ] Operator sees reload status in plugin management UI

## Test Plan

### Unit Tests
- [ ] test_version_compare_detects_update
- [ ] test_beacon_plugin_download_and_load
- [ ] test_load_failure_rollback
- [ ] test_heartbeat_update_notification

### System / Integration Tests
- [ ] Upload plugin v2; beacon reloads; v2 execute returns new output
- [ ] Upload broken plugin v3; beacon rolls back to v2
- [ ] Hot-reload completes while beacon continues heartbeating

### Playwright Tests
- [ ] Upload new plugin version; UI shows reload in progress
- [ ] After reload; module version badge updates to new version
- [ ] Rollback event shows warning toast in plugin settings
