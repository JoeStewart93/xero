# F0015: Go Beacon Agent

## Metadata
| Field | Value |
|---|---|
| ID | F0015 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 2 |
| Depends on | F0011, F0012, F0013, F0014 |

## Summary
MVP Go beacon binary under `platform/beacons/go/` that registers with the Xero C2 backend or assigned handler, maintains heartbeat, polls for tasks, executes built-in handlers, and returns results over the binary protocol.

## Requirements
- FR-16: Support custom profiles (sleep, jitter, user-agent)
- Cross-compile for Windows amd64 and Linux amd64
- Embedded config via compile-time or config file
- Integrate protocol codec, WS transport, and long-poll fallback
- Minimal footprint target under 10MB binary size

## Stages

### Stage 1: Beacon scaffold
**Goal:** Create Go module with main loop and config loading.
**Acceptance Criteria:**
- [ ] platform/beacons/go/ builds with go build
- [ ] Config specifies C2/handler URL, sleep, jitter, profile ID
- [ ] Graceful shutdown on SIGINT/SIGTERM

### Stage 2: C2 loop
**Goal:** Implement register -> heartbeat -> poll -> execute -> result cycle.
**Acceptance Criteria:**
- [ ] Beacon registers on startup and enters main loop
- [ ] Sleep with jitter between poll cycles
- [ ] Task received triggers module dispatch and result upload

### Stage 3: Cross-compile and packaging
**Goal:** Build scripts for target platforms.
**Acceptance Criteria:**
- [ ] Makefile targets windows/amd64 and linux/amd64
- [ ] CI builds beacon artifacts on tagged releases
- [ ] README documents authorized lab deployment only

## Feature Acceptance Criteria

- [ ] Go beacon registers, heartbeats, and completes echo task in lab
- [ ] Beacon survives C2 restart and re-registers automatically
- [ ] Cross-compiled binaries run on Windows and Linux test VMs

## Test Plan

### Unit Tests
- [ ] test_beacon_config_parse
- [ ] test_sleep_jitter_within_bounds
- [ ] test_protocol_register_message_encode
- [ ] test_task_dispatch_to_module_router
- [ ] test_result_frame_encode

### System / Integration Tests
- [ ] Start compose stack; run Go beacon; appears in beacon list
- [ ] Dispatch echo command; result returned within 30s
- [ ] Kill WS proxy; beacon falls back to long-poll and completes task

### Playwright Tests
- [ ] Generate beacon dialog shows download links for win/linux builds
- [ ] New Go beacon appears in UI after first check-in
- [ ] Beacon profile sleep/jitter values visible in beacon detail
