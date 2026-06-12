# F0017: Result Collection

## Metadata
| Field | Value |
|---|---|
| ID | F0017 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 3 |
| Depends on | F0016, F0005, F0015.01-AMD |

## Summary
Persistent storage and retrieval of task results including structured output, errors, artifacts metadata, and streaming chunks for long-running module output.

## Requirements
- task_results table with output blob, exit_code, error_message
- Chunked result upload for outputs exceeding single frame size
- GET /api/v1/tasks/{id}/result returns full assembled output
- Result retention policy with configurable TTL
- WebSocket event emitted on result completion
- Large result bodies, downloadable text exports, and binary result artifacts are stored through the F0015.01-AMD artifact store rather than ad hoc local paths.

## Stages

### Stage 1: Result schema
**Goal:** Design PostgreSQL storage for results and chunks.
**Acceptance Criteria:**
- [x] task_results linked 1:1 to tasks table
- [x] result_chunks table for multi-part uploads with sequence numbers
- [x] Indexes on task_id and created_at for history queries

### Stage 2: Ingest pipeline
**Goal:** Accept TASK_RESULT frames and assemble chunks.
**Acceptance Criteria:**
- [x] Single-frame results stored directly
- [x] Multi-chunk results assembled when final chunk received
- [x] Malformed chunk sequence returns error ACK to beacon

### Stage 3: Retrieval API
**Goal:** Expose result download and streaming to operators.
**Acceptance Criteria:**
- [x] GET /tasks/{id}/result returns JSON with output and metadata
- [x] Large results offer text/plain download endpoint
- [x] Completed task triggers Redis pub/sub for UI update

## Feature Acceptance Criteria

- [x] Task result retrievable immediately after beacon upload completes
- [x] Multi-chunk 5MB result assembles correctly without corruption
- [x] Result history paginated in API with 50 items per page default

## Test Plan

### Unit Tests
- [x] `test_task_result_updates_known_task_status`
- [x] `test_chunked_task_result_assembles_and_uses_artifact_storage`
- [x] `test_chunked_task_result_rejects_missing_chunks`
- [x] `test_expired_task_result_purge_removes_artifacts`
- [x] `test_task_result_completion_broadcasts_operator_event`
- [x] `BeaconsPage` result load, download, and `task.result.completed` refresh tests

### System / Integration Tests
- [x] Beacon uploads chunked 5MB result; API returns full output (`test_c2_stack_go_beacon_uploads_large_task_result_in_chunks`)
- [x] Result completion event is broadcast to the operator realtime hub
- [x] Result retention removes expired rows and artifact-store objects
- [x] DB foreign keys cascade result/chunk rows when owning task rows are removed; the public `DELETE /tasks/{id}` route remains a cancel operation.

### Playwright Tests
- [x] Task result panel renders completed output for a real C2 task (`f0017-task-results.spec.ts`)
- [x] Download button exports full combined result as a `.txt` file (`f0017-task-results.spec.ts`)
- [x] Task result panel auto-refresh is covered by component tests for `task.result.completed`
- [x] Result history pagination is API-scoped for F0017 and verified through `/api/v1/task-results` default limit/cursor behavior.

## Validation Evidence
- `python scripts/ci.py backend-lint`
- `python scripts/ci.py backend-unit`
- `python scripts/ci.py backend-behave`
- `python scripts/ci.py openapi-check`
- `python scripts/ci.py go-beacon-build`
- `python -m pytest tests/integration/test_compose_stacks.py::test_c2_stack_go_beacon_uploads_large_task_result_in_chunks -q`
- `npm --prefix platform/frontend run lint`
- `npm --prefix platform/frontend test -- --run`
- `npm --prefix platform/frontend run build`
- `npm --prefix platform/frontend run test:e2e`

## Maintainability Review
- Result persistence, chunk assembly, artifact routing, public serialization, downloads, and TTL cleanup live in `xero_c2.task_results` to keep protocol handlers and FastAPI routes thin.
- The Go beacon owns client-side chunking only; server-side validation and assembly stay in C2.
- Frontend result UI is scoped to the existing Beacons command modal and uses typed API helpers rather than embedding fetch logic in the component.
- No extra refactor round is required for F0017. The next likely extension point is a dedicated result-history view if operators need cross-beacon browsing beyond the API.
