# F0028: Inventory / Module Browser UI

## Metadata
| Field | Value |
|---|---|
| ID | F0028 |
| Priority | P0 |
| Status | Planned |
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
The Inventory side tab is visible today as a planned, disabled navigation item. This feature remains **Planned**; `/inventory` must not be considered implemented until this spec is completed.

## Stages

### Stage 1: Module catalog
**Goal:** Fetch and display module registry from API.
**Acceptance Criteria:**
- [ ] Inventory route at `/inventory` is enabled once C2 connection prerequisites are satisfied
- [ ] GET /api/v1/modules returns name, category, description, schema
- [ ] Card grid layout with category badges
- [ ] Search by module name or description

### Stage 2: Module detail
**Goal:** Detail view with schema and examples.
**Acceptance Criteria:**
- [ ] Args schema rendered as documented parameter table
- [ ] Example task JSON copyable to clipboard
- [ ] Launch Task navigates to task form with module pre-selected

### Stage 3: Plugin modules
**Goal:** Distinguish builtin vs plugin module sources.
**Acceptance Criteria:**
- [ ] Plugin modules show author and version badge
- [ ] Disabled plugins grayed out with reason tooltip
- [ ] Hot-reload indicator when plugin updated (links F0043)

## Feature Acceptance Criteria

- [ ] All builtin modules visible with accurate arg documentation
- [ ] Launch Task from portscan module opens pre-filled task form
- [ ] Plugin modules appear after plugin registration

## Test Plan

### Unit Tests
- [ ] test_module_list_renders_cards
- [ ] test_module_detail_renders_schema_table
- [ ] test_launch_task_prefills_form
- [ ] test_category_filter
- [ ] test_plugin_badge_rendered

### System / Integration Tests
- [ ] Modules API list matches UI catalog count
- [ ] Launch task from module creates valid queued task
- [ ] New plugin registration appears in module list after refresh

### Playwright Tests
- [ ] Inventory page lists Port Scan and Service Enum cards
- [ ] Open module detail shows args schema and example JSON
- [ ] Launch Task button opens task form with module selected
