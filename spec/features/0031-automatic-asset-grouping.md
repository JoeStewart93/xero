# F0031: Automatic Asset Grouping

## Metadata
| Field | Value |
|---|---|
| ID | F0031 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 4 |
| Depends on | F0030 |

## Summary
Rules engine that automatically assigns assets to groups based on network topology, domain membership, OS version, installed services, and geographic IP location.

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
- [ ] Subnet rule groups assets by /24 network prefix
- [ ] Domain rule groups by AD domain or workgroup
- [ ] OS rule groups by os_family and os_version major

### Stage 2: Rule configuration
**Goal:** API and seed data for default grouping rules.
**Acceptance Criteria:**
- [ ] GET/PUT /api/v1/grouping/rules for rule management
- [ ] Default rules enabled for subnet, domain, OS on install
- [ ] Manual re-group POST /api/v1/grouping/rerun

### Stage 3: Membership sync
**Goal:** Maintain asset_group_membership without duplicates.
**Acceptance Criteria:**
- [ ] Asset can belong to multiple auto-groups
- [ ] Rule disable removes future assignments; optional purge
- [ ] Grouping events logged for audit

## Feature Acceptance Criteria

- [ ] Assets in same /24 subnet auto-assigned to subnet group
- [ ] Domain-joined assets grouped separately from workgroup hosts
- [ ] Rule change triggers re-group within 60s for all assets

## Test Plan

### Unit Tests
- [ ] test_subnet_grouping_rule
- [ ] test_domain_grouping_rule
- [ ] test_os_version_grouping_rule
- [ ] test_multi_group_membership
- [ ] test_rule_disable_stops_new_assignments

### System / Integration Tests
- [ ] Create assets in same subnet; both appear in subnet group
- [ ] Change subnet rule prefix length; memberships update on rerun
- [ ] Disable OS rule; new assets not added to OS groups

### Playwright Tests
- [ ] Asset groups panel shows auto-generated subnet groups
- [ ] Group membership count matches assets in that subnet
- [ ] Settings grouping rules page shows enabled/disabled toggles
