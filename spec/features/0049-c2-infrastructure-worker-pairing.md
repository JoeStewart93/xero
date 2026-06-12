# F0049: C2 Infrastructure Worker Pairing

## Metadata
| Field | Value |
|---|---|
| ID | F0049 |
| Priority | P1 |
| Status | Complete |
| MVP Phase | 5 |
| Depends on | F0008, F0010, F0048 |

## Summary
Add the C2 control-plane workflow for infrastructure workers: embedded C2 handler/scanner identities, one-time pairing tokens for external beacon handlers and scanners, worker registration/heartbeat, stale/offline tracking, C2-managed local worker launch/stop, and a Settings subpage for operators to manage the worker inventory.

This feature does not implement handler traffic tunnels, beacon frame relay, scanner job execution, distributed scan orchestration, or pivot scanning.

## Requirements
- C2 exposes embedded beacon-handler and scanner identities by default.
- Operators can create one-time pairing tokens for external handler/scanner nodes after connecting to C2.
- External worker scaffolds can register with C2, receive opaque worker tokens, and heartbeat status/capacity/capabilities.
- C2 tracks worker status, last heartbeat, capacity, load, capabilities, and event history without exposing token hashes.
- Operators can launch and stop C2-managed handler/scanner scaffold containers from Settings > Infrastructure when local provisioning is enabled.
- Infrastructure includes worker inventory sections for beacon handlers and scanners.

## Stages

### Stage 1: C2 worker persistence
**Goal:** Store shared infrastructure worker identities and events under the C2 service boundary.
**Acceptance Criteria:**
- [x] C2 migration creates `infrastructure_workers`, `worker_pairing_tokens`, and `worker_events`.
- [x] Embedded handler and scanner records are seeded by C2 startup/listing.
- [x] Worker token hashes and pairing token hashes are never returned by list/detail responses.
- [x] C2 OpenAPI documents the worker control-plane schemas.

### Stage 2: Pairing and heartbeat APIs
**Goal:** Allow workers to join C2 and maintain liveness.
**Acceptance Criteria:**
- [x] `POST /api/v1/infrastructure/pairing-tokens` creates one-time pairing tokens for handlers or scanners.
- [x] `POST /api/v1/infrastructure/workers/register` validates pairing tokens, stores a worker token hash, and returns plaintext worker token once.
- [x] `POST /api/v1/infrastructure/workers/{worker_id}/heartbeat` validates worker bearer tokens and updates status/load/capabilities.
- [x] C2 stale worker monitor marks overdue non-embedded workers offline/failed and records events.
- [x] Worker realtime events are published for registration, heartbeat, status change, launch, and stop events.

### Stage 3: Local provisioning bridge
**Goal:** Let C2 start or stop local scaffold workers when explicitly enabled.
**Acceptance Criteria:**
- [x] `POST /api/v1/infrastructure/workers/launch` creates a C2-managed worker, issues a pairing token, and starts the matching compose service.
- [x] `POST /api/v1/infrastructure/workers/{worker_id}/stop` stops only C2-managed workers.
- [x] Local provisioning is guarded by `C2_LOCAL_PROVISIONING_ENABLED`.
- [x] Compose configuration provides C2 with the Docker socket and read-only platform workspace mount for local development.

### Stage 4: Operator UI workflow
**Goal:** Add an Infrastructure subpage for worker pairing and provisioning.
**Acceptance Criteria:**
- [x] Stitch MCP was used first for the C2 worker settings UI brief.
- [x] `/settings/infrastructure` is available only after local login and C2 connection; `/settings/c2` redirects there for compatibility.
- [x] Infrastructure shows handler and scanner inventory with status, origin, endpoint, load/capacity, heartbeat, port, and capabilities.
- [x] Operators can generate external pairing commands from the UI.
- [x] Operators can request C2-managed launch/stop from the UI.

## Feature Acceptance Criteria

- [x] Embedded C2 handler and scanner appear in C2 worker inventory.
- [x] External scanner/handler pairing tokens are one-time and token material is returned only in the create/register responses.
- [x] Worker heartbeat updates online status, load, capabilities, and last seen.
- [x] Stale workers are marked offline/failed without deleting history.
- [x] Settings has an Infrastructure subtab with scanner and beacon-handler sections.
- [x] Handler tunnel, scan execution, distributed scanning, and pivot features remain planned and out of scope.

## Test Plan

### Unit Tests
- [x] C2 worker list seeds embedded handler/scanner records.
- [x] Pairing/register/heartbeat flow persists token hashes and keeps list responses token-free.
- [x] Duplicate/reused pairing tokens are rejected.
- [x] Worker stale detector marks external workers offline and records `worker_events`.
- [x] Local provisioning disabled returns a controlled error.
- [x] Successful launch records a C2-managed worker.
- [x] Frontend API client sends worker pairing/launch requests with C2 bearer auth.
- [x] Infrastructure page renders disconnected, inventory, pairing, launch, and stop states.

### System / Integration Tests
- [x] Compose contract tests include worker env, volumes, provisioning variables, and healthchecks.
- [x] C2 compose integration lists embedded workers, creates a scanner pairing token, registers an external scanner, heartbeats it, and confirms list responses remain token-free.

### Playwright Tests
- [x] Infrastructure route shows embedded handler/scanner records after login and C2 connection.
- [x] Operator can create an external scanner pairing token and see the startup command.

## Follow-up (F0074)

- Infrastructure worker endpoints require C2 operator JWT instead of anonymous connect tokens.
- Role-based restrictions on pairing/launch/stop land in F0105; F0074 establishes operator identity on all worker control-plane routes.
