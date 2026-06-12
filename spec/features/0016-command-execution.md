# F0016: Command Execution

## Metadata
| Field | Value |
|---|---|
| Feature Number | F0016 |
| Description | Add the operator-facing shell command execution contract on top of the task queue and Go beacon lifecycle. |
| Summary | Operators can enqueue one-shot shell commands with shell type, priority, and timeout controls; C2 validates and dispatches those tasks, records lifecycle audit events, and exposes searchable command history. |
| Value | Gives operators a verified command execution workflow while preserving a clean boundary for durable result bodies and richer result UI in later features. |
| Story Points | 5 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 3 |
| Dependencies | F0014, F0015 |

## Use Cases
- An operator opens a beacon, queues `whoami`, and sees the task move through the lifecycle.
- An operator sets a short timeout on a long-running command and sees the task fail cleanly.
- An operator searches recent command history by command text and status.
- A reviewer inspects task audit events to confirm who queued or cancelled a command and when the beacon reported lifecycle updates.

## Assumptions
- The public module name remains `shell`; no `builtin.shell` rename is introduced in F0016.
- F0015 already provides Go beacon shell execution and capped TASK_RESULT stdout/stderr fields.
- F0016 stores task lifecycle and audit metadata only; stdout/stderr result body persistence, chunking, and downloads remain F0017.
- Full task result viewing and task execution workspace improvements remain F0026/F0027.
- Audit actor identity uses the C2 token subject when available, with an explicit UI-client fallback for local C2 sessions.

## Stages

### Stage 1: Shell Task Contract
**Scope:** Validate operator shell task creation and preserve the task queue dispatch contract.

**Acceptance Criteria:**
- [x] Task args schema supports `command`, `shell_type`, and `timeout_seconds`.
- [x] Public module contract is `shell`.
- [x] Validation rejects empty commands and excessive timeout values.
- [x] POST `/api/v1/tasks` returns a task id for status polling.

### Stage 2: Beacon Lifecycle Integration
**Scope:** Verify the Go beacon executes shell tasks and C2 applies lifecycle updates without persisting result bodies.

**Acceptance Criteria:**
- [x] Beacon spawns shell commands with timeout enforcement.
- [x] Beacon reports `running` followed by terminal `completed` or `failed` status.
- [x] C2 updates task lifecycle timestamps from TASK_RESULT frames.
- [x] C2 task API responses do not expose stdout/stderr before F0017 result storage.

### Stage 3: Command Audit And Search API
**Scope:** Persist command lifecycle audit events and expose command history filters.

**Acceptance Criteria:**
- [x] C2 stores task audit events with task id, beacon id, module, command, actor subject, event type, status, metadata, and timestamp.
- [x] Queue, dispatch, requeue, cancel, running, completed, and failed transitions are auditable.
- [x] GET `/api/v1/tasks` filters by command text, beacon, status, and limit.
- [x] GET `/api/v1/tasks/{task_id}/audit` returns recent audit events for an authenticated operator.
- [x] C2 OpenAPI spec documents the command filter and audit endpoint.

### Stage 4: Operator Command History UI
**Scope:** Improve the Beacons command queue modal for searchable history.

**Acceptance Criteria:**
- [x] Command queue modal can create shell tasks with shell type, priority, and timeout controls.
- [x] Command history can be searched by command text.
- [x] Command history can be filtered by task status.
- [x] Task rows show lifecycle status and relative lifecycle timing.
- [x] Queued tasks remain cancellable from the modal.

### Stage 5: Validation And Maintainability
**Scope:** Verify behavior, update docs, and review whether a refactor round is needed.

**Acceptance Criteria:**
- [x] Backend unit tests pass.
- [x] Frontend lint, unit tests, and build pass.
- [x] C2 OpenAPI export/check pass.
- [x] Compose C2 integration verifies Go beacon command lifecycle, timeout status, and command search.
- [x] Maintainability review completed with task audit helpers separated into `xero_c2.task_audit`.

## Feature Acceptance Criteria

- [x] Operator can dispatch a shell command and receive task lifecycle status within a beacon cycle.
- [x] Timed-out command returns failed lifecycle status.
- [x] Command history is searchable in the task list API and Beacons command modal.
- [x] Task audit events store operator/beacon actor, command, timestamp, and lifecycle metadata.
- [x] Result body storage/download behavior is explicitly deferred to F0017.

## Test Plan

### Unit Tests
- [x] Shell task schema validation.
- [x] Timeout validation.
- [x] Task lifecycle status updates from TASK_RESULT frames.
- [x] Audit log records operator and command.
- [x] Audit log records beacon lifecycle metadata without stdout/stderr persistence.
- [x] Command history filters by command.
- [x] API client calls command filter and task audit endpoints.
- [x] Beacons command modal filters history by command and status.

### System / Integration Tests
- [x] Dispatch shell task through C2 and Go beacon; beacon reports terminal status.
- [x] Dispatch timed command with short timeout; task fails with timeout status.
- [x] Command history search returns the expected task without exposing stdout/stderr bodies.

### Browser / UI Tests
- [x] Task UI: enter command, select beacon, submit shows queued history.
- [x] Task UI: queued task can be cancelled.
- [x] Task UI: command history search and status filter call the filtered API path.
- [x] Browser sanity check confirms the command modal layout remains usable after the history controls were added.
