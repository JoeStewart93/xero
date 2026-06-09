# F0027: Realtime Results UI

## Metadata
| Field | Value |
|---|---|
| ID | F0027 |
| Priority | P0 |
| Status | Planned |
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
- [ ] StreamOutput component appends chunks to display buffer
- [ ] Auto-scroll enabled by default; pause on manual scroll up
- [ ] Clear buffer button resets display

### Stage 2: WebSocket binding
**Goal:** Subscribe to task result events by task_id.
**Acceptance Criteria:**
- [ ] task.result.chunk events routed to correct stream panel
- [ ] task.result.complete event marks stream finished
- [ ] Multiple panels supported for concurrent tasks

### Stage 3: Notifications
**Goal:** Toast alerts for completions when panel not focused.
**Acceptance Criteria:**
- [ ] Browser notification permission requested on first use
- [ ] Toast shows task module and beacon on completion
- [ ] Click toast navigates to task result detail

## Feature Acceptance Criteria

- [ ] Port scan progress visible line-by-line during execution
- [ ] Auto-scroll pauses when operator scrolls up to review output
- [ ] Completion toast appears when operator is on different page

## Test Plan

### Unit Tests
- [ ] test_stream_append_chunk
- [ ] test_auto_scroll_pause_on_scroll_up
- [ ] test_chunk_routing_by_task_id
- [ ] test_complete_event_marks_stream_done
- [ ] test_reconnect_resumes_from_sequence

### System / Integration Tests
- [ ] Dispatch long-running scan; chunks appear in stream before complete
- [ ] WebSocket disconnect/reconnect resumes stream without duplicate lines
- [ ] Two concurrent tasks stream to separate panels

### Playwright Tests
- [ ] Running task shows streaming output updating in real time
- [ ] Scroll up pauses auto-scroll; new lines do not jump view
- [ ] Task completion toast appears and links to full result
