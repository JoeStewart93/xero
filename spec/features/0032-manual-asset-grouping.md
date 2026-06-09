# F0032: Manual Asset Grouping

## Metadata
| Field | Value |
|---|---|
| ID | F0032 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 4 |
| Depends on | F0030 |

## Summary
Operator-defined asset groups with custom names, tags, nested hierarchy, and drag-and-drop assignment for organizing assets beyond automatic grouping rules.

## Requirements
- CRUD API for manual groups with name, description, parent_id
- Tags and labels on assets for custom categorization
- Nested groups up to 5 levels deep
- Bulk assign/remove assets from groups via API
- Manual groups distinct from auto-groups in UI

## Stages

### Stage 1: Manual group schema
**Goal:** Extend asset_groups with type=manual and nesting.
**Acceptance Criteria:**
- [ ] asset_groups.type enum: auto, manual
- [ ] parent_id FK enables nested group hierarchy
- [ ] tags table with many-to-many asset_tags link

### Stage 2: Group CRUD API
**Goal:** Endpoints for manual group management.
**Acceptance Criteria:**
- [ ] POST /api/v1/groups creates manual group
- [ ] PUT /groups/{id}/assets bulk assigns asset IDs
- [ ] DELETE group removes group but not assets

### Stage 3: Tag management
**Goal:** Add/remove tags on assets.
**Acceptance Criteria:**
- [ ] POST /assets/{id}/tags adds tag labels
- [ ] Filter assets by tag via ?tag= query param
- [ ] Tags displayed as chips in asset list

## Feature Acceptance Criteria

- [ ] Operator creates team group and assigns 5 assets via API
- [ ] Nested group hierarchy renders correctly up to 5 levels
- [ ] Tag filter returns only assets with specified tag

## Test Plan

### Unit Tests
- [ ] test_create_manual_group
- [ ] test_nested_group_hierarchy
- [ ] test_bulk_assign_assets
- [ ] test_tag_add_and_filter
- [ ] test_delete_group_preserves_assets

### System / Integration Tests
- [ ] Create manual group; assign assets; membership persists
- [ ] Nested child group inherits no automatic assets from parent
- [ ] Tag filter API matches UI filter results

### Playwright Tests
- [ ] Create new manual group from Assets page
- [ ] Drag asset onto group in sidebar to assign
- [ ] Filter assets by tag chip click
