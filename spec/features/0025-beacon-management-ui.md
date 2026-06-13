# F0025: Beacon Management UI

## Metadata
| Field | Value |
|---|---|
| ID | F0025 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 3 |
| Depends on | F0024, F0009 |
| Story Points | 5 |

## Summary
Full beacon management interface with sortable list, detail panel, status filters, profile assignment, and contextual actions for tasking and sessions.

## Current Implementation Note
F0025 completes the richer Beacons management workspace on top of the F0009 `/beacons` route: sorting, filtering, search, profile assignment, contextual task/session actions, activity context, kill workflow, CSV export, and C2 soft-removal lifecycle support.

## Value
Gives operators a reliable inventory workspace for finding controlled systems, inspecting operational metadata, launching contextual workflows, exporting the visible roster, and safely removing stale or unwanted beacons.

## Assumptions
- F0025 completes the existing `/beacons` management surface rather than replacing it.
- Existing command queue, shell, file browser, registry, and traffic-profile workflows remain in scope only where needed to integrate with the richer management page.
- `Kill beacon` is an operator-initiated soft removal for this feature: it closes active interactive sessions, cancels queued tasks, hides the beacon from default active inventory, and publishes realtime state. It does not add OS-level agent process termination.
- CSV export is client-side and exports the currently visible filtered/sorted rows.
- Broader task execution UI remains owned by F0026.

## Implementation Scope
- Add C2 soft-removal lifecycle support and `POST /api/v1/beacons/{beacon_id}/kill`.
- Add explicit status filtering, URL-seeded offline filtering, CSV export, activity context, and kill confirmation to the Beacons page.
- Keep realtime transport generic; only add removal handling required to keep beacon inventory state correct.
- Update API specs and feature status documentation as implementation progresses.

## Requirements
- Beacons list page with sort, filter, and search
- Beacon detail panel: metadata, last seen, transport, profile
- Context actions: task, shell, file browser, registry, kill
- Export beacon inventory as CSV
- Deferred stretch: bulk selection for multi-beacon task dispatch remains outside F0025 and should be reconsidered with broader task orchestration work.

## Stages

### Stage 1: Beacon list
**Goal:** Table view with status badges and sorting.
**Acceptance Criteria:**
- [x] Beacons route at `/beacons` is enabled once C2 connection prerequisites are satisfied
- [x] List columns: hostname, OS, status, last_seen, transport
- [x] Filter by status online/offline/all
- [x] Search by hostname or IP substring

### Stage 2: Detail panel
**Goal:** Slide-over or page showing full beacon metadata.
**Acceptance Criteria:**
- [x] Detail shows registration metadata and profile assignment
- [x] Activity timeline of recent tasks and sessions
- [x] Kill beacon sends SESSION_CLOSE and marks removed

### Stage 3: Context actions
**Goal:** Action menu per beacon row.
**Acceptance Criteria:**
- [x] Actions menu: New Task, Shell, File Browser, Registry
- [x] Kill action with confirmation modal
- [x] CSV export of visible beacon list

## Feature Acceptance Criteria

- [x] Operator finds beacon by hostname search in under 3 keystrokes
- [x] Beacon detail shows accurate last_seen and transport mode
- [x] Kill beacon removes from active list and closes sessions

## Test Plan

### Unit Tests
- [x] test_beacon_list_sort_by_last_seen
- [x] test_beacon_filter_online
- [x] test_beacon_search_hostname
- [x] test_detail_panel_renders_metadata
- [x] test_kill_beacon_api_call

### System / Integration Tests
- [x] Beacon list matches GET /beacons API response
- [x] Kill beacon; subsequent list excludes killed beacon
- [x] Profile assignment persists after page refresh

### Playwright Tests
- [x] Beacons page lists all registered beacons with status badges
- [x] Search filters beacon list by hostname
- [x] Open beacon detail; metadata matches API data
- [x] Kill beacon with confirmation removes from list

## Validation Evidence
- `python -m pytest platform/tests/unit/test_c2_api.py -q` passed.
- `python -m pytest platform/tests/unit/test_persistence_split.py -q` passed.
- `npm --prefix platform/frontend test -- --run` passed.
- `npm --prefix platform/frontend run lint` passed.
- `npm --prefix platform/frontend run build` passed.
- `python platform/scripts/openapi.py check c2` passed.
- Full C2 and BFF/frontend Docker stacks were rebuilt and restarted with `--build --force-recreate`.
- Connected C2 Playwright validation passed with `e2e/f0025-beacon-management.spec.ts`.
