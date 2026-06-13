# F0030: Asset Inventory

## Metadata
| Field | Value |
|---|---|
| ID | F0030 |
| Priority | P1 |
| Status | Complete |
| MVP Phase | 4 |
| Depends on | F0005, F0009, F0022, F0023 |
| Effort | 8 |

## Summary
Asset inventory system that aggregates beacon hosts, discovered network entities from scan results, and software metadata into a unified PostgreSQL asset model.

## Value
Gives operators a single inventory surface for controlled beacon hosts, scan-discovered hosts, and identified network services so later grouping, topology, reporting, and post-exploitation workflows have a stable data foundation.

## Scope Boundaries
- F0030 owns C2 asset persistence, beacon and F0022/F0023 scan ingestion, read APIs, and a basic `/assets` inventory UI.
- F0030 does not own automatic grouping rules, manual groups/tags, drag/drop assignment, duplicate merge workflows, topology visualization, or broad recon ingestion beyond port scan and service enumeration.
- F0071 remains the future broader recon-result ingestion and relationship expansion feature.

## Sample Use Cases
- A beacon registers and immediately appears as a `beacon_host` asset with beacon metadata and identifiers.
- A port scan discovers `10.10.0.25`, creating or updating a `discovered_host` asset without duplicating an existing host with that IP.
- Service enumeration identifies SSH on `10.10.0.25:22`, creating a service asset linked to the host and source scan job.
- An operator searches `/assets` by IP, hostname, or domain and opens a detail view showing source links.

## Assumptions
- Canonical API paths are `/api/v1/assets` and `/api/v1/assets/{id}`.
- MVP deduplication is global and based on beacon fingerprint for beacon hosts, normalized IP for discovered hosts, and host/protocol/port for services.
- The 200ms search acceptance criterion means server response time for filtered `GET /api/v1/assets` against 1000 seeded assets.
- The current module catalog UI will move from `/assets` to `/modules`, while `/assets` becomes the basic asset inventory screen required by this feature.

## Requirements
- assets table linked to beacons and discovered hosts
- Automatic asset creation on beacon registration
- Ingest scan results to create/update discovered assets
- Asset fields: hostname, ips, os, domain, role, first_seen, last_seen
- API: GET /api/v1/assets with pagination and filters

## Stages

### Stage 1: Asset schema
**Goal:** Define assets and asset_beacon_link tables.
**Dependencies:** F0005 PostgreSQL persistence.
**Effort:** 3
**Acceptance Criteria:**
- [x] assets table with type: beacon_host, discovered_host, service
- [x] Beacon registration auto-creates beacon_host asset
- [x] Scan results create discovered_host assets with dedup by IP

### Stage 2: Ingest pipeline
**Goal:** Process module results into asset records.
**Dependencies:** F0022 port scanning, F0023 service enumeration.
**Effort:** 3
**Acceptance Criteria:**
- [x] Port scan results add/update discovered assets
- [x] Service enum adds service metadata to assets
- [x] Duplicate IP merges into existing asset record

### Stage 3: Asset API
**Goal:** REST endpoints for asset list, detail, and search.
**Dependencies:** Stage 1 and Stage 2.
**Effort:** 1
**Acceptance Criteria:**
- [x] GET /api/v1/assets returns paginated asset list
- [x] GET /api/v1/assets/{id} returns full metadata and relationships
- [x] Search by IP, hostname, or domain substring

### Stage 4: Basic asset inventory UI
**Goal:** Replace the `/assets` module-catalog placeholder with a usable asset inventory surface.
**Dependencies:** Stage 3.
**Effort:** 1
**Acceptance Criteria:**
- [x] `/assets` lists beacon, discovered host, and service assets from C2
- [x] Search by IP, hostname, or domain filters the asset list
- [x] Asset detail shows linked beacon and scan/source history

## Feature Acceptance Criteria

- [x] Every registered beacon has corresponding asset record
- [x] Scan-discovered hosts appear as assets without duplicate IPs
- [x] Asset search returns results within 200ms for 1000 assets

## Test Plan

### Unit Tests
- [x] test_asset_created_on_beacon_register
- [x] test_scan_result_creates_discovered_asset
- [x] test_asset_dedup_by_ip
- [x] test_asset_api_pagination
- [x] test_asset_search_hostname

### System / Integration Tests
- [x] Register beacon; asset count increments by 1
- [x] Run port scan; discovered hosts appear in asset list
- [x] Asset detail links back to originating beacon or scan task

### Playwright Tests
- [x] Assets page lists beacon hosts and discovered hosts
- [x] Search assets by IP filters list correctly
- [x] Asset detail shows linked beacon and scan history

## Validation Evidence
- `python -m pytest platform/tests/unit/test_c2_api.py -k "asset or portscan_job_scans_loopback_and_records_chunks or serviceenum_job_records_results_and_chunks" platform/tests/unit/test_persistence_split.py -k "c2"`
- `python platform/scripts/ci.py backend-unit`
- `python platform/scripts/ci.py openapi-check`
- `python platform/scripts/ci.py frontend-lint`
- `python platform/scripts/ci.py frontend-build`
- `python platform/scripts/ci.py frontend-test`
- `npm --prefix platform/frontend run test:e2e -- e2e/f0030-asset-inventory.spec.ts`
- Docker C2 and BFF/frontend stacks rebuilt and restarted with C2 `artifact_store` readiness healthy.

## Maintainability Review
- Asset creation, deduplication, scan ingestion, and API serialization live in `xero_c2/assets.py` instead of being embedded in route handlers or scanner modules.
- `main.py` remains responsible for route registration and lifecycle hooks only; scanner modules continue to own probe execution.
- Module catalog UI was preserved under `/modules`, keeping `/assets` focused on inventory without removing the existing operator workflow.
- No follow-up refactor round is required for F0030; advanced grouping, merge, topology, and relationship UX remain properly deferred to later features.
