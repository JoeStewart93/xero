# F0027: Realtime Results UI

## Metadata
| Field | Value |
|---|---|
| ID | F0027 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 3 |
| Depends on | F0008, F0017 |

## Summary
Live result streaming panel that displays task output chunks and session data as they arrive via operator WebSocket, without waiting for task completion.

## Requirements
- Stream task result chunks to UI as they arrive
- Auto-scroll terminal/output panel with scroll-lock toggle
- Support concurrent streams for multiple active tasks
- Notification toast on task completion while on other page
- Reconnect resumes stream from last received chunk sequence

## Stages

### Stage 1: Stream component
**Goal:** Reusable streaming output panel component.
**Acceptance Criteria:**
- [x] StreamOutput component appends chunks to display buffer
- [x] Auto-scroll enabled by default; pause on manual scroll up
- [x] Clear buffer button resets display

### Stage 2: WebSocket binding
**Goal:** Subscribe to task result events by task_id.
**Acceptance Criteria:**
- [x] task.result.chunk events routed to correct stream panel
- [x] task.result.completed event marks stream finished
- [x] Multiple panels supported for concurrent tasks

### Stage 3: Notifications
**Goal:** Toast alerts for completions when panel not focused.
**Acceptance Criteria:**
- [x] Browser notification permission requested on first use
- [x] Toast shows task module and beacon on completion
- [x] Click toast navigates to task result detail

## Feature Acceptance Criteria

- [x] Port scan progress visible line-by-line during execution
- [x] Auto-scroll pauses when operator scrolls up to review output
- [x] Completion toast appears when operator is on different page

## Test Plan

### Unit Tests
- [x] test_stream_append_chunk
- [x] test_auto_scroll_pause_on_scroll_up
- [x] test_chunk_routing_by_task_id
- [x] test_complete_event_marks_stream_done
- [x] test_reconnect_resumes_from_sequence

### System / Integration Tests
- [x] Dispatch long-running scan; chunks appear in stream before complete
- [x] WebSocket disconnect/reconnect resumes stream without duplicate lines
- [x] Two concurrent tasks stream to separate panels

### Playwright Tests
- [x] Running task shows streaming output updating in real time
- [x] Scroll up pauses auto-scroll; new lines do not jump view
- [x] Task completion toast appears and links to full result
