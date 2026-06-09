# F0023: Service Enumeration Module

## Metadata
| Field | Value |
|---|---|
| ID | F0023 |
| Priority | P0 |
| Status | Planned |
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

## Stages

### Stage 1: Enum module schema
**Goal:** Define serviceenum args and result format.
**Acceptance Criteria:**
- [ ] Args: host, ports[], probe_timeout_ms
- [ ] Result: [{port, service_guess, banner, tls_cn, tls_expiry}]
- [ ] Module listed as follow-up suggestion after portscan

### Stage 2: Scanner probes
**Goal:** Implement banner grab and TLS inspection in scanner execution.
**Acceptance Criteria:**
- [ ] HTTP probe sends HEAD request and captures Server header
- [ ] TLS probe extracts CN, issuer, expiry from certificate
- [ ] Timeout per probe prevents hung connections

### Stage 3: UI integration
**Goal:** Display enumeration results linked to scan results.
**Acceptance Criteria:**
- [ ] Run service enum from port scan result context menu
- [ ] Service guess shown with confidence indicator
- [ ] TLS expiry warnings highlighted in amber

## Feature Acceptance Criteria

- [ ] Service enum on lab HTTPS port returns correct certificate CN
- [ ] SSH port returns SSH banner string
- [ ] Enum completes within 30s for 20 open ports

## Test Plan

### Unit Tests
- [ ] test_serviceenum_args_validation
- [ ] test_http_banner_grab_mock
- [ ] test_tls_cert_parse
- [ ] test_fingerprint_match_ssh
- [ ] test_probe_timeout

### System / Integration Tests
- [ ] Port scan then service enum pipeline on lab host
- [ ] HTTPS probe returns valid certificate metadata
- [ ] Closed port skipped without scanner error

### Playwright Tests
- [ ] Context menu on port scan results offers Run Service Enum
- [ ] Service enum results show banners and TLS details
- [ ] TLS expiry warning badge shown for expiring certificates
