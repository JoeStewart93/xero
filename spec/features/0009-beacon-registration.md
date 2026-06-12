# F0009: Beacon Registration

## Metadata
| Field | Value |
|---|---|
| ID | F0009 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 2 |
| Depends on | F0004, F0005 |

## Summary
API, persistence, realtime, and initial UI workflow for beacon check-in. F0009 assigns stable beacon IDs, captures host metadata, stores hashed opaque registration token material, and exposes registered beacons in the operator Beacons overview.

## Current Implementation Notes
F0009 completes the beacon registration contract introduced during F0008. `POST /api/v1/beacons/register` is C2 API only, requires no operator JWT, validates and normalizes metadata, creates or updates one row per machine fingerprint, rotates an opaque per-beacon registration token on every successful registration, stores only a SHA-256 token hash, and returns the plaintext token only in that registration response. `GET /api/v1/beacons` and realtime event payloads never expose token material. The Beacons side tab is enabled when the UI is connected to C2 and opens `/beacons` with a dense overview/detail view. F0010 owns heartbeat/offline behavior, F0011 owns encrypted binary protocol key exchange and frame crypto, and later UI specs own richer management actions.

## Requirements
- FR-03: Persist beacon metadata in PostgreSQL
- Direct beacon-to-C2 embedded handler registration without external handler requirement
- Capture hostname, OS, architecture, internal/external IP, PID
- Idempotent re-registration for same machine fingerprint
- Return beacon ID, opaque registration token, and communication parameters on success

## Stages

### Stage 1: Registration schema
**Goal:** Define beacons table and Pydantic request/response models.
**Acceptance Criteria:**
- [x] beacons table stores id, hostname, os, arch, ips, first_seen, last_seen
- [x] beacons table stores hashed opaque token material and token issue time
- [x] Registration request schema validates required beacon metadata
- [x] Unique beacon_id assigned via UUID on first registration

### Stage 2: Registration endpoint
**Goal:** Implement POST /api/v1/beacons/register for beacon check-in.
**Acceptance Criteria:**
- [x] Valid registration creates or updates beacon record
- [x] Response includes beacon_id, opaque beacon_token, sleep, jitter defaults
- [x] Malformed payload returns 422 with field errors

### Stage 3: Fingerprint deduplication
**Goal:** Detect returning beacons by machine fingerprint hash.
**Acceptance Criteria:**
- [x] Same fingerprint updates existing record instead of duplicate
- [x] last_seen timestamp updated on each registration
- [x] Operator UI reflects updated metadata after re-registration

## Feature Acceptance Criteria

- [x] New beacon appears in database and API list after first check-in
- [x] Re-registration from same host updates record without duplicate entry
- [x] Registration endpoint documented in OpenAPI spec
- [x] Registration returns plaintext opaque token once and stores only token hash
- [x] Beacon list/detail UI renders registered metadata from C2

## Test Plan

### Unit Tests
- [x] test_register_new_beacon_creates_record
- [x] test_register_duplicate_fingerprint_updates_existing
- [x] test_register_invalid_payload_returns_422
- [x] test_beacon_model_serialization
- [x] test_registration_response_includes_comm_params
- [x] test_registration_response_returns_token_and_list_excludes_token_material
- [x] test_duplicate_fingerprint_rotates_token
- [x] test_register_invalid_ip_returns_422
- [x] test_alembic_upgrade_creates_token_columns

### System / Integration Tests
- [x] POST registration payload; GET /beacons returns new entry
- [x] Re-register same fingerprint; beacon count remains 1
- [x] Registration persists across backend restart
- [x] Re-registration emits status-change realtime event

### Playwright Tests
- [x] After simulated registration via API, beacon appears in Beacons list
- [x] Beacon detail panel shows hostname and OS from registration metadata
- [x] New beacon triggers dashboard active count increment via WebSocket
