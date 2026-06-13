# F0031: Automatic Asset Grouping

## Metadata
| Field | Value |
|---|---|
| ID | F0031 |
| Priority | P1 |
| Status | Complete |
| MVP Phase | 4 |
| Depends on | F0030 |

## Summary
Rules engine that automatically assigns assets to groups based on network topology, domain membership, OS version, installed services, and geographic IP location.

Implementation scope completed for the approved F0031 slice: subnet, AD domain, explicit workgroup metadata, and OS family/version grouping. Architecture, geo, and installed-service grouping remain deferred for later grouping expansion work.

## Requirements
- Auto-groups: by subnet, domain, OS, architecture, geo country
- Grouping rules run on asset create/update events
- asset_groups and asset_group_membership tables
- Rules configurable via API with enable/disable per rule
- Re-run grouping job for all assets on rule change

## Stages

### Stage 1: Grouping engine
**Goal:** Implement rule evaluator triggered on asset events.
**Acceptance Criteria:**
- [x] Subnet rule groups assets by /24 network prefix
- [x] Domain rule groups by AD domain or workgroup
- [x] OS rule groups by os_family and os_version major

### Stage 2: Rule configuration
**Goal:** API and seed data for default grouping rules.
**Acceptance Criteria:**
- [x] GET/PUT /api/v1/grouping/rules for rule management
- [x] Default rules enabled for subnet, domain, OS on install
- [x] Manual re-group POST /api/v1/grouping/rerun

### Stage 3: Membership sync
**Goal:** Maintain asset_group_membership without duplicates.
**Acceptance Criteria:**
- [x] Asset can belong to multiple auto-groups
- [x] Rule disable removes future assignments; optional purge
- [x] Grouping events logged for audit

## Feature Acceptance Criteria

- [x] Assets in same /24 subnet auto-assigned to subnet group
- [x] Domain-joined assets grouped separately from workgroup hosts
- [x] Rule change triggers re-group within 60s for all assets

## Test Plan

### Unit Tests
- [x] test_subnet_grouping_rule
- [x] test_domain_grouping_rule
- [x] test_os_version_grouping_rule
- [x] test_multi_group_membership
- [x] test_rule_disable_stops_new_assignments
- [x] test_subnet_rule_prefix_change_reruns_memberships

### System / Integration Tests
- [x] Create assets in same subnet; both appear in subnet group
- [x] Change subnet rule prefix length; memberships update on rerun
- [x] Disable OS rule; new assets not added to OS groups

### Playwright Tests
- [x] Asset groups panel shows auto-generated subnet groups
- [x] Group membership count matches assets in that subnet
- [x] Settings grouping rules page shows enabled/disabled toggles

## Validation Evidence

- [x] `python -m pytest platform/tests/unit/test_c2_api.py -k "grouping or asset" platform/tests/unit/test_persistence_split.py -k "c2 or crud"`: 111 passed, 3 deselected.
- [x] `python -m ruff check` on all F0031 backend, migration, and touched backend test files: passed.
- [x] `python platform/scripts/openapi.py export c2` and `python platform/scripts/ci.py openapi-check`: passed.
- [x] `npm --prefix platform/frontend run test -- src/api.test.ts src/pages/InventoryPage.test.tsx src/pages/GroupingRulesPage.test.tsx`: 26 tests passed.
- [x] `python platform/scripts/ci.py frontend-lint`: passed.
- [x] `python platform/scripts/ci.py frontend-build`: passed.
- [x] `python platform/scripts/ci.py backend-unit`: 137 tests passed.
- [x] `python platform/scripts/ci.py frontend-test`: 117 tests passed.
- [x] `docker compose -f platform/docker-compose.c2.yml up -d --build --force-recreate`: rebuilt and restarted C2 stack.
- [x] `docker compose -f platform/docker-compose.bff.yml up -d --build --force-recreate`: rebuilt and restarted BFF/frontend stack.
- [x] `curl.exe -s http://localhost:8001/ready`: ready with Postgres, Redis, and artifact store healthy.
- [x] `curl.exe -s http://localhost:8000/ready`: ready with Postgres and Redis healthy.
- [x] `curl.exe -I http://localhost:3000/assets`: HTTP 200 after rebuild.
- [x] `PLAYWRIGHT_BASE_URL=http://localhost:3000 PLAYWRIGHT_C2_BASE_URL=http://localhost:8001 C2_CONNECT_PASSWORD=c2_password npm --prefix platform/frontend run test:e2e -- e2e/f0031-automatic-asset-grouping.spec.ts`: live C2 e2e passed.
- [x] Browser sanity: app connected to C2, auto-group rail rendered, subnet filter showed live beacon assets, selected asset detail showed subnet group membership, grouping settings rendered, and no horizontal overflow on Assets or Grouping settings.
- [x] F0031 live-test assets, beacons, memberships, events, and empty sample groups cleaned from the local C2 database after validation.

## Maintainability Review

- [x] Grouping behavior is isolated in `xero_c2/asset_grouping.py`; asset ingestion and API route files call the service without owning rule logic.
- [x] Persistence is extensible for F0032-style hierarchy work through `asset_groups.type` and `parent_id`, while current automatic groups remain type `auto`.
- [x] Frontend grouping controls live in a dedicated settings page and the inventory page only consumes group summaries and filters.
- [x] No focused refactor round required before merge; existing shared boundaries remain clear.

## Known Notes

- Repository-wide `python platform/scripts/ci.py backend-lint` currently reports unrelated pre-existing Ruff issues in older migration/dashboard/portscan/serviceenum files. All F0031 backend files pass targeted Ruff checks.
