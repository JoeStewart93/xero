# F0025: Beacon Management UI

## Metadata
| Field | Value |
|---|---|
| ID | F0025 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 3 |
| Depends on | F0024, F0009 |

## Summary
Full beacon management interface with sortable list, detail panel, status filters, profile assignment, and contextual actions for tasking and sessions.

## Current Implementation Note
F0009 enables the Beacons side tab and `/beacons` overview/detail route for connected C2 backends. This feature remains **Planned** for the richer management workspace: sorting, filtering, search, profile assignment, contextual task/session actions, kill workflow, and CSV export.

## Requirements
- Beacons list page with sort, filter, and search
- Beacon detail panel: metadata, last seen, transport, profile
- Context actions: task, shell, file browser, registry, kill
- Bulk selection for multi-beacon task dispatch (P1 stretch)
- Export beacon inventory as CSV

## Stages

### Stage 1: Beacon list
**Goal:** Table view with status badges and sorting.
**Acceptance Criteria:**
- [x] Beacons route at `/beacons` is enabled once C2 connection prerequisites are satisfied
- [ ] List columns: hostname, OS, status, last_seen, transport
- [ ] Filter by status online/offline/all
- [ ] Search by hostname or IP substring

### Stage 2: Detail panel
**Goal:** Slide-over or page showing full beacon metadata.
**Acceptance Criteria:**
- [ ] Detail shows registration metadata and profile assignment
- [ ] Activity timeline of recent tasks and sessions
- [ ] Kill beacon sends SESSION_CLOSE and marks removed

### Stage 3: Context actions
**Goal:** Action menu per beacon row.
**Acceptance Criteria:**
- [ ] Actions menu: New Task, Shell, File Browser, Registry
- [ ] Kill action with confirmation modal
- [ ] CSV export of visible beacon list

## Feature Acceptance Criteria

- [ ] Operator finds beacon by hostname search in under 3 keystrokes
- [ ] Beacon detail shows accurate last_seen and transport mode
- [ ] Kill beacon removes from active list and closes sessions

## Test Plan

### Unit Tests
- [ ] test_beacon_list_sort_by_last_seen
- [ ] test_beacon_filter_online
- [ ] test_beacon_search_hostname
- [ ] test_detail_panel_renders_metadata
- [ ] test_kill_beacon_api_call

### System / Integration Tests
- [ ] Beacon list matches GET /beacons API response
- [ ] Kill beacon; subsequent list excludes killed beacon
- [ ] Profile assignment persists after page refresh

### Playwright Tests
- [ ] Beacons page lists all registered beacons with status badges
- [ ] Search filters beacon list by hostname
- [ ] Open beacon detail; metadata matches API data
- [ ] Kill beacon with confirmation removes from list
