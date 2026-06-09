# F0046: Distributed Scan Orchestration

## Metadata
| Field | Value |
|---|---|
| ID | F0046 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 5 |
| Depends on | F0022, F0045, F0017 |

## Summary
Coordinate scan execution across the embedded C2 scanner, selected external scanner workers, or a distributed scanner pool. Large scans can be split into shards, retried or reassigned on worker failure, and merged into one operator-visible result set.

## Requirements
- Scan requests support execution target `auto`, specific scanner, or distributed pool
- C2 validates targets against active project scope before creating scan jobs
- Distributed scans split work into shards with progress tracking
- Failed shards can be retried or reassigned to healthy scanners
- Final results are merged and deduplicated while preserving shard provenance

## Stages

### Stage 1: Scan job model
**Goal:** Represent scanner target selection and job lifecycle.
**Acceptance Criteria:**
- [ ] `scan_jobs` tracks project, operator, scan type, execution target, status, progress, and summary
- [ ] `scan_shards` tracks parent job, assigned scanner, shard scope, status, and result reference
- [ ] `auto` uses embedded scanner unless policy selects an external scanner

### Stage 2: Sharding and assignment
**Goal:** Split eligible scans across scanner workers.
**Acceptance Criteria:**
- [ ] Target lists and port ranges can be split into deterministic shards
- [ ] Assignment uses only healthy scanner workers with required capabilities
- [ ] Scanner failure triggers shard retry or reassignment

### Stage 3: Result merge and progress
**Goal:** Present distributed work as one scan to the operator.
**Acceptance Criteria:**
- [ ] Shard progress updates roll up to parent scan progress
- [ ] Duplicate host/port/service findings are merged deterministically
- [ ] Final result preserves scanner and shard provenance for audit

## Feature Acceptance Criteria

- [ ] Operator can run a scan using embedded scanner default
- [ ] Operator can select a specific external scanner for a scan
- [ ] One scan can be distributed across multiple healthy scanners and return merged results

## Test Plan

### Unit Tests
- [ ] test_scan_execution_target_validation
- [ ] test_scan_shard_split_deterministic
- [ ] test_assigns_only_capable_healthy_scanners
- [ ] test_failed_shard_reassignment
- [ ] test_result_merge_deduplicates_findings

### System / Integration Tests
- [ ] Run scan with embedded scanner and receive complete result
- [ ] Run scan on selected external scanner and verify assignment
- [ ] Run distributed scan across three scanners; kill one; remaining shards complete

### Playwright Tests
- [ ] Recon scan form supports scanner target selection
- [ ] Distributed scan progress rolls up across shards
- [ ] Merged result table shows scanner/shard provenance on detail view
