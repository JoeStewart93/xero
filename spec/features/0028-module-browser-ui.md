# F0028: Inventory / Module Browser UI

## Metadata
| Field | Value |
|---|---|
| ID | F0028 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 3 |
| Depends on | F0024, F0022 |

## Summary
Inventory tab surface for exploit, payload, and post-exploitation module inventory. Includes a module catalog browser showing built-in and plugin modules with descriptions, argument schemas, usage examples, and one-click task creation pre-filled with module args.

## Requirements
- Inventory page listing built-in and plugin modules
- Module detail: description, args schema, example task JSON
- Category filters: exploits, payloads, post-exploitation, scanning, enumeration, utility, plugin
- Launch task button pre-fills task creation form
- Module version and author metadata display

## Current Implementation Note
Inventory is implemented as the Assets section landing page at `/assets`. The legacy `/inventory` route redirects to `/assets` for compatibility.

## Stages

### Stage 1: Module catalog
**Goal:** Fetch and display module registry from API.
**Acceptance Criteria:**
- [x] Inventory route at `/assets` is enabled once C2 connection prerequisites are satisfied
- [x] Legacy `/inventory` redirects to `/assets`
- [x] GET /api/v1/modules returns name, category, description, schema, source, author, version, status, and tags
- [x] Card grid layout with category badges
- [x] Search by module name or description

### Stage 2: Module detail
**Goal:** Detail view with schema and examples.
**Acceptance Criteria:**
- [x] Args schema rendered as documented parameter table
- [x] Example task JSON copyable to clipboard
- [x] Launch Task navigates to compatible task form with module args pre-filled

### Stage 3: Plugin modules
**Goal:** Distinguish builtin vs plugin module sources.
**Acceptance Criteria:**
- [x] Plugin modules show source, author, version, and updated metadata badges when present
- [x] Disabled plugins are grayed out with reason tooltip and disabled launch action
- [x] Hot-reload metadata can be surfaced through `updated_at` when plugin registration lands in F0043

## Feature Acceptance Criteria

- [x] All builtin modules visible with accurate arg documentation
- [x] Launch Task from portscan module opens pre-filled Recon form
- [x] Plugin-shaped modules render with plugin metadata, disabled state, and update metadata; live plugin registration remains owned by F0043

## Test Plan

### Unit Tests
- [x] test_module_list_renders_cards
- [x] test_module_detail_renders_schema_table
- [x] test_launch_task_prefills_form
- [x] test_category_filter
- [x] test_plugin_badge_rendered

### System / Integration Tests
- [x] Modules API list matches UI catalog count
- [x] Launch from module produces valid encoded handoff args for Recon and Beacons task forms
- [x] Plugin-shaped API payload appears in module list after refresh; live plugin registration remains owned by F0043

### Playwright Tests
- [x] Inventory page lists Port Scan and Service Enum cards
- [x] Open module detail shows args schema and example JSON
- [x] Launch Task button opens compatible task form with module selected

## Completion Evidence
- `npm --prefix frontend test -- --run src/pages/InventoryPage.test.tsx src/pages/ReconPage.test.tsx src/pages/BeaconsPage.test.tsx`
- `python scripts/ci.py frontend-lint`
- `python scripts/ci.py frontend-test`
- `python scripts/ci.py frontend-build`
- `python scripts/ci.py openapi-check`
- `python scripts/ci.py backend-unit`
- `python -m ruff check services/c2-api/xero_c2/modules.py services/c2-api/xero_c2/schemas.py tests/unit/test_c2_api.py`
- `python -m pytest tests/unit/test_c2_api.py -k "module_registry"`
- C2 API and frontend images rebuilt with `docker compose ... build --no-cache`, containers recreated, and readiness verified on `http://localhost:8000/ready`, `http://localhost:8001/ready`, and `http://localhost:3000/assets`.
- `PLAYWRIGHT_BASE_URL=http://localhost:3000 PLAYWRIGHT_C2_BASE_URL=http://localhost:8001 npm --prefix frontend run test:e2e -- f0028-module-browser-ui.spec.ts`
