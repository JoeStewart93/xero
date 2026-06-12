# F0039: Handler Tunnel to C2 Backend

## Metadata
| Field | Value |
|---|---|
| ID | F0039 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 5 |
| Depends on | F0038, F0049 |

## Summary
Encrypted outbound tunnel from external connection handlers to the Xero C2 backend with certificate pinning, bidirectional frame relay, handler registration, heartbeat, and routing metadata.

## Implementation Note
F0049 provides shared infrastructure worker identity, one-time handler pairing, handler heartbeat, Settings > Infrastructure inventory, and local scaffold provisioning. F0039 remains planned for the encrypted handler-C2 tunnel, beacon frame relay, certificate pinning, handler draining semantics, and beacon routing through external handlers.

## Requirements
- FR-11: Outbound encrypted tunnel from handler to C2
- SR-03: Certificate pinning verifies C2 identity
- Handler pairs/registers with C2 through the F0049 worker control plane; tunnel startup still sends HANDLER_REGISTER metadata
- Tunnel uses TLS 1.3 with pinned C2 certificate fingerprint
- C2 routes beacon traffic to/from correct handler
- Handler heartbeat includes health, capacity, connected beacon count, and draining state

## Stages

### Stage 1: Tunnel protocol
**Goal:** Define handler-C2 tunnel message types.
**Acceptance Criteria:**
- [ ] HANDLER_REGISTER, HANDLER_HEARTBEAT, FRAME_RELAY, HANDLER_DRAINING message types
- [ ] Tunnel encrypted with TLS 1.3 and cert pinning
- [x] Handler worker ID assigned by C2 on F0049 registration
- [ ] Tunnel session ID assigned by C2 on HANDLER_REGISTER

### Stage 2: C2 handler manager
**Goal:** Backend tracks connected handlers and routes frames.
**Acceptance Criteria:**
- [x] Shared `infrastructure_workers` table stores handler id, endpoint, status, capacity, and last_seen through F0049
- [ ] Tunnel metadata stores connected_at, connected beacon counts, and relay state
- [ ] FRAME_RELAY routes to beacon via handler or direct path
- [ ] Handler disconnect marks associated beacons for reassignment by F0109

### Stage 3: Certificate pinning
**Goal:** Pin C2 cert fingerprint in handler config.
**Acceptance Criteria:**
- [ ] Handler refuses connection if C2 cert fingerprint mismatch
- [ ] Pin configurable via handler config file
- [ ] Pin mismatch logged as security event

## Feature Acceptance Criteria

- [ ] Handler establishes pinned tunnel to C2 within 10s of startup
- [ ] Beacon frame relayed through handler arrives at C2 identically
- [ ] Cert pin mismatch blocks tunnel with clear handler log error

## Test Plan

### Unit Tests
- [x] test_handler_worker_pairing_registration
- [ ] test_handler_register_message
- [ ] test_cert_pin_match_allows_connection
- [ ] test_cert_pin_mismatch_rejects
- [ ] test_frame_relay_routing
- [ ] test_handler_disconnect_updates_status

### System / Integration Tests
- [ ] Handler tunnels to C2; beacon task completes end-to-end
- [ ] Wrong pin config; handler fails to connect; logged error
- [x] C2 shows handler online in shared infrastructure worker registry API after F0049 registration
- [ ] C2 shows handler tunnel connected after tunnel establishment

### Playwright Tests
- [ ] Settings shows handler tunnel status Connected
- [x] Infrastructure lists handler worker inventory after F0049
- [ ] Handler list displays tunnel uptime
- [ ] Cert pin mismatch shows security alert in settings
