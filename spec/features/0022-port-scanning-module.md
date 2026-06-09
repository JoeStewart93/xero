# F0022: Port Scanning Module

## Metadata
| Field | Value |
|---|---|
| ID | F0022 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 3 |
| Depends on | F0016 |

## Summary
Built-in TCP port scanning module for discovering open ports on target hosts within authorized lab scope, with configurable port ranges and concurrency. The C2 backend embedded scanner is the default execution target; external scanners, distributed execution, and beacon pivot execution are planned extensions.

## Requirements
- builtin.portscan module with target, ports, timeout, threads args
- Execution target defaults to `auto`, which uses the embedded C2 scanner until external scanner orchestration is available
- Specific external scanner, distributed scanner pool, and beacon pivot execution are owned by F0045-F0047
- Scan types: TCP connect scan for MVP
- Results structured as JSON array of host:port:state
- Rate limiting to avoid network flooding in lab environments
- Progress updates streamed via result chunks for large scans

## Stages

### Stage 1: Scan module backend
**Goal:** Register portscan in module registry with schema.
**Acceptance Criteria:**
- [ ] Module args: targets[], port_range, timeout_ms, max_threads
- [ ] Module args include execution_target default `auto`
- [ ] Validation limits port range to 65535 and max 10 targets
- [ ] Module metadata exposed in /api/v1/modules list

### Stage 2: Scanner executor
**Goal:** Embedded C2 scanner implements TCP connect scan.
**Acceptance Criteria:**
- [ ] Scanner worker pool respects max_threads
- [ ] Each probe records open/closed/filtered state
- [ ] Partial results streamed every 100 ports

### Stage 3: Result formatting
**Goal:** Normalize scan output for UI display.
**Acceptance Criteria:**
- [ ] Result JSON schema: [{host, port, state, latency_ms}]
- [ ] Open ports highlighted in result viewer
- [ ] Scan summary includes duration and ports scanned count

## Feature Acceptance Criteria

- [ ] Port scan of lab target returns accurate open port list
- [ ] Large /24 scan completes with progress updates in UI
- [ ] Scan respects max_threads without exhausting beacon resources

## Test Plan

### Unit Tests
- [ ] test_portscan_args_validation
- [ ] test_tcp_connect_detects_open_port_mock
- [ ] test_scan_rate_limiter
- [ ] test_result_json_schema
- [ ] test_progress_chunk_emission

### System / Integration Tests
- [ ] Dispatch portscan against lab host; results match nmap baseline
- [ ] Scan 1000 ports; progress chunks received before completion
- [ ] Invalid target returns error result without scanner crash

### Playwright Tests
- [ ] Module browser shows Port Scan with configurable args form and embedded scanner default
- [ ] Submit scan task; progress bar updates during execution
- [ ] Result table highlights open ports in green
