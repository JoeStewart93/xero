# F0022: Port Scanning Module

## Metadata
| Field | Value |
|---|---|
| ID | F0022 |
| Priority | P0 |
| Status | Complete |
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
- Progress updates streamed via dedicated scan result chunks for large scans

## Approved Implementation Scope
- F0022 introduces scanner-specific `scan_jobs` persistence and does not make beacon `tasks` nullable or scanner-aware.
- Public module id is `builtin.portscan`; `execution_target` is accepted only as `auto` for this feature.
- `auto` resolves to the embedded C2 scanner. External scanner selection, distributed pools, and beacon pivot execution remain owned by F0045-F0047 and F0046.
- Scan progress uses dedicated scan chunks and `scan.*` realtime events, not task stdout/stderr result chunks.
- Until backend project scope exists, the embedded scanner accepts loopback/private/link-local lab targets and rejects public targets by default.
- For MVP TCP connect scans, `open` means connect succeeds, `closed` means the connection is actively refused/reset, and `filtered` means timeout or ambiguous network reachability failure.

## Stages

### Stage 1: Scan module backend
**Goal:** Register portscan in module registry with schema.
**Acceptance Criteria:**
- [x] Module args: targets[], port_range, timeout_ms, max_threads
- [x] Module args include execution_target default `auto`
- [x] Validation limits port range to 65535 and max 10 targets
- [x] Module metadata exposed in /api/v1/modules list

### Stage 2: Scanner executor
**Goal:** Embedded C2 scanner implements TCP connect scan.
**Acceptance Criteria:**
- [x] Scanner worker pool respects max_threads
- [x] Each probe records open/closed/filtered state
- [x] Partial results streamed every 100 ports

### Stage 3: Result formatting
**Goal:** Normalize scan output for UI display.
**Acceptance Criteria:**
- [x] Result JSON schema: [{host, port, state, latency_ms}]
- [x] Open ports highlighted in result viewer
- [x] Scan summary includes duration and ports scanned count

## Feature Acceptance Criteria

- [x] Port scan of lab target returns accurate open port list
- [x] Large /24 scan completes with progress updates in UI
- [x] Scan respects max_threads without exhausting beacon resources

## Test Plan

### Unit Tests
- [x] test_portscan_args_validation
- [x] test_tcp_connect_detects_open_port_mock
- [x] test_scan_rate_limiter
- [x] test_result_json_schema
- [x] test_progress_chunk_emission

### System / Integration Tests
- [x] Dispatch portscan against lab host; results match nmap baseline
- [x] Scan 1000 ports; progress chunks received before completion
- [x] Invalid target returns error result without scanner crash

### Playwright Tests
- [x] Module browser shows Port Scan with configurable args form and embedded scanner default
- [x] Submit scan task; progress bar updates during execution
- [x] Result table highlights open ports in green

## Completion Notes
- Completed on 2026-06-13 in `codex/F0022-port-scanning-module`.
- C2 API now exposes `/api/v1/modules`, `/api/v1/scan-jobs`, and scan chunk retrieval; OpenAPI spec updated in `platform/docs/api/c2.openapi.yaml`.
- Embedded scanner persists `scan_jobs` and `scan_result_chunks`, resolves `execution_target=auto` to `embedded-c2`, rejects public targets by default, and marks interrupted scans failed on C2 restart.
- Recon UI now provides a connected C2 port scan runner, live job list, progress bar, summary metrics, and highlighted open-result rows.
- Validation evidence:
  - `python -m pytest platform/tests/unit/test_c2_api.py platform/tests/unit/test_persistence_split.py -q` -> 84 passed.
  - `python platform/scripts/openapi.py check c2` -> passed.
  - `npm --prefix platform/frontend run lint` -> passed.
  - `npm --prefix platform/frontend run build` -> passed.
  - Rebuilt/recreated C2 and BFF/frontend stacks with Docker Compose; `/ready` reported postgres, redis, and artifact_store healthy.
  - Connected Playwright C2 test `npm run test:e2e -- --project=chromium e2e/f0022-portscan.spec.ts` -> passed.
  - Live `/24` scan against `127.0.0.0/24` completed 254 probes with 3 progress chunks and a summary chunk.
  - nmap host baseline for exposed C2 service: `127.0.0.1:8001` open and `127.0.0.1:65534` closed.

## Maintainability Review
- No follow-up refactor round required for F0022.
- Scan module registry, scan execution, scan persistence serialization, and HTTP route wiring are separated into focused backend modules rather than embedding scanner behavior into beacon task/result paths.
- Recon UI remains page-local with typed API client helpers; future F0045-F0047 execution-target work can extend the module schema and scan-job resolver without changing beacon task contracts.
