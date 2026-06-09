# F0038: Connection Handler Binary

## Metadata
| Field | Value |
|---|---|
| ID | F0038 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 5 |
| Depends on | F0011 |

## Summary
Go external beacon handler binary under `platform/handlers/go/` that accepts beacon traffic on the edge and forwards frames to the Xero C2 backend. The C2 backend remains the embedded/default handler; this feature adds dedicated handler nodes for distributed connection management.

## Requirements
- FR-10: Handlers deployable as standalone Linux/Windows binaries
- FR-15: mTLS authentication between beacons and handlers
- Handler listens on configurable port for beacon connections
- Forwards decoded frames to C2 via outbound tunnel (F0039)
- Handler reports identity, version, capacity, and connected beacon count
- Memory footprint target under 50MB

## Stages

### Stage 1: Handler scaffold
**Goal:** Go module with listener, handler identity, and config.
**Acceptance Criteria:**
- [ ] `platform/handlers/go/` builds standalone binary
- [ ] Config: listen_addr, c2_url, handler_name, mtls cert paths
- [ ] Handler exposes version and capacity metadata for registration
- [ ] Graceful shutdown and connection draining

### Stage 2: Beacon-facing listener
**Goal:** Accept beacon WS/long-poll on handler.
**Acceptance Criteria:**
- [ ] Handler exposes same beacon transport endpoints as embedded C2 handler
- [ ] mTLS required for beacon connections
- [ ] Per-beacon connection tracking includes beacon id, transport, connected_at, and last_seen

### Stage 3: Frame relay
**Goal:** Forward beacon frames to C2 tunnel interface.
**Acceptance Criteria:**
- [ ] Incoming beacon frames queued for tunnel transmission
- [ ] C2-originated frames routed to correct beacon connection
- [ ] Handler reports connection count and draining state to C2 heartbeat

## Feature Acceptance Criteria

- [ ] Handler binary runs on lab VM and accepts beacon connections
- [ ] Beacon connects to external handler instead of embedded C2 handler successfully
- [ ] Handler memory usage stays under 50MB with 10 beacons

## Test Plan

### Unit Tests
- [ ] test_handler_config_parse
- [ ] test_mtls_beacon_auth_required
- [ ] test_frame_relay_enqueue
- [ ] test_beacon_routing_by_id
- [ ] test_graceful_shutdown_drains_connections

### System / Integration Tests
- [ ] Start handler; point beacon at handler; registration succeeds via tunnel
- [ ] 10 beacons through handler; all heartbeats reach C2
- [ ] Handler restart; beacons reconnect within 2 sleep cycles

### Playwright Tests
- [ ] Settings handlers page shows handler binary download links
- [ ] Handler status card shows connected beacon count
- [ ] Register handler instance; appears in handler list
