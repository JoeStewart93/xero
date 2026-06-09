# F0026: Task Execution UI

## Metadata
| Field | Value |
|---|---|
| ID | F0026 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 3 |
| Depends on | F0024, F0016 |

## Summary
Task creation and monitoring interface supporting module selection, argument forms, beacon targeting, queue status, and result viewing for one-shot task operations.

## Current Implementation Note
The current navigation does not expose a standalone Tasks side tab. Task execution UI should be introduced through the Recon/tasking workflow or an explicitly approved future route, and must remain gated on an authenticated C2 backend connection.

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
- [ ] Module dropdown loads from /api/v1/modules
- [ ] Args form renders per module JSON schema
- [ ] Beacon target selectable via dropdown or drag-drop

### Stage 2: Task monitor
**Goal:** List and detail view for task lifecycle.
**Acceptance Criteria:**
- [ ] Task list shows status, beacon, module, created_at
- [ ] Click task opens detail with result viewer
- [ ] Running tasks show spinner; failed show error reason

### Stage 3: Drag-and-drop
**Goal:** Drag beacon from sidebar onto task form.
**Acceptance Criteria:**
- [ ] Beacon chip appears in target field on drop
- [ ] Invalid drop target shows visual rejection feedback
- [ ] Submit disabled until module, args, and target set

## Feature Acceptance Criteria

- [ ] Operator creates shell task via form and sees result in same view
- [ ] Drag beacon onto form sets target without manual selection
- [ ] Task list filters to show only failed tasks for triage

## Test Plan

### Unit Tests
- [ ] test_task_form_renders_module_args
- [ ] test_task_submit_calls_api
- [ ] test_task_list_status_filter
- [ ] test_drag_drop_sets_beacon_target
- [ ] test_result_viewer_renders_output

### System / Integration Tests
- [ ] Create task via UI; beacon receives and completes task
- [ ] Task status updates in list via WebSocket
- [ ] Module args validation errors shown inline in form

### Playwright Tests
- [ ] Create shell task from the tasking surface; status progresses to Complete
- [ ] Drag beacon onto task form sets target chip
- [ ] Filter task list to Failed; only failed tasks shown
