# F0030: Asset Inventory

## Metadata
| Field | Value |
|---|---|
| ID | F0030 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 4 |
| Depends on | F0005, F0009 |

## Summary
Asset inventory system that aggregates beacon hosts, discovered network entities from scan results, and software metadata into a unified PostgreSQL asset model.

## Requirements
- assets table linked to beacons and discovered hosts
- Automatic asset creation on beacon registration
- Ingest scan results to create/update discovered assets
- Asset fields: hostname, ips, os, domain, role, first_seen, last_seen
- API: GET /api/v1/assets with pagination and filters

## Stages

### Stage 1: Asset schema
**Goal:** Define assets and asset_beacon_link tables.
**Acceptance Criteria:**
- [ ] assets table with type: beacon_host, discovered_host, service
- [ ] Beacon registration auto-creates beacon_host asset
- [ ] Scan results create discovered_host assets with dedup by IP

### Stage 2: Ingest pipeline
**Goal:** Process module results into asset records.
**Acceptance Criteria:**
- [ ] Port scan results add/update discovered assets
- [ ] Service enum adds service metadata to assets
- [ ] Duplicate IP merges into existing asset record

### Stage 3: Asset API
**Goal:** REST endpoints for asset list, detail, and search.
**Acceptance Criteria:**
- [ ] GET /assets returns paginated asset list
- [ ] GET /assets/{id} returns full metadata and relationships
- [ ] Search by IP, hostname, or domain substring

## Feature Acceptance Criteria

- [ ] Every registered beacon has corresponding asset record
- [ ] Scan-discovered hosts appear as assets without duplicate IPs
- [ ] Asset search returns results within 200ms for 1000 assets

## Test Plan

### Unit Tests
- [ ] test_asset_created_on_beacon_register
- [ ] test_scan_result_creates_discovered_asset
- [ ] test_asset_dedup_by_ip
- [ ] test_asset_api_pagination
- [ ] test_asset_search_hostname

### System / Integration Tests
- [ ] Register beacon; asset count increments by 1
- [ ] Run port scan; discovered hosts appear in asset list
- [ ] Asset detail links back to originating beacon or scan task

### Playwright Tests
- [ ] Assets page lists beacon hosts and discovered hosts
- [ ] Search assets by IP filters list correctly
- [ ] Asset detail shows linked beacon and scan history
