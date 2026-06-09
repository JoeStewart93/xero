# F0016: Command Execution

## Metadata
| Field | Value |
|---|---|
| ID | F0016 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 3 |
| Depends on | F0014, F0015 |

## Summary
Framework for dispatching one-shot shell commands to beacons, tracking execution lifecycle, and returning stdout/stderr with exit codes through the task queue and result pipeline.

## Requirements
- Built-in shell module: cmd, powershell, bash based on target OS
- Operator API POST /api/v1/tasks with module=shell and command arg
- Timeout enforcement per task with configurable max duration
- Large output truncation with downloadable full result option
- Command audit log stored with operator ID and timestamp

## Stages

### Stage 1: Shell module backend
**Goal:** Define shell task schema and dispatch contract.
**Acceptance Criteria:**
- [ ] Task args schema: command, shell_type, timeout_seconds
- [ ] Module registry entry for builtin.shell
- [ ] Validation rejects empty command and excessive timeout

### Stage 2: Beacon execution
**Goal:** Go beacon executes command and captures output.
**Acceptance Criteria:**
- [ ] Beacon spawns process with timeout watchdog
- [ ] stdout/stderr captured up to configurable byte limit
- [ ] Exit code included in TASK_RESULT frame

### Stage 3: Operator dispatch API
**Goal:** Wire task creation to shell module for operators.
**Acceptance Criteria:**
- [ ] POST /tasks with shell module enqueues for target beacon
- [ ] Task status progresses queued -> running -> completed
- [ ] API returns task_id for result polling

## Feature Acceptance Criteria

- [ ] Operator dispatches whoami; result shows username within one beacon sleep cycle
- [ ] Timed-out command returns partial output with timeout status
- [ ] Command history searchable by operator in task list

## Test Plan

### Unit Tests
- [ ] test_shell_task_schema_validation
- [ ] test_beacon_shell_execute_captures_output
- [ ] test_timeout_kills_process_and_returns_partial
- [ ] test_output_truncation_at_limit
- [ ] test_audit_log_records_operator_and_command

### System / Integration Tests
- [ ] Dispatch echo hello; beacon returns hello in result
- [ ] Dispatch sleep 120 with 5s timeout; task fails with timeout status
- [ ] Command result persisted and retrievable via GET /tasks/{id}

### Playwright Tests
- [ ] Task UI: enter command, select beacon, submit shows Queued status
- [ ] Completed task shows stdout in result panel
- [ ] Failed timeout task shows error badge and partial output
