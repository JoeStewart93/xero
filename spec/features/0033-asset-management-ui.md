# F0033: Asset Management UI

## Metadata
| Field | Value |
|---|---|
| ID | F0033 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 4 |
| Depends on | F0030, F0032 |

## Summary
Assets page with inventory table, group sidebar, tag management, detail panel, and integration with automatic and manual grouping workflows.

## Requirements
- Assets list with columns: name, IP, OS, groups, tags, last_seen
- Group sidebar showing auto and manual groups with counts
- Asset detail panel with relationships and task history
- Drag-and-drop assignment to manual groups
- Merge duplicate assets UI workflow

## Stages

### Stage 1: Assets page layout
**Goal:** List + sidebar layout with group navigation.
**Acceptance Criteria:**
- [ ] Assets route at /assets with table and group sidebar
- [ ] Click group filters table to group members only
- [ ] All Assets view shows complete inventory

### Stage 2: Detail and actions
**Goal:** Asset detail with linked beacon and actions.
**Acceptance Criteria:**
- [ ] Detail panel shows metadata, groups, tags, scan history
- [ ] Quick action: dispatch task to linked beacon
- [ ] Merge duplicates flow selects canonical asset

### Stage 3: Drag-and-drop groups
**Goal:** Assign assets to manual groups via DnD.
**Acceptance Criteria:**
- [ ] Drag asset row onto group in sidebar assigns membership
- [ ] Visual feedback during drag operation
- [ ] Undo toast after assignment with 5s window

## Feature Acceptance Criteria

- [ ] Assets page shows all inventory with correct group counts in sidebar
- [ ] Drag asset to manual group updates membership immediately
- [ ] Asset detail links to beacon and shows recent tasks

## Test Plan

### Unit Tests
- [ ] test_assets_table_renders_columns
- [ ] test_group_sidebar_filter
- [ ] test_drag_drop_group_assignment
- [ ] test_asset_detail_renders_metadata
- [ ] test_merge_duplicates_flow

### System / Integration Tests
- [ ] Assets UI list matches GET /assets API
- [ ] Group filter shows same assets as API ?group_id= filter
- [ ] DnD assignment persists after page refresh

### Playwright Tests
- [ ] Assets page loads inventory with group sidebar
- [ ] Click subnet group filters table to members only
- [ ] Drag asset to manual group; count increments in sidebar
