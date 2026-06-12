# F0014: Task Queue

## Metadata
| Field | Value |
|---|---|
| ID | F0014 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 2 |
| Depends on | F0006, F0009 |

## Summary
Redis-backed per-beacon task queue with priority ordering, dispatch to connected beacons, status tracking, and operator API for enqueue and cancellation.

## Requirements
- Per-beacon Redis queue for pending tasks
- Task states: queued, dispatched, running, completed, failed, cancelled
- Priority levels: low, normal, high, urgent
- Operator API to enqueue, list, and cancel tasks
- Task dispatch integrates with WS and long-poll transports
- Shell-shaped task requests are accepted for queueing; actual shell execution remains F0016/F0015

## Stages

### Stage 1: Queue data model
**Goal:** Define task schema in PostgreSQL with Redis queue pointer.
**Acceptance Criteria:**
- [x] tasks table stores id, beacon_id, module, args, status, priority
- [x] Redis priority list keys `queue:beacon:{beacon_id}:{priority}` hold pending task IDs
- [x] Task creation writes DB record then enqueues Redis ID

### Stage 2: Enqueue and dispatch
**Goal:** Operator enqueues task; beacon poll receives next task.
**Acceptance Criteria:**
- [x] POST /api/v1/tasks creates queued task for target beacon
- [x] Beacon poll dequeues highest-priority pending task
- [x] Status transitions queued -> dispatched on delivery

### Stage 3: Cancellation and history
**Goal:** Support cancel pending tasks and retain history.
**Acceptance Criteria:**
- [x] DELETE /api/v1/tasks/{id} cancels if still queued
- [x] Running tasks cannot be cancelled via API
- [x] Completed tasks retained with 30-day default retention

## Feature Acceptance Criteria

- [x] Operator can queue task and beacon receives it on next poll
- [x] Priority ordering delivers urgent tasks before normal
- [x] Cancelled queued task never dispatched to beacon

## Test Plan

### Unit Tests
- [x] test_enqueue_task_adds_to_redis_queue
- [x] test_priority_ordering_urgent_first
- [x] test_dispatch_updates_status_to_dispatched
- [x] test_cancel_queued_task_removes_from_queue
- [x] test_cancel_running_task_returns_409

### System / Integration Tests
- [x] Enqueue 3 tasks; beacon poll receives highest priority first
- [x] Cancel queued task; subsequent poll skips cancelled task
- [x] Task history query returns completed tasks for beacon

### Playwright Tests
- [x] Queue task from UI; task appears in pending state for beacon
- [x] Cancel pending task; status shows Cancelled in task list
- [x] Task history tab shows completed tasks with timestamps

## Completion Notes

- Completed on June 12, 2026 with C2 task persistence, priority Redis queues, WebSocket/long-poll/protocol harness dispatch, lifecycle updates from `TASK_RESULT`, Beacons modal tasking UI, OpenAPI export/check, unit/integration/frontend/Playwright validation, and Docker compose sanity checks.
- Full task result body storage, chunking, command execution, and Go beacon execution remain with F0017, F0016, and F0015.
