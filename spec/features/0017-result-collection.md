# F0017: Result Collection

## Metadata
| Field | Value |
|---|---|
| ID | F0017 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 3 |
| Depends on | F0016, F0005 |

## Summary
Persistent storage and retrieval of task results including structured output, errors, artifacts metadata, and streaming chunks for long-running module output.

## Requirements
- task_results table with output blob, exit_code, error_message
- Chunked result upload for outputs exceeding single frame size
- GET /api/v1/tasks/{id}/result returns full assembled output
- Result retention policy with configurable TTL
- WebSocket event emitted on result completion

## Stages

### Stage 1: Result schema
**Goal:** Design PostgreSQL storage for results and chunks.
**Acceptance Criteria:**
- [ ] task_results linked 1:1 to tasks table
- [ ] result_chunks table for multi-part uploads with sequence numbers
- [ ] Indexes on task_id and created_at for history queries

### Stage 2: Ingest pipeline
**Goal:** Accept TASK_RESULT frames and assemble chunks.
**Acceptance Criteria:**
- [ ] Single-frame results stored directly
- [ ] Multi-chunk results assembled when final chunk received
- [ ] Malformed chunk sequence returns error ACK to beacon

### Stage 3: Retrieval API
**Goal:** Expose result download and streaming to operators.
**Acceptance Criteria:**
- [ ] GET /tasks/{id}/result returns JSON with output and metadata
- [ ] Large results offer text/plain download endpoint
- [ ] Completed task triggers Redis pub/sub for UI update

## Feature Acceptance Criteria

- [ ] Task result retrievable immediately after beacon upload completes
- [ ] Multi-chunk 5MB result assembles correctly without corruption
- [ ] Result history paginated in API with 50 items per page default

## Test Plan

### Unit Tests
- [ ] test_result_store_single_frame
- [ ] test_result_chunk_assembly_order
- [ ] test_result_missing_chunks_rejected
- [ ] test_result_retrieval_api
- [ ] test_result_ttl_cleanup_job

### System / Integration Tests
- [ ] Beacon uploads chunked result; API returns full output
- [ ] Result completion event received on operator WebSocket
- [ ] Deleted task cascades result removal

### Playwright Tests
- [ ] Task result panel auto-updates when result arrives via WebSocket
- [ ] Download button exports full result as .txt file
- [ ] Result history pagination loads older results on scroll
