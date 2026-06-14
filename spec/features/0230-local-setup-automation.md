# F0230: Local Setup Automation

## Metadata
| Field | Value |
|---|---|
| ID | F0230 |
| Priority | P1 |
| Status | Complete |
| MVP Phase | Developer Tooling |
| Depends on | F0001, F0003, F0009, F0048, F0049 |

## Summary
Create cross-platform local setup, smoke data seed, and smoke data cleanup scripts so a developer can clone Xero, start the Docker Compose stacks with one command, populate deterministic lab data, and remove that data safely between validation runs.

## Value
This reduces local onboarding friction, makes demos repeatable across Windows/macOS/Linux hosts, and keeps smoke artifacts from accumulating in shared local databases.

## Assumptions
- Docker Desktop or a Docker Engine with Compose v2 is installed.
- Default local credentials from `platform/.env.example` are acceptable for local-only development.
- Smoke data is identified by the `xero-smoke` prefix unless the caller provides a different safe prefix.
- Cleanup removes tagged smoke records from the C2 database and offers an explicit volume reset option for full local teardown.

## Requirements
- Provide a PowerShell one-command local installer.
- Provide a Bash one-command local installer.
- Provide PowerShell and Bash smoke data seed scripts.
- Provide PowerShell and Bash smoke data cleanup scripts.
- Keep setup aligned with the separate BFF, C2, handler, and scanner Compose stacks.

## Stages

### Stage 1: Local Install Entrypoints
**Goal:** Replace README-only Compose choreography with scripts.
**Acceptance Criteria:**
- [x] PowerShell script starts BFF and C2 stacks.
- [x] Bash script starts BFF and C2 stacks.
- [x] Scripts copy `platform/.env.example` to `platform/.env` only when missing.
- [x] Scripts support optional handler/scanner scaffold startup.
- [x] Scripts wait for frontend, BFF, and C2 readiness.

### Stage 2: Smoke Data Seed
**Goal:** Populate deterministic C2 smoke data through public APIs.
**Acceptance Criteria:**
- [x] PowerShell script registers and heartbeats smoke beacons.
- [x] Bash script registers and heartbeats smoke beacons.
- [x] Scripts create a smoke traffic profile and assign it to a beacon.
- [x] Scripts can queue sample shell tasks.
- [x] Scripts can register sample handler/scanner workers.

### Stage 3: Smoke Data Cleanup
**Goal:** Remove seeded data without wiping unrelated local state.
**Acceptance Criteria:**
- [x] PowerShell cleanup removes records matching the smoke prefix.
- [x] Bash cleanup removes records matching the smoke prefix.
- [x] Cleanup handles dependent task, asset, worker, profile, and beacon records.
- [x] Cleanup provides an explicit full volume reset option.

## Feature Acceptance Criteria

- [x] `scripts/install-local.ps1` and `scripts/install-local.sh` exist and are documented.
- [x] `scripts/smoke-data.ps1` and `scripts/smoke-data.sh` exist and are documented.
- [x] `scripts/clean-smoke-data.ps1` and `scripts/clean-smoke-data.sh` exist and are documented.
- [x] README local setup instructions are updated to make the scripts the primary path.
- [x] Script validation passes on the local Docker stack.

## Test Plan

### Unit Tests
- [x] PowerShell parser validation for script syntax.
- [x] Bash parser validation for script syntax.

### System / Integration Tests
- [x] Start local stacks with the install script.
- [x] Seed smoke data through C2 APIs.
- [x] Clean seeded smoke data through direct, prefix-scoped SQL cleanup.

### Playwright Tests
- [ ] Not required; this feature adds local tooling without changing browser behavior.
