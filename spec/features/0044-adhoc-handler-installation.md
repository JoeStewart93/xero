# F0044: Ad-Hoc Handler Installation

## Metadata
| Field | Value |
|---|---|
| ID | F0044 |
| Priority | P2 |
| Status | Planned |
| MVP Phase | 5 |
| Depends on | F0038, F0029, F0015 |

## Summary
Capability for Xero C2 to push connection handler binaries to authorized beacon hosts via file transfer, remotely install and launch them, turning beacon hosts into ad-hoc relay infrastructure.

## Requirements
- FR-12: C2 pushes handler binaries to beacons (P2)
- Task module builtin.install_handler with handler binary and config
- Beacon installs handler as service or background process
- C2 registers new handler instance automatically on tunnel connect
- Ad-hoc path: Beacon A -> Beacon B (as handler) -> C2

## Stages

### Stage 1: Install task module
**Goal:** Define install_handler task with binary and config args.
**Acceptance Criteria:**
- [ ] Task uploads handler binary via file transfer protocol
- [ ] Config includes listen port, C2 URL, cert pin
- [ ] Install script written for Windows (service) and Linux (systemd/user)

### Stage 2: Beacon installer
**Goal:** Go beacon installs and starts handler process.
**Acceptance Criteria:**
- [ ] Binary written to configurable path with appropriate permissions
- [ ] Handler started as child process or OS service
- [ ] Install result reports handler PID and listen port

### Stage 3: Auto-registration
**Goal:** C2 detects and registers ad-hoc handler on tunnel.
**Acceptance Criteria:**
- [ ] New handler tunnel triggers HANDLER_REGISTER with adhoc flag
- [ ] UI shows ad-hoc badge on handler instance
- [ ] Other beacons can be redirected to ad-hoc handler

## Feature Acceptance Criteria

- [ ] Operator installs handler on beacon host; handler tunnels to C2
- [ ] Second beacon routes through ad-hoc handler successfully
- [ ] Ad-hoc handler appears in handler list with adhoc badge

## Test Plan

### Unit Tests
- [ ] test_install_handler_task_schema
- [ ] test_beacon_writes_binary_and_starts_handler
- [ ] test_adhoc_handler_register_flag
- [ ] test_install_failure_rollback_cleanup

### System / Integration Tests
- [ ] Dispatch install_handler to lab beacon; handler tunnels to C2
- [ ] Route second beacon via ad-hoc handler; task completes
- [ ] Failed install cleans up binary and reports error

### Playwright Tests
- [ ] Install handler action available in beacon context menu
- [ ] Install progress shown during binary upload and install
- [ ] Ad-hoc handler appears in handlers list with badge
