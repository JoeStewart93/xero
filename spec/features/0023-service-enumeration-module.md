# F0023: Service Enumeration Module

## Metadata
| Field | Value |
|---|---|
| ID | F0023 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 3 |
| Depends on | F0022 |

## Summary
Built-in module that probes open ports identified by port scanning to determine service banners, TLS certificates, and common service fingerprints. It runs on the same scanner execution model as port scanning: embedded C2 scanner by default, with external/distributed/pivot execution owned by scanner infrastructure features.

## Requirements
- builtin.serviceenum module takes host and open_ports list
- Banner grabbing for TCP services (HTTP, SSH, FTP, SMTP)
- TLS certificate extraction for HTTPS ports
- Common service fingerprint database for 50+ services
- Chains naturally after port scan results in task workflow
- Execution target inherits from the parent scan or defaults to embedded C2 scanner

## Approved Implementation Scope
- F0023 introduces `builtin.serviceenum` as a second scanner module on the existing F0022 `scan_jobs` and `scan_result_chunks` path.
- The existing `/api/v1/scan-jobs` API, `scan.*` realtime events, and scan chunk persistence remain the execution surface; no beacon task/result path is introduced.
- `execution_target=auto` is the only accepted execution target for this feature and resolves to the embedded C2 scanner.
- External scanner selection, distributed scan orchestration, and beacon pivot execution remain owned by later scanner infrastructure features.
- F0023 accepts a single `host` plus `ports[]` for MVP. UI follow-up actions derive those args from open F0022 port scan rows.
- Manual backend invocation is allowed, but the primary operator workflow is launching service enumeration from open port scan results.
- F0022 lab-scope restrictions continue to apply: loopback/private/link-local hosts are allowed and public targets are rejected by default.
- Results use a canonical service finding shape: `{host, port, transport, status, service_guess, confidence, banner, tls, evidence, latency_ms, error}`.
- TLS expiry warnings are amber when a certificate expires within 30 days; expired certificates use critical styling where surfaced.
- The MVP fingerprint registry covers at least 50 service names through data-driven port/banner/header/TLS hints, but active probes remain shallow: passive banner read, HTTP `HEAD`, and TLS certificate metadata.
- Normalized asset/service inventory persistence is deferred to later asset inventory and reporting features; F0023 keeps findings in scan job JSON/chunks.

## Stages

### Stage 1: Enum module schema
**Goal:** Define serviceenum args and result format.
**Acceptance Criteria:**
- [x] Args: host, ports[], probe_timeout_ms
- [x] Result: [{port, service_guess, banner, tls_cn, tls_expiry}]
- [x] Module listed as follow-up suggestion after portscan

### Stage 2: Scanner probes
**Goal:** Implement banner grab and TLS inspection in scanner execution.
**Acceptance Criteria:**
- [x] HTTP probe sends HEAD request and captures Server header
- [x] TLS probe extracts CN, issuer, expiry from certificate
- [x] Timeout per probe prevents hung connections

### Stage 3: UI integration
**Goal:** Display enumeration results linked to scan results.
**Acceptance Criteria:**
- [x] Run service enum from port scan result context menu
- [x] Service guess shown with confidence indicator
- [x] TLS expiry warnings highlighted in amber

## Feature Acceptance Criteria

- [x] Service enum on lab HTTPS port returns correct certificate CN
- [x] SSH port returns SSH banner string
- [x] Enum completes within 30s for 20 open ports

## Test Plan

### Unit Tests
- [x] test_serviceenum_args_validation
- [x] test_http_banner_grab_mock
- [x] test_tls_cert_parse
- [x] test_fingerprint_match_ssh
- [x] test_probe_timeout

### System / Integration Tests
- [x] Port scan then service enum pipeline on lab host
- [x] HTTPS probe returns valid certificate metadata
- [x] Closed port skipped without scanner error

### Playwright Tests
- [x] Context menu on port scan results offers Run Service Enum
- [x] Service enum results show banners and TLS details
- [x] TLS expiry warning badge shown for expiring certificates

## Completion Notes
- Completed on 2026-06-13 in `codex/F0023-service-enumeration-module`.
- C2 scan jobs now dispatch by module id, with `builtin.portscan` and `builtin.serviceenum` sharing the same scan-job lifecycle, chunks, and `scan.*` realtime events.
- `builtin.serviceenum` validates single lab-scope hosts, bounded port lists, `execution_target=auto`, and optional source scan job lineage in args.
- Service enumeration performs shallow TCP service probing: open-port confirmation, passive banner read, HTTP `HEAD`, TLS certificate metadata extraction, and data-driven fingerprint matching for 50+ common service names.
- Recon UI now offers an `Enum` row action for open port scan rows and renders service enum results with service guess, confidence, evidence/banner, TLS CN/issuer/expiry, and amber expiry warning state.
- The UI acceptance references a context menu; implementation uses a visible row action button in the result table for a clearer operational workflow in the current Recon layout.
- Validation evidence:
  - `python -m pytest platform/tests/unit/test_c2_api.py platform/tests/unit/test_persistence_split.py -q` -> 90 passed.
  - `python platform/scripts/openapi.py check c2` -> passed.
  - `npm --prefix platform/frontend run lint` -> passed.
  - `npm --prefix platform/frontend run build` -> passed.
  - `npm --prefix platform/frontend test -- --run src/api.test.ts src/pages/ReconPage.test.tsx` -> 17 passed.
  - Rebuilt/recreated C2 and BFF/frontend stacks with Docker Compose; `/ready` reported postgres, redis, and artifact_store healthy.
  - Connected Playwright C2 tests `e2e/f0022-portscan.spec.ts` and `e2e/f0023-serviceenum.spec.ts` -> 2 passed.

## Maintainability Review
- No additional refactor round is required after F0023.
- The implementation moved generic scan-job orchestration into a shared backend module so future scanner modules can plug in without growing `portscan.py` or duplicating job/chunk/realtime lifecycle code.
- Service fingerprinting and network probe behavior are isolated in `serviceenum.py`, keeping scanner module logic separate from API route wiring and persistence serialization.
- Frontend API helpers are now module-aware while preserving the existing portscan call shape; Recon rendering branches by module without creating a separate page or parallel state model.
