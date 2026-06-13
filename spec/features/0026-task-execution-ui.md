# F0026: Task Execution UI

## Metadata
| Field | Value |
|---|---|
| ID | F0026 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 3 |
| Depends on | F0024, F0016 |

## Summary
Task creation and monitoring interface supporting module selection, argument forms, beacon targeting, queue status, and result viewing for one-shot task operations.

## Current Implementation Note
The current navigation does not expose a standalone Tasks side tab. Task execution UI should be introduced through the Recon/tasking workflow or an explicitly approved future route, and must remain gated on an authenticated C2 backend connection.

## Completion Note
Implemented through the Beacons workflow without adding a standalone Tasks side tab. The task execution panel loads beacon-task modules from `/api/v1/modules`, renders module argument fields from JSON schema, supports target selection by dropdown and beacon-row drag/drop, and shows task lifecycle/detail/result state in the same view.

## Requirements
- FR-09: Drag-and-drop task deployment to specific beacons
- Task creation form with module picker and dynamic args
- Task list with status filters: queued, running, completed, failed
- Inline result viewer for completed tasks
- Drag beacon onto task form to set target

## Stages

### Stage 1: Task creation form
**Goal:** Module picker with dynamic argument fields.
**Acceptance Criteria:**
- [x] Module dropdown loads from /api/v1/modules
- [x] Args form renders per module JSON schema
- [x] Beacon target selectable via dropdown or drag-drop

### Stage 2: Task monitor
**Goal:** List and detail view for task lifecycle.
**Acceptance Criteria:**
- [x] Task list shows status, beacon, module, created_at
- [x] Click task opens detail with result viewer
- [x] Running tasks show spinner; failed show error reason

### Stage 3: Drag-and-drop
**Goal:** Drag beacon from sidebar onto task form.
**Acceptance Criteria:**
- [x] Beacon chip appears in target field on drop
- [x] Invalid drop target shows visual rejection feedback
- [x] Submit disabled until module, args, and target set

## Feature Acceptance Criteria

- [x] Operator creates shell task via form and sees result in same view
- [x] Drag beacon onto form sets target without manual selection
- [x] Task list filters to show only failed tasks for triage

## Test Plan

### Unit Tests
- [x] test_task_form_renders_module_args
- [x] test_task_submit_calls_api
- [x] test_task_list_status_filter
- [x] test_drag_drop_sets_beacon_target
- [x] test_result_viewer_renders_output

### System / Integration Tests
- [x] Create task via UI; beacon receives and completes task
- [x] Task status updates in list via WebSocket
- [x] Module args validation errors shown inline in form

### Playwright Tests
- [x] Create shell task from the tasking surface; status progresses to Complete
- [x] Drag beacon onto task form sets target chip
- [x] Filter task list to Failed; only failed tasks shown
