# F0014: Task Queue

## Metadata
| Field | Value |
|---|---|
| ID | F0014 |
| Priority | P0 |
| Status | Planned |
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

## Stages

### Stage 1: Queue data model
**Goal:** Define task schema in PostgreSQL with Redis queue pointer.
**Acceptance Criteria:**
- [ ] tasks table stores id, beacon_id, module, args, status, priority
- [ ] Redis list key task:queue:{beacon_id} holds pending task IDs
- [ ] Task creation writes DB record then enqueues Redis ID

### Stage 2: Enqueue and dispatch
**Goal:** Operator enqueues task; beacon poll receives next task.
**Acceptance Criteria:**
- [ ] POST /api/v1/tasks creates queued task for target beacon
- [ ] Beacon poll dequeues highest-priority pending task
- [ ] Status transitions queued -> dispatched on delivery

### Stage 3: Cancellation and history
**Goal:** Support cancel pending tasks and retain history.
**Acceptance Criteria:**
- [ ] DELETE /api/v1/tasks/{id} cancels if still queued
- [ ] Running tasks cannot be cancelled via API
- [ ] Completed tasks retained with 30-day default retention

## Feature Acceptance Criteria

- [ ] Operator can queue task and beacon receives it on next poll
- [ ] Priority ordering delivers urgent tasks before normal
- [ ] Cancelled queued task never dispatched to beacon

## Test Plan

### Unit Tests
- [ ] test_enqueue_task_adds_to_redis_queue
- [ ] test_priority_ordering_urgent_first
- [ ] test_dispatch_updates_status_to_dispatched
- [ ] test_cancel_queued_task_removes_from_queue
- [ ] test_cancel_running_task_returns_409

### System / Integration Tests
- [ ] Enqueue 3 tasks; beacon poll receives highest priority first
- [ ] Cancel queued task; subsequent poll skips cancelled task
- [ ] Task history query returns completed tasks for beacon

### Playwright Tests
- [ ] Queue task from UI; task appears in pending state for beacon
- [ ] Cancel pending task; status shows Cancelled in task list
- [ ] Task history tab shows completed tasks with timestamps
